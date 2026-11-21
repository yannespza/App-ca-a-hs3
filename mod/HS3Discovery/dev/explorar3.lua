local out = {}
local function add(k, v) out[#out+1] = k .. ": " .. tostring(v) end
local function try(n, f) local ok, e = pcall(f); if not ok then add("ERRO " .. n, e) end end
local function pid(id) return id.PrimaryAssetType.Name:ToString() .. ":" .. id.PrimaryAssetName:ToString() end

try("inventario", function()
    local inv = FindFirstOf("HS3InventoryManagerComponent")
    inv.CachedInventoryList.Items:ForEach(function(_, e)
        local it = e:get()
        add("inv", pid(it.SaveInfo.AssetId) .. " tipo=" .. tostring(HS3.tagName(it.SaveInfo.Type)) .. " cargas=" .. it.Charges)
    end)
end)
try("comprados", function()
    local n = 0
    FindFirstOf("HS3StoreSaveGame").BoughtItems:ForEach(function(_, e)
        n = n + 1
        local it = e:get()
        if n <= 80 then add("comprado", pid(it.AssetId) .. " cargas=" .. it.Charges) end
    end)
    add("comprados_total", n)
end)
try("loja", function()
    local itens = FindAllOf("HS3StoreItemAsset") or {}
    add("loja_total", #itens)
    local tipos = {}
    for i, s in ipairs(itens) do
        local tipo = HS3.tagName(s.ItemType) or "?"
        tipos[tipo] = (tipos[tipo] or 0) + 1
        if i <= 25 or tipo:find("Cloth") or tipo:find("Outfit") or tipo:find("Cosmetic") then
            local nome, desc = "", ""
            pcall(function() nome = s.ItemName:ToString() end)
            pcall(function() desc = s.ItemDescription:ToString():sub(1, 120) end)
            add("item", s:GetFName():ToString() .. " | " .. tipo .. " | " .. nome .. " | $" .. s.ItemCost .. " | " .. pid(s.ItemAssetID) .. " | " .. desc)
        end
    end
    for k, v in pairs(tipos) do add("tipo_loja", k .. " = " .. v) end
end)
try("deteccao", function()
    local d = FindFirstOf("HS3AttributeSet_Detection")
    add("det_owner", d:GetFullName())
    add("visual", d.VisualDetectionFactor.CurrentValue .. " base " .. d.VisualDetectionFactor.BaseValue)
    add("som", d.SoundDetectionFactor.CurrentValue)
    add("cheiro", d.SmellDetectionFactor.CurrentValue)
    add("min_raw", d.MinRawDetectionFactor.CurrentValue)
    add("max_raw", d.MaxRawDetectionFactor.CurrentValue)
    pcall(function() add("na_estrutura", d.InHuntingStructure.CurrentValue) end)
end)
try("noise", function()
    for _, c in ipairs({"HS3AttributeSet_Movement", "HS3AttributeSet_Character", "HS3AttributeSet_Noise"}) do
        local o = FindFirstOf(c)
        if o and o:IsValid() then pcall(function() add("noise_" .. c, o.NoiseValue.CurrentValue) end) end
    end
end)
try("attr_configs", function()
    local da = FindFirstOf("HS3AttributeDataAsset")
    add("attr_asset", da and da:GetFullName())
    da.AttributeConfigs:ForEach(function(k, v)
        local a = k:get()
        add("attr", tostring(a.AttributeName))
    end)
end)
try("cosmeticos", function()
    for _, c in ipairs({"HS3CosmeticDataAsset", "HS3ClothingDataAsset", "HS3CharacterCosmeticAsset", "CharacterCosmeticDataAsset"}) do
        local l = FindAllOf(c)
        if l then add("classe_" .. c, #l .. " ex: " .. l[1]:GetFullName()) end
    end
end)
local f = io.open(HS3.dir .. "dev\\resultado_explorar3.txt", "w"); f:write(table.concat(out, "\n")); f:close()
return #out
