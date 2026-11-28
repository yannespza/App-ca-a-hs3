-- Sonda (só leitura): em que estrutura de caça o caçador está (torre, esconderijo, plataforma).
-- Rodar com o caçador DENTRO de uma estrutura e depois fora, para comparar.
local L = {}
local function p(s) L[#L + 1] = s end
local pawn, pos
pcall(function()
    local pc = FindFirstOf("PlayerController")
    pawn = pc.Pawn
    pos = pawn:K2_GetActorLocation()
    p(string.format("PAWN %s pos=%.0f,%.0f,%.0f", pawn:GetFullName():sub(1, 90), pos.X, pos.Y, pos.Z))
end)
pcall(function()
    local d = FindFirstOf("HS3AttributeSet_Detection")
    p("NA_ESTRUTURA " .. tostring(d.InHuntingStructure.CurrentValue))
end)
pcall(function()
    local pai = pawn:GetAttachParentActor()
    p("PAI " .. tostring(pai and pai:IsValid() and pai:GetFullName() or "nenhum"))
end)
pcall(function()
    local c = pawn.RootComponent:GetAttachParent()
    p("PAI_COMP " .. tostring(c and c:IsValid() and c:GetFullName() or "nenhum"))
end)
pcall(function() p("MOVIMENTO " .. tostring(pawn.CharacterMovement.MovementMode)) end)
local classes = { "HS3HuntingStructure", "HuntingStructure", "HS3HuntingStand", "HuntingStand", "HS3HuntingStructureBase",
    "HuntingStructureActor", "HS3HuntingStructureActor", "HS3BlindActor", "HS3TreeStand", "HS3GroundBlind" }
for _, cls in ipairs(classes) do
    pcall(function()
        local lista = FindAllOf(cls)
        if not lista then return end
        local melhor, md = nil, 1e18
        for i, a in ipairs(lista) do
            if i > 400 then break end
            pcall(function()
                local t = a:K2_GetActorLocation()
                local dd = (t.X - pos.X) ^ 2 + (t.Y - pos.Y) ^ 2 + (t.Z - pos.Z) ^ 2
                if dd < md then md, melhor = dd, a end
            end)
        end
        p(string.format("CLASSE %s n=%d mais_perto=%s dist=%.0fcm", cls, #lista,
            melhor and melhor:GetFullName():sub(1, 120) or "-", math.sqrt(md)))
    end)
end
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_estrutura.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
