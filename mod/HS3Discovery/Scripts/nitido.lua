-- Refaz os ícones de armas, roupas e itens em alta resolução.
-- O jogo guarda esses ícones em baixa resolução até serem vistos na loja; aqui pedimos a resolução
-- máxima (SetForceMipLevelsToBeResident), esperamos ~3 s e desenhamos de novo.
-- Segurança: entre um passo e outro guardamos só NOMES (texto). A textura é carregada e desenhada
-- no mesmo passo (guardar textura entre passos já fechou o jogo).
local M = {}

function M.iniciar(ctx)
    local DIR, log = ctx.DIR, ctx.log
    local IMG = DIR .. "img\\"
    if _G.HS3_NITIDO_RODANDO then log("nítido: já está rodando"); return end

    -- ícones que o app usa (lidos do jogo_dados.json)
    local ids, vistos = {}, {}
    local f = io.open(DIR .. "jogo_dados.json", "rb")
    if not f then log("nítido: falta jogo_dados.json"); return end
    local txt = f:read("*a"); f:close()
    for id in txt:gmatch('"icone":"item_(.-)%.png"') do
        if not vistos[id] then vistos[id] = true; ids[#ids + 1] = id end
    end
    -- já refeitos numa rodada anterior (lista em img\nitidos.txt)
    local feitos = {}
    local fl = io.open(IMG .. "nitidos.txt", "rb")
    if fl then for l in fl:lines() do feitos[l] = true end; fl:close() end
    local fila = {}
    for _, id in ipairs(ids) do
        if not feitos[id] and (not ctx.limite or #fila < ctx.limite) then fila[#fila + 1] = id end
    end
    local total, pron = #fila, 0
    log(string.format("nítido: %d ícones para refazer (%d já estavam nítidos)", total, #ids - total))
    if total == 0 then return end
    _G.HS3_NITIDO_RODANDO = true

    local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
    local KRL = StaticFindObject("/Script/Engine.Default__KismetRenderingLibrary")
    local function valido(o) local ok, v = pcall(function() return o and o:IsValid() end); return ok and v end
    local function classe(o) local c; pcall(function() c = o:GetClass():GetFName():ToString() end); return c end
    local function carregar(x)
        if x == nil then return nil end
        if classe(x) then return x end
        local ok, o = pcall(function() return KSL:LoadAsset_Blocking(x) end)
        return ok and valido(o) and o or nil
    end
    local function item(id)
        local ok, o = pcall(function()
            return KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(
                { PrimaryAssetType = { Name = FName("HS3StoreItemAsset") }, PrimaryAssetName = FName(id) }))
        end)
        return ok and valido(o) and o or nil
    end
    -- textura + recorte do ícone (PaperSprite ou Texture2D)
    local function fonte(id)
        local it = item(id); if not it then return nil end
        local ic = carregar(it.ItemIcon)
        local cls = classe(ic)
        if cls == "PaperSprite" then
            local tex, uv, dim = carregar(ic.BakedSourceTexture), ic.BakedSourceUV, ic.BakedSourceDimension
            if not tex or classe(tex) ~= "Texture2D" or dim.X == 0 then
                tex, uv, dim = carregar(ic.SourceTexture), ic.SourceUV, ic.SourceDimension
            end
            if not tex or classe(tex) ~= "Texture2D" or dim.X == 0 or dim.Y == 0 then return nil end
            return { tex = tex, x = uv.X, y = uv.Y, w = dim.X, h = dim.Y }
        elseif cls == "Texture2D" then
            return { tex = ic, x = 0, y = 0, w = ic:Blueprint_GetSizeX(), h = ic:Blueprint_GetSizeY() }
        end
    end

    local function pedirResolucao(id)
        local s = fonte(id)
        if s then pcall(function() s.tex:SetForceMipLevelsToBeResident(45.0, 0) end) end
    end

    local function desenhar(id, pc)
        local s = fonte(id); if not s then return false end
        local tw, th = s.tex:Blueprint_GetSizeX(), s.tex:Blueprint_GetSizeY()
        local maior = math.max(s.w, s.h)
        local tam = math.floor(math.max(256, math.min(512, maior)))
        local w, h = tam, tam
        if s.w > s.h then h = tam * s.h / s.w elseif s.h > s.w then w = tam * s.w / s.h end
        local rt = KRL:CreateRenderTarget2D(pc, tam, tam, 2, { R = 0, G = 0, B = 0, A = 0 }, false, false)
        local canvas, sz, c = {}, {}, {}
        KRL:BeginDrawCanvasToRenderTarget(pc, rt, canvas, sz, c)
        local cv = canvas.Canvas or canvas
        cv:K2_DrawTexture(s.tex, { X = (tam - w) / 2, Y = (tam - h) / 2 }, { X = w, Y = h },
            { X = s.x / tw, Y = s.y / th }, { X = s.w / tw, Y = s.h / th }, { R = 1, G = 1, B = 1, A = 1 }, 2, 0.0, { X = 0.5, Y = 0.5 })
        KRL:EndDrawCanvasToRenderTarget(pc, c.Context or c)
        KRL:ExportRenderTarget(pc, rt, IMG, "item_" .. id .. ".png")
        return true
    end

    local LOTE, ESPERA = 6, 7          -- 6 ícones por vez; espera 7 × 0,5 s = 3,5 s
    local pos, lote, contagem, erros = 1, nil, 0, 0
    local function progresso(fim)
        local p = io.open(IMG .. "nitido_progresso.json", "wb")
        if p then p:write(string.format('{"feitos":%d,"total":%d,"fim":%s,"ts":%d}', pron, total, fim and "true" or "false", os.time())); p:close() end
    end
    progresso(false)

    local acabou = false
    LoopAsync(500, function()
        if acabou then return true end
        ExecuteInGameThread(function()
            if acabou then return end
            local pc = FindFirstOf("HS3PlayerController")
            local okPawn = false
            if valido(pc) then pcall(function() okPawn = pc.Pawn:IsValid() end) end
            if not okPawn then
                log("nítido: pausado (fora da reserva). Rode de novo depois: continua de onde parou.")
                _G.HS3_NITIDO_RODANDO = false; acabou = true; progresso(true); return
            end
            if not lote then
                if pos > total then
                    log(string.format("nítido: terminado, %d ícones refeitos, %d falhas", pron, erros))
                    _G.HS3_NITIDO_RODANDO = false; acabou = true; progresso(true); return
                end
                lote = {}
                for k = pos, math.min(total, pos + LOTE - 1) do
                    lote[#lote + 1] = fila[k]
                    pcall(pedirResolucao, fila[k])
                end
                pos = pos + #lote
                contagem = 0
                return
            end
            contagem = contagem + 1
            if contagem < ESPERA then return end
            local fl2 = io.open(IMG .. "nitidos.txt", "ab")
            for _, id in ipairs(lote) do
                local ok, r = pcall(desenhar, id, pc)
                if ok and r then
                    pron = pron + 1
                    if fl2 then fl2:write(id .. "\n") end
                else
                    erros = erros + 1
                    if erros <= 5 then log("nítido: falha em " .. id .. ": " .. tostring(r)) end
                end
            end
            if fl2 then fl2:close() end
            lote = nil
            progresso(false)
        end)
        return false
    end)
end

return M
