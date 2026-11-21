-- Mochila (inventário levado para a caçada) e munição de cada arma.
-- Recarregado a cada comando (pode ser atualizado com o jogo aberto).
-- Regras de segurança (o jogo fechou em 21/11 com várias trocas seguidas):
--  * nada de guardar objetos do jogo entre chamadas; tudo é buscado na hora e checado com IsValid;
--  * a munição é lida pela propriedade AppliedWeaponStoreItems (nada de parâmetros de saída de funções);
--  * cada troca é feita num passo separado (main.lua põe numa fila, 1 por segundo) e só no fim salva e relê.
local M = {}

local TIPOS = { "Inventory.Weapon", "Inventory.Objects", "Inventory.GPS" }

local function tag(nome) return { TagName = FName(nome) } end
local function id(tipo, nome) return { PrimaryAssetType = { Name = FName(tipo) }, PrimaryAssetName = FName(nome) } end
local function idStr(pid)
    local ok, s = pcall(function() return pid.PrimaryAssetType.Name:ToString() .. ":" .. pid.PrimaryAssetName:ToString() end)
    return ok and s or nil
end
local function valido(o)
    if not o then return false end
    local ok, v = pcall(function() return o:IsValid() end)
    return ok and v
end
local function inv()
    local im = FindFirstOf("HS3InventoryManagerComponent")
    if valido(im) then return im end
end
local function chunkArmas()
    local ch = FindFirstOf("HS3WeaponSaveSlotChunk")
    if valido(ch) then return ch end
end

-- dentro de uma reserva, com personagem
function M.pronto()
    local pc = FindFirstOf("HS3PlayerController")
    if not valido(pc) then return false end
    local ok, pawn = pcall(function() return pc.Pawn end)
    return ok and valido(pawn) and inv() ~= nil
end

local function itensAtuais(im, tagName)
    local lista = {}
    pcall(function()
        im.CachedInventoryList.Items:ForEach(function(_, e)
            local it = e:get()
            lista[#lista + 1] = { item = idStr(it.SaveInfo.AssetId), tipo = tagName(it.SaveInfo.Type),
                                  idx = it.SaveInfo.SlotTypeIndex, cargas = it.Charges }
        end)
    end)
    return lista
end

function M.ler(ctx)
    local log, tagName = ctx.log, ctx.tagName
    local r = { ts = os.time(), slots = {}, itens = {}, erros = {}, pronto = M.pronto() }
    local im = inv()
    if not r.pronto or not im then
        -- fora da reserva: não sobrescreve a última leitura boa
        return r
    end
    for _, t in ipairs(TIPOS) do
        local ok, n = pcall(function() return im:GetNumSlotsForType(tag(t), false) end)
        if ok then r.slots[t] = n else r.erros[#r.erros + 1] = "slots " .. t end
    end
    r.itens = itensAtuais(im, tagName)
    ctx.writeFile(ctx.DIR .. "mochila.json", ctx.json(r))
    log(string.format("mochila lida: %d itens, slots arma=%s objeto=%s gps=%s",
        #r.itens, tostring(r.slots["Inventory.Weapon"]), tostring(r.slots["Inventory.Objects"]), tostring(r.slots["Inventory.GPS"])))
    return r
end

-- Munição e acessórios montados SÓ nas armas que estão na mochila -> armas.json.
-- (Ler os acessórios das 111 armas a cada 8 s fechou o jogo em 21/11: o UE4SS falha às vezes ao ler
--  uma lista dentro de outra. Agora: no máximo 2 armas, e só quando o app pede ou depois de uma troca.)
function M.armas(ctx)
    if not M.pronto() then return end
    local im, ch = inv(), chunkArmas()
    if not im or not ch then return end
    local alvos, n = {}, 0
    for _, i in ipairs(itensAtuais(im, ctx.tagName)) do
        if i.tipo == "Inventory.Weapon" and i.item then
            local nome = i.item:match("ID_(.+)$")
            if nome then alvos["DA_" .. nome .. "_StoreItem"] = true; n = n + 1 end
        end
    end
    local r = { ts = os.time(), municao = {} }
    if n > 0 then
        local ok, e = pcall(function()
            ch.AppliedWeaponStoreItems:ForEach(function(_, el)
                local c = el:get()
                local arma = idStr(c.WeaponStoreId)
                local nome = arma and (arma:match(":(.+)$") or arma)
                if nome and alvos[nome] then
                    local anexos = {}
                    c.AttachmentStoreIds:ForEach(function(_, a)
                        local s = idStr(a:get())
                        if s then anexos[#anexos + 1] = s:match(":(.+)$") or s end
                    end)
                    r.municao[nome] = anexos
                end
            end)
        end)
        if not ok then ctx.log("armas: " .. tostring(e)) end
    end
    ctx.writeFile(ctx.DIR .. "armas.json", ctx.json(r))
    ctx.log("armas da mochila lidas: " .. n)
end

-- põe um item (HS3InventoryItemDefinition:ID_x) no espaço idx (0, 1, 2…) do tipo
function M.por(ctx, item, tipo, idx)
    if not M.pronto() then ctx.log("mochila: fora da reserva, ignorado"); return end
    local im = inv()
    local t, n = item:match("^([^:]+):(.+)$")
    if not n then return end
    for _, i in ipairs(itensAtuais(im, ctx.tagName)) do
        if i.item == item and i.tipo == tipo and i.idx == idx then
            ctx.log("mochila: " .. n .. " já está no espaço " .. idx); return
        end
    end
    local okS, slot = pcall(function() return im:GetSlotIndexFromTypeIndex(tag(tipo), idx, false) end)
    if not okS or type(slot) ~= "number" or slot < 0 then ctx.log("mochila: espaço inválido " .. tipo .. " #" .. idx); return end
    ctx.log(string.format("mochila: pondo %s em %s #%d (slot %d)", n, tipo, idx, slot))
    im = inv(); if not im then return end
    im:AddItemAsset(id(t, n), tag(tipo), slot, true, false)
    ctx.emit("mochila", { acao = "por", item = item, tipo = tipo, idx = idx })
end

function M.tirar(ctx, item)
    if not M.pronto() then ctx.log("mochila: fora da reserva, ignorado"); return end
    local im = inv()
    local t, n = item:match("^([^:]+):(.+)$")
    if not n then return end
    local tem = false
    for _, i in ipairs(itensAtuais(im, ctx.tagName)) do if i.item == item then tem = true end end
    if not tem then ctx.log("mochila: " .. n .. " não está na mochila"); return end
    ctx.log("mochila: tirando " .. n)
    im:RemoveItemAsset(id(t, n))
    ctx.emit("mochila", { acao = "tirar", item = item })
end

-- troca a munição carregada numa arma (ids de loja: DA_..._StoreItem / D_Ammo_..._StoreItem)
function M.municao(ctx, armaLoja, municaoLoja)
    if not M.pronto() then ctx.log("mochila: fora da reserva, ignorado"); return end
    local ch = chunkArmas(); if not ch then ctx.log("munição: sem dados de armas"); return end
    ctx.log("munição: " .. armaLoja .. " <- " .. municaoLoja)
    ch:UpdateAttachmentForWeapon(id("HS3StoreItemAsset", armaLoja), id("HS3StoreItemAsset", municaoLoja))
    ctx.emit("mochila", { acao = "municao", arma = armaLoja, municao = municaoLoja })
end

-- acessório (mira, silenciador, freio de boca, bipé): montar usa a mesma função da munição
function M.acessorio(ctx, armaLoja, acessorioLoja)
    if not M.pronto() then ctx.log("mochila: fora da reserva, ignorado"); return end
    local ch = chunkArmas(); if not ch then ctx.log("acessório: sem dados de armas"); return end
    ctx.log("acessório: " .. armaLoja .. " <- " .. acessorioLoja)
    ch:UpdateAttachmentForWeapon(id("HS3StoreItemAsset", armaLoja), id("HS3StoreItemAsset", acessorioLoja))
    ctx.emit("mochila", { acao = "acessorio", arma = armaLoja, acessorio = acessorioLoja })
end

function M.tirarAcessorio(ctx, armaLoja, acessorioLoja)
    if not M.pronto() then ctx.log("mochila: fora da reserva, ignorado"); return end
    local ch = chunkArmas(); if not ch then ctx.log("acessório: sem dados de armas"); return end
    ctx.log("acessório: tirando " .. acessorioLoja .. " de " .. armaLoja)
    ch:RemoveAttachmentForWeaponId(id("HS3StoreItemAsset", armaLoja), id("HS3StoreItemAsset", acessorioLoja))
    ctx.emit("mochila", { acao = "tirar_acessorio", arma = armaLoja, acessorio = acessorioLoja })
end

-- grava no save do jogo e relê (chamado uma vez no fim de uma série de trocas)
function M.salvar(ctx)
    if not M.pronto() then return end
    local im = inv()
    if im then pcall(function() im:SaveInventoryData(true) end) end
    local ch = chunkArmas()
    if ch then pcall(function() ch:SaveWeaponCosmetics() end) end
    local r = M.ler(ctx)
    M.armas(ctx)
    return r
end

return M
