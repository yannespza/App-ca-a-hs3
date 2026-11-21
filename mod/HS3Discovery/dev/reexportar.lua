local chunk = assert(loadfile(HS3.dir .. "Scripts\\exportar.lua"))
local exp = chunk()
local function writeFile(path, s)
    local f = io.open(path .. ".tmp", "wb"); f:write(s); f:close()
    os.remove(path); os.rename(path .. ".tmp", path)
end
exp.iniciar({ DIR = HS3.dir, log = HS3.log, writeFile = writeFile, json = HS3.json, tagName = HS3.tagName, valid = HS3.valid })
