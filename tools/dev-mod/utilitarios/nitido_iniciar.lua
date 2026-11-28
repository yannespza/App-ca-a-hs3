local chunk, e = loadfile(HS3.dir .. "Scripts\\nitido.lua")
if not chunk then return "erro " .. tostring(e) end
chunk().iniciar({ DIR = HS3.dir, log = HS3.log })
return "iniciado"
