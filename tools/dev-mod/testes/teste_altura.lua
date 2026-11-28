-- Teste: o jogo acerta a altura do pino posto com z=0? (põe um pino 150 m ao norte, lê, e não tira)
local pc = FindFirstOf("HS3PlayerController")
local p = pc.Pawn:K2_GetActorLocation()
local nav = FindFirstOf("NavigationPlayerStateComponent")
local id = { PrimaryAssetType = { Name = FName("NavigationIconData") }, PrimaryAssetName = FName("DA_QuickWaypoint_MapIconData") }
nav:Server_AddQuickWaypoint(id, { Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = p.X, Y = p.Y + 15000, Z = 0 }, Scale3D = { X = 1, Y = 1, Z = 1 } })
local t = nav.QuickWaypoint.Transform.Translation
local r = string.format("jogador z=%.0f | pino z depois=%.0f hash=%s", p.Z, t.Z, tostring(nav.QuickWaypoint.Hash))
-- tentativa de altura do chão por traçado (só leitura)
pcall(function()
    local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
    local hit = {}
    local ok = KSL:LineTraceSingle(pc.Pawn, { X = p.X, Y = p.Y + 15000, Z = 200000 }, { X = p.X, Y = p.Y + 15000, Z = -200000 }, 0, false, {}, 0, hit, true, { R = 0, G = 0, B = 0, A = 0 }, { R = 0, G = 0, B = 0, A = 0 }, 0)
    r = r .. " | trace=" .. tostring(ok) .. " z=" .. tostring(hit.Location and hit.Location.Z or hit.ImpactPoint and hit.ImpactPoint.Z)
end)
return r
