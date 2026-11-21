-- teste: sincroniza a caixa de objetivos a cada 2 s sem reiniciar o jogo (o main.lua novo faz isso sozinho)
if _G.HS3_HUD_LOOP then HS3.log("hud_loop já está rodando"); return end
_G.HS3_HUD_LOOP = true
LoopAsync(2000, function()
    ExecuteInGameThread(function()
        local chunk = loadfile(HS3.dir .. "Scripts\\hud.lua")
        if chunk then
            local ok, e = pcall(function() chunk().sincronizar({ DIR = HS3.dir, log = HS3.log }) end)
            if not ok then HS3.log("hud_loop: " .. tostring(e)) end
        end
    end)
    return false
end)
HS3.log("hud_loop iniciado")
