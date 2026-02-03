"""
Music player module! Supports direct links, YouTube, and local files.
"""
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


class Music(commands.Cog):
    """Music player cog supporting YouTube, direct links, and local files."""

    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}

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

    def get_source(self, url: str):
        """Get audio source URL using yt-dlp or local file."""
        if url.startswith("file://"):
            # Decode percent-encoded characters
            path = urllib.parse.unquote(url[7:])
            if os.path.isfile(path):
                return {"type": "local", "path": path}
            else:
                logger.error(f"File not found: {path}")
                return None


        # Assume YouTube or direct link
        ydl_opts = {"format": "bestaudio", "quiet": True, "extract_flat": "in_playlist"}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {"type": "remote", "path": info["url"]}
        except Exception as e:
            logger.error(f"Error fetching audio: {e}")
            return None

    @commands.hybrid_command(name="play", description="Play a song from YouTube, direct URL, or local file")
    async def play(self, ctx, url: str):
        """Play a song from URL or local file."""
        logger.info(f"User {ctx.author} invoked play command with URL: {url}")
        vc = await self.connect_to_vc(ctx)
        if not vc:
            return

        if vc.is_playing():
            vc.stop()

        source_info = self.get_source(url)
        if not source_info:
            await ctx.reply("Failed to get audio source.")
            return

        if source_info["type"] == "local":
            ffmpeg_opts = FFMPEG_LOCAL_OPTIONS
        else:
            ffmpeg_opts = FFMPEG_REMOTE_OPTIONS

        vc.play(
            discord.FFmpegPCMAudio(source_info["path"], **ffmpeg_opts),
            after=lambda e: logger.error(f"Player error: {e}") if e else None
        )
        await ctx.reply(f"Now playing: {url}")

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

    @commands.hybrid_command(name="stop", description="Stop audio and disconnect")
    async def stop(self, ctx):
        vc = self.voice_clients.get(ctx.guild.id)
        if vc:
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            await vc.disconnect()
            await ctx.reply("Stopped and disconnected.")
        else:
            await ctx.reply("I am not connected to a voice channel.")


async def setup(bot):
    await bot.add_cog(Music(bot))
