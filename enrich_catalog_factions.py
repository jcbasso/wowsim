import json

cat_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\twinksim_web\catalog_full.json"
db_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\db.json"
leftover_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\leftover_db.json"

with open(db_path, "r", encoding="utf-8") as f: db = json.load(f)
with open(leftover_path, "r", encoding="utf-8") as f: ldb = json.load(f)
with open(cat_path, "r", encoding="utf-8") as f: cat = json.load(f)

all_db_items = {it["id"]: it for it in (db.get("items", []) + ldb.get("items", []))}

# Build base faction map from db
db_faction_map = {}
for iid, db_it in all_db_items.items():
    factions = set()
    if db_it.get("faction") in (1, 2):
        factions.add(db_it["faction"])
    for s in db_it.get("sources", []):
        q = s.get("quest")
        if q and q.get("faction") in (1, 2):
            factions.add(q["faction"])
        sb = s.get("soldBy")
        if sb and sb.get("faction") in (1, 2):
            factions.add(sb["faction"])
        d = s.get("drop")
        if d:
            zid = d.get("zoneId")
            if zid == 717: factions.add(1) # Stockade -> Alliance
            elif zid == 2437: factions.add(2) # Ragefire Chasm -> Horde
            
    if len(factions) == 1:
        db_faction_map[iid] = list(factions)[0]

total_updated = 0
alliance_count = 0
horde_count = 0

for slot, items in cat.items():
    if not isinstance(items, list): continue
    for it in items:
        iid = it.get("id", 0)
        if iid == 0:
            it["factionRestriction"] = None
            it["factionLabel"] = None
            continue
            
        src = ((it.get("sourceDetail") or "") + " " + (it.get("source") or "")).lower()
        name_lower = (it.get("name") or "").lower()
        
        fac = db_faction_map.get(iid)
        
        # Additional dungeon and name overrides
        if "stockade" in src:
            fac = 1
        elif "ragefire" in src:
            fac = 2
        elif any(k in name_lower for k in ["of the horde", "legionnaire", "advisor's ring", "defiler's", "warsong outrider"]):
            fac = 2
        elif any(k in name_lower for k in ["of the alliance", "protector's band", "lorekeeper's ring", "seal of wrynn", "highlander's", "silverwing"]):
            fac = 1
            
        if fac == 1:
            it["factionRestriction"] = 1
            it["factionLabel"] = "Alliance"
            alliance_count += 1
            total_updated += 1
        elif fac == 2:
            it["factionRestriction"] = 2
            it["factionLabel"] = "Horde"
            horde_count += 1
            total_updated += 1
        else:
            it["factionRestriction"] = None
            it["factionLabel"] = None

print(f"Total items with faction set: {total_updated} (Alliance: {alliance_count}, Horde: {horde_count})")

with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(cat, f, indent=2)

print("Saved enriched catalog_full.json with faction tags!")
