"""
Various D&D features to help with your campaigns, such as rolling dice, managing character sheets, and more.
"""
import discord
from discord.ext import commands
from turtlebott.utils.logger import setup_logger

logger = setup_logger("example")


class Example(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="roll")
    async def roll(self, ctx):
        """Roll a dice!"""
        logger.info(f"User {ctx.author} invoked roll command.")
        await ctx.reply("You rolled a NOTHING BECAUSE THIS IS JUST AN EXAMPLE COMMAND AHAH LOSER")


async def setup(bot):
    await bot.add_cog(Example(bot))
