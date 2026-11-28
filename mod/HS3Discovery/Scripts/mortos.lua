-- Animais mortos que o jogo marca no mapa (HS3DeadAnimalMapIconManager) e se levaram tiro do jogador
-- (UCreatureShotSaveChunk.CreatureShotMap). Sem tiro = morte natural. Recarregado a cada uso; só leitura.
local M = {}

local function idsComTiro()
    local ids = {}
    pcall(function()
        FindFirstOf("CreatureShotSaveChunk").CreatureShotMap:ForEach(function(_, v)
            local lista = v:get().InnerMap
            for j = 1, #lista do ids[lista[j].CreatureId] = true end
        end)
    end)
    return ids
end

-- devolve a lista e uma assinatura (ids) para o main.lua só regravar quando mudar
function M.ler()
    local mortos, chaves = {}, {}
    pcall(function()
        FindFirstOf("HS3DeadAnimalMapIconManager").DeadAnimalWidgets:ForEach(function(k, v)
            local t = v:get().Transform.Translation
            mortos[#mortos + 1] = { id = k:get(), x = t.X, y = t.Y, z = t.Z }
            chaves[#chaves + 1] = tostring(k:get())
        end)
    end)
    table.sort(chaves)
    return mortos, table.concat(chaves, ",")
end

function M.completar(mortos)
    if #mortos == 0 then return mortos end
    local tiros = idsComTiro()
    local especie = {}
    pcall(function()
        for _, a in ipairs(FindAllOf("AnimalCharacter") or {}) do
            pcall(function() especie[a.EcoSimCreatureId] = a.SpeciesTag.TagName:ToString() end)
        end
    end)
    for _, m in ipairs(mortos) do m.tiro = tiros[m.id] == true; m.especie = especie[m.id] end
    return mortos
end

-- animais que levaram tiro do jogador neste mapa: vivos (feridos) ou mortos. Só leitura, listas pequenas.
-- nivel = trecho do nome do mapa (ex.: Colorado_BlockOut); mortosIds = ids que o jogo marca como mortos no mapa
function M.alvejados(nivel, mortosIds)
    local lista, chaves = {}, {}
    pcall(function()
        FindFirstOf("CreatureShotSaveChunk").CreatureShotMap:ForEach(function(k, v)
            local nome = ""
            pcall(function() nome = k:get().PrimaryAssetName:ToString() end)
            if nivel and not nome:find(nivel, 1, true) then return end
            local inner = v:get().InnerMap
            for j = 1, math.min(#inner, 60) do
                pcall(function()
                    local c = inner[j]
                    local el = c.Elements
                    local t = { id = c.CreatureId, tiros = #el, orgaos = {} }
                    local vistos = {}
                    for i = 1, math.min(#el, 4) do
                        pcall(function()
                            local s = el[i]
                            if i == #el or i == 4 then
                                t.torre = s.bWasShotFromHuntingStand
                                local o = s.ProjectileOrigin
                                t.origem = { x = o.X, y = o.Y }
                                t.hora = s.SingleHits[1].TimeOfShot.Ticks
                            end
                            local hits = s.SingleHits
                            for h = 1, math.min(hits:GetArrayNum(), 3) do
                                local secs = hits[h].PenetrationResolution.ExitPropertiesPerSection
                                for q = 1, math.min(secs:GetArrayNum(), 16) do
                                    local nomeO = secs[q].OrganType.TagName:ToString()
                                    if nomeO ~= "" and nomeO ~= "None" and not vistos[nomeO] then
                                        vistos[nomeO] = true; t.orgaos[#t.orgaos + 1] = nomeO
                                    end
                                end
                            end
                        end)
                    end
                    if mortosIds and mortosIds[t.id] then t.morto = true end
                    lista[#lista + 1] = t
                    chaves[#chaves + 1] = t.id .. ":" .. t.tiros
                end)
            end
        end)
    end)
    -- animais carregados perto: vivo ou morto (o jogo só carrega até ~750 m)
    if #lista > 0 then
        local porId = {}
        for _, t in ipairs(lista) do porId[t.id] = t end
        pcall(function()
            local lib = StaticFindObject("/Script/HS3AnimalsRuntime.Default__CreatureUtilsFunctionLibrary")
            for i, a in ipairs(FindAllOf("AnimalCharacter") or {}) do
                if i > 300 then break end
                pcall(function()
                    local t = porId[a.EcoSimCreatureId]
                    if not t then return end
                    t.vivo = lib:IsCreatureAlive(a)
                    local p = a:K2_GetActorLocation()
                    t.pos = { x = p.X, y = p.Y }
                    t.especie = a.SpeciesTag.TagName:ToString()
                end)
            end
        end)
        for _, t in ipairs(lista) do
            if t.vivo ~= nil then chaves[#chaves + 1] = t.id .. (t.vivo and "v" or "m") end
        end
    end
    table.sort(chaves)
    return lista, table.concat(chaves, ",")
end

return M
