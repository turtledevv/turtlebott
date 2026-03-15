import json
import sys
from pathlib import Path
from pypdf import PdfReader
import re

INPUT_DIR  = Path("sheets")
OUTPUT_DIR = Path("sheets_json")

# ── Lookup tables (module-level, shared across all files) ─────────────────────

CHARACTER_CANONICAL = {
    "charactername": "name",   "charactername2": "name",
    "charactername3": "name",  "charactername4": "name",
    "class  level": "class_level",  "class  level2": "class_level",
    "player name": "player_name",   "player name2": "player_name",
    "race": "race",   "race2": "race",
    "background": "background",  "background2": "background",
    "experience points": "experience_points",
    "experience points2": "experience_points",
    "alignment": "alignment",
    "faith": "faith",
    "age": "age",   "size": "size",  "height": "height",  "weight": "weight",
    "gender": "gender", "skin": "skin", "eyes": "eyes", "hair": "hair",
}

ABILITY_KEYS = {
    "str": "str",    "dex": "dex",    "con": "con",
    "int": "int",    "wis": "wis",    "cha": "cha",
    "strmod": "str_mod",  "dexmod": "dex_mod",  "conmod": "con_mod",
    "intmod": "int_mod",  "wismod": "wis_mod",  "chamod": "cha_mod",
    # trailing-space variants that appear in some PDFs
    "dexmod ": "dex_mod", "conmod ": "con_mod", "chamod ": "cha_mod",
}

SAVING_THROW_VALUE_MAP = {
    "st strength": "str",    "st dexterity": "dex",
    "st constitution": "con", "st intelligence": "int",
    "st wisdom": "wis",      "st charisma": "cha",
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
    "personalitytraits":   "personality_traits",
    "personalitytraits ":  "personality_traits",
    "ideals":    "ideals",
    "bonds":     "bonds",
    "flaws":     "flaws",
    "appearance": "appearance",
    "backstory":  "backstory",
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
    "animal":         "Animal Handling",
    "animalhandling": "Animal Handling",
    "sleightofhand":  "Sleight of Hand",
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
    # bare variants (older sheet format)
    "savehit", "castingtime", "range", "components", "duration",
    "source", "notes", "prepared",
)

# Strip leading "spell" prefix when storing the key inside a spell entry
_SPELL_KEY_RE = re.compile(r"^spell")

# ── Helpers ───────────────────────────────────────────────────────────────────

def norm(s):
    return s.strip().lower()

def drop_trailing_digits(s):
    return re.sub(r'\s*\d+$', '', s)

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
    """Parse a single character sheet PDF and return structured data."""
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

            ln  = norm(raw)
            lns = drop_trailing_digits(ln)

            # 1. Character info
            key = CHARACTER_CANONICAL.get(ln) or CHARACTER_CANONICAL.get(lns)
            if key:
                if key not in data["character"]:
                    data["character"][key] = val
                continue

            # 2. Ability scores
            ab_key = ABILITY_KEYS.get(ln) or ABILITY_KEYS.get(ln.rstrip())
            if ab_key:
                data["abilities"][ab_key] = val
                continue

            # 3. Saving throws
            if ln in SAVING_THROW_VALUE_MAP:
                data["saving_throws"].setdefault(
                    SAVING_THROW_VALUE_MAP[ln], {})["value"] = val
                continue
            if ln in SAVING_THROW_PROF_MAP:
                data["saving_throws"].setdefault(
                    SAVING_THROW_PROF_MAP[ln], {})["prof"] = val
                continue

            # 4. Combat / carry
            if ln in COMBAT_FIELDS:
                data["combat"][COMBAT_FIELDS[ln]] = val
                continue

            # 5. Passives / senses / defenses
            if ln in PASSIVE_FIELDS:
                data["passives"][PASSIVE_FIELDS[ln]] = val
                continue
            if ln == "additionalsenses":
                data["senses"] = val
                continue
            if ln == "defenses":
                data["defenses"] = val
                continue

            # 6. Currency
            if ln in CURRENCY_FIELDS:
                data["currency"][ln] = val
                continue

            # 7. Skills
            sk = skill_base(ln)
            if sk:
                entry = data["skills"].setdefault(sk, {
                    "name":    SKILL_DISPLAY.get(sk, sk.capitalize()),
                    "value":   "",
                    "prof":    "",
                    "ability": "",
                })
                if ln.endswith("prof"):
                    entry["prof"] = val
                elif ln.endswith("mod"):
                    entry["ability"] = val
                else:
                    entry["value"] = val
                continue

            # 8. Equipment
            eq_n  = re.fullmatch(r'eq name(\d+)',        ln)
            eq_q  = re.fullmatch(r'eq qty(\d+)',         ln)
            eq_w  = re.fullmatch(r'eq weight(\d+)',      ln)
            at_n  = re.fullmatch(r'attuned name(\d+)',   ln)
            at_q  = re.fullmatch(r'attuned qty(\d+)',    ln)
            at_w  = re.fullmatch(r'attuned weight(\d+)', ln)
            at_w2 = re.fullmatch(r'attunedweight(\d+)',  ln)

            eq_hit = False
            for m, field, pfx in [
                (eq_n,  "name",   "eq"),  (eq_q,  "qty",    "eq"),
                (eq_w,  "weight", "eq"),  (at_n,  "name",   "att"),
                (at_q,  "qty",    "att"), (at_w,  "weight", "att"),
                (at_w2, "weight", "att"),
            ]:
                if m:
                    slot = f"{pfx}_{m.group(1)}"
                    data["equipment"].setdefault(
                        slot, {"name": "", "qty": "", "weight": "", "attuned": pfx == "att"})
                    data["equipment"][slot][field] = val
                    eq_hit = True
                    break
            if eq_hit:
                continue

            # 9. Weapons
            wn = re.fullmatch(r'wpn name\s*(\d*)', ln)
            wa = re.search(r'^wpn(\d+)\s*atkbonus', ln)
            wd = re.search(r'^wpn(\d+)\s*damage',   ln)
            wo = re.search(r'^wpn\s*notes\s*(\d+)', ln)

            wpn_hit = False
            if wn:
                idx = int(wn.group(1)) if wn.group(1) else 1
                data["weapons"].setdefault(idx, {"name": "", "atk_bonus": "", "damage": "", "notes": ""})
                data["weapons"][idx]["name"] = val
                wpn_hit = True
            elif wa:
                idx = int(wa.group(1))
                data["weapons"].setdefault(idx, {"name": "", "atk_bonus": "", "damage": "", "notes": ""})
                data["weapons"][idx]["atk_bonus"] = val
                wpn_hit = True
            elif wd:
                idx = int(wd.group(1))
                data["weapons"].setdefault(idx, {"name": "", "atk_bonus": "", "damage": "", "notes": ""})
                data["weapons"][idx]["damage"] = val
                wpn_hit = True
            elif wo:
                idx = int(wo.group(1))
                data["weapons"].setdefault(idx, {"name": "", "atk_bonus": "", "damage": "", "notes": ""})
                data["weapons"][idx]["notes"] = val
                wpn_hit = True
            if wpn_hit:
                continue

            # 10. Spells
            sm = re.search(r'(\d+)$', ln)
            if sm and any(ln.startswith(p) for p in SPELL_PREFIXES):
                idx = int(sm.group(1))
                # Strip trailing digits, then strip leading "spell" prefix so
                # e.g. "spellprepared3" → "prepared", "spellsavehit0" → "savehit"
                field_key = re.sub(r'\d+$', '', ln).rstrip()
                field_key = _SPELL_KEY_RE.sub('', field_key)
                data["spells"].setdefault(idx, {})[field_key] = val
                continue

            # 11. Features & actions
            if ln.startswith("featurestraits"):
                data["features"].append(val)
                continue
            if ln.startswith("actions"):
                data["actions"].append(val)
                continue

            # 12. Proficiencies & languages
            if ln.startswith("proficiencies") or ln == "proficiencieslang":
                if data["proficiencies"]:
                    data["proficiencies"] += "\n" + val
                else:
                    data["proficiencies"] = val
                continue

            # 13. Personality / backstory
            pk = PERSONALITY_FIELDS.get(ln) or PERSONALITY_FIELDS.get(lns)
            if pk:
                data["personality"][pk] = val
                continue

            # 14. Catch-all
            data["notes"][ln] = val

    # ── Post-process ──────────────────────────────────────────────────────────

    data["weapons"] = [
        data["weapons"][i]
        for i in sorted(data["weapons"])
        if data["weapons"][i].get("name")
    ]

    data["equipment"] = [
        v for k, v
        in sorted(data["equipment"].items(), key=lambda x: _eq_sort_key(x[0]))
        if v.get("name")
    ]

    seen, ordered = set(), []
    for sk in SKILL_ORDER:
        if sk in data["skills"] and sk not in seen:
            ordered.append(data["skills"][sk])
            seen.add(sk)
    for sk, v in data["skills"].items():
        if sk not in seen:
            ordered.append(v)
    data["skills"] = ordered

    data["spells"] = [
        data["spells"][i]
        for i in sorted(data["spells"])
        if any(data["spells"][i].values())
    ]

    data["features"] = "\n".join(data["features"]).strip()
    data["actions"]  = "\n".join(data["actions"]).strip()

    return data

# ── Batch runner ──────────────────────────────────────────────────────────────

def main():
    if not INPUT_DIR.exists():
        print(f"Error: input directory '{INPUT_DIR}' not found.", file=sys.stderr)
        sys.exit(1)

    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in '{INPUT_DIR}'.", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ok, failed = 0, []
    for pdf_path in pdf_files:
        out_path = OUTPUT_DIR / (pdf_path.stem + ".json")
        try:
            data = parse_sheet(pdf_path)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  ✓  {pdf_path.name}  →  {out_path}")
            ok += 1
        except Exception as e:
            print(f"  ✗  {pdf_path.name}  —  {e}", file=sys.stderr)
            failed.append(pdf_path.name)

    print(f"\nDone: {ok} exported, {len(failed)} failed.")
    if failed:
        for name in failed:
            print(f"  failed: {name}", file=sys.stderr)

if __name__ == "__main__":
    main()
