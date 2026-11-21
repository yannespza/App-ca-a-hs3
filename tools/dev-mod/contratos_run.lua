local chunk, e = loadfile(HS3.dir .. "Scripts\\contratos.lua")
if not chunk then return "erro " .. tostring(e) end
return chunk().ler({ DIR = HS3.dir, log = HS3.log, writeFile = function(p, s) local f = io.open(p, "wb"); f:write(s); f:close() end, json = HS3.json })
