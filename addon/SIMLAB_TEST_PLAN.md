# WoWSimLab • Empirical Calibration & Testing Sheet

This sheet defines the exact in-game tests needed to calibrate **`wowsim`** against the live **WoW Forever** server. Every test targets a specific formula in `index.html` (`simulateCombatInBrowser`) so we can replace estimates with exact server math.

---

## Testing Golden Rules
1. **Best Target:** A **dueling friend/alt** (naked in caster form = ~0 armor, standing with back turned = 0% parry/block, self-healing to stay alive).
2. **Solo Alternative:** Any equal-level open-world mob. Because WoW Forever's combat log records **both Raw (pre-armor) and Actual (post-armor)** damage, solo mobs still work for raw weapon rolls and armor reverse-engineering!
3. **Always equip a weapon** (never bare hands unless testing unarmed).
4. **No random procs/enchants** during Tier 1 & Tier 2 tests (no Crusader, Fiery, Windfury, Battle Shout, or temporary trinkets).
5. **Sample Size:** `50–100` swings for damage ranges; `200+` swings for hit/crit/proc percentages.

---

## Tier 1 — Core Physical & Stat Scaling (Highest Priority)

| ID | Test Name | Formula Calibrated in `wowsim` | Exact In-Game Setup | Target & Samples | Pass Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T1-1** | **Baseline White Swing Roll** | `WeaponMin..Max + (AP / 14) * Speed` | **Phase 1:** Strip all armor (`Strip Armor`), equip 1 weapon, 0 buffs. Auto-attack only. | Naked Duel Partner (from behind) or Mob • **50+ swings** | Raw logged `[Min, Max]` matches formula within **±1 dmg** |
| **T1-2** | **Attack Power Scaling** | `AP / 14` divisor & Strength/Agi → AP conversion per class | **Phase 2:** Same weapon as T1-1, equip pure +Str/+Agi/+AP gear (no procs). Compare Avg Raw Damage delta vs T1-1. | Same target • **50+ swings** | `(Avg_T1_2 - Avg_T1_1) / ((AP2 - AP1) / 14 * Speed)` ≈ **1.00** |
| **T1-3** | **Dual-Wield Off-Hand Penalty** | Off-hand `0.50x` base damage (and Dual-Wield Spec talent scaling) | Equip MH + OH weapons, strip armor, auto-attack only. | Naked Duel Partner • **100+ swings** | OH raw rolls match `0.50x` (or talent-adjusted multiplier) |
| **T1-4** | **Agility → Melee Crit Conversion** | Currently `4.0 + Agi / 19.5` (needs per-class & per-level table) | Record Character Sheet Crit% naked, then equip +Agi items one by one at levels 19, 29, 40, 60. *(Snapshot only — no combat needed!)* | Character Sheet Snapshot (`Export`) | Exact `Agi per 1% Crit` divisor per class/level |
| **T1-5** | **Intellect → Spell Crit Conversion** | Currently `2.5 + Int / 59.5` (needs per-class & per-level table) | Record Spell Crit% naked vs +Int gear at levels 19, 29, 40, 60. *(Snapshot only)* | Character Sheet Snapshot (`Export`) | Exact `Int per 1% Spell Crit` divisor per class/level |

---

## Tier 2 — Hit Table, Armor & Mitigation

| ID | Test Name | Formula Calibrated in `wowsim` | Exact In-Game Setup | Target & Samples | Pass Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T2-1** | **Armor Damage Reduction Formula** | `DR = Armor / (Armor + 400 + 85 * AttackerLvl)` | Duel partner wears **0 Armor**, then **known Armor** (e.g. 1,000 and 2,500). Hit with white swings. | Duel Partner (from behind) • **30 swings each** | Observed `1 - (Actual / Raw)` matches formula within **±0.3%** |
| **T2-2** | **Open-World & Boss Mob Armor** | Currently `targetArmor = 200 + lvl * 65` *(Ghostmaw Lvl 38 measured ~1,690 vs sim's 2,670!)* | Fight standard mobs across level brackets (Lvl 19, 29, 38, 50, 60, Dungeon Boss). | Open-world mobs & Dungeon Bosses • **20+ hits each** | Calibrate exact `targetArmor(lvl, mobType)` curve |
| **T2-3** | **Miss Rate (1H/2H vs Dual-Wield)** | Currently `max(1%, 5% - Hit%)` (check DW +19% penalty & level delta) | Auto-attack equal-level mob (0 level delta) vs +3 level mob, with 0% Hit. | Equal-level & +3 level mobs • **200+ swings** | Verify 1H/2H base miss (~5%), +3 lvl miss (~8-9%), and DW miss (~24%) |
| **T2-4** | **Glancing Blows (+1 / +2 / +3 Lvl)** | Glancing chance & damage penalty against higher-level mobs | Auto-attack a mob 3 levels higher than you with white swings only. | +3 Level Mob • **100+ swings** | Confirm Glancing % (~40%) and average glancing damage penalty (~30-35%) |

---

## Tier 3 — Spells, Imbues & WoW Forever Custom Mechanics

| ID | Test Name | Formula Calibrated in `wowsim` | Exact In-Game Setup | Target & Samples | Pass Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T3-1** | **Spell Base Damage & SP Coefficient** | `BaseDmg + SP * (CastTime / 3.5)` & Spell Crit multiplier (`1.5x` vs `2.0x`) | **Phase 3:** Cast 1 spell (e.g. Lightning Bolt / Fireball / Shadow Bolt) naked (`0 SP`), then with `+SP` gear. | Duel Partner or Mob • **25+ casts each** | `(Avg_Geared - Avg_Naked) / AddedSP` matches expected coefficient |
| **T3-2** | **Shaman Weapon Imbues (Forever Custom)** | Rockbiter AP, Flametongue spell scaling, Windfury sub-40 custom AP & proc rate | Auto-attack with each imbue active (no armor/procs). | Duel Partner • **100+ swings** | Verify WF proc rate (~20%), extra attack count, and custom sub-40 AP bonus |
| **T3-3** | **Warrior Tank Scaling (Forever Custom)** | Shield Slam Block Value scaling, Revenge damage, *Scarlet Retribution* & *Impaled* | Fight mob in Defensive Stance; log Shield Slam, Revenge, and Scarlet Retribution procs with 2 different Block Value / AP sets. | High-HP Mob • **20+ casts** | Exact BV coefficient for Shield Slam & scaling for custom Forever spells |
| **T3-4** | **Sunder Armor / Armor Debuffs** | Armor reduction per Sunder stack (`curTargetArmor = targetArmor - stacks * val`) | Attack high-armor mob, apply 1→5 stacks of Sunder Armor, compare `Actual/Raw` DR% after each stack. | High-HP Mob • **5 hits per stack** | Exact armor stripped per stack matches tooltip & sim |

---

## Tier 4 — Full Rotation (End-to-End Validation)

| ID | Test Name | Formula Calibrated in `wowsim` | Exact In-Game Setup | Target & Samples | Pass Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T4-1** | **Full APL Rotation DPS** | Composite sustained DPS, GCD/cooldown cadence, resource (Rage/Mana/Energy) regen | **Phase 4:** Full gear, full rotation for 60–180 seconds. Export JSON + upload `WoWCombatLog` into the **SimLab Validator** on the webpage. | High-HP Elite / Boss / Healing Duel Partner • **60–180s** | Simulated DPS within **±5%** of Empirical DPS; ability share within **±3%** |

---

## How to Log & Validate Any Test Above
1. In-game, type `/simlab`, pick the matching Phase, and click **`>> START TEST & LOGGING`**.
2. Perform the test, click **`[X] STOP & EXPORT`**, and press `Ctrl+C` to copy the JSON snapshot.
3. Open **WoW Forever • WoW Sim** (`index.html`), click **`🧪 SimLab Validator`** in the top bar.
4. Paste the JSON snapshot + upload your latest `WoWCombatLog-*.txt` from `Logs\`.
5. Review the automatic differential report and check off the test in the **Test Sheet** tab!
