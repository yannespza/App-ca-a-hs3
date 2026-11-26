-- Sonda (só leitura): cão, zonas de necessidade, munição, agentes/reputação, prazo dos contratos,
-- velocidade de andar e contratos de genética. Grava dev\sonda_sexta.txt. Não cria nada e não escreve no jogo.
local L = {}
local function p(s) L[#L + 1] = s end
local function tag(t)
    local ok, v = pcall(function() return t.TagName:ToString() end)
    return ok and v or "?"
end
local function nomeClasse(o)
    local ok, v = pcall(function() return o:GetClass():GetFName():ToString() end)
    return ok and v or "?"
end
local function curto(o)
    local ok, v = pcall(function() return o:GetFullName() end)
    if not ok or not v then return "?" end
    return v:match("([^%.]+)$") or v
end

-- 1) cão
pcall(function()
    local caes = FindAllOf("HS3CompanionPawn") or {}
    p("== CAES " .. #caes)
    for _, c in ipairs(caes) do
        pcall(function()
            local l = c:K2_GetActorLocation()
            p(string.format("CAO %s | %s | %.0f %.0f %.0f", nomeClasse(c), curto(c), l.X, l.Y, l.Z))
        end)
    end
end)

-- 2) zonas de animais (comer, dormir, beber etc.)
pcall(function()
    local zonas = FindAllOf("AnimalZoneBase") or {}
    p("== ZONAS " .. #zonas)
    for i, z in ipairs(zonas) do
        if i > 600 then p("(cortado em 600)"); break end
        pcall(function()
            local l = z:K2_GetActorLocation()
            p(string.format("Z %s|%s|%s|%.0f|%.0f|%.0f|%d|%d", nomeClasse(z), tag(z.CreatureTag), tag(z.ZoneTag),
                l.X, l.Y, z.ZoneRadius or 0, z.ZoneId or -1, z.GroupID or -1))
        end)
    end
end)

-- 3) munição e outros itens com pilhas (quantidade)
pcall(function()
    local itens = FindAllOf("HS3InventoryItemInstance") or {}
    p("== ITENS " .. #itens)
    for i, it in ipairs(itens) do
        if i > 80 then break end
        pcall(function()
            local pilhas = {}
            local st = it.StatTags.Stacks
            for j = 1, #st do
                local s = st[j]
                pilhas[#pilhas + 1] = tag(s.Tag) .. "=" .. tostring(s.StackCount)
            end
            local def = "?"
            pcall(function() def = it.ItemDef:GetFName():ToString() end)
            p("ITEM " .. def .. " | " .. table.concat(pilhas, ", "))
        end)
    end
end)

-- 4) agentes (NPC) e contratos liberados por nível de reputação
pcall(function()
    local npcs = FindAllOf("HS3ContractNPCDefinitionDataAsset") or {}
    p("== NPCS " .. #npcs)
    for _, n in ipairs(npcs) do
        pcall(function()
            local linha = "NPC " .. curto(n) .. " | " .. tag(n.NPCVendorTag)
            local u = n.ReputationContractUnlocks
            for j = 1, #u do
                local caminho = "?"
                pcall(function() caminho = u[j].UnlockedContract:ToString() end)
                if caminho == "?" then pcall(function() caminho = u[j].UnlockedContract.SoftObjectPtr.ObjectID.AssetPath.AssetName:ToString() end) end
                linha = linha .. " | nv" .. tostring(u[j].LevelToUnlockThisContract) .. ":" .. caminho
            end
            p(linha)
        end)
    end
end)

-- 5) contratos ativos do jogo e o tempo que falta
pcall(function()
    local m = FindFirstOf("B_HS3PlayerStateComp_ContractManager_C")
    if not m then p("== CONTRATOS: gerente não achado"); return end
    local a = m.ActiveContracts
    p("== CONTRATOS " .. #a)
    for j = 1, #a do
        pcall(function()
            local c = a[j]
            p(string.format("CONTRATO %s | tempo=%s | unico=%s", curto(c.ContractData), tostring(c.TimeLeftForContract), tostring(c.bIsUnique)))
        end)
    end
end)

-- 6) velocidade de andar
pcall(function()
    local pc = FindFirstOf("HS3PlayerController")
    local cm = pc.Pawn.CharacterMovement
    p(string.format("== ANDAR normal=%s agachado=%s", tostring(cm.MaxWalkSpeed), tostring(cm.MaxWalkSpeedCrouched)))
end)

-- 7) efeitos de contrato e contratos carregados (nomes mostram os de genética)
pcall(function()
    local ef = FindAllOf("HS3ContractEffect") or {}
    p("== EFEITOS " .. #ef)
    for i, e in ipairs(ef) do if i > 60 then break end; p("EFEITO " .. nomeClasse(e) .. " | " .. curto(e)) end
    local cs = FindAllOf("HS3ContractDataAsset") or {}
    p("== CONTRATOS_CARREGADOS " .. #cs)
    for i, c in ipairs(cs) do if i > 200 then break end; p("CDA " .. curto(c)) end
end)

local caminhos = { "ue4ss\\Mods\\HS3Discovery\\dev\\sonda_sexta.txt",
    "D:\\SteamLibrary\\steamapps\\common\\HS3\\HS3\\Binaries\\Win64\\ue4ss\\Mods\\HS3Discovery\\dev\\sonda_sexta.txt" }
for _, c in ipairs(caminhos) do
    local f = io.open(c, "wb")
    if f then f:write(table.concat(L, "\n")); f:close(); return #L .. " linhas em " .. c end
end
return "não consegui gravar; " .. #L .. " linhas"
