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

logger = setup_logger("dndhelper")

class CharSelectCharacter(discord.ui.Select):
    """Dropdown to switch between characters."""

    def __init__(self, characters, original_author, sheets_dir, guild_id, parent_view):
        options = [
            discord.SelectOption(label=char, description=f"View {char}'s sheet")
            for char in characters
        ]
        super().__init__(placeholder="Select character...", min_values=1, max_values=1, options=options)
        self.original_author = original_author
        self.sheets_dir = sheets_dir
        self.guild_id = guild_id
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.original_author.id:
            await interaction.response.send_message("You can't use this dropdown.", ephemeral=True)
            return

        char_name = self.values[0]
        filepath = os.path.join(self.sheets_dir, str(self.guild_id), f"{char_name}.json")
        if not os.path.exists(filepath):
            await interaction.response.send_message(f"Character `{char_name}` not found.", ephemeral=True)
            return

        with open(filepath, "r") as f:
            data = json.load(f)

        # Update parent view with new character data
        self.parent_view.current_character_data = data
        self.parent_view.current_character_name = char_name

        # Refresh section embed
        await self.parent_view.show_section(interaction, "Overview", is_intial=False)


class CharSelectSection(discord.ui.Select):
    """Dropdown to choose a section of the current character."""

    def __init__(self, parent_view):
        options = [
            discord.SelectOption(label="Overview", description="Basic character info"),
            discord.SelectOption(label="Abilities", description="Ability scores and modifiers"),
            discord.SelectOption(label="Saving Throws", description="Character saving throws"),
            discord.SelectOption(label="Skills", description="Character skills"),
            discord.SelectOption(label="Combat", description="Combat stats"),
            discord.SelectOption(label="Equipment", description="Inventory and equipment"),
            discord.SelectOption(label="Spells", description="Spells and casting info"),
            discord.SelectOption(label="Features/Traits", description="Special features and traits"),
            discord.SelectOption(label="Notes", description="Backstory, personality, etc."),
        ]
        super().__init__(placeholder="Select section...", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.original_author.id:
            await interaction.response.send_message("You can't use this dropdown.", ephemeral=True)
            return
        await self.parent_view.show_section(interaction, self.values[0], is_intial=False)


class CharView(discord.ui.View):
    """Holds dropdowns for character selection and sections."""

    def __init__(self, characters, current_character_data, current_character_name, original_author, sheets_dir, guild_id):
        super().__init__(timeout=None)
        self.original_author = original_author
        self.sheets_dir = sheets_dir
        self.guild_id = guild_id
        self.current_character_data = current_character_data
        self.current_character_name = current_character_name

        # Add dropdowns
        if len(characters) > 1:
            self.add_item(CharSelectCharacter(characters, original_author, sheets_dir, guild_id, self))
        self.add_item(CharSelectSection(self))

    async def show_section(self, interaction, section, is_intial):
        char = self.current_character_data.get("character", {})
        abilities = self.current_character_data.get("abilities", {})
        skills = self.current_character_data.get("skills", [])
        saves = self.current_character_data.get("saving_throws", {})
        combat = self.current_character_data.get("combat", {})
        weapons = self.current_character_data.get("weapons", {})
        personality = self.current_character_data.get("personality", {})
        spells = self.current_character_data.get("spells", [])
        equipment = self.current_character_data.get("equipment", {})
        notes = self.current_character_data.get("notes", {})

        embed = discord.Embed(color=discord.Color.blue())
        embed.set_author(name=self.current_character_name)
        
        if char.get("image"):
            embed.set_thumbnail(url=char["image"])
            
        if section == "Overview":
            embed.title = "Overview"
            embed.description = (
                f"**Player:** {char.get('player_name','Unknown')}\n"
                f"**Class / Level** {char.get('class_level','')}\n"
                f"**Race/Background:** {char.get('race','')} / {char.get('background','')}\n"
                f"**Alignment:** {char.get('alignment','')}\n"
                f"**Age / Gender:** {char.get('age','')} / {char.get('gender','')}\n"
                f"**Size / Height / Weight:** {char.get('size','')} / {char.get('height','')} / {char.get('weight','')}\n"
                f"**Faith:** {char.get('faith','')}\n"
                f"**Senses:** {self.current_character_data.get('senses','')}\n"
                f"**Defenses:** {self.current_character_data.get('defenses','')}"
            )

        elif section == "Abilities":
            embed.title = "Abilities"
            for key, val in abilities.items():
                embed.add_field(name=key.upper(), value=val, inline=True)

        elif section == "Saving Throws":
            embed.title = "Saving Throws"
            for save, info in saves.items():
                prof = info.get("prof", "")
                val = info.get("value", "")
                embed.add_field(name=save.upper(), value=f"{val} {prof}", inline=True)

        elif section == "Skills":
            embed.title = "Skills"
            for skill in skills:
                embed.add_field(name=skill["name"], value=f"{skill['value']} ({skill['ability']})", inline=True)

        elif section == "Combat":
            embed.title = "Combat"
            for key, val in combat.items():
                embed.add_field(name=key.replace("_"," ").title(), value=val, inline=True)

        elif section == "Equipment":
            embed.title = "Equipment"
            if equipment:
                for idx in sorted(equipment.keys()):
                    item = equipment[idx]
                    name = item.get("name", "Unknown")
                    qty = item.get("qty", "1")
                    weight = item.get("weight", "--")
                    embed.add_field(
                        name=name,
                        value=f"Quantity: {qty}\nWeight: {weight}",
                        inline=True
                    )
            else:
                embed.description = "No equipment recorded."

        elif section == "Spells":
            embed.title = "Spells"
            if spells:
                for spell in spells:
                    embed.add_field(
                        name=f"{spell.get('name','Unknown')} ({spell.get('castingclass','')})",
                        value=f"Atk Bonus: {spell.get('atkbonus','--')} | Save DC: {spell.get('savedc','--')}\n"
                              f"Range: {spell.get('range','--')} | Duration: {spell.get('duration','--')}\n"
                              f"Components: {spell.get('components','--')}\nPrepared: {spell.get('prepared','--')}",
                        inline=False
                    )
            else:
                embed.description = "No spells recorded."

        elif section == "Features/Traits":
            embed.title = "Features & Traits"
            features = notes.get("featurestraits1","") + "\n" + notes.get("featurestraits2","") + "\n" + notes.get("featurestraits3","")
            embed.description = features if features else "No features recorded."

        elif section == "Notes":
            embed.title = "Notes"
            note_fields = ["personalitytraits","ideals","bonds","flaws","backstory","additionalnotes1"]
            for nf in note_fields:
                if nf in notes:
                    embed.add_field(name=nf.replace("_"," ").title(), value=notes[nf], inline=False)
            
            person_fields = ["allies_organizations", "personality_traits", "ideals", "bonds", "flaws", "backstory", "additional_notes_1"]
            for pf in person_fields: 
                if pf in personality:
                    embed.add_field(name=pf.replace("_"," ").title(), value=personality[pf], inline=False)
        if is_intial:
            await interaction.reply(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
            
class DndHelper(commands.Cog):
    def __init__(self, bot):
        self.DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "dnd_helper"))
        self.TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "temp"))
        self.SHEETS_DIR = os.path.join(self.DATA_DIR, "sheets")

        self.bot = bot
    
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

        character_name = character_name or all_chars[0]
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
            
    # commands, and shit
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

        thing = expression.lower().strip()

        base_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sheets_folder = os.path.join(base_folder, "data", "dnd_helper", "sheets", f"{ctx.guild.id}")

        # Load first available sheet (replace later with user mapping)
        sheet_file = None
        for f in os.listdir(sheets_folder):
            if f.endswith(".json"):
                sheet_file = os.path.join(sheets_folder, f)
                break

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