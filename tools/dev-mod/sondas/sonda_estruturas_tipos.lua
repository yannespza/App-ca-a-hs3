local c = {}
for _, a in ipairs(FindAllOf("HuntingStructureActor") or {}) do
    pcall(function() local n = a:GetClass():GetFName():ToString(); c[n] = (c[n] or 0) + 1 end)
end
local L = {}
for k, v in pairs(c) do L[#L + 1] = k .. "=" .. v end
pcall(function()
    for _, k in ipairs({ "HuntingStructureActor" }) do
        local a = FindFirstOf(k)
        L[#L + 1] = "SUPER " .. a:GetClass():GetSuperStruct():GetFName():ToString()
    end
end)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_estruturas_tipos.txt", "wb"); f:write(table.concat(L, "\n")); f:close()
return #L
