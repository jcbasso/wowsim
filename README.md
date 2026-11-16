# WoW Forever TwinkSim ⚡

> **Interactive Level 10–60 Character Sheet, BiS Optimizer & Twink Simulator tailored for WoW Forever (Classic 1.12.1 Custom Scaled & Blizzlike Rates).**

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Demo-brightgreen?style=flat-square&logo=github)](https://jcbasso.github.io/twinksim/)
[![WoW Forever Version](https://img.shields.io/badge/WoW%20Forever-v1.4.2%20Live-orange?style=flat-square)](https://wowforever.site/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

---

## 🌟 Key Features

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
  - Interactive talent trees (Elemental, Enhancement, Restoration) with level 10–60 point constraints.
  - One-click talent builds and auto-optimization based on target level and chosen spec.

- **🍲 Consumables & Buffs Studio:**
  - Well Fed food ranking (+6 Str, +6 Agi, +6 Sta, +3 Spell Damage Smoked Sagefish), Battle & Guardian elixirs, scrolls, alcohol, and party buffs.

- **⚡ Full Monte-Carlo Combat Simulator:**
  - Integrated with `wowsimcli.exe` C++ engine for deep combat iterations, damage breakdowns, threat (TPS), and effective health (EHP).

---

## 🚀 Running Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jcbasso/twinksim.git
   cd twinksim
   ```

2. **Start the local Python server:**
   ```bash
   python server.py
   ```

3. **Open in your browser:**
   ```
   http://localhost:8090/
   ```

---

## 🌐 GitHub Pages Deployment

This repository is built to run directly on **GitHub Pages** as a static web application:

1. Go to your repository on GitHub: `https://github.com/<your-username>/<repo-name>`
2. Navigate to **Settings** ➔ **Pages**.
3. Under **Build and deployment** ➔ **Source**, select **Deploy from a branch**.
4. Choose the `main` branch and `/ (root)` folder, then click **Save**.
5. Your app will be live at `https://<your-username>.github.io/<repo-name>/`.
