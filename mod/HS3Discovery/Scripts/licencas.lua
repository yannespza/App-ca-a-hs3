-- Licenças de caça da reserva atual: quantos animais já foram usados de cada licença e compra de licença nova.
-- Recarregado a cada comando. Testado em 22/11/2026 (Colorado):
--  * HuntingLicenseControllerComp.LocalLicenseCache = licenças da reserva atual (espécie + ClaimedAmount = animais já usados);
--  * PurchaseLicenseForCurrentWorld(tag, false, false) renova a licença (usados volta a 0), mas NÃO cobra;
--  * TryPurchaseStoreItem e TryAddCurrency negativo não funcionam para isso -> o mod desconta o preço direto no saldo salvo.
local M = {}

local function valido(o)
    if not o then return false end
    local ok, v = pcall(function() return o:IsValid() end)
    return ok and v
end
local function controle()
    local lc = FindFirstOf("HuntingLicenseControllerComp")
    if valido(lc) then return lc end
end
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
local function usados(lc, tag)
    local n
    pcall(function()
        lc.LocalLicenseCache:ForEach(function(_, e)
            local c = e:get()
            if c.AnimalTag.TagName:ToString() == tag then n = c.ClaimedAmount end
        end)
    end)
    return n
end

function M.ler(ctx)
    local lc = controle()
    if not lc then return end
    local r = { ts = os.time(), licencas = {}, permitidas = {} }
    pcall(function()
        local pawn = FindFirstOf("HS3PlayerController").Pawn
        r.mapa = pawn:GetFullName():match("/([^/%.]+)%.")
    end)
    pcall(function()
        lc.LocalLicenseCache:ForEach(function(_, e)
            local c = e:get()
            r.licencas[#r.licencas + 1] = { tag = c.AnimalTag.TagName:ToString(), usados = c.ClaimedAmount }
        end)
    end)
    for _, l in ipairs(r.licencas) do
        pcall(function() l.ilimitada = lc:IsUnlimitedLicense({ TagName = FName(l.tag) }) and true or false end)
    end
    pcall(function()
        lc.AllowedLicenceForCurrentMap.GameplayTags:ForEach(function(_, t) r.permitidas[#r.permitidas + 1] = t:get().TagName:ToString() end)
    end)
    ctx.writeFile(ctx.DIR .. "licencas.json", ctx.json(r))
    return r
end

-- compra (renova) a licença de uma espécie na reserva atual e desconta o preço
function M.comprar(ctx, tag, preco, ref)
    local lc = controle()
    local s = saldo()
    local fim = function(ok, motivo)
        ctx.log(string.format("licença %s ($%d): %s %s", tag, preco, ok and "OK" or "FALHOU", motivo or ""))
        ctx.emit("compra", { item = tag, licenca = true, ok = ok, ref = ref, erro = motivo, depois = s and s.CurrencyAmount })
        M.ler(ctx)
    end
    if not lc or not s then return fim(false, "jogo não está pronto") end
    if s.CurrencyAmount < preco then return fim(false, "créditos insuficientes") end
    local antes = usados(lc, tag)
    local ok, e = pcall(function() lc:PurchaseLicenseForCurrentWorld({ TagName = FName(tag) }, false, false) end)
    local depois = usados(lc, tag)
    if not ok or depois == nil or (antes ~= nil and depois >= antes and antes > 0) then
        return fim(false, ok and "o jogo não renovou a licença" or tostring(e))
    end
    s = saldo()
    s.CurrencyAmount = s.CurrencyAmount - preco
    fim(true)
end

return M
