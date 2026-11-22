-- Teste: comprar a licença mais barata (pato-preto, $20) pela loja e ver se os créditos e a licença mudam.
local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
local function creditos()
    local v
    pcall(function()
        FindFirstOf("HS3StoreSaveGame").CurrencyTypeList:ForEach(function(_, e)
            local it = e:get()
            if it.CurrencyType.TagName:ToString() == "Currency.Credits" then v = it.CurrencyAmount end
        end)
    end)
    return v
end
local function licenca(tag)
    local n
    pcall(function()
        FindFirstOf("HuntingLicenseControllerComp").LocalLicenseCache:ForEach(function(_, e)
            local c = e:get()
            if c.AnimalTag.TagName:ToString() == tag then n = c.ClaimedAmount end
        end)
    end)
    return n
end
local TAG = "Animals.Types.Bird.Duck.Black"
local item
local ids = {}
KSL:GetPrimaryAssetIdList({ Name = FName("HS3StoreItemAsset") }, ids)
for _, v in ipairs(ids) do
    local id = v:get()
    if id.PrimaryAssetName:ToString() == "DA_Duck_Black_License" then
        item = KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(id))
    end
end
local a, la = creditos(), licenca(TAG)
local ok, e = pcall(function() FindFirstOf("HuntingLicenseControllerComp"):PurchaseLicenseForCurrentWorld({ TagName = FName(TAG) }, false, false) end)
local d, ld = creditos(), licenca(TAG)
local ilim
pcall(function() ilim = FindFirstOf("HuntingLicenseControllerComp"):IsUnlimitedLicense({ TagName = FName(TAG) }) end)
return string.format("licenca-mundo ok=%s err=%s creditos %s->%s licenca %s->%s ilimitada=%s", tostring(ok), tostring(e), tostring(a), tostring(d), tostring(la), tostring(ld), tostring(ilim))
