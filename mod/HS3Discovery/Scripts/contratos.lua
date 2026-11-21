-- Contratos ativos do próprio jogo -> contratos_jogo.json (o app mostra como "do jogo").
-- Só leitura, tudo no mesmo passo; nada é guardado entre chamadas.
local M = {}

local function txt(t)
    local ok, s = pcall(function() return t:ToString() end)
    return ok and s or nil
end
local function valido(o)
    if not o then return false end
    local ok, v = pcall(function() return o:IsValid() end)
    return ok and v
end

local function gerente()
    for _, nome in ipairs({ "B_HS3PlayerStateComp_ContractManager_C", "HS3PlayerStateComponent_ContractManager" }) do
        local todos = FindAllOf(nome)
        if todos then
            for _, o in ipairs(todos) do
                if valido(o) and not o:GetFullName():find("Default__") then return o end
            end
        end
    end
end

function M.ler(ctx)
    local pc = FindFirstOf("HS3PlayerController")
    if not valido(pc) then return end
    local cm = gerente()
    if not cm then return end
    local r = { ts = os.time(), contratos = {} }
    local trk = cm.CurrentTrackingContract
    local trkNome = valido(trk) and trk:GetFullName() or nil
    cm.ActiveContracts:ForEach(function(_, e)
        local c = e:get()
        if not valido(c) then return end
        local d = c.ContractData
        local k = { objetivos = {}, rastreado = (trkNome ~= nil and c:GetFullName() == trkNome) }
        pcall(function() k.tempo = c.TimeLeftForContract end)
        if valido(d) then
            k.id = d:GetFName():ToString()
            k.titulo = txt(d.Title)
            k.descricao = txt(d.Description)
            pcall(function() k.vendedor = d.VendorTag.TagName:ToString() end)
            pcall(function() k.limitado = d.bIsTimeLimited end)
        end
        -- versões já formatadas pelo jogo (sem {0.GetAnimalTypeText})
        pcall(function() local s = txt(c:GetContractTitle()); if s and s ~= "" then k.titulo = s end end)
        pcall(function() local s = txt(c:GetContractDescription()); if s and s ~= "" then k.descricao = s end end)
        c.CurrentStepObjectives:ForEach(function(_, oe)
            local o = oe:get()
            if not valido(o) then return end
            local ob = { titulo = txt(o.ObjectiveTitle) }
            pcall(function() local s = txt(o:GetObjectiveTitle(pc)); if s and s ~= "" then ob.titulo = s end end)
            pcall(function() ob.progresso = o.CurrentProgressAmount end)
            pcall(function() ob.meta = o.RequiredQuantity end)
            pcall(function() ob.quantidade = o.bRequiresQuantity end)
            pcall(function() ob.texto_progresso = txt(o:GetObjectiveProgressText()) end)
            k.objetivos[#k.objetivos + 1] = ob
        end)
        r.contratos[#r.contratos + 1] = k
    end)
    ctx.writeFile(ctx.DIR .. "contratos_jogo.json", ctx.json(r))
    return #r.contratos
end

return M
