"""
Built-in commands module.
"""
import time
import discord
from discord.ext import commands
from ..utils.logger import setup_logger
from ..utils.module_loader import get_module_doc, get_all_modules, is_enabled

logger = setup_logger("builtin")

class Builtin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    @commands.hybrid_command(name="ping")
    async def ping(self, ctx):
        """Replies with Pong! and the bot's latency."""
        latency_ms = self.bot.latency * 1000
        logger.info(f"User {ctx.author} invoked ping command. Latency: {latency_ms:.0f}ms")
        await ctx.reply(f"Pong! ({latency_ms:.0f}ms)")

    @commands.hybrid_command(name="uptime")
    async def uptime(self, ctx):
        """Replies with the bot's uptime."""
        current_time = time.time()
        uptime_seconds = int(current_time - self.start_time)

        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_str = f"{hours}h {minutes}m {seconds}s"
        logger.info(f"User {ctx.author} invoked uptime command. Uptime: {uptime_str}")
        await ctx.reply(f"Uptime: {uptime_str}")

    @commands.hybrid_command(name="help")
    async def help_command(self, ctx):
        """Provides help information about available commands."""
        logger.info(f"User {ctx.author} invoked help command.")

        commands_list = []
        for command in self.bot.commands:
            if not command.hidden:
                commands_list.append(f"**{command.name}** – *{command.help or 'No description provided.'}*")

        help_message = "## **Available Commands:**\n" + "\n".join(commands_list)
        await ctx.reply(help_message)

    @commands.hybrid_command(name="listmodules")
    async def listmodules(self, ctx):
        """Lists enabled and disabled modules with descriptions."""
        logger.info(f"User {ctx.author} invoked listmodules command.")

        enabled = []
        disabled = []

        for module in get_all_modules():
            desc = get_module_doc(module)
            line = f"**{module}** – *{desc}*"

            if is_enabled(module):
                enabled.append(line)
            else:
                disabled.append(line)

        if not enabled:
            await ctx.reply("No modules are currently enabled.")
            return

        await ctx.reply("## **Enabled modules:**\n" + "\n".join(enabled) + "\n\n## **Disabled modules:**\n" + "\n".join(disabled))


async def setup(bot):
    await bot.add_cog(Builtin(bot))
