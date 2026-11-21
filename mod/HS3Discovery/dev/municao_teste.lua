local log = HS3.log
local ch = FindFirstOf("HS3WeaponSaveSlotChunk")
local function id(t, n) return { PrimaryAssetType = { Name = FName(t) }, PrimaryAssetName = FName(n) } end
local function s(p) local ok, r = pcall(function() return p.PrimaryAssetType.Name:ToString() .. ":" .. p.PrimaryAssetName:ToString() end); return ok and r or ("?" .. type(p)) end
for _, arma in ipairs({ "DA_VerneyCarron_Linergie_One_StoreItem", "DA_Browning_XBolt_EV_StoreItem" }) do
    local wid = id("HS3StoreItemAsset", arma)
    local ok, e = pcall(function()
        local out = {}
        ch:GetAllAttachmentStoreIdsForWeapon(wid, out)
        local n = 0
        for k, v in pairs(out) do
            n = n + 1
            local val = v; pcall(function() val = v:get() end)
            if type(val) == "table" then for k2, v2 in pairs(val) do log("   out[" .. tostring(k) .. "]." .. tostring(k2) .. " = " .. tostring(v2)) end
            else log("   out[" .. tostring(k) .. "] = " .. s(val)) end
        end
        log(arma .. ": " .. n .. " anexos (store ids)")
    end)
    if not ok then log(arma .. " GetAll falhou: " .. tostring(e)) end
    local ok2, r = pcall(function() return ch:GetAttachmentOfTypeForWeaponId(wid, { TagName = FName("Cosmetics.Weapons.Attachments.Ammo") }) end)
    log("  GetAttachmentOfType: ok=" .. tostring(ok2) .. " tipo=" .. type(r) .. " val=" .. (ok2 and s(r) or tostring(r)))
end
pcall(function()
    local n = 0
    ch.AppliedWeaponStoreItems:ForEach(function(_, e)
        n = n + 1
        if n <= 2 then
            local c = e:get()
            pcall(function() log("  cfg arma=" .. s(c.WeaponStoreId)) end)
            pcall(function() c.AttachmentStoreIds:ForEach(function(_, a) log("    anexo " .. s(a:get())) end) end)
            pcall(function() c.Attachments:ForEach(function(_, a) log("    anexo2 " .. s(a:get())) end) end)
        end
    end)
    log("  AppliedWeaponStoreItems: " .. n)
end)
log("municao_teste fim")
