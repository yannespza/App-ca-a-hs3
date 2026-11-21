-- Exploração da Fase 1: animais ao vivo, navegação/waypoints, mapa e névoa
local out = {}
local function add(k, v) out[#out+1] = k .. ": " .. tostring(v) end
local function try(nome, f) local ok, e = pcall(f); if not ok then add("ERRO " .. nome, e) end end

-- 1) Animais carregados
try("animais", function()
    local lista = FindAllOf("AnimalCharacter") or {}
    add("animais_carregados", #lista)
    for i, a in ipairs(lista) do
        if i > 40 then break end
        local id, cls, loc = "?", "?", nil
        pcall(function() id = a.EcoSimCreatureId end)
        pcall(function() cls = a:GetClass():GetFName():ToString() end)
        pcall(function() loc = a:K2_GetActorLocation() end)
        add("animal", string.format("id=%s %s %s", tostring(id), cls,
            loc and string.format("%.0f,%.0f,%.0f", loc.X, loc.Y, loc.Z) or "sem pos"))
    end
end)

-- 2) Navegação do jogador
try("navegacao", function()
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    add("nav_comp", nav and nav:IsValid() and nav:GetFullName() or "nao achou")
    if nav and nav:IsValid() then
        add("max_waypoints", nav.MaxAllowedWaypoints)
        add("fog_size", nav.FogOfWarArraySize)
        add("discover_radius", nav.DiscoverRadius)
        pcall(function() add("hard_fog_tex", nav.HardFogTexture:GetFullName()) end)
        pcall(function() add("texture_data_len", nav.TextureData:GetArrayNum()) end)
        pcall(function()
            local q = nav.QuickWaypoint
            add("quick_hash", q.Hash)
            add("quick_icon", q.MapIconDataId.PrimaryAssetType.Name:ToString() .. ":" .. q.MapIconDataId.PrimaryAssetName:ToString())
            local t = q.Transform.Translation
            add("quick_pos", string.format("%.0f,%.0f,%.0f", t.X, t.Y, t.Z))
        end)
        pcall(function()
            nav.Waypoints:ForEach(function(i, e)
                local w = e:get()
                local t = w.Transform.Translation
                add("waypoint", w.MapIconDataId.PrimaryAssetType.Name:ToString() .. ":" .. w.MapIconDataId.PrimaryAssetName:ToString() ..
                    string.format(" %.0f,%.0f,%.0f", t.X, t.Y, t.Z))
            end)
        end)
    end
    local imw = FindFirstOf("InteractiveMapWidget")
    if imw and imw:IsValid() then
        pcall(function() add("widget_quick_id", imw.QuickWaypointNavigationActorDataId.PrimaryAssetType.Name:ToString() .. ":" .. imw.QuickWaypointNavigationActorDataId.PrimaryAssetName:ToString()) end)
        pcall(function() add("widget_wp_id", imw.WaypointNavigationActorDataId.PrimaryAssetType.Name:ToString() .. ":" .. imw.WaypointNavigationActorDataId.PrimaryAssetName:ToString()) end)
    else add("map_widget", "nao carregado") end
end)

-- 3) Dados do mapa
try("mapa", function()
    local assets = FindAllOf("LevelNavigationDataAsset") or {}
    add("level_nav_assets", #assets)
    for _, a in ipairs(assets) do
        pcall(function() add("mapa_nome", a.MapName:ToString()) end)
        pcall(function() add("mapa_tamanho", string.format("%.0f x %.0f", a.MapSize.X, a.MapSize.Y)) end)
        pcall(function() add("fog_ativa", a.bShouldUseFogOfWar) end)
        pcall(function()
            a.DetailTexturesArray:ForEach(function(i, e)
                local z = e:get()
                add("zoom", string.format("escala=%.3f texturas=%d", z.Scale, z.Textures:GetArrayNum()))
            end)
        end)
        pcall(function() add("brush_res", a.MapBrush.ResourceObject:GetFullName()) end)
    end
    local save = FindFirstOf("NavigationSaveData")
    if save and save:IsValid() then
        save.FogOfWarLists:ForEach(function(i, e)
            local f = e:get(); add("fog_nivel", f.LevelName:ToString() .. " bytes=" .. f.FogArray:GetArrayNum())
        end)
        save.DiscoverStatusLists:ForEach(function(i, e)
            local f = e:get(); add("descobertas", f.LevelName:ToString() .. " itens=" .. f.DiscoveryStatesList:GetArrayNum())
        end)
    end
    local navc = FindFirstOf("NavigationContentComponent")
    if navc and navc:IsValid() then
        local n = 0
        navc.NavigationActorDataMap:ForEach(function(k, v)
            n = n + 1
            local key = k:get()
            if n <= 40 then
                add("nav_tipo", key.PrimaryAssetType.Name:ToString() .. ":" .. key.PrimaryAssetName:ToString() .. " qtd=" .. v:get().ActorDataArray:GetArrayNum())
            end
        end)
        add("nav_tipos_total", n)
    end
end)

local f = io.open(HS3.dir .. "dev\\resultado_explorar.txt", "w")
if f then f:write(table.concat(out, "\n")); f:close() end
return #out .. " linhas"
