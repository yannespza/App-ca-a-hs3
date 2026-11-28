-- Teste: cobrar $20 escrevendo direto no saldo salvo (HS3StoreSaveGame.CurrencyTypeList).
local function entrada()
    local alvo
    FindFirstOf("HS3StoreSaveGame").CurrencyTypeList:ForEach(function(_, e)
        local it = e:get()
        if it.CurrencyType.TagName:ToString() == "Currency.Credits" then alvo = it end
    end)
    return alvo
end
local a = entrada().CurrencyAmount
local ok, e = pcall(function() local it = entrada(); it.CurrencyAmount = it.CurrencyAmount - 20 end)
local d = entrada().CurrencyAmount
return string.format("cobrar direto ok=%s err=%s creditos %s->%s", tostring(ok), tostring(e), tostring(a), tostring(d))
