-- Sala de troféus: quantos animais estão empalhados em cada mapa (lido a cada ~45 s, só leitura).
-- Testado em 28/11 (sonda_cao_trofeus): TaxidermyStandsSaveChunk.PerLevelStandsSavedData
local M = {}

function M.contar()
    local ch = FindFirstOf("TaxidermyStandsSaveChunk")
    if not ch or not ch:IsValid() then return nil end
    local porNivel, total = {}, 0
    ch.PerLevelStandsSavedData:ForEach(function(k, v)
        local arr = v:get().StandSavedData
        local n = 0
        for i = 1, math.min(arr:GetArrayNum(), 120) do
            pcall(function() n = n + arr[i].AssignedAnimalsForSpots:GetArrayNum() end)
        end
        local nome = k:get():ToString():match("([^/]+)$") or "?"
        porNivel[nome] = n
        total = total + n
    end)
    return total, porNivel
end

return M
