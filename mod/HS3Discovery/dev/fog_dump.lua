local DEV = HS3.dir .. "dev\\"
local result = "nada"
FindFirstOf("NavigationSaveData").FogOfWarLists:ForEach(function(_, e)
    local f = e:get()
    if f.LevelName:ToString():find("Texas") then
        local arr = f.FogArray
        local n = arr:GetArrayNum()
        local fh = io.open(DEV .. "nevoa_texas.bin", "wb")
        local buf = {}
        for i = 1, n do
            buf[#buf+1] = string.char(arr[i])
            if #buf == 65536 then fh:write(table.concat(buf)); buf = {} end
        end
        fh:write(table.concat(buf)); fh:close()
        result = "bytes=" .. n
    end
end)
return result
