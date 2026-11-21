-- Fase 1b: exportar mapa e névoa, listar pontos de interesse, testar pino do jogo
local out = {}
local function add(k, v) out[#out+1] = k .. ": " .. tostring(v) end
local function try(nome, f) local ok, e = pcall(f); add(nome, ok and "ok" or ("ERRO " .. tostring(e))) end
local DEV = HS3.dir .. "dev\\"
local pc = FindFirstOf("HS3PlayerController")
local KRL = StaticFindObject("/Script/Engine.Default__KismetRenderingLibrary")
add("krl", KRL and KRL:IsValid())

-- 1) Exportar textura do minimapa direto
try("export_minimap_direto", function()
    local tex = StaticFindObject("/HS3DefaultMaps/Terrain/Texas_a/Map/ZoomLevel1/T_Texas_a_MiniMap.T_Texas_a_MiniMap")
    add("minimap_tex", tex and tex:IsValid() and tex:GetFullName() or "nao achou")
    pcall(function() add("minimap_size", tex:Blueprint_GetSizeX() .. "x" .. tex:Blueprint_GetSizeY()) end)
    KRL:ExportTexture2D(pc, tex, DEV, "mapa_texas_direto.png")
end)

-- 2) Exportar via render target (desenha a textura num canvas e salva)
try("export_minimap_rt", function()
    local tex = StaticFindObject("/HS3DefaultMaps/Terrain/Texas_a/Map/ZoomLevel1/T_Texas_a_MiniMap.T_Texas_a_MiniMap")
    local rt = KRL:CreateRenderTarget2D(pc, 4096, 4096, 2, {R=0,G=0,B=0,A=1}, false, false)
    add("rt", rt and rt:IsValid())
    local params = {}
    local canvas, size, ctx = {}, {}, {}
    KRL:BeginDrawCanvasToRenderTarget(pc, rt, canvas, size, ctx)
    add("canvas_tipo", type(canvas) .. " " .. tostring(canvas.Canvas or canvas[1] or canvas))
    local cv = canvas.Canvas or canvas
    if type(cv) == "table" then for k, v in pairs(cv) do add("canvas_k", tostring(k) .. "=" .. tostring(v)) end end
    pcall(function()
        local c = (type(cv) == "userdata") and cv or cv.Canvas
        c:K2_DrawTexture(tex, {X=0,Y=0}, {X=4096,Y=4096}, {X=0,Y=0}, {X=1,Y=1}, {R=1,G=1,B=1,A=1}, 0, 0.0, {X=0.5,Y=0.5})
    end)
    KRL:EndDrawCanvasToRenderTarget(pc, ctx.Context or ctx)
    KRL:ExportRenderTarget(pc, rt, DEV, "mapa_texas_rt.png")
end)

-- 3) Névoa: exportar a textura e salvar uma amostra dos dados
try("export_fog_tex", function()
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    KRL:ExportTexture2D(pc, nav.HardFogTexture, DEV, "nevoa_texas.png")
end)
try("fog_amostra", function()
    local save = FindFirstOf("NavigationSaveData")
    save.FogOfWarLists:ForEach(function(_, e)
        local f = e:get()
        local nome = f.LevelName:ToString()
        if nome:find("Texas") then
            local t0 = os.clock()
            local linhas = {}
            local arr = f.FogArray
            for y = 0, 255 do
                local row = {}
                for x = 0, 255 do
                    row[#row+1] = string.format("%02x", arr[(y * 8) * 2048 + (x * 8) + 1])
                end
                linhas[#linhas+1] = table.concat(row)
            end
            local fh = io.open(DEV .. "nevoa_texas_256.txt", "w")
            fh:write(table.concat(linhas, "\n")); fh:close()
            add("fog_tempo_s", os.clock() - t0)
        end
    end)
end)

-- 4) Pontos de interesse com posição e estado de descoberta
try("pois", function()
    local estados = {}
    FindFirstOf("NavigationSaveData").DiscoverStatusLists:ForEach(function(_, e)
        local d = e:get()
        if d.LevelName:ToString():find("Texas") then
            d.DiscoveryStatesList:ForEach(function(_, s)
                local st = s:get()
                estados[st.ActorHash] = HS3.tagName(st.DiscoveryStatus)
            end)
        end
    end)
    local lista = {}
    FindFirstOf("NavigationContentComponent").NavigationActorDataMap:ForEach(function(k, v)
        local tipo = k:get().PrimaryAssetName:ToString()
        if tipo ~= "DA_Herd_MapIconData" then
            v:get().ActorDataArray:ForEach(function(_, e)
                local a = e:get()
                local t = a.Transform.Translation
                local nome = ""
                pcall(function() nome = a.IconNameOverride:ToString() end)
                lista[#lista+1] = { tipo = tipo, hash = a.Hash, nome = nome, x = t.X, y = t.Y, z = t.Z, estado = estados[a.Hash] }
            end)
        end
    end)
    local fh = io.open(DEV .. "pois_texas.json", "w")
    fh:write(HS3.json(lista)); fh:close()
    add("pois_total", #lista)
    local n = 0; for _ in pairs(estados) do n = n + 1 end
    add("estados_total", n)
end)

-- 5) Pino rápido de teste: 300 m ao norte (+X) do jogador
try("pino_teste", function()
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    local loc = pc.Pawn:K2_GetActorLocation()
    local id = { PrimaryAssetType = { Name = FName("NavigationIconData") }, PrimaryAssetName = FName("DA_QuickWaypoint_MapIconData") }
    local tr = { Rotation = {X=0,Y=0,Z=0,W=1}, Translation = {X=loc.X + 30000, Y=loc.Y, Z=loc.Z}, Scale3D = {X=1,Y=1,Z=1} }
    nav:Server_AddQuickWaypoint(id, tr)
    local q = nav.QuickWaypoint.Transform.Translation
    add("pino_depois", string.format("%.0f,%.0f,%.0f (jogador %.0f,%.0f)", q.X, q.Y, q.Z, loc.X, loc.Y))
end)

local fh = io.open(DEV .. "resultado_fase1b.txt", "w")
fh:write(table.concat(out, "\n")); fh:close()
return #out
