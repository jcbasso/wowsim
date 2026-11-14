import json
import os

db_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\db.json"
leftover_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\leftover_db.json"
cat_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\twinksim_web\catalog_full.json"

with open(db_path, "r", encoding="utf-8") as f:
    db = json.load(f)
with open(leftover_path, "r", encoding="utf-8") as f:
    ldb = json.load(f)
with open(cat_path, "r", encoding="utf-8") as f:
    cat = json.load(f)

items_by_id = {it["id"]: it for it in (db.get("items", []) + ldb.get("items", []))}
base_by_name = {it.get("name"): it for it in db.get("items", []) if it["id"] < 200000}

ranged_names = {
    1: "Bow", 2: "Crossbow", 3: "Gun", 4: "Thrown", 5: "Wand",
    6: "Idol", 7: "Libram", 8: "Totem", 9: "Sigil"
}

count_class_allow = 0
count_faction = 0
count_ranged = 0
fixed_req_lvls = 0

for slot, items in cat.items():
    for it in items:
        it_id = it.get("id", 0)
        if it_id == 0:
            continue
            
        db_it = items_by_id.get(it_id)
        if db_it:
            if "classAllowlist" in db_it:
                it["classAllowlist"] = db_it["classAllowlist"]
                count_class_allow += 1
            if "factionRestriction" in db_it:
                it["factionRestriction"] = db_it["factionRestriction"]
                count_faction += 1
            if "rangedWeaponType" in db_it:
                rw = db_it["rangedWeaponType"]
                it["rangedWeaponType"] = rw
                count_ranged += 1
                if rw in ranged_names:
                    it["slotName"] = ranged_names[rw]
            if db_it.get("unique"):
                it["isUnique"] = True
                
        # Fix lvl 60 clones (e.g. Quick Strike Ring 288927, Choker of the Fire Lord 288926)
        if it_id >= 200000:
            base = base_by_name.get(it.get("name"))
            if base and base.get("reqLvl", 0) > it.get("reqLvl", 0):
                it["reqLvl"] = base.get("reqLvl")
                fixed_req_lvls += 1
                
        # Explicit hard guard for Quick Strike Ring
        if it.get("name") == "Quick Strike Ring":
            it["reqLvl"] = 60

with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(cat, f, indent=2)

print(f"Updated {cat_path} successfully:")
print(f"  - Class allowlists added: {count_class_allow}")
print(f"  - Faction restrictions added: {count_faction}")
print(f"  - Ranged weapon types added: {count_ranged}")
print(f"  - Fixed reqLvl discrepancies: {fixed_req_lvls}")
