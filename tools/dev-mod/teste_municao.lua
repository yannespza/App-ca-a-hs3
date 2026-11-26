-- Teste: soma 1 bala na reserva (Ammo.Spare) da Winchester .22 e lê de volta.
local r = {}
for _, it in ipairs(FindAllOf("HS3InventoryItemInstance") or {}) do
    pcall(function()
        local def = it.ItemDef:GetFName():ToString()
        if not def:find("Winchester") then return end
        local st = it.StatTags.Stacks
        for j = 1, #st do
            local s = st[j]
            if s.Tag.TagName:ToString():find("Ammo.Spare") then
                local antes = s.StackCount
                local ok, e = pcall(function() it:AddStatTagStack(s.Tag, 1) end)
                local depois = "?"
                pcall(function() depois = it:GetStatTagStackCount(s.Tag) end)
                r[#r + 1] = def .. " antes=" .. tostring(antes) .. " add=" .. tostring(ok) .. (ok and "" or (" " .. tostring(e))) .. " depois=" .. tostring(depois)
            end
        end
    end)
end
return #r > 0 and table.concat(r, " ; ") or "arma não achada"
