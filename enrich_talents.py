import json
import os

db_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\assets\database\db.json"
tree_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\wowsims-forever\ui\sim\talents\trees\shaman.json"
out_path = r"C:\Users\jcbas\.gemini\antigravity\scratch\twinksim_web\talents_data.json"

with open(db_path, "r", encoding="utf-8") as f:
    db = json.load(f)
with open(tree_path, "r", encoding="utf-8") as f:
    trees = json.load(f)

icons = {x["id"]: x["icon"] for x in db.get("spellIcons", []) if "id" in x and "icon" in x}

for tree in trees:
    for t in tree["talents"]:
        sid = t["spellId"]
        t["icon"] = icons.get(sid, "inv_misc_questionmark")

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(trees, f, indent=2)

print("Enriched talents_data.json successfully written with icons!")
