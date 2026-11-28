local ch, e = loadfile(HS3.dir .. "Scripts\\licencas.lua")
if not ch then return "erro " .. tostring(e) end
local r = ch().ler({ DIR = HS3.dir, log = HS3.log, emit = HS3.emit, json = HS3.json,
                     writeFile = function(p, s) local f = io.open(p, "wb"); f:write(s); f:close() end })
return r and (#r.licencas .. " licenças, mapa " .. tostring(r.mapa)) or "sem dados"
