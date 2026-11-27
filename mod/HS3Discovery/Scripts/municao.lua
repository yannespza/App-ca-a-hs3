-- Recarregar a reserva de munição das armas pelo app (v0.1.42). Recarregado a cada comando.
-- Testado em 26/11/2026 (Texas): a reserva fica em HS3InventoryItemInstance.StatTags (Inventory.Weapon.Properties.Ammo.Spare);
-- o máximo vem da definição da arma (fragmento InventoryFragment_SetStats -> InitialItemStats); AddStatTagStack soma.
local M = {}
local SPARE = "Inventory.Weapon.Properties.Ammo.Spare"

local function saldo()
    local alvo
    pcall(function()
        FindFirstOf("HS3StoreSaveGame").CurrencyTypeList:ForEach(function(_, e)
            local it = e:get()
            if it.CurrencyType.TagName:ToString() == "Currency.Credits" then alvo = it end
        end)
    end)
    return alvo
end

-- máximo da reserva definido pelo jogo para a arma (nil se não achar)
local function maximo(it)
    local m
    pcall(function()
        local fr = it.ItemDef:GetCDO().Fragments
        for j = 1, #fr do
            pcall(function()
                fr[j].InitialItemStats:ForEach(function(k, v)
                    if k:get().TagName:ToString() == SPARE then m = v:get() end
                end)
            end)
            if m then break end
        end
    end)
    return m
end

-- precoBala: créditos por bala reposta (0 = de graça)
function M.recarregar(ctx, precoBala, ref)
    local faltas, total = {}, 0
    for _, it in ipairs(FindAllOf("HS3InventoryItemInstance") or {}) do
        pcall(function()
            local st = it.StatTags.Stacks
            for j = 1, #st do
                local s = st[j]
                if s.Tag.TagName:ToString() == SPARE then
                    local mx = maximo(it)
                    local falta = mx and (mx - s.StackCount) or 0
                    if falta > 0 then
                        faltas[#faltas + 1] = { it = it, tag = s.Tag, n = falta, nome = it.ItemDef:GetFName():ToString() }
                        total = total + falta
                    end
                    break
                end
            end
        end)
    end
    local custo = math.floor(total * (precoBala or 0) + 0.5)
    local fim = function(ok, motivo, postas)
        ctx.log(string.format("recarregar munição: %s balas, $%d: %s %s", tostring(postas or 0), custo, ok and "OK" or "FALHOU", motivo or ""))
        ctx.emit("compra", { item = "municao", municao = true, ok = ok, ref = ref, erro = motivo, balas = postas or 0, custo = custo })
    end
    if total == 0 then return fim(true, "reserva já cheia", 0) end
    local s = saldo()
    if custo > 0 and (not s or s.CurrencyAmount < custo) then return fim(false, "créditos insuficientes") end
    local postas = 0
    for _, f in ipairs(faltas) do
        local ok = pcall(function() f.it:AddStatTagStack(f.tag, f.n) end)
        if ok then postas = postas + f.n end
    end
    if postas == 0 then return fim(false, "o jogo não aceitou") end
    custo = math.floor(postas * (precoBala or 0) + 0.5)
    if custo > 0 then s = saldo(); s.CurrencyAmount = s.CurrencyAmount - custo end
    fim(true, nil, postas)
end

return M
