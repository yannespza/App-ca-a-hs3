-- Testa Scripts\municao.lua sem reiniciar o jogo (o comando "municao" só existe após reiniciar).
local saida = {}
local ch, e = loadfile("ue4ss\\Mods\\HS3Discovery\\Scripts\\municao.lua")
if not ch then return "erro: " .. tostring(e) end
-- antes: reserva e máximo de cada arma
for _, it in ipairs(FindAllOf("HS3InventoryItemInstance") or {}) do
    pcall(function()
        local st = it.StatTags.Stacks
        for j = 1, #st do
            if st[j].Tag.TagName:ToString():find("Ammo.Spare") then saida[#saida + 1] = it.ItemDef:GetFName():ToString() .. " antes=" .. st[j].StackCount end
        end
    end)
end
local ctx = { log = function(s) saida[#saida + 1] = s end, emit = function(k, d) saida[#saida + 1] = "evento " .. k .. " ok=" .. tostring(d.ok) .. " balas=" .. tostring(d.balas) end }
ch().recarregar(ctx, 0, "teste")
return table.concat(saida, " ; ")
