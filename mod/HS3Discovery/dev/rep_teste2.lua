local out = {}
local function add(k, v) out[#out+1] = k .. ": " .. tostring(v) end
local rm = FindFirstOf("HS3PlayerControllerComponent_ReputationManager")
local tag = { TagName = FName("NPC.Vendor.SportsShooter") }
add("antes", rm:GetReputationForVendor(tag))
local chunk = FindFirstOf("HS3ReputationSaveSlotChunk")
local ok, e = pcall(function()
    chunk.ReputationSaveDataPerMap:ForEach(function(k, v)
        local nome = k:get().PrimaryAssetName:ToString()
        if nome:find("Texas") then
            v:get().ReputationPerVendor:ForEach(function(vk, vv)
                if HS3.tagName(vk:get()) == "NPC.Vendor.SportsShooter" then
                    local d = vv:get()
                    add("salvo_antes", d.Reputation)
                    d.Reputation = d.Reputation + 10
                    add("salvo_depois", d.Reputation)
                end
            end)
        end
    end)
end)
add("escrita", ok and "ok" or e)
add("depois", rm:GetReputationForVendor(tag))
pcall(function() add("progresso", rm:GetReputationProgressForVendor(tag)) end)
local f = io.open(HS3.dir .. "dev\\resultado_rep2.txt", "w"); f:write(table.concat(out, "\n")); f:close()
return #out
