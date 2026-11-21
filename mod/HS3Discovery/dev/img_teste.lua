local log, valid, tag, DIR = HS3.log, HS3.valid, HS3.tagName, HS3.dir
local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
local KRL = StaticFindObject("/Script/Engine.Default__KismetRenderingLibrary")
local pc = FindFirstOf("HS3PlayerController")
local IMG = DIR .. "img\\"
os.execute('mkdir "' .. IMG .. '" 2>nul')

local function ids(tipo)
    local r, l = {}, {}
    KSL:GetPrimaryAssetIdList({ Name = FName(tipo) }, r)
    for _, v in ipairs(r) do l[#l + 1] = v:get() end
    return l
end
local function carregar(id) return KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(id)) end
local function desc(o)
    if o == nil then return "nil" end
    local s = type(o)
    pcall(function() s = s .. " valid=" .. tostring(o:IsValid()) end)
    pcall(function() s = s .. " nome=" .. o:GetFullName() end)
    return s
end

local function exportar(obj, arq, tam)
    local rt = KRL:CreateRenderTarget2D(pc, tam, tam, 2, { R = 0, G = 0, B = 0, A = 0 }, false, false)
    local classe = obj:GetClass():GetFName():ToString()
    log("  classe=" .. classe)
    if classe:find("Material") then
        KRL:DrawMaterialToRenderTarget(pc, rt, obj)
    else
        local w, h = tam, tam
        local ok, e = pcall(function()
            local sx, sy = obj:Blueprint_GetSizeX(), obj:Blueprint_GetSizeY()
            log("  tamanho " .. sx .. "x" .. sy)
            if sx > sy then h = tam * sy / sx elseif sy > sx then w = tam * sx / sy end
        end)
        if not ok then log("  sem GetSize: " .. tostring(e)) end
        local canvas, sz, c = {}, {}, {}
        KRL:BeginDrawCanvasToRenderTarget(pc, rt, canvas, sz, c)
        local cv = canvas.Canvas or canvas
        cv:K2_DrawTexture(obj, { X = (tam - w) / 2, Y = (tam - h) / 2 }, { X = w, Y = h }, { X = 0, Y = 0 }, { X = 1, Y = 1 },
            { R = 1, G = 1, B = 1, A = 1 }, 2, 0.0, { X = 0.5, Y = 0.5 })
        KRL:EndDrawCanvasToRenderTarget(pc, c.Context or c)
    end
    KRL:ExportRenderTarget(pc, rt, IMG, arq)
    log("  exportado " .. arq)
end

local function resolver(soft, nome)
    log(nome .. ": bruto=" .. desc(soft))
    if soft == nil then return nil end
    local ok, v = pcall(function() return soft:IsValid() end)
    if ok and v then
        local cls = ""
        pcall(function() cls = soft:GetClass():GetFName():ToString() end)
        if cls ~= "" then return soft end
    end
    local ok2, o = pcall(function() return KSL:LoadAsset_Blocking(soft) end)
    log(nome .. ": carregado=" .. (ok2 and desc(o) or ("erro " .. tostring(o))))
    if ok2 and o and o:IsValid() then return o end
    local ok3, s = pcall(function() return soft:ToString() end)
    if ok3 then log(nome .. ": ToString=" .. tostring(s)) end
    return nil
end

local function teste(nome, f)
    local ok, e = pcall(f)
    if not ok then log("FALHA " .. nome .. ": " .. tostring(e)) end
end

teste("diario", function()
    local l = ids("AnimalFieldJournalEntryDataAsset")
    for i = 1, 2 do
        local o = carregar(l[i])
        log("diario " .. o:GetFName():ToString())
        local img = resolver(o.InfoFrameData1.InfoBrush.ResourceObject, "InfoBrush")
        if img then exportar(img, "teste_diario" .. i .. ".png", 768) end
        pcall(function() log("  IconBrush? " .. desc(o.EntryIcon)) end)
    end
end)

teste("especie", function()
    local l = ids("SpeciesDefinitionDataAsset")
    local s = carregar(l[1])
    log("especie " .. s:GetFName():ToString())
    s.PerLevelLicenseData:ForEach(function(k, v)
        local img = resolver(v:get().Image, "licenca")
        if img then exportar(img, "teste_licenca.png", 512) end
    end)
end)

teste("cao", function()
    local l = ids("HS3CompanionDefinitionDataAsset")
    local c = carregar(l[1])
    log("cao " .. c:GetFName():ToString() .. " " .. c.DisplayName:ToString())
    local img = resolver(c.DisplayIcon, "DisplayIcon")
    if img then exportar(img, "teste_cao.png", 512) end
end)

teste("loja", function()
    local l = ids("HS3StoreItemAsset")
    local n = 0
    for _, id in ipairs(l) do
        local it = carregar(id)
        local t = tag(it.ItemType) or ""
        if (t:find("Weapon") or t:find("Rifle")) and n < 1 then
            n = n + 1
            log("arma " .. it:GetFName():ToString() .. " tipo=" .. t .. " nome=" .. it.ItemName:ToString())
            local img = resolver(it.ItemIcon, "ItemIcon")
            if img then exportar(img, "teste_arma.png", 256) end
            local alvo = carregar(it.ItemAssetID)
            log("  alvo " .. desc(alvo))
            local ATTR = StaticFindObject("/Script/HS3CoreRuntime.Default__HS3AttributeFunctionLibrary")
            FindFirstOf("HS3AttributeDataAsset").AttributeConfigs:ForEach(function(k, v)
                local a = k:get()
                local ok, val = pcall(function() return ATTR:GetAttributeValueFromAssetRaw(a, alvo) end)
                log("  attr " .. a.AttributeName:ToString() .. " = " .. tostring(ok and val or "erro"))
            end)
        end
    end
end)
log("img_teste fim")
