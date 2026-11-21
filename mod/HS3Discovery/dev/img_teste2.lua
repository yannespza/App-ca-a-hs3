local log, valid, tag, DIR = HS3.log, HS3.valid, HS3.tagName, HS3.dir
local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
local KRL = StaticFindObject("/Script/Engine.Default__KismetRenderingLibrary")
local pc = FindFirstOf("HS3PlayerController")
local IMG = DIR .. "img\\"

local function ids(tipo)
    local r, l = {}, {}
    KSL:GetPrimaryAssetIdList({ Name = FName(tipo) }, r)
    for _, v in ipairs(r) do l[#l + 1] = v:get() end
    return l
end
local function carregar(id) return KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(id)) end
local function nome(o) local s = "?"; pcall(function() s = o:GetFullName() end); return s end
local function resolver(x)
    if x == nil then return nil end
    local ok, cls = pcall(function() return x:GetClass():GetFName():ToString() end)
    if ok and cls then return x end
    local ok2, o = pcall(function() return KSL:LoadAsset_Blocking(x) end)
    if ok2 and o and o:IsValid() then return o end
    return nil
end
local function v2(v) local s = "?"; pcall(function() s = v.X .. "," .. v.Y end); return s end

local function desenharSprite(sp, arq, tam)
    local tex = resolver(sp.BakedSourceTexture)
    local uv, dim = sp.BakedSourceUV, sp.BakedSourceDimension
    log("  baked tex=" .. nome(tex) .. " uv=" .. v2(uv) .. " dim=" .. v2(dim))
    if not tex or dim.X == 0 then
        tex = resolver(sp.SourceTexture)
        uv, dim = sp.SourceUV, sp.SourceDimension
        log("  source tex=" .. nome(tex) .. " uv=" .. v2(uv) .. " dim=" .. v2(dim))
    end
    if not tex then return end
    local tw, th = tex:Blueprint_GetSizeX(), tex:Blueprint_GetSizeY()
    log("  tex " .. tw .. "x" .. th)
    local w, h = tam, tam
    if dim.X > dim.Y then h = tam * dim.Y / dim.X else w = tam * dim.X / dim.Y end
    local rt = KRL:CreateRenderTarget2D(pc, tam, tam, 2, { R = 0, G = 0, B = 0, A = 0 }, false, false)
    local canvas, sz, c = {}, {}, {}
    KRL:BeginDrawCanvasToRenderTarget(pc, rt, canvas, sz, c)
    local cv = canvas.Canvas or canvas
    cv:K2_DrawTexture(tex, { X = (tam - w) / 2, Y = (tam - h) / 2 }, { X = w, Y = h }, { X = uv.X / tw, Y = uv.Y / th },
        { X = dim.X / tw, Y = dim.Y / th }, { R = 1, G = 1, B = 1, A = 1 }, 2, 0.0, { X = 0.5, Y = 0.5 })
    KRL:EndDrawCanvasToRenderTarget(pc, c.Context or c)
    KRL:ExportRenderTarget(pc, rt, IMG, arq)
    log("  exportado " .. arq)
end

local vistos = {}
local ok, e = pcall(function()
    for _, id in ipairs(ids("HS3StoreItemAsset")) do
        local it = carregar(id)
        local t = tag(it.ItemType) or ""
        local grupo = t:match("^([^%.]+%.[^%.]+%.?[^%.]*)") or t
        if not vistos[grupo] then
            vistos[grupo] = true
            local ic = resolver(it.ItemIcon)
            local cls = "nil"
            pcall(function() cls = ic:GetClass():GetFName():ToString() end)
            log("tipo " .. t .. " | " .. it:GetFName():ToString() .. " | icone " .. cls .. " " .. nome(ic))
            if cls == "PaperSprite" and (t:find("Weapon") or t:find("Companion")) then
                pcall(desenharSprite, ic, "teste2_" .. grupo:gsub("[^%w]", "_") .. ".png", 256)
            end
        end
    end
end)
if not ok then log("falha loja: " .. tostring(e)) end

pcall(function()
    local l = ids("HS3ClothingDataAsset")
    local r = carregar(l[1])
    local ic = resolver(r.DisplayIcon)
    log("roupa " .. r:GetFName():ToString() .. " icone " .. nome(ic))
end)
pcall(function()
    for _, id in ipairs(ids("HS3CompanionDefinitionDataAsset")) do
        local c = carregar(id)
        local s = c:GetFName():ToString() .. " raca=" .. tostring(tag(c.CompanionBreed))
        pcall(function() s = s .. " cosm=" .. nome(resolver(c.DefaultCosmetic)) end)
        log("cao " .. s)
    end
end)
pcall(function()
    for _, id in ipairs(ids("FieldJournalEntryDataAsset")) do
        local o = carregar(id)
        local s = o:GetFName():ToString() .. " cls=" .. o:GetClass():GetFName():ToString()
        pcall(function() s = s .. " titulo=" .. o.EntryTitle:ToString() end)
        pcall(function() s = s .. " cat=" .. tostring(tag(o.FieldJournalCategoryTag)) .. " hdr=" .. tostring(tag(o.FieldJournalHeaderTag)) end)
        pcall(function() s = s .. " img=" .. nome(resolver(o.InfoFrameData1.InfoBrush.ResourceObject)) end)
        log("diario " .. s)
    end
end)
log("img_teste2 fim")
