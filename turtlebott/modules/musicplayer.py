"""
Music player module! Supports direct links, YouTube (including playlists), YouTube search, and local files.
Includes queueing, skip, pause/resume, playpause toggle, stop, volume control,
and a Now Playing embed with control buttons.
"""

import asyncio
import discord
from discord.ext import commands
from turtlebott.utils.logger import setup_logger
import yt_dlp
import urllib.parse
import os

logger = setup_logger("music")

FFMPEG_REMOTE_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
FFMPEG_LOCAL_OPTIONS = {
    "options": "-vn",
}

YTDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": False,  # IMPORTANT: allow playlists
    "extract_flat": False,
}


def format_duration(seconds: int | None) -> str:
    if not seconds or seconds <= 0:
        return "Unknown"

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class NowPlayingView(discord.ui.View):
    def __init__(self, cog: "Music", guild_id: int, *, timeout: float = 7200):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id

    def get_vc(self) -> discord.VoiceClient | None:
        return self.cog.voice_clients.get(self.guild_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Optional: require user to be in the same VC
        vc = self.get_vc()
        if not vc or not vc.is_connected():
            await interaction.response.send_message("Not connected.", ephemeral=True)
            return False

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("Join a voice channel first.", ephemeral=True)
            return False

        if vc.channel != interaction.user.voice.channel:
            await interaction.response.send_message("You must be in my voice channel.", ephemeral=True)
            return False

        return True

    @discord.ui.button(label="Pause/Play", style=discord.ButtonStyle.primary, emoji="⏯")
    async def pauseplay(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.get_vc()
        if not vc:
            await interaction.response.send_message("Not connected.", ephemeral=True)
            return

        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("Paused.", ephemeral=True)
            return

        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message("Resumed.", ephemeral=True)
            return

        await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.get_vc()
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.get_vc()
        if not vc:
            await interaction.response.send_message("Not connected.", ephemeral=True)
            return

        self.cog.queues[self.guild_id] = []

        if vc.is_playing() or vc.is_paused():
            vc.stop()

        await vc.disconnect()
        await interaction.response.send_message("Stopped, cleared queue, and disconnected.", ephemeral=True)


class Music(commands.Cog):
    """Music player cog supporting YouTube, playlists, direct links, local files, and YouTube search."""

    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.queues = {}   # guild_id -> list of tracks
        self.locks = {}    # guild_id -> asyncio.Lock()
        self.volumes = {}  # guild_id -> float (0.0 - 2.0)

    def get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    def get_volume(self, guild_id: int) -> float:
        return self.volumes.get(guild_id, 1.0)

    def set_volume(self, guild_id: int, volume: float):
        volume = max(0.0, min(volume, 2.0))
        self.volumes[guild_id] = volume

    async def connect_to_vc(self, ctx):
        if ctx.author.voice is None:
            await ctx.reply("You must be in a voice channel first!")
            return None

        channel = ctx.author.voice.channel
        vc = ctx.guild.voice_client

        if vc and vc.is_connected():
            return vc

        vc = await channel.connect()
        self.voice_clients[ctx.guild.id] = vc
        return vc

    def parse_file_url(self, url: str):
        if not url.startswith("file://"):
            return None

        path = urllib.parse.unquote(url[7:])
        if os.path.isfile(path):
            return path

        logger.error(f"File not found: {path}")
        return None

    def looks_like_url(self, text: str) -> bool:
        text = text.strip().lower()
        return text.startswith(("http://", "https://", "www.", "file://"))

    def extract_tracks(self, input_text: str, *, allow_search: bool):
        """
        Returns a list of track dicts.
        Each track dict contains:
          - title
          - webpage_url
          - stream_url
          - type: local/remote
          - ffmpeg_opts
          - duration
          - thumbnail
        """

        input_text = input_text.strip()

        # Local file support
        local_path = self.parse_file_url(input_text)
        if local_path:
            return [{
                "title": os.path.basename(local_path),
                "webpage_url": input_text,
                "stream_url": local_path,
                "type": "local",
                "ffmpeg_opts": FFMPEG_LOCAL_OPTIONS,
                "duration": None,
                "thumbnail": None,
            }]

        # If search is allowed, and it doesn't look like a URL, treat as YouTube search
        if allow_search and not self.looks_like_url(input_text):
            input_text = f"ytsearch:{input_text}"

        # If search is NOT allowed, reject non-URLs
        if not allow_search and not self.looks_like_url(input_text):
            return []

        try:
            with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                info = ydl.extract_info(input_text, download=False)

            # Playlist case
            if "entries" in info and info["entries"] and info.get("_type") == "playlist":
                tracks = []
                for entry in info["entries"]:
                    if not entry:
                        continue

                    if "url" not in entry or entry.get("_type") == "url":
                        with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                            entry = ydl.extract_info(entry["webpage_url"], download=False)

                    tracks.append({
                        "title": entry.get("title", "Unknown title"),
                        "webpage_url": entry.get("webpage_url", input_text),
                        "stream_url": entry["url"],
                        "type": "remote",
                        "ffmpeg_opts": FFMPEG_REMOTE_OPTIONS,
                        "duration": entry.get("duration"),
                        "thumbnail": entry.get("thumbnail"),
                    })

                return tracks

            # ytsearch case
            if "entries" in info and info["entries"]:
                entry = info["entries"][0]
                if not entry:
                    return []

                with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                    entry = ydl.extract_info(entry["webpage_url"], download=False)

                return [{
                    "title": entry.get("title", "Unknown title"),
                    "webpage_url": entry.get("webpage_url", input_text),
                    "stream_url": entry["url"],
                    "type": "remote",
                    "ffmpeg_opts": FFMPEG_REMOTE_OPTIONS,
                    "duration": entry.get("duration"),
                    "thumbnail": entry.get("thumbnail"),
                }]

            # Single video case
            return [{
                "title": info.get("title", "Unknown title"),
                "webpage_url": info.get("webpage_url", input_text),
                "stream_url": info["url"],
                "type": "remote",
                "ffmpeg_opts": FFMPEG_REMOTE_OPTIONS,
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
            }]

        except Exception as e:
            logger.error(f"Error fetching audio: {e}")
            return []

    async def send_now_playing_embed(self, channel: discord.abc.Messageable, guild_id: int, track: dict):
        title = track.get("title", "Unknown title")
        url = track.get("webpage_url")
        duration = format_duration(track.get("duration"))
        thumbnail = track.get("thumbnail")

        embed = discord.Embed(
            title="<a:music:1470271875581087923> Now Playing",
            description=f"[**{title}**]({url})" if url else f"**{title}**",
        )
        embed.add_field(name="Length", value=duration, inline=True)

        if thumbnail and isinstance(thumbnail, str) and thumbnail.startswith("http"):
            embed.set_thumbnail(url=thumbnail)

        view = NowPlayingView(self, guild_id)

        await channel.send(embed=embed, view=view)

    async def play_next(self, guild_id: int, text_channel: discord.abc.Messageable):
        lock = self.get_lock(guild_id)

        async with lock:
            vc = self.voice_clients.get(guild_id)
            if not vc or not vc.is_connected():
                return

            queue = self.queues.get(guild_id, [])
            if not queue:
                await text_channel.send("Queue finished.")
                return

            track = queue.pop(0)

            def after_play(err):
                if err:
                    logger.error(f"Player error: {err}")

                fut = asyncio.run_coroutine_threadsafe(
                    self.play_next(guild_id, text_channel),
                    self.bot.loop
                )
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"Error scheduling next track: {e}")

            source = discord.FFmpegPCMAudio(track["stream_url"], **track["ffmpeg_opts"])
            source = discord.PCMVolumeTransformer(source, volume=self.get_volume(guild_id))

            vc.play(source, after=after_play)

            await self.send_now_playing_embed(text_channel, guild_id, track)

    @commands.hybrid_command(
        name="play",
        description="Play a song or playlist from YouTube, direct URL, local file, or search query"
    )
    async def play(self, ctx, *, input_text: str):
        logger.info(f"User {ctx.author} invoked play with: {input_text}")

        vc = await self.connect_to_vc(ctx)
        if not vc:
            return
        
        ctx.reply("<a:loading:1470271877992677396> Processing links...")

        tracks = self.extract_tracks(input_text, allow_search=True)
        if not tracks:
            await ctx.reply("Failed to get audio source.")
            return

        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = []

        self.queues[ctx.guild.id].extend(tracks)

        if len(tracks) == 1:
            await ctx.reply(f"Queued: **{tracks[0]['title']}**")
        else:
            await ctx.reply(f"Queued playlist: **{len(tracks)} tracks**")

        if not vc.is_playing() and not vc.is_paused():
            await self.play_next(ctx.guild.id, ctx.channel)

    @commands.hybrid_command(
        name="forceplay",
        description="Play ONLY a direct URL or file:// path (no YouTube search detection)"
    )
    async def forceplay(self, ctx, *, input_text: str):
        logger.info(f"User {ctx.author} invoked forceplay with: {input_text}")

        vc = await self.connect_to_vc(ctx)
        if not vc:
            return

        tracks = self.extract_tracks(input_text, allow_search=False)
        if not tracks:
            await ctx.reply("forceplay requires a direct URL or file:// path (no search).")
            return

        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = []

        self.queues[ctx.guild.id].extend(tracks)

        if len(tracks) == 1:
            await ctx.reply(f"Queued: **{tracks[0]['title']}**")
        else:
            await ctx.reply(f"Queued playlist: **{len(tracks)} tracks**")

        if not vc.is_playing() and not vc.is_paused():
            await self.play_next(ctx.guild.id, ctx.channel)

    @commands.hybrid_command(name="skip", description="Skip the current track")
    async def skip(self, ctx):
        vc = self.voice_clients.get(ctx.guild.id)
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await ctx.reply("Skipped.")
        else:
            await ctx.reply("Nothing is playing.")

    @commands.hybrid_command(name="queue", description="Show the current queue")
    async def queue(self, ctx):
        queue = self.queues.get(ctx.guild.id, [])
        if not queue:
            await ctx.reply("Queue is empty.")
            return

        preview = queue[:10]
        msg = "\n".join([f"{i+1}. {t['title']}" for i, t in enumerate(preview)])

        if len(queue) > 10:
            msg += f"\n...and {len(queue) - 10} more."

        await ctx.reply(f"**Queue:**\n{msg}")

    @commands.hybrid_command(name="pause", description="Pause the current audio")
    async def pause(self, ctx):
        vc = self.voice_clients.get(ctx.guild.id)
        if vc and vc.is_playing():
            vc.pause()
            await ctx.reply("Paused.")
        else:
            await ctx.reply("Nothing is playing.")

    @commands.hybrid_command(name="resume", description="Resume paused audio")
    async def resume(self, ctx):
        vc = self.voice_clients.get(ctx.guild.id)
        if vc and vc.is_paused():
            vc.resume()
            await ctx.reply("Resumed.")
        else:
            await ctx.reply("Nothing is paused.")

    @commands.hybrid_command(name="playpause", description="Toggle pause/resume")
    async def playpause(self, ctx):
        vc = self.voice_clients.get(ctx.guild.id)
        if not vc or not vc.is_connected():
            await ctx.reply("I am not connected to a voice channel.")
            return

        if vc.is_playing():
            vc.pause()
            await ctx.reply("Paused.")
            return

        if vc.is_paused():
            vc.resume()
            await ctx.reply("Resumed.")
            return

        await ctx.reply("Nothing is playing.")

    @commands.hybrid_command(name="volume", description="Set volume (0-200). Default is 100.")
    async def volume(self, ctx, volume: int):
        guild_id = ctx.guild.id

        if volume < 0 or volume > 200:
            await ctx.reply("Volume must be between 0 and 200.")
            return

        vol_float = volume / 100.0
        self.set_volume(guild_id, vol_float)

        vc = self.voice_clients.get(guild_id)

        if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = vol_float

        await ctx.reply(f"Volume set to **{volume}%**")

    @commands.hybrid_command(name="stop", description="Stop audio, clear queue, and disconnect")
    async def stop(self, ctx):
        guild_id = ctx.guild.id
        vc = self.voice_clients.get(guild_id)

        self.queues[guild_id] = []

        if vc:
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            await vc.disconnect()
            await ctx.reply("Stopped, cleared queue, and disconnected.")
        else:
            await ctx.reply("I am not connected to a voice channel.")


async def setup(bot):
    await bot.add_cog(Music(bot))
