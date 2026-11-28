-- Sonda: instâncias do componente de navegação (pino) e relógio do jogo. Grava dev\sonda_pino_tempo.txt
local L = {}
local function p(s) L[#L + 1] = tostring(s) end
local navs = FindAllOf("NavigationPlayerStateComponent") or {}
p("navs: " .. #navs)
for i, n in ipairs(navs) do
    pcall(function()
        local q = n.QuickWaypoint
        local t = q.Transform.Translation
        p(string.format("%d %s hash=%s x=%.0f y=%.0f", i, n:GetFullName(), tostring(q.Hash), t.X, t.Y))
    end)
end
local envs = FindAllOf("EnvironmentManagerComponent") or {}
p("envs: " .. #envs)
for i, e in ipairs(envs) do
    pcall(function()
        p(string.format("%d %s solar=%s dia=%s/%s/%s clock=%s", i, e:GetFullName(), tostring(e.CurrentSolarTime),
            tostring(e.Day), tostring(e.Month), tostring(e.Year), tostring(e.InGameClockSpeed)))
    end)
end
local f = io.open(DIR_DEV_SAIDA or "ue4ss\\Mods\\HS3Discovery\\dev\\sonda_pino_tempo.txt", "w")
if f then f:write(table.concat(L, "\n")); f:close() end
return table.concat(L, " | ")
