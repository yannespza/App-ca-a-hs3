-- Sonda: como o jogo transforma as roupas em detecção. Grava dev\sonda_roupa.txt
local L = {}
local function p(s) L[#L + 1] = tostring(s) end
local function v(a) local ok, r = pcall(function() return string.format("base=%.4f atual=%.4f", a.BaseValue, a.CurrentValue) end); return ok and r or "?" end
local d = FindFirstOf("HS3AttributeSet_Detection")
if d and d:IsValid() then
    for _, n in ipairs({ "VisualDetectionFactor", "SoundDetectionFactor", "SmellDetectionFactor", "InHuntingStructure", "MinRawDetectionFactor", "MaxRawDetectionFactor" }) do
        p(n .. ": " .. v(d[n]))
    end
else p("sem HS3AttributeSet_Detection") end
-- configuração dos atributos (o que cada um faz com o valor das roupas)
pcall(function()
    FindFirstOf("HS3AttributeDataAsset").AttributeConfigs:ForEach(function(k, val)
        local nome = k:get().AttributeName:ToString()
        if nome:find("Detection") or nome:find("Sprint") then
            local c = val:get()
            local linha = string.format("cfg %s: min=%s max=%s cosmeticos=%s maxRaw=%s", nome, tostring(c.MinValue), tostring(c.MaxValue),
                tostring(c.bIsInfluencedByCosmetics), tostring(c.MaxRawAttributeValue))
            p(linha)
            pcall(function()
                c.CosmeticInfluencers:ForEach(function(_, e)
                    local i = e:get()
                    p(string.format("   %s maxChange=%s temPadrao=%s padrao=%s", i.CosmeticType.TagName:ToString(), tostring(i.MaxAttributeChange),
                        tostring(i.bHasDefaultValue), tostring(i.DefaultInfluence)))
                end)
            end)
        end
    end)
end)
-- outras classes que podem guardar a fórmula
for _, cn in ipairs({ "HS3DetectionSettings", "HS3CosmeticDetectionSettings", "HS3AttributeDataAsset" }) do
    local o = FindFirstOf(cn)
    if o and o:IsValid() then
        p("== " .. cn .. " " .. o:GetFullName())
        pcall(function()
            o:GetClass():ForEachProperty(function(prop)
                local pn = prop:GetFName():ToString()
                local s = "?"
                pcall(function() s = tostring(o[pn]) end)
                pcall(function() s = string.format("%.4f", o[pn]) end)
                p("  " .. pn .. " (" .. prop:GetClass():GetFName():ToString() .. ") = " .. s)
            end)
        end)
    end
end
local f = io.open(HS3.dir .. "dev\\sonda_roupa.txt", "wb"); f:write(table.concat(L, "\n")); f:close()
return #L .. " linhas"
