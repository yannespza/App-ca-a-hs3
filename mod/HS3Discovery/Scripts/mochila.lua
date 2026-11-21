-- Mochila (inventário levado para a caçada) e munição de cada arma.
-- Recarregado a cada comando (pode ser atualizado com o jogo aberto).
-- Regra de segurança: nada de guardar objetos do jogo entre chamadas; tudo é buscado na hora.
local M = {}

local TIPOS = { "Inventory.Weapon", "Inventory.Objects", "Inventory.GPS" }
local TAG_MUNICAO = "Cosmetics.Weapons.Attachments.Ammo"

local function tag(nome) return { TagName = FName(nome) } end
local function id(tipo, nome) return { PrimaryAssetType = { Name = FName(tipo) }, PrimaryAssetName = FName(nome) } end
local function idStr(pid)
    local ok, s = pcall(function() return pid.PrimaryAssetType.Name:ToString() .. ":" .. pid.PrimaryAssetName:ToString() end)
    return ok and s or nil
end
local function inv() return FindFirstOf("HS3InventoryManagerComponent") end
local function chunkArmas() return FindFirstOf("HS3WeaponSaveSlotChunk") end

function M.ler(ctx)
    local log, tagName = ctx.log, ctx.tagName
    local r = { ts = os.time(), slots = {}, itens = {}, municao = {}, erros = {} }
    local im = inv()
    if not im then r.erros[#r.erros + 1] = "sem inventário"; ctx.writeFile(ctx.DIR .. "mochila.json", ctx.json(r)); return r end
    for _, t in ipairs(TIPOS) do
        local ok, n = pcall(function() return im:GetNumSlotsForType(tag(t), false) end)
        if ok then r.slots[t] = n else r.erros[#r.erros + 1] = "slots " .. t .. ": " .. tostring(n) end
    end
    pcall(function()
        im.CachedInventoryList.Items:ForEach(function(_, e)
            local it = e:get()
            r.itens[#r.itens + 1] = { item = idStr(it.SaveInfo.AssetId), tipo = tagName(it.SaveInfo.Type),
                                      idx = it.SaveInfo.SlotTypeIndex, cargas = it.Charges }
        end)
    end)
    local ch = chunkArmas()
    if ch then
        local ok, e = pcall(function()
            local lista = {}
            ch:GetAllWeaponStoreIds(lista)
            for _, v in ipairs(lista) do
                local wid = v:get()
                local nome = wid.PrimaryAssetName:ToString()
                -- todos os acessórios salvos da arma (luneta, bipé, munição…); o app separa a munição
                local anexos = {}
                pcall(function()
                    local out = {}
                    ch:GetAllAttachmentStoreIdsForWeapon(wid, out)
                    for _, a in pairs(out) do
                        local v = a; pcall(function() v = a:get() end)
                        local nomeA = idStr(v)
                        if nomeA then anexos[#anexos + 1] = nomeA:match(":(.+)$") or nomeA end
                    end
                end)
                r.municao[nome] = anexos
            end
        end)
        if not ok then r.erros[#r.erros + 1] = "munição: " .. tostring(e) end
    else
        r.erros[#r.erros + 1] = "sem HS3WeaponSaveSlotChunk"
    end
    ctx.writeFile(ctx.DIR .. "mochila.json", ctx.json(r))
    log(string.format("mochila lida: %d itens, slots arma=%s objeto=%s gps=%s, %d armas com config",
        #r.itens, tostring(r.slots["Inventory.Weapon"]), tostring(r.slots["Inventory.Objects"]),
        tostring(r.slots["Inventory.GPS"]), (function() local n = 0; for _ in pairs(r.municao) do n = n + 1 end; return n end)()))
    return r
end

-- põe um item (HS3InventoryItemDefinition:ID_x) no espaço idx (0, 1, 2…) do tipo
function M.por(ctx, item, tipo, idx)
    local im = inv(); if not im then error("sem inventário") end
    local t, n = item:match("^([^:]+):(.+)$")
    local slot = im:GetSlotIndexFromTypeIndex(tag(tipo), idx, false)
    ctx.log(string.format("mochila: pondo %s em %s #%d (slot %s)", n, tipo, idx, tostring(slot)))
    im:AddItemAsset(id(t, n), tag(tipo), slot, true, false)
    pcall(function() im:SaveInventoryData(true) end)
    ctx.emit("mochila", { acao = "por", item = item, tipo = tipo, idx = idx })
    return M.ler(ctx)
end

function M.tirar(ctx, item)
    local im = inv(); if not im then error("sem inventário") end
    local t, n = item:match("^([^:]+):(.+)$")
    ctx.log("mochila: tirando " .. n)
    im:RemoveItemAsset(id(t, n))
    pcall(function() im:SaveInventoryData(true) end)
    ctx.emit("mochila", { acao = "tirar", item = item })
    return M.ler(ctx)
end

-- troca a munição carregada numa arma (ids de loja: DA_..._StoreItem / D_Ammo_..._StoreItem)
function M.municao(ctx, armaLoja, municaoLoja)
    local ch = chunkArmas(); if not ch then error("sem HS3WeaponSaveSlotChunk") end
    ctx.log("munição: " .. armaLoja .. " <- " .. municaoLoja)
    ch:UpdateAttachmentForWeapon(id("HS3StoreItemAsset", armaLoja), id("HS3StoreItemAsset", municaoLoja))
    pcall(function() ch:SaveWeaponCosmetics() end)
    ctx.emit("mochila", { acao = "municao", arma = armaLoja, municao = municaoLoja })
    return M.ler(ctx)
end

return M
