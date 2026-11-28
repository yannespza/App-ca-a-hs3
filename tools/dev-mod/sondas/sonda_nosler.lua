local ESP = {"Animals.Types.Antelope.Nilgai","Animals.Types.Antelope.ScimitarOryx","Animals.Types.Bear.Black","Animals.Types.Bird.Chukar","Animals.Types.Bird.Dove.Mourning","Animals.Types.Bird.Duck.Black","Animals.Types.Bird.Duck.Bufflehead","Animals.Types.Bird.Duck.NorthernPintail","Animals.Types.Bird.Goose.Canada","Animals.Types.Bird.MontezumaQuail","Animals.Types.Bird.Pheasant","Animals.Types.Bird.Quail","Animals.Types.Bird.Teal.GreenWinged","Animals.Types.Bird.Turkey.RioGrande","Animals.Types.Bison.American.Plains","Animals.Types.Canine.Coyote.Plains","Animals.Types.Deer.DesertMule","Animals.Types.Deer.MountainMule","Animals.Types.Deer.WhiteTail.Colorado","Animals.Types.Deer.WhiteTail.Hub","Animals.Types.Deer.WhiteTail.Texas","Animals.Types.Elk","Animals.Types.Feline.Bobcat.Colorado","Animals.Types.Feline.Bobcat.Texas","Animals.Types.Feline.Cougar","Animals.Types.Fox.Red","Animals.Types.Hare.JackRabbit","Animals.Types.Peccary.Collared","Animals.Types.Pig.Feral","Animals.Types.PrairieDog.BlackTail","Animals.Types.Pronghorn.American","Animals.Types.Rabbit.CottonTail.Colorado","Animals.Types.Rabbit.CottonTail.Texas","Animals.Types.Sheep.Aoudad","Animals.Types.Sheep.Bighorn.Colorado","Animals.Types.Sheep.Bighorn.Texas","Animals.Types.Wolf.Gray"}
local comp = StaticFindObject("/Script/HS3AnimalsRuntime.Default__CaliberCompatibilityFunctionLibrary")
local L = {}
for _, e in ipairs(ESP) do
    local ok, r = pcall(function() return comp:IsCaliberCompatibleWithAnimal({ TagName = FName("Inventory.Ammo.Bullet.27.Nosler") }, { TagName = FName(e) }) end)
    L[#L + 1] = e .. " " .. (ok and (r and "1" or "0") or "E")
end
local f = io.open("ue4ss\\Mods\\HS3Discovery\\dev\\sonda_nosler.txt", "wb"); f:write(table.concat(L, "\n")); f:close()
return #L
