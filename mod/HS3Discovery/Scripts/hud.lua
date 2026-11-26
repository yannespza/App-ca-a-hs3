-- Contratos do app na caixa de objetivos do próprio jogo (W_HS3ContractObjectiveStatusList).
-- O app escreve hud.txt; este arquivo é recarregado a cada sincronização (pode ser atualizado com o jogo aberto).
-- Segurança: não guardamos objetos do jogo entre chamadas; os nossos widgets são reencontrados a cada vez.
--
-- hud.txt (uma linha por item, campos separados por TAB):
--   T<TAB>título da caixa quando não há contrato do jogo rastreado
--   O<TAB>texto do objetivo (rich text)<TAB>progresso (rich text)<TAB>1 se concluído
local M = {}
local CLASSE = "/HS3Core/Contracts/Menu/W_HS3HUDObjectiveStatus.W_HS3HUDObjectiveStatus_C"
local VISIVEL, RECOLHIDO, ESCONDIDO, SO_VISUAL = 0, 1, 2, 4

local estado = _G.HS3_HUD or { assinatura = nil, forcamos_visivel = false }
_G.HS3_HUD = estado

local function lerPedido(DIR)
    local f = io.open(DIR .. "hud.txt", "rb")
    if not f then return "", nil, {} end
    local txt = f:read("*a") or ""
    f:close()
    local titulo, itens = nil, {}
    for linha in txt:gmatch("[^\r\n]+") do
        local c = {}
        for campo in (linha .. "\t"):gmatch("([^\t]*)\t") do c[#c + 1] = campo end
        if c[1] == "T" then titulo = c[2]
        elseif c[1] == "O" and c[2] and c[2] ~= "" then
            itens[#itens + 1] = { texto = c[2], progresso = c[3] or "", feito = c[4] == "1" }
        end
    end
    return txt, titulo, itens
end

-- nossos widgets: objetivos que NÃO nasceram dentro de um WidgetTree do jogo
local function nossos(painel)
    local lista = {}
    local nomePainel = painel and painel:GetFullName() or ""
    for _, w in ipairs(FindAllOf("W_HS3HUDObjectiveStatus_C") or {}) do
        local ok, nome = pcall(function() return w:GetFullName() end)
        if ok and nome and not nome:find("WidgetTree_[%d]+%.W_HS3HUDObjectiveStatus") then
            local okP, pai = pcall(function() local p = w:GetParent(); return p and p:IsValid() and p:GetFullName() or "" end)
            -- widgets fora do painel são sobras já removidas (o jogo apaga depois); ignoramos
            if okP and pai == nomePainel then lista[#lista + 1] = { w = w } end
        end
    end
    return lista
end

function M.sincronizar(ctx)
    local tracker = FindFirstOf("W_HS3ContractObjectiveStatusList_C")
    if not tracker or not tracker:IsValid() then return end
    local painel = tracker.ObjectivePanel
    if not painel or not painel:IsValid() then return end

    local txt, titulo, itens = lerPedido(ctx.DIR)
    local atuais = nossos(painel)
    local mudou = not (#atuais == #itens and estado.assinatura == txt)

    -- refaz: tira os antigos e cria os novos
    if mudou then
    for _, a in ipairs(atuais) do pcall(function() a.w:RemoveFromParent() end) end
    local WBL = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary")
    local classe = StaticFindObject(CLASSE)
    local pc = FindFirstOf("HS3PlayerController")
    if #itens > 0 and WBL and classe and pc then
        for _, it in ipairs(itens) do
            local w = WBL:Create(pc, classe, pc)
            if w and w:IsValid() then
                pcall(function() w:ApplyObjectiveFromParams(FText(""), FText(""), it.feito, nil, {}) end)
                pcall(function() w.ObjectiveTitleRich:SetText(FText(it.texto)) end)
                pcall(function()
                    local p = w.W_HS3ObjectiveStringProgressDisplay
                    p.CommonRichTextBlock_87:SetText(FText(it.progresso))
                    p:SetVisibility(it.progresso ~= "" and VISIVEL or RECOLHIDO)
                end)
                painel:AddChild(w)
            end
        end
    end
    end

    -- sem contrato do jogo rastreado: a caixa fica escondida pelo jogo; mostramos com o nosso título.
    -- Conferido a cada vez: quando um contrato do jogo termina, o jogo esconde a caixa de novo (v0.1.39).
    local temContratoDoJogo = false
    pcall(function() temContratoDoJogo = tracker.TrackedContract ~= nil and tracker.TrackedContract:IsValid() end)
    if not temContratoDoJogo then
        if #itens > 0 then
            local vis = -1
            pcall(function() vis = tracker:GetVisibility() end)
            if mudou or vis ~= SO_VISUAL or not estado.forcamos_visivel then
                pcall(function() tracker.ContractTitle:SetText(FText(titulo or "Contratos do Velho Earl")) end)
            end
            if vis ~= SO_VISUAL then pcall(function() tracker:SetVisibility(SO_VISUAL) end) end
            estado.forcamos_visivel = true
        elseif estado.forcamos_visivel then
            pcall(function() tracker:SetVisibility(RECOLHIDO) end)
            estado.forcamos_visivel = false
        end
    end
    estado.assinatura = txt
    if not mudou then return end
    ctx.log(string.format("hud: %d objetivo(s) do app na caixa de contratos%s", #itens, temContratoDoJogo and " (junto do contrato do jogo)" or ""))
end

return M
