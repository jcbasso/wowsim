-- WoWSimLab: Arrow.lua
-- RestedXP/TomTom style directional navigation arrow
WoWSimLab = WoWSimLab or {}

local arrowFrame = CreateFrame("Frame", "WoWSimLabArrowFrame", UIParent)
arrowFrame:SetSize(64, 64)
arrowFrame:SetPoint("TOP", UIParent, "TOP", 0, -140)
arrowFrame:SetMovable(true)
arrowFrame:EnableMouse(true)
arrowFrame:RegisterForDrag("LeftButton")
arrowFrame:SetScript("OnDragStart", arrowFrame.StartMoving)
arrowFrame:SetScript("OnDragStop", arrowFrame.StopMovingOrSizing)
arrowFrame:Hide()

-- Texture for the 3D-styled arrow
local arrowTexture = arrowFrame:CreateTexture(nil, "OVERLAY")
arrowTexture:SetSize(48, 48)
arrowTexture:SetPoint("CENTER", arrowFrame, "CENTER", 0, 8)
arrowTexture:SetTexture("Interface\\Minimap\\ROTATING-MINIMAPARROW")

-- Distance text label
local textLabel = arrowFrame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
textLabel:SetPoint("TOP", arrowTexture, "BOTTOM", 0, -2)
textLabel:SetText("Target Dummy")

local targetLoc = nil

function WoWSimLab:ShowArrow(location)
    targetLoc = location or self:GetNearestDummy()
    arrowFrame:Show()
end

function WoWSimLab:HideArrow()
    arrowFrame:Hide()
end

local throttle = 0
arrowFrame:SetScript("OnUpdate", function(self, elapsed)
    throttle = throttle + elapsed
    if throttle < 0.04 then return end
    throttle = 0

    if not targetLoc then return end

    local currentMap = C_Map.GetBestMapForUnit("player")
    if not currentMap then
        textLabel:SetText(targetLoc.name)
        return
    end

    local playerPos = C_Map.GetPlayerMapPosition(currentMap, "player")
    local facing = GetPlayerFacing()

    if not playerPos or not facing then
        textLabel:SetText(targetLoc.name)
        return
    end

    -- If player is on a different map, display zone guidance
    if currentMap ~= targetLoc.mapID then
        local isFb = false
        if targetLoc.fallbackMapIDs then
            for _, id in ipairs(targetLoc.fallbackMapIDs) do
                if id == currentMap then isFb = true break end
            end
        end
        if not isFb then
            textLabel:SetText("|cffffcc00Go to " .. targetLoc.zone .. "|r")
            arrowTexture:SetRotation(0)
            arrowTexture:SetVertexColor(1, 0.8, 0.2)
            return
        end
    end

    local dx = targetLoc.x - playerPos.x
    local dy = targetLoc.y - playerPos.y

    -- Distance estimation in yards
    local yards = math.sqrt(dx * dx + dy * dy) * 1000

    -- In-range check (<= 5 yds is standard melee combat range)
    if yards <= 6.0 then
        arrowTexture:SetVertexColor(0.2, 1.0, 0.2) -- Green
        textLabel:SetText("|cff33ff33[OK] In Position (Ready)|r")
        arrowTexture:SetRotation(0)
        return
    end

    -- Angle calculation (Cartesian coordinates to map orientation)
    local angle = math.atan2(-dx, dy)
    local relAngle = angle - facing

    arrowTexture:SetRotation(relAngle)

    if yards > 100 then
        arrowTexture:SetVertexColor(1.0, 0.3, 0.2) -- Red (far)
    elseif yards > 30 then
        arrowTexture:SetVertexColor(1.0, 0.8, 0.2) -- Yellow
    else
        arrowTexture:SetVertexColor(0.2, 0.8, 1.0) -- Blue/Cyan (close)
    end

    textLabel:SetText(string.format("%s\n|cffffffff%d yds|r", targetLoc.name, math.floor(yards)))
end)

WoWSimLab.ArrowFrame = arrowFrame
