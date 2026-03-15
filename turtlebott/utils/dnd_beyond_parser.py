import json
from pathlib import Path
from pypdf import PdfReader
import re

# ── Lookup tables ─────────────────────────────────────────────────────────────

CHARACTER_CANONICAL = {
    "charactername": "name", "charactername2": "name",
    "charactername3": "name", "charactername4": "name",
    "class  level": "class_level", "class  level2": "class_level",
    "player name": "player_name", "player name2": "player_name",
    "race": "race", "race2": "race",
    "background": "background", "background2": "background",
    "experience points": "experience_points",
    "experience points2": "experience_points",
    "alignment": "alignment",
    "faith": "faith",
    "age": "age", "size": "size", "height": "height", "weight": "weight",
    "gender": "gender", "skin": "skin", "eyes": "eyes", "hair": "hair",
}

ABILITY_KEYS = {
    "str": "str", "dex": "dex", "con": "con",
    "int": "int", "wis": "wis", "cha": "cha",
    "strmod": "str_mod", "dexmod": "dex_mod", "conmod": "con_mod",
    "intmod": "int_mod", "wismod": "wis_mod", "chamod": "cha_mod",
    "dexmod ": "dex_mod", "conmod ": "con_mod", "chamod ": "cha_mod",
}

SAVING_THROW_VALUE_MAP = {
    "st strength": "str", "st dexterity": "dex",
    "st constitution": "con", "st intelligence": "int",
    "st wisdom": "wis", "st charisma": "cha",
}

SAVING_THROW_PROF_MAP = {
    "strprof": "str", "dexprof": "dex", "conprof": "con",
    "intprof": "int", "wisprof": "wis", "chaprof": "cha",
}

COMBAT_FIELDS = {
    "ac": "ac",
    "init": "initiative",
    "speed": "speed",
    "maxhp": "max_hp",
    "currenthp": "current_hp",
    "temphp": "temp_hp",
    "profbonus": "prof_bonus",
    "total": "hit_dice_total",
    "hd": "hit_dice_remaining",
    "abilitysavedc": "ability_save_dc",
    "abilitysavescore1": "ability_save_score_1",
    "abilitysavescore2": "ability_save_score_2",
    "abilitysavedc2": "ability_save_dc_2",
    "inspiration": "inspiration",
    "savemodifiers": "save_modifiers",
    "weight carried": "weight_carried",
    "encumbered": "encumbered",
    "pushdraglift": "push_drag_lift",
}

PASSIVE_FIELDS = {
    "passive1": "passive_perception",
    "passive2": "passive_insight",
    "passive3": "passive_investigation",
}

CURRENCY_FIELDS = {"cp", "sp", "ep", "gp", "pp"}

PERSONALITY_FIELDS = {
    "personalitytraits": "personality_traits",
    "personalitytraits ": "personality_traits",
    "ideals": "ideals",
    "bonds": "bonds",
    "flaws": "flaws",
    "appearance": "appearance",
    "backstory": "backstory",
    "additionalnotes1": "additional_notes_1",
    "additionalnotes2": "additional_notes_2",
    "alliesorganizations": "allies_organizations",
    "character image": "character_image",
}

SKILL_NAMES = {
    "acrobatics", "animal", "animalhandling", "arcana", "athletics",
    "deception", "history", "insight", "intimidation", "investigation",
    "medicine", "nature", "perception", "performance", "persuasion",
    "religion", "sleightofhand", "stealth", "survival",
}

SKILL_DISPLAY = {
    "animal": "Animal Handling",
    "animalhandling": "Animal Handling",
    "sleightofhand": "Sleight of Hand",
}

SKILL_ORDER = [
    "acrobatics", "animal", "arcana", "athletics", "deception",
    "history", "insight", "intimidation", "investigation", "medicine",
    "nature", "perception", "performance", "persuasion", "religion",
    "sleightofhand", "stealth", "survival",
]

SPELL_PREFIXES = (
    "spellname", "spellsource", "spellsavehit", "spellcastingtime",
    "spellrange", "spellcomponents", "spellduration", "spellpage",
    "spellnotes", "spellprepared", "spellheader", "spellslotheader",
    "spellcastingability", "spellsavedc", "spellatk", "spellatkbonus",
    "spellcastingclass",
    "savehit", "castingtime", "range", "components", "duration",
    "source", "notes", "prepared",
)

_SPELL_KEY_RE = re.compile(r"^spell")


def norm(s):
    return s.strip().lower()


def drop_trailing_digits(s):
    return re.sub(r"\s*\d+$", "", s)


def skill_base(lname):
    for sk in SKILL_NAMES:
        if lname in (sk, sk + "prof", sk + "mod", sk + " "):
            return sk
        if lname.startswith(sk) and lname[len(sk):] in ("", "prof", "mod", " "):
            return sk
    return None


def _eq_sort_key(k):
    p, n = k.split("_", 1)
    return (p, int(n))


# ── Core parser ───────────────────────────────────────────────────────────────

def parse_sheet(pdf_path: Path) -> dict:
    reader = PdfReader(pdf_path)

    data = {
        "character": {},
        "abilities": {},
        "saving_throws": {},
        "combat": {},
        "skills": {},
        "passives": {},
        "senses": "",
        "defenses": "",
        "currency": {},
        "equipment": {},
        "weapons": {},
        "spells": {},
        "features": [],
        "actions": [],
        "proficiencies": "",
        "personality": {},
        "notes": {},
    }

    for page in reader.pages:
        annots = page.get("/Annots")
        if not annots:
            continue

        for ref in annots:
            annot = ref.get_object()
            if annot.get("/Subtype") != "/Widget":
                continue

            raw = annot.get("/T")
            if not raw:
                continue

            value = annot.get("/V") or annot.get("/Contents") or ""
            val = str(value).strip()
            if val in ("", "/Off", "Off"):
                continue

            ln = norm(raw)
            lns = drop_trailing_digits(ln)

            key = CHARACTER_CANONICAL.get(ln) or CHARACTER_CANONICAL.get(lns)
            if key:
                if key not in data["character"]:
                    data["character"][key] = val
                continue

            ab_key = ABILITY_KEYS.get(ln) or ABILITY_KEYS.get(ln.rstrip())
            if ab_key:
                data["abilities"][ab_key] = val
                continue

            if ln in SAVING_THROW_VALUE_MAP:
                data["saving_throws"].setdefault(
                    SAVING_THROW_VALUE_MAP[ln], {})["value"] = val
                continue
            
            # --- Personality ---
            p_key = PERSONALITY_FIELDS.get(ln) or PERSONALITY_FIELDS.get(lns)
            if p_key:
                data["personality"][p_key] = val
                continue

            # --- Equipment ---
            if ln.startswith("eq name") or ln.startswith("eq qty") or ln.startswith("eq weight"):
                idx = int(re.search(r"\d+$", ln).group(0))
                item = data["equipment"].setdefault(idx, {"name": "", "qty": "", "weight": ""})
                if "name" in ln:
                    item["name"] = val
                elif "qty" in ln:
                    item["qty"] = val
                elif "weight" in ln:
                    item["weight"] = val
                continue

            # --- Weapons ---
            if ln.startswith("wpn"):
                # handle numeric suffix
                m = re.search(r"wpn(\d*)\s*(.*)", ln)
                if m:
                    idx = int(m.group(1)) if m.group(1) else 0
                    field = m.group(2).strip()  # atkbonus, damage, notes, etc.
                    weapon = data["weapons"].setdefault(idx, {})
                    weapon[field] = val
                continue

            if ln in SAVING_THROW_PROF_MAP:
                data["saving_throws"].setdefault(
                    SAVING_THROW_PROF_MAP[ln], {})["prof"] = val
                continue

            if ln in COMBAT_FIELDS:
                data["combat"][COMBAT_FIELDS[ln]] = val
                continue

            if ln in PASSIVE_FIELDS:
                data["passives"][PASSIVE_FIELDS[ln]] = val
                continue

            if ln == "additionalsenses":
                data["senses"] = val
                continue

            if ln == "defenses":
                data["defenses"] = val
                continue

            if ln in CURRENCY_FIELDS:
                data["currency"][ln] = val
                continue

            sk = skill_base(ln)
            if sk:
                entry = data["skills"].setdefault(sk, {
                    "name": SKILL_DISPLAY.get(sk, sk.capitalize()),
                    "value": "",
                    "prof": "",
                    "ability": "",
                })
                if ln.endswith("prof"):
                    entry["prof"] = val
                elif ln.endswith("mod"):
                    entry["ability"] = val
                else:
                    entry["value"] = val
                continue

            sm = re.search(r"(\d+)$", ln)
            if sm and any(ln.startswith(p) for p in SPELL_PREFIXES):
                idx = int(sm.group(1))
                field_key = re.sub(r"\d+$", "", ln).rstrip()
                field_key = _SPELL_KEY_RE.sub("", field_key)
                data["spells"].setdefault(idx, {})[field_key] = val
                continue

            data["notes"][ln] = val

    data["skills"] = [
        data["skills"][sk]
        for sk in SKILL_ORDER
        if sk in data["skills"]
    ]

    data["spells"] = [
        data["spells"][i]
        for i in sorted(data["spells"])
        if any(data["spells"][i].values())
    ]

    data["features"] = "\n".join(data["features"]).strip()
    data["actions"] = "\n".join(data["actions"]).strip()

    return data


# ── Public API ───────────────────────────────────────────────────────────────

def convert(pdf_file):
    """
    Convert a D&D character sheet PDF to structured JSON.

    Usage:
        data = convert("character.pdf")
    """
    pdf_path = Path(pdf_file)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_file)

    return parse_sheet(pdf_path)


def convert_to_file(pdf_file, output_json):
    """
    Convert a PDF and save it directly to a JSON file.
    """
    data = convert(pdf_file)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)