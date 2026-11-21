local log = HS3.log
local function nome(o) local s = "?"; pcall(function() s = o:GetFullName() end); return s end
for _, cls in ipairs({ "W_HS3ContractObjectiveStatusList_C", "HS3HUDContractTrackerWidget", "W_HS3HUDObjectiveStatus_C", "W_HS3DefaultHUDLayout_C", "W_TutorialObjectiveStatus_C" }) do
    local ok, lista = pcall(FindAllOf, cls)
    local n = (ok and lista) and #lista or 0
    log(cls .. ": " .. n .. " instâncias")
    if ok and lista then
        for i, w in ipairs(lista) do
            if i > 4 then break end
            local info = nome(w)
            pcall(function() info = info .. " vis=" .. tostring(w:GetVisibility()) end)
            pcall(function() info = info .. " naTela=" .. tostring(w:IsInViewport()) end)
            pcall(function() info = info .. " titulo=" .. w.ContractTitle:GetText():ToString() end)
            pcall(function() info = info .. " filhos=" .. w.ObjectivePanel:GetChildrenCount() end)
            pcall(function() info = info .. " objClass=" .. nome(w.ObjectiveWidgetClass) end)
            pcall(function() info = info .. " rastreado=" .. nome(w.TrackedContract) end)
            log("  " .. info)
        end
    end
end
pcall(function()
    local cm = FindFirstOf("HS3PlayerStateComponent_ContractManager")
    log("ContractManager: " .. nome(cm) .. " rastreando=" .. nome(cm.CurrentTrackingContract) .. " ativos=" .. #cm.ActiveContracts)
end)
log("hud_teste fim")
