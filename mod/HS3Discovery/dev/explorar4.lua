local out = {}
local function add(k, v) out[#out+1] = k .. ": " .. tostring(v) end
local function try(n, f) local ok, e = pcall(f); if not ok then add("ERRO " .. n, e) end end
local function pid(id) return id.PrimaryAssetType.Name:ToString() .. ":" .. id.PrimaryAssetName:ToString() end

try("roupa_equipada", function()
    FindFirstOf("HS3CharacterAssetSaveGame").SavedCharacterParts:ForEach(function(_, e)
        local p = e:get()
        add("parte", pid(p.CosmeticId) .. " tipo=" .. tostring(HS3.tagName(p.CosmeticType)))
    end)
end)

local attrs = {}
try("atributos", function()
    FindFirstOf("HS3AttributeDataAsset").AttributeConfigs:ForEach(function(k, v)
        local a = k:get()
        local nome = a.AttributeName:ToString()
        attrs[#attrs + 1] = { nome = nome, ref = a, cosm = v:get().bIsInfluencedByCosmetics }
        add("attr", nome .. " cosmetico=" .. tostring(v:get().bIsInfluencedByCosmetics))
    end)
end)

try("roupas_valores", function()
    local lib = StaticFindObject("/Script/HS3CoreRuntime.Default__HS3AttributeFunctionLibrary")
    for _, c in ipairs(FindAllOf("HS3ClothingDataAsset") or {}) do
        local nome = c:GetFName():ToString()
        pcall(function() nome = nome .. " (" .. c.DisplayName:ToString() .. ")" end)
        local vals = {}
        for _, a in ipairs(attrs) do
            if a.cosm then
                local ok, v = pcall(function() return lib:GetAttributeValueFromAssetRaw(a.ref, c) end)
                vals[#vals + 1] = a.nome .. "=" .. (ok and tostring(v) or ("erro " .. tostring(v)))
            end
        end
        add("roupa", nome .. " | " .. table.concat(vals, " "))
    end
end)

try("teleporte", function()
    local pc = FindFirstOf("HS3PlayerController")
    local loc = pc.Pawn:K2_GetActorLocation()
    add("antes", string.format("%.0f,%.0f,%.0f", loc.X, loc.Y, loc.Z))
    local nav = FindFirstOf("NavigationPlayerStateComponent")
    add("pode_viajar", tostring(nav.bIsFastTravelAllowed))
    local alvo = { Rotation = {X=0,Y=0,Z=0,W=1}, Translation = {X=loc.X + 1500, Y=loc.Y, Z=loc.Z + 100}, Scale3D = {X=1,Y=1,Z=1} }
    nav:Server_SafeFastTravel({ alvo })
    add("teleporte_chamado", "ok")
end)

local f = io.open(HS3.dir .. "dev\\resultado_explorar4.txt", "w"); f:write(table.concat(out, "\n")); f:close()
return #out
