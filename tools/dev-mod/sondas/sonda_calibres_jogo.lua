local ESP = {"Animals.Types.Antelope.Nilgai","Animals.Types.Antelope.ScimitarOryx","Animals.Types.Bear.Black","Animals.Types.Bird.Chukar","Animals.Types.Bird.Dove.Mourning","Animals.Types.Bird.Duck.Black","Animals.Types.Bird.Duck.Bufflehead","Animals.Types.Bird.Duck.NorthernPintail","Animals.Types.Bird.Goose.Canada","Animals.Types.Bird.MontezumaQuail","Animals.Types.Bird.Pheasant","Animals.Types.Bird.Quail","Animals.Types.Bird.Teal.GreenWinged","Animals.Types.Bird.Turkey.RioGrande","Animals.Types.Bison.American.Plains","Animals.Types.Canine.Coyote.Plains","Animals.Types.Deer.DesertMule","Animals.Types.Deer.MountainMule","Animals.Types.Deer.WhiteTail.Colorado","Animals.Types.Deer.WhiteTail.Hub","Animals.Types.Deer.WhiteTail.Texas","Animals.Types.Elk","Animals.Types.Feline.Bobcat.Colorado","Animals.Types.Feline.Bobcat.Texas","Animals.Types.Feline.Cougar","Animals.Types.Fox.Red","Animals.Types.Hare.JackRabbit","Animals.Types.Peccary.Collared","Animals.Types.Pig.Feral","Animals.Types.PrairieDog.BlackTail","Animals.Types.Pronghorn.American","Animals.Types.Rabbit.CottonTail.Colorado","Animals.Types.Rabbit.CottonTail.Texas","Animals.Types.Sheep.Aoudad","Animals.Types.Sheep.Bighorn.Colorado","Animals.Types.Sheep.Bighorn.Texas","Animals.Types.Wolf.Gray"}
local CAL = {"Inventory.Ammo.Arrow.350gr","Inventory.Ammo.Arrow.450gr","Inventory.Ammo.Arrow.550gr","Inventory.Ammo.Bolt.350gr","Inventory.Ammo.Bolt.450gr","Inventory.Ammo.Bolt.550gr","Inventory.Ammo.Bullet.22-250.Rem","Inventory.Ammo.Bullet.22.LR","Inventory.Ammo.Bullet.223.Rem","Inventory.Ammo.Bullet.243.Win","Inventory.Ammo.Bullet.270.WSM","Inventory.Ammo.Bullet.270.Win","Inventory.Ammo.Bullet.30-06.Spr","Inventory.Ammo.Bullet.30-30","Inventory.Ammo.Bullet.300.Win","Inventory.Ammo.Bullet.308.Win","Inventory.Ammo.Bullet.338.WM","Inventory.Ammo.Bullet.38-40.Win","Inventory.Ammo.Bullet.9-3x62","Inventory.Ammo.Shell.12G.Bird","Inventory.Ammo.Shell.12G.Bird.Medium","Inventory.Ammo.Shell.12G.Buck","Inventory.Ammo.Shell.12G.Slug","Inventory.Ammo.Shell.20G.Bird","Inventory.Ammo.Shell.20G.Bird.Medium","Inventory.Ammo.Shell.20G.Buck","Inventory.Ammo.Shell.20G.Slug"}
local L = {}
local comp = StaticFindObject("/Script/HS3AnimalsRuntime.Default__CaliberCompatibilityFunctionLibrary")
L[#L + 1] = "LIB " .. tostring(comp and comp:IsValid())
for _, e in ipairs(ESP) do
    local linha = {}
    for _, c in ipairs(CAL) do
        local ok, r = pcall(function() return comp:IsCaliberCompatibleWithAnimal({ TagName = FName(c) }, { TagName = FName(e) }) end)
        linha[#linha + 1] = ok and (r and "1" or "0") or "E"
    end
    L[#L + 1] = e .. " " .. table.concat(linha, "")
end
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_calibres_jogo.txt", "wb"); f:write(table.concat(L, "\n")); f:close()
return #L
