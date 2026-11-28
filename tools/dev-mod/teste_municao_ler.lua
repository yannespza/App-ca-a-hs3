local L = {}
for i, it in ipairs(FindAllOf("HS3InventoryItemInstance") or {}) do
    if i > 40 then break end
    pcall(function()
        local st = it.StatTags.Stacks
        local t = {}
        for j = 1, #st do t[#t + 1] = st[j].Tag.TagName:ToString() .. "=" .. tostring(st[j].StackCount) end
        if #t > 0 then L[#L + 1] = it.ItemDef:GetFName():ToString() .. " " .. table.concat(t, " ") end
    end)
end
pcall(function()
    local pc = FindFirstOf("HS3PlayerController")
    L[#L + 1] = "PAWN " .. pc.Pawn:GetFullName():sub(1, 80)
end)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\teste_municao_ler.txt", "wb"); f:write(table.concat(L, "\n")); f:close()
return #L
