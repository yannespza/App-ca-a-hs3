-- Sonda: licenças de caça (quantas você tem por espécie, limite de cada licença) e itens de DLC da loja.
-- Grava dev\sonda_licencas.json. Rodar numa reserva: script sonda_licencas.lua
local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
local function valido(o) local ok, v = pcall(function() return o and o:IsValid() end); return ok and v end
local function tagn(t) local s = "?"; pcall(function() s = t.TagName:ToString() end); return s end
local r = { cache = {}, permitidas = {}, salvas = {}, licencas = {}, dlc = {}, prefixos = {}, erros = {} }

local lc = FindFirstOf("HuntingLicenseControllerComp")
if valido(lc) then
    pcall(function() lc.LocalLicenseCache:ForEach(function(_, e) local c = e:get(); r.cache[#r.cache + 1] = { tag = tagn(c.AnimalTag), n = c.ClaimedAmount } end) end)
    pcall(function() lc.AllowedLicenceForCurrentMap.GameplayTags:ForEach(function(_, t) r.permitidas[#r.permitidas + 1] = tagn(t:get()) end) end)
    local ok, e = pcall(function()
        lc.LicenseSaveSlot.PerLevelHuntingLicenses:ForEach(function(_, el)
            local p = el:get()
            local nivel = p.LevelId.PrimaryAssetName:ToString()
            local l = { nivel = nivel, compradas = {}, ilimitadas = {} }
            p.PurchassedLicensesWithCount:ForEach(function(_, x) local c = x:get(); l.compradas[#l.compradas + 1] = { tag = tagn(c.AnimalTag), n = c.ClaimedAmount } end)
            p.UnlimitedLicenses:ForEach(function(_, x) l.ilimitadas[#l.ilimitadas + 1] = tagn(x:get()) end)
            r.salvas[#r.salvas + 1] = l
        end)
    end)
    if not ok then r.erros[#r.erros + 1] = "salvas: " .. tostring(e) end
else r.erros[#r.erros + 1] = "sem HuntingLicenseControllerComp" end

local ids = {}
pcall(function() KSL:GetPrimaryAssetIdList({ Name = FName("HS3StoreItemAsset") }, ids) end)
for _, v in ipairs(ids) do
    local id = v:get()
    local nome = id.PrimaryAssetName:ToString()
    local o
    pcall(function() o = KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(id)) end)
    if valido(o) then
        local fn = o:GetFullName()
        local pref = fn:match("^%S+%s+/([^/]+)/") or "?"
        r.prefixos[pref] = (r.prefixos[pref] or 0) + 1
        local ci = ""; pcall(function() ci = o.ContentIdentifier:ToString() end)
        if ci ~= "" or pref:find("DLC") then r.dlc[#r.dlc + 1] = { id = nome, pref = pref, ci = ci } end
        if nome:find("_License$") then
            local l = { id = nome, tag = tagn(o.ItemType), pref = pref }
            pcall(function() l.max = o.MaxClaims end)
            pcall(function() l.transitoria = o.bIsAlwaysTransient end)
            pcall(function() l.vale = o.bShouldAllowPurchaseWithVouchers end)
            pcall(function() l.preco = o.ItemCost end)
            r.licencas[#r.licencas + 1] = l
        end
    end
end

local f = io.open(HS3.dir .. "dev\\sonda_licencas.json", "wb")
f:write(HS3.json(r)); f:close()
return #r.cache .. " no cache, " .. #r.licencas .. " licenças, " .. #r.dlc .. " itens DLC"
