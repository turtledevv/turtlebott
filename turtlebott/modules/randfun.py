"""
Random fun commands module!
"""
import random
import discord
from discord.ext import commands
from turtlebott.utils.logger import setup_logger

logger = setup_logger("example")


class RandFun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command(name="idfk")
    async def idfk(self, ctx):
        """No description provided."""
        logger.info(f"User {ctx.author} invoked idfk command.")
        await ctx.reply(f"Well, *I* don't know either! Don't ask me!")

    @commands.hybrid_command(name="gif")
    async def gif(self, ctx):
        """Simple example command that sends a random gif."""
        logger.info(f"User {ctx.author} invoked gif command.")
        tenor_ids = [
            "sonic-unleashed-eggman-robotnik-sandwich-eggman-sandwich-gif-8651613417481721241",
            "tf2-bread-gif-10184446768704095641",
            "boykisser-spin-silly-cat-silly-cat-gif-15869807335045066863",
            "gun-loading-gun-cursed-emoji-mad-gif-24853374",
            "cary-cary-huang-huang-bfdi-battle-for-dream-island-gif-15347344906309488092",
            "r-tachyon-ume-musume-uma-musume-horse-gif-6355441694660360746",
            "will-wood-ik-i-know-gif-13165299665569457587",
            "jollyposting-cat-the-voices-jolly-santa-gif-13844772206269131622",
            "post-this-cat-ryujinr-grey-cat-gif-13471549557469691566",
        ]

        random_tenor_id = random.choice(tenor_ids)
        await ctx.reply(f"https://tenor.com/view/{random_tenor_id}")


async def setup(bot):
    await bot.add_cog(RandFun(bot))