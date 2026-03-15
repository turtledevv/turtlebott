import discord
import json
import os
from pathlib import Path
from .dnd_beyond_parser import convert

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
     