-- Sonda (só leitura): animais mortos que o jogo marca no mapa + peso dos animais vivos.
local L = {}
local function p(s) L[#L + 1] = s end
pcall(function()
    local m = FindFirstOf("HS3DeadAnimalMapIconManager")
    if not m then p("sem gerente de mortos"); return end
    local n = 0
    m.DeadAnimalWidgets:ForEach(function(k, v)
        n = n + 1
        local d = v:get()
        local t = d.Transform.Translation
        p(string.format("MORTO id=%s %.0f %.0f hash=%s", tostring(k:get()), t.X, t.Y, tostring(d.Hash)))
    end)
    p("MORTOS " .. n)
end)
pcall(function()
    local c = FindAllOf("AnimalCosmeticsComponent") or {}
    p("COSMETICOS " .. #c)
    for i, x in ipairs(c) do
        if i > 15 then break end
        pcall(function()
            local o = x:GetOwner()
            local ci = x.ReplicatedCosmeticInfo
            p(string.format("VIVO id=%s %s peso=%.1f idade=%s faixa=%s", tostring(o.EcoSimCreatureId), ci.AnimalTag.TagName:ToString(), ci.WeightG / 1000, tostring(ci.AgeDays), tostring(ci.AgeGroup)))
        end)
    end
end)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_mortos.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
