"""
Discord bot module for remotely controlling the Roblox game "The Battle Bricks" via a sick af Discord control panel.
"""
# NOTES TO SELF:
#     - Make it only work when Roblox is focused
#     - Add more functionality (like changing loadout, upgrading/buying battlers, etc..) (Will require a *LOT* of mouse input and maybe some game state detection, mayhaps?)
import discord
from discord.ext import commands
import pydirectinput
import asyncio
from turtlebott.config import settings
from turtlebott.utils.logger import setup_logger

logger = setup_logger("battle_panel")

pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False

if settings.config["experiments_config"]["battle_panel"]["userWhitelistEnabled"]:
    logger.info("Battle Panel Whitelist is ENABLED")


# ---------- Authorization ----------
def is_user_allowed(user_id: int) -> bool:
    """Check if a user is allowed to use the battle panel based on whitelist."""
    config = settings.config.get("experiments_config", {}).get("battle_panel", {})
    whitelist_enabled = config.get("userWhitelistEnabled", False)
    
    if not whitelist_enabled:
        return True
    
    whitelist = config.get("userWhitelist", [])
    return user_id in whitelist


async def check_authorization(interaction: discord.Interaction) -> bool:
    """Check if user is authorized and respond appropriately."""
    if not is_user_allowed(interaction.user.id):
        logger.warning(f"Unauthorized access attempt by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this.", ephemeral=True)
        return False
    return True


# ---------- Input Logging ----------
def log_input(interaction: discord.Interaction, key: str, action: str):
    user = interaction.user
    logger.info(f"Input from {user} ({user.id}) | key={key} | action={action}")


# ---------- Input helpers ----------
def press(key: str):
    pydirectinput.keyDown(key)
    pydirectinput.keyUp(key)


def click_position(x, y):
    pydirectinput.moveTo(x, y, duration=0)
    pydirectinput.click()


async def hold_key(key: str, duration: float):
    pydirectinput.keyDown(key)
    await asyncio.sleep(duration)
    pydirectinput.keyUp(key)


# -------- Panel 1: Movement --------
class MovementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="↤", style=discord.ButtonStyle.primary, row=0)
    async def leftest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "a", "hold 3.5s")
        await hold_key("a", 3.5)
        await interaction.response.defer()

    @discord.ui.button(label="↞", style=discord.ButtonStyle.primary, row=1)
    async def lefter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "a", "hold 1s")
        await hold_key("a", 1)
        await interaction.response.defer()

    @discord.ui.button(label="←", style=discord.ButtonStyle.primary, row=1)
    async def left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "a", "hold 0.4s")
        await hold_key("a", 0.4)
        await interaction.response.defer()

    @discord.ui.button(label="→", style=discord.ButtonStyle.primary, row=1)
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "d", "hold 0.4s")
        await hold_key("d", 0.4)
        await interaction.response.defer()

    @discord.ui.button(label="↠", style=discord.ButtonStyle.primary, row=1)
    async def righter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "d", "hold 1s")
        await hold_key("d", 1)
        await interaction.response.defer()

    @discord.ui.button(label="↦", style=discord.ButtonStyle.primary, row=0)
    async def rightest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "d", "hold 3.5s")
        await hold_key("d", 3.5)
        await interaction.response.defer()


# -------- Panel 2: Battlers + Bank/Cannon/Die --------
class BattlersView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary, row=0)
    async def b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "1", "press")
        press("1")
        await interaction.response.defer()

    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary, row=0)
    async def b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "2", "press")
        press("2")
        await interaction.response.defer()

    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary, row=0)
    async def b3(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "3", "press")
        press("3")
        await interaction.response.defer()

    @discord.ui.button(label="4", style=discord.ButtonStyle.secondary, row=0)
    async def b4(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "4", "press")
        press("4")
        await interaction.response.defer()

    @discord.ui.button(label="5", style=discord.ButtonStyle.secondary, row=1)
    async def b5(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "5", "press")
        press("5")
        await interaction.response.defer()

    @discord.ui.button(label="6", style=discord.ButtonStyle.secondary, row=1)
    async def b6(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "6", "press")
        press("6")
        await interaction.response.defer()

    @discord.ui.button(label="7", style=discord.ButtonStyle.secondary, row=1)
    async def b7(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "7", "press")
        press("7")
        await interaction.response.defer()

    @discord.ui.button(label="8", style=discord.ButtonStyle.secondary, row=1)
    async def b8(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "8", "press")
        press("8")
        await interaction.response.defer()

    @discord.ui.button(label="Bank", style=discord.ButtonStyle.primary, row=2)
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "q", "press")
        press("q")
        await interaction.response.defer()

    @discord.ui.button(label="Cannon", style=discord.ButtonStyle.primary, row=2)
    async def cannon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "e", "press")
        press("e")
        await interaction.response.defer()

    @discord.ui.button(label="Die", style=discord.ButtonStyle.danger, row=2)
    async def die(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "tab", "spam 1s")
        end_time = asyncio.get_event_loop().time() + 1
        while asyncio.get_event_loop().time() < end_time:
            press("tab")
            await asyncio.sleep(0.03)
        await interaction.response.defer()


# -------- Panel 3: Screen clicks --------
class ScreenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Return", style=discord.ButtonStyle.secondary, row=0)
    async def ret(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "mouse", "click return")
        click_position(1061, 993)
        await interaction.response.defer()

    @discord.ui.button(label="Battle", style=discord.ButtonStyle.secondary, row=0)
    async def battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "mouse", "click battle")
        click_position(1687, 927)
        await interaction.response.defer()

    @discord.ui.button(label="Prev Stage", style=discord.ButtonStyle.secondary, row=0)
    async def prev_stage(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "mouse", "click prev_stage")
        click_position(581, 122)
        await interaction.response.defer()

    @discord.ui.button(label="Next Stage", style=discord.ButtonStyle.secondary, row=0)
    async def next_stage(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "mouse", "click next_stage")
        click_position(1330, 106)
        await interaction.response.defer()

    @discord.ui.button(label="Replay", style=discord.ButtonStyle.success, row=1)
    async def replay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_authorization(interaction):
            return
        log_input(interaction, "mouse", "click replay")
        click_position(864, 992)
        await interaction.response.defer()


class BattlePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def panel(self, ctx):
        await ctx.reply(embed=discord.Embed(title="Controls", color=0x2b2d31), view=MovementView())
        await ctx.send(view=BattlersView())
        await ctx.send(view=ScreenView())


async def setup(bot):
    await bot.add_cog(BattlePanel(bot))
