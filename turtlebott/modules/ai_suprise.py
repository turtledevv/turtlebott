import discord
from discord.ext import commands
import asyncio
import random
from turtlebott.utils.logger import setup_logger

logger = setup_logger("ai_suprise")


class AISuprise(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="suprise")
    async def suprise(self, ctx: commands.Context):
        """A chaotic command that does… things."""
        logger.info(f"User {ctx.author} invoked suprise command.")
        # Step 1: Acknowledge nothing
        msg = await ctx.send(r"-# This was made 100% by generative AI. Upon asking for a suprise, this was it's response.")

        await asyncio.sleep(1.5)

        # Step 2: Begin nonsense
        frames = [
            "..",
            "...",
            "processing",
            "processing.",
            "processing..",
            "processing...",
            "thinking",
            "thinking.",
            "thinking..",
            "thinking...",
            "no thoughts",
            "one thought",
            "too many thoughts",
        ]

        for frame in frames:
            await msg.edit(content=frame)
            await asyncio.sleep(0.45)

        # # Step 3: Mild chaos, fully reversible
        # emojis = ["🟦", "🟥", "🟨", "🟩", "⬛", "⬜"]
        # for _ in range(12):
        #     await ctx.message.add_reaction(random.choice(emojis))
        #     await asyncio.sleep(0.15)

        # await asyncio.sleep(0.6)

        # # Step 4: Clean up evidence
        # try:
        #     await ctx.message.clear_reactions()
        # except discord.Forbidden:
        #     logger.warning("Missing permissions to clear reactions.")

        await msg.edit(content="done")

        await asyncio.sleep(1.2)
        await msg.delete()


async def setup(bot):
    await bot.add_cog(AISuprise(bot))
