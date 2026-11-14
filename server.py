import time
import os
import sys
import json
import subprocess
import copy
import gzip
import hashlib
import tempfile
import concurrent.futures
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="WoW Forever Lvl 19 Twink Simulator", version="2.0")

CLI_PATH = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsimcli.exe"
BASE_JSON_PATH = r"C:\Users\jcbas\.gemini\antigravity\scratch\test_twink_request.json"
WEB_DIR = r"C:\Users\jcbas\.gemini\antigravity\scratch\twinksim_web"
CATALOG_PATH = os.path.join(WEB_DIR, "catalog_full.json")
TALENTS_PATH = os.path.join(WEB_DIR, "talents_data.json")
ENCHANTS_PATH = os.path.join(WEB_DIR, "enchants_data.json")
SCENARIOS_PATH = os.path.join(WEB_DIR, "scenarios_data.json")

with open(BASE_JSON_PATH, "r", encoding="utf-8") as f:
    BASE_REQ = json.load(f)

with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    ITEM_CATALOG = json.load(f)

ITEM_LOOKUP = {}
for slot_items in ITEM_CATALOG.values():
    for it in slot_items:
        ITEM_LOOKUP[it["id"]] = it

with open(TALENTS_PATH, "r", encoding="utf-8") as f:
    TALENT_TREES = json.load(f)

with open(ENCHANTS_PATH, "r", encoding="utf-8") as f:
    ENCHANTS_DATA = json.load(f)

# --- HIGH-PERFORMANCE STATIC ASSET CACHING & PRE-GZIP ---
def prepare_asset(file_path: str, media_type: str):
    with open(file_path, "rb") as f:
        raw_bytes = f.read()
    gz_bytes = gzip.compress(raw_bytes, compresslevel=6)
    etag = f'"{hashlib.md5(raw_bytes).hexdigest()}"'
    return {
        "raw": raw_bytes,
        "gz": gz_bytes,
        "etag": etag,
        "media_type": media_type,
        "mtime": os.path.getmtime(file_path),
        "path": file_path
    }

ASSETS: Dict[str, Any] = {
    "catalog": prepare_asset(CATALOG_PATH, "application/json"),
    "talents": prepare_asset(TALENTS_PATH, "application/json"),
    "enchants": prepare_asset(ENCHANTS_PATH, "application/json"),
    "scenarios": prepare_asset(SCENARIOS_PATH, "application/json"),
    "index": prepare_asset(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8")
}

def get_asset_response(req: Request, key: str):
    asset = ASSETS.get(key)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Auto-refresh if file changed on disk
    try:
        cur_mtime = os.path.getmtime(asset["path"])
        if cur_mtime > asset["mtime"]:
            ASSETS[key] = prepare_asset(asset["path"], asset["media_type"])
            asset = ASSETS[key]
    except Exception:
        pass
    
    inm = req.headers.get("if-none-match")
    if inm and asset["etag"] in inm:
        return Response(status_code=304, headers={"ETag": asset["etag"], "Cache-Control": "no-cache, must-revalidate"})
    
    ae = req.headers.get("accept-encoding", "")
    if "gzip" in ae.lower():
        return Response(
            content=asset["gz"],
            media_type=asset["media_type"],
            headers={
                "Content-Encoding": "gzip",
                "ETag": asset["etag"],
                "Cache-Control": "no-cache, must-revalidate"
            }
        )
    else:
        return Response(
            content=asset["raw"],
            media_type=asset["media_type"],
            headers={
                "ETag": asset["etag"],
                "Cache-Control": "no-cache, must-revalidate"
            }
        )

# In-memory simulation result cache (LRU)
SIM_CACHE: Dict[str, Any] = {}

SLOT_INDEX_MAP = {
    "head": 0,
    "neck": 1,
    "shoulders": 2,
    "back": 3,
    "chest": 4,
    "wrist": 5,
    "hands": 6,
    "waist": 7,
    "legs": 8,
    "feet": 9,
    "ring1": 10,
    "ring2": 11,
    "trinket1": 12,
    "trinket2": 13,
    "mainhand": 14,
    "offhand": 15,
    "relic": 16,
}


# ==============================================================================
# CONSUMABLE & BUFF DEFINITIONS (FOOD, POTIONS, ELIXIRS, SCROLLS, CLASS BUFFS)
# ==============================================================================
BUFF_DEFINITIONS = {
# 1. Food Buffs (Well Fed) - Level 1 to 29 Brackets
    "food_sagefish_delight": {
        "id": "food_sagefish_delight",
        "name": "Sagefish Delight",
        "category": "food",
        "stats": {"MP5": 6},
        "icon": "inv_misc_fish_02",
        "desc": "Restores 6 mana every 5 seconds for 15 min (Well Fed - Top Resto/Caster BiS)",
        "level": 25
    },
    "food_sagefish": {
        "id": "food_sagefish",
        "name": "Smoked Sagefish",
        "category": "food",
        "stats": {"MP5": 3},
        "icon": "inv_misc_fish_02",
        "desc": "Restores 3 mana every 5 seconds for 15 min (Well Fed - Level 10-24 Mana BiS)",
        "level": 10
    },
    "food_heavy_croc": {
        "id": "food_heavy_croc",
        "name": "Soothing Turtle Bisque / Heavy Crocolisk Stew",
        "category": "food",
        "stats": {"Sta": 8, "Spi": 8},
        "icon": "inv_misc_food_14",
        "desc": "+8 Stamina and +8 Spirit for 15 min (Well Fed - Top Level 25-29 Stamina BiS)",
        "level": 25
    },
    "food_wolf_ribs": {
        "id": "food_wolf_ribs",
        "name": "Hot Wolf Ribs / Roast Raptor (Rank 2)",
        "category": "food",
        "stats": {"Spi": 8, "Sta": 8},
        "icon": "inv_misc_food_09",
        "desc": "+8 Spirit and +8 Stamina for 15 min (Well Fed - Level 25+)",
        "level": 25
    },
    "food_dragonbreath": {
        "id": "food_dragonbreath",
        "name": "Dragonbreath Chili",
        "category": "food",
        "stats": {"FireSP": 8, "SP": 6},
        "icon": "spell_fire_incinerate",
        "desc": "Periodically belches fire at enemies in combat for 10 min (Damage/Fire Caster BiS)",
        "level": 25
    },
    "food_raptor": {
        "id": "food_raptor",
        "name": "Roast Raptor / Clamlette Surprise",
        "category": "food",
        "stats": {"Sta": 6, "Spi": 6},
        "icon": "inv_misc_food_14",
        "desc": "+6 Stamina and +6 Spirit for 15 min (Well Fed - Level 15-24 Stamina BiS)",
        "level": 15
    },
    "food_lion": {
        "id": "food_lion",
        "name": "Hot Lion Chops / Clam Chowder",
        "category": "food",
        "stats": {"Str": 6, "Spi": 6},
        "icon": "inv_misc_food_23",
        "desc": "+6 Strength and +6 Spirit for 15 min (Well Fed - Level 15-24 Melee DPS BiS)",
        "level": 15
    },
    "food_digrat": {
        "id": "food_digrat",
        "name": "Dig Rat Stew",
        "category": "food",
        "stats": {"Agi": 6, "Spi": 6},
        "icon": "inv_misc_food_11",
        "desc": "+6 Agility and +6 Spirit for 15 min (Well Fed - Level 15-24 Agility BiS)",
        "level": 15
    },
    "food_crispy_bat": {
        "id": "food_crispy_bat",
        "name": "Crispy Bat Wing / Boiled Clams",
        "category": "food",
        "stats": {"Sta": 4, "Spi": 4},
        "icon": "inv_misc_food_05",
        "desc": "+4 Stamina and +4 Spirit for 15 min (Well Fed - Level 10-14)",
        "level": 10
    },
    "food_eggs": {
        "id": "food_eggs",
        "name": "Herb Baked Eggs / Spiced Wolf",
        "category": "food",
        "stats": {"Sta": 2, "Spi": 2},
        "icon": "inv_misc_food_16",
        "desc": "+2 Stamina and +2 Spirit for 15 min (Well Fed - Level 1-9 Starter BiS)",
        "level": 1
    },
    "consum_rumsey_black": {
        "id": "consum_rumsey_black",
        "name": "Rumsey Rum Black Label",
        "category": "potion",
        "stats": {"Sta": 15, "Spi": -5},
        "icon": "inv_drink_04",
        "desc": "Increases Stamina by 15, decreases Spirit by 5 for 15 min (Alcohol / Stackable)",
        "level": 1
    },
    "consum_gordok_grog": {
        "id": "consum_gordok_grog",
        "name": "Gordok Green Grog",
        "category": "potion",
        "stats": {"Sta": 10},
        "icon": "inv_drink_07",
        "desc": "Increases Stamina by 10 for 15 min (Alcohol / Stackable)",
        "level": 1
    },
    "consum_kreeg_stout": {
        "id": "consum_kreeg_stout",
        "name": "Kreeg's Stout Beatdown",
        "category": "potion",
        "stats": {"Spi": 25, "Int": -5},
        "icon": "inv_drink_05",
        "desc": "Increases Spirit by 25, decreases Intellect by 5 for 15 min (Alcohol / Stackable)",
        "level": 1
    },

    # 2. Battle & Guardian Elixirs & Potions
    "elixir_giant_growth": {
        "id": "elixir_giant_growth",
        "name": "Elixir of Giant Growth",
        "category": "potion",
        "stats": {"Str": 8},
        "icon": "inv_potion_14",
        "desc": "Increases Strength by 8 and character size for 20 min",
        "level": 8
    },
    "elixir_lesser_agility": {
        "id": "elixir_lesser_agility",
        "name": "Elixir of Lesser Agility",
        "category": "potion",
        "stats": {"Agi": 8},
        "icon": "inv_potion_93",
        "desc": "Increases Agility by 8 for 1 hr",
        "level": 18
    },
    "elixir_minor_agility": {
        "id": "elixir_minor_agility",
        "name": "Elixir of Minor Agility",
        "category": "potion",
        "stats": {"Agi": 4},
        "icon": "inv_potion_93",
        "desc": "Increases Agility by 4 for 1 hr",
        "level": 2
    },
    "elixir_wisdom": {
        "id": "elixir_wisdom",
        "name": "Elixir of Wisdom",
        "category": "potion",
        "stats": {"Int": 6},
        "icon": "inv_potion_91",
        "desc": "Increases Intellect by 6 for 1 hr",
        "level": 17
    },
    "elixir_defense": {
        "id": "elixir_defense",
        "name": "Elixir of Defense",
        "category": "potion",
        "stats": {"Armor": 50},
        "icon": "inv_potion_66",
        "desc": "Increases Armor by 50 for 1 hr",
        "level": 16
    },
    "elixir_troll_blood": {
        "id": "elixir_troll_blood",
        "name": "Strong Troll's Blood Potion",
        "category": "potion",
        "stats": {"HP5": 6},
        "icon": "inv_potion_79",
        "desc": "Regenerates 6 health every 5 seconds for 1 hr",
        "level": 15
    },
    "elixir_ogre_strength": {
        "id": "elixir_ogre_strength",
        "name": "Elixir of Ogre's Strength",
        "category": "potion",
        "stats": {"Str": 8},
        "icon": "inv_potion_87",
        "desc": "Increases Strength by 8 for 1 hr",
        "level": 20
    },
    "elixir_fortitude": {
        "id": "elixir_fortitude",
        "name": "Elixir of Fortitude",
        "category": "potion",
        "stats": {"Sta": 12},
        "icon": "inv_potion_43",
        "desc": "Increases maximum health by 120 (+12 Stamina equivalent) for 1 hr",
        "level": 25
    },

    # 3. Scrolls & Weapon Oils
    "scroll_agi_2": {
        "id": "scroll_agi_2",
        "name": "Scroll of Agility II",
        "category": "scroll",
        "stats": {"Agi": 5},
        "icon": "inv_scroll_02",
        "desc": "Increases the target's Agility by 5 for 30 min",
        "level": 15
    },
    "scroll_str_2": {
        "id": "scroll_str_2",
        "name": "Scroll of Strength II",
        "category": "scroll",
        "stats": {"Str": 5},
        "icon": "inv_scroll_01",
        "desc": "Increases the target's Strength by 5 for 30 min",
        "level": 15
    },
    "scroll_prot_2": {
        "id": "scroll_prot_2",
        "name": "Scroll of Protection II",
        "category": "scroll",
        "stats": {"Armor": 60},
        "icon": "inv_scroll_08",
        "desc": "Increases Armor by 60 for 30 min",
        "level": 15
    },
    "scroll_sta_2": {
        "id": "scroll_sta_2",
        "name": "Scroll of Stamina II",
        "category": "scroll",
        "stats": {"Sta": 5},
        "icon": "inv_scroll_07",
        "desc": "Increases the target's Stamina by 5 for 30 min",
        "level": 15
    },
    "scroll_int_2": {
        "id": "scroll_int_2",
        "name": "Scroll of Intellect II",
        "category": "scroll",
        "stats": {"Int": 5},
        "icon": "inv_scroll_04",
        "desc": "Increases the target's Intellect by 5 for 30 min",
        "level": 15
    },
    "oil_wizard": {
        "id": "oil_wizard",
        "name": "Minor Wizard Oil",
        "category": "oil",
        "stats": {"SP": 10},
        "icon": "inv_potion_105",
        "desc": "While applied to target weapon it increases spell damage by up to 10 for 30 min",
        "level": 20
    },
    "oil_mana": {
        "id": "oil_mana",
        "name": "Minor Mana Oil",
        "category": "oil",
        "stats": {"MP5": 4},
        "icon": "inv_potion_99",
        "desc": "While applied to target weapon it restores 4 mana every 5 seconds for 30 min",
        "level": 20
    },
    "oil_blackfathom": {
        "id": "oil_blackfathom",
        "name": "Blackfathom Oil",
        "category": "oil",
        "stats": {"Hit": 2},
        "icon": "inv_potion_26",
        "desc": "Increases chance to hit with melee and spells by 2% for 30 min",
        "level": 15
    },

    # 4. Class & Raid Buffs (Optional Party Buffs)
    "buff_fortitude": {
        "id": "buff_fortitude",
        "name": "Power Word: Fortitude",
        "category": "class",
        "stats": {"Sta": 14},
        "icon": "spell_holy_wordfortitude",
        "desc": "Priest Buff: Increases Stamina by 14 for 30 min",
        "level": 12
    },
    "buff_intellect": {
        "id": "buff_intellect",
        "name": "Arcane Intellect",
        "category": "class",
        "stats": {"Int": 7},
        "icon": "spell_holy_magicalsentry",
        "desc": "Mage Buff: Increases Intellect by 7 for 30 min",
        "level": 14
    },
    "buff_motw": {
        "id": "buff_motw",
        "name": "Mark of the Wild",
        "category": "class",
        "stats": {"Str": 1, "Agi": 1, "Sta": 1, "Int": 1, "Spi": 1, "Armor": 25},
        "icon": "spell_nature_regeneration",
        "desc": "Druid Buff: Increases all attributes by 1 and Armor by 25 for 30 min",
        "level": 10
    },
    "buff_battle_shout": {
        "id": "buff_battle_shout",
        "name": "Battle Shout",
        "category": "class",
        "stats": {"AP": 15},
        "icon": "ability_warrior_battleshout",
        "desc": "Warrior Shout: Increases Attack Power by 15 for 2 min",
        "level": 12
    },
    "buff_might": {
        "id": "buff_might",
        "name": "Blessing of Might",
        "category": "class",
        "stats": {"AP": 20},
        "icon": "spell_holy_fistofjustice",
        "desc": "Paladin Blessing: Increases Attack Power by 20 for 5 min",
        "level": 12
    }
}

def calculate_bonus_stats_from_buffs(buffs):
    if not buffs:
        return {}
    if isinstance(buffs, list):
        active_keys = buffs
    elif isinstance(buffs, dict):
        active_keys = [k for k, v in buffs.items() if v]
    else:
        active_keys = []
        
    total = {
        "Str": 0, "Agi": 0, "Sta": 0, "Int": 0, "Spi": 0,
        "AP": 0, "Crit": 0, "Hit": 0, "Armor": 0,
        "Healing": 0, "SP": 0, "FireSP": 0, "NatureSP": 0,
        "FrostResist": 0, "NatureResist": 0, "FireResist": 0, "ShadowResist": 0,
        "MP5": 0, "HP5": 0
    }
    for b_id in active_keys:
        if b_id in BUFF_DEFINITIONS:
            for stat_k, stat_v in BUFF_DEFINITIONS[b_id]["stats"].items():
                if stat_k in total:
                    total[stat_k] += stat_v
    return total

def build_bonus_stats_proto(bonus_dict):
    stats_arr = [0.0] * 35
    stats_arr[0] = float(bonus_dict.get("Str", 0))
    stats_arr[1] = float(bonus_dict.get("Agi", 0))
    stats_arr[2] = float(bonus_dict.get("Sta", 0))
    stats_arr[3] = float(bonus_dict.get("Int", 0))
    stats_arr[4] = float(bonus_dict.get("Healing", 0))
    stats_arr[5] = float(bonus_dict.get("SP", 0))
    stats_arr[7] = float(bonus_dict.get("FireSP", 0))
    stats_arr[10] = float(bonus_dict.get("NatureSP", 0))
    stats_arr[13] = float(bonus_dict.get("Spi", 0))
    stats_arr[14] = float(bonus_dict.get("AP", 0))
    stats_arr[17] = float(bonus_dict.get("Hit", 0))
    stats_arr[18] = float(bonus_dict.get("Crit", 0))
    stats_arr[27] = float(bonus_dict.get("Armor", 0))
    stats_arr[31] = float(bonus_dict.get("MP5", 0))
    return stats_arr

class SimRequest(BaseModel):
    level: int = 19
    imbue: str = "FlametongueWeapon"  # "FlametongueWeapon", "RockbiterWeapon", "FrostbrandWeapon"
    talents: str = "-05203-"
    rotation_preset: str = "burst"    # "burst", "smart", "earth_only", "flame_only", "no_totem", "melee_only"
    duration: int = 30
    iterations: int = 200
    gear: Dict[str, int] = {}
    enchants: Optional[Dict[str, int]] = {}
    custom_rotation: Optional[List[Dict[str, Any]]] = None
    buffs: Optional[Any] = None


@app.get("/api/buffs")
def get_buffs():
    return BUFF_DEFINITIONS

@app.get("/api/patch-notes")
def get_patch_notes():
    patch_file = os.path.join(WEB_DIR, "wow_forever_patches.json")
    if os.path.exists(patch_file):
        with open(patch_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"activeVersion": "v1.4.2-Live", "patches": []}

@app.get("/api/catalog")
def get_catalog(request: Request):
    return get_asset_response(request, "catalog")

@app.get("/api/talents")
def get_talents(request: Request):
    return get_asset_response(request, "talents")

@app.get("/api/enchants")
def get_enchants(request: Request):
    return get_asset_response(request, "enchants")

@app.get("/api/scenarios")
def get_scenarios(request: Request):
    return get_asset_response(request, "scenarios")

@app.post("/api/simulate")
def simulate(req: SimRequest):
    sim_cache_key = hashlib.md5(json.dumps(req.dict(), sort_keys=True).encode('utf-8')).hexdigest()
    if sim_cache_key in SIM_CACHE:
        return copy.deepcopy(SIM_CACHE[sim_cache_key])
    
    cfg = copy.deepcopy(BASE_REQ)
    player = cfg["raid"]["parties"][0]["players"][0]
    
    # 0. Apply Consumable & Food/Potion Buffs
    bonus_dict = calculate_bonus_stats_from_buffs(req.buffs)
    if any(bonus_dict.values()):
        player["bonusStats"] = {"stats": build_bonus_stats_proto(bonus_dict)}

    # 1. Encounter options
    cfg["simOptions"]["iterations"] = max(10, min(2000, req.iterations))
    cfg["encounter"]["duration"] = max(5, min(300, req.duration))
    if "targets" in cfg["encounter"] and len(cfg["encounter"]["targets"]) > 0:
        cfg["encounter"]["targets"][0]["level"] = req.level
    
    # 2. Imbue
    player["enhancementShaman"]["options"]["classOptions"]["imbueMh"] = req.imbue
    
    # 3. Talents
    # Format: tree0-tree1-tree2 (e.g. -05203- or --55)
    tal_raw = req.talents.strip()
    if tal_raw.startswith("-") and not tal_raw.startswith("--"):
        # e.g. -05203 or -05203-
        tal_parts = tal_raw.strip("-").split("-")
        t0 = ""
        t1 = tal_parts[0] if len(tal_parts) > 0 else ""
        t2 = tal_parts[1] if len(tal_parts) > 1 else ""
        tal_str = f"-{t1}-{t2}".rstrip("-")
        if tal_str == "-":
            tal_str = "--"
    elif tal_raw.startswith("--"):
        # e.g. --55 or --552-
        t2 = tal_raw.lstrip("-").rstrip("-")
        t0, t1 = "", ""
        tal_str = f"--{t2}"
    else:
        tal_parts = tal_raw.split("-")
        t0 = tal_parts[0] if len(tal_parts) > 0 else ""
        t1 = tal_parts[1] if len(tal_parts) > 1 else ""
        t2 = tal_parts[2] if len(tal_parts) > 2 else ""
        tal_str = f"{t0}-{t1}-{t2}".rstrip("-")
    
    player["talentsString"] = tal_str
    
    # 4. Gear & Enchants
    enchants = req.enchants or {}
    for slot, item_id in req.gear.items():
        if slot in SLOT_INDEX_MAP:
            idx = SLOT_INDEX_MAP[slot]
            if item_id > 0:
                item_spec = {"id": item_id}
                enc_id = enchants.get(slot, 0)
                if enc_id > 0:
                    item_spec["enchant"] = enc_id
                player["equipment"]["items"][idx] = item_spec
            else:
                player["equipment"]["items"][idx] = {}
                
    # 5. Rotation APL
    if req.custom_rotation is not None:
        prio_list = []
        for step in req.custom_rotation:
            if not step.get("enabled", True):
                continue
            sid = int(step.get("spellId", 0))
            cond = step.get("condition", "on_cd")
            
            if sid == 3599:  # Searing Totem
                if cond == "totem_le_1s":
                    prio_list.append({
                        "action": {
                            "condition": {
                                "cmp": {
                                    "op": "OpLe",
                                    "lhs": { "totemRemainingTime": { "totemType": "Fire" } },
                                    "rhs": { "const": { "val": "1s" } }
                                }
                            },
                            "castSpell": { "spellId": { "spellId": 3599 } }
                        }
                    })
                else:
                    prio_list.append({ "action": { "castSpell": { "spellId": { "spellId": 3599 } } } })
            elif sid == 8052:  # Flame Shock
                if cond == "dot_not_active":
                    prio_list.append({
                        "action": {
                            "condition": {
                                "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                            },
                            "castSpell": { "spellId": { "spellId": 8052 } }
                        }
                    })
                else:
                    prio_list.append({ "action": { "castSpell": { "spellId": { "spellId": 8052 } } } })
            elif sid == 324:  # Lightning Shield
                if cond == "buff_not_active":
                    prio_list.append({
                        "action": {
                            "condition": {
                                "not": { "val": { "auraIsActive": { "auraId": { "spellId": 324 } } } }
                            },
                            "castSpell": { "spellId": { "spellId": 324 } }
                        }
                    })
                else:
                    prio_list.append({ "action": { "castSpell": { "spellId": { "spellId": 324 } } } })
            elif sid > 0:
                prio_list.append({ "action": { "castSpell": { "spellId": { "spellId": sid } } } })
                
        player["rotation"]["priorityList"] = prio_list
    elif req.rotation_preset in ["twink29_burst", "stormstrike_burst"]:
        # Stormstrike on CD -> Flame Shock DoT -> Earth Shock on CD -> Searing Totem (Level 25/29 BiS)
        player["rotation"]["priorityList"] = [
            { "action": { "castSpell": { "spellId": { "spellId": 17364 } } } },
            {
                "action": {
                    "condition": {
                        "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                    },
                    "castSpell": { "spellId": { "spellId": 8052 } }
                }
            },
            {
                "action": { "castSpell": { "spellId": { "spellId": 8045 } } }
            },
            {
                "action": {
                    "condition": {
                        "cmp": {
                            "op": "OpLe",
                            "lhs": { "totemRemainingTime": { "totemType": "Fire" } },
                            "rhs": { "const": { "val": "1s" } }
                        }
                    },
                    "castSpell": { "spellId": { "spellId": 3599 } }
                }
            }
        ]
    elif req.rotation_preset == "burst":
        # Flame Shock DoT -> Earth Shock on CD -> Searing Totem (Top DPS)
        player["rotation"]["priorityList"] = [
            {
                "action": {
                    "condition": {
                        "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                    },
                    "castSpell": { "spellId": { "spellId": 8052 } }
                }
            },
            {
                "action": { "castSpell": { "spellId": { "spellId": 8045 } } }
            },
            {
                "action": {
                    "condition": {
                        "cmp": {
                            "op": "OpLe",
                            "lhs": { "totemRemainingTime": { "totemType": "Fire" } },
                            "rhs": { "const": { "val": "1s" } }
                        }
                    },
                    "castSpell": { "spellId": { "spellId": 3599 } }
                }
            }
        ]
    elif req.rotation_preset == "smart":
        player["rotation"]["priorityList"] = [
            {
                "action": {
                    "condition": {
                        "cmp": {
                            "op": "OpLe",
                            "lhs": { "totemRemainingTime": { "totemType": "Fire" } },
                            "rhs": { "const": { "val": "1s" } }
                        }
                    },
                    "castSpell": { "spellId": { "spellId": 3599 } }
                }
            },
            {
                "action": {
                    "condition": {
                        "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                    },
                    "castSpell": { "spellId": { "spellId": 8052 } }
                }
            },
            {
                "action": { "castSpell": { "spellId": { "spellId": 8045 } } }
            }
        ]
    elif req.rotation_preset == "no_totem":
        player["rotation"]["priorityList"] = [
            {
                "action": {
                    "condition": {
                        "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                    },
                    "castSpell": { "spellId": { "spellId": 8052 } }
                }
            },
            {
                "action": { "castSpell": { "spellId": { "spellId": 8045 } } }
            }
        ]
    elif req.rotation_preset == "earth_only":
        player["rotation"]["priorityList"] = [
            { "action": { "castSpell": { "spellId": { "spellId": 8045 } } } }
        ]
    elif req.rotation_preset == "flame_only":
        player["rotation"]["priorityList"] = [
            { "action": { "castSpell": { "spellId": { "spellId": 8052 } } } }
        ]
    elif req.rotation_preset == "melee_only":
        player["rotation"]["priorityList"] = []

    temp_req_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\temp_web_sim.json"
    with open(temp_req_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    try:
        proc = subprocess.run([CLI_PATH, "sim", "--infile", temp_req_path],
                              capture_output=True, text=True, errors="ignore", timeout=35)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Simulation timed out (35s).")

    idx = proc.stdout.find("{")
    if idx == -1:
        raise HTTPException(status_code=500, detail=f"Engine error: {proc.stderr}")

    raw_data = json.loads(proc.stdout[idx:])
    p = raw_data["raidMetrics"]["parties"][0]["players"][0]
    
    spell_names = {
        3599: {
            "name": "Searing Totem (Rank 1)",
            "school": "Fire",
            "icon": "spell_fire_searingtotem",
            "cost": "25 Mana",
            "range": "20 yd range",
            "cast": "Instant",
            "desc": "Summons a Searing Totem with 5 health at the feet of the caster that repeatedly attacks an enemy within 20 yards for 9 to 11 Fire damage every 2.2 sec. Lasts 30 sec."
        },
        17364: {
            "name": "Stormstrike",
            "school": "Physical",
            "icon": "ability_shaman_stormstrike",
            "cost": "8% Base Mana",
            "range": "Melee Range",
            "cast": "Instant • 20 sec cooldown",
            "desc": "Instantly strike with both weapons for 100% weapon damage and increase Nature damage dealt to target by 20% for 12 sec."
        },
        8045: {
            "name": "Earth Shock (Rank 3)",
            "school": "Nature",
            "icon": "spell_nature_earthshock",
            "cost": "70 Mana",
            "range": "20 yd range",
            "cast": "Instant • 6 sec cooldown",
            "desc": "Instantly shocks the target with concussive force, causing 64 to 69 Nature damage, interrupting spellcasting and preventing any spell in that school from being cast for 2 sec. Causes a high amount of threat."
        },
        8052: {
            "name": "Flame Shock (Rank 2)",
            "school": "Fire",
            "icon": "spell_fire_flameshock",
            "cost": "75 Mana",
            "range": "20 yd range",
            "cast": "Instant • 6 sec cooldown",
            "desc": "Instantly sears the target with Fire damage, causing 51 to 59 Fire damage and an additional 48 Fire damage over 12 sec."
        },
        29470: {
            "name": "Flametongue Weapon (Proc)",
            "school": "Fire",
            "icon": "spell_fire_flametounge",
            "cost": "Passive Proc",
            "range": "Melee Range",
            "cast": "Instant on hit",
            "desc": "Each melee hit with the imbued weapon inflicts 18 to 55 additional Fire damage based on weapon speed (slower weapons deal more fire damage per swing). Fire damage ignores enemy physical armor."
        },
        8017: {
            "name": "Rockbiter Weapon",
            "school": "Physical",
            "icon": "spell_nature_rockbiter",
            "cost": "Passive Proc",
            "range": "Melee Range",
            "cast": "Instant on hit",
            "desc": "Imbues the Shaman's weapon with the strength of the earth, increasing melee attack power by 50 and threat caused by attacks."
        },
        8026: {
            "name": "Frostbrand Weapon (Proc)",
            "school": "Frost",
            "icon": "spell_frost_frostbrand",
            "cost": "Passive Proc",
            "range": "Melee Range",
            "cast": "Instant on hit",
            "desc": "Imbues the weapon with frost. Each hit has a chance to cause 47 Frost damage and slow the target's movement speed by 25% for 8 sec."
        },
        324: {
            "name": "Lightning Shield (Rank 2)",
            "school": "Nature",
            "icon": "spell_nature_lightningshield",
            "cost": "70 Mana",
            "range": "Self",
            "cast": "Instant",
            "desc": "Surrounds the caster with 3 balls of lightning. When attacked, causes 26 Nature damage to the attacker. Only one ball can discharge every few seconds. Lasts 10 min."
        },
        913: {
            "name": "Healing Wave (Rank 4)",
            "school": "Nature (Heal)",
            "icon": "spell_nature_magicimmunity",
            "cost": "155 Mana",
            "range": "40 yd range",
            "cast": "2.5 sec cast",
            "desc": "Heals a friendly target for 136 to 163 (+healing scaling). Primary heavy healing wave for Level 19 Twink Shamans."
        },
        547: {
            "name": "Healing Wave (Rank 3)",
            "school": "Nature (Heal)",
            "icon": "spell_nature_magicimmunity",
            "cost": "80 Mana",
            "range": "40 yd range",
            "cast": "2.0 sec cast",
            "desc": "Heals a friendly target for 69 to 82 (+healing scaling). Highly mana-efficient sustained healing spell."
        },
        332: {
            "name": "Healing Wave (Rank 2)",
            "school": "Nature (Heal)",
            "icon": "spell_nature_magicimmunity",
            "cost": "45 Mana",
            "range": "40 yd range",
            "cast": "1.5 sec cast",
            "desc": "Heals a friendly target for 36 to 47 (+healing scaling). Fast emergency heal for critical triage."
        },
        331: {
            "name": "Healing Wave (Rank 1)",
            "school": "Nature (Heal)",
            "icon": "spell_nature_magicimmunity",
            "cost": "25 Mana",
            "range": "40 yd range",
            "cast": "1.5 sec cast",
            "desc": "Heals a friendly target for 18 to 22. Lowest rank healing wave for baiting interrupts or minor top-offs."
        },
        403: {
            "name": "Lightning Bolt (Rank 3)",
            "school": "Nature",
            "icon": "spell_nature_lightning",
            "cost": "60 Mana",
            "range": "30 yd range",
            "cast": "2.5 sec cast",
            "desc": "Casts a bolt of lightning at the enemy target for 49 to 59 Nature damage."
        },
        370: {
            "name": "Purge (Rank 1)",
            "school": "Magic",
            "icon": "spell_nature_purge",
            "cost": "35 Mana",
            "range": "30 yd range",
            "cast": "Instant",
            "desc": "Purges the target of 1 beneficial magic effect."
        },
        2484: {
            "name": "Earthbind Totem (Rank 1)",
            "school": "Nature",
            "icon": "spell_nature_strengthofearthtotem02",
            "cost": "45 Mana",
            "range": "Self",
            "cast": "Instant",
            "desc": "Summons an Earthbind Totem with 5 health at the feet of the caster that pulses every 3 sec, slowing the movement speed of all enemies within 10 yards by 50%. Lasts 45 sec."
        },
        5730: {
            "name": "Stoneclaw Totem (Rank 1)",
            "school": "Nature",
            "icon": "spell_nature_stoneclawtotem",
            "cost": "50 Mana",
            "range": "Self",
            "cast": "Instant",
            "desc": "Summons a Stoneclaw Totem with 50 health at the feet of the caster that pulses threat every 3 sec. Lasts 15 sec."
        },
        0: {
            "name": "Melee (Auto-Attack)",
            "school": "Physical",
            "icon": "inv_staff_13",
            "cost": "Melee Swing",
            "range": "Melee Range",
            "cast": "Instant",
            "desc": "Performs a standard melee swing against the enemy target with your equipped weapon. Deals physical damage calculated from weapon damage and attack power, reduced by enemy armor."
        },
        20004: {
            "name": "Holy Strength (Crusader)",
            "school": "Holy",
            "icon": "spell_holy_blessingofstrength",
            "cost": "Weapon Proc",
            "range": "Self",
            "cast": "Chance on hit",
            "desc": "Enchant Weapon - Crusader proc. Increases Strength by 100 for 15 sec and restores 73 to 118 health."
        },
        13897: {
            "name": "Fiery Weapon (Proc)",
            "school": "Fire",
            "icon": "spell_fire_fireweapon",
            "cost": "Weapon Proc",
            "range": "Melee Range",
            "cast": "Chance on hit",
            "desc": "Enchant Weapon - Fiery Weapon proc. Strikes the target for 40 Fire damage."
        },
        20007: {
            "name": "Lifestealing (Proc)",
            "school": "Shadow",
            "icon": "spell_shadow_lifedrain02",
            "cost": "Weapon Proc",
            "range": "Melee Range",
            "cast": "Chance on hit",
            "desc": "Enchant Weapon - Lifestealing proc. Steals 30 health from the enemy target and transfers it to the wielder."
        }
    }
    
    total_dps = p["dps"]["avg"]
    actions_list = []
    
    for act in p.get("actions", []):
        act_id = act.get("id", {})
        sid = act_id.get("spellId", 0)
        
        info = spell_names.get(sid, {
            "name": act_id.get("otherId") or f"Spell {sid}",
            "school": "Magic",
            "icon": "spell_nature_elementalprecision_1",
            "cost": "",
            "range": "",
            "cast": "",
            "desc": "Casts a class spell causing direct damage or periodic effects."
        })
        if act_id.get("otherId") == "OtherActionAttack":
            info = spell_names[0]
            
        for tgt in act.get("targets", []):
            dmg = tgt.get("damage", 0)
            casts = tgt.get("casts", 0)
            hits = tgt.get("hits", 0)
            crits = tgt.get("crits", 0)
            misses = tgt.get("misses", 0)
            dodges = tgt.get("dodges", 0)
            parries = tgt.get("parries", 0)
            blocks = tgt.get("blocks", 0)
            
            if dmg > 0 or casts > 0 or hits > 0:
                actions_list.append({
                    "name": info["name"],
                    "school": info["school"],
                    "icon": info["icon"],
                    "rank": act_id.get("rank", 0),
                    "cost": info.get("cost", ""),
                    "range": info.get("range", ""),
                    "cast": info.get("cast", ""),
                    "desc": info.get("desc", ""),
                    "damage_per_sim": round(dmg / req.iterations, 1),
                    "dps": round(dmg / (req.iterations * req.duration), 2),
                    "percent": round((dmg / (req.iterations * req.duration * total_dps)) * 100, 1) if total_dps > 0 else 0,
                    "casts_per_sim": round(casts / req.iterations, 1),
                    "hits_per_sim": round(hits / req.iterations, 1),
                    "crits_per_sim": round(crits / req.iterations, 1),
                    "crit_percent": round((crits / hits * 100), 1) if hits > 0 else 0.0,
                    "misses_per_sim": round((misses + dodges + parries) / req.iterations, 1)
                })

    actions_list.sort(key=lambda x: x["damage_per_sim"], reverse=True)

    # --- HEALING & SUSTAIN CALCULATIONS ---
    total_heal_bonus = 0
    total_sp = 0
    total_int = 23  # Base Tauren Shaman Intellect at lvl 19
    total_spi = 28  # Base Spirit
    total_mp5 = 0
    
    item_lookup = {}
    for slot_items in ITEM_CATALOG.values():
        for it in slot_items:
            item_lookup[it["id"]] = it
            
    for item_id in req.gear.values():
        if item_id in item_lookup:
            stats = item_lookup[item_id].get("parsedStats", {})
            total_heal_bonus += stats.get("Healing", 0)
            total_sp += stats.get("SP", 0)
            total_int += stats.get("Int", 0)
            total_spi += stats.get("Spi", 0)
            total_mp5 += stats.get("MP5", 0)

    # Parse talents: format is tree0-tree1-tree2 (e.g. -05203- or --55)
    clean_tal = tal_str.strip("-")
    tal_parts = tal_str.split("-")
    t0 = tal_parts[0] if len(tal_parts) > 0 else ""
    t1 = tal_parts[1] if len(tal_parts) > 1 else ""
    t2 = tal_parts[2] if len(tal_parts) > 2 else ""
    
    # Tree 2 (Resto): pos 0 = Imp HW (0-5), pos 1 = Tidal Focus (0-5)
    # Tree 1 (Enhance): pos 2 = Ancestral Knowledge (0-5)
    imp_hw_rank = int(t2[0]) if len(t2) > 0 and t2[0].isdigit() else 0
    tidal_focus_rank = int(t2[1]) if len(t2) > 1 and t2[1].isdigit() else 0
    anc_know_rank = int(t1[2]) if len(t1) > 2 and t1[2].isdigit() else 0

    base_mana = 450 + (total_int * 15)
    if anc_know_rank > 0:
        base_mana = int(base_mana * (1 + anc_know_rank * 0.01))
        
    spell_crit_pct = round(2.2 + (total_int / 59.5), 1)

    hw_spells_data = {
        913: {
            "name": "Healing Wave (Rank 4)", "rank": 4,
            "min_base": 136, "max_base": 163, "base_cast": 2.5, "base_mana": 155,
            "coeff": 2.5 / 3.5, "icon": "spell_nature_magicimmunity"
        },
        547: {
            "name": "Healing Wave (Rank 3)", "rank": 3,
            "min_base": 69, "max_base": 82, "base_cast": 2.0, "base_mana": 80,
            "coeff": 2.0 / 3.5, "icon": "spell_nature_magicimmunity"
        },
        332: {
            "name": "Healing Wave (Rank 2)", "rank": 2,
            "min_base": 36, "max_base": 47, "base_cast": 1.5, "base_mana": 45,
            "coeff": 1.5 / 3.5, "icon": "spell_nature_magicimmunity"
        },
        331: {
            "name": "Healing Wave (Rank 1)", "rank": 1,
            "min_base": 18, "max_base": 22, "base_cast": 1.5, "base_mana": 25,
            "coeff": 1.5 / 3.5, "icon": "spell_nature_magicimmunity"
        }
    }

    effective_heal_power = total_heal_bonus + total_sp
    calculated_hw_ranks = {}
    for sid, hdata in hw_spells_data.items():
        cast_t = max(1.0, round(hdata["base_cast"] - (imp_hw_rank * 0.1), 1))
        mana_c = round(hdata["base_mana"] * (1 - (tidal_focus_rank * 0.01)), 1)
        min_h = round(hdata["min_base"] + (effective_heal_power * hdata["coeff"]), 1)
        max_h = round(hdata["max_base"] + (effective_heal_power * hdata["coeff"]), 1)
        avg_h = round((min_h + max_h) / 2, 1)
        hps_val = round(avg_h / cast_t, 1)
        hpm_val = round(avg_h / mana_c, 2)
        c_to_oom = round(base_mana / mana_c, 1) if mana_c > 0 else 99
        t_to_oom = round(c_to_oom * cast_t, 1)
        tot_cap = int(c_to_oom * avg_h)

        calculated_hw_ranks[sid] = {
            "spell_id": sid,
            "name": hdata["name"],
            "rank": hdata["rank"],
            "icon": hdata["icon"],
            "min_heal": min_h,
            "max_heal": max_h,
            "avg_heal": avg_h,
            "crit_heal": round(avg_h * 1.5, 1),
            "cast_time": cast_t,
            "base_cast_time": hdata["base_cast"],
            "mana_cost": mana_c,
            "base_mana_cost": hdata["base_mana"],
            "hps": hps_val,
            "hpm": hpm_val,
            "casts_to_oom": c_to_oom,
            "time_to_oom": t_to_oom,
            "healing_capacity": tot_cap
        }

    # Check for active healing spells in rotation
    active_heal_steps = []
    if req.custom_rotation is not None:
        for s in req.custom_rotation:
            if s.get("enabled", True) and int(s.get("spellId", 0)) in hw_spells_data:
                active_heal_steps.append(s)

    has_healing = len(active_heal_steps) > 0 or req.rotation_preset in ["resto_burst", "resto_sustain", "hybrid_twink"]
    
    primary_sid = 913
    if active_heal_steps:
        primary_sid = int(active_heal_steps[0].get("spellId", 913))
    elif req.rotation_preset == "resto_sustain":
        primary_sid = 547
    elif req.rotation_preset == "hybrid_twink":
        primary_sid = 913

    prim = calculated_hw_ranks[primary_sid]

    # If healing is active in rotation, inject into actions breakdown
    if has_healing:
        cond = active_heal_steps[0].get("condition", "continuous_heal") if active_heal_steps else "continuous_heal"
        if "continuous" in cond or req.rotation_preset in ["resto_burst", "resto_sustain"]:
            fight_casts = round(req.duration / prim["cast_time"], 1)
        elif "hp50" in cond:
            fight_casts = 2.0  # ~2 emergency heals per 30s fight
        elif "hp80" in cond:
            fight_casts = 4.0
        else:
            fight_casts = round(req.duration / (prim["cast_time"] * 2), 1)

        tot_healed = round(fight_casts * prim["avg_heal"], 1)
        sim_hps = round(tot_healed / req.duration, 2)
        crits = round(fight_casts * (spell_crit_pct / 100), 1)

        actions_list.insert(0, {
            "name": f"{prim['name']} [Heal]",
            "school": "Nature (Heal)",
            "icon": prim["icon"],
            "rank": prim["rank"],
            "is_heal": True,
            "cost": f"{prim['mana_cost']} Mana",
            "range": "40 yd range",
            "cast": f"{prim['cast_time']} sec cast",
            "desc": f"Heals friendly target for {prim['min_heal']} to {prim['max_heal']} HP (+{effective_heal_power} heal power). HPM: {prim['hpm']} HP/Mana.",
            "damage_per_sim": tot_healed,
            "dps": sim_hps,  # represents HPS
            "percent": 0.0,
            "casts_per_sim": fight_casts,
            "hits_per_sim": fight_casts,
            "crits_per_sim": crits,
            "crit_percent": spell_crit_pct,
            "misses_per_sim": 0.0
        })

    healing_summary = {
        "active": has_healing,
        "primary_spell": prim["name"],
        "primary_hps": prim["hps"],
        "primary_hpm": prim["hpm"],
        "avg_heal": prim["avg_heal"],
        "min_heal": prim["min_heal"],
        "max_heal": prim["max_heal"],
        "crit_heal": prim["crit_heal"],
        "cast_time": prim["cast_time"],
        "base_cast_time": prim["base_cast_time"],
        "cast_reduction": round(imp_hw_rank * 0.1, 1),
        "mana_cost": prim["mana_cost"],
        "base_mana_cost": prim["base_mana_cost"],
        "mana_discount_pct": tidal_focus_rank * 1.0,
        "total_mana": base_mana,
        "casts_to_oom": prim["casts_to_oom"],
        "time_to_oom": prim["time_to_oom"],
        "healing_capacity": prim["healing_capacity"],
        "total_healing_power": effective_heal_power,
        "total_int": total_int,
        "total_spi": total_spi,
        "total_mp5": total_mp5,
        "spell_crit": spell_crit_pct,
        "ranks": calculated_hw_ranks
    }

    is_1h = req.gear.get("offhand", 0) != 0
    w_mode = "1h_shield" if is_1h else "2h_staff"
    imb_flag = "flametongue" if "Flametongue" in req.imbue else ("rockbiter" if "Rockbiter" in req.imbue else "frostbrand")

    # --- TANK SURVIVABILITY, MITIGATION & THREAT CALCULATIONS ---
    gear_stats_tank = calculate_gear_stats_from_catalog(req.gear)
    for bk, bv in bonus_dict.items():
        if bk in gear_stats_tank:
            gear_stats_tank[bk] += bv

    # Check if offhand is a shield
    oh_id = req.gear.get("offhand", 0)
    oh_item = item_lookup.get(oh_id, {}) if oh_id else {}
    has_shield = bool(oh_item.get("isShield", False) or (oh_item.get("armor", 0) > 80))

    # Parse tanking talents from Tree 1 (Enhancement):
    # [1][0] Earth's Grasp, [1][3] Guardian Totems, [1][5] Imp Lightning Shield,
    # [1][8] Anticipation (+1% Dodge/rank), [1][9] Toughness (+2% Stamina/rank), [1][13] Spirit Weapons (+5% Parry)
    anticipation_rank = int(t1[8]) if len(t1) > 8 and t1[8].isdigit() else 0
    toughness_rank = int(t1[9]) if len(t1) > 9 and t1[9].isdigit() else 0
    spirit_wpn_rank = int(t1[13]) if len(t1) > 13 and t1[13].isdigit() else 0
    imp_ls_rank = int(t1[5]) if len(t1) > 5 and t1[5].isdigit() else 0

    total_sta = 32 + int(req.level * 1.4) + gear_stats_tank.get("Sta", 0)
    if toughness_rank > 0:
        total_sta = int(round(total_sta * (1.0 + 0.02 * toughness_rank)))
    max_hp = 260 + (req.level * 24) + (total_sta * 10)

    total_agi = 20 + int(req.level * 0.9) + gear_stats_tank.get("Agi", 0)
    total_str = 28 + int(req.level * 1.2) + gear_stats_tank.get("Str", 0)
    total_def = gear_stats_tank.get("Def", 0)
    total_armor = 120 + (total_agi * 2) + gear_stats_tank.get("Armor", 0)

    boss_lvl = req.level + 2
    armor_denom = total_armor + 400 + (85 * boss_lvl)
    armor_dr = min(0.75, max(0.05, total_armor / armor_denom)) if armor_denom > 0 else 0.15
    armor_dr_pct = round(armor_dr * 100, 1)

    dodge_pct = round(4.2 + (total_agi / 14.5) + (anticipation_rank * 1.0) + (total_def * 0.04) + gear_stats_tank.get("Dodge", 0), 1)
    parry_pct = round(5.0 + (total_def * 0.04), 1) if spirit_wpn_rank > 0 else 0.0
    block_pct = round(5.0 + (total_def * 0.04) + (anticipation_rank * 1.0), 1) if has_shield else 0.0
    block_val = int(8 + (req.level * 0.65) + (total_str / 20)) if has_shield else 0
    miss_pct = round(5.0 + (total_def * 0.04), 1)
    total_avoidance_pct = round(miss_pct + dodge_pct + parry_pct + block_pct, 1)

    avoid_mult = max(0.20, 1.0 - ((miss_pct + dodge_pct + parry_pct) / 100.0))
    ehp = int(round(max_hp / max(0.12, (1.0 - armor_dr) * avoid_mult)))

    raw_boss_dps = 42.0 + (req.level * 1.9)
    mitigated_dps = raw_boss_dps * (1.0 - armor_dr) * avoid_mult
    block_mitigation_dps = (block_pct / 100.0) * (block_val / 2.0)
    stoneskin_mitigation = 5.5 + (req.level * 0.25)
    hp5_regen_s = bonus_dict.get("HP5", 0) / 5.0
    dtps = round(max(6.0, mitigated_dps - block_mitigation_dps - stoneskin_mitigation - hp5_regen_s), 1)
    ttd = round(max_hp / max(1.0, dtps), 1)

    # Threat Per Second (TPS):
    # - Base Damage DPS = 1.0 threat per dmg
    # - Earth Shock has a 2.0x threat multiplier in Classic WoW
    # - Rockbiter Weapon adds massive flat bonus threat per second (~32-48 TPS scaled by level)
    # - Lightning Shield adds reflective threat when hit (~14 TPS)
    earth_shock_dps = sum(a["dps"] for a in actions_list if "Earth Shock" in a["name"])
    rockbiter_tps = round((26.0 + req.level * 0.85) if "Rockbiter" in req.imbue else 0.0, 1)
    ls_tps = round((11.0 + req.level * 0.45) * (1.0 + 0.05 * imp_ls_rank), 1)
    total_tps = round(p["dps"]["avg"] + earth_shock_dps + rockbiter_tps + ls_tps, 1)

    tank_score = min(100, int((ehp / (18 + req.level * 1.1)) * 0.45 + (total_tps * 0.35) + (armor_dr_pct * 0.45) + (12 if has_shield else 0)))
    tank_grade = "S+" if tank_score >= 92 else ("S" if tank_score >= 84 else ("A" if tank_score >= 72 else ("B" if tank_score >= 60 else "C")))

    is_tank_active = bool(req.rotation_preset in ["tank_threat", "tank_mitigation"] or (has_shield and "Rockbiter" in req.imbue))

    tank_summary = {
        "active": is_tank_active,
        "ehp": ehp,
        "max_hp": max_hp,
        "total_sta": total_sta,
        "total_armor": total_armor,
        "armor_dr_pct": armor_dr_pct,
        "has_shield": has_shield,
        "dodge_pct": dodge_pct,
        "parry_pct": parry_pct,
        "block_pct": block_pct,
        "block_value": block_val,
        "miss_pct": miss_pct,
        "total_avoidance_pct": total_avoidance_pct,
        "dtps": dtps,
        "ttd": ttd,
        "tps": total_tps,
        "rockbiter_tps": rockbiter_tps,
        "earth_shock_bonus_tps": round(earth_shock_dps, 1),
        "lightning_shield_tps": ls_tps,
        "tank_score": tank_score,
        "tank_grade": tank_grade
    }

    res_data = {
        "status": "success",
        "dps": {
            "avg": round(p["dps"]["avg"], 2),
            "min": round(p["dps"]["min"], 2),
            "max": round(p["dps"]["max"], 2),
            "stdev": round(p["dps"]["stdev"], 2),
        },
        "healing": healing_summary,
        "tank": tank_summary,
        "fight_duration": req.duration,
        "iterations": req.iterations,
        "character_level": req.level,
        "actions": actions_list,
        "cli_equivalent": f"python C:\\Users\\jcbas\\.gemini\\antigravity\\scratch\\sim_cotto.py --weapon-mode {w_mode} --imbue {imb_flag} --talents \"{tal_str}\" --rotation {req.rotation_preset} --iterations {req.iterations}"
    }

    SIM_CACHE[sim_cache_key] = res_data
    if len(SIM_CACHE) > 200:
        try:
            SIM_CACHE.pop(next(iter(SIM_CACHE)))
        except Exception:
            pass

    return res_data

# --- MULTI-ENVIRONMENT & SCENARIO LAB RUNNER ---
class ScenarioSuiteRequest(BaseModel):
    level: int = 19
    imbue: str = "FlametongueWeapon"
    talents: str = "-05203-"
    rotation_preset: str = "burst"
    custom_rotation: Optional[List[Dict[str, Any]]] = None
    buffs: Optional[Any] = None
    gear: Dict[str, int] = {}
    enchants: Optional[Dict[str, int]] = {}
    selected_scenarios: Optional[List[str]] = None
    custom_scenarios: Optional[List[Dict[str, Any]]] = None
    buffs: Optional[Any] = None
    scenarios: Optional[List[Dict[str, Any]]] = None
    buffs: Optional[Any] = None

def calculate_gear_stats_from_catalog(gear: Dict[str, int]):
    total_stats = {
        "Str": 0, "Agi": 0, "Sta": 0, "Int": 0, "Spi": 0,
        "AP": 0, "Crit": 0, "Hit": 0, "Armor": 0,
        "Healing": 0, "SP": 0, "FireSP": 0, "NatureSP": 0,
        "FrostResist": 0, "NatureResist": 0, "FireResist": 0, "ShadowResist": 0, "MP5": 0
    }
    for slot, item_id in gear.items():
        if item_id in ITEM_LOOKUP:
            it = ITEM_LOOKUP[item_id]
            total_stats["Armor"] += it.get("armor", 0)
            stats = it.get("parsedStats", {})
            for k, v in stats.items():
                if k in total_stats:
                    total_stats[k] += v
    return total_stats

def run_single_scenario_sim(scenario: Dict[str, Any], req: ScenarioSuiteRequest):
    s_id = scenario["id"]
    cat = scenario.get("category", "pve_dps")
    dur = scenario.get("duration", 30)
    target_count = scenario.get("targetCount", 1)
    lvl_offset = scenario.get("targetLevelOffset", 0)
    char_lvl = req.level
    target_lvl = char_lvl + lvl_offset
    gear_stats = calculate_gear_stats_from_catalog(req.gear)
    buff_stats = calculate_bonus_stats_from_buffs(req.buffs)
    for bk, bv in buff_stats.items():
        if bk in gear_stats:
            gear_stats[bk] += bv

    # 1. HEALING SCENARIOS
    if cat in ["pve_healing", "pvp_healing"]:
        effective_heal = gear_stats["Healing"] + gear_stats["SP"]
        total_int = gear_stats["Int"]
        base_mana = 400 + (char_lvl * 25) + (total_int * 15)
        mp5 = gear_stats.get("MP5", 0) + (gear_stats["Spi"] * 0.4)
        
        hw_mana = 155 * (1.0 - 0.05)
        hw_heal = 150 + (effective_heal * (2.5 / 3.5))
        hw_hps = round(hw_heal / 2.5, 1)
        casts_to_oom = int(base_mana / hw_mana) if hw_mana > 0 else 20
        time_to_oom = round((casts_to_oom * 2.5) + (base_mana / (mp5 + 1) * 0.2), 1)
        incoming = scenario.get("incomingDps", 85)
        
        triage_ratio = min(1.5, hw_hps / max(1, incoming))
        score = min(100, int((hw_hps * 1.8) + (triage_ratio * 30)))
        grade = "S+" if score >= 92 else ("S" if score >= 84 else ("A" if score >= 72 else ("B" if score >= 60 else "C")))
        
        return {
            "id": s_id,
            "name": scenario["name"],
            "badge": scenario.get("badge", "Healing"),
            "category": cat,
            "primary_metric": f"{hw_hps} HPS",
            "metric_value": hw_hps,
            "score": score,
            "grade": grade,
            "detail_label": "Party Triage & Sustain",
            "details": f"HW R4: ~{int(hw_heal)} heal/cast • {casts_to_oom} casts to OOM (~{time_to_oom}s sustain)",
            "tip": "Stacking MP5 and +Healing increases party survival during high-damage encounters."
        }

    # 1.5 TANKING & MITIGATION SCENARIOS (MAIN TANK & AOE PACK TANK)
    if cat == "pve_tank":
        oh_id = req.gear.get("offhand", 0)
        oh_item = ITEM_LOOKUP.get(oh_id, {}) if oh_id else {}
        has_shield = bool(oh_item.get("isShield", False) or (oh_item.get("armor", 0) > 80))

        # Parse tanking talents from req.talents (Tree 1: [8]=Anticipation, [9]=Toughness, [13]=Spirit Weapons, [5]=Imp LS)
        tal_parts = (req.talents or "").split("-")
        t1 = tal_parts[1] if len(tal_parts) > 1 else ""
        anticipation_rank = int(t1[8]) if len(t1) > 8 and t1[8].isdigit() else 0
        toughness_rank = int(t1[9]) if len(t1) > 9 and t1[9].isdigit() else 0
        spirit_wpn_rank = int(t1[13]) if len(t1) > 13 and t1[13].isdigit() else 0
        imp_ls_rank = int(t1[5]) if len(t1) > 5 and t1[5].isdigit() else 0

        total_sta = 32 + int(char_lvl * 1.4) + gear_stats.get("Sta", 0)
        if toughness_rank > 0:
            total_sta = int(round(total_sta * (1.0 + 0.02 * toughness_rank)))
        max_hp = 260 + (char_lvl * 24) + (total_sta * 10)

        total_agi = 20 + int(char_lvl * 0.9) + gear_stats.get("Agi", 0)
        total_str = 28 + int(char_lvl * 1.2) + gear_stats.get("Str", 0)
        total_def = gear_stats.get("Def", 0)
        total_armor = 120 + (total_agi * 2) + gear_stats.get("Armor", 0)

        denom = total_armor + 400 + (85 * target_lvl)
        armor_dr = min(0.75, max(0.05, total_armor / denom)) if denom > 0 else 0.15
        armor_dr_pct = round(armor_dr * 100, 1)

        dodge_pct = round(4.2 + (total_agi / 14.5) + (anticipation_rank * 1.0) + (total_def * 0.04) + gear_stats.get("Dodge", 0), 1)
        parry_pct = round(5.0 + (total_def * 0.04), 1) if spirit_wpn_rank > 0 else 0.0
        block_pct = round(5.0 + (total_def * 0.04) + (anticipation_rank * 1.0), 1) if has_shield else 0.0
        block_val = int(8 + (char_lvl * 0.65) + (total_str / 20)) if has_shield else 0
        miss_pct = round(5.0 + (total_def * 0.04), 1)

        avoid_mult = max(0.20, 1.0 - ((miss_pct + dodge_pct + parry_pct) / 100.0))
        ehp = int(round(max_hp / max(0.12, (1.0 - armor_dr) * avoid_mult)))

        incoming_raw = scenario.get("incomingDps", 68)
        mitigated = incoming_raw * (1.0 - armor_dr) * avoid_mult
        block_mit = (block_pct / 100.0) * (block_val * max(1, target_count * 0.6))
        stoneskin = (5.5 + char_lvl * 0.25) * max(1, target_count * 0.5)
        dtps = round(max(6.0, mitigated - block_mit - stoneskin), 1)
        ttd = round(max_hp / max(1.0, dtps), 1)

        # Estimate Tank Threat Per Second (TPS)
        ap_est = (total_str * 2) + gear_stats.get("AP", 0) + (80 if "Rockbiter" in req.imbue else 0)
        base_melee_tps = 22.0 + (char_lvl * 1.1) + (ap_est * 0.14)
        rockbiter_tps = (28.0 + char_lvl * 0.9) if "Rockbiter" in req.imbue else 0.0
        earth_shock_tps = 24.0 + (gear_stats.get("SP", 0) * 0.5) + (gear_stats.get("Hit", 0) * 1.5)
        ls_tps = (12.0 + char_lvl * 0.5) * (1.0 + 0.05 * imp_ls_rank) * (1.6 if target_count > 1 else 1.0)
        aoe_totem_tps = (18.0 + gear_stats.get("FireSP", 0) * 0.8) if target_count > 1 else 0.0
        tps = round(base_melee_tps + rockbiter_tps + earth_shock_tps + ls_tps + aoe_totem_tps, 1)

        shield_bonus = 14 if has_shield else 0
        if s_id == "pve_aoe_tank_pack":
            score = min(100, int((ehp / (22 + char_lvl * 1.2)) * 0.42 + (tps * 0.34) + (armor_dr_pct * 0.42) + shield_bonus))
            metric_str = f"{ehp} EHP • {tps} AoE TPS"
            detail_lbl = "4-Mob Pack Mitigation & Aggro"
            tip_str = "1H + Shield with Rockbiter, Lightning Shield, and Stoneclaw/Fire Nova Totem holds multi-mob aggro while minimizing DTPS."
        else:
            score = min(100, int((ehp / (20 + char_lvl * 1.15)) * 0.45 + (tps * 0.35) + (armor_dr_pct * 0.45) + shield_bonus))
            metric_str = f"{ehp} EHP • {tps} TPS"
            detail_lbl = "Main Tank EHP, Mitigation & Threat"
            tip_str = "Equipping a high-Armor Shield + Stamina gear and Rockbiter Weapon maximizes Effective Health (EHP) and Boss Threat."

        grade = "S+" if score >= 92 else ("S" if score >= 84 else ("A" if score >= 72 else ("B" if score >= 60 else "C")))

        return {
            "id": s_id,
            "name": scenario["name"],
            "badge": scenario.get("badge", "Tank"),
            "category": cat,
            "primary_metric": metric_str,
            "metric_value": ehp,
            "score": score,
            "grade": grade,
            "detail_label": detail_lbl,
            "details": f"{max_hp} HP • {total_armor} Armor ({armor_dr_pct}% DR) • {dtps} DTPS • {ttd}s Unhealed TTD",
            "tip": tip_str
        }

    # 2. WSG FLAG RUNNER & ESCAPE SCENARIO
    if s_id == "pvp_flag_runner":
        base_hp = 300 + (char_lvl * 28) + (gear_stats["Sta"] * 10)
        total_armor = gear_stats["Armor"]
        denom = (total_armor + 400 + (85 * char_lvl))
        armor_dr = total_armor / denom if denom > 0 else 0.1
        armor_dr = min(0.75, max(0.05, armor_dr))
        
        has_wolf = char_lvl >= 20
        speed_pct = 140 if has_wolf else 100
        transit_time = 10.2 if has_wolf else 14.3
        
        incoming_dps = scenario.get("incomingDps", 75)
        net_dps_taken = incoming_dps * (1.0 - armor_dr)
        total_damage_taken = net_dps_taken * transit_time
        survival_hp_left = base_hp - total_damage_taken
        survival_rate = max(5, min(99, int((survival_hp_left / max(1, base_hp)) * 100)))
        
        score = min(100, int((survival_rate * 0.7) + (armor_dr * 50) + (15 if has_wolf else 0)))
        grade = "S+" if score >= 92 else ("S" if score >= 84 else ("A" if score >= 72 else ("B" if score >= 60 else "C")))
        
        return {
            "id": s_id,
            "name": scenario["name"],
            "badge": scenario.get("badge", "Flag Runner"),
            "category": cat,
            "primary_metric": f"{survival_rate}% Escape Rate",
            "metric_value": survival_rate,
            "score": score,
            "grade": grade,
            "detail_label": "Flag Transit Survival",
            "details": f"{base_hp} HP • {total_armor} Armor ({int(armor_dr*100)}% DR) • {transit_time:.1f}s cross time ({speed_pct}% speed)",
            "tip": "High Armor + Stamina ensures surviving physical ranged fire and dazes across the midfield."
        }

    # 3. COMBAT DPS SIMULATIONS VIA WOWSIMCLI
    cfg = copy.deepcopy(BASE_REQ)
    player = cfg["raid"]["parties"][0]["players"][0]
    
    cfg["simOptions"]["iterations"] = 50
    cfg["encounter"]["duration"] = dur
    
    targets_list = []
    for i in range(target_count):
        targets_list.append({
            "id": i + 1,
            "name": f"Target {i+1}",
            "level": target_lvl,
            "swingSpeed": 2.0
        })
    cfg["encounter"]["targets"] = targets_list
    
    enchants = req.enchants or {}
    for s_name, item_id in req.gear.items():
        if s_name in SLOT_INDEX_MAP and item_id > 0:
            item_spec = {"id": item_id}
            if enchants.get(s_name, 0) > 0:
                item_spec["enchant"] = enchants[s_name]
            player["equipment"]["items"][SLOT_INDEX_MAP[s_name]] = item_spec

    if any(buff_stats.values()):
        player["bonusStats"] = {"stats": build_bonus_stats_proto(buff_stats)}

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
        json.dump(cfg, tf)
        tmp_name = tf.name

    try:
        proc = subprocess.run([CLI_PATH, "sim", "--infile", tmp_name], capture_output=True, text=True, errors="ignore", timeout=15)
        os.remove(tmp_name)
        if proc.returncode != 0:
            return {"id": s_id, "name": scenario["name"], "badge": scenario.get("badge", "DPS"), "category": cat, "score": 50, "grade": "C", "primary_metric": "--", "details": "Simulation failed"}
        idx = proc.stdout.find("{")
        out = json.loads(proc.stdout[idx:])
        p_res = out["raidMetrics"]["parties"][0]["players"][0]
        dps_val = round(p_res["dps"]["avg"], 1)
        
        if s_id == "pvp_burst_skirmish":
            tot_burst = int(round(dps_val * dur, 0))
            score = min(100, int(dps_val * 1.5))
            metric_text = f"{tot_burst} Dmg (10s)"
            label = "Burst Damage Window"
            tip = "Critical Strike and weapon swing damage maximize kill pressure within 10 seconds."
        elif s_id == "aoe_dungeon_trash":
            score = min(100, int(dps_val * 1.3))
            metric_text = f"{dps_val} Cleave DPS"
            label = f"Cleave Across {target_count} Targets"
            tip = "Fire Nova Totem and Spell Power dramatically amplify AoE clear speeds."
        elif s_id == "pve_dungeon_boss":
            score = min(100, int(dps_val * 1.8))
            metric_text = f"{dps_val} DPS"
            label = "Boss DPS (+3 Lvls Glancing)"
            tip = "Hit Rating mitigates glancing blow penalties against level +3 dungeon bosses."
        elif s_id == "pve_raid_boss":
            score = min(100, int(dps_val * 1.7))
            metric_text = f"{dps_val} DPS"
            label = "90s Raid Endurance DPS"
            tip = "MP5 and mana efficiency sustain your Shock rotation over 90 seconds."
        else:
            score = min(100, int(dps_val * 1.6))
            metric_text = f"{dps_val} DPS"
            label = f"{dur}s Encounter Output"
            tip = "Optimized attack power and spell rank rotation maximize damage per second."

        grade = "S+" if score >= 92 else ("S" if score >= 84 else ("A" if score >= 72 else ("B" if score >= 60 else "C")))

        return {
            "id": s_id,
            "name": scenario["name"],
            "badge": scenario.get("badge", "Combat"),
            "category": cat,
            "primary_metric": metric_text,
            "metric_value": dps_val,
            "score": score,
            "grade": grade,
            "detail_label": label,
            "details": f"Avg DPS: {dps_val} • Fight Length: {dur}s • Targets: {target_count}",
            "tip": tip
        }
    except Exception as e:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        return {"id": s_id, "name": scenario["name"], "badge": scenario.get("badge", "Error"), "category": cat, "score": 50, "grade": "C", "primary_metric": "--", "details": str(e), "tip": "Simulation timed out."}

@app.post("/api/scenarios/simulate-suite")
def simulate_suite(req: ScenarioSuiteRequest):
    start_t = time.time()
    suite_cache_key = hashlib.md5(json.dumps(req.dict(), sort_keys=True).encode('utf-8')).hexdigest()
    if suite_cache_key in SIM_CACHE:
        cached = copy.deepcopy(SIM_CACHE[suite_cache_key])
        cached["execution_time_ms"] = int((time.time() - start_t) * 1000)
        return cached
        
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        all_scenarios = json.load(f)
        
    if req.scenarios:
        active_scenarios = req.scenarios
    elif req.selected_scenarios:
        selected_set = set(req.selected_scenarios)
        active_scenarios = [s for s in all_scenarios if s["id"] in selected_set]
    else:
        active_scenarios = [s for s in all_scenarios if s.get("enabled", True)]
        
    if req.custom_scenarios:
        active_scenarios.extend(req.custom_scenarios)
        
    if not active_scenarios:
        active_scenarios = all_scenarios[:4]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_single_scenario_sim, sc, req) for sc in active_scenarios]
        results = [f.result() for f in futures]

    total_score = sum(r["score"] for r in results)
    composite_score = round(total_score / max(1, len(results)), 1)
    composite_grade = "S+" if composite_score >= 92 else ("S" if composite_score >= 84 else ("A" if composite_score >= 72 else ("B" if composite_score >= 60 else "C")))

    res_map = {r["id"]: r["score"] for r in results}
    radar = {
        "Single DPS": res_map.get("pve_single_mob", res_map.get("pve_single_target", composite_score)),
        "AoE Cleave": res_map.get("pve_aoe_pack", res_map.get("aoe_dungeon_trash", composite_score)),
        "Raid/Boss": max(res_map.get("pve_dungeon_boss", 0), res_map.get("pve_raid_boss", 0)) or composite_score,
        "Tank Mitig.": max(res_map.get("pve_dungeon_tank", 0), res_map.get("pve_aoe_tank_pack", 0)) or composite_score,
        "PvP Anti-Caster": res_map.get("pvp_duel_caster", res_map.get("pvp_caster_duel", composite_score)),
        "PvP Anti-Melee": res_map.get("pvp_duel_melee", res_map.get("pvp_melee_brawler", composite_score)),
        "WSG Survival": res_map.get("pvp_flag_runner", composite_score),
        "Healing Sustain": max(res_map.get("pve_dungeon_healing", 0), res_map.get("pvp_arena_healer", 0), res_map.get("pvp_arena_healing", 0)) or composite_score
    }

    best_sc = max(results, key=lambda x: x["score"]) if results else {"name": "None", "score": 0, "primary_metric": "--"}
    weakest_sc = min(results, key=lambda x: x["score"]) if results else {"name": "None", "score": 0, "primary_metric": "--"}

    results_dict = {r["id"]: r for r in results}
    elapsed_ms = max(25, int((time.time() - start_t) * 1000))

    top_dps_vals = [r.get("metric_value", 0) for r in results if ("DPS" in r.get("primary_metric", "") or "Dmg" in r.get("primary_metric", ""))]
    top_hps_vals = [r.get("metric_value", 0) for r in results if "HPS" in r.get("primary_metric", "")]
    surv_vals = [r.get("metric_value", 100) for r in results if "Escape Rate" in r.get("primary_metric", "")]

    out_data = {
        "status": "success",
        "composite_score": composite_score,
        "composite_grade": composite_grade,
        "radar": radar,
        "best_scenario": {"name": best_sc["name"], "score": best_sc["score"], "metric": best_sc["primary_metric"]},
        "weakest_scenario": {"name": weakest_sc["name"], "score": weakest_sc["score"], "metric": weakest_sc["primary_metric"]},
        "results": results_dict,
        "results_list": results,
        "scenarios_run": len(results),
        "execution_time_ms": elapsed_ms,
        "top_dps": max(top_dps_vals) if top_dps_vals else 0,
        "top_hps": max(top_hps_vals) if top_hps_vals else 0,
        "avg_survival_rate": round(sum(surv_vals) / len(surv_vals), 1) if surv_vals else 95.0
    }

    SIM_CACHE[suite_cache_key] = out_data
    if len(SIM_CACHE) > 200:
        try:
            SIM_CACHE.pop(next(iter(SIM_CACHE)))
        except Exception:
            pass
            
    return out_data

@app.get("/api/scenarios")
def get_scenarios(request: Request):
    return get_asset_response(request, "scenarios")

@app.post("/api/simulate")
def simulate(req: SimRequest):
    sim_cache_key = hashlib.md5(json.dumps(req.dict(), sort_keys=True).encode('utf-8')).hexdigest()
    if sim_cache_key in SIM_CACHE:
        return copy.deepcopy(SIM_CACHE[sim_cache_key])
    
    cfg = copy.deepcopy(BASE_REQ)
    player = cfg["raid"]["parties"][0]["players"][0]
    
    # 1. Encounter options
    cfg["simOptions"]["iterations"] = max(10, min(2000, req.iterations))
    cfg["encounter"]["duration"] = max(5, min(300, req.duration))
    if "targets" in cfg["encounter"] and len(cfg["encounter"]["targets"]) > 0:
        cfg["encounter"]["targets"][0]["level"] = req.level
    
    # 2. Imbue
    player["enhancementShaman"]["options"]["classOptions"]["imbueMh"] = req.imbue
    
    # 3. Talents
    # Format: tree0-tree1-tree2 (e.g. -05203- or --55)
    tal_raw = req.talents.strip()
    if tal_raw.startswith("-") and not tal_raw.startswith("--"):
        # e.g. -05203 or -05203-
        tal_parts = tal_raw.strip("-").split("-")
        t0 = ""
        t1 = tal_parts[0] if len(tal_parts) > 0 else ""
        t2 = tal_parts[1] if len(tal_parts) > 1 else ""
        tal_str = f"-{t1}-{t2}".rstrip("-")
        if tal_str == "-":
            tal_str = "--"
    elif tal_raw.startswith("--"):
        # e.g. --55 or --552-
        t2 = tal_raw.lstrip("-").rstrip("-")
        t0, t1 = "", ""
        tal_str = f"--{t2}"
    else:
        tal_parts = tal_raw.split("-")
        t0 = tal_parts[0] if len(tal_parts) > 0 else ""
        t1 = tal_parts[1] if len(tal_parts) > 1 else ""
        t2 = tal_parts[2] if len(tal_parts) > 2 else ""
        tal_str = f"{t0}-{t1}-{t2}".rstrip("-")
    
    player["talentsString"] = tal_str
    
    # 4. Gear & Enchants
    enchants = req.enchants or {}
    for slot, item_id in req.gear.items():
        if slot in SLOT_INDEX_MAP:
            idx = SLOT_INDEX_MAP[slot]
            if item_id > 0:
                item_spec = {"id": item_id}
                enc_id = enchants.get(slot, 0)
                if enc_id > 0:
                    item_spec["enchant"] = enc_id
                player["equipment"]["items"][idx] = item_spec
            else:
                player["equipment"]["items"][idx] = {}
                
    # 5. Rotation APL
    if req.custom_rotation is not None:
        prio_list = []
        for step in req.custom_rotation:
            if not step.get("enabled", True):
                continue
            sid = int(step.get("spellId", 0))
            cond = step.get("condition", "on_cd")
            
            if sid == 3599:  # Searing Totem
                if cond == "totem_le_1s":
                    prio_list.append({
                        "action": {
                            "condition": {
                                "cmp": {
                                    "op": "OpLe",
                                    "lhs": { "totemRemainingTime": { "totemType": "Fire" } },
                                    "rhs": { "const": { "val": "1s" } }
                                }
                            },
                            "castSpell": { "spellId": { "spellId": 3599 } }
                        }
                    })
                else:
                    prio_list.append({ "action": { "castSpell": { "spellId": { "spellId": 3599 } } } })
            elif sid == 8052:  # Flame Shock
                if cond == "dot_not_active":
                    prio_list.append({
                        "action": {
                            "condition": {
                                "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                            },
                            "castSpell": { "spellId": { "spellId": 8052 } }
                        }
                    })
                else:
                    prio_list.append({ "action": { "castSpell": { "spellId": { "spellId": 8052 } } } })
            elif sid == 324:  # Lightning Shield
                if cond == "buff_not_active":
                    prio_list.append({
                        "action": {
                            "condition": {
                                "not": { "val": { "auraIsActive": { "auraId": { "spellId": 324 } } } }
                            },
                            "castSpell": { "spellId": { "spellId": 324 } }
                        }
                    })
                else:
                    prio_list.append({ "action": { "castSpell": { "spellId": { "spellId": 324 } } } })
            elif sid > 0:
                prio_list.append({ "action": { "castSpell": { "spellId": { "spellId": sid } } } })
                
        player["rotation"]["priorityList"] = prio_list
    elif req.rotation_preset in ["twink29_burst", "stormstrike_burst"]:
        # Stormstrike on CD -> Flame Shock DoT -> Earth Shock on CD -> Searing Totem (Level 25/29 BiS)
        player["rotation"]["priorityList"] = [
            { "action": { "castSpell": { "spellId": { "spellId": 17364 } } } },
            {
                "action": {
                    "condition": {
                        "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                    },
                    "castSpell": { "spellId": { "spellId": 8052 } }
                }
            },
            {
                "action": { "castSpell": { "spellId": { "spellId": 8045 } } }
            },
            {
                "action": {
                    "condition": {
                        "cmp": {
                            "op": "OpLe",
                            "lhs": { "totemRemainingTime": { "totemType": "Fire" } },
                            "rhs": { "const": { "val": "1s" } }
                        }
                    },
                    "castSpell": { "spellId": { "spellId": 3599 } }
                }
            }
        ]
    elif req.rotation_preset == "burst":
        # Flame Shock DoT -> Earth Shock on CD -> Searing Totem (Top DPS)
        player["rotation"]["priorityList"] = [
            {
                "action": {
                    "condition": {
                        "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                    },
                    "castSpell": { "spellId": { "spellId": 8052 } }
                }
            },
            {
                "action": { "castSpell": { "spellId": { "spellId": 8045 } } }
            },
            {
                "action": {
                    "condition": {
                        "cmp": {
                            "op": "OpLe",
                            "lhs": { "totemRemainingTime": { "totemType": "Fire" } },
                            "rhs": { "const": { "val": "1s" } }
                        }
                    },
                    "castSpell": { "spellId": { "spellId": 3599 } }
                }
            }
        ]
    elif req.rotation_preset == "smart":
        player["rotation"]["priorityList"] = [
            {
                "action": {
                    "condition": {
                        "cmp": {
                            "op": "OpLe",
                            "lhs": { "totemRemainingTime": { "totemType": "Fire" } },
                            "rhs": { "const": { "val": "1s" } }
                        }
                    },
                    "castSpell": { "spellId": { "spellId": 3599 } }
                }
            },
            {
                "action": {
                    "condition": {
                        "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                    },
                    "castSpell": { "spellId": { "spellId": 8052 } }
                }
            },
            {
                "action": { "castSpell": { "spellId": { "spellId": 8045 } } }
            }
        ]
    elif req.rotation_preset == "no_totem":
        player["rotation"]["priorityList"] = [
            {
                "action": {
                    "condition": {
                        "not": { "val": { "dotIsActive": { "spellId": { "spellId": 8052 } } } }
                    },
                    "castSpell": { "spellId": { "spellId": 8052 } }
                }
            },
            {
                "action": { "castSpell": { "spellId": { "spellId": 8045 } } }
            }
        ]
    elif req.rotation_preset == "earth_only":
        player["rotation"]["priorityList"] = [
            { "action": { "castSpell": { "spellId": { "spellId": 8045 } } } }
        ]
    elif req.rotation_preset == "flame_only":
        player["rotation"]["priorityList"] = [
            { "action": { "castSpell": { "spellId": { "spellId": 8052 } } } }
        ]
    elif req.rotation_preset == "melee_only":
        player["rotation"]["priorityList"] = []

    temp_req_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\temp_web_sim.json"
    with open(temp_req_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    try:
        proc = subprocess.run([CLI_PATH, "sim", "--infile", temp_req_path],
                              capture_output=True, text=True, errors="ignore", timeout=35)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Simulation timed out (35s).")

    idx = proc.stdout.find("{")
    if idx == -1:
        raise HTTPException(status_code=500, detail=f"Engine error: {proc.stderr}")

    raw_data = json.loads(proc.stdout[idx:])
    p = raw_data["raidMetrics"]["parties"][0]["players"][0]
    
    spell_names = {
        3599: {
            "name": "Searing Totem (Rank 1)",
            "school": "Fire",
            "icon": "spell_fire_searingtotem",
            "cost": "25 Mana",
            "range": "20 yd range",
            "cast": "Instant",
            "desc": "Summons a Searing Totem with 5 health at the feet of the caster that repeatedly attacks an enemy within 20 yards for 9 to 11 Fire damage every 2.2 sec. Lasts 30 sec."
        },
        17364: {
            "name": "Stormstrike",
            "school": "Physical",
            "icon": "ability_shaman_stormstrike",
            "cost": "8% Base Mana",
            "range": "Melee Range",
            "cast": "Instant • 20 sec cooldown",
            "desc": "Instantly strike with both weapons for 100% weapon damage and increase Nature damage dealt to target by 20% for 12 sec."
        },
        8045: {
            "name": "Earth Shock (Rank 3)",
            "school": "Nature",
            "icon": "spell_nature_earthshock",
            "cost": "70 Mana",
            "range": "20 yd range",
            "cast": "Instant • 6 sec cooldown",
            "desc": "Instantly shocks the target with concussive force, causing 64 to 69 Nature damage, interrupting spellcasting and preventing any spell in that school from being cast for 2 sec. Causes a high amount of threat."
        },
        8052: {
            "name": "Flame Shock (Rank 2)",
            "school": "Fire",
            "icon": "spell_fire_flameshock",
            "cost": "75 Mana",
            "range": "20 yd range",
            "cast": "Instant • 6 sec cooldown",
            "desc": "Instantly sears the target with Fire damage, causing 51 to 59 Fire damage and an additional 48 Fire damage over 12 sec."
        },
        29470: {
            "name": "Flametongue Weapon (Proc)",
            "school": "Fire",
            "icon": "spell_fire_flametounge",
            "cost": "Passive Proc",
            "range": "Melee Range",
            "cast": "Instant on hit",
            "desc": "Each melee hit with the imbued weapon inflicts 18 to 55 additional Fire damage based on weapon speed (slower weapons deal more fire damage per swing). Fire damage ignores enemy physical armor."
        },
        8017: {
            "name": "Rockbiter Weapon",
            "school": "Physical",
            "icon": "spell_nature_rockbiter",
            "cost": "Passive Proc",
            "range": "Melee Range",
            "cast": "Instant on hit",
            "desc": "Imbues the Shaman's weapon with the strength of the earth, increasing melee attack power by 50 and threat caused by attacks."
        },
        8026: {
            "name": "Frostbrand Weapon (Proc)",
            "school": "Frost",
            "icon": "spell_frost_frostbrand",
            "cost": "Passive Proc",
            "range": "Melee Range",
            "cast": "Instant on hit",
            "desc": "Imbues the weapon with frost. Each hit has a chance to cause 47 Frost damage and slow the target's movement speed by 25% for 8 sec."
        },
        324: {
            "name": "Lightning Shield (Rank 2)",
            "school": "Nature",
            "icon": "spell_nature_lightningshield",
            "cost": "70 Mana",
            "range": "Self",
            "cast": "Instant",
            "desc": "Surrounds the caster with 3 balls of lightning. When attacked, causes 26 Nature damage to the attacker. Only one ball can discharge every few seconds. Lasts 10 min."
        },
        913: {
            "name": "Healing Wave (Rank 4)",
            "school": "Nature (Heal)",
            "icon": "spell_nature_magicimmunity",
            "cost": "155 Mana",
            "range": "40 yd range",
            "cast": "2.5 sec cast",
            "desc": "Heals a friendly target for 136 to 163 (+healing scaling). Primary heavy healing wave for Level 19 Twink Shamans."
        },
        547: {
            "name": "Healing Wave (Rank 3)",
            "school": "Nature (Heal)",
            "icon": "spell_nature_magicimmunity",
            "cost": "80 Mana",
            "range": "40 yd range",
            "cast": "2.0 sec cast",
            "desc": "Heals a friendly target for 69 to 82 (+healing scaling). Highly mana-efficient sustained healing spell."
        },
        332: {
            "name": "Healing Wave (Rank 2)",
            "school": "Nature (Heal)",
            "icon": "spell_nature_magicimmunity",
            "cost": "45 Mana",
            "range": "40 yd range",
            "cast": "1.5 sec cast",
            "desc": "Heals a friendly target for 36 to 47 (+healing scaling). Fast emergency heal for critical triage."
        },
        331: {
            "name": "Healing Wave (Rank 1)",
            "school": "Nature (Heal)",
            "icon": "spell_nature_magicimmunity",
            "cost": "25 Mana",
            "range": "40 yd range",
            "cast": "1.5 sec cast",
            "desc": "Heals a friendly target for 18 to 22. Lowest rank healing wave for baiting interrupts or minor top-offs."
        },
        403: {
            "name": "Lightning Bolt (Rank 3)",
            "school": "Nature",
            "icon": "spell_nature_lightning",
            "cost": "60 Mana",
            "range": "30 yd range",
            "cast": "2.5 sec cast",
            "desc": "Casts a bolt of lightning at the enemy target for 49 to 59 Nature damage."
        },
        370: {
            "name": "Purge (Rank 1)",
            "school": "Magic",
            "icon": "spell_nature_purge",
            "cost": "35 Mana",
            "range": "30 yd range",
            "cast": "Instant",
            "desc": "Purges the target of 1 beneficial magic effect."
        },
        2484: {
            "name": "Earthbind Totem (Rank 1)",
            "school": "Nature",
            "icon": "spell_nature_strengthofearthtotem02",
            "cost": "45 Mana",
            "range": "Self",
            "cast": "Instant",
            "desc": "Summons an Earthbind Totem with 5 health at the feet of the caster that pulses every 3 sec, slowing the movement speed of all enemies within 10 yards by 50%. Lasts 45 sec."
        },
        5730: {
            "name": "Stoneclaw Totem (Rank 1)",
            "school": "Nature",
            "icon": "spell_nature_stoneclawtotem",
            "cost": "50 Mana",
            "range": "Self",
            "cast": "Instant",
            "desc": "Summons a Stoneclaw Totem with 50 health at the feet of the caster that pulses threat every 3 sec. Lasts 15 sec."
        },
        0: {
            "name": "Melee (Auto-Attack)",
            "school": "Physical",
            "icon": "inv_staff_13",
            "cost": "Melee Swing",
            "range": "Melee Range",
            "cast": "Instant",
            "desc": "Performs a standard melee swing against the enemy target with your equipped weapon. Deals physical damage calculated from weapon damage and attack power, reduced by enemy armor."
        },
        20004: {
            "name": "Holy Strength (Crusader)",
            "school": "Holy",
            "icon": "spell_holy_blessingofstrength",
            "cost": "Weapon Proc",
            "range": "Self",
            "cast": "Chance on hit",
            "desc": "Enchant Weapon - Crusader proc. Increases Strength by 100 for 15 sec and restores 73 to 118 health."
        },
        13897: {
            "name": "Fiery Weapon (Proc)",
            "school": "Fire",
            "icon": "spell_fire_fireweapon",
            "cost": "Weapon Proc",
            "range": "Melee Range",
            "cast": "Chance on hit",
            "desc": "Enchant Weapon - Fiery Weapon proc. Strikes the target for 40 Fire damage."
        },
        20007: {
            "name": "Lifestealing (Proc)",
            "school": "Shadow",
            "icon": "spell_shadow_lifedrain02",
            "cost": "Weapon Proc",
            "range": "Melee Range",
            "cast": "Chance on hit",
            "desc": "Enchant Weapon - Lifestealing proc. Steals 30 health from the enemy target and transfers it to the wielder."
        }
    }
    
    total_dps = p["dps"]["avg"]
    actions_list = []
    
    for act in p.get("actions", []):
        act_id = act.get("id", {})
        sid = act_id.get("spellId", 0)
        
        info = spell_names.get(sid, {
            "name": act_id.get("otherId") or f"Spell {sid}",
            "school": "Magic",
            "icon": "spell_nature_elementalprecision_1",
            "cost": "",
            "range": "",
            "cast": "",
            "desc": "Casts a class spell causing direct damage or periodic effects."
        })
        if act_id.get("otherId") == "OtherActionAttack":
            info = spell_names[0]
            
        for tgt in act.get("targets", []):
            dmg = tgt.get("damage", 0)
            casts = tgt.get("casts", 0)
            hits = tgt.get("hits", 0)
            crits = tgt.get("crits", 0)
            misses = tgt.get("misses", 0)
            dodges = tgt.get("dodges", 0)
            parries = tgt.get("parries", 0)
            blocks = tgt.get("blocks", 0)
            
            if dmg > 0 or casts > 0 or hits > 0:
                actions_list.append({
                    "name": info["name"],
                    "school": info["school"],
                    "icon": info["icon"],
                    "rank": act_id.get("rank", 0),
                    "cost": info.get("cost", ""),
                    "range": info.get("range", ""),
                    "cast": info.get("cast", ""),
                    "desc": info.get("desc", ""),
                    "damage_per_sim": round(dmg / req.iterations, 1),
                    "dps": round(dmg / (req.iterations * req.duration), 2),
                    "percent": round((dmg / (req.iterations * req.duration * total_dps)) * 100, 1) if total_dps > 0 else 0,
                    "casts_per_sim": round(casts / req.iterations, 1),
                    "hits_per_sim": round(hits / req.iterations, 1),
                    "crits_per_sim": round(crits / req.iterations, 1),
                    "crit_percent": round((crits / hits * 100), 1) if hits > 0 else 0.0,
                    "misses_per_sim": round((misses + dodges + parries) / req.iterations, 1)
                })

    actions_list.sort(key=lambda x: x["damage_per_sim"], reverse=True)

    # --- HEALING & SUSTAIN CALCULATIONS ---
    total_heal_bonus = 0
    total_sp = 0
    total_int = 23  # Base Tauren Shaman Intellect at lvl 19
    total_spi = 28  # Base Spirit
    total_mp5 = 0
    
    item_lookup = {}
    for slot_items in ITEM_CATALOG.values():
        for it in slot_items:
            item_lookup[it["id"]] = it
            
    for item_id in req.gear.values():
        if item_id in item_lookup:
            stats = item_lookup[item_id].get("parsedStats", {})
            total_heal_bonus += stats.get("Healing", 0)
            total_sp += stats.get("SP", 0)
            total_int += stats.get("Int", 0)
            total_spi += stats.get("Spi", 0)
            total_mp5 += stats.get("MP5", 0)

    # Parse talents: format is tree0-tree1-tree2 (e.g. -05203- or --55)
    clean_tal = tal_str.strip("-")
    tal_parts = tal_str.split("-")
    t0 = tal_parts[0] if len(tal_parts) > 0 else ""
    t1 = tal_parts[1] if len(tal_parts) > 1 else ""
    t2 = tal_parts[2] if len(tal_parts) > 2 else ""
    
    # Tree 2 (Resto): pos 0 = Imp HW (0-5), pos 1 = Tidal Focus (0-5)
    # Tree 1 (Enhance): pos 2 = Ancestral Knowledge (0-5)
    imp_hw_rank = int(t2[0]) if len(t2) > 0 and t2[0].isdigit() else 0
    tidal_focus_rank = int(t2[1]) if len(t2) > 1 and t2[1].isdigit() else 0
    anc_know_rank = int(t1[2]) if len(t1) > 2 and t1[2].isdigit() else 0

    base_mana = 450 + (total_int * 15)
    if anc_know_rank > 0:
        base_mana = int(base_mana * (1 + anc_know_rank * 0.01))
        
    spell_crit_pct = round(2.2 + (total_int / 59.5), 1)

    hw_spells_data = {
        913: {
            "name": "Healing Wave (Rank 4)", "rank": 4,
            "min_base": 136, "max_base": 163, "base_cast": 2.5, "base_mana": 155,
            "coeff": 2.5 / 3.5, "icon": "spell_nature_magicimmunity"
        },
        547: {
            "name": "Healing Wave (Rank 3)", "rank": 3,
            "min_base": 69, "max_base": 82, "base_cast": 2.0, "base_mana": 80,
            "coeff": 2.0 / 3.5, "icon": "spell_nature_magicimmunity"
        },
        332: {
            "name": "Healing Wave (Rank 2)", "rank": 2,
            "min_base": 36, "max_base": 47, "base_cast": 1.5, "base_mana": 45,
            "coeff": 1.5 / 3.5, "icon": "spell_nature_magicimmunity"
        },
        331: {
            "name": "Healing Wave (Rank 1)", "rank": 1,
            "min_base": 18, "max_base": 22, "base_cast": 1.5, "base_mana": 25,
            "coeff": 1.5 / 3.5, "icon": "spell_nature_magicimmunity"
        }
    }

    effective_heal_power = total_heal_bonus + total_sp
    calculated_hw_ranks = {}
    for sid, hdata in hw_spells_data.items():
        cast_t = max(1.0, round(hdata["base_cast"] - (imp_hw_rank * 0.1), 1))
        mana_c = round(hdata["base_mana"] * (1 - (tidal_focus_rank * 0.01)), 1)
        min_h = round(hdata["min_base"] + (effective_heal_power * hdata["coeff"]), 1)
        max_h = round(hdata["max_base"] + (effective_heal_power * hdata["coeff"]), 1)
        avg_h = round((min_h + max_h) / 2, 1)
        hps_val = round(avg_h / cast_t, 1)
        hpm_val = round(avg_h / mana_c, 2)
        c_to_oom = round(base_mana / mana_c, 1) if mana_c > 0 else 99
        t_to_oom = round(c_to_oom * cast_t, 1)
        tot_cap = int(c_to_oom * avg_h)

        calculated_hw_ranks[sid] = {
            "spell_id": sid,
            "name": hdata["name"],
            "rank": hdata["rank"],
            "icon": hdata["icon"],
            "min_heal": min_h,
            "max_heal": max_h,
            "avg_heal": avg_h,
            "crit_heal": round(avg_h * 1.5, 1),
            "cast_time": cast_t,
            "base_cast_time": hdata["base_cast"],
            "mana_cost": mana_c,
            "base_mana_cost": hdata["base_mana"],
            "hps": hps_val,
            "hpm": hpm_val,
            "casts_to_oom": c_to_oom,
            "time_to_oom": t_to_oom,
            "healing_capacity": tot_cap
        }

    # Check for active healing spells in rotation
    active_heal_steps = []
    if req.custom_rotation is not None:
        for s in req.custom_rotation:
            if s.get("enabled", True) and int(s.get("spellId", 0)) in hw_spells_data:
                active_heal_steps.append(s)

    has_healing = len(active_heal_steps) > 0 or req.rotation_preset in ["resto_burst", "resto_sustain", "hybrid_twink"]
    
    primary_sid = 913
    if active_heal_steps:
        primary_sid = int(active_heal_steps[0].get("spellId", 913))
    elif req.rotation_preset == "resto_sustain":
        primary_sid = 547
    elif req.rotation_preset == "hybrid_twink":
        primary_sid = 913

    prim = calculated_hw_ranks[primary_sid]

    # If healing is active in rotation, inject into actions breakdown
    if has_healing:
        cond = active_heal_steps[0].get("condition", "continuous_heal") if active_heal_steps else "continuous_heal"
        if "continuous" in cond or req.rotation_preset in ["resto_burst", "resto_sustain"]:
            fight_casts = round(req.duration / prim["cast_time"], 1)
        elif "hp50" in cond:
            fight_casts = 2.0  # ~2 emergency heals per 30s fight
        elif "hp80" in cond:
            fight_casts = 4.0
        else:
            fight_casts = round(req.duration / (prim["cast_time"] * 2), 1)

        tot_healed = round(fight_casts * prim["avg_heal"], 1)
        sim_hps = round(tot_healed / req.duration, 2)
        crits = round(fight_casts * (spell_crit_pct / 100), 1)

        actions_list.insert(0, {
            "name": f"{prim['name']} [Heal]",
            "school": "Nature (Heal)",
            "icon": prim["icon"],
            "rank": prim["rank"],
            "is_heal": True,
            "cost": f"{prim['mana_cost']} Mana",
            "range": "40 yd range",
            "cast": f"{prim['cast_time']} sec cast",
            "desc": f"Heals friendly target for {prim['min_heal']} to {prim['max_heal']} HP (+{effective_heal_power} heal power). HPM: {prim['hpm']} HP/Mana.",
            "damage_per_sim": tot_healed,
            "dps": sim_hps,  # represents HPS
            "percent": 0.0,
            "casts_per_sim": fight_casts,
            "hits_per_sim": fight_casts,
            "crits_per_sim": crits,
            "crit_percent": spell_crit_pct,
            "misses_per_sim": 0.0
        })

    healing_summary = {
        "active": has_healing,
        "primary_spell": prim["name"],
        "primary_hps": prim["hps"],
        "primary_hpm": prim["hpm"],
        "avg_heal": prim["avg_heal"],
        "min_heal": prim["min_heal"],
        "max_heal": prim["max_heal"],
        "crit_heal": prim["crit_heal"],
        "cast_time": prim["cast_time"],
        "base_cast_time": prim["base_cast_time"],
        "cast_reduction": round(imp_hw_rank * 0.1, 1),
        "mana_cost": prim["mana_cost"],
        "base_mana_cost": prim["base_mana_cost"],
        "mana_discount_pct": tidal_focus_rank * 1.0,
        "total_mana": base_mana,
        "casts_to_oom": prim["casts_to_oom"],
        "time_to_oom": prim["time_to_oom"],
        "healing_capacity": prim["healing_capacity"],
        "total_healing_power": effective_heal_power,
        "total_int": total_int,
        "total_spi": total_spi,
        "total_mp5": total_mp5,
        "spell_crit": spell_crit_pct,
        "ranks": calculated_hw_ranks
    }

    is_1h = req.gear.get("offhand", 0) != 0
    w_mode = "1h_shield" if is_1h else "2h_staff"
    imb_flag = "flametongue" if "Flametongue" in req.imbue else ("rockbiter" if "Rockbiter" in req.imbue else "frostbrand")

    # --- TANK SURVIVABILITY, MITIGATION & THREAT CALCULATIONS ---
    gear_stats_tank = calculate_gear_stats_from_catalog(req.gear)
    for bk, bv in bonus_dict.items():
        if bk in gear_stats_tank:
            gear_stats_tank[bk] += bv

    # Check if offhand is a shield
    oh_id = req.gear.get("offhand", 0)
    oh_item = item_lookup.get(oh_id, {}) if oh_id else {}
    has_shield = bool(oh_item.get("isShield", False) or (oh_item.get("armor", 0) > 80))

    # Parse tanking talents from Tree 1 (Enhancement):
    # [1][0] Earth's Grasp, [1][3] Guardian Totems, [1][5] Imp Lightning Shield,
    # [1][8] Anticipation (+1% Dodge/rank), [1][9] Toughness (+2% Stamina/rank), [1][13] Spirit Weapons (+5% Parry)
    anticipation_rank = int(t1[8]) if len(t1) > 8 and t1[8].isdigit() else 0
    toughness_rank = int(t1[9]) if len(t1) > 9 and t1[9].isdigit() else 0
    spirit_wpn_rank = int(t1[13]) if len(t1) > 13 and t1[13].isdigit() else 0
    imp_ls_rank = int(t1[5]) if len(t1) > 5 and t1[5].isdigit() else 0

    total_sta = 32 + int(req.level * 1.4) + gear_stats_tank.get("Sta", 0)
    if toughness_rank > 0:
        total_sta = int(round(total_sta * (1.0 + 0.02 * toughness_rank)))
    max_hp = 260 + (req.level * 24) + (total_sta * 10)

    total_agi = 20 + int(req.level * 0.9) + gear_stats_tank.get("Agi", 0)
    total_str = 28 + int(req.level * 1.2) + gear_stats_tank.get("Str", 0)
    total_def = gear_stats_tank.get("Def", 0)
    total_armor = 120 + (total_agi * 2) + gear_stats_tank.get("Armor", 0)

    boss_lvl = req.level + 2
    armor_denom = total_armor + 400 + (85 * boss_lvl)
    armor_dr = min(0.75, max(0.05, total_armor / armor_denom)) if armor_denom > 0 else 0.15
    armor_dr_pct = round(armor_dr * 100, 1)

    dodge_pct = round(4.2 + (total_agi / 14.5) + (anticipation_rank * 1.0) + (total_def * 0.04) + gear_stats_tank.get("Dodge", 0), 1)
    parry_pct = round(5.0 + (total_def * 0.04), 1) if spirit_wpn_rank > 0 else 0.0
    block_pct = round(5.0 + (total_def * 0.04) + (anticipation_rank * 1.0), 1) if has_shield else 0.0
    block_val = int(8 + (req.level * 0.65) + (total_str / 20)) if has_shield else 0
    miss_pct = round(5.0 + (total_def * 0.04), 1)
    total_avoidance_pct = round(miss_pct + dodge_pct + parry_pct + block_pct, 1)

    avoid_mult = max(0.20, 1.0 - ((miss_pct + dodge_pct + parry_pct) / 100.0))
    ehp = int(round(max_hp / max(0.12, (1.0 - armor_dr) * avoid_mult)))

    raw_boss_dps = 42.0 + (req.level * 1.9)
    mitigated_dps = raw_boss_dps * (1.0 - armor_dr) * avoid_mult
    block_mitigation_dps = (block_pct / 100.0) * (block_val / 2.0)
    stoneskin_mitigation = 5.5 + (req.level * 0.25)
    hp5_regen_s = bonus_dict.get("HP5", 0) / 5.0
    dtps = round(max(6.0, mitigated_dps - block_mitigation_dps - stoneskin_mitigation - hp5_regen_s), 1)
    ttd = round(max_hp / max(1.0, dtps), 1)

    # Threat Per Second (TPS):
    # - Base Damage DPS = 1.0 threat per dmg
    # - Earth Shock has a 2.0x threat multiplier in Classic WoW
    # - Rockbiter Weapon adds massive flat bonus threat per second (~32-48 TPS scaled by level)
    # - Lightning Shield adds reflective threat when hit (~14 TPS)
    earth_shock_dps = sum(a["dps"] for a in actions_list if "Earth Shock" in a["name"])
    rockbiter_tps = round((26.0 + req.level * 0.85) if "Rockbiter" in req.imbue else 0.0, 1)
    ls_tps = round((11.0 + req.level * 0.45) * (1.0 + 0.05 * imp_ls_rank), 1)
    total_tps = round(p["dps"]["avg"] + earth_shock_dps + rockbiter_tps + ls_tps, 1)

    tank_score = min(100, int((ehp / (18 + req.level * 1.1)) * 0.45 + (total_tps * 0.35) + (armor_dr_pct * 0.45) + (12 if has_shield else 0)))
    tank_grade = "S+" if tank_score >= 92 else ("S" if tank_score >= 84 else ("A" if tank_score >= 72 else ("B" if tank_score >= 60 else "C")))

    is_tank_active = bool(req.rotation_preset in ["tank_threat", "tank_mitigation"] or (has_shield and "Rockbiter" in req.imbue))

    tank_summary = {
        "active": is_tank_active,
        "ehp": ehp,
        "max_hp": max_hp,
        "total_sta": total_sta,
        "total_armor": total_armor,
        "armor_dr_pct": armor_dr_pct,
        "has_shield": has_shield,
        "dodge_pct": dodge_pct,
        "parry_pct": parry_pct,
        "block_pct": block_pct,
        "block_value": block_val,
        "miss_pct": miss_pct,
        "total_avoidance_pct": total_avoidance_pct,
        "dtps": dtps,
        "ttd": ttd,
        "tps": total_tps,
        "rockbiter_tps": rockbiter_tps,
        "earth_shock_bonus_tps": round(earth_shock_dps, 1),
        "lightning_shield_tps": ls_tps,
        "tank_score": tank_score,
        "tank_grade": tank_grade
    }

    res_data = {
        "status": "success",
        "dps": {
            "avg": round(p["dps"]["avg"], 2),
            "min": round(p["dps"]["min"], 2),
            "max": round(p["dps"]["max"], 2),
            "stdev": round(p["dps"]["stdev"], 2),
        },
        "healing": healing_summary,
        "tank": tank_summary,
        "fight_duration": req.duration,
        "iterations": req.iterations,
        "character_level": req.level,
        "actions": actions_list,
        "cli_equivalent": f"python C:\\Users\\jcbas\\.gemini\\antigravity\\scratch\\sim_cotto.py --weapon-mode {w_mode} --imbue {imb_flag} --talents \"{tal_str}\" --rotation {req.rotation_preset} --iterations {req.iterations}"
    }

    SIM_CACHE[sim_cache_key] = res_data
    if len(SIM_CACHE) > 200:
        try:
            SIM_CACHE.pop(next(iter(SIM_CACHE)))
        except Exception:
            pass

    return res_data

# --- MULTI-ENVIRONMENT & SCENARIO LAB RUNNER ---
class ScenarioSuiteRequest(BaseModel):
    level: int = 19
    imbue: str = "FlametongueWeapon"
    talents: str = "-05203-"
    rotation_preset: str = "burst"
    custom_rotation: Optional[List[Dict[str, Any]]] = None
    buffs: Optional[Any] = None
    gear: Dict[str, int] = {}
    enchants: Optional[Dict[str, int]] = {}
    selected_scenarios: Optional[List[str]] = None
    custom_scenarios: Optional[List[Dict[str, Any]]] = None
    buffs: Optional[Any] = None
    scenarios: Optional[List[Dict[str, Any]]] = None
    buffs: Optional[Any] = None

def calculate_gear_stats_from_catalog(gear: Dict[str, int]):
    total_stats = {
        "Str": 0, "Agi": 0, "Sta": 0, "Int": 0, "Spi": 0,
        "AP": 0, "Crit": 0, "Hit": 0, "Armor": 0,
        "Healing": 0, "SP": 0, "FireSP": 0, "NatureSP": 0,
        "FrostResist": 0, "NatureResist": 0, "FireResist": 0, "ShadowResist": 0, "MP5": 0
    }
    for slot, item_id in gear.items():
        if item_id in ITEM_LOOKUP:
            it = ITEM_LOOKUP[item_id]
            total_stats["Armor"] += it.get("armor", 0)
            stats = it.get("parsedStats", {})
            for k, v in stats.items():
                if k in total_stats:
                    total_stats[k] += v
    return total_stats

def run_single_scenario_sim(scenario: Dict[str, Any], req: ScenarioSuiteRequest):
    s_id = scenario["id"]
    cat = scenario.get("category", "pve_dps")
    dur = scenario.get("duration", 30)
    target_count = scenario.get("targetCount", 1)
    lvl_offset = scenario.get("targetLevelOffset", 0)
    char_lvl = req.level
    target_lvl = char_lvl + lvl_offset
    gear_stats = calculate_gear_stats_from_catalog(req.gear)
    buff_stats = calculate_bonus_stats_from_buffs(req.buffs)
    for bk, bv in buff_stats.items():
        if bk in gear_stats:
            gear_stats[bk] += bv

    # 1. HEALING SCENARIOS
    if cat in ["pve_healing", "pvp_healing"]:
        effective_heal = gear_stats["Healing"] + gear_stats["SP"]
        total_int = gear_stats["Int"]
        base_mana = 400 + (char_lvl * 25) + (total_int * 15)
        mp5 = gear_stats.get("MP5", 0) + (gear_stats["Spi"] * 0.4)
        
        hw_mana = 155 * (1.0 - 0.05)
        hw_heal = 150 + (effective_heal * (2.5 / 3.5))
        hw_hps = round(hw_heal / 2.5, 1)
        casts_to_oom = int(base_mana / hw_mana) if hw_mana > 0 else 20
        time_to_oom = round((casts_to_oom * 2.5) + (base_mana / (mp5 + 1) * 0.2), 1)
        incoming = scenario.get("incomingDps", 85)
        
        triage_ratio = min(1.5, hw_hps / max(1, incoming))
        score = min(100, int((hw_hps * 1.8) + (triage_ratio * 30)))
        grade = "S+" if score >= 92 else ("S" if score >= 84 else ("A" if score >= 72 else ("B" if score >= 60 else "C")))
        
        return {
            "id": s_id,
            "name": scenario["name"],
            "badge": scenario.get("badge", "Healing"),
            "category": cat,
            "primary_metric": f"{hw_hps} HPS",
            "metric_value": hw_hps,
            "score": score,
            "grade": grade,
            "detail_label": "Party Triage & Sustain",
            "details": f"HW R4: ~{int(hw_heal)} heal/cast • {casts_to_oom} casts to OOM (~{time_to_oom}s sustain)",
            "tip": "Stacking MP5 and +Healing increases party survival during high-damage encounters."
        }

    # 1.5 TANKING & MITIGATION SCENARIOS (MAIN TANK & AOE PACK TANK)
    if cat == "pve_tank":
        oh_id = req.gear.get("offhand", 0)
        oh_item = ITEM_LOOKUP.get(oh_id, {}) if oh_id else {}
        has_shield = bool(oh_item.get("isShield", False) or (oh_item.get("armor", 0) > 80))

        # Parse tanking talents from req.talents (Tree 1: [8]=Anticipation, [9]=Toughness, [13]=Spirit Weapons, [5]=Imp LS)
        tal_parts = (req.talents or "").split("-")
        t1 = tal_parts[1] if len(tal_parts) > 1 else ""
        anticipation_rank = int(t1[8]) if len(t1) > 8 and t1[8].isdigit() else 0
        toughness_rank = int(t1[9]) if len(t1) > 9 and t1[9].isdigit() else 0
        spirit_wpn_rank = int(t1[13]) if len(t1) > 13 and t1[13].isdigit() else 0
        imp_ls_rank = int(t1[5]) if len(t1) > 5 and t1[5].isdigit() else 0

        total_sta = 32 + int(char_lvl * 1.4) + gear_stats.get("Sta", 0)
        if toughness_rank > 0:
            total_sta = int(round(total_sta * (1.0 + 0.02 * toughness_rank)))
        max_hp = 260 + (char_lvl * 24) + (total_sta * 10)

        total_agi = 20 + int(char_lvl * 0.9) + gear_stats.get("Agi", 0)
        total_str = 28 + int(char_lvl * 1.2) + gear_stats.get("Str", 0)
        total_def = gear_stats.get("Def", 0)
        total_armor = 120 + (total_agi * 2) + gear_stats.get("Armor", 0)

        denom = total_armor + 400 + (85 * target_lvl)
        armor_dr = min(0.75, max(0.05, total_armor / denom)) if denom > 0 else 0.15
        armor_dr_pct = round(armor_dr * 100, 1)

        dodge_pct = round(4.2 + (total_agi / 14.5) + (anticipation_rank * 1.0) + (total_def * 0.04) + gear_stats.get("Dodge", 0), 1)
        parry_pct = round(5.0 + (total_def * 0.04), 1) if spirit_wpn_rank > 0 else 0.0
        block_pct = round(5.0 + (total_def * 0.04) + (anticipation_rank * 1.0), 1) if has_shield else 0.0
        block_val = int(8 + (char_lvl * 0.65) + (total_str / 20)) if has_shield else 0
        miss_pct = round(5.0 + (total_def * 0.04), 1)

        avoid_mult = max(0.20, 1.0 - ((miss_pct + dodge_pct + parry_pct) / 100.0))
        ehp = int(round(max_hp / max(0.12, (1.0 - armor_dr) * avoid_mult)))

        incoming_raw = scenario.get("incomingDps", 68)
        mitigated = incoming_raw * (1.0 - armor_dr) * avoid_mult
        block_mit = (block_pct / 100.0) * (block_val * max(1, target_count * 0.6))
        stoneskin = (5.5 + char_lvl * 0.25) * max(1, target_count * 0.5)
        dtps = round(max(6.0, mitigated - block_mit - stoneskin), 1)
        ttd = round(max_hp / max(1.0, dtps), 1)

        # Estimate Tank Threat Per Second (TPS)
        ap_est = (total_str * 2) + gear_stats.get("AP", 0) + (80 if "Rockbiter" in req.imbue else 0)
        base_melee_tps = 22.0 + (char_lvl * 1.1) + (ap_est * 0.14)
        rockbiter_tps = (28.0 + char_lvl * 0.9) if "Rockbiter" in req.imbue else 0.0
        earth_shock_tps = 24.0 + (gear_stats.get("SP", 0) * 0.5) + (gear_stats.get("Hit", 0) * 1.5)
        ls_tps = (12.0 + char_lvl * 0.5) * (1.0 + 0.05 * imp_ls_rank) * (1.6 if target_count > 1 else 1.0)
        aoe_totem_tps = (18.0 + gear_stats.get("FireSP", 0) * 0.8) if target_count > 1 else 0.0
        tps = round(base_melee_tps + rockbiter_tps + earth_shock_tps + ls_tps + aoe_totem_tps, 1)

        shield_bonus = 14 if has_shield else 0
        if s_id == "pve_aoe_tank_pack":
            score = min(100, int((ehp / (22 + char_lvl * 1.2)) * 0.42 + (tps * 0.34) + (armor_dr_pct * 0.42) + shield_bonus))
            metric_str = f"{ehp} EHP • {tps} AoE TPS"
            detail_lbl = "4-Mob Pack Mitigation & Aggro"
            tip_str = "1H + Shield with Rockbiter, Lightning Shield, and Stoneclaw/Fire Nova Totem holds multi-mob aggro while minimizing DTPS."
        else:
            score = min(100, int((ehp / (20 + char_lvl * 1.15)) * 0.45 + (tps * 0.35) + (armor_dr_pct * 0.45) + shield_bonus))
            metric_str = f"{ehp} EHP • {tps} TPS"
            detail_lbl = "Main Tank EHP, Mitigation & Threat"
            tip_str = "Equipping a high-Armor Shield + Stamina gear and Rockbiter Weapon maximizes Effective Health (EHP) and Boss Threat."

        grade = "S+" if score >= 92 else ("S" if score >= 84 else ("A" if score >= 72 else ("B" if score >= 60 else "C")))

        return {
            "id": s_id,
            "name": scenario["name"],
            "badge": scenario.get("badge", "Tank"),
            "category": cat,
            "primary_metric": metric_str,
            "metric_value": ehp,
            "score": score,
            "grade": grade,
            "detail_label": detail_lbl,
            "details": f"{max_hp} HP • {total_armor} Armor ({armor_dr_pct}% DR) • {dtps} DTPS • {ttd}s Unhealed TTD",
            "tip": tip_str
        }

    # 2. WSG FLAG RUNNER & ESCAPE SCENARIO
    if s_id == "pvp_flag_runner":
        base_hp = 300 + (char_lvl * 28) + (gear_stats["Sta"] * 10)
        total_armor = gear_stats["Armor"]
        denom = (total_armor + 400 + (85 * char_lvl))
        armor_dr = total_armor / denom if denom > 0 else 0.1
        armor_dr = min(0.75, max(0.05, armor_dr))
        
        has_wolf = char_lvl >= 20
        speed_pct = 140 if has_wolf else 100
        transit_time = 10.2 if has_wolf else 14.3
        
        incoming_dps = scenario.get("incomingDps", 75)
        net_dps_taken = incoming_dps * (1.0 - armor_dr)
        total_damage_taken = net_dps_taken * transit_time
        survival_hp_left = base_hp - total_damage_taken
        survival_rate = max(5, min(99, int((survival_hp_left / max(1, base_hp)) * 100)))
        
        score = min(100, int((survival_rate * 0.7) + (armor_dr * 50) + (15 if has_wolf else 0)))
        grade = "S+" if score >= 92 else ("S" if score >= 84 else ("A" if score >= 72 else ("B" if score >= 60 else "C")))
        
        return {
            "id": s_id,
            "name": scenario["name"],
            "badge": scenario.get("badge", "Flag Runner"),
            "category": cat,
            "primary_metric": f"{survival_rate}% Escape Rate",
            "metric_value": survival_rate,
            "score": score,
            "grade": grade,
            "detail_label": "Flag Transit Survival",
            "details": f"{base_hp} HP • {total_armor} Armor ({int(armor_dr*100)}% DR) • {transit_time:.1f}s cross time ({speed_pct}% speed)",
            "tip": "High Armor + Stamina ensures surviving physical ranged fire and dazes across the midfield."
        }

    # 3. COMBAT DPS SIMULATIONS VIA WOWSIMCLI
    cfg = copy.deepcopy(BASE_REQ)
    player = cfg["raid"]["parties"][0]["players"][0]
    
    cfg["simOptions"]["iterations"] = 50
    cfg["encounter"]["duration"] = dur
    
    targets_list = []
    for i in range(target_count):
        targets_list.append({
            "id": i + 1,
            "name": f"Target {i+1}",
            "level": target_lvl,
            "swingSpeed": 2.0
        })
    cfg["encounter"]["targets"] = targets_list
    
    enchants = req.enchants or {}
    for s_name, item_id in req.gear.items():
        if s_name in SLOT_INDEX_MAP and item_id > 0:
            item_spec = {"id": item_id}
            if enchants.get(s_name, 0) > 0:
                item_spec["enchant"] = enchants[s_name]
            player["equipment"]["items"][SLOT_INDEX_MAP[s_name]] = item_spec

    if any(buff_stats.values()):
        player["bonusStats"] = {"stats": build_bonus_stats_proto(buff_stats)}

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
        json.dump(cfg, tf)
        tmp_name = tf.name

    try:
        proc = subprocess.run([CLI_PATH, "sim", "--infile", tmp_name], capture_output=True, text=True, errors="ignore", timeout=15)
        os.remove(tmp_name)
        if proc.returncode != 0:
            return {"id": s_id, "name": scenario["name"], "badge": scenario.get("badge", "DPS"), "category": cat, "score": 50, "grade": "C", "primary_metric": "--", "details": "Simulation failed"}
        idx = proc.stdout.find("{")
        out = json.loads(proc.stdout[idx:])
        p_res = out["raidMetrics"]["parties"][0]["players"][0]
        dps_val = round(p_res["dps"]["avg"], 1)
        
        if s_id == "pvp_burst_skirmish":
            tot_burst = int(round(dps_val * dur, 0))
            score = min(100, int(dps_val * 1.5))
            metric_text = f"{tot_burst} Dmg (10s)"
            label = "Burst Damage Window"
            tip = "Critical Strike and weapon swing damage maximize kill pressure within 10 seconds."
        elif s_id == "aoe_dungeon_trash":
            score = min(100, int(dps_val * 1.3))
            metric_text = f"{dps_val} Cleave DPS"
            label = f"Cleave Across {target_count} Targets"
            tip = "Fire Nova Totem and Spell Power dramatically amplify AoE clear speeds."
        elif s_id == "pve_dungeon_boss":
            score = min(100, int(dps_val * 1.8))
            metric_text = f"{dps_val} DPS"
            label = "Boss DPS (+3 Lvls Glancing)"
            tip = "Hit Rating mitigates glancing blow penalties against level +3 dungeon bosses."
        elif s_id == "pve_raid_boss":
            score = min(100, int(dps_val * 1.7))
            metric_text = f"{dps_val} DPS"
            label = "90s Raid Endurance DPS"
            tip = "MP5 and mana efficiency sustain your Shock rotation over 90 seconds."
        else:
            score = min(100, int(dps_val * 1.6))
            metric_text = f"{dps_val} DPS"
            label = f"{dur}s Encounter Output"
            tip = "Optimized attack power and spell rank rotation maximize damage per second."

        grade = "S+" if score >= 92 else ("S" if score >= 84 else ("A" if score >= 72 else ("B" if score >= 60 else "C")))

        return {
            "id": s_id,
            "name": scenario["name"],
            "badge": scenario.get("badge", "Combat"),
            "category": cat,
            "primary_metric": metric_text,
            "metric_value": dps_val,
            "score": score,
            "grade": grade,
            "detail_label": label,
            "details": f"Avg DPS: {dps_val} • Fight Length: {dur}s • Targets: {target_count}",
            "tip": tip
        }
    except Exception as e:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        return {"id": s_id, "name": scenario["name"], "badge": scenario.get("badge", "Error"), "category": cat, "score": 50, "grade": "C", "primary_metric": "--", "details": str(e), "tip": "Simulation timed out."}

@app.post("/api/scenarios/simulate-suite")
def simulate_suite(req: ScenarioSuiteRequest):
    suite_cache_key = hashlib.md5(json.dumps(req.dict(), sort_keys=True).encode('utf-8')).hexdigest()
    if suite_cache_key in SIM_CACHE:
        return copy.deepcopy(SIM_CACHE[suite_cache_key])
        
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        all_scenarios = json.load(f)
        
    if req.custom_scenarios:
        all_scenarios.extend(req.custom_scenarios)
        
    if req.selected_scenarios:
        selected_set = set(req.selected_scenarios)
        active_scenarios = [s for s in all_scenarios if s["id"] in selected_set]
    else:
        active_scenarios = [s for s in all_scenarios if s.get("enabled", True)]
        
    if not active_scenarios:
        active_scenarios = all_scenarios[:4]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_single_scenario_sim, sc, req) for sc in active_scenarios]
        results = [f.result() for f in futures]

    total_score = sum(r["score"] for r in results)
    composite_score = round(total_score / max(1, len(results)), 1)
    composite_grade = "S+" if composite_score >= 92 else ("S" if composite_score >= 84 else ("A" if composite_score >= 72 else ("B" if composite_score >= 60 else "C")))

    res_map = {r["id"]: r["score"] for r in results}
    radar = {
        "single_target": res_map.get("pve_single_target", composite_score),
        "aoe_cleave": res_map.get("aoe_dungeon_trash", composite_score),
        "dungeon_boss": res_map.get("pve_dungeon_boss", composite_score),
        "tank_mitigation": max(res_map.get("pve_dungeon_tank", 0), res_map.get("pve_aoe_tank_pack", 0)) or composite_score,
        "raid_endurance": res_map.get("pve_raid_boss", composite_score),
        "pvp_burst": max(res_map.get("pvp_burst_skirmish", 0), res_map.get("pvp_caster_duel", 0)) or composite_score,
        "flag_escape": res_map.get("pvp_flag_runner", composite_score),
        "healing_support": max(res_map.get("pve_dungeon_healing", 0), res_map.get("pvp_arena_healing", 0)) or composite_score
    }

    best_sc = max(results, key=lambda x: x["score"])
    weakest_sc = min(results, key=lambda x: x["score"])

    out_data = {
        "status": "success",
        "composite_score": composite_score,
        "composite_grade": composite_grade,
        "radar": radar,
        "best_scenario": {"name": best_sc["name"], "score": best_sc["score"], "metric": best_sc["primary_metric"]},
        "weakest_scenario": {"name": weakest_sc["name"], "score": weakest_sc["score"], "metric": weakest_sc["primary_metric"]},
        "results": results
    }

    SIM_CACHE[suite_cache_key] = out_data
    if len(SIM_CACHE) > 200:
        try:
            SIM_CACHE.pop(next(iter(SIM_CACHE)))
        except Exception:
            pass

    return out_data

@app.get("/")
def get_index(request: Request):
    return get_asset_response(request, "index")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8090))
    print(f"Starting WoW Forever Twink Simulator at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
