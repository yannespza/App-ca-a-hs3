local M = loadfile("ue4ss\\Mods\\HS3Discovery\\Scripts\\mortos.lua")()
local ids = {}
for _, m in ipairs((M.ler())) do ids[m.id] = true end
local lista, ass = M.alvejados("Colorado_BlockOut", ids)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\teste_alvejados.txt", "wb")
f:write(HS3.json({ lista = lista, ass = ass })); f:close()
return #lista
