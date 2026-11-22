-- WoWSimLab: WoWSimLab.lua
-- Main controller, GUI window, pre-flight guardrails, and logging engine
WoWSimLab = WoWSimLab or {}

-- Slash Commands registered at the very top so they are ALWAYS available
SLASH_WOWSIMLAB1 = "/simlab"
SLASH_WOWSIMLAB2 = "/wowsim"
SlashCmdList["WOWSIMLAB"] = function(msg)
    local cmd = (msg or ""):lower():match("^%s*(%S+)")
    if cmd == "reset" or cmd == "clear" then
        WoWSimLab:ResetTest()
    elseif cmd == "sync" or cmd == "export" then
        local ok, snapOrErr = pcall(function() return WoWSimLab:CaptureCharacterSnapshot() end)
        if not ok then
            print("|cffff4444[WoWSimLab] Sync error:|r " .. tostring(snapOrErr))
            return
        end
        local snap = snapOrErr
        print(string.format("|cff00e5ff[WoWSimLab]|r Synced %s (Lvl %d): %d Bag items, %d Bank items, %d Professions, %d Owned total. Type |cffffd100/reload|r to save WoWSimLab.lua for Drag & Drop, or press Ctrl+C!", snap.name or "Character", snap.level or 1, #(snap.bags or {}), #(snap.bank or {}), #(snap.professions or {}), #(snap.ownedItems or {})))
        WoWSimLab:ShowExportPopup(snap)
    else
        WoWSimLab:ToggleUI()
    end
end

SLASH_SIMSYNC1 = "/simsync"
SlashCmdList["SIMSYNC"] = function()
    local ok, snapOrErr = pcall(function() return WoWSimLab:CaptureCharacterSnapshot() end)
    if not ok then
        print("|cffff4444[WoWSimLab] Sync error:|r " .. tostring(snapOrErr))
        return
    end
    local snap = snapOrErr
    print(string.format("|cff00e5ff[WoWSimLab]|r Synced %s (Lvl %d): %d Bag items, %d Bank items, %d Owned items total. Type |cffffd100/reload|r to save WoWSimLab.lua for Drag & Drop, or press Ctrl+C!", snap.name or "Character", snap.level or 1, #(snap.bags or {}), #(snap.bank or {}), #(snap.ownedItems or {})))
    WoWSimLab:ShowExportPopup(snap)
end

local isTesting = false
local testStartTime = 0
local testStartClock = 0
local testSampleCount = 0
local currentSessionId = nil
local activePhase = "phase1_white_hits"
local lastSnapshot = nil
local activeTargetGUID = nil

-- Testing phases (Works on ANY hostile mob, dungeon boss, or duel partner)
local TEST_PHASES = {
    {
        key = "phase1_white_hits",
        title = "1. Baseline White Swings",
        desc = "Auto-attacks only. Verifies weapon base damage roll, speed, and hit table.",
        targetSamples = 100,
        maxDuration = 180
    },
    {
        key = "phase2_stat_scaling",
        title = "2. Equipped Gear Swings",
        desc = "Auto-attacks with full gear. Verifies Attack Power scaling & Crit conversion.",
        targetSamples = 100,
        maxDuration = 180
    },
    {
        key = "phase3_spell_damage",
        title = "3. Spell Damage & SP",
        desc = "Cast selected spell repeatedly. Verifies base rank spell range and SP coefficient.",
        targetSamples = 25,
        maxDuration = 120
    },
    {
        key = "phase4_full_rotation",
        title = "4. Full APL Rotation",
        desc = "Full rotation combat. Verifies composite sustained DPS and ability breakdown.",
        targetSamples = 150,
        maxDuration = 180
    }
}

-- Main Window Frame
local mainFrame = CreateFrame("Frame", "WoWSimLabMainFrame", UIParent, "BackdropTemplate")
mainFrame:SetSize(420, 500)
mainFrame:SetPoint("CENTER", UIParent, "CENTER", 0, 40)
mainFrame:SetMovable(true)
mainFrame:EnableMouse(true)
mainFrame:RegisterForDrag("LeftButton")
mainFrame:SetScript("OnDragStart", mainFrame.StartMoving)
mainFrame:SetScript("OnDragStop", mainFrame.StopMovingOrSizing)
mainFrame:SetBackdrop({
    bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background-Dark",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    tile = true, tileSize = 16, edgeSize = 16,
    insets = { left = 4, right = 4, top = 4, bottom = 4 }
})
mainFrame:Hide()

function WoWSimLab:ToggleUI()
    if mainFrame:IsShown() then
        mainFrame:Hide()
    else
        mainFrame:Show()
    end
end

-- Header
local titleText = mainFrame:CreateFontString(nil, "OVERLAY", "GameFontHighlightLarge")
titleText:SetPoint("TOPLEFT", mainFrame, "TOPLEFT", 16, -14)
titleText:SetText("|cff00e5ffWoWSimLab|r |cffffd100[Sim Validator]|r")

-- Close Button (explicit OnClick handler prevents Blizzard UI taint bug)
local closeBtn = CreateFrame("Button", nil, mainFrame, "UIPanelCloseButton")
closeBtn:SetPoint("TOPRIGHT", mainFrame, "TOPRIGHT", -4, -4)
closeBtn:SetScript("OnClick", function()
    mainFrame:Hide()
end)

-- Phase Info Display Box
local phaseBox = CreateFrame("Frame", nil, mainFrame, "BackdropTemplate")
phaseBox:SetSize(388, 70)
phaseBox:SetPoint("TOP", mainFrame, "TOP", 0, -42)
phaseBox:SetBackdrop({
    bgFile = "Interface\\ChatFrame\\ChatFrameBackground",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    tile = false, edgeSize = 12,
    insets = { left = 3, right = 3, top = 3, bottom = 3 }
})
phaseBox:SetBackdropColor(0.05, 0.08, 0.12, 0.85)
phaseBox:SetBackdropBorderColor(0.2, 0.4, 0.6, 0.8)

local phaseTitle = phaseBox:CreateFontString(nil, "OVERLAY", "GameFontHighlightMedium")
phaseTitle:SetPoint("TOPLEFT", phaseBox, "TOPLEFT", 10, -8)
phaseTitle:SetText(TEST_PHASES[1].title)

local phaseDesc = phaseBox:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
phaseDesc:SetPoint("TOPLEFT", phaseTitle, "BOTTOMLEFT", 0, -4)
phaseDesc:SetPoint("RIGHT", phaseBox, "RIGHT", -10, 0)
phaseDesc:SetJustifyH("LEFT")
phaseDesc:SetText(TEST_PHASES[1].desc)

-- Live Target & Pre-Flight Card
local checkCard = CreateFrame("Frame", nil, mainFrame, "BackdropTemplate")
checkCard:SetSize(388, 105)
checkCard:SetPoint("TOP", phaseBox, "BOTTOM", 0, -8)
checkCard:SetBackdrop({
    bgFile = "Interface\\ChatFrame\\ChatFrameBackground",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    tile = false, edgeSize = 12,
    insets = { left = 3, right = 3, top = 3, bottom = 3 }
})
checkCard:SetBackdropColor(0.04, 0.05, 0.08, 0.9)
checkCard:SetBackdropBorderColor(0.3, 0.3, 0.3, 0.6)

local checkTitle = checkCard:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
checkTitle:SetPoint("TOPLEFT", checkCard, "TOPLEFT", 10, -6)
checkTitle:SetText("|cffa0aec0TARGET & PRE-FLIGHT VALIDATION|r")

local targetCheck = checkCard:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
targetCheck:SetPoint("TOPLEFT", checkTitle, "BOTTOMLEFT", 0, -5)
targetCheck:SetText("- Target: Select any mob or duel partner")

local targetDetails = checkCard:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
targetDetails:SetPoint("TOPLEFT", targetCheck, "BOTTOMLEFT", 12, -2)
targetDetails:SetText("|cffa0aec0No target selected.|r")

local gearCheck = checkCard:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
gearCheck:SetPoint("TOPLEFT", targetDetails, "BOTTOMLEFT", -12, -4)
gearCheck:SetText("- Equipment: Checking...")

local buffCheck = checkCard:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
buffCheck:SetPoint("TOPLEFT", gearCheck, "BOTTOMLEFT", 0, -3)
buffCheck:SetText("- Buffs: Checking...")

-- Live Test Meter
local meterCard = CreateFrame("Frame", nil, mainFrame, "BackdropTemplate")
meterCard:SetSize(388, 80)
meterCard:SetPoint("TOP", checkCard, "BOTTOM", 0, -8)
meterCard:SetBackdrop({
    bgFile = "Interface\\ChatFrame\\ChatFrameBackground",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    tile = false, edgeSize = 12,
    insets = { left = 3, right = 3, top = 3, bottom = 3 }
})
meterCard:SetBackdropColor(0.02, 0.03, 0.05, 0.95)
meterCard:SetBackdropBorderColor(0.15, 0.6, 0.3, 0.8)

local meterTitle = meterCard:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
meterTitle:SetPoint("TOPLEFT", meterCard, "TOPLEFT", 10, -6)
meterTitle:SetText("|cff2ecc71LIVE LAB RECORDER & COUNTER|r")

local sampleText = meterCard:CreateFontString(nil, "OVERLAY", "GameFontHighlightLarge")
sampleText:SetPoint("TOPLEFT", meterTitle, "BOTTOMLEFT", 0, -4)
sampleText:SetText("Samples: |cffffd1000 / 100|r")

local timerText = meterCard:CreateFontString(nil, "OVERLAY", "GameFontHighlightMedium")
timerText:SetPoint("TOPRIGHT", meterCard, "TOPRIGHT", -12, -26)
timerText:SetText("Time: |cffffffff00:00|r")

local lastActionText = meterCard:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
lastActionText:SetPoint("BOTTOMLEFT", meterCard, "BOTTOMLEFT", 10, 8)
lastActionText:SetText("Status: |cffa0aec0Standby. Target a mob and click Start.|r")

-- ACTION BUTTON 1: MARK TARGET WITH SKULL
local markBtn = CreateFrame("Button", nil, mainFrame, "UIPanelButtonTemplate")
markBtn:SetSize(188, 28)
markBtn:SetPoint("TOPLEFT", meterCard, "BOTTOMLEFT", 0, -10)
markBtn:SetText("Mark Target (Skull)")
markBtn:SetScript("OnClick", function()
    if UnitExists("target") and SetRaidTarget then
        pcall(SetRaidTarget, "target", 8)
    end
end)

-- ACTION BUTTON 2: SWITCH TEST PHASE
local phaseBtn = CreateFrame("Button", nil, mainFrame, "UIPanelButtonTemplate")
phaseBtn:SetSize(188, 28)
phaseBtn:SetPoint("TOPRIGHT", meterCard, "BOTTOMRIGHT", 0, -10)
phaseBtn:SetText("Next Test Phase >")
local currentPhaseIdx = 1
phaseBtn:SetScript("OnClick", function()
    currentPhaseIdx = (currentPhaseIdx % #TEST_PHASES) + 1
    local p = TEST_PHASES[currentPhaseIdx]
    activePhase = p.key
    phaseTitle:SetText(p.title)
    phaseDesc:SetText(p.desc)
    sampleText:SetText(string.format("Samples: |cffffd1000 / %d|r", p.targetSamples))
end)

-- ACTION BUTTON 3: STRIP ARMOR (FOR NAKED WEAPON BASELINE)
local stripBtn = CreateFrame("Button", nil, mainFrame, "UIPanelButtonTemplate")
stripBtn:SetSize(188, 28)
stripBtn:SetPoint("TOPLEFT", markBtn, "BOTTOMLEFT", 0, -6)
stripBtn:SetText("Strip Armor (Naked)")
stripBtn:SetScript("OnClick", function()
    WoWSimLab:StripArmorForTest()
end)

-- ACTION BUTTON 4: EXPORT / SYNC ACCOUNT & INVENTORY (Ctrl+C POPUP)
local exportBtn = CreateFrame("Button", nil, mainFrame, "UIPanelButtonTemplate")
exportBtn:SetSize(188, 28)
exportBtn:SetPoint("TOPRIGHT", phaseBtn, "BOTTOMRIGHT", 0, -6)
exportBtn:SetText("Sync Account & Bags")
exportBtn:SetScript("OnClick", function()
    local snap = lastSnapshot or WoWSimLab:CaptureCharacterSnapshot()
    WoWSimLab:ShowExportPopup(snap)
end)

-- ACTION BUTTON 5: START / STOP MASTER TEST BUTTON
local startBtn = CreateFrame("Button", nil, mainFrame, "UIPanelButtonTemplate")
startBtn:SetSize(280, 36)
startBtn:SetPoint("BOTTOMLEFT", mainFrame, "BOTTOMLEFT", 16, 16)
startBtn:SetText("|cff33ff33>> START TEST & LOGGING|r")

-- ACTION BUTTON 6: RESET / CLEAR TEST BUTTON
local resetBtn = CreateFrame("Button", nil, mainFrame, "UIPanelButtonTemplate")
resetBtn:SetSize(102, 36)
resetBtn:SetPoint("BOTTOMRIGHT", mainFrame, "BOTTOMRIGHT", -16, 16)
resetBtn:SetText("|cffffcc00Reset|r")
resetBtn:SetScript("OnClick", function()
    WoWSimLab:ResetTest()
end)

-- Reset / Clear Logic
function WoWSimLab:ResetTest()
    isTesting = false
    if LoggingCombat then LoggingCombat(false) end
    testStartTime = 0
    testStartClock = 0
    testSampleCount = 0
    currentSessionId = nil
    activeTargetGUID = nil
    lastSnapshot = nil

    local targetMax = TEST_PHASES[currentPhaseIdx] and TEST_PHASES[currentPhaseIdx].targetSamples or 100
    sampleText:SetText(string.format("Samples: |cffffd1000 / %d|r", targetMax))
    timerText:SetText("Time: |cffffffff00:00|r")
    lastActionText:SetText("Status: |cffa0aec0Test reset. Select target & click Start.|r")
    startBtn:SetText("|cff33ff33>> START TEST & LOGGING|r")
    resetBtn:SetText("|cffffcc00Reset|r")
    print("|cff00e5ff[WoWSimLab]|r Test session cleared. Ready for a new target.")
end

-- Start/Stop Test Logic
function WoWSimLab:StartTest()
    if isTesting then return end

    if not UnitExists("target") then
        print("|cffff4444[WoWSimLab]|r Please target an attackable mob or duel partner first!")
        return
    end

    local playerClass = select(2, UnitClass("player")) or "class"
    currentSessionId = string.format("simlab_%s_%s_%d",
        playerClass:lower(),
        activePhase,
        time()
    )

    isTesting = true
    testStartTime = GetTime()
    testStartClock = time()
    testSampleCount = 0
    activeTargetGUID = UnitGUID("target")

    if LoggingCombat then LoggingCombat(true) end
    if PlaySound and SOUNDKIT and SOUNDKIT.READY_CHECK then
        PlaySound(SOUNDKIT.READY_CHECK)
    end
    startBtn:SetText("|cffff4444[X] STOP & EXPORT|r")
    resetBtn:SetText("|cffff8800Cancel|r")
    lastActionText:SetText("|cff33ff33[*] Recording active... Attack target.|r")
    print("|cff00e5ff[WoWSimLab]|r Combat logging started. Target: " .. (UnitName("target") or "Unknown"))
end

function WoWSimLab:StopTest(wasAborted, reason)
    if not isTesting then return end
    isTesting = false

    if LoggingCombat then LoggingCombat(false) end

    local duration = GetTime() - testStartTime
    local targetCreatureType = UnitCreatureType and UnitCreatureType("target") or "Unknown"
    local testMeta = {
        sessionId = currentSessionId,
        phase = activePhase,
        target = UnitName("target") or "Target",
        targetLevel = UnitLevel("target") or 60,
        targetCreatureType = targetCreatureType,
        targetGUID = activeTargetGUID,
        durationSeconds = math.floor(duration * 10) / 10,
        samplesRecorded = testSampleCount,
        status = wasAborted and "ABORTED" or "VALID_COMPLETED",
        abortReason = reason or nil
    }

    lastSnapshot = WoWSimLab:CaptureCharacterSnapshot(testMeta)

    -- Persist into SavedVariables
    WoWSimLabDB = WoWSimLabDB or { sessions = {} }
    WoWSimLabDB.sessions[currentSessionId] = lastSnapshot

    startBtn:SetText("|cff33ff33>> START TEST & LOGGING|r")
    resetBtn:SetText("|cffffcc00Reset|r")

    if wasAborted then
        if PlaySound and SOUNDKIT and SOUNDKIT.RAID_WARNING then
            PlaySound(SOUNDKIT.RAID_WARNING)
        end
        lastActionText:SetText("|cffff4444ABORTED: " .. (reason or "Target lost or changed") .. "|r")
        print("|cffff4444[WoWSimLab] Test aborted!|r " .. (reason or ""))
    else
        if PlaySound and SOUNDKIT and SOUNDKIT.UI_QUEST_COMPLETE then
            PlaySound(SOUNDKIT.UI_QUEST_COMPLETE)
        end
        lastActionText:SetText(string.format("|cff33ff33Complete! %d samples in %.1fs.|r", testSampleCount, duration))
        print(string.format("|cff00e5ff[WoWSimLab]|r Test complete (%d samples). Export popup ready.", testSampleCount))
        WoWSimLab:ShowExportPopup(lastSnapshot)
    end
end

startBtn:SetScript("OnClick", function()
    if isTesting then
        WoWSimLab:StopTest(false)
    else
        WoWSimLab:StartTest()
    end
end)

-- Continuous Live Monitor
local monitorThrottle = 0
mainFrame:SetScript("OnUpdate", function(self, elapsed)
    monitorThrottle = monitorThrottle + elapsed
    if monitorThrottle < 0.1 then return end
    monitorThrottle = 0

    -- 1. Target Details (Adapts to ANY target)
    if UnitExists("target") then
        local tName = UnitName("target")
        local tLvl = UnitLevel("target")
        local tType = (UnitCreatureType and UnitCreatureType("target")) or "Creature"
        local canAttack = UnitCanAttack("player", "target")

        if canAttack then
            targetCheck:SetText("- Target: |cff33ff33[OK] " .. tName .. "|r")
            targetDetails:SetText(string.format("|cffffd100Lvl %s %s - Attackable|r", tostring(tLvl), tType))
        else
            targetCheck:SetText("- Target: |cffffcc00" .. tName .. " (Friendly/Passive)|r")
            targetDetails:SetText("|cffffcc00Cannot attack this target (Friendly).|r")
        end
    else
        targetCheck:SetText("- Target: |cffff4444[X] No target selected|r")
        targetDetails:SetText("|cffa0aec0Target any hostile mob or duel partner.|r")
    end

    -- 2. Equipment Checklist
    local gearOk, gearMsg = WoWSimLab:ValidateGearForPhase(activePhase)
    if gearOk then
        gearCheck:SetText("- Gear: |cff33ff33[OK] " .. (gearMsg or "OK") .. "|r")
    else
        gearCheck:SetText("- Gear: |cffff4444[X] " .. (gearMsg or "Mismatch") .. "|r")
    end

    -- 3. Buff Checklist (Cleanliness)
    local buffCount = 0
    for i = 1, 40 do
        if UnitBuff and UnitBuff("player", i) then
            buffCount = buffCount + 1
        else
            break
        end
    end
    if buffCount == 0 then
        buffCheck:SetText("- Buffs: |cff33ff33[OK] Clean (0 active buffs)|r")
    else
        buffCheck:SetText(string.format("- Buffs: |cffffcc00%d active buffs (Verify)|r", buffCount))
    end

    -- 4. Timer update during active test
    if isTesting then
        local curDuration = GetTime() - testStartTime
        local mins = math.floor(curDuration / 60)
        local secs = math.floor(curDuration % 60)
        timerText:SetText(string.format("Time: |cffffffff%02d:%02d|r", mins, secs))

        -- Target died normally - finish test cleanly!
        if UnitExists("target") and UnitIsDead("target") then
            WoWSimLab:StopTest(false)
        end

        -- Auto-completion threshold
        local targetMax = TEST_PHASES[currentPhaseIdx] and TEST_PHASES[currentPhaseIdx].targetSamples or 100
        if testSampleCount >= targetMax or curDuration >= 180 then
            WoWSimLab:StopTest(false)
        end
    end
end)

-- Event Listener for Combat Log Hits, Real-Time Counters & Auto Account/Bank/Bag Sync
local eventFrame = CreateFrame("Frame")
eventFrame:RegisterEvent("ADDON_LOADED")
eventFrame:RegisterEvent("PLAYER_ENTERING_WORLD")
eventFrame:RegisterEvent("BANKFRAME_OPENED")
eventFrame:RegisterEvent("BANKFRAME_CLOSED")
eventFrame:RegisterEvent("PLAYERBANKSLOTS_CHANGED")
eventFrame:RegisterEvent("BAG_UPDATE")
eventFrame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
eventFrame:RegisterEvent("SKILL_LINES_CHANGED")
eventFrame:RegisterEvent("UPDATE_FACTION")
eventFrame:RegisterEvent("CHARACTER_POINTS_CHANGED")
eventFrame:RegisterEvent("PLAYER_LOGOUT")
eventFrame:RegisterEvent("UNIT_COMBAT")
eventFrame:RegisterEvent("COMBAT_LOG_EVENT_UNFILTERED")

local function RecordHitSample(amount, hitType)
    if not isTesting then return end
    testSampleCount = testSampleCount + 1
    local targetMax = TEST_PHASES[currentPhaseIdx] and TEST_PHASES[currentPhaseIdx].targetSamples or 100
    sampleText:SetText(string.format("Samples: |cffffd100%d / %d|r", testSampleCount, targetMax))
    lastActionText:SetText(string.format("Last Hit: |cffffffff%s|r [%s]", tostring(amount or ""), tostring(hitType or "Hit")))
end

local lastAutoSyncTime = 0
local function ThrottledAutoSync(forceNow)
    local now = GetTime and GetTime() or 0
    if not forceNow and (now - lastAutoSyncTime) < 1.5 then return end
    lastAutoSyncTime = now
    if WoWSimLab and WoWSimLab.CaptureCharacterSnapshot then
        pcall(function() WoWSimLab:CaptureCharacterSnapshot() end)
    end
end

eventFrame:SetScript("OnEvent", function(self, event, ...)
    if event == "ADDON_LOADED" then
        local addon = ...
        if addon == "WoWSimLab" then
            WoWSimLabDB = WoWSimLabDB or { sessions = {}, characters = {} }
            print("|cff00e5ff[WoWSimLab]|r Account Sync & Sim Validator loaded! Type |cffffd100/simsync|r to sync Equipped, Bags, Bank, Professions & Reps.")
        end
    elseif event == "PLAYER_ENTERING_WORLD" or event == "PLAYER_LOGOUT" then
        ThrottledAutoSync(true)
    elseif event == "BANKFRAME_OPENED" then
        WoWSimLab.isBankOpen = true
        ThrottledAutoSync(true)
        local charKey = (UnitName("player") or "Character") .. "-" .. (GetRealmName and GetRealmName() or "Forever")
        local snap = WoWSimLabDB and WoWSimLabDB.characters and WoWSimLabDB.characters[charKey]
        local bankCount = snap and snap.bank and #snap.bank or 0
        print(string.format("|cff00e5ff[WoWSimLab]|r Bank cached (%d items)! Type |cffffd100/reload|r or log out to write WoWSimLab.lua for Drag & Drop Sync.", bankCount))
    elseif event == "PLAYERBANKSLOTS_CHANGED" then
        if WoWSimLab.isBankOpen then
            ThrottledAutoSync(true)
        end
    elseif event == "BANKFRAME_CLOSED" then
        ThrottledAutoSync(true)
        WoWSimLab.isBankOpen = false
    elseif event == "BAG_UPDATE" or event == "PLAYER_EQUIPMENT_CHANGED" or event == "SKILL_LINES_CHANGED" or event == "UPDATE_FACTION" or event == "CHARACTER_POINTS_CHANGED" then
        ThrottledAutoSync(false)
    elseif event == "UNIT_COMBAT" and isTesting then
        local unit, action, indicator, amount, damageType = ...
        if unit == "target" then
            RecordHitSample(amount, action or "Hit")
        end
    elseif event == "COMBAT_LOG_EVENT_UNFILTERED" and isTesting then
        if not CombatLogGetCurrentEventInfo then return end
        local timestamp, subevent, hideCaster, sourceGUID, sourceName, sourceFlags, sourceRaidFlags, destGUID, destName, destFlags, destRaidFlags, arg12, arg13, arg14, arg15, arg16, arg17, arg18, arg19, arg20 = CombatLogGetCurrentEventInfo()

        if sourceGUID == UnitGUID("player") and (destGUID == activeTargetGUID or not activeTargetGUID) then
            if subevent == "SWING_DAMAGE" or subevent == "SPELL_DAMAGE" then
                local amount = (subevent == "SWING_DAMAGE") and arg12 or arg15
                local isCrit = (subevent == "SWING_DAMAGE") and arg18 or arg21
                RecordHitSample(amount or 0, isCrit and "CRIT" or "Hit")
            elseif subevent == "SWING_MISSED" or subevent == "SPELL_MISSED" then
                local missType = (subevent == "SWING_MISSED") and arg12 or arg15
                RecordHitSample(0, missType or "Miss")
            end
        end
    end
end)
