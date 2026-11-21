-- lê os contratos ativos do jogo só por propriedades (sem guardar nada)
local log = HS3.log
local function txt(t) local ok, s = pcall(function() return t:ToString() end); return ok and s or "?" end
local cm
for _, nome in ipairs({ "B_HS3PlayerStateComp_ContractManager_C", "HS3PlayerStateComponent_ContractManager" }) do
    local todos = FindAllOf(nome)
    if todos then
        for _, o in ipairs(todos) do
            if o:IsValid() and not o:GetFullName():find("Default__") then cm = o; break end
        end
    end
    if cm then break end
end
if not cm then log("contratos: sem ContractManager"); return "sem" end
log("contratos: " .. cm:GetFullName())
local trk = cm.CurrentTrackingContract
local trkNome = (trk and trk:IsValid()) and trk:GetFullName() or "nenhum"
log("  rastreado: " .. trkNome)
local n = 0
cm.ActiveContracts:ForEach(function(_, e)
    n = n + 1
    local c = e:get()
    if not (c and c:IsValid()) then log("  [" .. n .. "] inválido"); return end
    local d = c.ContractData
    local titulo, desc, vend = "?", "?", "?"
    if d and d:IsValid() then
        titulo = txt(d.Title); desc = txt(d.Description)
        pcall(function() vend = d.VendorTag.TagName:ToString() end)
    end
    log(string.format("  [%d] %s | %s | vendedor=%s | tempo=%s | rastreado=%s", n, titulo, desc, vend,
        tostring(c.TimeLeftForContract), tostring(c:GetFullName() == trkNome)))
    local k = 0
    c.CurrentStepObjectives:ForEach(function(_, oe)
        k = k + 1
        local o = oe:get()
        if not (o and o:IsValid()) then return end
        local t = txt(o.ObjectiveTitle)
        local tf = "?"
        pcall(function() tf = txt(o:GetObjectiveTitle(FindFirstOf("HS3PlayerController"))) end)
        local ps = "?"
        pcall(function() ps = txt(o:GetObjectiveProgressText()) end)
        log(string.format("     obj%d: prop='%s' func='%s' desc='%s' qtd=%s/%s req=%s prog='%s' classe=%s", k, t, tf,
            txt(o.ObjectiveDescription), tostring(o.CurrentProgressAmount), tostring(o.RequiredQuantity),
            tostring(o.bRequiresQuantity), ps, o:GetClass():GetFName():ToString()))
    end)
end)
log("contratos: " .. n .. " ativos")
return n
