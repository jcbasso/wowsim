-- WoWSimLab: Coords.lua
-- Database of authentic Classic Target Dummies and test locations
WoWSimLab = WoWSimLab or {}

WoWSimLab.DUMMY_LOCATIONS = {
    -- Horde Capitals
    {
        name = "Orgrimmar Target Dummies",
        zone = "Orgrimmar",
        mapID = 1454, -- Orgrimmar
        fallbackMapIDs = { 85 },
        x = 0.762,
        y = 0.344,
        faction = "Horde",
        targetName = "Target Dummy"
    },
    {
        name = "Thunder Bluff Hunter Rise Dummies",
        zone = "Thunder Bluff",
        mapID = 1456,
        fallbackMapIDs = { 88 },
        x = 0.602,
        y = 0.815,
        faction = "Horde",
        targetName = "Target Dummy"
    },
    {
        name = "Undercity War Quarter Dummies",
        zone = "Undercity",
        mapID = 1458,
        fallbackMapIDs = { 90 },
        x = 0.621,
        y = 0.358,
        faction = "Horde",
        targetName = "Target Dummy"
    },

    -- Alliance Capitals
    {
        name = "Ironforge Military Ward Dummies",
        zone = "Ironforge",
        mapID = 1455,
        fallbackMapIDs = { 87 },
        x = 0.701,
        y = 0.880,
        faction = "Alliance",
        targetName = "Target Dummy"
    },
    {
        name = "Stormwind Command Center Dummies",
        zone = "Stormwind City",
        mapID = 1453,
        fallbackMapIDs = { 84 },
        x = 0.784,
        y = 0.698,
        faction = "Alliance",
        targetName = "Target Dummy"
    },
    {
        name = "Darnassus Warrior's Terrace Dummies",
        zone = "Darnassus",
        mapID = 1457,
        fallbackMapIDs = { 89 },
        x = 0.638,
        y = 0.142,
        faction = "Alliance",
        targetName = "Target Dummy"
    }
}

-- Returns the best matching dummy location for the player's faction and proximity
function WoWSimLab:GetNearestDummy()
    local playerFaction, _ = UnitFactionGroup("player")
    local currentMap = C_Map.GetBestMapForUnit("player")
    local playerPos = currentMap and C_Map.GetPlayerMapPosition(currentMap, "player")

    local bestLocation = nil
    local shortestDist = 9999999

    for _, loc in ipairs(self.DUMMY_LOCATIONS) do
        if loc.faction == playerFaction or not playerFaction then
            -- Check if player is on the same map
            local isSameMap = (currentMap == loc.mapID)
            if not isSameMap and loc.fallbackMapIDs then
                for _, fbId in ipairs(loc.fallbackMapIDs) do
                    if fbId == currentMap then isSameMap = true break end
                end
            end

            if isSameMap and playerPos then
                local dx = (loc.x - playerPos.x) * 1000 -- Approximate local yards
                local dy = (loc.y - playerPos.y) * 1000
                local dist = math.sqrt(dx * dx + dy * dy)
                if dist < shortestDist then
                    shortestDist = dist
                    bestLocation = loc
                    bestLocation.distanceYards = dist
                end
            elseif not bestLocation and (loc.faction == playerFaction) then
                bestLocation = loc
                bestLocation.distanceYards = 1000
            end
        end
    end

    return bestLocation or self.DUMMY_LOCATIONS[1]
end
