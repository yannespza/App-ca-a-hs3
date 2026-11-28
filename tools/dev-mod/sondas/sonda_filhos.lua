local L = {}
local function p(s) L[#L + 1] = s end
local function tags(c) local t = {}; pcall(function() c.GameplayTags:ForEach(function(_, e) t[#t + 1] = e:get().TagName:ToString() end) end); return table.concat(t, ",") end
local est = {}
pcall(function() FindFirstOf("NavigationSaveData").DiscoverStatusLists:ForEach(function(_, e) e:get().DiscoveryStatesList:ForEach(function(_, st) local s = st:get(); est[s.ActorHash] = s.DiscoveryStatus.TagName:ToString() end) end) end)
local n, ce = 0, 0
pcall(function()
    FindFirstOf("NavigationContentComponent").NavigationActorDataChildsMap:ForEach(function(k, v)
        local pai = k:get()
        v:get().ActorDataArray:ForEach(function(_, e)
            local a = e:get(); n = n + 1
            local es = est[a.Hash]; if es then ce = ce + 1 end
            if n <= 8 or (es and ce <= 6) then
                local t = a.Transform.Translation
                p(string.format("FILHO pai=%s hash=%s %.0f %.0f est=%s icone=%s extra=[%s]", tostring(pai), tostring(a.Hash), t.X, t.Y, tostring(es),
                    a.MapIconDataId.PrimaryAssetName:ToString(), tags(a.ExtraTags)))
            end
        end)
    end)
end)
p("FILHOS " .. n .. " com estado " .. ce)
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_filhos.txt", "wb")
if f then f:write(table.concat(L, "\n")); f:close() end
return #L .. " linhas"
