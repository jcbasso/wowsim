# WoW Forever • WoW Sim ⚡

> **Interactive Level 1–60 Character Sheet, BiS Optimizer & Combat Simulator tailored for WoW Forever (Classic 1.12.1 Custom Scaled & Blizzlike Rates).**

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Demo-brightgreen?style=flat-square&logo=github)](https://jcbasso.github.io/wowsim/)
[![WoW Forever Version](https://img.shields.io/badge/WoW%20Forever-v1.4.2%20Live-orange?style=flat-square)](https://wowforever.site/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

---

## 🌟 Key Features

- **⚡ In-Browser Client Monte-Carlo Combat Simulator:**
  - Runs 50–2,000 iterations of full combat encounters directly in your browser client in milliseconds.
  - Complete simulation of auto-attacks, weapon imbues (Flametongue, Rockbiter, Frostbrand, Windfury), spell rotations (Shocks, Totems, Stormstrike), and enchant procs (Crusader, Fiery Weapon, Lifestealing).
  - Works 100% standalone on **GitHub Pages** with zero backend or installation required.

- **🛡️ Authentic Character Equipment Sheet:**
  - 17 gear slot cards with authentic WoW item rarity borders, Wowhead dynamic tooltips, and middle-click Wowhead navigation.
  - Interactive gear picker with instant search, stat filters, BoP vs. BoE filtering, and faction restrictions.
  - Multi-source badges: 🏰 Dungeons, 📜 Quests, 🔨 Crafted, 🌍 World BoE, ⚔️ PvP / Rep, and 💰 Vendors.

- **📈 Next-Level BiS Upgrade Roadmap & Planner:**
  - Inline unlock pills on each equipment slot (`🔼 Lvl X: [Item Name] (+Y pts)`) showing upcoming BiS unlocks.
  - Chronological Timeline mode (`📅 By Level`) and progression chain mode (`🛡️ By Slot Chain`).
  - Scan lookahead horizons (`+5 Levels`, `+10 Levels / Next Bracket`, `+20 Levels`, or up to `Level 60`).

- **⚖️ Configurable Stat Weights & Spec Profiles:**
  - Full support for **Enhancement DPS**, **Elemental Caster**, **Warden Tank**, and **Restoration Healer**.
  - Customizable Pawn stat weights (Strength, Agility, Attack Power, Melee/Spell Crit, Spell Power, MP5, Armor, Defense, Dodge).

- **🌳 Authentic Talent Calculator:**
  - Interactive talent trees (Elemental, Enhancement, Restoration) with level 1–60 point constraints.
  - Default starter setup at Level 1 with 0 talent points, unlocking points dynamically as you level.

- **🍲 Consumables & Buffs Studio:**
  - Well Fed food ranking (+6 Str, +6 Agi, +6 Sta, +3 Spell Damage Smoked Sagefish), Battle & Guardian elixirs, scrolls, alcohol, and party buffs.

- **🔬 Scenarios Multi-Environment Lab:**
  - 12 built-in and customizable encounters: Dungeon Bosses, AoE Cleave Trash, Raid Boss Endurance, WSG Flag Runner, Main Tank, AoE Tank Pack, and Dungeon/Raid/PvP Healing.
  - Evaluates composite score, letter grade, and multi-axis radar chart directly in your browser.

---

## 🚀 Running Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jcbasso/wowsim.git
   cd wowsim
   ```

2. **Start the local Python server (optional for local C++ CLI execution):**
   ```bash
   python server.py
   ```

3. **Open in your browser:**
   ```
   http://localhost:8090/
   ```
   *(Or simply open `index.html` directly in any web browser!)*

---

## 🌐 GitHub Pages Deployment

This repository runs directly on **GitHub Pages** as a static web application:

1. Go to your repository on GitHub: `https://github.com/<your-username>/<repo-name>`
2. Navigate to **Settings** ➔ **Pages**.
3. Under **Build and deployment** ➔ **Source**, select **Deploy from a branch**.
4. Choose the `main` branch and `/ (root)` folder, then click **Save**.
5. Your app will be live at `https://<your-username>.github.io/<repo-name>/`.
