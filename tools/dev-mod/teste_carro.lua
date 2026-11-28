-- Teste: traz o veículo atual para 8 m ao lado do jogador (Server_TeleportSpawnedVehicle).
local pc = FindFirstOf("HS3PlayerController")
local p = pc.Pawn:K2_GetActorLocation()
local comp = FindFirstOf("HS3PlayerStateComponent_Vehicle")
if not comp then return "sem componente de veículo" end
local antes = "?"
pcall(function() local v = FindFirstOf("HS3WheeledVehiclePawn"); local l = v:K2_GetActorLocation(); antes = string.format("%.0f %.0f %.0f", l.X, l.Y, l.Z) end)
local ok, e = pcall(function()
    comp:Server_TeleportSpawnedVehicle({ Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = p.X + 800, Y = p.Y, Z = p.Z + 100 }, Scale3D = { X = 1, Y = 1, Z = 1 } })
end)
local depois = "?"
pcall(function() local v = FindFirstOf("HS3WheeledVehiclePawn"); local l = v:K2_GetActorLocation(); depois = string.format("%.0f %.0f %.0f", l.X, l.Y, l.Z) end)
return string.format("ok=%s %s | carro antes=%s depois=%s | jogador %.0f %.0f %.0f", tostring(ok), tostring(e or ""), antes, depois, p.X, p.Y, p.Z)
