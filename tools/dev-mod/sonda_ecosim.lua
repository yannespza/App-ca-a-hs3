-- Sonda (só leitura): o EcoSim expõe animais no mapa todo ou só perto do jogador?
local L = {}
local function p(s) L[#L + 1] = s end
local px, py = 0, 0
pcall(function()
    local pc = FindFirstOf("PlayerController")
    local t = pc.Pawn:K2_GetActorLocation()
    px, py = t.X, t.Y
    p(string.format("JOGADOR %.0f %.0f", px, py))
end)
local function dist(x, y) return math.sqrt((x - px) ^ 2 + (y - py) ^ 2) / 100 end
local function contar(classe)
    local ok, lista = pcall(FindAllOf, classe)
    lista = (ok and lista) or {}
    local maxd, n = 0, 0
    for _, a in ipairs(lista) do
        pcall(function()
            local o = a.GetOwner and a:GetOwner() or a
            local t = o:K2_GetActorLocation()
            local d = dist(t.X, t.Y)
            n = n + 1
            if d > maxd then maxd = d end
        end)
    end
    p(string.format("%s total=%d comPos=%d maisLonge=%.0fm", classe, #lista, n, maxd))
end
for _, c in ipairs({ "AnimalCharacter", "AnimalInterfaceComponent", "EcoSimAnimalComponent",
    "EcoSimImposterInterfaceComponent", "EcoSimStats_AnimalComponent", "AnimalCosmeticsComponent" }) do
    contar(c)
end
pcall(function()
    local g = FindFirstOf("EcoSimGameStateComponent")
    p("GAMESTATE_COMP " .. tostring(g and g:IsValid()))
    local m = g.m_Manager
    p("MANAGER " .. tostring(m and m:IsValid() and m:GetFullName()))
    pcall(function() p("REMOTEVIEWER " .. tostring(m:RemoteViewerIsEnabled())) end)
end)
pcall(function()
    local im = FindFirstOf("EcoSimImposterGameStateComponent")
    p("IMPOSTER " .. tostring(im and im:IsValid()))
end)
pcall(function()
    local d = FindFirstOf("EcoSimDataComponent")
    p("DATA_COMP " .. tostring(d and d:IsValid()) .. " especies=" .. tostring(d.PerSpeciesData:GetArrayNum()))
end)
pcall(function()
    local m = FindFirstOf("HS3DeadAnimalMapIconManager")
    local n, maxd = 0, 0
    m.DeadAnimalWidgets:ForEach(function(k, v)
        n = n + 1
        local t = v:get().Transform.Translation
        local d = dist(t.X, t.Y)
        if d > maxd then maxd = d end
    end)
    p(string.format("MORTOS %d maisLonge=%.0fm", n, maxd))
end)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_ecosim.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
