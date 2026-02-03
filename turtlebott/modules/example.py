import discord
from discord.ext import commands
from turtlebott.utils.logger import setup_logger

logger = setup_logger("example")


class Example(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="test")
    async def test(self, ctx):
        """Simple example command that replies with Hello World!"""
        logger.info(f"User {ctx.author} invoked test command.")
        await ctx.send("Hello World!")


async def setup(bot):
    await bot.add_cog(Example(bot))
