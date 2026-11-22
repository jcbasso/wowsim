-- WoWSimLab: Export.lua
-- Extracts complete character state + Equipped Gear + Bags (0..4) + Bank (-1, 5..10) + Professions + Reputations + PvP Rank + Talents
-- Persists to WoWSimLabDB (WTF/Account/<Acc>/SavedVariables/WoWSimLab.lua) for Drag & Drop Sync and formats JSON for /simsync
WoWSimLab = WoWSimLab or {}

-- Converts Lua table to clean JSON string
local function TableToJson(val, indent)
    indent = indent or ""
    local nextIndent = indent .. "  "
    local t = type(val)

    if t == "table" then
        local isArray = (#val > 0)
        local hasAny = false
        for _ in pairs(val) do hasAny = true; break end
        if not hasAny then return "{}" end
        local parts = {}
        if isArray then
            for _, v in ipairs(val) do
                table.insert(parts, nextIndent .. TableToJson(v, nextIndent))
            end
            return "[\n" .. table.concat(parts, ",\n") .. "\n" .. indent .. "]"
        else
            local keys = {}
            for k in pairs(val) do table.insert(keys, k) end
            table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
            for _, k in ipairs(keys) do
                local v = val[k]
                local keyStr = string.format("%q", tostring(k))
                table.insert(parts, nextIndent .. keyStr .. ": " .. TableToJson(v, nextIndent))
            end
            return "{\n" .. table.concat(parts, ",\n") .. "\n" .. indent .. "}"
        end
    elseif t == "string" then
        return string.format("%q", val)
    elseif t == "number" then
        return tostring(val)
    elseif t == "boolean" then
        return val and "true" or "false"
    else
        return "null"
    end
end

WoWSimLab.TableToJson = TableToJson

-- Extracts item ID, enchant ID, and item Name from itemLink
local function ParseItemLink(link)
    if not link then return 0, 0, "" end
    local itemId, enchantId = link:match("item:(%d+):(%d*)")
    local name = link:match("%[(.-)%]") or ""
    return tonumber(itemId) or 0, tonumber(enchantId) or 0, name
end

-- Cross-version container helpers (supports Classic 1.12/1.14/1.15 GetContainerNumSlots AND C_Container)
local function SafeGetBagSlots(bagId)
    if C_Container and C_Container.GetContainerNumSlots then
        return C_Container.GetContainerNumSlots(bagId) or 0
    elseif GetContainerNumSlots then
        return GetContainerNumSlots(bagId) or 0
    end
    return 0
end

local function SafeGetBagItemLink(bagId, slotId)
    if C_Container and C_Container.GetContainerItemLink then
        return C_Container.GetContainerItemLink(bagId, slotId)
    elseif GetContainerItemLink then
        return GetContainerItemLink(bagId, slotId)
    end
    return nil
end

local function SafeGetBagItemCount(bagId, slotId)
    if C_Container and C_Container.GetContainerItemInfo then
        local info = C_Container.GetContainerItemInfo(bagId, slotId)
        return (info and info.stackCount) or 1
    elseif GetContainerItemInfo then
        local _, count = GetContainerItemInfo(bagId, slotId)
        return count or 1
    end
    return 1
end

-- Scan player's active bags (Backpack 0 + Bags 1..4)
function WoWSimLab:ScanBagsInventory()
    local bagItems = {}
    for bag = 0, 4 do
        local numSlots = SafeGetBagSlots(bag)
        for slot = 1, numSlots do
            local link = SafeGetBagItemLink(bag, slot)
            if link then
                local iId, eId, iName = ParseItemLink(link)
                if iId and iId > 0 then
                    local count = SafeGetBagItemCount(bag, slot)
                    table.insert(bagItems, {
                        id = iId,
                        enchant = eId,
                        name = iName,
                        count = count,
                        bag = bag,
                        slot = slot,
                        location = "bag"
                    })
                end
            end
        end
    end
    return bagItems
end

-- Scan player's Bank when Bank frame is open (Main bank -1 + Bank Bags 5..10)
function WoWSimLab:ScanBankInventory()
    local bankItems = {}
    local bankBags = { -1, 5, 6, 7, 8, 9, 10 }
    for _, bag in ipairs(bankBags) do
        local numSlots = SafeGetBagSlots(bag)
        for slot = 1, numSlots do
            local link = SafeGetBagItemLink(bag, slot)
            if link then
                local iId, eId, iName = ParseItemLink(link)
                if iId and iId > 0 then
                    local count = SafeGetBagItemCount(bag, slot)
                    table.insert(bankItems, {
                        id = iId,
                        enchant = eId,
                        name = iName,
                        count = count,
                        bag = bag,
                        slot = slot,
                        location = "bank"
                    })
                end
            end
        end
    end
    return bankItems
end

-- Scan Primary & Secondary Professions (Leatherworking, Skinning, Engineering, Blacksmithing, etc.)
local KNOWN_PROFESSIONS = {
    ["alchemy"] = true, ["blacksmithing"] = true, ["enchanting"] = true,
    ["engineering"] = true, ["herbalism"] = true, ["leatherworking"] = true,
    ["mining"] = true, ["skinning"] = true, ["tailoring"] = true,
    ["cooking"] = true, ["first aid"] = true, ["fishing"] = true
}

function WoWSimLab:ScanProfessions()
    local profs = {}
    if not GetNumSkillLines or not GetSkillLineInfo then return profs end
    local numSkills = GetNumSkillLines() or 0
    for i = 1, numSkills do
        local skillName, isHeader, _, skillRank, _, _, skillMaxRank = GetSkillLineInfo(i)
        if skillName and not isHeader then
            local lower = string.lower(skillName)
            if KNOWN_PROFESSIONS[lower] then
                table.insert(profs, {
                    id = lower,
                    name = skillName,
                    skill = tonumber(skillRank) or 0,
                    max = tonumber(skillMaxRank) or 300
                })
            end
        end
    end
    return profs
end

-- Scan Faction Reputations (Neutral -> Exalted)
local STANDING_LABELS = {
    [1] = "Hated", [2] = "Hostile", [3] = "Unfriendly", [4] = "Neutral",
    [5] = "Friendly", [6] = "Honored", [7] = "Revered", [8] = "Exalted"
}

function WoWSimLab:ScanReputations()
    local reps = {}
    if not GetNumFactions or not GetFactionInfo then return reps end
    local numFactions = GetNumFactions() or 0
    for i = 1, numFactions do
        local name, _, standingID, barMin, barMax, barValue, _, _, isHeader = GetFactionInfo(i)
        if name and not isHeader and standingID then
            reps[name] = STANDING_LABELS[standingID] or "Neutral"
        end
    end
    return reps
end

-- Scan PvP Rank (0..14)
function WoWSimLab:ScanPvPRank()
    if not UnitPVPRank then return 0, "None" end
    local pvpRankRaw = UnitPVPRank("player") or 0
    local rankNumber = 0
    local rankName = "None"
    if pvpRankRaw >= 5 then
        rankNumber = pvpRankRaw - 4
        if GetPVPRankInfo then
            local rName, rNum = GetPVPRankInfo(pvpRankRaw)
            if rNum and rNum > 0 then rankNumber = rNum end
            if rName then rankName = rName end
        end
    end
    return rankNumber, rankName
end

-- Collects full per-talent point strings (e.g. "000000000000000-505030300410000-000000000000000") and tree totals ("0-21-0")
function WoWSimLab:ScanTalents()
    local treeTotals = {}
    local fullTrees = {}
    local numTabs = GetNumTalentTabs and GetNumTalentTabs() or 0
    for tab = 1, numTabs do
        local pts = 0
        local digitList = {}
        local numTalents = GetNumTalents(tab) or 0
        for t = 1, numTalents do
            local _, _, _, _, curPts = GetTalentInfo(tab, t)
            local p = tonumber(curPts) or 0
            pts = pts + p
            table.insert(digitList, tostring(p))
        end
        table.insert(treeTotals, tostring(pts))
        table.insert(fullTrees, table.concat(digitList, ""))
    end
    return table.concat(treeTotals, "-"), table.concat(fullTrees, "-")
end

-- Collects 100% complete character & account snapshot matching wowsim inputs
function WoWSimLab:CaptureCharacterSnapshot(testMeta)
    local charName = UnitName("player") or "Character"
    local realmName = GetRealmName and GetRealmName() or "Forever"
    local charKey = charName .. "-" .. realmName
    local _, playerClass = UnitClass("player")
    local _, playerRace = UnitRace("player")
    local playerLevel = UnitLevel("player") or 1
    local factionGroup = select(1, UnitFactionGroup("player")) or "Horde"

    -- Ensure SavedVariables table structure exists
    WoWSimLabDB = WoWSimLabDB or {}
    WoWSimLabDB.sessions = WoWSimLabDB.sessions or {}
    WoWSimLabDB.characters = WoWSimLabDB.characters or {}
    local prevCharData = WoWSimLabDB.characters[charKey] or {}

    -- Attributes & Health/Mana
    local str = UnitStat("player", 1) or 0
    local agi = UnitStat("player", 2) or 0
    local sta = UnitStat("player", 3) or 0
    local int = UnitStat("player", 4) or 0
    local spi = UnitStat("player", 5) or 0
    local maxHP = UnitHealthMax("player") or 0
    local maxMana = UnitPowerMax and UnitPowerMax("player", 0) or (UnitManaMax and UnitManaMax("player") or 0)

    local baseAP, posAP, negAP = UnitAttackPower("player")
    local totalAP = (baseAP or 0) + (posAP or 0) + (negAP or 0)

    local rangedBaseAP, rangedPosAP, rangedNegAP = UnitRangedAttackPower("player")
    local totalRangedAP = (rangedBaseAP or 0) + (rangedPosAP or 0) + (rangedNegAP or 0)

    local meleeCrit = GetCritChance and GetCritChance() or 0.0
    local rangedCrit = GetRangedCritChance and GetRangedCritChance() or 0.0
    local spellCrit = GetSpellCritChance and GetSpellCritChance(1) or 0.0
    local hitMod = GetHitModifier and GetHitModifier() or 0.0

    local _, effectiveArmor = UnitArmor("player")
    local baseDef, bonusDef = UnitDefense("player")
    local dodge = GetDodgeChance and GetDodgeChance() or 0.0
    local parry = GetParryChance and GetParryChance() or 0.0
    local block = GetBlockChance and GetBlockChance() or 0.0
    local blockVal = GetShieldBlock and GetShieldBlock() or 0

    -- Resistances (Holy=1, Fire=2, Nature=3, Frost=4, Shadow=5, Arcane=6)
    local fireRes = select(2, UnitResistance("player", 2)) or 0
    local natureRes = select(2, UnitResistance("player", 3)) or 0
    local frostRes = select(2, UnitResistance("player", 4)) or 0
    local shadowRes = select(2, UnitResistance("player", 5)) or 0
    local arcaneRes = select(2, UnitResistance("player", 6)) or 0

    -- Weapon bounds
    local mhLow, mhHigh = UnitDamage("player")
    local mhSpeed = UnitAttackSpeed("player")

    -- Explicit slot constants (supports both ring1/ring2 and finger1/finger2)
    local slots = {
        head = 1, neck = 2, shoulders = 3,
        back = 15, chest = 5, wrist = 9,
        hands = 10, waist = 6, legs = 7,
        feet = 8, ring1 = 11, ring2 = 12,
        trinket1 = 13, trinket2 = 14,
        mainhand = 16, offhand = 17, relic = 18
    }

    local gear = {}
    local enchants = {}
    local equippedDetails = {}
    for slotName, slotId in pairs(slots) do
        local link = GetInventoryItemLink("player", slotId)
        local iId, eId, iName = ParseItemLink(link)
        gear[slotName] = iId
        enchants[slotName] = eId
        if iId > 0 then
            table.insert(equippedDetails, {
                id = iId,
                enchant = eId,
                name = iName,
                slot = slotName,
                location = "equipped"
            })
        end
    end
    gear.finger1 = gear.ring1
    gear.finger2 = gear.ring2

    local talentSummary, talentFull = self:ScanTalents()
    local professions = self:ScanProfessions()
    local reputations = self:ScanReputations()
    local pvpRank, pvpRankName = self:ScanPvPRank()
    local bagItems = self:ScanBagsInventory()

    -- Keep previously scanned bank cache unless bank is currently open and non-empty
    local cachedBank = prevCharData.bank or {}
    local bankLastUpdated = prevCharData.bankLastUpdated or nil
    if self.isBankOpen then
        local freshBank = self:ScanBankInventory()
        if #freshBank > 0 or SafeGetBagSlots(-1) > 0 then
            cachedBank = freshBank
            bankLastUpdated = date("%Y-%m-%d %H:%M:%S")
        end
    end

    -- Build deduplicated ownedItems summary (Equipped + Bags + Bank) for instant BiS filtering
    local ownedById = {}
    local ownedList = {}
    local function addOwned(entry)
        if not entry or not entry.id or entry.id <= 0 then return end
        local existing = ownedById[entry.id]
        if not existing then
            local rec = {
                id = entry.id,
                name = entry.name or "",
                enchant = entry.enchant or 0,
                location = entry.location or "bag",
                count = entry.count or 1
            }
            ownedById[entry.id] = rec
            table.insert(ownedList, rec)
        else
            existing.count = (existing.count or 1) + (entry.count or 1)
            if entry.location == "equipped" then
                existing.location = "equipped"
            end
        end
    end

    for _, it in ipairs(equippedDetails) do addOwned(it) end
    for _, it in ipairs(bagItems) do addOwned(it) end
    for _, it in ipairs(cachedBank) do addOwned(it) end

    -- Buffs
    local buffs = {}
    for i = 1, 40 do
        local name, _, _, _, _, _, _, _, _, spellId
        if UnitBuff then
            name, _, _, _, _, _, _, _, _, spellId = UnitBuff("player", i)
        end
        if name then
            table.insert(buffs, { name = name, spellId = spellId })
        else
            break
        end
    end

    local snapshot = {
        addon_version = "1.2.0",
        session_id = testMeta and testMeta.sessionId or ("simsync_" .. time()),
        timestamp = date("%Y-%m-%d %H:%M:%S"),
        name = charName,
        realm = realmName,
        charKey = charKey,
        level = playerLevel,
        class = string.lower(playerClass or "shaman"),
        race = string.lower((playerRace or "tauren"):gsub("%s+", "_")),
        faction = factionGroup,
        pvpRank = pvpRank,
        pvpRankName = pvpRankName,
        professions = professions,
        reputations = reputations,
        character = {
            name = charName,
            realm = realmName,
            class = string.lower(playerClass or "shaman"),
            race = string.lower((playerRace or "tauren"):gsub("%s+", "_")),
            level = playerLevel,
            faction = factionGroup,
            pvpRank = pvpRank
        },
        gear = gear,
        enchants = enchants,
        bags = bagItems,
        bank = cachedBank,
        bankLastUpdated = bankLastUpdated,
        ownedItems = ownedList,
        talents = talentSummary,
        talentFull = talentFull,
        buffs = buffs,
        armoryStats = {
            health = maxHP,
            mana = maxMana,
            str = str,
            agi = agi,
            sta = sta,
            int = int,
            spi = spi
        },
        empirical_stats = {
            health = maxHP,
            mana = maxMana,
            strength = str,
            agility = agi,
            stamina = sta,
            intellect = int,
            spirit = spi,
            melee_ap = totalAP,
            ranged_ap = totalRangedAP,
            melee_crit_pct = math.floor(meleeCrit * 10) / 10,
            ranged_crit_pct = math.floor(rangedCrit * 10) / 10,
            spell_crit_pct = math.floor(spellCrit * 10) / 10,
            hit_pct = hitMod,
            armor = effectiveArmor or 0,
            defense = (baseDef or 0) + (bonusDef or 0),
            dodge_pct = math.floor(dodge * 10) / 10,
            parry_pct = math.floor(parry * 10) / 10,
            block_pct = math.floor(block * 10) / 10,
            block_value = blockVal,
            weapon_speed = math.floor((mhSpeed or 2.0) * 100) / 100,
            weapon_min = math.floor(mhLow or 0),
            weapon_max = math.floor(mhHigh or 0),
            resistances = {
                fire = fireRes,
                nature = natureRes,
                frost = frostRes,
                shadow = shadowRes,
                arcane = arcaneRes
            }
        },
        test_meta = testMeta or {}
    }

    -- Save to WoWSimLabDB so /reload or logout writes everything to SavedVariables/WoWSimLab.lua!
    WoWSimLabDB.characters[charKey] = snapshot
    WoWSimLabDB.lastSyncedChar = charKey
    WoWSimLabDB.lastSyncJson = TableToJson(snapshot)

    return snapshot
end

-- Export Modal Frame (Ctrl+C popup)
local exportFrame = CreateFrame("Frame", "WoWSimLabExportFrame", UIParent, "BackdropTemplate")
exportFrame:SetSize(540, 440)
exportFrame:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
exportFrame:SetMovable(true)
exportFrame:EnableMouse(true)
exportFrame:RegisterForDrag("LeftButton")
exportFrame:SetScript("OnDragStart", exportFrame.StartMoving)
exportFrame:SetScript("OnDragStop", exportFrame.StopMovingOrSizing)
exportFrame:SetBackdrop({
    bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background-Dark",
    edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
    tile = true, tileSize = 32, edgeSize = 24,
    insets = { left = 6, right = 6, top = 6, bottom = 6 }
})
exportFrame:Hide()

local title = exportFrame:CreateFontString(nil, "OVERLAY", "GameFontHighlightLarge")
title:SetPoint("TOP", exportFrame, "TOP", 0, -14)
title:SetText("|cff00e5ffWoWSimLab - Account & Inventory Sync|r")

local subtitle = exportFrame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
subtitle:SetPoint("TOP", title, "BOTTOM", 0, -4)
subtitle:SetText("|cffffd100Press Ctrl+C to copy JSON, OR type /reload to save WoWSimLab.lua for Drag & Drop!|r")

local scroll = CreateFrame("ScrollFrame", "WoWSimLabExportScroll", exportFrame, "UIPanelScrollFrameTemplate")
scroll:SetPoint("TOPLEFT", exportFrame, "TOPLEFT", 18, -50)
scroll:SetPoint("BOTTOMRIGHT", exportFrame, "BOTTOMRIGHT", -36, 44)

local editBox = CreateFrame("EditBox", "WoWSimLabExportEditBox", scroll)
editBox:SetMultiLine(true)
editBox:SetFontObject(GameFontHighlightSmall)
editBox:SetWidth(475)
scroll:SetScrollChild(editBox)

editBox:SetScript("OnEscapePressed", function() exportFrame:Hide() end)

local closeBtn = CreateFrame("Button", nil, exportFrame, "UIPanelButtonTemplate")
closeBtn:SetSize(110, 24)
closeBtn:SetPoint("BOTTOM", exportFrame, "BOTTOM", 0, 12)
closeBtn:SetText("Close (Esc)")
closeBtn:SetScript("OnClick", function() exportFrame:Hide() end)

function WoWSimLab:ShowExportPopup(snapshotTable)
    local snap = snapshotTable or self:CaptureCharacterSnapshot()
    local jsonStr = TableToJson(snap)
    editBox:SetText(jsonStr)
    exportFrame:Show()
    editBox:SetFocus()
    editBox:HighlightText()
end
