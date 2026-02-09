"""
Music player module! Supports direct links, YouTube (including playlists), YouTube search, and local files.
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


class Music(commands.Cog):
    """Music player cog supporting YouTube, playlists, direct links, local files, and YouTube search."""

    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.queues = {}  # guild_id -> list of tracks
        self.locks = {}   # guild_id -> asyncio.Lock()

    def get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    async def connect_to_vc(self, ctx):
        """Helper to join the user's voice channel."""
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
        """Parse file:// URL into local file path if it exists."""
        if not url.startswith("file://"):
            return None

        path = urllib.parse.unquote(url[7:])
        if os.path.isfile(path):
            return path

        logger.error(f"File not found: {path}")
        return None

    def looks_like_url(self, text: str) -> bool:
        """Basic URL detection."""
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
            }]

        # If search is allowed, and it doesn't look like a URL, treat as YouTube search
        if allow_search and not self.looks_like_url(input_text):
            input_text = f"ytsearch:{input_text}"

        # If search is NOT allowed, reject non-URLs
        if not allow_search and not self.looks_like_url(input_text):
            return []

        # yt-dlp (YouTube single OR playlist OR direct link)
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                info = ydl.extract_info(input_text, download=False)

            # Playlist case
            if "entries" in info and info["entries"] and info.get("_type") == "playlist":
                tracks = []
                for entry in info["entries"]:
                    if not entry:
                        continue

                    # Some entries are incomplete, re-extract to get stream url
                    if "url" not in entry or entry.get("_type") == "url":
                        with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                            entry = ydl.extract_info(entry["webpage_url"], download=False)

                    tracks.append({
                        "title": entry.get("title", "Unknown title"),
                        "webpage_url": entry.get("webpage_url", input_text),
                        "stream_url": entry["url"],
                        "type": "remote",
                        "ffmpeg_opts": FFMPEG_REMOTE_OPTIONS,
                    })

                return tracks

            # ytsearch case (returns entries)
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
                }]

            # Single video case
            return [{
                "title": info.get("title", "Unknown title"),
                "webpage_url": info.get("webpage_url", input_text),
                "stream_url": info["url"],
                "type": "remote",
                "ffmpeg_opts": FFMPEG_REMOTE_OPTIONS,
            }]

        except Exception as e:
            logger.error(f"Error fetching audio: {e}")
            return []

    async def play_next(self, guild_id: int, text_channel: discord.abc.Messageable):
        """Plays the next track in queue for a guild."""
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

            vc.play(
                discord.FFmpegPCMAudio(track["stream_url"], **track["ffmpeg_opts"]),
                after=after_play
            )

            await text_channel.send(f"Now playing: **{track['title']}**")

    @commands.hybrid_command(
        name="play",
        description="Play a song or playlist from YouTube, direct URL, local file, or search query"
    )
    async def play(self, ctx, *, input_text: str):
        logger.info(f"User {ctx.author} invoked play with: {input_text}")

        vc = await self.connect_to_vc(ctx)
        if not vc:
            return

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
