-- WoWSimLab: Gear.lua
-- Equipment profile manager and automated stripper/validator
WoWSimLab = WoWSimLab or {}

-- Explicit inventory slot numbers in WoW (avoids nil globals at load time)
local INVSLOT_HEAD = 1
local INVSLOT_NECK = 2
local INVSLOT_SHOULDER = 3
local INVSLOT_CHEST = 5
local INVSLOT_WAIST = 6
local INVSLOT_LEGS = 7
local INVSLOT_FEET = 8
local INVSLOT_WRIST = 9
local INVSLOT_HAND = 10
local INVSLOT_FINGER1 = 11
local INVSLOT_FINGER2 = 12
local INVSLOT_TRINKET1 = 13
local INVSLOT_TRINKET2 = 14
local INVSLOT_BACK = 15
local INVSLOT_MAINHAND = 16
local INVSLOT_OFFHAND = 17
local INVSLOT_RANGED = 18

local ARMOR_SLOTS = {
    INVSLOT_HEAD,
    INVSLOT_NECK,
    INVSLOT_SHOULDER,
    INVSLOT_BACK,
    INVSLOT_CHEST,
    INVSLOT_WRIST,
    INVSLOT_HAND,
    INVSLOT_WAIST,
    INVSLOT_LEGS,
    INVSLOT_FEET,
    INVSLOT_FINGER1,
    INVSLOT_FINGER2,
    INVSLOT_TRINKET1,
    INVSLOT_TRINKET2,
    INVSLOT_OFFHAND,
    INVSLOT_RANGED
}

-- Unequips all armor, rings, trinkets, and offhand to isolate single-weapon baseline
function WoWSimLab:StripArmorForTest()
    if InCombatLockdown() then
        print("|cffff4444[WoWSimLab]|r Cannot change gear while in combat!")
        return false
    end

    local unequippedCount = 0
    for _, slotId in ipairs(ARMOR_SLOTS) do
        local itemLink = GetInventoryItemLink("player", slotId)
        if itemLink then
            PickupInventoryItem(slotId)
            -- Put into first available bag space
            for bag = 0, 4 do
                local freeSlots, bagType
                if C_Container and C_Container.GetContainerNumFreeSlots then
                    freeSlots, bagType = C_Container.GetContainerNumFreeSlots(bag)
                elseif GetContainerNumFreeSlots then
                    freeSlots, bagType = GetContainerNumFreeSlots(bag)
                end

                if freeSlots and freeSlots > 0 and (bagType == 0 or bag == 0 or not bagType) then
                    local numSlots = (C_Container and C_Container.GetContainerNumSlots) and C_Container.GetContainerNumSlots(bag) or (GetContainerNumSlots and GetContainerNumSlots(bag)) or 16
                    for slot = 1, numSlots do
                        local info = (C_Container and C_Container.GetContainerItemInfo) and C_Container.GetContainerItemInfo(bag, slot) or (GetContainerItemInfo and GetContainerItemInfo(bag, slot))
                        if not info then
                            if C_Container and C_Container.PickupContainerItem then
                                C_Container.PickupContainerItem(bag, slot)
                            elseif PickupContainerItem then
                                PickupContainerItem(bag, slot)
                            end
                            unequippedCount = unequippedCount + 1
                            break
                        end
                    end
                    break
                end
            end
        end
    end

    print(string.format("|cff00e5ff[WoWSimLab]|r Unequipped %d armor slots. Weapon isolated.", unequippedCount))
    return true
end

-- Validates whether character meets gear profile for active test phase
function WoWSimLab:ValidateGearForPhase(phaseKey)
    local mhLink = GetInventoryItemLink("player", INVSLOT_MAINHAND)
    if not mhLink then
        return false, "Missing Main-Hand Weapon!"
    end

    if phaseKey == "phase1_white_hits" then
        -- Must have 0 armor items equipped
        for _, slotId in ipairs(ARMOR_SLOTS) do
            local itemLink = GetInventoryItemLink("player", slotId)
            if itemLink then
                return false, "Armor items still equipped! Click 'Strip Armor'."
            end
        end
        return true, "Clean single weapon equipped (Naked)."
    end

    return true, "Gear ready."
end
