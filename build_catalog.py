import json
import os

db_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\db.json"
leftover_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\leftover_db.json"
out_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\twinksim_web\catalog_full.json"

with open(db_path, "r", encoding="utf-8") as f:
    db = json.load(f)
with open(leftover_path, "r", encoding="utf-8") as f:
    ldb = json.load(f)

zones = {z["id"]: z.get("name", "") for z in db.get("zones", [])}
npcs = {n["id"]: n.get("name", "") for n in db.get("npcs", [])}

items_by_id = {}
for it in (db.get("items", []) + ldb.get("items", [])):
    items_by_id[it["id"]] = it

quality_names = {0: "poor", 1: "common", 2: "uncommon", 3: "rare", 4: "epic", 5: "legendary"}
weapon_type_names = {1: "Axe", 2: "Dagger", 3: "Fist", 4: "Mace", 5: "Off-Hand", 7: "Shield", 8: "Staff"}
armor_type_names = {0: "", 1: "Cloth", 2: "Leather", 3: "Mail", 4: "Plate"}

# Exact Stat enum from common.proto (0-indexed)
STAT_NAMES = {
    0: "Str",
    1: "Agi",
    2: "Sta",
    3: "Int",
    4: "Healing",
    5: "SP",
    6: "Arcane SP",
    7: "Fire SP",
    8: "Frost SP",
    9: "Holy SP",
    10: "Nature SP",
    11: "Shadow SP",
    12: "Spell Pen",
    13: "Spi",
    14: "AP",
    15: "RAP",
    16: "Feral AP",
    17: "Hit",
    18: "Crit",
    19: "Haste",
    20: "ArP",
    21: "Exp",
    22: "Def",
    23: "Block",
    24: "Block Value",
    25: "Dodge",
    26: "Parry",
    27: "Armor",
    28: "Bonus Armor",
    29: "Health",
    30: "Mana",
    31: "MP5",
    32: "Arcane Res",
    33: "Fire Res",
    34: "Frost Res",
    35: "Nature Res",
    36: "Shadow Res",
    37: "Phys Dmg"
}

slot_map = {
    1: "head", 2: "neck", 3: "shoulders", 4: "back", 5: "chest",
    6: "wrist", 7: "hands", 8: "waist", 9: "legs", 10: "feet",
    11: "finger", 12: "trinket", 14: "relic"
}

slot_names_display = {
    "head": "Head", "neck": "Neck", "shoulders": "Shoulders", "back": "Back",
    "chest": "Chest", "wrist": "Wrist", "hands": "Hands", "waist": "Waist",
    "legs": "Legs", "feet": "Feet", "finger": "Finger", "trinket": "Trinket",
    "mainhand": "Main Hand", "offhand": "Off Hand", "relic": "Relic"
}

catalog = {s: [] for s in [
    "head", "neck", "shoulders", "back", "chest", "wrist",
    "hands", "waist", "legs", "feet", "finger", "trinket",
    "mainhand", "offhand", "relic"
]}

for it in items_by_id.values():
    req = it.get("reqLvl", 0)
    if req > 19:
        continue
    sc = it.get("scalingOptions", {})
    ilvl = list(sc.values())[0].get("ilvl", 0) if sc else 0
    if req == 0 and ilvl > 26:
        continue
    if ilvl > 28:
        continue
    
    atype = it.get("armorType", 0)
    itype = it.get("type", 0)
    wtype = it.get("weaponType", 0)
    htype = it.get("handType", 0)
    
    # Allowed armor types for Lvl 19 Twink Shaman (Cloth, Leather, Shields, Misc)
    if atype not in [0, 1, 2]:
        continue
    
    # Target slot
    target_slot = None
    if itype == 13: # Weapon
        if wtype in [6, 9]: # Polearm, Sword
            continue
        if htype == 4 and wtype in [1, 4]: # 2H axe, 2H mace
            continue
        if wtype in [5, 7] or htype == 3:
            target_slot = "offhand"
        else:
            target_slot = "mainhand"
    elif itype in slot_map:
        target_slot = slot_map[itype]
        
    if not target_slot:
        continue
    
    # Stat summary & parsed stats
    summary_parts = []
    first_sc = list(sc.values())[0] if sc else {}
    
    speed = it.get("weaponSpeed", 0)
    dmin = first_sc.get("weaponDamageMin", 0)
    dmax = first_sc.get("weaponDamageMax", 0)
    if speed > 0:
        summary_parts.append(f"{speed:.2f}s ({dmin}-{dmax})")
        
    stats_dict = first_sc.get("stats", {})
    parsed_stats = {}
    armor_val = stats_dict.get("27", 0)
    
    if armor_val > 0:
        summary_parts.append(f"{armor_val} Armor")
        
    for sid_str, sval in stats_dict.items():
        sid = int(sid_str)
        if sid == 27: # Handled armor above
            continue
        sname = STAT_NAMES.get(sid)
        if sname and sval != 0:
            parsed_stats[sname] = sval
            prefix = "+" if sval > 0 else ""
            summary_parts.append(f"{prefix}{sval} {sname}")
            
    summary_str = ", ".join(summary_parts)
    
    # Source detection
    source_str = ""
    sources = it.get("sources", [])
    if sources:
        first_src = sources[0]
        if "drop" in first_src:
            drop = first_src["drop"]
            n_name = npcs.get(drop.get("npcId", 0), "")
            z_name = zones.get(drop.get("zoneId", 0), "")
            if n_name and z_name:
                source_str = f"Drop: {n_name} ({z_name})"
            elif z_name:
                source_str = f"Drop: {z_name}"
            elif n_name:
                source_str = f"Drop: {n_name}"
        elif "quest" in first_src:
            source_str = "Quest Reward"
        elif "craft" in first_src:
            source_str = "Crafted"
            
    catalog[target_slot].append({
        "id": it["id"],
        "name": it.get("name", f"Item {it['id']}"),
        "quality": quality_names.get(it.get("quality", 1), "common"),
        "icon": it.get("icon", "inv_misc_questionmark"),
        "ilvl": ilvl,
        "reqLvl": req,
        "summary": summary_str,
        "armor": armor_val,
        "speed": speed,
        "dmgMin": dmin,
        "dmgMax": dmax,
        "parsedStats": parsed_stats,
        "armorType": armor_type_names.get(atype, ""),
        "slotName": slot_names_display.get(target_slot, ""),
        "source": source_str,
        "isCustom": (it["id"] >= 200000),
        "is2H": (htype == 4),
        "isShield": (wtype == 7)
    })

# Add empty/none to each slot
for s in catalog:
    catalog[s].insert(0, {
        "id": 0,
        "name": "None",
        "quality": "common",
        "icon": "inventoryslot_empty",
        "ilvl": 0,
        "reqLvl": 0,
        "summary": "Empty slot",
        "armor": 0,
        "speed": 0,
        "dmgMin": 0,
        "dmgMax": 0,
        "parsedStats": {},
        "armorType": "",
        "slotName": slot_names_display.get(s, ""),
        "source": "",
        "isCustom": False,
        "is2H": False,
        "isShield": False
    })

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(catalog, f, indent=2)

print(f"Successfully generated {out_path} with accurate stats and sources!")
for slot in ["feet", "mainhand", "neck"]:
    print(f"Slot {slot} count: {len(catalog[slot])}")
