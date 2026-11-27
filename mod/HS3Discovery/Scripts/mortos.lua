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

return M
