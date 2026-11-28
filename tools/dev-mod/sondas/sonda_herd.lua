-- Sonda (só leitura): ícones de bando/zona do mapa (DA_Herd) — o que identifica espécie, tipo e a zona dona.
local L = {}
local function p(s) L[#L + 1] = s end
local function tags(c)
    local t = {}
    pcall(function() c.GameplayTags:ForEach(function(_, e) t[#t + 1] = e:get().TagName:ToString() end) end)
    return table.concat(t, ",")
end
pcall(function()
    local n = 0
    FindFirstOf("NavigationContentComponent").NavigationActorDataMap:ForEach(function(k, v)
        if k:get().PrimaryAssetName:ToString() ~= "DA_Herd_MapIconData" then return end
        v:get().ActorDataArray:ForEach(function(_, e)
            n = n + 1
            if n > 12 then return end
            local a = e:get()
            local dono = "?"
            pcall(function() dono = a.OwnerSoftPtr:ToString() end)
            if dono == "?" then pcall(function() dono = tostring(a.OwnerSoftPtr.SoftObjectPtr.ObjectID.SubPathString) end) end
            local t = a.Transform.Translation
            p(string.format("HERD hash=%s pai=%s %.0f %.0f extra=[%s] widget=[%s] dono=%s nome=%s", tostring(a.Hash), tostring(a.ParentHash),
                t.X, t.Y, tags(a.ExtraTags), tags(a.WidgetTypeTags), dono, pcall(function() return a.IconNameOverride:ToString() end) and a.IconNameOverride:ToString() or "?"))
        end)
    end)
    p("HERD total " .. n)
end)
-- zonas carregadas: hash do componente e o dono, para cruzar
pcall(function()
    local n = 0
    for _, z in ipairs(FindAllOf("AnimalZoneBase") or {}) do
        n = n + 1
        if n > 6 then break end
        pcall(function()
            local nav = z.NavigationActorComponent
            local l = z:K2_GetActorLocation()
            p(string.format("ZONA hash=%s pai=%s %.0f %.0f %s %s extra=[%s] nome=%s", tostring(nav.NavigationActorData.Hash), tostring(nav.NavigationActorData.ParentHash),
                l.X, l.Y, z.CreatureTag.TagName:ToString(), z.ZoneTag.TagName:ToString(), tags(nav.NavigationActorData.ExtraTags), z:GetFName():ToString()))
        end)
    end
end)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_herd.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
