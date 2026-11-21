local chunk = loadfile(HS3.dir .. "Scripts\\mochila.lua")
local mo = chunk()
local ctx = { DIR = HS3.dir, log = HS3.log, emit = HS3.emit, json = HS3.json, tagName = HS3.tagName,
  writeFile = function(p, s) local f = io.open(p, "wb"); f:write(s); f:close() end }
local r = mo.salvar(ctx)
return r and #r.itens or "nil"
