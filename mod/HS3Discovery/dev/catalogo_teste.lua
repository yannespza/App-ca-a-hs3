local out = {}
local function add(k, v) out[#out+1] = k .. ": " .. tostring(v) end
local function try(n, f) local ok, e = pcall(f); if not ok then add("ERRO " .. n, e) end end
local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
local ids = {}
try("lista", function()
    local r = {}
    local ret = KSL:GetPrimaryAssetIdList({ Name = FName("HS3StoreItemAsset") }, r)
    add("ret_tipo", type(ret) .. " " .. tostring(ret))
    for _, v in ipairs(r) do
        local id = v:get()
        ids[#ids + 1] = { t = id.PrimaryAssetType.Name:ToString(), n = id.PrimaryAssetName:ToString() }
    end
    add("ids", #ids)
    for i = 1, math.min(5, #ids) do add("id", ids[i].t .. ":" .. ids[i].n) end
end)
try("carregar", function()
    local t0 = os.clock()
    for i = 1, math.min(3, #ids) do
        local id = { PrimaryAssetType = { Name = FName(ids[i].t) }, PrimaryAssetName = FName(ids[i].n) }
        local soft = KSL:GetSoftObjectReferenceFromPrimaryAssetId(id)
        add("soft", tostring(soft))
        local okp, path = pcall(function() return KSL:Conv_SoftObjRefToSoftObjPath(soft) end)
        local okq, str = pcall(function() return KSL:BreakSoftObjectPath(path, {}) end)
        add("path", tostring(okp) .. " " .. tostring(path) .. " " .. tostring(okq) .. " " .. tostring(str))
        local okl, obj = pcall(function() return KSL:LoadAsset_Blocking(soft) end)
        add("load", tostring(okl) .. " " .. (okl and obj and obj.IsValid and obj:IsValid() and obj:GetFullName() or tostring(obj)))
    end
    add("tempo", os.clock() - t0)
end)
local f = io.open(HS3.dir .. "dev\\resultado_catalogo.txt", "w"); f:write(table.concat(out, "\n")); f:close()
return #out
