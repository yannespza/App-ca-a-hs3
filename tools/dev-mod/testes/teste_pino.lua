-- Teste 3: tirar o marcador e zerar o pino rápido direto
local nav = FindFirstOf("NavigationPlayerStateComponent")
if not (nav and nav:IsValid()) then return "sem nav" end
local function h() local q = nav.QuickWaypoint; return tostring(q.Hash) .. "@" .. string.format("%.0f", q.Transform.Translation.X) end
local r = "inicio=" .. h()
local q = nav.QuickWaypoint
local ok1, e1 = pcall(function() nav:RemoveInWorldMarker(q) end)
r = r .. " | marcador " .. tostring(ok1) .. " " .. tostring(e1)
local ok2, e2 = pcall(function() nav:NavigationActorRemoved(q) end)
r = r .. " | removido " .. tostring(ok2) .. " " .. tostring(e2) .. " -> " .. h()
local ok3, e3 = pcall(function()
    nav.QuickWaypoint.Hash = -1
    nav.QuickWaypoint.Transform.Translation.X = 0
    nav.QuickWaypoint.Transform.Translation.Y = 0
    nav.QuickWaypoint.Transform.Translation.Z = 0
end)
r = r .. " | zerar " .. tostring(ok3) .. " " .. tostring(e3) .. " -> " .. h()
local ok4, e4 = pcall(function() nav:OnRep_QuickWaypoint() end)
return r .. " | onrep " .. tostring(ok4) .. " " .. tostring(e4) .. " -> " .. h()
