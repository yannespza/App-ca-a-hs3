"""Instalação no PC de quem for usar: acha o jogo, instala o UE4SS e o mod HS3Discovery e diz o que falta.

O UE4SS (carregador de mods, licença MIT) e o mod vão dentro do HS3Companion.exe; nada é baixado na instalação.
"""
import glob
import os
import shutil
import string
import sys

EXE_JOGO = "HS3-Win64-Shipping.exe"


def recursos():
    """Pasta com os arquivos embutidos no .exe (ou a pasta do repositório, rodando pelo Python)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def kit_ue4ss():
    return os.path.join(recursos(), "ue4ss_kit")


def mod_embutido():
    p = os.path.join(recursos(), "HS3Discovery")
    return p if os.path.isdir(p) else os.path.join(recursos(), "mod", "HS3Discovery")


def win64_de(pasta):
    """Aceita a pasta do jogo em qualquer nível (…\\common\\HS3, …\\HS3\\HS3, …\\Win64) e devolve a Win64."""
    if not pasta:
        return None
    pasta = os.path.normpath(pasta.strip().strip('"'))
    candidatos = [pasta, os.path.join(pasta, "Binaries", "Win64"), os.path.join(pasta, "HS3", "Binaries", "Win64")]
    # subiu demais? (ex.: escolheu …\Win64\ue4ss\Mods\HS3Discovery)
    p = pasta
    for _ in range(4):
        p = os.path.dirname(p)
        candidatos.append(p)
    for c in candidatos:
        if os.path.isfile(os.path.join(c, EXE_JOGO)):
            return c
    return None


def raiz_jogo(win64):
    """…\\common\\HS3\\HS3\\Binaries\\Win64 -> …\\common\\HS3"""
    return os.path.dirname(os.path.dirname(os.path.dirname(win64))) if win64 else None


def _bibliotecas_steam():
    pastas = []
    try:
        import winreg
        for raiz, chave in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(raiz, chave) as k:
                    for nome in ("SteamPath", "InstallPath"):
                        try:
                            pastas.append(winreg.QueryValueEx(k, nome)[0])
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass
    libs = []
    for s in pastas:
        s = os.path.normpath(s)
        libs.append(s)
        vdf = os.path.join(s, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, encoding="utf-8", errors="ignore") as f:
                for linha in f:
                    linha = linha.strip()
                    if linha.startswith('"path"'):
                        libs.append(os.path.normpath(linha.split('"')[3].replace("\\\\", "\\")))
        except OSError:
            pass
    return libs


def achar_jogo():
    """Procura o Hunting Simulator 3 nas bibliotecas da Steam e nos lugares comuns de cada disco."""
    candidatos = [os.path.join(l, "steamapps", "common", "HS3") for l in _bibliotecas_steam()]
    if os.name == "nt":
        for letra in string.ascii_uppercase:
            d = f"{letra}:\\"
            if not os.path.exists(d):
                continue
            for sub in (r"SteamLibrary\steamapps\common\HS3", r"Steam\steamapps\common\HS3",
                        r"Program Files (x86)\Steam\steamapps\common\HS3", r"Program Files\Steam\steamapps\common\HS3",
                        r"Jogos\SteamLibrary\steamapps\common\HS3", r"Games\SteamLibrary\steamapps\common\HS3"):
                candidatos.append(os.path.join(d, sub))
    vistos = set()
    for c in candidatos:
        w = win64_de(c)
        if w and os.path.normcase(w) not in vistos:
            vistos.add(os.path.normcase(w))
            return w
    return None


def pasta_save():
    """Onde o jogo grava o progresso (só para mostrar; o app não mexe no save)."""
    base = os.environ.get("LOCALAPPDATA") or ""
    for c in (os.path.join(base, "HS3", "Saved", "SaveGames"), os.path.join(base, "HS3")):
        if c and os.path.isdir(c):
            return c
    return None


def situacao(win64):
    if not win64 or not os.path.isfile(os.path.join(win64, EXE_JOGO)):
        return {"jogo": False, "ue4ss": False, "mod": False, "win64": win64}
    ue = os.path.join(win64, "ue4ss")
    mod = os.path.join(ue, "Mods", "HS3Discovery")
    return {
        "jogo": True, "win64": win64, "raiz": raiz_jogo(win64),
        "ue4ss": os.path.isfile(os.path.join(win64, "dwmapi.dll")) and os.path.isfile(os.path.join(ue, "UE4SS.dll")),
        "mod": os.path.isfile(os.path.join(mod, "Scripts", "main.lua")) and os.path.isfile(os.path.join(mod, "enabled.txt")),
        "pasta_mod": mod, "save": pasta_save(),
    }


def _copiar_arvore(origem, destino, sobrescrever=True):
    for raiz, _, arquivos in os.walk(origem):
        alvo = os.path.join(destino, os.path.relpath(raiz, origem))
        os.makedirs(alvo, exist_ok=True)
        for a in arquivos:
            d = os.path.join(alvo, a)
            if sobrescrever or not os.path.exists(d):
                shutil.copy2(os.path.join(raiz, a), d)


def instalar(win64):
    """Instala o UE4SS (só se faltar) e o mod. Não apaga nada do jogo nem do save."""
    s = situacao(win64)
    if not s["jogo"]:
        raise RuntimeError("Não achei o jogo nesta pasta (falta o HS3-Win64-Shipping.exe).")
    if not s["ue4ss"]:
        kit = kit_ue4ss()
        if not os.path.isdir(kit):
            raise RuntimeError("Os arquivos do UE4SS não vieram dentro do programa.")
        # se já existir um UE4SS de outra pessoa, mantém as configurações dela
        _copiar_arvore(kit, win64, sobrescrever=False)
        for obrig in ("dwmapi.dll", os.path.join("ue4ss", "UE4SS.dll")):
            shutil.copy2(os.path.join(kit, obrig), os.path.join(win64, obrig))
    origem = mod_embutido()
    if not os.path.isdir(origem):
        raise RuntimeError("O mod HS3Discovery não veio dentro do programa.")
    destino = os.path.join(win64, "ue4ss", "Mods", "HS3Discovery")
    _copiar_arvore(origem, destino, sobrescrever=True)
    open(os.path.join(destino, "enabled.txt"), "a").close()
    return situacao(win64)


def escolher_pasta(titulo="Escolha a pasta do Hunting Simulator 3"):
    """Abre a janela do Windows para escolher uma pasta (no PC onde o app roda)."""
    try:
        import tkinter
        from tkinter import filedialog
        r = tkinter.Tk()
        r.withdraw()
        r.attributes("-topmost", True)
        p = filedialog.askdirectory(title=titulo, mustexist=True)
        r.destroy()
        return os.path.normpath(p) if p else None
    except Exception:
        return None


def arquivos_mod_iguais(win64):
    """True se os scripts do mod no jogo são os mesmos do programa (senão: reinstalar / atualizar)."""
    origem = os.path.join(mod_embutido(), "Scripts")
    destino = os.path.join(win64 or "", "ue4ss", "Mods", "HS3Discovery", "Scripts")
    for a in glob.glob(os.path.join(origem, "*.lua")):
        b = os.path.join(destino, os.path.basename(a))
        try:
            with open(a, "rb") as fa, open(b, "rb") as fb:
                if fa.read() != fb.read():
                    return False
        except OSError:
            return False
    return True
