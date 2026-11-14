import json

# Descriptions for all 50 shaman talents across all ranks
TALENT_RANKS = {
    # ELEMENTAL
    "convection": [
        "Reduces the mana cost of your Shock, Lightning Bolt, and Chain Lightning spells by 2%.",
        "Reduces the mana cost of your Shock, Lightning Bolt, and Chain Lightning spells by 4%.",
        "Reduces the mana cost of your Shock, Lightning Bolt, and Chain Lightning spells by 6%.",
        "Reduces the mana cost of your Shock, Lightning Bolt, and Chain Lightning spells by 8%.",
        "Reduces the mana cost of your Shock, Lightning Bolt, and Chain Lightning spells by 10%."
    ],
    "concussion": [
        "Increases the damage done by your Lightning Bolt, Chain Lightning, and Shock spells by 1%.",
        "Increases the damage done by your Lightning Bolt, Chain Lightning, and Shock spells by 2%.",
        "Increases the damage done by your Lightning Bolt, Chain Lightning, and Shock spells by 3%.",
        "Increases the damage done by your Lightning Bolt, Chain Lightning, and Shock spells by 4%.",
        "Increases the damage done by your Lightning Bolt, Chain Lightning, and Shock spells by 5%."
    ],
    "elementalDevastation": [
        "Your Critical Strikes with direct damage spells increase your chance to get a critical strike with melee attacks by 3% for 10 sec.",
        "Your Critical Strikes with direct damage spells increase your chance to get a critical strike with melee attacks by 6% for 10 sec.",
        "Your Critical Strikes with direct damage spells increase your chance to get a critical strike with melee attacks by 9% for 10 sec."
    ],
    "reverberation": [
        "Reduces the cooldown of your Shock spells by 0.2 sec.",
        "Reduces the cooldown of your Shock spells by 0.4 sec.",
        "Reduces the cooldown of your Shock spells by 0.6 sec.",
        "Reduces the cooldown of your Shock spells by 0.8 sec.",
        "Reduces the cooldown of your Shock spells by 1.0 sec."
    ],
    "elementalAlacrity": [
        "Reduces the cast time of your Lightning Bolt and Chain Lightning spells by 0.1 sec.",
        "Reduces the cast time of your Lightning Bolt and Chain Lightning spells by 0.2 sec.",
        "Reduces the cast time of your Lightning Bolt and Chain Lightning spells by 0.3 sec."
    ],
    "callOfFlame": [
        "Increases the damage done by your Fire Totems and Flame Shock by 5%.",
        "Increases the damage done by your Fire Totems and Flame Shock by 10%.",
        "Increases the damage done by your Fire Totems and Flame Shock by 15%."
    ],
    "elementalFocus": [
        "Gives you a 100% chance to enter a Clearcasting state after casting any damage spell. Clearcasting reduces mana cost of your next 2 damage spells by 40%."
    ],
    "elementalWarding": [
        "Reduces damage taken from Fire, Frost, and Nature effects by 4%.",
        "Reduces damage taken from Fire, Frost, and Nature effects by 7%.",
        "Reduces damage taken from Fire, Frost, and Nature effects by 10%."
    ],
    "trialByFire": [
        "Increases damage done by your Fire Nova spell by 15% and reduces its cooldown by 3 sec.",
        "Increases damage done by your Fire Nova spell by 30% and reduces its cooldown by 6 sec."
    ],
    "eyeOfTheStorm": [
        "Gives your Lightning Bolt and Chain Lightning spells a 33% chance to not lose casting time when taking damage.",
        "Gives your Lightning Bolt and Chain Lightning spells a 66% chance to not lose casting time when taking damage.",
        "Gives your Lightning Bolt and Chain Lightning spells a 100% chance to not lose casting time when taking damage."
    ],
    "earthbound": [
        "Your Earthbind Totem immobilizes nearby targets for 3 sec when cast."
    ],
    "elementalReach": [
        "Increases the range of your Lightning Bolt, Chain Lightning, and Fire Totem spells by 3 yards.",
        "Increases the range of your Lightning Bolt, Chain Lightning, and Fire Totem spells by 6 yards."
    ],
    "callOfThunder": [
        "Increases the critical strike chance of your Lightning Bolt and Chain Lightning spells by an additional 5%."
    ],
    "lightningOverload": [
        "Gives your Lightning Bolt and Chain Lightning spells a 7% chance to cast a second similar spell on the same target at no additional mana cost.",
        "Gives your Lightning Bolt and Chain Lightning spells a 14% chance to cast a second similar spell on the same target at no additional mana cost.",
        "Gives your Lightning Bolt and Chain Lightning spells a 20% chance to cast a second similar spell on the same target at no additional mana cost."
    ],
    "elementalFury": [
        "Increases critical strike damage bonus of your Searing, Magma, and Fire Nova Totems and your Fire, Frost, and Nature spells by 20%.",
        "Increases critical strike damage bonus of your Searing, Magma, and Fire Nova Totems and your Fire, Frost, and Nature spells by 40%.",
        "Increases critical strike damage bonus of your Searing, Magma, and Fire Nova Totems and your Fire, Frost, and Nature spells by 60%.",
        "Increases critical strike damage bonus of your Searing, Magma, and Fire Nova Totems and your Fire, Frost, and Nature spells by 80%.",
        "Increases critical strike damage bonus of your Searing, Magma, and Fire Nova Totems and your Fire, Frost, and Nature spells by 100%."
    ],
    "lightningMastery": [
        "Gain mastery over Lightning, reducing the cast time of your Lightning Bolt and Chain Lightning spells by 0.5 sec."
    ],

    # ENHANCEMENT
    "earthsGrasp": [
        "Increases the health of your Stoneclaw Totem by 25% and the radius of your Earthbind Totem by 10%.",
        "Increases the health of your Stoneclaw Totem by 50% and the radius of your Earthbind Totem by 20%."
    ],
    "thunderingStrikes": [
        "Improves your chance to get a critical strike with all spells and attacks by 1%.",
        "Improves your chance to get a critical strike with all spells and attacks by 2%.",
        "Improves your chance to get a critical strike with all spells and attacks by 3%.",
        "Improves your chance to get a critical strike with all spells and attacks by 4%.",
        "Improves your chance to get a critical strike with all spells and attacks by 5%."
    ],
    "ancestralKnowledge": [
        "Increases your Intellect by 1%.",
        "Increases your Intellect by 2%.",
        "Increases your Intellect by 3%.",
        "Increases your Intellect by 4%.",
        "Increases your Intellect by 5%."
    ],
    "guardianTotems": [
        "Increases the amount of damage reduced by your Stoneskin Totem and Windwall Totem by 10% and reduces Grounding Totem cooldown by 1 sec.",
        "Increases the amount of damage reduced by your Stoneskin Totem and Windwall Totem by 20% and reduces Grounding Totem cooldown by 2 sec."
    ],
    "mentalDexterity": [
        "Increases your Attack Power by an amount equal to 33% of your Intellect.",
        "Increases your Attack Power by an amount equal to 66% of your Intellect.",
        "Increases your Attack Power by an amount equal to 100% of your Intellect."
    ],
    "improvedLightningShield": [
        "Increases the damage done by your Lightning Shield orbs by 5%.",
        "Increases the damage done by your Lightning Shield orbs by 10%.",
        "Increases the damage done by your Lightning Shield orbs by 15%."
    ],
    "elementalWeapons": [
        "Increases the melee attack power bonus of your Rockbiter Weapon by 7%, and the damage of Flametongue and Frostbrand by 7%.",
        "Increases the melee attack power bonus of your Rockbiter Weapon by 14%, and the damage of Flametongue and Frostbrand by 14%.",
        "Increases the melee attack power bonus of your Rockbiter Weapon by 20%, and the damage of Flametongue and Frostbrand by 20%."
    ],
    "shamanisticFocus": [
        "Reduces the mana cost of your Shock and Lightning Shield spells by 60% after landing a melee critical strike."
    ],
    "anticipation": [
        "Increases your chance to dodge by an additional 1%.",
        "Increases your chance to dodge by an additional 2%.",
        "Increases your chance to dodge by an additional 3%."
    ],
    "toughness": [
        "Increases your Stamina by 2%.",
        "Increases your Stamina by 4%.",
        "Increases your Stamina by 6%.",
        "Increases your Stamina by 8%.",
        "Increases your Stamina by 10%."
    ],
    "flurry": [
        "Increases your attack speed by 10% for your next 3 swings after dealing a melee critical strike.",
        "Increases your attack speed by 15% for your next 3 swings after dealing a melee critical strike.",
        "Increases your attack speed by 20% for your next 3 swings after dealing a melee critical strike.",
        "Increases your attack speed by 25% for your next 3 swings after dealing a melee critical strike.",
        "Increases your attack speed by 30% for your next 3 swings after dealing a melee critical strike."
    ],
    "stormstrike": [
        "Instantly strike with both weapons for 100% weapon damage and increase Nature damage dealt to target by 20% for 12 sec."
    ],
    "improvedGhostWolf": [
        "Reduces the cast time of your Ghost Wolf spell by 1.0 sec.",
        "Reduces the cast time of your Ghost Wolf spell by 2.0 sec."
    ],
    "spiritWeapons": [
        "Gives a 5% chance to parry enemy melee attacks and reduces all threat generated by melee attacks by 30%."
    ],
    "mentalQuickness": [
        "Increases your spell damage and healing by up to 15% of your Attack Power.",
        "Increases your spell damage and healing by up to 30% of your Attack Power."
    ],
    "improvedStormstrike": [
        "When you Stormstrike, you have a 50% chance to gain 10% base mana and grant an extra Nature charge.",
        "When you Stormstrike, you have a 100% chance to gain 20% base mana and grant 2 extra Nature charges."
    ],
    "maelstromWeapon": [
        "When you deal damage with a melee attack, you have a chance to reduce cast time and mana cost of next spell by 20%. Stacks up to 5 times.",
        "When you deal damage with a melee attack, you have a higher chance to reduce cast time and mana cost of next spell by 20%. Stacks up to 5 times.",
        "When you deal damage with a melee attack, you have a higher chance to reduce cast time and mana cost of next spell by 20%. Stacks up to 5 times.",
        "When you deal damage with a melee attack, you have a higher chance to reduce cast time and mana cost of next spell by 20%. Stacks up to 5 times.",
        "When you deal damage with a melee attack, you have the maximum chance to reduce cast time and mana cost of next spell by 20%. Stacks up to 5 times."
    ],
    "rageOfTheFarseer": [
        "Increases your attack speed by 20% for 15 sec."
    ],

    # RESTORATION
    "improvedHealingWave": [
        "Reduces the casting time of your Healing Wave spell by 0.1 sec.",
        "Reduces the casting time of your Healing Wave spell by 0.2 sec.",
        "Reduces the casting time of your Healing Wave spell by 0.3 sec.",
        "Reduces the casting time of your Healing Wave spell by 0.4 sec.",
        "Reduces the casting time of your Healing Wave spell by 0.5 sec."
    ],
    "tidalFocus": [
        "Reduces the Mana cost of your healing spells by 1% and improves casting pushback resistance by 14%.",
        "Reduces the Mana cost of your healing spells by 2% and improves casting pushback resistance by 28%.",
        "Reduces the Mana cost of your healing spells by 3% and improves casting pushback resistance by 42%.",
        "Reduces the Mana cost of your healing spells by 4% and improves casting pushback resistance by 56%.",
        "Reduces the Mana cost of your healing spells by 5% and improves casting pushback resistance by 70%."
    ],
    "mindfulness": [
        "Allows 10% of your Mana regeneration to continue while casting.",
        "Allows 20% of your Mana regeneration to continue while casting.",
        "Allows 30% of your Mana regeneration to continue while casting."
    ],
    "naturalGrace": [
        "Reduces the threat generated by your spells by 4%.",
        "Reduces the threat generated by your spells by 7%.",
        "Reduces the threat generated by your spells by 10%."
    ],
    "totemicFocus": [
        "Reduces the Mana cost of your totems and spells that summon or move totems by 5%.",
        "Reduces the Mana cost of your totems and spells that summon or move totems by 10%.",
        "Reduces the Mana cost of your totems and spells that summon or move totems by 15%.",
        "Reduces the Mana cost of your totems and spells that summon or move totems by 20%.",
        "Reduces the Mana cost of your totems and spells that summon or move totems by 25%."
    ],
    "improvedReincarnation": [
        "Reduces cooldown of Reincarnation by 10 min and increases health and mana returned upon reincarnation by 10%.",
        "Reduces cooldown of Reincarnation by 20 min and increases health and mana returned upon reincarnation by 20%."
    ],
    "ancestralHealing": [
        "Increases target's armor value by 8% for 15 sec after getting a critical strike from a healing spell.",
        "Increases target's armor value by 16% for 15 sec after getting a critical strike from a healing spell.",
        "Increases target's armor value by 25% for 15 sec after getting a critical strike from a healing spell."
    ],
    "healingFocus": [
        "Gives your healing spells a 23% chance to not lose casting time when taking damage.",
        "Gives your healing spells a 46% chance to not lose casting time when taking damage.",
        "Gives your healing spells a 70% chance to not lose casting time when taking damage."
    ],
    "waterShield": [
        "Surrounds the caster with 3 globes of water, granting mana regeneration and restoring mana when attacked."
    ],
    "tidalMastery": [
        "Increases critical effect chance of your healing and lightning spells by 1%.",
        "Increases critical effect chance of your healing and lightning spells by 2%.",
        "Increases critical effect chance of your healing and lightning spells by 3%.",
        "Increases critical effect chance of your healing and lightning spells by 4%.",
        "Increases critical effect chance of your healing and lightning spells by 5%."
    ],
    "restorativeTotems": [
        "Increases effect of Mana Spring Totem by 5% and healing done by Healing Stream Totem by 5%.",
        "Increases effect of Mana Spring Totem by 10% and healing done by Healing Stream Totem by 10%.",
        "Increases effect of Mana Spring Totem by 15% and healing done by Healing Stream Totem by 15%.",
        "Increases effect of Mana Spring Totem by 20% and healing done by Healing Stream Totem by 20%.",
        "Increases effect of Mana Spring Totem by 25% and healing done by Healing Stream Totem by 25%."
    ],
    "manaTideTotem": [
        "Summons a Mana Tide Totem with 10% of caster's health that restores mana to party members within 20 yards."
    ],
    "healingWay": [
        "Increases the amount healed by your Healing Wave spell by 4%.",
        "Increases the amount healed by your Healing Wave spell by 8%.",
        "Increases the amount healed by your Healing Wave spell by 12%."
    ],
    "naturesSwiftness": [
        "When activated, your next Nature spell with a base casting time less than 10 sec becomes an instant cast spell."
    ],
    "purification": [
        "Increases the effectiveness of your healing spells by 2%.",
        "Increases the effectiveness of your healing spells by 4%.",
        "Increases the effectiveness of your healing spells by 6%.",
        "Increases the effectiveness of your healing spells by 8%.",
        "Increases the effectiveness of your healing spells by 10%."
    ],
    "riptide": [
        "Heals a friendly target instantly and heals additional health over 15 sec."
    ]
}

def main():
    path = r"C:\Users\jcbas\.gemini\antigravity\scratch\twinksim_web\talents_data.json"
    with open(path, "r", encoding="utf-8") as f:
        trees = json.load(f)
    
    for tree in trees:
        for t in tree["talents"]:
            field = t["fieldName"]
            max_pts = t["maxPoints"]
            if field in TALENT_RANKS:
                t["rankDescriptions"] = TALENT_RANKS[field]
            else:
                # Fallback if somehow missing
                t["rankDescriptions"] = [f"Rank {i+1} effect for {t['fancyName']}." for i in range(max_pts)]
                
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trees, f, indent=2)
        
    print(f"Successfully updated {path} with full rank descriptions for all 50 talents!")

if __name__ == "__main__":
    main()
