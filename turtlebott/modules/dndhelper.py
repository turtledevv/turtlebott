import os
import json
import discord
from discord.ext import commands
import aiohttp
from pathlib import Path
from urllib.parse import urlparse
import asyncio
from PIL import Image
import io, base64

from turtlebott.utils.logger import setup_logger
import turtlebott.utils.dice as dice
from turtlebott.utils.dnd_beyond_parser import convert, convert_to_file
from turtlebott.utils.dnd_views import CharView

logger = setup_logger("dndhelper")
       
class DndHelper(commands.Cog):
    def __init__(self, bot):
        self.DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "dnd_helper"))
        self.TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "temp"))
        self.SHEETS_DIR = os.path.join(self.DATA_DIR, "sheets")

        self.bot = bot
    
    def get_linked_character(self, guild_id: int, user_id: int) -> str | None:
        """Return the character name linked to a user, or None."""

        link_file = os.path.join(self.DATA_DIR, "char_link.json")

        if not os.path.exists(link_file):
            return None

        with open(link_file, "r") as f:
            links = json.load(f)

        server_links = links.get(str(guild_id), {})
        return server_links.get(str(user_id))
    
    # helpah functions, cause of course I wouldn't ever move them into their own seperate utils file!
    async def download(self, url: str, filepath: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return False
                with open(filepath, "wb") as f:
                    f.write(await resp.read())
        return True

    async def wait_for_confirm(self, ctx, message):
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in ["✅", "❌"]
                and reaction.message.id == message.id
            )

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
            return str(reaction.emoji) == "✅"
        except asyncio.TimeoutError:
            return None
    
    @commands.hybrid_command(name="charlink", aliases=["clink", "characterlink", "tclink"])
    async def charlink(self, ctx, character_name: str | None = None, *, target: str | None = None):
        """Link a character sheet to a Discord user."""

        # Check admin if targeting another user
        if target:
            if not ctx.author.guild_permissions.administrator:
                await ctx.reply("You don't have the power to link someone else's character.")
                return

            # Try to resolve user
            target_user = None
            if target.isdigit():
                target_user = ctx.guild.get_member(int(target))
            if not target_user:
                if target.startswith("<@") and target.endswith(">"):
                    target_user_id = int(target.strip("<@!>"))
                    target_user = ctx.guild.get_member(target_user_id)
            if not target_user:
                target_user = discord.utils.get(ctx.guild.members, name=target)

            if not target_user:
                await ctx.reply(f"Could not find a user matching `{target}`.")
                return
        else:
            target_user = ctx.author

        # Check if character exists
        guild_folder = os.path.join(self.SHEETS_DIR, str(ctx.guild.id))
        if not os.path.exists(guild_folder):
            await ctx.reply("No character sheets found for this server.")
            return

        all_chars = [f[:-5] for f in os.listdir(guild_folder) if f.endswith(".json")]
        if not character_name:
            await ctx.reply("You must specify a character name.")
            return

        if character_name not in all_chars:
            await ctx.reply(f"No character sheet found with the name `{character_name}`.")
            return

        # Load char_link.json
        link_file = os.path.join(self.DATA_DIR, "char_link.json")
        if os.path.exists(link_file):
            with open(link_file, "r") as f:
                links = json.load(f)
        else:
            links = {}

        server_links = links.get(str(ctx.guild.id), {})

        # Check if character already linked
        if character_name in server_links.values():
            # Find current owner
            current_owner_id = None
            for uid, char in server_links.items():
                if char == character_name:
                    current_owner_id = uid
                    break

            # If author is admin, ask to overwrite
            if ctx.author.guild_permissions.administrator:
                msg = await ctx.reply(
                    f"Character `{character_name}` is already linked to <@{current_owner_id}>. Overwrite?"
                )
                def check(reaction, user):
                    return (
                        user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
                    )
                await msg.add_reaction("✅")
                await msg.add_reaction("❌")

                try:
                    reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
                    if str(reaction.emoji) != "✅":
                        await ctx.reply("Linking cancelled.")
                        return
                except asyncio.TimeoutError:
                    await ctx.reply("Timed out. Linking cancelled.")
                    return
            else:
                await ctx.reply("This character is already linked to someone else.")
                return

        # Add or update link
        server_links[str(target_user.id)] = character_name
        links[str(ctx.guild.id)] = server_links

        os.makedirs(os.path.dirname(link_file), exist_ok=True)
        with open(link_file, "w") as f:
            json.dump(links, f, indent=4)

        await ctx.reply(f"Linked character `{character_name}` to <@{target_user.id}> successfully.")
    
    @commands.hybrid_command(name="char")
    async def char(self, ctx, *, character_name: str | None = None):
        guild_folder = os.path.join(self.SHEETS_DIR, str(ctx.guild.id))
        if not os.path.exists(guild_folder):
            await ctx.reply("No character sheets found for this server.")
            return

        all_chars = [f[:-5] for f in os.listdir(guild_folder) if f.endswith(".json")]
        if not all_chars:
            await ctx.reply("No character sheets found for this server.")
            return

        char = self.get_linked_character(ctx.guild.id, ctx.author.id)
        character_name = character_name or char or all_chars[0]
        if character_name not in all_chars:
            await ctx.reply(f"No character sheet found with the name `{character_name}`.")
            return

        filepath = os.path.join(guild_folder, f"{character_name}.json")
        with open(filepath, "r") as f:
            data = json.load(f)

        view = CharView(all_chars, data, character_name, ctx.author, self.SHEETS_DIR, ctx.guild.id)
        await view.show_section(ctx, "Overview", is_intial=True)
        
    @commands.hybrid_command(name="uchars", aliases=["updatechar", "updatecharacters", "updatecharacter", "updatechars", "uchar"])
    async def uchars(self, ctx):
        """Update all character sheets for this server by re-downloading and re-parsing their data."""
        guild_id = ctx.guild.id
        sheets_folder = os.path.join(self.SHEETS_DIR, f"{guild_id}")
        
        if not os.path.exists(sheets_folder):
            await ctx.reply("No character sheets found for this server.")
            return
        
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply("You don't have the power to update character sheets.")
            return

        
        updated = 0
        failed = 0
        fails = []
        updates = []
        
        for filename in os.listdir(sheets_folder):
            if not filename.endswith(".json"):
                continue
            
            filepath = os.path.join(sheets_folder, filename)
            with open(filepath, "r") as f:
                data = json.load(f)
            
            source_url = data.get("meta", {}).get("source")
            if not source_url:
                fails.append(filename)
                failed += 1
                logger.warning(f"No source URL for {filename}, skipping.")
                continue
            
            logger.info(f"Updating character from {source_url}")
            temp_path = os.path.join(self.TEMP_DIR, f"temp_{filename}")
            
            if not await self.download(source_url, temp_path):
                fails.append(filename)
                failed += 1
                logger.error(f"Failed to download {source_url} for {filename}")
                continue
            
            try:
                new_data = convert(temp_path)
                new_data["meta"] = data.get("meta", {})
                new_data["meta"]["last_updated"] = ctx.message.created_at.isoformat()
                
                try:
                    await self.download(new_data["character"]["image"], os.path.join(self.TEMP_DIR, f"temp_{filename}_img.png"))
                    pfp_img = new_data["character"]["image"]
                except Exception as e:
                    logger.warning(f"Failed to download image for {filename}: {e}, defaulting to normal")
                    pfp_img = "https://www.dndbeyond.com/Content/Skins/Waterdeep/images/characters/default-avatar-builder.png"
                    
                new_data["character"]["image"] = pfp_img
                with open(filepath, "w") as f:
                    json.dump(new_data, f, indent=4)
                updates.append(filename)
                updated += 1
            except Exception as e:
                fails.append(filename)
                failed += 1
                logger.error(f"Error updating {filename}: {e}")
            finally:
                os.remove(temp_path)
                
        await ctx.reply(f"Updated {updated} character sheets. Failed: {failed}\n-# Updated: {', '.join(updates)}\n-# Failed: {', '.join(fails)}")
            
    @commands.hybrid_command(name="newchar", aliases=["newcharacter"])
    async def newchar(self, ctx, url: str, pfp: str | None = None):
        logger.info(f"User {ctx.author} invoked newchar with URL: {url}")

        if not url.lower().endswith(".pdf"):
            await ctx.reply("That URL does not appear to be a PDF.")
            return

        os.makedirs(self.TEMP_DIR, exist_ok=True)

        filename = os.path.basename(urlparse(url).path)
        filepath = os.path.join(self.TEMP_DIR, filename)

        await ctx.reply(f"Downloading `{filename}`...")

        if not await self.download(url, filepath):
            await ctx.reply("Failed to download the file.")
            return

        await ctx.send(f"Downloaded `{filename}`! Parsing...")

        try:
            data = convert(filepath)
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            await ctx.reply("Failed to parse the PDF.")
            return

        if not data:
            await ctx.reply("Failed to extract character data from the PDF.")
            return

        name = data.get("character", {}).get("name", "Unknown")

        msg = await ctx.reply(f"Successfully parsed character `{name}`. Save?")
        confirm = await self.wait_for_confirm(ctx, msg)

        if not confirm:
            await ctx.reply("Character not saved.")
            return

        save_path = os.path.abspath(
            os.path.join(self.SHEETS_DIR, f"{ctx.guild.id}", f"{name}.json")
        )

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        if os.path.exists(save_path):
            with open(save_path) as f:
                existing = json.load(f)

            existing_char = existing.get("character", {})
            new_char = data.get("character", {})

            diff = (
                f"Existing: `{existing_char.get('name','Unknown')}` - {existing_char.get('class_level','')}\n"
                f"New: `{new_char.get('name','Unknown')}` - {new_char.get('class_level','')}\n\n"
                "Overwrite?"
            )

            msg = await ctx.reply(diff)
            confirm = await self.wait_for_confirm(ctx, msg)

            if not confirm:
                await ctx.reply("Character not saved.")
                return

        data["meta"] = {}
        data["meta"]["source"] = url
        data["meta"]["added_on"] = ctx.message.created_at.isoformat()
        data["meta"]["last_updated"] = ctx.message.created_at.isoformat()
        data["meta"]["uploader"] = str(ctx.author)
        data["meta"]["tool"] = "Turtlebott (D&D Helper module)"
        
        if pfp:
            pfp_url = pfp
        else:
            pfp_url = "https://www.dndbeyond.com/Content/Skins/Waterdeep/images/characters/default-avatar-builder.png"
        
        data["character"]["image"] = pfp_url
        with open(save_path, "w") as f:
            json.dump(data, f, indent=4)

        await ctx.reply(f"Character saved! Use `{ctx.prefix}char {name}` to view it.")      

    @commands.hybrid_command(name="roll", aliases=["r"])
    async def roll(self, ctx, *, expression: str | None = None):
        """Smart rolling. Uses character sheet keywords or dice expressions."""

        if not expression:
            expression = "1d20"
        if expression.startswith("<@"):
            user = int(expression.split(">")[0][2:].replace("!", ""))
            expression = expression.split(">")[1].strip()
        else:
            user = ctx.author.id
        thing = expression.lower().strip()

        base_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sheets_folder = os.path.join(base_folder, "data", "dnd_helper", "sheets", f"{ctx.guild.id}")

        # Get linked character
        char_name = self.get_linked_character(ctx.guild.id, user)
        sheet_file = os.path.join(sheets_folder, f"{char_name}.json")
        if not char_name:
            for f in os.listdir(sheets_folder):
                if f.endswith(".json"):
                    sheet_file = os.path.join(sheets_folder, f)
                    break
        if not os.path.exists(sheet_file):
            await ctx.reply(f"Character sheet for `{char_name}` was not found.")
            return

        data = None
        if sheet_file:
            with open(sheet_file, "r") as f:
                data = json.load(f)

        # Try smart lookup if we have a sheet
        if data:
            character = data.get("character", {}).get("name", "Unknown")
            abilities = data.get("abilities", {})
            skills = data.get("skills", [])
            saves = data.get("saving_throws", {})
            combat = data.get("combat", {})

            mod = None
            label = thing

            if thing in ["initiative", "init"]:
                mod = combat.get("initiative")
                label = "Initiative"

            elif thing in ["str", "strength"]:
                mod = abilities.get("str_mod")
                label = "Strength"

            elif thing in ["dex", "dexterity"]:
                mod = abilities.get("dex_mod")
                label = "Dexterity"

            elif thing in ["con", "constitution"]:
                mod = abilities.get("con_mod")
                label = "Constitution"

            elif thing in ["int", "intelligence"]:
                mod = abilities.get("int_mod")
                label = "Intelligence"

            elif thing in ["wis", "wisdom"]:
                mod = abilities.get("wis_mod")
                label = "Wisdom"

            elif thing in ["cha", "charisma"]:
                mod = abilities.get("cha_mod")
                label = "Charisma"

            elif thing in saves:
                mod = saves[thing]["value"]
                label = f"{thing.upper()} Save"

            else:
                for skill in skills:
                    if skill["name"].lower() == thing:
                        mod = skill["value"]
                        label = skill["name"]
                        break

            if mod is not None:
                expression = f"1d20{mod}"

                result = dice.parse_roll(expression)

                rolls_str = ", ".join(map(str, result.rolls))
                total = dice.clean_number(result.total)
                mod_clean = dice.clean_number(result.modifier)

                msg = f"**:game_die: Rolling 1d20 for `{label}` ({mod_clean:+})**"
                msg += f"\n-# Character: {character}"
                msg += f"\n# Total: {total}"
                msg += f"\n-# Rolls: [{rolls_str}]"

                await ctx.reply(msg)
                return

        # Fallback to normal dice parser
        try:
            result = dice.parse_roll(expression)

            rolls_str = ", ".join(map(str, result.rolls))
            mod = dice.clean_number(result.modifier)
            total = dice.clean_number(result.total)

            msg = f"**:game_die: Rolling {result.count} d{result.size}"

            if result.reason:
                msg += f" for `{result.reason}`"

            if result.modifier:
                msg += f" ({mod:+} mod)"

            msg += "**"
            msg += f"\n# Total: {total}"
            msg += f"\n-# Rolls: [{rolls_str}]"

            await ctx.reply(msg)

        except ValueError as e:
            await ctx.reply(str(e))

async def setup(bot):
    await bot.add_cog(DndHelper(bot))