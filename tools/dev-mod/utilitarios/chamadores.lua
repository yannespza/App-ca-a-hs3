-- Lê, para cada chamador e chamariz da loja, quais espécies ele atrai (AnimalTags da classe *Instance*),
-- o raio e o sexo. Grava chamadores.json na pasta do mod. Rodar uma vez numa reserva: script chamadores.lua
local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
local log = {}

local function valido(o) local ok, v = pcall(function() return o and o:IsValid() end); return ok and v end
local function carregarCaminho(c)
    local o
    pcall(function() o = StaticFindObject(c) end)
    if not valido(o) then pcall(function() o = LoadAsset(c) end) end
    if not valido(o) then pcall(function() o = StaticFindObject(c) end) end
    return valido(o) and o or nil
end
local function tags(cont)
    local l = {}
    pcall(function() cont.GameplayTags:ForEach(function(_, t) l[#l + 1] = t:get().TagName:ToString() end) end)
    return l
end

local saida = {}
local r = {}
KSL:GetPrimaryAssetIdList({ Name = FName("HS3StoreItemAsset") }, r)
for _, v in ipairs(r) do
    local id = v:get()
    local nome = id.PrimaryAssetName:ToString()
    if nome:find("Caller") or nome:find("Decoy") then
        local loja
        pcall(function() loja = KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(id)) end)
        if valido(loja) then
            local caminho = loja:GetFullName():match("^%S+%s+(.+)$") or ""
            local pasta = caminho:match("^(.*/)") or ""
            local item = ""
            pcall(function() item = loja.ItemAssetID.PrimaryAssetName:ToString() end)
            local base = item:gsub("^ID_", "")                 -- Caller_Deer / DecoyElk
            local resto = base:gsub("^Caller_", ""):gsub("^Decoy", "")  -- Deer / Elk
            local candidatos = {
                "B_CallerInstance_" .. resto, "B_DecoyInstance_" .. resto, "B_" .. base .. "Instance", "B_" .. base .. "_Instance",
                "B_DecoyInstance" .. resto, "B_" .. base, "BP_" .. base, "B_Decoy_" .. resto,
            }
            local achou = nil
            local pastas = { pasta, pasta .. "Data/", pasta .. base .. "/Data/", pasta .. base .. "/" }
            for _, c in ipairs(candidatos) do
              for _, pp in ipairs(pastas) do
                if achou then break end
                local cls = carregarCaminho(pp .. c .. "." .. c .. "_C")
                if cls then
                    local cdo
                    pcall(function() cdo = cls:GetCDO() end)
                    if valido(cdo) then
                        local t = {}
                        pcall(function() t = tags(cdo.AnimalTags) end)
                        if #t > 0 then
                            local e = { loja = nome, item = item, classe = c, especies = t }
                            pcall(function() e.raio_m = cdo.DetectionRadiusMeter end)
                            pcall(function() e.sexo = cdo.AnimalGender end)
                            saida[#saida + 1] = e
                            achou = c
                            break
                        else
                            -- procura qualquer propriedade com tags de animais
                            local e = { loja = nome, item = item, classe = c, especies = {}, props = {} }
                            local k = cls
                            while valido(k) and #e.especies == 0 do
                                pcall(function()
                                    k:ForEachProperty(function(prop)
                                        local pn = prop:GetFName():ToString()
                                        local tp = prop:GetClass():GetFName():ToString()
                                        e.props[#e.props + 1] = pn .. ":" .. tp
                                        if tp == "StructProperty" then
                                            local l = {}
                                            pcall(function() l = tags(cdo[pn]) end)
                                            for _, t in ipairs(l) do
                                                if t:find("^Animals%.") then e.especies[#e.especies + 1] = t end
                                            end
                                            if #l > 0 then e.props[#e.props] = e.props[#e.props] .. "=" .. table.concat(l, ",") end
                                        elseif tp == "FloatProperty" or tp == "DoubleProperty" or tp == "IntProperty" then
                                            pcall(function() e.props[#e.props] = e.props[#e.props] .. "=" .. tostring(cdo[pn]) end)
                                        end
                                    end)
                                end)
                                local sup; pcall(function() sup = k:GetSuperStruct() end)
                                local sn = ""; pcall(function() sn = sup:GetFName():ToString() end)
                                if sn == "Actor" or sn == "Object" or sn == "" then break end
                                k = sup
                            end
                            saida[#saida + 1] = e
                            achou = c
                        end
                    end
                end
              end
              if achou then break end
            end
            if not achou then log[#log + 1] = nome .. ": nada em " .. pasta end
        end
    end
end

local f = io.open(HS3.dir .. "chamadores.json", "wb")
f:write(HS3.json({ ts = os.time(), itens = saida, avisos = log }))
f:close()
return #saida .. " itens, " .. #log .. " avisos"
