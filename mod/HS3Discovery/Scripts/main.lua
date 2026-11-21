-- HS3 Companion - mod UE4SS para Hunting Simulator 3
-- Grava o estado do jogo em state.json (a cada 1 s) e os eventos em events.jsonl.
-- Recebe comandos do HS3Companion.exe pelo arquivo cmd.txt.

local function scriptDir()
    local src = debug.getinfo(1, "S").source:gsub("^@", "")
    return (src:match("^(.*[\\/])Scripts[\\/][^\\/]*$")) or ""
end

local okDir, DIR = pcall(scriptDir)
if not okDir or DIR == "" then
    DIR = [[D:\SteamLibrary\steamapps\common\HS3\HS3\Binaries\Win64\ue4ss\Mods\HS3Discovery\]]
end
local LOG_FILE = DIR .. "output.txt"
local STATE_FILE = DIR .. "state.json"
local EVENTS_FILE = DIR .. "events.jsonl"
local CMD_FILE = DIR .. "cmd.txt"
local VENDOR = "NPC.Vendor.SportsShooter"

------------------------------------------------------------------ utilidades
local function log(msg)
    print("[HS3Companion] " .. msg .. "\n")
    local f = io.open(LOG_FILE, "a")
    if f then f:write(os.date("%Y-%m-%d %H:%M:%S ") .. msg .. "\n"); f:close() end
end

local function jsonEncode(v)
    local t = type(v)
    if t == "nil" then return "null"
    elseif t == "boolean" then return v and "true" or "false"
    elseif t == "number" then
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        if math.type and math.type(v) == "integer" then return tostring(v) end
        return string.format("%.4f", v)
    elseif t == "string" then
        return '"' .. v:gsub('[%c"\\]', function(c)
            local map = { ['"'] = '\\"', ['\\'] = '\\\\', ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t' }
            return map[c] or string.format("\\u%04x", c:byte())
        end) .. '"'
    elseif t == "table" then
        if #v > 0 or next(v) == nil then
            local parts = {}
            for i = 1, #v do parts[i] = jsonEncode(v[i]) end
            return "[" .. table.concat(parts, ",") .. "]"
        end
        local parts = {}
        for k, val in pairs(v) do parts[#parts + 1] = jsonEncode(tostring(k)) .. ":" .. jsonEncode(val) end
        return "{" .. table.concat(parts, ",") .. "}"
    end
    return "null"
end

local function tagName(tag)
    local ok, s = pcall(function() return tag.TagName:ToString() end)
    return ok and s or nil
end

local function valid(o) return o ~= nil and o:IsValid() end

local seq = 0
local function emit(kind, data)
    seq = seq + 1
    data.tipo = kind
    data.seq = seq
    data.ts = os.time()
    local f = io.open(EVENTS_FILE, "a")
    if f then f:write(jsonEncode(data) .. "\n"); f:close() end
end

------------------------------------------------------------------ leitura do estado
local function readState()
    local s = { ok = false, ts = os.time() }
    local pc = FindFirstOf("HS3PlayerController")
    if not valid(pc) then return s end

    -- mapa atual
    pcall(function()
        local full = pc.Pawn:GetFullName()
        s.mapa_caminho = full:match("%s(/[^%.]+)%.")
        s.mapa = s.mapa_caminho and s.mapa_caminho:match("([^/]+)$")
    end)

    -- posição e direção
    pcall(function()
        local loc = pc.Pawn:K2_GetActorLocation()
        s.pos = { x = loc.X, y = loc.Y, z = loc.Z }
        local rot = pc:GetControlRotation()
        s.yaw = rot.Yaw
    end)

    -- moedas
    local store = FindFirstOf("HS3StoreSaveGame")
    if valid(store) then
        s.moedas = {}
        pcall(function()
            store.CurrencyTypeList:ForEach(function(_, e)
                local it = e:get()
                local n = tagName(it.CurrencyType)
                if n then s.moedas[n] = it.CurrencyAmount end
            end)
        end)
        s.pontos_campo = {}
        pcall(function()
            store.LevelSpecificCurrencies:ForEach(function(k, v)
                local name = k:get().PrimaryAssetName:ToString()
                v:get().Currencies:ForEach(function(_, e)
                    local it = e:get()
                    if tagName(it.CurrencyType) == "Currency.Level.FieldPoints" then
                        s.pontos_campo[name] = it.CurrencyAmount
                    end
                end)
            end)
        end)
    end

    -- reputação por mapa
    local rep = FindFirstOf("HS3ReputationSaveSlotChunk")
    if valid(rep) then
        s.reputacao = {}
        pcall(function()
            rep.ReputationSaveDataPerMap:ForEach(function(k, v)
                local name = k:get().PrimaryAssetName:ToString()
                v:get().ReputationPerVendor:ForEach(function(vk, vv)
                    local d = vv:get()
                    s.reputacao[#s.reputacao + 1] = {
                        mapa = name, vendedor = tagName(vk:get()),
                        valor = d.Reputation, sequencia = d.ReputationStreak }
                end)
            end)
        end)
    end

    pcall(function()
        local q = FindFirstOf("NavigationPlayerStateComponent").QuickWaypoint
        if q.Hash ~= 0 then
            local t = q.Transform.Translation
            s.pino_jogo = { x = t.X, y = t.Y, z = t.Z }
        end
    end)
    s.ok = s.moedas ~= nil
    return s
end

local function writeState()
    local ok, st = pcall(readState)
    if not ok then st = { ok = false, erro = tostring(st), ts = os.time() } end
    local tmp = STATE_FILE .. ".tmp"
    local f = io.open(tmp, "w")
    if not f then return end
    f:write(jsonEncode(st)); f:close()
    os.remove(STATE_FILE)
    os.rename(tmp, STATE_FILE)
end

------------------------------------------------------------------ ações (recompensas)
local function credits()
    local v
    pcall(function()
        FindFirstOf("HS3StoreSaveGame").CurrencyTypeList:ForEach(function(_, e)
            local it = e:get()
            if tagName(it.CurrencyType) == "Currency.Credits" then v = it.CurrencyAmount end
        end)
    end)
    return v
end

local function giveCredits(amount, ref)
    local before = credits()
    local lib = StaticFindObject("/Script/HS3CoreRuntime.Default__HS3StoreFunctionLibrary")
    local pc = FindFirstOf("HS3PlayerController")
    local ok, err = pcall(function()
        lib:TryAddCurrency(pc, { TagName = FName("Currency.Credits") }, amount)
    end)
    local after = credits()
    local success = ok and before ~= nil and after ~= nil and after > before
    log(string.format("add_credits %d: %s (%s -> %s)", amount, success and "OK" or "FALHOU", tostring(before), tostring(after)))
    emit("recompensa", { recurso = "creditos", valor = amount, ok = success, antes = before, depois = after, ref = ref, erro = (not ok) and tostring(err) or nil })
end

local function repSalva(mapaCurto)
    -- reputação gravada no save (por mapa) para o vendedor
    local chunk = FindFirstOf("HS3ReputationSaveSlotChunk")
    local alvo
    chunk.ReputationSaveDataPerMap:ForEach(function(k, v)
        if k:get().PrimaryAssetName:ToString():find(mapaCurto, 1, true) then
            v:get().ReputationPerVendor:ForEach(function(vk, vv)
                if tagName(vk:get()) == VENDOR then alvo = vv:get() end
            end)
        end
    end)
    return alvo
end

local function giveReputation(amount, ref)
    local rm = FindFirstOf("HS3PlayerControllerComponent_ReputationManager")
    local tag = { TagName = FName(VENDOR) }
    local before, after
    pcall(function() before = rm:GetReputationForVendor(tag) end)
    local ok, err = pcall(function() rm:Client_AddReputationForVendor(tag, amount) end)
    pcall(function() after = rm:GetReputationForVendor(tag) end)
    local metodo = "oficial"
    if not (before and after and after > before) then
        -- plano B: escreve direto na reputação salva do mapa atual (o jogo grava no save normalmente)
        local okB, errB = pcall(function()
            local mapa = FindFirstOf("HS3PlayerController").Pawn:GetFullName():match("/([^/%.]+)%.")
            local d = repSalva(mapa)
            d.Reputation = d.Reputation + amount
        end)
        pcall(function() after = rm:GetReputationForVendor(tag) end)
        metodo = "direto"
        if not okB then err = errB end
    end
    local success = before ~= nil and after ~= nil and after > before
    log(string.format("add_rep %d (%s): %s (%s -> %s)", amount, metodo, success and "OK" or "FALHOU", tostring(before), tostring(after)))
    emit("recompensa", { recurso = "reputacao", valor = amount, ok = success, antes = before, depois = after, ref = ref, erro = (not success) and tostring(err) or nil })
end

------------------------------------------------------------------ eventos: binóculo
local spottedHooked = false
local especiePorId = {}   -- id do animal -> tag da espécie (vinda do binóculo)
local function tryHookSpotted()
    if spottedHooked then return true end
    local w = FindFirstOf("B_AnimalSpottedNotification_C")
    if not valid(w) then return false end
    local path = w:GetClass():GetFullName():match("%s(.+)$")
    if not path then return false end
    local ok, err = pcall(function()
        RegisterHook(path .. ":ApplyPayload", function(_, payload)
            pcall(function()
                local p = payload:get()
                local l = p.AnimalLocation
                especiePorId[p.CreatureId] = { TagName = p.AnimalTag.TagName }
                emit("marcado", {
                    id = p.CreatureId, especie = tagName(p.AnimalTag), sexo = p.AnimalSex,
                    lendario = p.LegendaryStatus, genetica = p.GeneticScore,
                    potencial = p.GeneticPotentialScore, idade_dias = p.AnimalAgeDays,
                    pos = { x = l.X, y = l.Y, z = l.Z } })
            end)
        end)
    end)
    spottedHooked = ok
    log(ok and "Hook do binoculo ativo" or ("Falha no hook do binoculo: " .. tostring(err)))
    return ok
end

------------------------------------------------------------------ eventos: abates
local function readKill(info)
    local t = {}
    pcall(function() t.id = info.AnimalId end)
    pcall(function() t.zona = tagName(info.Zone) end)
    pcall(function() t.regiao = info.Region:ToString() end)
    pcall(function() t.genetica = info.ScoreInfo.GeneticScore end)
    pcall(function() t.classe = info.Animal:GetClass():GetFName():ToString() end)
    pcall(function()
        local a = info.Animal:K2_GetActorLocation()
        t.pos = { x = a.X, y = a.Y, z = a.Z }
    end)
    pcall(function() t.tiros = info.InfoList:GetArrayNum() end)
    pcall(function() t.atraido = info.bIsUnderAttractionInfluence end)
    pcall(function()
        local shot = info.InfoList[1]
        t.arma = shot.WeaponId.PrimaryAssetName:ToString()
        t.municao = shot.ProjectileId.PrimaryAssetName:ToString()
        t.parte = shot.ComponentName:ToString()
        t.torre = shot.bWasShotFromHuntingStand
        t.estado_animal = shot.AnimalState
        t.postura = shot.PlayerStance
        pcall(function()
            local lib = StaticFindObject("/Script/HS3WeaponsRuntime.Default__HS3ProjectileFunctionLibrary")
            local cal = lib:GetCaliberTagFromPrimaryAssetId(shot.ProjectileId)
            t.calibre = tagName(cal)
            local esp = especiePorId[t.id]
            if esp and t.calibre then
                local comp = StaticFindObject("/Script/HS3AnimalsRuntime.Default__CaliberCompatibilityFunctionLibrary")
                t.calibre_compativel = comp:IsCaliberCompatibleWithAnimal({ TagName = FName(t.calibre) }, esp)
                t.especie = tagName(esp)
            end
        end)
        local o = shot.ProjectileOrigin
        t.origem = { x = o.X, y = o.Y, z = o.Z }
    end)
    if t.pos and t.origem then
        local dx, dy, dz = t.pos.x - t.origem.x, t.pos.y - t.origem.y, t.pos.z - t.origem.z
        t.distancia_m = math.sqrt(dx * dx + dy * dy + dz * dz) / 100
    end
    return t
end

pcall(function()
    RegisterHook("/Script/HS3AnimalsRuntime.AnimalBaggingHandlerComponent:Client_ShowBagPopupWithInfo", function(_, info)
        local ok, t = pcall(readKill, info:get())
        if ok then emit("abate", t) else log("erro abate: " .. tostring(t)) end
    end)
    log("Hook de abate ativo")
end)

-- Observação: o hook em Client_OnBagRequestFinished derrubava o jogo ao vender o animal.
-- O abate é registrado pelo popup (acima); a ponte ignora popups repetidos do mesmo animal.


------------------------------------------------------------------ mapa, névoa, pontos de interesse e animais
local function writeFile(path, data, mode)
    local tmp = path .. ".tmp"
    local f = io.open(tmp, mode or "w")
    if not f then return false end
    f:write(data); f:close()
    os.remove(path)
    os.rename(tmp, path)
    return true
end

local function currentLevel()
    local nav = FindFirstOf("LevelNavigationDataAsset")
    if not valid(nav) then return nil end
    local nome = nav.MapName:ToString()          -- /HS3DefaultMaps/Maps/Texas/Texas_a
    return nav, nome, nome:match("([^/]+)$")
end

local function exportMap()
    local nav, _, curto = currentLevel()
    if not nav then return log("exportar mapa: nível não encontrado") end
    local pc = FindFirstOf("HS3PlayerController")
    local KRL = StaticFindObject("/Script/Engine.Default__KismetRenderingLibrary")
    local tex = nav.MapBrush.ResourceObject
    local size = 4096
    pcall(function() size = tex:Blueprint_GetSizeX() end)
    local rt = KRL:CreateRenderTarget2D(pc, size, size, 2, { R = 0, G = 0, B = 0, A = 1 }, false, false)
    local canvas, sz, ctx = {}, {}, {}
    KRL:BeginDrawCanvasToRenderTarget(pc, rt, canvas, sz, ctx)
    local cv = canvas.Canvas or canvas
    cv:K2_DrawTexture(tex, { X = 0, Y = 0 }, { X = size, Y = size }, { X = 0, Y = 0 }, { X = 1, Y = 1 },
        { R = 1, G = 1, B = 1, A = 1 }, 0, 0.0, { X = 0.5, Y = 0.5 })
    KRL:EndDrawCanvasToRenderTarget(pc, ctx.Context or ctx)
    KRL:ExportRenderTarget(pc, rt, DIR, "mapa_" .. curto .. ".png")
    local info = { nivel = curto, tamanho_mundo = nav.MapSize.X, pixels = size }
    writeFile(DIR .. "mapa_" .. curto .. ".json", jsonEncode(info))
    log("mapa exportado: " .. curto)
end

local function exportPois()
    local _, nome, curto = currentLevel()
    if not nome then return end
    local estados = {}
    local save = FindFirstOf("NavigationSaveData")
    if valid(save) then
        save.DiscoverStatusLists:ForEach(function(_, e)
            local d = e:get()
            if d.LevelName:ToString() == nome then
                d.DiscoveryStatesList:ForEach(function(_, st)
                    local s = st:get()
                    estados[s.ActorHash] = tagName(s.DiscoveryStatus)
                end)
            end
        end)
    end
    local lista = {}
    local content = FindFirstOf("NavigationContentComponent")
    if valid(content) then
        content.NavigationActorDataMap:ForEach(function(k, v)
            local tipo = k:get().PrimaryAssetName:ToString()
            if tipo ~= "DA_Herd_MapIconData" and tipo ~= "DA_Player_MapIconData" and tipo ~= "DA_PlayerSmell_NavigationIcon" then
                v:get().ActorDataArray:ForEach(function(_, e)
                    local a = e:get()
                    local t = a.Transform.Translation
                    lista[#lista + 1] = { tipo = tipo, hash = a.Hash, x = t.X, y = t.Y, z = t.Z, estado = estados[a.Hash] }
                end)
            end
        end)
    end
    writeFile(DIR .. "pois_" .. curto .. ".json", jsonEncode(lista))
end

local function exportFog()
    local _, nome, curto = currentLevel()
    local save = FindFirstOf("NavigationSaveData")
    if not nome or not valid(save) then return end
    save.FogOfWarLists:ForEach(function(_, e)
        local f = e:get()
        if f.LevelName:ToString() == nome then
            local arr = f.FogArray
            local n = math.min(arr:GetArrayNum(), 524288)   -- 2048x2048 bits
            local parts, buf = {}, {}
            for i = 1, n do
                buf[#buf + 1] = string.char(arr[i])
                if #buf == 8192 then parts[#parts + 1] = table.concat(buf); buf = {} end
            end
            parts[#parts + 1] = table.concat(buf)
            writeFile(DIR .. "nevoa_" .. curto .. ".bin", table.concat(parts), "wb")
        end
    end)
end

local function exportCalibres()
    local tabela = {}
    for _, dt in ipairs(FindAllOf("DataTable") or {}) do
        pcall(function()
            local rs = dt.RowStruct:GetFName():ToString()
            if rs == "CaliberCompatibility" then
                dt:ForEachRow(function(nome, linha)
                    local compat, incompat = {}, {}
                    pcall(function() linha.CompatibleCalibers.GameplayTags:ForEach(function(_, e) compat[#compat + 1] = tagName(e:get()) end) end)
                    pcall(function() linha.IncompatibleCalibers.GameplayTags:ForEach(function(_, e) incompat[#incompat + 1] = tagName(e:get()) end) end)
                    tabela[#tabela + 1] = { animal = tostring(nome), compativeis = compat, incompativeis = incompat }
                end)
            end
        end)
    end
    if #tabela > 0 then
        writeFile(DIR .. "calibres.json", jsonEncode(tabela))
        log("tabela de calibres exportada: " .. #tabela .. " linhas")
    end
end

local function writeAnimals()
    local lista = {}
    for _, a in ipairs(FindAllOf("AnimalCharacter") or {}) do
        pcall(function()
            local loc = a:K2_GetActorLocation()
            local rot = a:K2_GetActorRotation()
            lista[#lista + 1] = { id = a.EcoSimCreatureId, classe = a:GetClass():GetFName():ToString(),
                x = loc.X, y = loc.Y, z = loc.Z, yaw = rot.Yaw }
        end)
    end
    writeFile(DIR .. "animais.json", jsonEncode({ ts = os.time(), animais = lista }))
end

local function quickWaypoint()
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    if not valid(nav) then return nil end
    local q = nav.QuickWaypoint
    if q.Hash == 0 then return nil end
    local t = q.Transform.Translation
    return { x = t.X, y = t.Y, z = t.Z }
end

local function setPin(x, y, z)
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    local id = { PrimaryAssetType = { Name = FName("NavigationIconData") }, PrimaryAssetName = FName("DA_QuickWaypoint_MapIconData") }
    nav:Server_AddQuickWaypoint(id, { Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = x, Y = y, Z = z }, Scale3D = { X = 1, Y = 1, Z = 1 } })
    log(string.format("pino no jogo: %.0f, %.0f", x, y))
end

local function clearPin()
    FindFirstOf("NavigationPlayerStateComponent"):Server_ClearQuickWaypoint()
    log("pino removido do jogo")
end

local ultimoNivel, ticks = nil, 0
local function periodic()
    ticks = ticks + 1
    local _, _, curto = currentLevel()
    if curto and curto ~= ultimoNivel and FindFirstOf("HS3PlayerController") then
        ultimoNivel = curto
        local f = io.open(DIR .. "mapa_" .. curto .. ".png", "rb")
        if f then f:close() else pcall(exportMap) end
        pcall(exportPois); pcall(exportFog); pcall(exportCalibres)
    end
    if ticks % 5 == 0 then pcall(writeAnimals) end
    if ticks % 60 == 0 then pcall(exportPois) end
    if ticks % 180 == 0 then pcall(exportFog) end   -- névoa a cada 3 min (leitura mais pesada)
end

-- utilidades disponíveis para scripts de desenvolvimento (pasta dev\)
HS3 = { log = log, emit = emit, json = jsonEncode, tagName = tagName, valid = valid, dir = DIR }

------------------------------------------------------------------ laços
LoopAsync(3000, function() return tryHookSpotted() end)

LoopAsync(1000, function()
    ExecuteInGameThread(function() pcall(writeState); pcall(periodic) end)

    local f = io.open(CMD_FILE, "r")
    if not f then return false end
    local text = f:read("*a") or ""
    f:close()
    if text:match("^%s*$") then return false end
    os.remove(CMD_FILE)
    for line in text:gmatch("[^\r\n]+") do
        local cmd, arg, ref = line:match("^(%S+)%s*(%S*)%s*(%S*)")
        local n = tonumber(arg)
        ExecuteInGameThread(function()
            local ok, err = pcall(function()
                if cmd == "add_credits" and n then giveCredits(n, ref)
                elseif cmd == "add_rep" and n then giveReputation(n, ref)
                elseif cmd == "status" then log("status solicitado")
                elseif cmd == "pin" then
                    local x, y, z = line:match("^pin%s+(%S+)%s+(%S+)%s*(%S*)")
                    setPin(tonumber(x), tonumber(y), tonumber(z) or 0)
                elseif cmd == "unpin" then clearPin()
                elseif cmd == "export_map" then exportMap(); exportPois(); exportFog(); exportCalibres()
                elseif cmd == "script" and arg ~= "" and arg:match("^[%w_%-]+%.lua$") then
                    local chunk, e = loadfile(DIR .. "dev" .. "\\" .. arg)
                    if not chunk then log("script erro ao carregar: " .. tostring(e)); return end
                    local okS, res = pcall(chunk)
                    log("script " .. arg .. ": " .. (okS and ("ok " .. tostring(res)) or ("ERRO " .. tostring(res))))
                else log("comando desconhecido: " .. line) end
            end)
            if not ok then log("ERRO comando: " .. tostring(err)) end
        end)
    end
    return false
end)

log("HS3 Companion carregado. Pasta: " .. DIR)
