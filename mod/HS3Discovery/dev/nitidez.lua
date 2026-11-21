local log, DIR = HS3.log, HS3.dir
local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
local KRL = StaticFindObject("/Script/Engine.Default__KismetRenderingLibrary")
local pc = FindFirstOf("HS3PlayerController")
local nomes = { "DA_Winchester_XPR_Strata_StoreItem", "D_Vest_VerneyCarron_Rapace_StoreItem", "DA_WindPowder_X7_StoreItem" }
local sprites = {}
for _, n in ipairs(nomes) do
    local ok, e = pcall(function()
        local it = KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId({ PrimaryAssetType = { Name = FName("HS3StoreItemAsset") }, PrimaryAssetName = FName(n) }))
        local sp = it.ItemIcon
        local tex = sp.BakedSourceTexture
        local ok2, cls = pcall(function() return tex:GetClass():GetFName():ToString() end)
        if not ok2 then tex = KSL:LoadAsset_Blocking(tex) end
        log(n .. " tex=" .. tex:GetFullName() .. " " .. tex:Blueprint_GetSizeX() .. "x" .. tex:Blueprint_GetSizeY())
        pcall(function() log("  NeverStream=" .. tostring(tex.NeverStream) .. " LODGroup=" .. tostring(tex.LODGroup) .. " LODBias=" .. tostring(tex.LODBias)) end)
        local r1 = pcall(function() tex:SetForceMipLevelsToBeResident(30.0, 0) end)
        log("  SetForceMipLevelsToBeResident " .. tostring(r1))
        local r2 = pcall(function() tex.bForceMiplevelsToBeResident = true end)
        log("  bForceMiplevelsToBeResident " .. tostring(r2))
        sprites[#sprites + 1] = { n = n, sp = sp, tex = tex }
    end)
    if not ok then log("falha " .. n .. ": " .. tostring(e)) end
end
local function desenhar(s, arq)
    local tex, uv, dim = s.tex, s.sp.BakedSourceUV, s.sp.BakedSourceDimension
    local tw, th = tex:Blueprint_GetSizeX(), tex:Blueprint_GetSizeY()
    local tam = 512
    local w, h = tam, tam
    if dim.X > dim.Y then h = tam * dim.Y / dim.X else w = tam * dim.X / dim.Y end
    log("  " .. s.n .. " uv=" .. uv.X .. "," .. uv.Y .. " dim=" .. dim.X .. "x" .. dim.Y)
    local rt = KRL:CreateRenderTarget2D(pc, tam, tam, 2, { R = 0, G = 0, B = 0, A = 0 }, false, false)
    local canvas, sz, c = {}, {}, {}
    KRL:BeginDrawCanvasToRenderTarget(pc, rt, canvas, sz, c)
    local cv = canvas.Canvas or canvas
    cv:K2_DrawTexture(tex, { X = (tam - w) / 2, Y = (tam - h) / 2 }, { X = w, Y = h }, { X = uv.X / tw, Y = uv.Y / th },
        { X = dim.X / tw, Y = dim.Y / th }, { R = 1, G = 1, B = 1, A = 1 }, 2, 0.0, { X = 0.5, Y = 0.5 })
    KRL:EndDrawCanvasToRenderTarget(pc, c.Context or c)
    KRL:ExportRenderTarget(pc, rt, DIR .. "img\\", arq)
end
local passo = 0
LoopAsync(3000, function()
    passo = passo + 1
    ExecuteInGameThread(function()
        for i, s in ipairs(sprites) do pcall(desenhar, s, "nitidez_" .. passo .. "_" .. i .. ".png") end
        log("nitidez passo " .. passo)
    end)
    return passo >= 3
end)
