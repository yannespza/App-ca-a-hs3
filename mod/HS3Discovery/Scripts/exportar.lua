-- Exportação dos dados do jogo para o app: fauna (diário de campo), espécies, cães,
-- catálogo da loja (roupas, armas, itens) e as imagens/ícones usados pelo próprio jogo.
-- Roda em lotes para não travar o jogo. Uso: local exp = dofile(DIR .. "Scripts\\exportar.lua"); exp.iniciar(ctx)

local M = {}
M.VERSAO = 3
local VERSAO_DADOS = M.VERSAO

local function txt(x) local ok, s = pcall(function() return x:ToString() end); return ok and s or "" end
local function pid(id) return id.PrimaryAssetType.Name:ToString() .. ":" .. id.PrimaryAssetName:ToString() end

function M.iniciar(ctx)
    local DIR, log, writeFile, json, tag, valid = ctx.DIR, ctx.log, ctx.writeFile, ctx.json, ctx.tagName, ctx.valid
    local IMG = DIR .. "img\\"
    local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
    local KRL = StaticFindObject("/Script/Engine.Default__KismetRenderingLibrary")
    local ATTR = StaticFindObject("/Script/HS3CoreRuntime.Default__HS3AttributeFunctionLibrary")
    local PROJ = StaticFindObject("/Script/HS3WeaponsRuntime.Default__HS3ProjectileFunctionLibrary")

    local function ids(tipo)
        local r, lista = {}, {}
        pcall(function() KSL:GetPrimaryAssetIdList({ Name = FName(tipo) }, r) end)
        for _, v in ipairs(r) do lista[#lista + 1] = v:get() end
        return lista
    end
    local function carregar(id)
        local ok, o = pcall(function() return KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(id)) end)
        return ok and valid(o) and o or nil
    end
    local function carregarSoft(soft)
        local ok, o = pcall(function() return KSL:LoadAsset_Blocking(soft) end)
        return ok and valid(o) and o or nil
    end

    -- atributos (camuflagem das roupas e características das armas)
    local atributos = {}
    pcall(function()
        FindFirstOf("HS3AttributeDataAsset").AttributeConfigs:ForEach(function(k, v)
            local a = k:get()
            atributos[#atributos + 1] = { nome = a.AttributeName:ToString(), ref = a, cfg = v:get() }
        end)
    end)
    local function lerAtributos(obj, so_cosmeticos)
        local st = {}
        for _, a in ipairs(atributos) do
            if not so_cosmeticos or a.cfg.bIsInfluencedByCosmetics then
                local ok, v = pcall(function() return ATTR:GetAttributeValueFromAssetRaw(a.ref, obj) end)
                if ok and v and v ~= 0 then st[a.nome] = v end
            end
        end
        return st
    end

    -- imagens: desenha a textura num render target e salva como PNG.
    -- Só Texture2D vai para o canvas; PaperSprite usa a textura dele com o recorte (UV) certo.
    -- Qualquer outro tipo (material etc.) é ignorado: desenhar o tipo errado fecha o jogo.
    local rts = {}
    local pc = FindFirstOf("HS3PlayerController")
    local function classe(o) local c; pcall(function() c = o:GetClass():GetFName():ToString() end); return c end
    local function resolver(x)
        if x == nil then return nil end
        if classe(x) then return x end
        local o = carregarSoft(x)
        return o and classe(o) and o or nil
    end
    local function desenhar(tex, arquivo, tam, uv0, uvT, larg, alt)
        local rt = rts[tam]
        if not rt then
            rt = KRL:CreateRenderTarget2D(pc, tam, tam, 2, { R = 0, G = 0, B = 0, A = 0 }, false, false)
            rts[tam] = rt
        end
        KRL:ClearRenderTarget2D(pc, rt, { R = 0, G = 0, B = 0, A = 0 })
        local w, h = tam, tam
        if larg > alt then h = tam * alt / larg elseif alt > larg then w = tam * larg / alt end
        local canvas, sz, c = {}, {}, {}
        KRL:BeginDrawCanvasToRenderTarget(pc, rt, canvas, sz, c)
        local cv = canvas.Canvas or canvas
        cv:K2_DrawTexture(tex, { X = (tam - w) / 2, Y = (tam - h) / 2 }, { X = w, Y = h }, uv0, uvT,
            { R = 1, G = 1, B = 1, A = 1 }, 2, 0.0, { X = 0.5, Y = 0.5 })
        KRL:EndDrawCanvasToRenderTarget(pc, c.Context or c)
        KRL:ExportRenderTarget(pc, rt, IMG, arquivo)
    end
    local function exportarImagem(x, arquivo, tam)
        local obj = resolver(x)
        if not obj then return nil end
        local f = io.open(IMG .. arquivo, "rb")
        if f then f:close(); return arquivo end
        local cls = classe(obj)
        local ok = false
        if cls == "Texture2D" then
            if obj:GetFullName():find("Icon%-Warning") then return nil end
            ok = pcall(function()
                desenhar(obj, arquivo, tam, { X = 0, Y = 0 }, { X = 1, Y = 1 }, obj:Blueprint_GetSizeX(), obj:Blueprint_GetSizeY())
            end)
        elseif cls == "PaperSprite" then
            ok = pcall(function()
                local tex, uv, dim = resolver(obj.BakedSourceTexture), obj.BakedSourceUV, obj.BakedSourceDimension
                if not tex or classe(tex) ~= "Texture2D" or dim.X == 0 then
                    tex, uv, dim = resolver(obj.SourceTexture), obj.SourceUV, obj.SourceDimension
                end
                if not tex or classe(tex) ~= "Texture2D" or dim.X == 0 or dim.Y == 0 then error("sprite sem textura") end
                local tw, th = tex:Blueprint_GetSizeX(), tex:Blueprint_GetSizeY()
                desenhar(tex, arquivo, tam, { X = uv.X / tw, Y = uv.Y / th }, { X = dim.X / tw, Y = dim.Y / th }, dim.X, dim.Y)
            end)
        end
        return ok and arquivo or nil
    end
    local function imagemDeBrush(brush, arquivo, tam)
        local r
        pcall(function() r = brush.ResourceObject end)
        return exportarImagem(r, arquivo, tam)
    end

    local function secoes(frame)
        local lista = {}
        pcall(function()
            frame.InfoSections:ForEach(function(_, e)
                local s = txt(e:get().SectionText)
                if s ~= "" then lista[#lista + 1] = s end
            end)
        end)
        return lista
    end

    -- fila de tarefas (cada uma processa um item)
    local fila, saida = {}, { versao = VERSAO_DADOS, animais = {}, especies = {}, caes = {}, itens = {}, diario = {} }

    for _, id in ipairs(ids("AnimalFieldJournalEntryDataAsset")) do
        fila[#fila + 1] = function()
            local o = carregar(id); if not o then return end
            local nome = o:GetFName():ToString()
            local a = { id = nome, titulo = txt(o.EntryTitle), tag = tag(o.AnimalTag), grupo = tag(o.FieldJournalHeaderTag),
                        descricao = txt(o.InfoFrameData1.InfoText), mapas = {}, secoes = secoes(o.ScheduleInfo),
                        secoes_titulo = txt(o.ScheduleInfo.TitleText), habitat = secoes(o.HabitatInfo),
                        habitat_titulo = txt(o.HabitatInfo.TitleText), trofeu = txt(o.ThrophyInfo.TitleText) }
            pcall(function() o.IncludedMaps:ForEach(function(_, e) a.mapas[#a.mapas + 1] = e:get().PrimaryAssetName:ToString() end) end)
            a.imagem = imagemDeBrush(o.InfoFrameData1.InfoBrush, "animal_" .. nome .. ".png", 768)
            vistosDiario[nome] = true
            saida.animais[#saida.animais + 1] = a
        end
    end

    for _, id in ipairs(ids("SpeciesDefinitionDataAsset")) do
        fila[#fila + 1] = function()
            local s = carregar(id); if not s then return end
            local e = { id = s:GetFName():ToString(), tag = tag(s.CreatureTag), tipo_caca = tag(s.HuntingTypeTag),
                        preco_kg = s.PricePerKg, preco_taxidermia = s.TaxidermyPrice, chamado_m = s.CallAudibleDistance / 100,
                        medalhas = {}, licencas = {} }
            pcall(function() s.Male.MedalThresholds:ForEach(function(k, v) e.medalhas[tag(k:get())] = v:get() end) end)
            pcall(function() e.medalha_max = s.Male.MedalMaximumScore end)
            pcall(function()
                s.PerLevelLicenseData:ForEach(function(k, v)
                    local mapa = k:get().PrimaryAssetName:ToString()
                    local arq = exportarImagem(v:get().Image, "licenca_" .. e.id .. "_" .. mapa:gsub("[^%w]", "_") .. ".png", 512)
                    e.licencas[#e.licencas + 1] = { mapa = mapa, imagem = arq }
                end)
            end)
            saida.especies[#saida.especies + 1] = e
        end
    end

    for _, id in ipairs(ids("HS3CompanionDefinitionDataAsset")) do
        fila[#fila + 1] = function()
            local c = carregar(id); if not c then return end
            local e = { id = c:GetFName():ToString(), nome = txt(c.DisplayName), raca = tag(c.CompanionBreed) }
            pcall(function() e.imagem = exportarImagem(c.DisplayIcon, "cao_" .. e.id .. ".png", 512) end)
            saida.caes[#saida.caes + 1] = e
        end
    end

    local vistosDiario = {}
    for _, id in ipairs(ids("FieldJournalEntryDataAsset")) do
        fila[#fila + 1] = function()
            local o = carregar(id); if not o then return end
            local nome = o:GetFName():ToString()
            if vistosDiario[nome] then return end
            local e = { id = nome, titulo = txt(o.EntryTitle), categoria = tag(o.FieldJournalCategoryTag), grupo = tag(o.FieldJournalHeaderTag) }
            pcall(function() e.descricao = txt(o.InfoFrameData1.InfoText) end)
            pcall(function() e.imagem = imagemDeBrush(o.InfoFrameData1.InfoBrush, "diario_" .. nome .. ".png", 512) end)
            saida.diario[#saida.diario + 1] = e
        end
    end

    local relevantes = { "Inventory.", "Cosmetics.Character.Clothing", "Cosmetics.Companion", "Companion.", "Cosmetics.Weapons" }
    for _, id in ipairs(ids("HS3StoreItemAsset")) do
        fila[#fila + 1] = function()
            local item = carregar(id); if not item then return end
            local tipo = tag(item.ItemType) or ""
            local serve = false
            for _, p in ipairs(relevantes) do if tipo:sub(1, #p) == p then serve = true end end
            if not serve then return end
            local e = { id = item:GetFName():ToString(), tipo = tipo, nome = txt(item.ItemName), descricao = txt(item.ItemDescription),
                        preco = item.ItemCost, moeda = tag(item.CurrencyType), marca = tag(item.ItemBrand), item = pid(item.ItemAssetID),
                        cargas = item.NumberOfChargesPerPurchase, desativado = item.bIsDisabled, padrao = item.bIsDefaultBought }
            pcall(function()
                local tags = {}
                item.CompatibilityTags.GameplayTags:ForEach(function(_, t) tags[#tags + 1] = tag(t:get()) end)
                if #tags > 0 then e.compat = tags end
            end)
            pcall(function() local c = tag(PROJ:GetCaliberTagFromPrimaryAssetId(item.ItemAssetID)); if c and c ~= "None" then e.calibre = c end end)
            local alvo = carregar(item.ItemAssetID)
            if alvo then
                local tipoAsset = item.ItemAssetID.PrimaryAssetType.Name:ToString()
                if tipoAsset == "HS3ClothingDataAsset" or tipoAsset == "HS3BackpackDataAsset" then
                    e.stats = lerAtributos(alvo, true)
                    e.parte = tag(alvo.CosmeticTypeTag)
                    if e.nome == "" then e.nome = txt(alvo.DisplayName) end
                    if e.descricao == "" then e.descricao = txt(alvo.Description) end
                else
                    local st = lerAtributos(alvo, false)
                    if next(st) then e.atributos = st end
                end
            end
            pcall(function() e.icone = exportarImagem(item.ItemIcon, "item_" .. e.id .. ".png", 256) end)
            if not e.icone and alvo then pcall(function() e.icone = exportarImagem(alvo.DisplayIcon, "item_" .. e.id .. ".png", 256) end) end
            saida.itens[#saida.itens + 1] = e
        end
    end

    local total, i = #fila, 1
    log("exportação dos dados do jogo: " .. total .. " tarefas")
    LoopAsync(400, function()
        ExecuteInGameThread(function()
            local fim = math.min(i + 4, total)
            for k = i, fim do pcall(fila[k]) end
            i = fim + 1
            if i > total and fila then
                saida.diario = saida.diario or {}
                fila = nil
                writeFile(DIR .. "jogo_dados.json", json(saida))
                log(string.format("dados do jogo exportados: %d animais, %d espécies, %d cães, %d itens",
                    #saida.animais, #saida.especies, #saida.caes, #saida.itens))
                if ctx.fim then ctx.fim() end
            end
        end)
        return fila == nil
    end)
end

return M
