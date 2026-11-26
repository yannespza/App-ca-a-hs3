-- Sonda 2 (só leitura): zonas de animais no mapa do jogo (descobertas ou não), contratos dos agentes
-- (preço, dificuldade, prazo, efeitos), níveis de reputação e máximo de munição. Grava dev\sonda_estudo.txt.
local L = {}
local function p(s) L[#L + 1] = s end
local function tag(t)
    local ok, v = pcall(function() return t.TagName:ToString() end)
    return ok and v or "?"
end
local function curto(o)
    local ok, v = pcall(function() return o:GetFullName() end)
    if not ok or not v then return "?" end
    return v:match("([^%.]+)$") or v
end
local function classe(o)
    local ok, v = pcall(function() return o:GetClass():GetFName():ToString() end)
    return ok and v or "?"
end
local function texto(t)
    local ok, v = pcall(function() return t:ToString() end)
    return ok and v or "?"
end

-- A) zonas de animais no mapa do jogo (DA_Herd_MapIconData) e estado de descoberta
pcall(function()
    local estados = {}
    local save = FindFirstOf("NavigationSaveData")
    if save then
        save.DiscoverStatusLists:ForEach(function(_, e)
            local d = e:get()
            d.DiscoveryStatesList:ForEach(function(_, st)
                local s = st:get()
                estados[s.ActorHash] = tag(s.DiscoveryStatus)
            end)
        end)
    end
    local content = FindFirstOf("NavigationContentComponent")
    local tipos, amostras = {}, 0
    content.NavigationActorDataMap:ForEach(function(k, v)
        local tipo = "?"
        pcall(function() tipo = k:get().PrimaryAssetName:ToString() end)
        local n, desc = 0, 0
        v:get().ActorDataArray:ForEach(function(_, e)
            local a = e:get()
            n = n + 1
            local est = estados[a.Hash]
            if est then desc = desc + 1 end
            if tipo == "DA_Herd_MapIconData" and amostras < 25 then
                amostras = amostras + 1
                local t = a.Transform.Translation
                p(string.format("HERD hash=%s %.0f %.0f estado=%s", tostring(a.Hash), t.X, t.Y, tostring(est)))
            end
        end)
        tipos[#tipos + 1] = string.format("TIPO %s total=%d com_estado=%d", tipo, n, desc)
    end)
    for _, t in ipairs(tipos) do p(t) end
end)

-- B) contratos carregados: preço, dificuldade, prazo, efeitos (genética?), agente
pcall(function()
    for _, c in ipairs(FindAllOf("HS3ContractDataAsset") or {}) do
        pcall(function()
            local efs = {}
            pcall(function()
                local e = c.Effects
                for j = 1, #e do
                    local ef = e[j]
                    local extra = ""
                    pcall(function() extra = " herd=" .. tostring(ef.HerdId) end)
                    pcall(function() extra = extra .. " fator=" .. tostring(ef.Factor) end)
                    efs[#efs + 1] = classe(ef) .. extra
                end
            end)
            p(string.format("CDA %s | %s | %s | preço=%s | %s | prazo=%s %s s | efeitos: %s", curto(c), tag(c.VendorTag), texto(c.Title),
                tostring(c.Price), tag(c.ContractDifficulty), tostring(c.bIsTimeLimited), tostring(c.ContractDurationInSeconds), table.concat(efs, "; ")))
        end)
    end
end)

-- C) contratos liberados por nível (caminho do contrato)
pcall(function()
    for _, n in ipairs(FindAllOf("HS3ContractNPCDefinitionDataAsset") or {}) do
        local u = n.ReputationContractUnlocks
        for j = 1, #u do
            local x = u[j]
            local cam = "?"
            for _, f in ipairs({
                function() return x.UnlockedContract:ToString() end,
                function() return tostring(x.UnlockedContract) end,
                function() return x.UnlockedContract.SoftObjectPtr.ObjectID.AssetPath.AssetName:ToString() end,
                function() return x.UnlockedContract.ObjectID.AssetPath.AssetName:ToString() end,
                function() return x.UnlockedContract:Get():GetFullName() end,
            }) do
                local ok, v = pcall(f)
                if ok and v and v ~= "" and not tostring(v):find("^userdata") and not tostring(v):find("^UE4SS") then cam = tostring(v); break end
            end
            p(string.format("UNLOCK %s nv%s %s", tag(n.NPCVendorTag), tostring(x.LevelToUnlockThisContract), cam))
        end
    end
end)

-- D) níveis de reputação (quantos pontos por nível)
pcall(function()
    local s = StaticFindObject("/Script/HS3CoreRuntime.Default__HS3ContractDeveloperSettings")
    local r = s.ReputationLevelDefinitions
    local t = {}
    for j = 1, #r do t[#t + 1] = tostring(r[j].ReputationLevel) .. "=" .. tostring(r[j].RequiredReputationAmount) end
    p("NIVEIS " .. table.concat(t, ", ") .. " | teto=" .. tostring(s.ReputationUpperBoundCap))
end)

-- E) máximo de munição: estatísticas iniciais dos itens das armas (fragmentos da definição)
pcall(function()
    for _, it in ipairs(FindAllOf("HS3InventoryItemInstance") or {}) do
        pcall(function()
            local nome = it.ItemDef:GetFName():ToString()
            if not (nome:find("Winchester") or nome:find("Linergie") or nome:find("Verney")) then return end
            local cdo = it.ItemDef:GetCDO()
            local fr = cdo.Fragments
            for j = 1, #fr do
                local f = fr[j]
                local linha = "FRAG " .. nome .. " " .. classe(f)
                pcall(function()
                    f.InitialItemStats:ForEach(function(k, v)
                        linha = linha .. " | " .. tag(k:get()) .. "=" .. tostring(v:get())
                    end)
                end)
                p(linha)
            end
        end)
    end
end)

local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_estudo.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
