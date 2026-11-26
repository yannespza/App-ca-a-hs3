-- Sonda 3 (só leitura): onde o jogo guarda quais zonas de necessidade foram descobertas.
local L = {}
local function p(s) L[#L + 1] = s end
local function tag(t) local ok, v = pcall(function() return t.TagName:ToString() end); return ok and v or "?" end
local estados = {}
pcall(function()
    FindFirstOf("NavigationSaveData").DiscoverStatusLists:ForEach(function(_, e)
        e:get().DiscoveryStatesList:ForEach(function(_, st)
            local s = st:get(); estados[s.ActorHash] = tag(s.DiscoveryStatus)
        end)
    end)
end)
local nEst = 0; for _ in pairs(estados) do nEst = nEst + 1 end
p("ESTADOS no save: " .. nEst)
-- filhos no mapa (zona -> rastros?)
pcall(function()
    local n, ce = 0, 0
    FindFirstOf("NavigationContentComponent").NavigationActorDataChildsMap:ForEach(function(k, v)
        v:get().ActorDataArray:ForEach(function(_, e)
            n = n + 1
            if estados[e:get().Hash] then ce = ce + 1 end
        end)
    end)
    p("FILHOS no mapa: " .. n .. " com estado: " .. ce)
end)
local zonas = FindAllOf("AnimalZoneBase") or {}
local resumo = { total = 0, hash_com_estado = 0, com_rastro_true = 0, rastros = 0, rastros_true = 0, rastro_com_estado = 0 }
for i, z in ipairs(zonas) do
    pcall(function()
        local zt = tag(z.ZoneTag)
        if not (zt:find("Eating") or zt:find("Drinking") or zt:find("Sleeping")) or zt:find("Burrow") then return end
        resumo.total = resumo.total + 1
        local nav = z.NavigationActorComponent
        local h = nav.NavigationActorData.Hash
        local est = estados[h]
        if est then resumo.hash_com_estado = resumo.hash_com_estado + 1 end
        local t, tt, ts = 0, 0, 0
        pcall(function()
            nav.Traces:ForEach(function(k, v)
                t = t + 1
                if v:get() then tt = tt + 1 end
                pcall(function()
                    local tr = k:get()
                    for _, c in ipairs({ "NavigationActorComponent", "NavigationComponent" }) do
                        local okc, comp = pcall(function() return tr[c] end)
                        if okc and comp and comp:IsValid() and estados[comp.NavigationActorData.Hash] then ts = ts + 1; break end
                    end
                end)
            end)
        end)
        resumo.rastros = resumo.rastros + t; resumo.rastros_true = resumo.rastros_true + tt; resumo.rastro_com_estado = resumo.rastro_com_estado + ts
        if tt > 0 then resumo.com_rastro_true = resumo.com_rastro_true + 1 end
        if i <= 400 and (est or tt > 0 or ts > 0) then
            local l = z:K2_GetActorLocation()
            p(string.format("ZONA %s %s hash=%s estado=%s rastros=%d/%d/%d %.0f %.0f", tag(z.CreatureTag), zt, tostring(h), tostring(est), tt, t, ts, l.X, l.Y))
        end
    end)
end
p(string.format("RESUMO zonas=%d hash_com_estado=%d zonas_com_rastro_visto=%d rastros=%d vistos=%d rastro_com_estado=%d",
    resumo.total, resumo.hash_com_estado, resumo.com_rastro_true, resumo.rastros, resumo.rastros_true, resumo.rastro_com_estado))
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_zonas.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
