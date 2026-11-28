-- Sonda (só leitura): posição/estado do cão e salas de troféus (empalhados)
local L = {}
local function p(s) L[#L + 1] = s end
pcall(function()
    local lista = FindAllOf("HS3CompanionPawn") or {}
    p("CAES " .. #lista)
    for i, c in ipairs(lista) do
        if i > 3 then break end
        pcall(function()
            local t = c:K2_GetActorLocation()
            p(string.format("CAO %s pos=%.0f,%.0f,%.0f estado=%s raca=%s energia=%s", c:GetFullName():sub(1, 80), t.X, t.Y, t.Z,
                tostring(c.CompanionState), tostring(c.CompanionBreed.TagName:ToString()), tostring(c.CompanionEnergy)))
        end)
        pcall(function() p("CAO nome=" .. tostring(c:GetCompanionName():ToString())) end)
    end
end)
pcall(function()
    local ch = FindFirstOf("TaxidermyStandsSaveChunk")
    p("CHUNK " .. tostring(ch and ch:IsValid()))
    local n = 0
    ch.PerLevelStandsSavedData:ForEach(function(k, v)
        local arr = v:get().StandSavedData
        local nst = arr:GetArrayNum()
        local animais = 0
        for i = 1, math.min(nst, 60) do
            pcall(function() animais = animais + arr[i].AssignedAnimalsForSpots:GetArrayNum() end)
        end
        p(string.format("NIVEL %s estandes=%d animais=%d", k:get():ToString(), nst, animais))
        if nst > 0 then
            pcall(function()
                local s1 = arr[1]
                p("  ex: " .. s1.ActorName:ToString() .. " comp=" .. s1.SelectedCompositionAsset.PrimaryAssetName:ToString())
                local a = s1.AssignedAnimalsForSpots[1]
                if a then p("  animal id=" .. tostring(a.AnimalIdentity.Identifier) .. " nivel=" .. a.AnimalIdentity.AssociatedLevelAssetId.PrimaryAssetName:ToString() .. " slot=" .. a.SocketName:ToString()) end
            end)
        end
        n = n + 1
    end)
    p("NIVEIS " .. n)
end)
pcall(function()
    local st = FindAllOf("TaxidermyStandActor") or {}
    p("ESTANDES_NO_MUNDO " .. #st)
end)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_cao_trofeus.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
