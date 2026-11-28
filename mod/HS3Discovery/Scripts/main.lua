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
local zonasFeitas = nil
local calmoAte = os.time() + 60   -- os.time(): até quando evitar leituras extras (jogo abrindo, mapa carregando, viagem)

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
-- Listas dentro de listas (pontos de campo por mapa, reputação por mapa e vendedor) são lidas só a cada
-- 10 s e guardadas como números: ler esse tipo de dado o tempo todo já fechou o jogo (ver mochila.lua).
local lentos = { quando = 0, pontos_campo = nil, reputacao = nil }
local caoCache = { nome = nil, ultimo = nil, tick = 0 }   -- só números/texto: nunca guardar objeto do jogo entre leituras
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
    end
    local lerLentos = os.time() - lentos.quando >= 10 and os.time() > calmoAte   -- listas dentro de listas: nunca durante carregamento
    if lerLentos and valid(store) then
        local pontos = {}
        pcall(function()
            store.LevelSpecificCurrencies:ForEach(function(k, v)
                local name = k:get().PrimaryAssetName:ToString()
                v:get().Currencies:ForEach(function(_, e)
                    local it = e:get()
                    if tagName(it.CurrencyType) == "Currency.Level.FieldPoints" then
                        pontos[name] = it.CurrencyAmount
                    end
                end)
            end)
        end)
        lentos.pontos_campo = pontos
    end

    -- reputação por mapa
    local rep = lerLentos and FindFirstOf("HS3ReputationSaveSlotChunk")
    if rep and valid(rep) then
        local lista = {}
        pcall(function()
            rep.ReputationSaveDataPerMap:ForEach(function(k, v)
                local name = k:get().PrimaryAssetName:ToString()
                v:get().ReputationPerVendor:ForEach(function(vk, vv)
                    local d = vv:get()
                    lista[#lista + 1] = {
                        mapa = name, vendedor = tagName(vk:get()),
                        valor = d.Reputation, sequencia = d.ReputationStreak }
                end)
            end)
        end)
        lentos.reputacao = lista
    end
    if lerLentos then lentos.quando = os.time() end
    s.pontos_campo, s.reputacao = lentos.pontos_campo, lentos.reputacao

    pcall(function()
        local q = FindFirstOf("NavigationPlayerStateComponent").QuickWaypoint
        local t = q.Transform.Translation
        -- sem pino o jogo deixa Hash -1 (ou 0) e a posição zerada
        if q.Hash ~= 0 and q.Hash ~= -1 and (t.X ~= 0 or t.Y ~= 0) then
            s.pino_jogo = { x = t.X, y = t.Y, z = t.Z }
        end
    end)
    pcall(function()
        -- 1 = andando no chão (MOVE_Walking); 3 = caindo. O app só guarda "último local" com o caçador no chão
        local pawn = FindFirstOf("HS3PlayerController").Pawn
        if not valid(pawn) or os.time() <= calmoAte then return end
        local mm = pawn.CharacterMovement.MovementMode
        s.chao = (mm == 1 or mm == 2)
    end)
    pcall(function()
        local e = FindFirstOf("EnvironmentManagerComponent")
        if e and e:IsValid() then
            s.hora = e.CurrentSolarTime
            pcall(function() s.vento = { angulo = e.WindAngle } end)      -- só um número do relógio do clima
            pcall(function() s.vento.forca = e:GetNormalizedWindSpeed() end)
        end
    end)
    -- cão em campo (só leitura; sonda 28/11): posição, estado, raça, energia e nome
    pcall(function()
        if os.time() <= calmoAte or not s.mapa or s.mapa:find("Hub") or s.mapa:find("Menu") then caoCache.ultimo = nil; return end
        caoCache.tick = caoCache.tick + 1
        if caoCache.tick % 2 == 0 and caoCache.ultimo then s.cao = caoCache.ultimo; return end   -- lê a cada 2 s
        local c = FindFirstOf("HS3CompanionPawn")
        if not (c and c:IsValid()) then caoCache.ultimo = nil; return end
        local t = c:K2_GetActorLocation()
        local cao = { x = t.X, y = t.Y, z = t.Z, estado = c.CompanionState, energia = c.CompanionEnergy }
        pcall(function() cao.raca = c.CompanionBreed.TagName:ToString() end)
        if not caoCache.nome then pcall(function() caoCache.nome = c:GetCompanionName():ToString() end) end
        cao.nome = caoCache.nome
        caoCache.ultimo, s.cao = cao, cao
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

local pagos = {}   -- referências já pagas nesta sessão (evita pagar duas vezes o mesmo contrato)
local function jaPago(recurso, ref)
    if not ref or ref == "" then return false end
    local k = recurso .. ":" .. ref
    if pagos[k] then log("pagamento repetido ignorado: " .. k); return true end
    pagos[k] = true
    return false
end

local function giveCredits(amount, ref)
    if jaPago("creditos", ref) then
        emit("recompensa", { recurso = "creditos", valor = amount, ok = true, ref = ref, repetido = true }); return
    end
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

local function repSalva(mapaCurto, vendedor)
    -- reputação gravada no save (por mapa) para o vendedor
    local chunk = FindFirstOf("HS3ReputationSaveSlotChunk")
    local alvo
    chunk.ReputationSaveDataPerMap:ForEach(function(k, v)
        if k:get().PrimaryAssetName:ToString():find(mapaCurto, 1, true) then
            v:get().ReputationPerVendor:ForEach(function(vk, vv)
                if tagName(vk:get()) == (vendedor or VENDOR) then alvo = vv:get() end
            end)
        end
    end)
    return alvo
end

local function giveReputation(amount, ref, vendedor)
    if jaPago("reputacao", ref) then
        emit("recompensa", { recurso = "reputacao", valor = amount, ok = true, ref = ref, repetido = true }); return
    end
    -- agente que recebe os pontos (o contrato do Earl diz qual); sem agente: Atirador esportivo
    if not (vendedor and vendedor:match("^NPC%.Vendor%.%w+$")) then vendedor = VENDOR end
    local rm = FindFirstOf("HS3PlayerControllerComponent_ReputationManager")
    local tag = { TagName = FName(vendedor) }
    local before, after
    pcall(function() before = rm:GetReputationForVendor(tag) end)
    local ok, err = pcall(function() rm:Client_AddReputationForVendor(tag, amount) end)
    pcall(function() after = rm:GetReputationForVendor(tag) end)
    local metodo = "oficial"
    if not (before and after and after ~= before) then     -- (negativo = penalidade de contrato abortado)
        -- plano B: escreve direto na reputação salva do mapa atual (o jogo grava no save normalmente)
        local okB, errB = pcall(function()
            local mapa = FindFirstOf("HS3PlayerController").Pawn:GetFullName():match("/([^/%.]+)%.")
            local d = repSalva(mapa, vendedor)
            d.Reputation = d.Reputation + amount
        end)
        pcall(function() after = rm:GetReputationForVendor(tag) end)
        metodo = "direto"
        if not okB then err = errB end
    end
    local success = before ~= nil and after ~= nil and after ~= before
    log(string.format("add_rep %d (%s): %s (%s -> %s)", amount, metodo, success and "OK" or "FALHOU", tostring(before), tostring(after)))
    emit("recompensa", { recurso = "reputacao", valor = amount, ok = success, antes = before, depois = after, ref = ref, erro = (not success) and tostring(err) or nil })
end

------------------------------------------------------------------ eventos: binóculo
local spottedHooked = false
local especiePorId = {}   -- id do animal -> tag da espécie (vinda do binóculo)
local marcadosPendentes = {}
local function soltarMarcados()
    if #marcadosPendentes == 0 then return end
    local lista = marcadosPendentes
    marcadosPendentes = {}
    for _, m in ipairs(lista) do
        if os.time() > calmoAte then
            pcall(function()
                for _, c in ipairs(FindAllOf("AnimalCosmeticsComponent") or {}) do
                    if c:IsValid() then
                        local ok, id = pcall(function() return c:GetOwner().EcoSimCreatureId end)
                        if ok and id == m.id then m.peso_kg = c.ReplicatedCosmeticInfo.WeightG / 1000; break end
                    end
                end
            end)
        end
        emit("marcado", m)
    end
end

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
                -- dentro do gancho só copiamos os números; o peso é procurado depois, fora do gancho
                -- (procurar componentes aqui fechou o jogo em 28/11 logo após passar o tempo)
                marcadosPendentes[#marcadosPendentes + 1] = {
                    id = p.CreatureId, especie = tagName(p.AnimalTag), sexo = p.AnimalSex,
                    lendario = p.LegendaryStatus, genetica = p.GeneticScore,
                    potencial = p.GeneticPotentialScore, idade_dias = p.AnimalAgeDays,
                    pos = { x = l.X, y = l.Y, z = l.Z } }
            end)
        end)
    end)
    spottedHooked = ok
    log(ok and "Hook do binoculo ativo" or ("Falha no hook do binoculo: " .. tostring(err)))
    return ok
end

local ticks = 0
local mortosAssinatura = nil
local trofeusAntes = nil

------------------------------------------------------------------ eventos: abates
local function readKill(info)
    local t = {}
    pcall(function() t.id = info.AnimalId end)
    pcall(function() t.zona = tagName(info.Zone) end)
    pcall(function() t.regiao = info.Region:ToString() end)
    pcall(function() t.genetica = info.ScoreInfo.GeneticScore end)
    -- ficha completa da carcaça (v0.1.41): peso, idade, potencial, pontuação, lendário, área
    pcall(function() t.potencial = info.ScoreInfo.MaxGeneticPotential end)
    pcall(function() t.creditos_jogo = info.ScoreInfo.Credits end)
    pcall(function() t.xp_jogo = info.ScoreInfo.XP end)
    pcall(function() t.area = info.Area.PrimaryAssetName:ToString() end)
    pcall(function()
        local c = info.AnimalCosmeticInfo
        t.especie_jogo = tagName(c.AnimalTag)
        t.sexo = c.Sex
        t.lendario = c.LegendaryStatus
        t.faixa_idade = c.AgeGroup
        t.idade_dias = c.AgeDays
        t.peso_kg = c.WeightG / 1000
    end)
    pcall(function()
        local e = info.ScoreInfo.AnimalScoreSummary.Entries
        local pts, maxp = 0, 0
        for j = 1, #e do pts = pts + (e[j].ScoreModifier or 0); maxp = maxp + (e[j].ScoreMax or 0) end
        t.pontos_trofeu, t.pontos_max = pts, maxp
    end)
    pcall(function() t.morte_ticks = info.TimeOfDeath.Ticks end)
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
        -- acessórios da arma no tiro (luneta ou mira aberta)
        pcall(function()
            local at, luneta = shot.WeaponAttachments, false
            for j = 1, #at do
                local tg = at[j].PartGameplayTag.TagName:ToString()
                local id = at[j].PartId.PrimaryAssetName:ToString()
                if tg:find("Scope") or id:find("Scope") then luneta = true end
            end
            t.tem_luneta = luneta
            t.acessorios_tiro = #at
        end)
        -- primeiro impacto: hora do tiro (tempo até a morte) e velocidade do animal (alvo em movimento)
        pcall(function()
            local h = shot.SingleHits[1]
            t.tiro_ticks = h.TimeOfShot.Ticks
            local v = h.AnimalVelocity
            t.vel_animal = math.sqrt(v.X * v.X + v.Y * v.Y) / 100
        end)
        local o = shot.ProjectileOrigin
        t.origem = { x = o.X, y = o.Y, z = o.Z }
    end)
    -- órgãos atingidos (o mesmo que o jogo mostra na ficha ao recolher): seções que cada projétil atravessou
    pcall(function()
        local vistos, lista = {}, {}
        local nTiros = math.min(info.InfoList:GetArrayNum(), 6)
        for i = 1, nTiros do
            pcall(function()
                local hits = info.InfoList[i].SingleHits
                for j = 1, math.min(hits:GetArrayNum(), 4) do
                    pcall(function()
                        local secs = hits[j].PenetrationResolution.ExitPropertiesPerSection
                        for k = 1, math.min(secs:GetArrayNum(), 24) do
                            local nome = tagName(secs[k].OrganType)
                            if nome and nome ~= "" and nome ~= "None" and not vistos[nome] then
                                vistos[nome] = true
                                lista[#lista + 1] = nome
                            end
                        end
                    end)
                end
            end)
        end
        t.orgaos = lista
    end)
    if t.morte_ticks and t.tiro_ticks and t.morte_ticks >= t.tiro_ticks then
        t.segundos_ate_morte = (t.morte_ticks - t.tiro_ticks) / 1e7
    end
    if t.pos and t.origem then
        local dx, dy, dz = t.pos.x - t.origem.x, t.pos.y - t.origem.y, t.pos.z - t.origem.z
        t.distancia_m = math.sqrt(dx * dx + dy * dy + dz * dz) / 100
    end
    return t
end

-- F9: foto para a Sala de troféus (o app do PC tira o print e prefere esta à automática). Só grava um evento.
pcall(function()
    RegisterKeyBind(Key.F9, function()
        emit("foto_trofeu", {})
    end)
    RegisterKeyBind(Key.F8, function() emit("tecla", { tecla = "carro" }) end)   -- trazer o carro para perto
    RegisterKeyBind(Key.F7, function() emit("tecla", { tecla = "marca" }) end)   -- marcar este lugar no app
end)

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
    if os.time() <= calmoAte then return end
    -- zonas de necessidade do MAPA TODO (v0.1.62): ficam como "filhas" dos ícones de bando no mapa do jogo
    -- (NavigationActorDataChildsMap: pai = bando; ExtraTags = espécie + tipo). Antes vinham só dos atores carregados perto.
    pcall(function()
        local zonas = {}
        content.NavigationActorDataChildsMap:ForEach(function(k, v)
            local bando = k:get()
            v:get().ActorDataArray:ForEach(function(_, e)
                local a = e:get()
                local especie, tipo
                pcall(function()
                    a.ExtraTags.GameplayTags:ForEach(function(_, tg)
                        local n = tg:get().TagName:ToString()
                        if n:find("^Animals%.Zone%.Type%.") then tipo = n:match("([^%.]+)$")
                        elseif n:find("^Animals%.Types%.") then especie = n end
                    end)
                end)
                if tipo and especie and (tipo == "Eating" or tipo == "Drinking" or tipo == "Sleeping" or tipo == "Roaming") then
                    local t = a.Transform.Translation
                    zonas[#zonas + 1] = { especie = especie, tipo = tipo, x = t.X, y = t.Y, grupo = bando, hash = a.Hash,
                        descoberta = estados[a.Hash] == "Map.UI.POI.Discovered" }
                end
            end)
        end)
        writeFile(DIR .. "zonas_" .. curto .. ".json", jsonEncode(zonas))
    end)
end

-- quantas coisas já estão descobertas neste mapa (só o tamanho da lista: barato). Mudou = exporta zonas na hora.
local descobertasAntes = nil
local function contarDescobertas()
    local _, nome = currentLevel()
    local save = FindFirstOf("NavigationSaveData")
    if not nome or not valid(save) then return nil end
    local n
    save.DiscoverStatusLists:ForEach(function(_, e)
        local d = e:get()
        if d.LevelName:ToString() == nome then n = d.DiscoveryStatesList:GetArrayNum() end
    end)
    return n
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
            local esp
            pcall(function() esp = a.SpeciesTag.TagName:ToString() end)
            lista[#lista + 1] = { id = a.EcoSimCreatureId, classe = a:GetClass():GetFName():ToString(), especie = esp,
                x = loc.X, y = loc.Y, z = loc.Z, yaw = rot.Yaw }
        end)
    end
    writeFile(DIR .. "animais.json", jsonEncode({ ts = os.time(), animais = lista }))
end

local function quickWaypoint()
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    if not valid(nav) then return nil end
    local q = nav.QuickWaypoint
    local t = q.Transform.Translation
    if q.Hash == 0 or q.Hash == -1 or (t.X == 0 and t.Y == 0) then return nil end
    return { x = t.X, y = t.Y, z = t.Z }
end

local function setPin(x, y, z)
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    local id = { PrimaryAssetType = { Name = FName("NavigationIconData") }, PrimaryAssetName = FName("DA_QuickWaypoint_MapIconData") }
    nav:Server_AddQuickWaypoint(id, { Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = x, Y = y, Z = z }, Scale3D = { X = 1, Y = 1, Z = 1 } })
    log(string.format("pino no jogo: %.0f, %.0f", x, y))
end

local function clearPin()
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    if not valid(nav) then return end
    pcall(function() nav:Server_ClearQuickWaypoint() end)
    -- o pedido acima não tira um pino posto pelo jogo: tira o marcador e zera o pino rápido direto
    if nav.QuickWaypoint.Hash ~= -1 then
        local q = nav.QuickWaypoint
        pcall(function() nav:RemoveInWorldMarker(q) end)
        pcall(function() nav:NavigationActorRemoved(q) end)
        nav.QuickWaypoint.Hash = -1
        nav.QuickWaypoint.Transform.Translation.X = 0
        nav.QuickWaypoint.Transform.Translation.Y = 0
        nav.QuickWaypoint.Transform.Translation.Z = 0
        pcall(function() nav:OnRep_QuickWaypoint() end)
    end
    log("pino removido do jogo")
end

-- passar o tempo (o mesmo que dormir na cama do acampamento): o jogo mostra a tela de tempo passando
local function passarTempo(horas)
    local e = FindFirstOf("EnvironmentManagerComponent")
    if not valid(e) then log("passar tempo: relógio não encontrado"); return end
    horas = math.max(0.25, math.min(23.5, horas))
    e:SkipSolarTime(horas)
    calmoAte = os.time() + 45      -- o jogo recria os animais depois de passar o tempo: 45 s sem leituras extras
    log(string.format("passar tempo: %.2f h (era %.2f h)", horas, e.CurrentSolarTime))
end


------------------------------------------------------------------ catálogo da loja, inventário, roupas e compras
local function pidStr(id) return id.PrimaryAssetType.Name:ToString() .. ":" .. id.PrimaryAssetName:ToString() end
local function idDe(str)
    local t, n = str:match("^([^:]+):(.+)$")
    return { PrimaryAssetType = { Name = FName(t) }, PrimaryAssetName = FName(n) }
end
local function texto(t) local ok, s = pcall(function() return t:ToString() end); return ok and s or "" end

local ATRIBUTOS = nil
local function atributosRoupa()
    if ATRIBUTOS then return ATRIBUTOS end
    local lista = {}
    pcall(function()
        FindFirstOf("HS3AttributeDataAsset").AttributeConfigs:ForEach(function(k, v)
            if v:get().bIsInfluencedByCosmetics then
                local a = k:get()
                lista[#lista + 1] = { nome = a.AttributeName:ToString(), ref = a }
            end
        end)
    end)
    if #lista > 0 then ATRIBUTOS = lista end
    return lista
end

local function statsRoupa(obj)
    local lib = StaticFindObject("/Script/HS3CoreRuntime.Default__HS3AttributeFunctionLibrary")
    local st = {}
    for _, a in ipairs(atributosRoupa()) do
        pcall(function() st[a.nome] = lib:GetAttributeValueFromAssetRaw(a.ref, obj) end)
    end
    return st
end

local catalogo = nil   -- exportação em lotes: { ids = {...}, i = 1, itens = {} }
local function iniciarCatalogo()
    local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
    local r = {}
    KSL:GetPrimaryAssetIdList({ Name = FName("HS3StoreItemAsset") }, r)
    local ids = {}
    for _, v in ipairs(r) do ids[#ids + 1] = v:get() end
    catalogo = { ids = ids, i = 1, itens = {} }
    log("catálogo: " .. #ids .. " itens da loja para ler")
end

local function passoCatalogo()
    if not catalogo then return end
    local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
    local proj = StaticFindObject("/Script/HS3WeaponsRuntime.Default__HS3ProjectileFunctionLibrary")
    local fim = math.min(catalogo.i + 39, #catalogo.ids)
    for i = catalogo.i, fim do
        pcall(function()
            local item = KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(catalogo.ids[i]))
            if not valid(item) then return end
            local e = {
                id = item:GetFName():ToString(), tipo = tagName(item.ItemType), nome = texto(item.ItemName),
                descricao = texto(item.ItemDescription), preco = item.ItemCost, moeda = tagName(item.CurrencyType),
                marca = tagName(item.ItemBrand), item = pidStr(item.ItemAssetID), cargas = item.NumberOfChargesPerPurchase,
                desativado = item.bIsDisabled, padrao = item.bIsDefaultBought,
            }
            local tipoAsset = item.ItemAssetID.PrimaryAssetType.Name:ToString()
            if tipoAsset == "HS3ClothingDataAsset" or tipoAsset == "HS3BackpackDataAsset" then
                local roupa = KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(item.ItemAssetID))
                if valid(roupa) then
                    e.stats = statsRoupa(roupa)
                    e.parte = tagName(roupa.CosmeticTypeTag)
                    if e.nome == "" then e.nome = texto(roupa.DisplayName) end
                end
            end
            pcall(function()
                local c = tagName(proj:GetCaliberTagFromPrimaryAssetId(item.ItemAssetID))
                if c and c ~= "None" then e.calibre = c end
            end)
            pcall(function()
                local tags = {}
                item.CompatibilityTags.GameplayTags:ForEach(function(_, t) tags[#tags + 1] = tagName(t:get()) end)
                if #tags > 0 then e.compat = tags end
            end)
            catalogo.itens[#catalogo.itens + 1] = e
        end)
    end
    catalogo.i = fim + 1
    if catalogo.i > #catalogo.ids then
        writeFile(DIR .. "catalogo_v2.json", jsonEncode(catalogo.itens))
        log("catálogo exportado: " .. #catalogo.itens .. " itens")
        catalogo = nil
    end
end

local function writeEquipamento()
    local eq = { ts = os.time(), mochila = {}, roupa = {}, comprados = {} }
    pcall(function()
        FindFirstOf("HS3InventoryManagerComponent").CachedInventoryList.Items:ForEach(function(_, e)
            local it = e:get()
            eq.mochila[#eq.mochila + 1] = { item = pidStr(it.SaveInfo.AssetId), tipo = tagName(it.SaveInfo.Type), cargas = it.Charges }
        end)
    end)
    pcall(function()
        FindFirstOf("HS3CharacterAssetSaveGame").SavedCharacterParts:ForEach(function(_, e)
            local p = e:get()
            local tipo = tagName(p.CosmeticType) or ""
            if tipo:find("Clothing") then eq.roupa[#eq.roupa + 1] = { item = pidStr(p.CosmeticId), tipo = tipo } end
        end)
    end)
    pcall(function()
        FindFirstOf("HS3StoreSaveGame").BoughtItems:ForEach(function(_, e)
            local b = e:get()
            eq.comprados[#eq.comprados + 1] = { id = b.AssetId.PrimaryAssetName:ToString(), cargas = b.Charges }
        end)
    end)
    pcall(function()
        local d = FindFirstOf("HS3AttributeSet_Detection")
        eq.deteccao = { visual = d.VisualDetectionFactor.CurrentValue, som = d.SoundDetectionFactor.CurrentValue,
                        cheiro = d.SmellDetectionFactor.CurrentValue, na_estrutura = d.InHuntingStructure.CurrentValue }
    end)
    writeFile(DIR .. "equipamento.json", jsonEncode(eq))
end

local function comprar(nomeItem, ref)
    local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
    local item = KSL:LoadAsset_Blocking(KSL:GetSoftObjectReferenceFromPrimaryAssetId(idDe("HS3StoreItemAsset:" .. nomeItem)))
    local lib = StaticFindObject("/Script/HS3CoreRuntime.Default__HS3StoreFunctionLibrary")
    local pc = FindFirstOf("HS3PlayerController")
    local antes = credits()
    local ok, err = pcall(function() lib:TryPurchaseStoreItem(pc, item) end)
    local depois = credits()
    local success = ok and antes and depois and depois < antes
    log(string.format("compra %s: %s (%s -> %s)", nomeItem, success and "OK" or "FALHOU", tostring(antes), tostring(depois)))
    emit("compra", { item = nomeItem, ok = success, antes = antes, depois = depois, ref = ref, erro = (not ok) and tostring(err) or nil })
    pcall(writeEquipamento)
end

-- altura do chão num ponto (traço vertical; testado 27/11: bate com a altura que o jogo dá ao pino)
local function alturaChao(x, y)
    local z
    pcall(function()
        local pc = FindFirstOf("HS3PlayerController")
        local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
        local hit = {}
        local ok = KSL:LineTraceSingle(pc.Pawn, { X = x, Y = y, Z = 200000 }, { X = x, Y = y, Z = -200000 }, 0, false, {}, 0, hit, true,
            { R = 0, G = 0, B = 0, A = 0 }, { R = 0, G = 0, B = 0, A = 0 }, 0)
        if ok and hit.Location then z = hit.Location.Z end
    end)
    return z
end

local function teleportar(x, y, z)
    calmoAte = os.time() + 90
    -- sem altura (barracas, pontos com afastamento): usa a do chão para não cair do céu
    if not z then
        z = alturaChao(x, y)
        if not z then log("viagem cancelada: sem altura do chão no destino"); return end
    end
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    nav:Server_SafeFastTravel({ { Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = x, Y = y, Z = z + 60 }, Scale3D = { X = 1, Y = 1, Z = 1 } } })
    log(string.format("teleporte para %.0f, %.0f", x, y))
end

-- dados do jogo para a enciclopédia (fauna, cães, armas, roupas, itens + imagens): roda uma vez por versão
local exportador, exportando = nil, false
local function exportarDados(forcar)
    if exportando then return end
    do  -- recarrega sempre (permite atualizar exportar.lua sem reiniciar o jogo)
        local chunk, e = loadfile(DIR .. "Scripts\\exportar.lua")
        if not chunk then log("exportar.lua: " .. tostring(e)); return end
        exportador = chunk()
    end
    if not forcar then
        local f = io.open(DIR .. "jogo_dados.json", "rb")
        if f then
            local cab = f:read(40) or ""; f:close()
            if tonumber(cab:match('"versao":%s*(%d+)')) == exportador.VERSAO then return end
        end
    end
    local marca = io.open(DIR .. "img\\.ok", "rb")
    if marca then marca:close() else
        os.execute('mkdir "' .. DIR .. 'img" 2>nul')
        local m = io.open(DIR .. "img\\.ok", "wb"); if m then m:write("1"); m:close() end
    end
    exportando = true
    exportador.iniciar({ DIR = DIR, log = log, writeFile = writeFile, json = jsonEncode, tagName = tagName, valid = valid,
                         fim = function()
                             exportando = false
                             -- depois de ler os dados, refaz em alta resolução os ícones novos (img\nitidos.txt guarda os já feitos)
                             local ch = loadfile(DIR .. "Scripts\\nitido.lua")
                             if ch then pcall(function() ch().iniciar({ DIR = DIR, log = log }) end) end
                         end })
end

------------------------------------------------------------------ mochila e contratos do jogo
-- (Scripts\mochila.lua e Scripts\contratos.lua, recarregados a cada uso)
local filaMochila = {}
local mochilaMexeu = false
local function ctxScripts() return { DIR = DIR, log = log, emit = emit, writeFile = writeFile, json = jsonEncode, tagName = tagName } end
local function rodarMochila(fn)
    local chunk, e = loadfile(DIR .. "Scripts\\mochila.lua")
    if not chunk then log("mochila.lua: " .. tostring(e)); return end
    local ok, err = pcall(function() fn(chunk(), ctxScripts()) end)
    if not ok then log("mochila: " .. tostring(err)) end
end
local function passoMochila()
    if #filaMochila == 0 then
        if mochilaMexeu then mochilaMexeu = false; rodarMochila(function(mo, ctx) mo.salvar(ctx) end) end
        return
    end
    local line = table.remove(filaMochila, 1)
    local p = {}
    for w in line:gmatch("%S+") do p[#p + 1] = w end
    local acao = p[2]
    mochilaMexeu = true
    rodarMochila(function(mo, ctx)
        if acao == "por" and p[3] and p[4] and tonumber(p[5]) then mo.por(ctx, p[3], p[4], math.tointeger(tonumber(p[5])) or 0)
        elseif acao == "tirar" and p[3] then mo.tirar(ctx, p[3])
        elseif acao == "municao" and p[3] and p[4] then mo.municao(ctx, p[3], p[4])
        elseif acao == "acessorio" and p[3] and p[4] and mo.acessorio then mo.acessorio(ctx, p[3], p[4])
        elseif acao == "tirar_acessorio" and p[3] and p[4] and mo.tirarAcessorio then mo.tirarAcessorio(ctx, p[3], p[4])
        else log("mochila: comando inválido: " .. line) end
    end)
end
local function lerContratosJogo()
    local chunk = loadfile(DIR .. "Scripts\\contratos.lua")
    if chunk then pcall(function() chunk().ler(ctxScripts()) end) end
end

local ultimoNivel = nil
local nivelBruto = false
local function periodic()
    ticks = ticks + 1
    pcall(soltarMarcados)
    local _, _, curto = currentLevel()
    -- qualquer troca de mapa (menu, rancho, reserva): 60 s sem leituras extras enquanto o jogo carrega
    if curto ~= nivelBruto then
        nivelBruto = curto
        if os.time() + 60 > calmoAte then calmoAte = os.time() + 60 end
        caoCache.ultimo = nil
    end
    -- o acampamento (Hub) e o menu não são reservas: nada de exportar mapa/pontos/névoa ali
    if curto and (curto:find("Hub") or curto:find("Menu")) then curto = nil end
    if curto and curto ~= ultimoNivel and FindFirstOf("HS3PlayerController") then
        ultimoNivel = curto
        zonasFeitas = nil
        calmoAte = os.time() + 90
        local f = io.open(DIR .. "mapa_" .. curto .. ".png", "rb")
        if f then f:close() else pcall(exportMap) end
        pcall(exportPois); pcall(exportCalibres)   -- névoa só quando o app pede (leitura pesada)
        local f2 = io.open(DIR .. "catalogo_v2.json", "rb")
        if f2 then f2:close() else pcall(iniciarCatalogo) end
    end
    if catalogo then pcall(passoCatalogo) end
    -- (cria widgets do jogo: só numa reserva já carregada; criar objeto durante carregamento fecha o jogo)
    if ticks % 2 == 0 and curto and os.time() > calmoAte and valid(FindFirstOf("HS3PlayerController")) then
        -- contratos do app na caixa de objetivos do jogo (Scripts\hud.lua, recarregado a cada vez)
        local f = io.open(DIR .. "hud.txt", "rb")
        if f then
            f:close()
            local chunk = loadfile(DIR .. "Scripts\\hud.lua")
            if chunk then
                local okH, errH = pcall(function() chunk().sincronizar({ DIR = DIR, log = log }) end)
                if not okH and ticks % 60 == 0 then log("hud: " .. tostring(errH)) end
            end
        end
    end
    pcall(passoMochila)
    local calmo = os.time() <= calmoAte          -- jogo carregando / logo após viagem ou passar o tempo
    if not calmo and ticks % 10 == 3 and #filaMochila == 0 then lerContratosJogo() end
    if not calmo and ticks % 15 == 0 then pcall(writeEquipamento) end
    if not calmo and ticks % 2 == 0 then pcall(writeAnimals) end      -- posição dos animais a cada 2 s (antes 5 s)
    -- pontos descobertos a cada 5 min (o app marca na hora as estruturas por onde você passa)
    -- v0.1.34 tinha um gancho na descoberta: fechou o jogo ao descobrir uma estrutura. Não usar.
    if curto and ticks % 120 == 0 and os.time() > calmoAte then pcall(exportPois) end
    -- zona descoberta agora: a lista de descobertas cresce; exporta em seguida (antes só a cada 5 min)
    if curto and ticks % 5 == 2 and os.time() > calmoAte then
        pcall(function()
            local n = contarDescobertas()
            if n and descobertasAntes and n ~= descobertasAntes then pcall(exportPois) end
            descobertasAntes = n
        end)
    end
    -- logo que o mapa termina de carregar (fim do período calmo), exporta pontos e zonas uma vez
    if curto and os.time() > calmoAte and zonasFeitas ~= curto and ticks % 10 == 0 then
        zonasFeitas = curto
        pcall(exportPois)
    end
    -- sala de troféus: avisa quando aparece animal empalhado novo (o app tira print no PC)
    if nivelBruto and ticks % 45 == 20 and os.time() > calmoAte and valid(FindFirstOf("HS3PlayerController")) then
        pcall(function()
            local ch = loadfile(DIR .. "Scripts\\trofeus.lua")
            if not ch then return end
            local total, porNivel = ch().contar()
            if not total then return end
            if trofeusAntes and total > trofeusAntes then
                emit("empalhado", { total = total, antes = trofeusAntes, por_nivel = porNivel })
            end
            trofeusAntes = total
        end)
    end
    -- animais mortos no mapa (natural = sem tiro do jogador); só regrava quando a lista muda (v0.1.43)
    if curto and ticks % 30 == 5 and os.time() > calmoAte then
        pcall(function()
            local ch = loadfile(DIR .. "Scripts\\mortos.lua")
            if not ch then return end
            local M = ch()
            local lista, ass = M.ler()
            if ass ~= mortosAssinatura then
                mortosAssinatura = ass
                writeFile(DIR .. "mortos.json", jsonEncode({ ts = os.time(), mortos = M.completar(lista) }))
            end
        end)
    end
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
                elseif cmd == "add_rep" and n then giveReputation(n, ref, line:match("^add_rep%s+%S+%s+%S+%s+(%S+)"))
                elseif cmd == "status" then log("status solicitado")
                elseif cmd == "pin" then
                    local x, y, z = line:match("^pin%s+(%S+)%s+(%S+)%s*(%S*)")
                    setPin(tonumber(x), tonumber(y), tonumber(z) or 0)
                elseif cmd == "unpin" then clearPin()
                elseif cmd == "dormir" and tonumber(arg) then passarTempo(tonumber(arg))
                elseif cmd == "comprar" and arg ~= "" then comprar(arg, ref)
                elseif cmd == "catalogo" then iniciarCatalogo()
                elseif cmd == "exportar_dados" then
                    local _, _, curto = currentLevel()
                    if not curto or curto:find("Hub") or curto:find("Menu") or not FindFirstOf("HS3PlayerController") then
                        log("exportar_dados: entre numa reserva primeiro")
                    else exportarDados(true) end
                elseif cmd == "teleport" then
                    local x, y, z = line:match("^teleport%s+(%S+)%s+(%S+)%s*(%S*)")
                    teleportar(tonumber(x), tonumber(y), tonumber(z))
                elseif cmd == "carro" then
                    -- carro x y [z]: traz o último veículo usado (com o setup dele) para perto do ponto (testado 27/11)
                    local x, y, z = line:match("^carro%s+(%S+)%s+(%S+)%s*(%S*)")
                    x, y, z = tonumber(x), tonumber(y), tonumber(z)
                    if x and y then
                        z = z or alturaChao(x, y)
                        if not z then log("carro: sem altura do chão no destino")
                        else
                            local ok, e = pcall(function()
                                FindFirstOf("HS3PlayerStateComponent_Vehicle"):Server_TeleportSpawnedVehicle({ Rotation = { X = 0, Y = 0, Z = 0, W = 1 },
                                    Translation = { X = x, Y = y, Z = z + 100 }, Scale3D = { X = 1, Y = 1, Z = 1 } })
                            end)
                            log("carro trazido: " .. (ok and "OK" or tostring(e)))
                        end
                    end
                elseif cmd == "cobrar" then
                    -- cobrar <créditos> <ref>: itens do app (barracas, câmeras...) pagos com o dinheiro do jogo
                    local valor, r = line:match("^cobrar%s+(%d+)%s*(%S*)")
                    valor = tonumber(valor)
                    if valor and not jaPago("cobrar", r) then
                        local alvo
                        pcall(function()
                            FindFirstOf("HS3StoreSaveGame").CurrencyTypeList:ForEach(function(_, e)
                                local it = e:get()
                                if tagName(it.CurrencyType) == "Currency.Credits" then alvo = it end
                            end)
                        end)
                        local ok = alvo ~= nil and alvo.CurrencyAmount >= valor
                        if ok then alvo.CurrencyAmount = alvo.CurrencyAmount - valor end
                        log(string.format("cobrança $%d: %s", valor, ok and "OK" or "FALHOU"))
                        emit("compra", { item = "app", ok = ok, ref = r, erro = (not ok) and "créditos insuficientes" or nil, depois = alvo and alvo.CurrencyAmount })
                    end
                elseif cmd == "nitido" then
                    local ch, e = loadfile(DIR .. "Scripts\\nitido.lua")
                    if ch then ch().iniciar({ DIR = DIR, log = log }) else log("nitido.lua: " .. tostring(e)) end
                elseif cmd == "export_map" then exportMap(); exportPois(); exportCalibres()
                elseif cmd == "nevoa" then
                    -- névoa do mapa: 524 mil leituras (lista dentro de lista) -> só quando você pede no app
                    local _, _, curto = currentLevel()
                    if curto and not curto:find("Hub") and not curto:find("Menu") then exportFog(); log("névoa exportada") end
                elseif cmd == "mochila" then
                    -- mochila ler | mochila por <item> <tipo> <idx> | mochila tirar <item> | mochila municao <arma> <municao>
                    -- leitura na hora; trocas vão para a fila (uma por segundo, depois salva e relê)
                    if arg == "ler" then if os.time() > calmoAte then rodarMochila(function(mo, ctx) mo.ler(ctx) end) end
                    elseif arg == "armas" then rodarMochila(function(mo, ctx) if mo.armas then mo.armas(ctx) end end)
                    else filaMochila[#filaMochila + 1] = line end
                elseif cmd == "licencas" or cmd == "licenca" then
                    -- licencas (lê) | licenca <tag da espécie> <preço> <ref> (compra/renova na reserva atual)
                    local ch, e = loadfile(DIR .. "Scripts\\licencas.lua")
                    if not ch then log("licencas.lua: " .. tostring(e)); return end
                    local li = ch()
                    if cmd == "licencas" then if os.time() > calmoAte then li.ler(ctxScripts()) end
                    else
                        local tag, preco, r = line:match("^licenca%s+(%S+)%s+(%d+)%s*(%S*)")
                        if tag and not jaPago("licenca", r) then li.comprar(ctxScripts(), tag, tonumber(preco), r) end
                    end
                elseif cmd == "municao" then
                    -- municao [créditos por bala] [ref]: enche a reserva das armas da mochila até o máximo do jogo
                    local ch, e = loadfile(DIR .. "Scripts\\municao.lua")
                    if not ch then log("municao.lua: " .. tostring(e)); return end
                    local preco, r = line:match("^municao%s*(%d*)%s*(%S*)")
                    if not jaPago("municao", r) then ch().recarregar(ctxScripts(), tonumber(preco) or 0, r) end
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

-- registro muito grande: guarda só o fim
do
    local f = io.open(LOG_FILE, "rb")
    if f then
        local tam = f:seek("end")
        if tam > 300000 then
            f:seek("set", tam - 60000)
            local fim = f:read("*a"); f:close()
            local g = io.open(LOG_FILE, "wb"); if g then g:write((fim:gsub("^[^\n]*\n", ""))); g:close() end
        else f:close() end
    end
end

-- eventos de sessões antigas (o app já leu): recomeça o arquivo quando passar de 1 MB
do
    local f = io.open(EVENTS_FILE, "rb")
    if f then
        local tam = f:seek("end"); f:close()
        if tam > 1000000 then os.remove(EVENTS_FILE) end
    end
end

-- comandos que sobraram de uma sessão anterior (jogo fechado) não são executados
do
    local f = io.open(CMD_FILE, "r")
    if f then f:close(); os.remove(CMD_FILE); log("cmd.txt antigo descartado ao iniciar") end
end
log("HS3 Companion carregado. Pasta: " .. DIR)
