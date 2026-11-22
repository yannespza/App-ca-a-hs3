-- Sonda: quais telas (widgets) de contrato estão abertas agora. Só lê nomes.
local L = {}
for _, base in ipairs({ "CommonActivatableWidget", "CommonUserWidget" }) do
    local ws = FindAllOf(base) or {}
    for _, w in ipairs(ws) do
        pcall(function()
            local n = w:GetFullName()
            if n:find("Contract") and not n:find("Default__") then
                local vis = "?"
                pcall(function() vis = tostring(w:IsVisible()) end)
                L[#L + 1] = n:match("^(%S+)") .. " " .. (n:match("([^%.]+)$") or n) .. " vis=" .. vis
            end
        end)
    end
end
return #L .. " | " .. table.concat(L, " | ")
