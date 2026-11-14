import json
import os

db_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\db.json"
leftover_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\leftover_db.json"
cat_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\twinksim_web\catalog_full.json"

with open(db_path, "r", encoding="utf-8") as f: db = json.load(f)
with open(leftover_path, "r", encoding="utf-8") as f: ldb = json.load(f)
with open(cat_path, "r", encoding="utf-8") as f: cat = json.load(f)

items_by_id = {it["id"]: it for it in (db.get("items", []) + ldb.get("items", []))}
zones = {z["id"]: z.get("name", "") for z in db.get("zones", [])}
npcs = {n["id"]: n.get("name", "") for n in db.get("npcs", [])}

dungeon_zone_ids = {
    209, 491, 717, 718, 719, 721, 722, 796, 1176, 1337, 1477,
    1581, 1583, 1584, 2017, 2057, 2100, 2437, 2557
}
raid_zone_ids = {1977, 2159, 2677, 2717, 3428, 3429, 3456}

prof_names = {
    1: "Alchemy", 2: "Blacksmithing", 3: "Enchanting", 4: "Engineering",
    5: "Herbalism", 6: "Inscription", 8: "Leatherworking", 9: "Mining",
    10: "Skinning", 11: "Tailoring"
}

prof_keys = {
    1: "alchemy", 2: "blacksmithing", 3: "enchanting", 4: "engineering",
    5: "herbalism", 6: "inscription", 8: "leatherworking", 9: "mining",
    10: "skinning", 11: "tailoring"
}

count_updated = 0

for slot, items in cat.items():
    for it in items:
        iid = it["id"]
        if iid == 0:
            it["sourceCategory"] = "none"
            it["sourceLabel"] = "Empty"
            it["sourceDetail"] = ""
            it["isBoP"] = False
            it["isBoE"] = False
            it["craftedProfession"] = None
            it["requiredProfession"] = None
            continue
            
        db_it = items_by_id.get(iid)
        
        category = "world"
        label = "World Drop"
        detail = "World Drop (BoE)"
        crafted_prof = None
        req_prof = None
        is_bop = False
        
        if db_it:
            sources = db_it.get("sources", [])
            req_prof = db_it.get("requiredProfession")
            
            for s in sources:
                if "crafted" in s:
                    category = "crafted"
                    p_id = s["crafted"].get("profession")
                    crafted_prof = prof_keys.get(p_id)
                    p_name = prof_names.get(p_id, "Crafting")
                    label = f"Crafted ({p_name})"
                    detail = f"Crafted: {p_name}"
                    break
                elif "quest" in s:
                    category = "quest"
                    label = "Quest"
                    q_name = s["quest"].get("name", "")
                    detail = f"Quest: {q_name}" if q_name else "Quest Reward"
                    is_bop = True
                    break
                elif "drop" in s:
                    d = s["drop"]
                    diff = d.get("difficulty", 0)
                    zid = d.get("zoneId", 0)
                    zname = zones.get(zid, "")
                    n_id = d.get("npcId", 0)
                    n_name = npcs.get(n_id, "")
                    
                    if diff == 2 or zid in raid_zone_ids:
                        category = "raid"
                        label = "Raid Drop"
                        detail = f"Raid: {zname}" if zname else "Raid Drop"
                        is_bop = True
                    elif diff == 1 or zid in dungeon_zone_ids or any(k in zname.lower() for k in ["caverns", "deadmines", "keep", "kraul", "deep", "gnome", "monastery", "stockade", "chasm"]):
                        category = "dungeon"
                        label = "Dungeon Drop"
                        if n_name and zname:
                            detail = f"Dungeon: {zname} ({n_name})"
                        elif zname:
                            detail = f"Dungeon: {zname}"
                        elif n_name:
                            detail = f"Dungeon: {n_name}"
                        else:
                            detail = "Dungeon Drop"
                        if it.get("quality") in ["rare", "epic"] and not d.get("otherName") == "World Drop":
                            is_bop = True
                    else:
                        category = "world"
                        label = "World Drop"
                        detail = f"World Drop: {zname}" if zname else "World Drop"
                    break
                elif "pvp" in s:
                    category = "pvp"
                    label = "PvP / WSG"
                    detail = "PvP / Honor / WSG"
                    is_bop = True
                    break
                elif "rep" in s:
                    category = "rep"
                    label = "Reputation"
                    detail = "Reputation Reward"
                    is_bop = True
                    break
                elif "soldBy" in s:
                    category = "vendor"
                    label = "Vendor"
                    sb = s["soldBy"]
                    vnd = sb.get("npcName", "")
                    detail = f"Vendor: {vnd}" if vnd else "Vendor Purchase"
                    break
                    
            name_lower = (it.get("name") or "").lower()
            if any(k in name_lower for k in ["goggles", "flying tiger", "green lens", "deepdive helmet", "rocket boots", "recombobulator", "discombobulator"]):
                req_prof = 4 # Engineering
                if category == "world":
                    category = "crafted"
                    crafted_prof = "engineering"
                    label = "Crafted (Engineering)"
                    detail = label
                is_bop = True

        it["sourceCategory"] = category
        it["sourceLabel"] = label
        it["sourceDetail"] = detail
        it["craftedProfession"] = crafted_prof
        it["requiredProfession"] = req_prof
        it["requiredProfessionName"] = prof_names.get(req_prof) if req_prof else None
        it["isBoP"] = is_bop
        it["isBoE"] = not is_bop
        count_updated += 1

with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(cat, f, indent=2)

print(f"Enriched {count_updated} items with sources, professions and BoP/BoE flags in {cat_path}")
