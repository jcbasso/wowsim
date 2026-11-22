/**
 * WoWSimLab: simlab_analyzer.js
 * Companion Analyzer & Log Differential Tool
 * 
 * Usage:
 *   node simlab_analyzer.js --session <session.json> --log <path/to/WoWCombatLog.txt>
 */

const fs = require('fs');
const path = require('path');

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    session: null,
    log: null
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--session' && args[i + 1]) {
      options.session = args[i + 1];
      i++;
    } else if (args[i] === '--log' && args[i + 1]) {
      options.log = args[i + 1];
      i++;
    }
  }
  return options;
}

function parseCombatLog(logFilePath, session) {
  if (!fs.existsSync(logFilePath)) {
    console.error(`[Error] Combat log file not found at: ${logFilePath}`);
    process.exit(1);
  }

  const logContent = fs.readFileSync(logFilePath, 'utf8');
  const lines = logContent.split(/\r?\n/);

  const stats = {
    totalEvents: 0,
    swings: {
      total: 0,
      hits: 0,
      crits: 0,
      misses: 0,
      dodges: 0,
      glances: 0,
      damageValues: [],
      critValues: [],
      glanceValues: [],
      minDmg: Infinity,
      maxDmg: -Infinity,
      totalDamage: 0
    },
    spells: {}
  };

  const playerName = session?.character?.name || null;
  const targetName = session?.test_meta?.target || null;

  for (const line of lines) {
    if (!line.trim()) continue;

    if (line.includes('SWING_DAMAGE') || line.includes('SWING_MISSED')) {
      if (line.includes('SWING_DAMAGE_LANDED')) continue;

      // Filter by player or target if specified
      if (playerName && !line.includes(playerName)) continue;
      if (targetName && !line.includes(targetName)) continue;

      const parts = line.split(',');
      if (parts.length < 10) continue;

      const eventType = parts[0].split(/\s+/).pop();

      if (eventType === 'SWING_DAMAGE') {
        stats.swings.total++;

        // Detect format: modern logs have 30+ columns with target coords before damage
        let amount = 0;
        let isCrit = false;
        let isGlance = false;

        if (parts.length >= 28) {
          // Modern WoW Combat Log (Build 1.60 / Project 18)
          // Damage fields start after unit coordinates/facing (around index 28)
          amount = parseInt(parts[28]) || parseInt(parts[29]) || 0;
          // In modern log: crit is around index 36, glance around index 37
          for (let i = 28; i < parts.length; i++) {
            const val = parts[i];
            if (val === '1' && (i === 36 || i === 37)) {
              if (i === 36) isCrit = true;
              if (i === 37) isGlance = true;
            }
          }
        } else {
          // Classic 1.12 standard format
          amount = parseInt(parts[9]) || 0;
          isCrit = parts[17] === '1' || parts[17] === 'true';
          isGlance = parts[18] === '1' || parts[18] === 'true';
        }

        if (amount > 0) {
          stats.swings.totalDamage += amount;
          stats.swings.damageValues.push(amount);

          if (amount < stats.swings.minDmg) stats.swings.minDmg = amount;
          if (amount > stats.swings.maxDmg) stats.swings.maxDmg = amount;

          if (isCrit) {
            stats.swings.crits++;
            stats.swings.critValues.push(amount);
          } else if (isGlance) {
            stats.swings.glances++;
            stats.swings.glanceValues.push(amount);
          } else {
            stats.swings.hits++;
          }
        }
      } else if (eventType === 'SWING_MISSED') {
        stats.swings.total++;
        const missType = parts[9] || parts[parts.length - 2] || 'MISS';
        if (missType.includes('DODGE')) stats.swings.dodges++;
        else stats.swings.misses++;
      }
    }
  }

  return stats;
}

function runAnalysis() {
  const options = parseArgs();

  console.log('===============================================================');
  console.log('   WoWSimLab Companion • Combat Simulation Validation Engine   ');
  console.log('===============================================================');

  let session = null;
  if (options.session && fs.existsSync(options.session)) {
    const sessionRaw = fs.readFileSync(options.session, 'utf8');
    session = JSON.parse(sessionRaw);

    console.log(`\n[Test Session Loaded]`);
    console.log(`- ID:        ${session.session_id}`);
    console.log(`- Character: Lvl ${session.character.level} ${session.character.race} ${session.character.class}`);
    console.log(`- Phase:     ${session.test_meta.phase || 'Custom'}`);
    console.log(`- Target:    ${session.test_meta.target} (Lvl ${session.test_meta.targetLevel})`);
    console.log(`- Duration:  ${session.test_meta.durationSeconds}s (${session.test_meta.samplesRecorded} samples)`);

    console.log(`\n[Empirical In-Game Character Attributes]`);
    console.log(`- AP:        ${session.empirical_stats.melee_ap} (Ranged: ${session.empirical_stats.ranged_ap})`);
    console.log(`- Crit %:    ${session.empirical_stats.melee_crit_pct}%`);
    console.log(`- Weapon:    Speed ${session.empirical_stats.weapon_speed}s | Roll: ${session.empirical_stats.weapon_min} - ${session.empirical_stats.weapon_max}`);
    console.log(`- Armor:     ${session.empirical_stats.armor} (Def: ${session.empirical_stats.defense})`);
  }

  if (options.log) {
    console.log(`\n[Parsing Combat Log: ${options.log}...]`);
    const logStats = parseCombatLog(options.log, session);

    const sw = logStats.swings;
    const hitPct = sw.total > 0 ? ((sw.hits / sw.total) * 100).toFixed(1) : 0;
    const critPct = sw.total > 0 ? ((sw.crits / sw.total) * 100).toFixed(1) : 0;
    const missPct = sw.total > 0 ? ((sw.misses / sw.total) * 100).toFixed(1) : 0;
    const dodgePct = sw.total > 0 ? ((sw.dodges / sw.total) * 100).toFixed(1) : 0;
    const glancePct = sw.total > 0 ? ((sw.glances / sw.total) * 100).toFixed(1) : 0;

    const avgDmg = sw.damageValues.length > 0
      ? (sw.damageValues.reduce((a, b) => a + b, 0) / sw.damageValues.length).toFixed(1)
      : 0;

    console.log(`\n---------------------------------------------------------------`);
    console.log(`  EMPIRICAL COMBAT LOG RESULTS (${sw.total} Swings Analyzed)`);
    console.log(`---------------------------------------------------------------`);
    console.log(`- Hit Distribution:`);
    console.log(`  * Normal Hits:  ${sw.hits.toString().padStart(4)} (${hitPct}%)`);
    console.log(`  * Criticals:    ${sw.crits.toString().padStart(4)} (${critPct}%)`);
    console.log(`  * Glancing:     ${sw.glances.toString().padStart(4)} (${glancePct}%)`);
    console.log(`  * Misses:       ${sw.misses.toString().padStart(4)} (${missPct}%)`);
    console.log(`  * Dodges:       ${sw.dodges.toString().padStart(4)} (${dodgePct}%)`);
    console.log(`- Damage Roll Boundaries:`);
    console.log(`  * Logged Range: ${sw.minDmg === Infinity ? 0 : sw.minDmg} - ${sw.maxDmg === -Infinity ? 0 : sw.maxDmg} dmg (Avg: ${avgDmg})`);
    if (session) {
      console.log(`  * Tooltip Base: ${session.empirical_stats.weapon_min} - ${session.empirical_stats.weapon_max} dmg`);
    }
    console.log(`---------------------------------------------------------------\n`);
  } else {
    console.log(`\n[Tip] Provide --log <WoWCombatLog.txt> to compare actual combat swings against your sim math!`);
  }
}

runAnalysis();
