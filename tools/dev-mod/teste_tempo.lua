-- Teste: avança 1 hora no relógio do jogo
local e = FindFirstOf("EnvironmentManagerComponent")
if not (e and e:IsValid()) then return "sem env" end
local antes = e.CurrentSolarTime
local ok, err = pcall(function() e:SkipSolarTime(1.0) end)
local r = "antes=" .. tostring(antes) .. " interface=" .. tostring(ok) .. " " .. tostring(err)
if not ok then
    local ok2, err2 = pcall(function() e:SkipSolarTimeInternal(1.0) end)
    r = r .. " internal=" .. tostring(ok2) .. " " .. tostring(err2)
end
return r .. " depois=" .. tostring(e.CurrentSolarTime)
