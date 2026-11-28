-- Sonda (só leitura): animais alvejados (vivos ou mortos), rastro de sangue e estado de ferido.
local L = {}
local function p(s) L[#L + 1] = s end
local function tg(t) local ok, r = pcall(function() return t.TagName:ToString() end); return ok and r or "?" end
local pos
pcall(function()
    local t = FindFirstOf("PlayerController").Pawn:K2_GetActorLocation(); pos = t
    p(string.format("EU %.0f %.0f %.0f", t.X, t.Y, t.Z))
end)
local mortos = {}
pcall(function()
    FindFirstOf("HS3DeadAnimalMapIconManager").DeadAnimalWidgets:ForEach(function(k) mortos[k:get()] = true end)
end)
local comTiro = {}
pcall(function()
    FindFirstOf("CreatureShotSaveChunk").CreatureShotMap:ForEach(function(k, v)
        local nivel = "?"
        pcall(function() nivel = k:get().PrimaryAssetName:ToString() end)
        local lista = v:get().InnerMap
        p(string.format("NIVEL %s criaturas_com_tiro=%d", nivel, #lista))
        for j = 1, math.min(#lista, 40) do
            pcall(function()
                local c = lista[j]
                local el = c.Elements
                comTiro[c.CreatureId] = #el
                local linha = string.format("  TIRO id=%d tiros=%d morto_no_mapa=%s", c.CreatureId, #el, tostring(mortos[c.CreatureId] == true))
                pcall(function()
                    local s = el[#el]
                    linha = linha .. " parte=" .. s.ComponentName:ToString() .. " torre=" .. tostring(s.bWasShotFromHuntingStand)
                        .. " estado=" .. tostring(s.AnimalState)
                    local h = s.SingleHits[1]
                    linha = linha .. " hora=" .. tostring(h.TimeOfShot.Ticks)
                    local secs = h.PenetrationResolution.ExitPropertiesPerSection
                    local org = {}
                    for q = 1, math.min(secs:GetArrayNum(), 12) do org[#org + 1] = tg(secs[q].OrganType) end
                    linha = linha .. " orgaos=" .. table.concat(org, "|")
                    local o = s.ProjectileOrigin
                    linha = linha .. string.format(" origem=%.0f,%.0f", o.X, o.Y)
                end)
                p(linha)
            end)
        end
    end)
end)
-- animais carregados perto (até ~750 m)
pcall(function()
    local lib = StaticFindObject("/Script/HS3AnimalsRuntime.Default__CreatureUtilsFunctionLibrary")
    local n = 0
    for _, a in ipairs(FindAllOf("AnimalCharacter") or {}) do
        pcall(function()
            local id = a.EcoSimCreatureId
            local t = a:K2_GetActorLocation()
            local d = pos and math.sqrt((t.X - pos.X) ^ 2 + (t.Y - pos.Y) ^ 2) / 100 or -1
            local vivo, ferido = "?", "?"
            pcall(function() vivo = tostring(lib:IsCreatureAlive(a)) end)
            pcall(function()
                local hc = a:GetComponentByClass(StaticFindObject("/Script/HS3AnimalsRuntime.AnimalHitAnimHandlerComponent"))
                ferido = tostring(hc:IsInjured())
            end)
            if comTiro[id] or ferido == "true" or n < 6 then
                p(string.format("ANIMAL id=%d %s dist=%.0fm vivo=%s ferido=%s tiros=%s pos=%.0f,%.0f", id, tg(a.SpeciesTag), d, vivo, ferido,
                    tostring(comTiro[id]), t.X, t.Y))
                n = n + 1
            end
        end)
    end
end)
-- rastros de sangue no chão
pcall(function()
    local lista = FindAllOf("HS3AnimalBloodTrail") or {}
    p("SANGUE " .. #lista)
    for i, b in ipairs(lista) do
        if i > 15 then break end
        pcall(function()
            local t = b:K2_GetActorLocation()
            p(string.format("  SANGUE id=%d %s orgao=%s pos=%.0f,%.0f criado=%s", b.EcoSimCreatureId, tg(b.AnimalTag), tg(b.OrganHitCache), t.X, t.Y,
                tostring(b.TimeOfCreation.Ticks)))
        end)
    end
end)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_ferido.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
