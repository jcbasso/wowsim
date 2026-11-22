# WoWSimLab • In-Game Account, Bags & Bank Inventory Sync + Sim Validator

`WoWSimLab` is an in-game Classic / WoW Forever addon that serves two purposes:
1. **Full Character, Bags & Bank Account Sync (`/simsync` & `WoWSimLab.lua` Drag & Drop):** Automatically scans your **Equipped Gear (17 slots + Enchants), All Bags (`0–4`), Full Bank (`-1` & `5–10`), Primary & Secondary Professions (`Skill / Max`), All Faction Reputations, PvP Rank, Talents, and Live Character Stats**, syncing them into the **WoW Forever Sim** so you can build and compare multiple specs/builds for the same character.
2. **In-Game Simulation Verification Lab (`/simlab`):** Guided target dummy benchmark harness and `/combatlog` differential analyzer.

---

## 📁 Package Structure

* **`WoWSimLab/`** (In-Game Addon):
  * [WoWSimLab.toc](file:///D:/jcbas/Documents/Workspace/Personal/wowsim/addon/WoWSimLab/WoWSimLab.toc): Addon manifest (`SavedVariables: WoWSimLabDB`).
  * [Export.lua](file:///D:/jcbas/Documents/Workspace/Personal/wowsim/addon/WoWSimLab/Export.lua): Full character, Bags (`0–4`), Bank (`-1, 5–10`), Professions, Reputations, PvP Rank, and Talents scanner + JSON / `SavedVariables` serializer.
  * [WoWSimLab.lua](file:///D:/jcbas/Documents/Workspace/Personal/wowsim/addon/WoWSimLab/WoWSimLab.lua): Event listeners (`BANKFRAME_OPENED`, `BAG_UPDATE`, `PLAYER_EQUIPMENT_CHANGED`, `SKILL_LINES_CHANGED`, `UPDATE_FACTION`), `/simsync` command, and `/simlab` UI.
  * [Coords.lua](file:///D:/jcbas/Documents/Workspace/Personal/wowsim/addon/WoWSimLab/Coords.lua), [Arrow.lua](file:///D:/jcbas/Documents/Workspace/Personal/wowsim/addon/WoWSimLab/Arrow.lua), [Gear.lua](file:///D:/jcbas/Documents/Workspace/Personal/wowsim/addon/WoWSimLab/Gear.lua): Target dummy navigation and test helpers.
* **`simlab_analyzer.js`**:
  * [simlab_analyzer.js](file:///D:/jcbas/Documents/Workspace/Personal/wowsim/addon/simlab_analyzer.js): Companion differential analyzer parsing `WoWCombatLog.txt`.

---

## 🔄 How to Sync Your Character, Bags & Bank into the Web Simulator

1. **Install the Addon:**
   Copy the `addon/WoWSimLab` folder into your World of Warcraft AddOns directory:
   ```text
   World of Warcraft/_classic_era_/Interface/AddOns/WoWSimLab/
   ```
2. **Cache Your Bank (Once per Bank Visit):**
   Open your Bank in-game. You will see:
   `[WoWSimLab] Bank cached (X items)!`
   *(Your bank items stay cached in `WoWSimLabDB` even after you walk away from the bank.)*
3. **Sync to the Web App (Both Modes Supported):**
   * **Mode 1 — Drag & Drop `WoWSimLab.lua` (or 1-Click Linked File Re-Sync):**
     * Type `/reload` (or log out) in WoW so the client flushes `SavedVariables` to disk.
     * In the web simulator, click **`🔄 Sync Account & Armory`** and **drag-and-drop** your file from:
       ```text
       World of Warcraft/_classic_era_/WTF/Account/<YourAccount>/SavedVariables/WoWSimLab.lua
       ```
     * Or click **`🔗 Link WoWSimLab.lua for 1-Click Re-Sync`** once — the browser remembers the file handle so you can click **`🔄 Re-Sync File`** on the top bar anytime!
   * **Mode 2 — In-Game `/simsync` Copy & Paste:**
     * Type `/simsync` in-game -> press `Ctrl+C` -> paste directly into the **`🔄 Sync Account & Armory`** modal.

---

## 📊 Running the Companion Differential Analyzer

Run the analyzer with your exported session and combat log:
```bash
node addon/simlab_analyzer.js --session path/to/session.json --log "C:/Program Files (x86)/World of Warcraft/_classic_era_/Logs/WoWCombatLog.txt"
```
