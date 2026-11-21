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

local function giveReputation(amount, ref)
    local rm = FindFirstOf("HS3PlayerControllerComponent_ReputationManager")
    local tag = { TagName = FName(VENDOR) }
    local before, after
    pcall(function() before = rm:GetReputationForVendor(tag) end)
    local ok, err = pcall(function() rm:Client_AddReputationForVendor(tag, amount) end)
    pcall(function() after = rm:GetReputationForVendor(tag) end)
    local success = ok and before ~= nil and after ~= nil and after > before
    log(string.format("add_rep %d: %s (%s -> %s)", amount, success and "OK" or "FALHOU", tostring(before), tostring(after)))
    emit("recompensa", { recurso = "reputacao", valor = amount, ok = success, antes = before, depois = after, ref = ref, erro = (not ok) and tostring(err) or nil })
end

------------------------------------------------------------------ eventos: binóculo
local spottedHooked = false
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
    pcall(function()
        local shot = info.InfoList[1]
        t.arma = shot.WeaponId.PrimaryAssetName:ToString()
        t.municao = shot.ProjectileId.PrimaryAssetName:ToString()
        t.parte = shot.ComponentName:ToString()
        t.torre = shot.bWasShotFromHuntingStand
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

pcall(function()
    RegisterHook("/Script/HS3AnimalsRuntime.AnimalBaggingHandlerComponent:Client_OnBagRequestFinished", function(_, req, res, info)
        local ok, t = pcall(readKill, info:get())
        if not ok then t = {} end
        t.acao = req:get()
        t.resultado = res:get()
        emit("abate_final", t)
    end)
    log("Hook de resultado do abate ativo")
end)

------------------------------------------------------------------ laços
LoopAsync(3000, function() return tryHookSpotted() end)

LoopAsync(1000, function()
    ExecuteInGameThread(function() pcall(writeState) end)

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
                else log("comando desconhecido: " .. line) end
            end)
            if not ok then log("ERRO comando: " .. tostring(err)) end
        end)
    end
    return false
end)

log("HS3 Companion carregado. Pasta: " .. DIR)
