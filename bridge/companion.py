"""HS3 Companion - ponte entre o mod UE4SS do Hunting Simulator 3 e o app.

Lê state.json e events.jsonl gravados pelo mod, gera e valida missões,
paga recompensas escrevendo comandos em cmd.txt e serve o app em http://localhost.
Só usa a biblioteca padrão do Python.
"""
import hmac
import socket
import json
import random
import re
import urllib.parse
import math
import os
import sys
import threading
import time
import uuid
import webbrowser
import shutil
import ssl
import subprocess
import tempfile
import urllib.request
import zipfile
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import extras
import imagens
import instalador
import missoes
import manejo
import mapa


# ------------------------------------------------------------------ caminhos
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    WEB_DIR = os.path.join(sys._MEIPASS, "web")  # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    WEB_DIR = os.path.join(BASE_DIR, "web")

if getattr(sys, "frozen", False) and (sys.stdout is None or sys.stderr is None):
    try:   # registro grande: guarda só o fim
        _p = os.path.join(BASE_DIR, "hs3companion.log")
        if os.path.getsize(_p) > 300_000:
            with open(_p, "rb") as _f:
                _f.seek(-100_000, 2)
                _fim = _f.read()
            with open(_p, "wb") as _f:
                _f.write(_fim[_fim.find(b"\n") + 1:])
    except OSError:
        pass
    _log = open(os.path.join(BASE_DIR, "hs3companion.log"), "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = _log


def _ler_versao():
    try:
        with open(os.path.join(os.path.dirname(WEB_DIR), "versao.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "dev"


VERSAO = _ler_versao()
REPO = "yannespza/App-ca-a-hs3"

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DADOS_PATH = os.path.join(BASE_DIR, "dados_hs3.json")

CONFIG_PADRAO = {
    "pasta_mod": "",          # achada sozinha (ou escolhida na tela Instalação do app)
    "porta": 8765,
    "abrir_navegador": True,
    "missoes_ativas": 4,
    "ofertas": 8,
    "voltar_ao_ultimo_local": True,
    "contratos_no_jogo": True,
    "limite_diario_creditos": 20000,
    "github_token": "",
    "celular": True,          # aceita o celular na mesma rede Wi-Fi (com PIN)
    "pin": "",                # criado sozinho na primeira vez
    "versao_config": 3,
}

# ------------------------------------------------------------------ catálogo
GRUPOS = [
    # (chave, nome em português, palavras que identificam no tag/classe)
    ("pato", "Pato / marreca", ["duck", "mallard", "pintail", "bufflehead", "teal", "wigeon", "canvasback"]),
    ("ganso", "Ganso", ["goose"]),
    ("peru", "Peru-selvagem", ["turkey"]),
    ("faisao", "Faisão / perdiz", ["pheasant", "chukar", "partridge", "grouse", "woodcock"]),
    ("codorna", "Codorna", ["quail"]),
    ("pomba", "Pomba", ["dove", "pigeon"]),
    ("antilope", "Antílope", ["antelope", "nilgai", "oryx"]),
    ("felino", "Felino", ["feline", "bobcat", "cougar", "puma", "lion", "lynx"]),
    ("roedor", "Cão-da-pradaria", ["prairiedog"]),
    ("cervo", "Veado", ["deer", "cervidae"]),
    ("alce", "Uapiti / Alce", ["elk", "moose", "wapiti"]),
    ("antilocapra", "Antilocapra", ["pronghorn"]),
    ("porco", "Javali / queixada", ["hog", "boar", "pig", "suidae", "javelina", "peccary"]),
    ("coiote", "Coiote", ["coyote", "raccoondog"]),
    ("lobo", "Lobo", ["wolf"]),
    ("raposa", "Raposa", ["fox", "marten"]),
    ("coelho", "Coelho / lebre", ["rabbit", "hare", "jackrabbit", "cottontail"]),
    ("urso", "Urso", ["bear"]),
    ("carneiro", "Carneiro / cabra", ["sheep", "bighorn", "goat", "ram", "aoudad", "mouflon"]),
    ("bisao", "Bisão", ["bison", "buffalo"]),
]


def grupo_de(texto):
    t = (texto or "").lower().replace("_", "")
    for chave, nome, palavras in GRUPOS:
        if any(p in t for p in palavras):
            return chave, nome
    return "outro", "Outro animal"


# Nomes em português do Brasil, iguais aos do próprio jogo (diário de campo). O app usa primeiro os
# títulos lidos do jogo (TITULOS_JOGO); esta tabela só vale enquanto os dados do jogo não foram lidos.
NOMES_PT = {
    "Antelope.Nilgai": "Nilgai", "Antelope.ScimitarOryx": "Órix-de-cimitarra", "Bear.Black": "Urso-negro",
    "Bear.Brown": "Urso-pardo", "Bird.Chukar": "Perdiz-chukar", "Bird.Dove.Mourning": "Pomba-chorona",
    "Bird.Duck.Black": "Pato-preto-americano", "Bird.Duck.Bufflehead": "Marreca-de-cabeça-bufa",
    "Bird.Duck.NorthernPintail": "Marreca-de-rabo-pintado-do-norte", "Bird.Duck.Mallard": "Pato-real",
    "Bird.Duck.Tufted": "Marreca-de-topete", "Bird.Goose.Canada": "Ganso-canadense-gigante",
    "Bird.Goose.Graylag": "Ganso-patola-cinzento", "Bird.Grouse.Black": "Galo-lira-preto",
    "Bird.MontezumaQuail": "Codorna-de-Montezuma", "Bird.Partridge.Gray": "Perdiz-cinzenta", "Bird.Pheasant": "Faisão-comum",
    "Bird.Quail": "Codorna-escamada", "Bird.Teal.GreenWinged": "Marreca-de-asa-verde",
    "Bird.Turkey.RioGrande": "Peru-selvagem do Rio Grande", "Bird.Woodcock": "Galinhola-eurasiana",
    "Bison.American": "Bisão das planícies", "Bison": "Bisão-europeu", "Boar": "Javali da Europa Central",
    "Canine.Coyote": "Coiote das planícies do Texas", "Deer.DesertMule": "Veado-mula do deserto",
    "Deer.MountainMule": "Veado-mula das Montanhas Rochosas", "Deer.Red": "Veado-vermelho", "Deer.Roe": "Corça-ocidental",
    "Deer.WhiteTail": "Veado-de-cauda-branca", "Elk": "Uapiti das Montanhas Rochosas",
    "Feline.Bobcat": "Lince-pardo", "Feline.Cougar": "Puma", "Feline.Lynx": "Lince-do-norte", "Fox.Red": "Raposa-vermelha",
    "Hare.Brown": "Lebre-comum", "Hare.JackRabbit": "Lebre-de-cauda-preta", "Marten": "Marta-do-pinheiro europeia",
    "Moose": "Alce", "Peccary.Collared": "Queixada-de-coleira", "Pig.Feral": "Javali selvagem",
    "PrairieDog.BlackTail": "Cão-da-pradaria-de-cauda-preta", "Pronghorn.American": "Antilocapra-americano",
    "Rabbit.CottonTail": "Coelho-de-cauda-de-algodão", "RaccoonDog": "Cão-guaxinim-comum",
    "Sheep.Aoudad": "Aoudad", "Sheep.Bighorn": "Carneiro-selvagem", "Sheep.Mouflon": "Muflão", "Wolf.Gray": "Lobo-cinzento",
}
TITULOS_JOGO = {}   # "Animals.Types.Deer.WhiteTail.Texas" -> "Veado-de-cauda-branca" (do diário do jogo, jogo_dados.json)


def nome_especie(tag):
    """Nome em português da espécie a partir da tag do jogo (Animals.Types.Deer.WhiteTail.Texas -> Veado-de-cauda-branca)."""
    if not tag:
        return None
    if tag in TITULOS_JOGO:
        return TITULOS_JOGO[tag]
    pref = [t for t in TITULOS_JOGO if t.startswith(tag + ".") or tag.startswith(t + ".")]
    if pref:
        return TITULOS_JOGO[sorted(pref, key=len)[0]]
    resto = tag.replace("Animals.Types.", "")
    for chave in sorted(NOMES_PT, key=len, reverse=True):
        if resto == chave or resto.startswith(chave + "."):
            return NOMES_PT[chave]

    def espacar(t):
        out = ""
        for i, c in enumerate(t):
            if i and c.isupper() and not t[i - 1].isupper():
                out += " "
            out += c
        return out

    partes = [p for p in tag.split(".")[2:] if p.lower() not in ("texas", "colorado", "a", "b")] or tag.split(".")[-1:]
    if len(partes) == 2:
        if partes[0].lower() in partes[1].lower():
            return espacar(partes[1])
        return f"{espacar(partes[1])} {espacar(partes[0])}"
    return espacar(partes[-1])


SEXO = {0: "Macho", 1: "Fêmea", 2: "Indefinido"}
AGENTES = (("NPC.Vendor.SportsShooter", "Atirador esportivo"), ("NPC.Vendor.Ranger", "Guarda-florestal"),
           ("NPC.Vendor.Butcher", "Açougueiro"), ("NPC.Vendor.DogHandler", "Adestrador de cães"))
ACOES = {0: "Descartado", 1: "Vendido (danificado)", 2: "Vendido", 3: "Taxidermia"}


# ------------------------------------------------------------------ persistência
def carregar_json(path, padrao):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


def salvar_json(path, dados):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def carregar_config():
    cfg = dict(CONFIG_PADRAO)
    salvo = carregar_json(CONFIG_PATH, {})
    cfg.update({k: v for k, v in salvo.items() if k in CONFIG_PADRAO})   # descarta opções antigas (Ollama etc.)
    if salvo.get("versao_config", 1) < 3:
        # versões antigas gravaram 3 ofertas / 3 ativos: passa para os limites novos
        cfg["missoes_ativas"], cfg["ofertas"] = CONFIG_PADRAO["missoes_ativas"], CONFIG_PADRAO["ofertas"]
        cfg["versao_config"] = CONFIG_PADRAO["versao_config"]
    if not os.path.isfile(os.path.join(cfg.get("pasta_mod") or "", "Scripts", "main.lua")):
        # primeira vez (ou o jogo mudou de lugar): procura o jogo e usa o mod se já estiver instalado
        try:
            w = instalador.achar_jogo()
            sit = instalador.situacao(w)
            if sit.get("mod"):
                cfg["pasta_mod"] = sit["pasta_mod"]
        except Exception as e:
            print("procura do jogo falhou:", repr(e))
    if not re.fullmatch(r"\d{4,8}", str(cfg.get("pin") or "")):
        import secrets
        cfg["pin"] = f"{secrets.randbelow(10000):04d}"
    if cfg != {k: v for k, v in salvo.items()}:
        salvar_json(CONFIG_PATH, cfg)
    return cfg


def ips_locais():
    """Todos os endereços IPv4 de rede de casa deste PC (cabo, Wi-Fi; sem os virtuais conhecidos)."""
    import socket
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith(("127.", "169.254.")):
                ips.append(ip)
    except Exception:
        pass
    casa = lambda ip: ip.startswith("192.168.") or ip.startswith("10.") or any(ip.startswith(f"172.{n}.") for n in range(16, 32))
    return sorted(ips, key=lambda ip: (not ip.startswith("192.168."), not casa(ip)))


def ip_local():
    """Endereço deste PC na rede de casa (o celular abre http://<ip>:<porta>)."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))     # não envia nada: só descobre por qual placa sairia
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None


PAGINA_PIN = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HS3 Companion</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#121c19;color:#e3e8dc;font:16px system-ui,sans-serif}
form{display:grid;gap:14px;padding:28px;border-radius:16px;background:#1a2723;border:1px solid #30443c;width:min(320px,86vw);text-align:center}
h1{margin:0;font-size:22px}p{margin:0;color:#9fae9f;font-size:14px}input{font-size:28px;letter-spacing:8px;text-align:center;padding:10px;border-radius:10px;border:1px solid #43594f;background:#101916;color:#e3e8dc}
button{font-size:17px;font-weight:700;padding:12px;border:0;border-radius:10px;background:#ff6b1a;color:#1b0d04}.erro{color:#f0a27a}</style></head>
<body><form method="get" action="/"><h1>HS3 Companion</h1><p>Digite o PIN que aparece no app do PC (botão <b>Celular</b>), ou leia o QR code.</p>
__ERRO__<input name="pin" inputmode="numeric" autocomplete="one-time-code" maxlength="8" autofocus><button>Entrar</button></form></body></html>"""


# ------------------------------------------------------------------ geometria
def distancia_m(a, b):
    if not a or not b:
        return None
    dx, dy, dz = a["x"] - b["x"], a["y"] - b["y"], a.get("z", 0) - b.get("z", 0)
    return math.sqrt(dx * dx + dy * dy + dz * dz) / 100.0


def direcao(jogador, alvo, yaw):
    """Ângulo relativo (graus) do alvo em relação para onde o jogador olha. 0 = frente, 90 = direita."""
    if not jogador or not alvo or yaw is None:
        return None
    ang = math.degrees(math.atan2(alvo["y"] - jogador["y"], alvo["x"] - jogador["x"]))
    rel = (ang - yaw + 540) % 360 - 180
    return rel


# ------------------------------------------------------------------ missões
ESTADOS_CALMOS = {1, 2, 4, 256, 512}   # parado, vagando, andando, comendo, dormindo


def nome_grupo(chave):
    return dict((g[0], g[1]) for g in GRUPOS).get(chave, chave)


ARMA_TIPOS = {}   # "ID_Browning_XBolt_EV" -> "rifle" | "espingarda" | "arco" | "curta_arma" (preenchido com jogo_dados.json)


def arma_tipo_de(arma):
    return ARMA_TIPOS.get((arma or "").split(":")[-1])


def dentro(pos, local, raio_m=60):
    d = distancia_m(pos, local)
    return d is not None and d <= raio_m


def avaliar_missoes(dados, evento, reserva=None):
    """Atualiza o progresso das missões ativas com um evento (abate confirmado, marcação ou posição).
    Cada contrato vale só na reserva onde foi oferecido."""
    concluidas = []
    for m in dados["missoes"]:
        if m["status"] != "ativa" or evento.get("ts", 0) < max(m.get("aceita_em", m["criada"]), m.get("etapa_desde", 0)) - 2:
            continue
        if m.get("reserva") and reserva and m["reserva"] != reserva:
            continue
        t = m["tipo"]
        if t == "combo":
            ev = dict(evento)
            if not missoes.conta(m, ev, dentro, arma_tipo_de):
                continue
            chave = f"{ev['tipo']}:{ev.get('id')}"
            if chave in m["contados"]:
                continue
            m["contados"].append(chave)
            m["progresso"] = len(m["contados"])
            if m["progresso"] >= m["meta"]:
                if missoes.proxima_etapa(m):       # campanha: começa a etapa seguinte
                    continue
                m["status"] = "concluida"
                m["concluida_em"] = time.time()
                concluidas.append(m)
            continue
        chave = f"{evento['tipo']}:{evento.get('id')}"
        if chave in m["contados"]:
            continue
        conta = False
        if evento["tipo"] == "abate_confirmado":
            if t == "abater_qualquer":
                conta = True
            elif t == "abater_grupo":
                conta = evento.get("grupo") == m["grupo"]
            elif t == "distancia":
                d = evento.get("distancia_m") or 0
                conta = d >= m.get("dist_min", m.get("distancia", 0))   # só distância mínima
            elif t in ("calibre", "atrair", "nao_detectado") and (not m.get("grupo") or evento.get("grupo") == m["grupo"]):
                if t == "calibre":
                    conta = evento.get("calibre_compativel") is True
                elif t == "atrair":
                    conta = evento.get("atraido") is True
                else:
                    conta = missoes.nao_percebeu(evento.get("estado_animal"))
            elif t == "genetica":
                conta = (evento.get("genetica") or 0) >= m["genetica"]
            elif t == "sem_torre":
                conta = evento.get("torre") is False
        elif evento["tipo"] == "marcado" and t == "marcar":
            conta = True
        elif evento["tipo"] == "posicao" and t == "visitar":
            conta = dentro(evento.get("pos"), m.get("local"))
        if conta:
            m["contados"].append(chave)
            m["progresso"] = len(m["contados"])
            if m["progresso"] >= m["meta"]:
                m["status"] = "concluida"
                m["concluida_em"] = time.time()
                concluidas.append(m)
    return concluidas


# ------------------------------------------------------------------ atualização automática
def _versao_tupla(v):
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0,)


def _contexto_ssl():
    """Certificados: os do Windows + o pacote certifi embutido no programa.
    No Windows, o Python só enxerga os certificados-raiz que já foram baixados pelo sistema;
    o navegador baixa os que faltam na hora, o Python não. Por isso juntamos os dois."""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


CTX_SSL = _contexto_ssl()


def _curl_windows(url, destino=None, headers=None, so_cabecalho=False):
    """Plano C: o curl.exe que vem no Windows 10/11 usa a verificação do próprio Windows."""
    curl = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")
    if not os.path.isfile(curl):
        raise RuntimeError("curl.exe não encontrado")
    cmd = [curl, "-sS", "--max-time", "120"]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if so_cabecalho:
        cmd += ["-I"]
    else:
        cmd += ["-L", "--fail"]
    if destino:
        cmd += ["-o", destino]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("curl: " + r.stderr.decode("utf-8", "ignore").strip()[:200])
    return r.stdout


class Atualizador:
    def __init__(self, cfg):
        self.cfg = cfg
        self.ultima = None          # dados da última release
        self.erro = None
        self.estado = "parado"      # parado | verificando | baixando | reiniciando | erro
        self.verificado_em = 0

    def _req(self, url, accept="application/vnd.github+json"):
        h = {"Accept": accept, "User-Agent": "HS3Companion"}
        if self.cfg.get("github_token"):
            h["Authorization"] = "Bearer " + self.cfg["github_token"]
        return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60, context=CTX_SSL)

    def _ultima_pelo_site(self):
        """Plano B sem a API: github.com/<repo>/releases/latest redireciona para a tag mais nova."""
        class SemRedirecionar(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        abridor = urllib.request.build_opener(SemRedirecionar, urllib.request.HTTPSHandler(context=CTX_SSL))
        try:
            abridor.open(urllib.request.Request(f"https://github.com/{REPO}/releases/latest",
                                                headers={"User-Agent": "HS3Companion"}), timeout=30)
        except urllib.error.HTTPError as e:
            destino = e.headers.get("Location", "")
            tag = destino.rstrip("/").rsplit("/", 1)[-1]
            if tag.startswith("v"):
                url = f"https://github.com/{REPO}/releases/download/{tag}/HS3Companion.zip"
                return {"versao": tag.lstrip("v"), "asset_api": url, "asset_url": url, "notas": ""}
            raise
        raise RuntimeError("resposta inesperada do GitHub")

    def _ultima_pelo_curl(self):
        cab = _curl_windows(f"https://github.com/{REPO}/releases/latest", headers={"User-Agent": "HS3Companion"},
                            so_cabecalho=True).decode("utf-8", "ignore")
        m = re.search(r"(?im)^location:\s*(\S+)", cab)
        tag = m.group(1).rstrip("/").rsplit("/", 1)[-1] if m else ""
        if not tag.startswith("v"):
            raise RuntimeError("resposta inesperada do GitHub (curl)")
        url = f"https://github.com/{REPO}/releases/download/{tag}/HS3Companion.zip"
        return {"versao": tag.lstrip("v"), "asset_api": url, "asset_url": url, "notas": "", "via_curl": True}

    def verificar(self):
        self.estado = "verificando"
        self.erro = None
        try:
            with self._req(f"https://api.github.com/repos/{REPO}/releases/latest") as r:
                rel = json.load(r)
            asset = next(a for a in rel["assets"] if a["name"].endswith(".zip"))
            self.ultima = {"versao": rel["tag_name"].lstrip("v"), "asset_api": asset["url"],
                           "asset_url": asset["browser_download_url"], "notas": rel.get("body", "")}
        except Exception as e1:
            try:
                self.ultima = self._ultima_pelo_site()
            except Exception as e2:
                try:
                    self.ultima = self._ultima_pelo_curl()
                except Exception as e3:
                    motivo = getattr(e2, "reason", None) or getattr(e1, "reason", None) or e3
                    self.erro = f"Sem conexão com o GitHub: {motivo}"
                    print("atualização:", repr(e1), repr(e2), repr(e3))
        self.verificado_em = time.time()
        self.estado = "parado" if not self.erro else "erro"

    def disponivel(self):
        return bool(self.ultima) and VERSAO != "dev" and _versao_tupla(self.ultima["versao"]) > _versao_tupla(VERSAO)

    def info(self):
        return {"atual": VERSAO, "nova": self.ultima and self.ultima["versao"], "disponivel": self.disponivel(),
                "estado": self.estado, "erro": self.erro}

    def atualizar(self):
        if not self.ultima:
            self.verificar()
        if not self.ultima:
            return False
        threading.Thread(target=self._aplicar, daemon=True).start()
        return True

    def _aplicar(self):
        try:
            self.estado = "baixando"
            tmp = tempfile.mkdtemp(prefix="hs3upd_")
            zip_path = os.path.join(tmp, "pacote.zip")
            url = self.ultima["asset_api"] if self.cfg.get("github_token") else self.ultima["asset_url"]
            try:
                with self._req(url, accept="application/octet-stream") as r, open(zip_path, "wb") as f:
                    shutil.copyfileobj(r, f)
            except Exception as e:
                print("download pelo Python falhou, tentando curl do Windows:", repr(e))
                _curl_windows(self.ultima["asset_url"], destino=zip_path, headers={"User-Agent": "HS3Companion"})
            pasta = os.path.join(tmp, "pacote")
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(pasta)

            # 1) mod: copia para a pasta do jogo (vale na próxima vez que o jogo abrir)
            mod_novo = os.path.join(pasta, "HS3Discovery")
            if os.path.isdir(mod_novo) and os.path.isdir(self.cfg["pasta_mod"]):
                for raiz, _, arquivos in os.walk(mod_novo):
                    destino = os.path.join(self.cfg["pasta_mod"], os.path.relpath(raiz, mod_novo))
                    os.makedirs(destino, exist_ok=True)
                    for a in arquivos:
                        shutil.copy2(os.path.join(raiz, a), os.path.join(destino, a))

            # 2) programa: o Windows deixa renomear um .exe em uso; troca e abre a versão nova
            if not getattr(sys, "frozen", False):
                self.estado = "parado"
                return
            exe_atual = sys.executable
            exe_novo = os.path.join(pasta, "HS3Companion.exe")
            for extra in ("LEIA-ME.txt",):
                if os.path.exists(os.path.join(pasta, extra)):
                    shutil.copy2(os.path.join(pasta, extra), os.path.join(BASE_DIR, extra))
            antigo = exe_atual + ".old"
            if os.path.exists(antigo):
                try:
                    os.remove(antigo)
                except OSError:
                    antigo = exe_atual + f".{int(time.time())}.old"
            os.replace(exe_atual, antigo)
            try:
                shutil.copy2(exe_novo, exe_atual)
            except Exception:
                os.replace(antigo, exe_atual)  # desfaz se não conseguiu copiar
                raise
            self.estado = "reiniciando"
            time.sleep(1.5)  # deixa o app receber o estado "reiniciando"
            iniciar_nova_instancia(exe_atual, ["--sem-navegador", "--aguardar-porta"])
            os._exit(0)
        except Exception as e:
            self.erro = f"Falha ao atualizar: {e}"
            self.estado = "erro"

    def loop(self):
        while True:
            self.verificar()
            time.sleep(1800)


# ------------------------------------------------------------------ núcleo
class Companion:
    def __init__(self):
        self.cfg = carregar_config()
        self.lock = threading.Lock()
        self.estado = {}
        self.estado_lido_em = 0
        self.dados = carregar_json(DADOS_PATH, {})
        d = self.dados
        self._completar_dados(d)
        # missões da versão antiga continuam valendo como ativas
        for m in d["missoes"]:
            if m.get("status") == "concluida" and (m.get("pago") or {}).get("creditos"):
                m["status"] = "paga"
            m.setdefault("aceita_em", m.get("criada", 0))
            m.setdefault("fala", "")
        self.gerando = False
        self._pois_cache = (None, 0, [])
        self._nevoa_cache = (None, 0, b"")
        self.salvar_pendente = False
        self.cache = extras.Cache()
        self.estava_em = None            # reserva em que o jogador estava no ciclo anterior
        self.teleporte = None            # (destino, hora) aguardando
        self.aviso_teleporte = None

    @staticmethod
    def _completar_dados(d):
        for chave, padrao in (("missoes", []), ("abates", []), ("marcados", {}), ("grupos_vistos", []),
                              ("eventos_offset", 0), ("pagamentos_dia", {}), ("recompensas", []),
                              ("chat", []), ("pino_app", None), ("posicoes", {}), ("ultima_pos", {}),
                              ("especies_vistas", {}), ("compras", []), ("reputacao_maxima", 0),
                              ("dia_jogo", 0), ("avistamentos", [])):
            d.setdefault(chave, padrao)

    # --- instalação e jogo novo
    def info_instalacao(self, pasta=None):
        w = instalador.win64_de(pasta) if pasta else instalador.win64_de(self.cfg.get("pasta_mod"))
        achado = None
        if not w:
            achado = w = instalador.achar_jogo()
        sit = instalador.situacao(w)
        sit["achado_sozinho"] = bool(achado)
        sit["atualizado"] = bool(sit.get("mod")) and instalador.arquivos_mod_iguais(w)
        sit["em_uso"] = bool(sit.get("pasta_mod")) and os.path.normcase(sit["pasta_mod"]) == os.path.normcase(self.cfg.get("pasta_mod") or "")
        sit["pronto"] = bool(sit.get("mod")) and sit["em_uso"]
        sit["jogo_aberto"] = self.conectado()
        return sit

    def acao_instalacao(self, corpo):
        acao = corpo.get("acao")
        if acao == "procurar":
            p = instalador.escolher_pasta()
            if not p:
                return {"ok": False, "erro": "Nenhuma pasta escolhida."}
            if not instalador.win64_de(p):
                return {"ok": False, "erro": f"Não achei o jogo em {p}. Escolha a pasta HS3 dentro de steamapps\\common."}
            return {"ok": True, "pasta": p, "situacao": self.info_instalacao(p)}
        if acao in ("instalar", "usar"):
            w = instalador.win64_de(corpo.get("pasta") or self.cfg.get("pasta_mod"))
            if not w:
                return {"ok": False, "erro": "Não achei o jogo nesta pasta (falta o HS3-Win64-Shipping.exe)."}
            if acao == "instalar":
                if self.conectado():
                    return {"ok": False, "erro": "Feche o jogo antes de instalar (o jogo trava os arquivos do UE4SS)."}
                try:
                    instalador.instalar(w)
                except Exception as e:
                    return {"ok": False, "erro": f"Não consegui instalar: {e}"}
            sit = instalador.situacao(w)
            if not sit.get("mod"):
                return {"ok": False, "erro": "O mod ainda não está instalado nesta pasta. Clique em Instalar."}
            self.cfg["pasta_mod"] = sit["pasta_mod"]
            salvar_json(CONFIG_PATH, self.cfg)
            self.cache = extras.Cache()
            return {"ok": True, "situacao": self.info_instalacao()}
        if acao == "zerar":
            return self.comecar_do_zero()
        return {"ok": False, "erro": "Ação inválida."}

    def comecar_do_zero(self):
        """Jogo novo: guarda o histórico do app numa cópia e recomeça (contratos, abates, patente, pinos)."""
        with self.lock:
            copia = os.path.join(BASE_DIR, f"dados_hs3_ate_{time.strftime('%Y-%m-%d_%H%M')}.json")
            salvar_json(copia, self.dados)
            offset = self.dados.get("eventos_offset", 0)
            self.dados.clear()
            self._completar_dados(self.dados)
            self.dados["eventos_offset"] = offset      # não reprocessa eventos antigos do mod
            for nome in ("licencas_todas.json",):
                try:
                    os.remove(os.path.join(BASE_DIR, nome))
                except OSError:
                    pass
            if hasattr(self, "_licencas_todas"):
                self._licencas_todas = {}
            self.novo_jogo_suspeito = False
            salvar_json(DADOS_PATH, self.dados)
        self.manter_ofertas()
        return {"ok": True, "copia": os.path.basename(copia)}

    def vigiar_jogo_novo(self):
        """Se a reputação total cair muito (save novo), avisa no app para recomeçar do zero."""
        total = sum((r.get("valor") or 0) for r in self.estado.get("reputacao") or [] if isinstance(r, dict))
        if not self.estado.get("reputacao"):
            return
        maxima = self.dados.get("reputacao_maxima", 0)
        if total > maxima:
            self.dados["reputacao_maxima"] = total
            self.novo_jogo_suspeito = False
        elif maxima >= 100 and total < maxima * 0.4:
            self.novo_jogo_suspeito = True

    # --- arquivos do mod
    def caminho(self, nome):
        return os.path.join(self.cfg["pasta_mod"] or os.path.join(BASE_DIR, "_mod_nao_instalado_"), nome)

    def nivel(self):
        return self.estado.get("mapa")

    def ler_estado(self):
        try:
            with open(self.caminho("state.json"), "r", encoding="utf-8") as f:
                self.estado = json.load(f)
            pj = self.estado.get("pino_jogo")
            if isinstance(pj, dict) and time.time() - getattr(self, "_pino_tirado_em", 0) < 10:
                pj = None   # acabou de pedir para tirar: o jogo leva 1–2 s para confirmar
            # sem pino o jogo deixa a posição zerada (versões antigas do mod mandavam assim mesmo)
            if not isinstance(pj, dict) or (abs(pj.get("x") or 0) < 1 and abs(pj.get("y") or 0) < 1):
                self.estado.pop("pino_jogo", None)
            self.estado_lido_em = os.path.getmtime(self.caminho("state.json"))
        except Exception:
            pass

    def conectado(self):
        return time.time() - self.estado_lido_em < 6

    def em_reserva(self):
        return self.conectado() and self.estado.get("ok") and self.estado.get("pos") is not None

    def ler_eventos(self):
        path = self.caminho("events.jsonl")
        if not os.path.exists(path):
            return []
        tam = os.path.getsize(path)
        off = self.dados["eventos_offset"]
        if tam < off:
            off = 0
        if tam == off:
            return []
        with open(path, "rb") as f:
            f.seek(off)
            bruto = f.read()
        ultimo = bruto.rfind(b"\n")
        if ultimo < 0:
            return []
        self.dados["eventos_offset"] = off + ultimo + 1
        eventos = []
        for linha in bruto[: ultimo + 1].splitlines():
            try:
                eventos.append(json.loads(linha.decode("utf-8")))
            except Exception:
                pass
        return eventos

    def ler_animais(self):
        try:
            with open(self.caminho("animais.json"), encoding="utf-8") as f:
                vivos = json.load(f)
        except Exception:
            return
        marcados = self.dados["marcados"]
        for a in vivos.get("animais", []):
            id_ = str(a.get("id"))
            if id_ in marcados:
                self.dados["posicoes"][id_] = {"x": a["x"], "y": a["y"], "z": a["z"], "yaw": a.get("yaw"),
                                               "ts": vivos.get("ts", time.time())}

    def zonas(self):
        """Zonas de necessidade da reserva atual (exportadas pelo mod com o estado de descoberta)."""
        nivel = self.nivel()
        if not nivel:
            return []
        lista = carregar_json(self.caminho(f"zonas_{nivel}.json"), []) or []
        if not isinstance(lista, list):
            lista = []
        # guarda a última lista boa: uma exportação vazia (mapa carregando) não apaga as zonas do app
        copia = os.path.join(os.path.dirname(DADOS_PATH), f"zonas_{nivel}.json")
        if lista:
            if not hasattr(self, "_zonas_salvas") or self._zonas_salvas.get(nivel) != len(lista):
                salvar_json(copia, lista)
                self._zonas_salvas = dict(getattr(self, "_zonas_salvas", {}), **{nivel: len(lista)})
        else:
            lista = carregar_json(copia, []) or []
        # o que você já viu em cada zona descoberta (avistamentos da mesma espécie dentro da zona)
        avs = {}
        for a in self.dados.get("avistamentos") or []:
            if a.get("reserva") == nivel and a.get("pos") and a.get("especie"):
                avs.setdefault(a["especie"], []).append(a)
        tipos_do_bando = {}
        for z in lista:
            if z.get("descoberta"):
                tipos_do_bando.setdefault((z.get("especie"), z.get("grupo")), set()).add(z.get("tipo"))
        for z in lista:
            z["especie_nome"] = nome_especie(z.get("especie")) or z.get("especie")
            bando = z.get("grupo")
            z["grupo"] = grupo_de(z.get("especie"))[0]
            if not z.get("descoberta"):
                continue
            z["bando"] = bando
            z["bando_tipos"] = sorted(tipos_do_bando.get((z.get("especie"), bando), set()))
            raio = (z.get("raio") or 3000) + 3000          # cm: a zona + 30 m de folga
            vistos = [a for a in avs.get(z.get("especie"), [])
                      if (a["pos"]["x"] - z["x"]) ** 2 + (a["pos"]["y"] - z["y"]) ** 2 <= raio * raio]
            ids = {}
            for a in vistos:
                ids[a.get("id")] = a
            z["vistos"] = len(ids)
            z["machos"] = sum(1 for a in ids.values() if a.get("sexo") == 0)
            z["femeas"] = sum(1 for a in ids.values() if a.get("sexo") == 1)
            z["horas"] = sorted({int(a["hora"]) for a in vistos if isinstance(a.get("hora"), (int, float))})
            z["ultimo_dia"] = max((a.get("dia") or 0 for a in vistos), default=None)
        return lista

    def pois(self):
        nivel = self.nivel()
        if not nivel:
            return []
        path = self.caminho(f"pois_{nivel}.json")
        try:
            mt = os.path.getmtime(path)
        except OSError:
            return []
        if self._pois_cache[0] != path or self._pois_cache[1] != mt:
            self._pois_cache = (path, mt, mapa.carregar_pois(path))
        vistos = set((self.dados.get("vistos_app") or {}).get(nivel) or [])
        if not vistos:
            return self._pois_cache[2]
        # estruturas por onde você já passou contam como descobertas (o jogo só exporta a cada 5 min)
        return [dict(p, descoberto=True) if not p.get("descoberto") and p.get("hash") in vistos else p
                for p in self._pois_cache[2]]

    TITULOS_PERTO_ANTIGOS = {"Tiro de perto", "Cara a cara", "Nariz com nariz", "Coragem no capim", "Encostado no bicho"}

    def revisar_contratos(self):
        """Uma vez por versão: distância só mínima, plurais certos e recontagem dos abates que a regra antiga
        de "sem ser percebido" (e o limite máximo de distância) deixaram de contar."""
        d = self.dados
        if d.get("versao_contratos", 0) >= 2 or not self.em_reserva() or not self.reserva():
            return
        for m in d["missoes"]:
            c = m.get("cond") or {}
            for alvo in (m, c):
                alvo.pop("dist_max", None)
            desc = m.get("descricao") or ""
            if c.get("dist_min") is not None:
                teto = 35 if m.get("grupo") in missoes.AVES or c.get("arma") == "espingarda" else 350
                if c["dist_min"] > teto:
                    desc = re.sub(r"a \d+–\d+ m", f"a {teto}–0 m", desc)
                    c["dist_min"] = m["dist_min"] = teto
            if c.get("dist_min") is not None and c["dist_min"] < 20:
                c.pop("dist_min", None)
                m.pop("dist_min", None)
                desc = re.sub(r",? a \d+–\d+ m", "", desc)
                if m.get("titulo") in self.TITULOS_PERTO_ANTIGOS:
                    m["titulo"] = "Caçada no capricho"
            else:
                desc = re.sub(r"a (\d+)–\d+ m", r"a \1 m ou mais", desc)
                if m.get("titulo") in self.TITULOS_PERTO_ANTIGOS:
                    m["titulo"] = "Distância segura"
            m["descricao"] = re.sub(r"(\w[\w-]*)\(s\)", lambda x: missoes.plural(x.group(1)), desc)
        r = self.reserva()
        # visitas: nomes de lugar em português; ofertas para "Estrutura de caça" (nome repetido) saem da mesa
        nomes = {p.get("hash"): p.get("nome") for p in self.pois()}
        d["missoes"] = [m for m in d["missoes"] if not (m["status"] == "oferta" and m.get("reserva") == r and any(
            (l or {}).get("nome") == "Estrutura de caça" for l in (m.get("locais") or [])))]
        for m in d["missoes"]:
            if m.get("reserva") == r and m.get("locais") and m["status"] in ("oferta", "ativa"):
                for l in m["locais"]:
                    if nomes.get(l.get("hash")):
                        l["nome"] = nomes[l["hash"]]
                if isinstance(m.get("local"), dict) and nomes.get(m["local"].get("hash")):
                    m["local"]["nome"] = nomes[m["local"]["hash"]]
                lista = ", ".join(l["nome"] for l in m["locais"])
                m["descricao"] = f"Vá até: {lista}." if len(m["locais"]) == 1 else f"Passe por estes {len(m['locais'])} lugares: {lista}."
        ativas = [m for m in d["missoes"] if m["status"] == "ativa" and m.get("reserva") == r]
        if ativas:
            desde = min(m.get("aceita_em", m["criada"]) for m in ativas) - 2
            for ab in list(d["abates"]):
                if (ab.get("ts") or 0) >= desde and extras.nome_mapa(ab.get("reserva") or "") == r:
                    avaliar_missoes(d, dict(ab, tipo="abate_confirmado"), r)
        d["versao_contratos"] = 2
        self.salvar_pendente = True
        print("contratos revisados (distância mínima, plurais, recontagem)")

    def marcar_estruturas_perto(self):
        """Marca como descoberta a estrutura de caça a menos de 35 m de você (sem perguntar nada ao jogo)."""
        if not self.em_reserva():
            return
        nivel, pos = self.nivel(), self.estado.get("pos") or {}
        if not nivel or pos.get("x") is None:
            return
        vistos = self.dados.setdefault("vistos_app", {}).setdefault(nivel, [])
        for p in self.pois():
            if p.get("categoria") == "estrutura" and not p.get("descoberto") and p.get("hash") is not None \
                    and (p["x"] - pos["x"]) ** 2 + (p["y"] - pos["y"]) ** 2 < 3500 ** 2:
                vistos.append(p["hash"])
                self.salvar_pendente = True

    def nevoa_png(self, nivel):
        path = self.caminho(f"nevoa_{nivel}.bin")
        mt = os.path.getmtime(path)
        if self._nevoa_cache[0] != path or self._nevoa_cache[1] != mt:
            self._nevoa_cache = (path, mt, mapa.nevoa_png(path))
        return self._nevoa_cache[2]

    def info_mapa(self):
        nivel = self.nivel()
        info = carregar_json(self.caminho(f"mapa_{nivel}.json"), {}) if nivel else {}
        info.setdefault("tamanho_mundo", 1224000)
        info["imagem"] = bool(nivel) and os.path.exists(self.caminho(f"mapa_{nivel}.png"))
        info["nevoa"] = bool(nivel) and os.path.exists(self.caminho(f"nevoa_{nivel}.bin"))
        try:
            info["nevoa_versao"] = int(os.path.getmtime(self.caminho(f"nevoa_{nivel}.bin")))
        except OSError:
            info["nevoa_versao"] = 0
        info["nivel"] = nivel
        return info

    def enviar_comando(self, linhas):
        """Escreve comandos para o mod. Com o jogo fechado não escreve nada (o mod descarta comandos antigos ao abrir)."""
        if not self.conectado():
            return False
        with open(self.caminho("cmd.txt"), "a", encoding="utf-8") as f:
            for l in linhas:
                f.write(l + "\n")
        return True

    # --- processamento de eventos
    def registrar_grupo(self, chave):
        if chave and chave not in self.dados["grupos_vistos"]:
            self.dados["grupos_vistos"].append(chave)

    def processar(self, ev):
        d = self.dados
        tipo = ev.get("tipo")
        if tipo == "marcado":
            # peso: só uma faixa estimada (~15%), sempre a mesma para o mesmo animal; o peso exato não fica guardado
            real = ev.pop("peso_kg", None)
            if isinstance(real, (int, float)) and real > 0:
                r = random.Random(f"peso{ev.get('id')}")
                lo = real * (1 - r.uniform(0.02, 0.13))
                hi = lo * 1.15
                casas = 1 if real < 5 else 0
                ev["peso_faixa"] = [round(lo, casas), round(hi, casas)]
            chave, nome = grupo_de(ev.get("especie"))
            ev.update({"grupo": chave, "grupo_nome": nome, "especie_nome": nome_especie(ev.get("especie")),
                       "sexo_nome": SEXO.get(ev.get("sexo"), "?"), "visto_em": time.time(), "reserva": self.nivel()})
            novo = str(ev.get("id")) not in d["marcados"]
            if novo and ev.get("especie"):
                d["especies_vistas"][ev["especie"]] = d["especies_vistas"].get(ev["especie"], 0) + 1
            d["marcados"][str(ev.get("id"))] = ev
            self.ultimo_marcado = {"id": str(ev.get("id")), "ts": time.time()}
            # histórico de avistamentos (base do censo e do manejo); o mesmo animal só entra de novo após 10 min
            av = d["avistamentos"]
            ult = next((x for x in reversed(av[-200:]) if x.get("id") == ev.get("id")), None)
            if not ult or time.time() - ult.get("ts", 0) > 600:
                av.append({k: ev.get(k) for k in ("id", "especie", "sexo", "potencial", "genetica", "idade_dias", "lendario", "pos")}
                          | {"ts": time.time(), "dia": d.get("dia_jogo", 0), "hora": (self.estado or {}).get("hora"), "reserva": self.nivel()})
                del av[:-4000]
            self.registrar_grupo(chave)
            # conta para "marque N ... diferentes" mesmo se o animal já tinha sido marcado antes (o contrato não repete o mesmo id)
            return avaliar_missoes(d, {"tipo": "marcado", "id": ev.get("id"), "grupo": chave, "especie": ev.get("especie"),
                                       "ts": time.time()}, self.reserva())
        elif tipo in ("abate", "abate_final"):
            id_ = str(ev.get("id"))
            if any(str(a.get("id")) == id_ for a in d["abates"]):
                return []
            ab = dict(ev)
            # arma com ou sem luneta no tiro (para o contrato "Caça tradicional"): o mod lê do tiro;
            # sem isso, olha os acessórios da arma na mochila (o tiro traz ID_X; a lista usa DA_X_StoreItem/StoreAsset)
            if ab.get("tem_luneta") is None:
                ab["tem_luneta"] = self.arma_tem_luneta(ab.get("arma"))
            marc = d["marcados"].get(id_)
            especie = (marc or {}).get("especie") or ab.get("especie_jogo")
            chave, nome = grupo_de(especie or ab.get("classe"))
            ab.update({"grupo": chave, "grupo_nome": nome, "especie": especie,
                       "especie_nome": nome_especie(especie) or nome, "sexo_nome": (marc or {}).get("sexo_nome") or SEXO.get(ab.get("sexo")),
                       "dia_jogo": d.get("dia_jogo", 0), "hora_jogo": (self.estado or {}).get("hora"),
                       "acao_nome": ACOES.get(ab.get("acao"), "Recolhido"), "ts": time.time(), "reserva": self.nivel()})
            if chave in missoes.PREDADORES and isinstance(ab.get("pos"), dict):
                try:
                    zs = [z for z in self.zonas() if z.get("descoberta") and z.get("grupo") not in missoes.PREDADORES]
                    dz = min((distancia_m(ab["pos"], {"x": z["x"], "y": z["y"], "z": 0}) or 1e9 for z in zs), default=None)
                    ab["perto_presa_m"] = round(dz) if dz is not None and dz < 1e8 else None
                except Exception:
                    pass
            if isinstance(ab.get("orgaos"), list):
                ab["orgaos_nome"] = list(dict.fromkeys(missoes.nome_orgao(o) for o in ab["orgaos"]))
                ab["vital"] = missoes.acertou_vital(ab["orgaos"])
            self.registrar_grupo(chave)
            d["abates"].append(ab)
            d["marcados"].pop(id_, None)
            d["posicoes"].pop(id_, None)
            if id_ in d.get("carcacas", {}):
                d["carcacas"][id_]["fim"] = time.time()
                ab["natural"] = True
                return avaliar_missoes(d, {"tipo": "carcaca_recolhida", "id": id_, "ts": time.time()}, self.reserva())
            return avaliar_missoes(d, dict(ab, tipo="abate_confirmado"), self.reserva())
        elif tipo == "empalhado":
            # Sala de troféus: animal novo num estande. O print sai 2 s depois (a câmera do estande mostra o animal)
            reg = {"ts": time.time(), "total": ev.get("total"), "por_nivel": ev.get("por_nivel"), "dia": d.get("dia_jogo")}
            d.setdefault("trofeus", []).append(reg)
            threading.Timer(2.0, self.print_trofeu, args=(reg,)).start()
            return []
        elif tipo == "foto_trofeu":
            # F9 no jogo: foto escolhida por você. Vai para o troféu empalhado nos últimos 15 min (no lugar da automática);
            # sem troféu recente, vira uma foto nova na sala
            lista = d.setdefault("trofeus", [])
            alvo = lista[-1] if lista and time.time() - lista[-1].get("ts", 0) < 900 else None
            if not alvo:
                alvo = {"ts": time.time(), "total": None, "dia": d.get("dia_jogo"), "so_manual": True}
                lista.append(alvo)
            # foto limpa: tira os contratos do app da tela do jogo, espera o mod sincronizar (~2 s) e só então fotografa
            self.hud_oculto_ate = time.time() + 8
            self.escrever_hud()
            threading.Timer(2.8, self.print_trofeu, args=(alvo, True)).start()
            return []
        elif tipo == "compra":
            d["compras"] = (d["compras"] + [ev])[-50:]
            for lista in list((d.get("barracas") or {}).values()):
                for b in lista:
                    if b.get("pendente") and b["pendente"] == ev.get("ref"):
                        b.pop("pendente")
                        if not ev.get("ok"):
                            b["falhou"] = True
        elif tipo == "recompensa":
            d["recompensas"] = (d["recompensas"] + [ev])[-100:]
            for m in d["missoes"]:
                if m["id"] == ev.get("ref"):
                    m.setdefault("pago", {})[ev.get("recurso")] = bool(ev.get("ok"))
                    # o dinheiro é a recompensa principal; a reputação é registrada mas não trava o contrato
                    if m["pago"].get("creditos") and "reputacao" in m["pago"]:
                        m["status"], m["pago_em"] = "paga", time.time()
        return []

    def pagar_pendentes(self):
        if not self.em_reserva():
            return
        hoje = date.today().isoformat()
        dia = self.dados["pagamentos_dia"]
        agora = time.time()
        for m in self.dados["missoes"]:
            if m["status"] != "concluida":
                continue
            if m.get("enviado"):
                # sem confirmação do jogo (ex.: o jogo fechou antes de ler o comando): manda de novo
                pago = m.get("pago") or {}
                if agora - m["enviado"] > 60 and not pago.get("creditos"):
                    if m.get("tentativas", 1) >= 3:
                        m["status"], m["pago_em"], m["sem_confirmacao"] = "paga", agora, True
                        continue
                    m["tentativas"] = m.get("tentativas", 1) + 1
                    linhas = [f"add_credits {m.get('creditos_pagos', 0)} {m['id']}"] if m.get("creditos_pagos") else []
                    if "reputacao" not in pago:
                        linhas.append(f"add_rep {m['reputacao']} {m['id']} {missoes.agente_de(m)}")
                    if linhas and self.enviar_comando(linhas):
                        m["enviado"] = agora
                continue
            pago_hoje = dia.get(hoje, 0)
            cred = min(m["creditos"], max(0, self.cfg["limite_diario_creditos"] - pago_hoje))
            linhas = [f"add_credits {cred} {m['id']}"] if cred > 0 else []
            if cred <= 0:
                m.setdefault("pago", {})["creditos"] = True
            linhas.append(f"add_rep {m['reputacao']} {m['id']} {missoes.agente_de(m)}")
            self.enviar_comando(linhas)
            dia[hoje] = pago_hoje + cred
            m["enviado"] = time.time()
            m["creditos_pagos"] = cred
            if self.dados.get("pino_app") and self.dados["pino_app"].get("missao") == m["id"]:
                self.remover_pino()

    # --- missões
    def reserva(self):
        """Nome da reserva atual (Texas, Colorado...) ou None no rancho/menu."""
        n = self.nivel()
        if not n:
            return None
        r = extras.nome_mapa(n)
        return None if r == "Rancho" else r

    def por_status(self, *status, todas=False):
        """Contratos com esse status na reserva atual (todas=True: de todas as reservas)."""
        r = self.reserva()
        return [m for m in self.dados["missoes"] if m["status"] in status and (todas or (r and m.get("reserva") == r))]

    def separar_por_reserva(self):
        """Contratos antigos (sem reserva): ofertas são refeitas; ativos ficam com a reserva atual."""
        r = self.reserva()
        if not r or not self.em_reserva():
            return
        antes = len(self.dados["missoes"])
        self.dados["missoes"] = [m for m in self.dados["missoes"] if not (m["status"] == "oferta" and not m.get("reserva"))]
        mudou = len(self.dados["missoes"]) != antes
        sem = [m for m in self.dados["missoes"] if not m.get("reserva")]
        if not sem:
            return
        # em que reservas vive cada grupo de animal (para mandar contratos antigos para a reserva certa)
        dados = self.cache.json(self.caminho("jogo_dados.json"), None) or {}
        onde = {}
        for a in dados.get("animais", []):
            g = grupo_de(a.get("tag"))[0]
            for mp in a.get("mapas", []):
                nome = extras.nome_mapa(mp)
                if nome not in ("Rancho", mp):
                    onde.setdefault(g, set()).add(nome)
        visitadas = {extras.nome_mapa(x.get("mapa")) for x in self.estado.get("reputacao") or [] if isinstance(x, dict)}
        visitadas |= {extras.nome_mapa(k) for k in (self.estado.get("pontos_campo") or {})}
        for m in sem:
            lugares = onde.get(m.get("grupo") or "", set())
            if len(lugares) > 1 and r not in lugares and len(lugares & visitadas) == 1:
                lugares = lugares & visitadas
            m["reserva"] = r if (not lugares or r in lugares or len(lugares) > 1) else next(iter(lugares))
            mudou = True
        if mudou:
            self.salvar_pendente = True

    def outras_reservas(self):
        r = self.reserva()
        cont = {}
        for m in self.dados["missoes"]:
            if m["status"] in ("ativa", "oferta") and m.get("reserva") and m["reserva"] != r:
                c = cont.setdefault(m["reserva"], {"reserva": m["reserva"], "ativas": 0, "ofertas": 0})
                c["ativas" if m["status"] == "ativa" else "ofertas"] += 1
        return sorted(cont.values(), key=lambda c: c["reserva"])

    def manter_ofertas(self):
        if self.gerando or not self.reserva() or not self.em_reserva():
            return
        faltam = self.cfg["ofertas"] - len(self.por_status("oferta"))
        if faltam <= 0:
            return
        self.gerando = True
        threading.Thread(target=self._gerar_ofertas, args=(faltam, self.reserva()), daemon=True).start()

    def info_gerador(self):
        """Espécies que vivem na reserva atual e tipos de arma que você tem (para o gerador de contratos)."""
        dados = self.cache.json(self.caminho("jogo_dados.json"), None) or {}
        for a in dados.get("animais", []):
            t, titulo = a.get("tag"), (a.get("titulo") or "").strip()
            if t and titulo and not t.endswith(".Hub"):
                TITULOS_JOGO[t] = titulo
        nivel = (self.nivel() or "").lower().split("_")[0]
        grupos = []
        for a in dados.get("animais", []):
            if nivel and any(nivel in (mp or "").lower() for mp in a.get("mapas", [])):
                g = grupo_de(a.get("tag"))[0]
                if g != "outro" and g not in grupos:
                    grupos.append(g)
        for i in dados.get("itens", []):
            if (i.get("tipo") or "").startswith("Inventory.Weapon"):
                ARMA_TIPOS[(i.get("item") or "").split(":")[-1]] = missoes._arma_tipo(i["tipo"])
        # só o que dá para caçar com as armas e a munição que você tem (jogo novo = poucas opções)
        cap = extras.capacidade(dados, self.tabela_calibres(), self.equipamento(), self.nivel(), grupo_de, missoes._arma_tipo)
        grupos = [g for g in grupos if g in cap["grupos"]]
        # nível de progresso = maior nível entre os agentes desta reserva (200 pontos por nível)
        reps = [int(r.get("valor") or 0) for r in (self.estado or {}).get("reputacao") or []
                if self.nivel() and self.nivel() in (r.get("mapa") or "")]
        cap["nivel"] = min(5, max(reps, default=0) // 200)
        # avistamentos desta reserva (para o "troféu fugitivo")
        cap["avistamentos"] = [dict(a, especie_nome=nome_especie(a.get("especie")))
                               for a in (self.dados.get("avistamentos") or [])[-600:]
                               if a.get("pos") and a.get("reserva") == self.nivel()]
        # zonas ainda não descobertas por grupo (contrato de reconhecimento) e se há predador para "limpeza de corredor"
        try:
            zs = self.zonas()
            falt = {}
            for z in zs:
                if not z.get("descoberta"):
                    falt[z.get("grupo")] = falt.get(z.get("grupo"), 0) + 1
            cap["zonas_faltando"] = falt
            cap["corredor"] = any(g in missoes.PREDADORES for g in grupos) and any(z.get("descoberta") for z in zs)
            cap["orgaos"] = any(isinstance(a.get("orgaos"), list) for a in (self.dados.get("abates") or [])[-30:])
        except Exception:
            pass
        return grupos, cap

    def _gerar_ofertas(self, n, reserva):
        try:
            grupos, cap = self.info_gerador()
            with self.lock:
                if self.reserva() != reserva:
                    return  # trocou de reserva no meio: gera de novo na próxima volta
                novas = missoes.gerar(self.dados, self.pois(), nome_grupo, grupos, cap, n)
                espera = self.dados.get("espera_agente") or {}
                dia = self.dados.get("dia_jogo", 0)
                novas = [m for m in novas if espera.get(missoes.agente_de(m), -1) <= dia]
                # Bolsa de carne (painel Manejo): contrato do Açougueiro paga mais pela espécie que está em falta
                try:
                    dem = {}
                    for l in manejo.painel(self.dados, self.nivel(), nome_especie, grupo_de)["especies"]:
                        dem[l["grupo"]] = max(dem.get(l["grupo"], 0), l["demanda"])
                except Exception:
                    dem = {}
                for m in novas:
                    m["reserva"] = reserva
                    f = dem.get(m.get("grupo"))
                    if f and missoes.agente_de(m) == "NPC.Vendor.Butcher" and m.get("creditos") and abs(f - 1) >= 0.05:
                        m["creditos"] = int(round(m["creditos"] * f / 10) * 10)
                        m["demanda"] = f
                self.dados["missoes"].extend(novas[:n])
                self.salvar_pendente = True
        except Exception as e:
            print("erro ao gerar contratos:", e)
        finally:
            self.gerando = False

    def acao_missao(self, acao, id_):
        with self.lock:
            m = next((x for x in self.dados["missoes"] if x["id"] == id_), None)
            if not m:
                return {"ok": False, "erro": "missão não encontrada"}
            if m.get("reserva") and m["reserva"] != self.reserva() and acao in ("aceitar", "focar"):
                return {"ok": False, "erro": f"Este contrato é da reserva {m['reserva']}. Vá até lá para usar."}
            if acao == "aceitar" and m["status"] == "oferta":
                if len(self.por_status("ativa")) >= self.cfg["missoes_ativas"]:
                    return {"ok": False, "erro": f"Você já tem {self.cfg['missoes_ativas']} contratos ativos. Abandone um antes."}
                m["status"], m["aceita_em"] = "ativa", time.time()
                if m.get("local"):
                    self._pino(m["local"], m["titulo"], m["id"])
            elif acao == "recusar" and m["status"] == "oferta":
                m["status"] = "recusada"
            elif acao == "abandonar" and m["status"] == "ativa":
                # rescisão: perde metade da reputação do contrato no agente, multa de 10% do valor
                # e o Earl não oferece contratos desse agente até o próximo dia do jogo
                agente = missoes.agente_de(m)
                perda = max(3, int(m.get("reputacao") or 0) // 2)
                multa = max(20, int(round((m.get("creditos") or 0) * 0.10)))
                cred = (self.estado.get("moedas") or {}).get("Currency.Credits") or 0
                linhas = [f"add_rep -{perda} ab{m['id']} {agente}"]
                if cred >= multa:
                    linhas.append(f"cobrar {multa} mu{m['id']}")
                self.enviar_comando(linhas)
                m["status"] = "abandonada"
                m["penalidade"] = {"reputacao": perda, "multa": multa if cred >= multa else 0, "agente": agente}
                self.dados.setdefault("espera_agente", {})[agente] = self.dados.get("dia_jogo", 0) + 1
                if (self.dados.get("pino_app") or {}).get("missao") == id_:
                    self.remover_pino()
            elif acao == "focar" and m["status"] == "ativa":
                if not m.get("local"):
                    return {"ok": False, "erro": "Esta missão não tem local no mapa."}
                self._pino(m["local"], m["titulo"], m["id"])
            else:
                return {"ok": False, "erro": "ação inválida"}
            self.salvar_pendente = True
        return {"ok": True}

    # --- pinos
    def _pino(self, pos, rotulo="Pino", missao=None):
        self._pino_tirado_em = 0
        self.dados["pino_app"] = {"x": pos["x"], "y": pos["y"], "z": pos.get("z", 0), "rotulo": rotulo,
                                  "missao": missao, "ts": time.time()}
        self.enviar_comando([f"pin {pos['x']:.0f} {pos['y']:.0f} {pos.get('z', 0):.0f}"])
        self.salvar_pendente = True

    def pino(self, x, y, rotulo="Meu pino"):
        with self.lock:
            z = (self.estado.get("pos") or {}).get("z", 0)
            self._pino({"x": float(x), "y": float(y), "z": z}, rotulo)
        return {"ok": True}

    def vigiar_pino(self):
        """Se o pino sumiu do jogo (tirado lá dentro), tira também do app."""
        if not self.em_reserva():
            return
        tem = bool(self.estado.get("pino_jogo"))
        pa = self.dados.get("pino_app")
        if tem:
            self._pino_visto = True
        elif pa and getattr(self, "_pino_visto", False) and time.time() - (pa.get("ts") or 0) > 8:
            self.dados["pino_app"] = None
            self.salvar_pendente = True
            self._pino_visto = False

    def passar_tempo(self, horas=None, ate=None):
        if not self.em_reserva() or not self.reserva():
            return {"ok": False, "erro": "Entre numa reserva no jogo primeiro."}
        agora = self.estado.get("hora")
        if ate is not None:
            if agora is None:
                return {"ok": False, "erro": "Ainda não li o relógio do jogo. Tente de novo em alguns segundos."}
            horas = (float(ate) - float(agora)) % 24
        try:
            horas = float(horas)
        except (TypeError, ValueError):
            return {"ok": False, "erro": "Quantidade de horas inválida."}
        if horas < 0.25:
            return {"ok": False, "erro": "Já está nesse horário."}
        horas = min(horas, 23.5)
        self.enviar_comando([f"dormir {horas:.2f}"])
        return {"ok": True, "horas": round(horas, 2)}

    def remover_pino(self):
        self._pino_visto = False
        self._pino_tirado_em = time.time()   # até o jogo confirmar, o app já mostra sem pino
        self.dados["pino_app"] = None
        self.enviar_comando(["unpin"])
        self.salvar_pendente = True
        return {"ok": True}

    # --- dicas do Earl (respostas prontas, sem IA)
    def conversar(self, texto):
        texto = (texto or "").strip()[:300]
        if not texto:
            return {"ok": False}
        resposta = missoes.dica(texto)
        with self.lock:
            agora = time.time()
            self.dados["chat"] = (self.dados["chat"] + [{"role": "user", "content": texto, "ts": agora},
                                                        {"role": "assistant", "content": resposta, "ts": agora}])[-40:]
            self.salvar_pendente = True
        return {"ok": True, "resposta": resposta}

    # --- voltar ao último local
    def vigiar_mortos(self):
        """Animal morto de causa natural (o jogo marca no mapa e ninguém atirou nele) vira contrato de recolher a carcaça."""
        if not self.em_reserva() or time.time() - getattr(self, "_mortos_visto", 0) < 5:
            return
        self._mortos_visto = time.time()
        arq = self.cache.json(self.caminho("mortos.json"), None)
        if not isinstance(arq, dict) or not isinstance(arq.get("mortos"), list):
            return
        d = self.dados
        carc = d.setdefault("carcacas", {})
        atuais = {str(m.get("id")): m for m in arq["mortos"] if isinstance(m, dict)}
        pos = (self.estado or {}).get("pos")
        reserva = self.reserva()
        for id_, m in atuais.items():
            if m.get("tiro") or id_ in carc:
                continue
            r = random.Random(f"carcaca{id_}")
            ang, dist = r.uniform(0, 6.283), r.uniform(5, 35) * 100     # centro da área a até 35 m do animal
            centro = (m["x"] + dist * math.cos(ang), m["y"] + dist * math.sin(ang), m.get("z", 0))
            missao = missoes.carcaca(id_, nome_especie(m.get("especie")) if m.get("especie") else None, centro)
            missao["reserva"] = reserva
            d["missoes"].append(missao)
            carc[id_] = {"x": m["x"], "y": m["y"], "missao": missao["id"], "ts": time.time()}
            self.carcaca_nova = {"id": missao["id"], "ts": time.time(), "especie": missao.get("titulo")}
            self.salvar_pendente = True
        # sumiu da lista com você perto = recolhida
        for id_, c in list(carc.items()):
            if id_ in atuais or c.get("fim"):
                continue
            if pos and distancia_m(pos, {"x": c["x"], "y": c["y"], "z": pos.get("z", 0)}) is not None \
                    and distancia_m(pos, {"x": c["x"], "y": c["y"], "z": pos.get("z", 0)}) < 60:
                c["fim"] = time.time()
                avaliar_missoes(d, {"tipo": "carcaca_recolhida", "id": id_, "ts": time.time()}, reserva)
                self.salvar_pendente = True

    def arma_tem_luneta(self, arma):
        try:
            mun = (self.cache.json(self.caminho("armas.json"), None) or {}).get("municao") or {}
            nome = (arma or "").split("ID_", 1)[-1]
            anexos = mun.get(arma) or mun.get(f"DA_{nome}_StoreItem") or mun.get(f"DA_{nome}_StoreAsset")
            if anexos is None:
                return None
            tipos = {c.get("id"): c.get("tipo") or "" for c in self.catalogo()}
            return any("Scope" in tipos.get(x, "") or "Scope" in x for x in anexos)
        except Exception:
            return None

    def recontar_marcacoes(self):
        """Uma vez ao abrir: marcações feitas depois de aceitar um contrato de censo e que não contaram (erro até a v0.1.58)."""
        if getattr(self, "_recontou", False) or not self.em_reserva():
            return
        self._recontou = True
        d = self.dados
        # contratos de "linhagem" por nível (v0.1.60) saíram: genética nova é só dos agentes do jogo
        d["missoes"] = [m for m in d["missoes"] if not (m.get("genetica_nivel") and m["status"] in ("oferta", "ativa"))]
        for m in d["missoes"]:
            if m["status"] == "ativa" and (m.get("cond") or {}).get("sem_luneta"):
                for ab in d["abates"]:
                    if ab.get("ts", 0) >= m.get("aceita_em", m["criada"]) and ab.get("tem_luneta") is None:
                        ab["tem_luneta"] = self.arma_tem_luneta(ab.get("arma"))
                        avaliar_missoes(d, dict(ab, tipo="abate_confirmado"), self.reserva())
        for m in d["missoes"]:
            if m["status"] != "ativa" or not (m.get("cond") or {}).get("marcar"):
                continue
            for a in d.get("avistamentos") or []:
                if a.get("ts", 0) >= m.get("aceita_em", m["criada"]) and a.get("reserva") == self.nivel():
                    chave = grupo_de(a.get("especie"))[0]
                    avaliar_missoes(d, {"tipo": "marcado", "id": a.get("id"), "grupo": chave, "especie": a.get("especie"),
                                        "ts": a["ts"]}, self.reserva())
        self.salvar_pendente = True

    def contar_dias(self):
        """Dia do jogo contado pelo app: a hora volta de ~24 para ~0 (noite passando ou "dormir")."""
        h = (self.estado or {}).get("hora")
        if not isinstance(h, (int, float)) or not self.em_reserva():
            return
        antes = getattr(self, "_hora_antes", None)
        self._hora_antes = h
        if antes is not None and h < antes - 6:
            self.dados["dia_jogo"] = self.dados.get("dia_jogo", 0) + 1
            self.registrar_boletim()
            salvar_json(DADOS_PATH, self.dados)

    def registrar_boletim(self):
        """Boletim da manhã: o resumo do dia que acabou de passar nesta reserva."""
        try:
            nv = self.nivel()
            p = manejo.painel(dict(self.dados, dia_jogo=self.dados.get("dia_jogo", 1) - 1), nv, nome_especie, grupo_de)
            b = dict(p["hoje"], reserva=nv, ts=time.time())
            if not b["abates"] and not b["avistados"]:
                return
            self.dados.setdefault("boletins", []).append(b)
            del self.dados["boletins"][:-60]
            self.boletim_novo = {"ts": b["ts"], "dia": b["dia"]}
        except Exception as e:
            print("boletim:", e)

    def mapa_manejo(self):
        """Pontos para a camada Manejo do mapa: avistamentos (calor por sexo) e abates desta reserva, últimos 7 dias."""
        with self.lock:
            nv = self.nivel()
            dia = self.dados.get("dia_jogo", 0)
            ini = dia - manejo.JANELA_DIAS + 1

            def recente(a, chave):
                d = a.get(chave)
                return d is None or d >= ini
            av = [{"x": a["pos"]["x"], "y": a["pos"]["y"], "sexo": a.get("sexo"), "especie": a.get("especie"),
                   "grupo": grupo_de(a.get("especie"))[0], "nome": nome_especie(a.get("especie")), "dia": a.get("dia")}
                  for a in (self.dados.get("avistamentos") or [])
                  if nv and a.get("reserva") == nv and a.get("pos") and a.get("especie") and recente(a, "dia")][-1500:]
            ab = [{"x": a["pos"]["x"], "y": a["pos"]["y"], "especie": a.get("especie"), "nome": a.get("especie_nome") or nome_especie(a.get("especie")),
                   "sexo": a.get("sexo_nome"), "dia": a.get("dia_jogo")}
                  for a in (self.dados.get("abates") or [])
                  if nv and a.get("reserva") == nv and isinstance(a.get("pos"), dict) and a["pos"].get("x") is not None
                  and a.get("especie") and recente(a, "dia_jogo")][-500:]
            return {"avistamentos": av, "abates": ab, "dia": dia}

    def dados_manejo(self):
        with self.lock:
            nv = self.nivel() if self.em_reserva() else None
            if not nv:
                nv = next((a.get("reserva") for a in reversed(self.dados.get("avistamentos") or []) if a.get("reserva")), None)
            return manejo.painel(self.dados, nv, nome_especie, grupo_de)

    def vigiar_queda(self, x, y, z):
        if z is not None:
            self._vigia = {"x": x, "y": y, "z": z, "ate": time.time() + 40, "n": 0, "ultimo": time.time()}

    def cuidar_posicao(self):
        nivel = self.nivel() if self.em_reserva() else None
        agora = time.time()
        if nivel and nivel != self.estava_em and "Hub" not in nivel:
            destino = self.dados["ultima_pos"].get(nivel)
            if destino and not destino.get("solo"):
                destino = None   # posição gravada antes da v0.1.39 (podia ser no meio de uma queda)
            self.anterior = destino if destino and (distancia_m(self.estado["pos"], destino) or 0) > 150 else None
            if self.cfg.get("voltar_ao_ultimo_local") and destino and (distancia_m(self.estado["pos"], destino) or 0) > 150:
                self.teleporte = (destino, agora + 12)     # espera o mapa carregar um pouco
                self.aviso_teleporte = "Voltando ao último local em instantes…"
        self.estava_em = nivel
        if self.teleporte:
            destino, hora = self.teleporte
            if agora >= hora:
                self.enviar_comando([f"teleport {destino['x']:.0f} {destino['y']:.0f} {destino['z']:.0f}"])
                self.vigiar_queda(destino["x"], destino["y"], destino["z"])
                self.teleporte = None
                self.aviso_teleporte = None
                self.pausa_pos_ate = agora + 45
            return
        # depois de uma viagem: se o chão ainda não tinha carregado e o caçador está caindo, manda de novo para o ponto
        v = getattr(self, "_vigia", None)
        if v and nivel:
            p = self.estado.get("pos") or {}
            if agora > v["ate"]:
                self._vigia = None
            elif p.get("z") is not None and p["z"] < v["z"] - 1500 and agora - v["ultimo"] > 4:
                if v["n"] >= 4:
                    self._vigia = None
                else:
                    v["n"] += 1
                    v["ultimo"] = agora
                    self.enviar_comando([f"teleport {v['x']:.0f} {v['y']:.0f} {v['z']:.0f}"])
                    print("viagem: caindo abaixo do chão, repetindo o teleporte", v["n"])
        if nivel and "Hub" not in nivel and agora >= getattr(self, "pausa_pos_ate", 0):
            p = self.estado["pos"]
            # só guarda com o caçador no chão: altura quase igual nas últimas leituras (nada de queda ou pulo)
            alturas = (getattr(self, "_alturas", []) + [p["z"]])[-4:]
            self._alturas = alturas
            no_chao = self.estado.get("chao")
            if len(alturas) == 4 and max(alturas) - min(alturas) < 40 and no_chao is not False:
                self.dados["ultima_pos"][nivel] = {"x": p["x"], "y": p["y"], "z": p["z"], "ts": agora, "chao": True,
                                                   "solo": no_chao is True}

    def voltar_agora(self):
        with self.lock:
            destino = getattr(self, "anterior", None)
            if not destino:
                return {"ok": False, "erro": "Nenhum local anterior salvo para esta reserva."}
            self.enviar_comando([f"teleport {destino['x']:.0f} {destino['y']:.0f} {destino['z']:.0f}"])
        return {"ok": True}

    def configurar(self, chave, valor):
        if chave in ("voltar_ao_ultimo_local", "contratos_no_jogo"):
            self.cfg[chave] = bool(valor)
            salvar_json(CONFIG_PATH, self.cfg)
            return {"ok": True}
        return {"ok": False}

    # --- armário, loja, enciclopédia
    def catalogo(self):
        return self.cache.json(self.caminho("catalogo_v2.json"), [])

    def equipamento(self):
        return self.cache.json(self.caminho("equipamento.json"), {})

    def tabela_calibres(self):
        """Tabela espécie × calibre do jogo. Cada reserva exporta só o que carregou, então o app junta tudo
        o que já viu (calibres_todos.json) para o Diário mostrar a balística de todas as espécies."""
        atual = self.cache.json(self.caminho("calibres.json"), []) or []
        if not hasattr(self, "_calibres_todos"):
            self._calibres_todos = {l.get("animal"): l for l in carregar_json(os.path.join(BASE_DIR, "calibres_todos.json"), [])
                                    if isinstance(l, dict) and l.get("animal")}
        mudou = False
        for l in atual:
            if isinstance(l, dict) and l.get("animal") and self._calibres_todos.get(l["animal"]) != l:
                self._calibres_todos[l["animal"]] = l
                mudou = True
        if mudou:
            salvar_json(os.path.join(BASE_DIR, "calibres_todos.json"), list(self._calibres_todos.values()))
        return list(self._calibres_todos.values())

    # --- mochila
    # --- contratos do próprio jogo (lidos pelo mod em contratos_jogo.json)
    PALAVRAS_PT = [("porco", ["javali", "porco", "caititu", "queixada", "cateto"]), ("cervo", ["cervo", "veado", "corça"]),
                   ("alce", ["alce", "wapiti", "uapiti"]), ("antilocapra", ["antilocapra", "pronghorn"]), ("pato", ["pato", "marreca", "arrabio"]),
                   ("ganso", ["ganso"]), ("peru", ["peru"]), ("faisao", ["faisão", "perdiz"]), ("codorna", ["codorna"]),
                   ("pomba", ["pomba", "rolinha"]), ("antilope", ["antílope", "nilgai", "órix"]), ("felino", ["lince", "puma", "felino"]),
                   ("roedor", ["cão-da-pradaria"]), ("coiote", ["coiote"]), ("lobo", ["lobo"]), ("raposa", ["raposa"]),
                   ("coelho", ["coelho", "lebre"]), ("urso", ["urso"]), ("carneiro", ["carneiro", "cabra"]), ("bisao", ["bisão"])]
    VENDEDORES = {"Ranger": "Guarda-florestal", "SportsShooter": "Atirador esportivo", "Hunter": "Caçador", "Guide": "Guia"}

    def contratos_jogo(self):
        d = self.cache.json(self.caminho("contratos_jogo.json"), None)
        if not d or not self.em_reserva() or time.time() - (d.get("ts") or 0) > 120:
            return []
        limpo = lambda t: re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(t or ""))).strip()
        saida = []
        for c in d.get("contratos") or []:
            if not isinstance(c, dict):
                continue
            objs = []
            for o in c.get("objetivos") or []:
                meta = int(o.get("meta") or 1) if o.get("quantidade") else 1
                prog = min(int(o.get("progresso") or 0), meta)
                texto_o = limpo(o.get("titulo"))
                if texto_o.endswith("sob influência"):
                    texto_o += " de um chamador"
                objs.append({"texto": texto_o, "progresso": prog, "meta": meta, "feito": prog >= meta})
            vend = (c.get("vendedor") or "").split(".")[-1]
            tempo = c.get("tempo")
            texto = " ".join([limpo(c.get("titulo")), limpo(c.get("descricao"))] + [o["texto"] for o in objs]).lower()
            grupo = next((g for g, palavras in self.PALAVRAS_PT if any(p in texto for p in palavras)), None)
            dist = re.search(r"(\d{2,4})\s*m(?:etros)?\b", texto)
            tipo = "atrair" if re.search(r"apito|chamad|atrai|isca|chamariz", texto) else \
                ("distancia" if dist and re.search(r"dist|longe|mais de|alcance", texto) else ("abater_grupo" if grupo else "abater_qualquer"))
            saida.append({"id": "jogo:" + str(c.get("id") or len(saida)), "titulo": limpo(c.get("titulo")) or "Contrato do jogo",
                          "descricao": limpo(c.get("descricao")), "vendedor": self.VENDEDORES.get(vend, vend or "Jogo"),
                          "rastreado": bool(c.get("rastreado")), "objetivos": objs, "do_jogo": True,
                          "tempo_min": round(tempo / 60) if isinstance(tempo, (int, float)) and c.get("limitado") and tempo > 0 else None,
                          "tipo": tipo, "grupo": grupo, "dist_min": int(dist.group(1)) if tipo == "distancia" else 0})
        return saida

    def _lida_mochila(self):
        """mochila.json + munição/acessórios das armas (armas.json); pede ao jogo uma leitura nova de vez em quando."""
        agora = time.time()
        if self.em_reserva() and agora - getattr(self, "_mochila_pedida", 0) > 12:
            self._mochila_pedida = agora
            self.enviar_comando(["mochila ler"])
        lida = self.cache.json(self.caminho("mochila.json"), None)
        if lida and not lida.get("itens") and lida.get("pronto") is not True:
            lida = None
        if lida:
            # munição e acessórios: só das armas da mochila, lidos raramente (armas.json)
            armas = self.cache.json(self.caminho("armas.json"), None) or {}
            mun = armas.get("municao") if isinstance(armas.get("municao"), dict) else {}
            lida = dict(lida, municao=mun if mun or "municao" not in lida else lida["municao"])
            nas = {"DA_" + i["item"].split("ID_", 1)[-1] + "_StoreItem" for i in lida.get("itens") or []
                   if i.get("tipo") == "Inventory.Weapon" and "ID_" in (i.get("item") or "")}
            faltam = {x for x in nas if x not in mun and x.replace("_StoreItem", "_StoreAsset") not in mun}
            velho = agora - (armas.get("ts") or 0) > 300
            if self.em_reserva() and (faltam or velho) and agora - getattr(self, "_armas_pedidas", 0) > 30:
                self._armas_pedidas = agora
                self.enviar_comando(["mochila armas"])
        return lida

    def licencas(self):
        """licencas.json da reserva atual (pedido ao jogo a cada 30 s) + a última leitura guardada de cada reserva."""
        agora = time.time()
        if self.em_reserva() and agora - getattr(self, "_licencas_pedidas", 0) > 30:
            self._licencas_pedidas = agora
            self.enviar_comando(["licencas"])
        if not hasattr(self, "_licencas_todas"):
            self._licencas_todas = carregar_json(os.path.join(BASE_DIR, "licencas_todas.json"), {})
        atual = self.cache.json(self.caminho("licencas.json"), None)
        if atual and atual.get("mapa") and self._licencas_todas.get(atual["mapa"]) != atual:
            self._licencas_todas[atual["mapa"]] = atual
            salvar_json(os.path.join(BASE_DIR, "licencas_todas.json"), self._licencas_todas)
        nivel = (self.nivel() or "")
        if atual and (not self.em_reserva() or (atual.get("mapa") and atual["mapa"] not in nivel)):
            atual = None      # leitura de outra reserva: não vale para comprar aqui
        return atual, self._licencas_todas

    NIVEL_EARL, MAX_NIVEL_EARL = 200, 10

    def pontos_earl(self):
        """Pontos próprios do Earl (todas as reservas): a reputação de cada contrato dele que foi pago,
        menos a perda dos contratos abortados. Entram na patente no recálculo final."""
        v = 0
        for m in self.dados.get("missoes") or []:
            if m.get("status") == "paga":
                v += int(m.get("reputacao") or 0)
            elif (m.get("penalidade") or {}).get("reputacao"):
                v -= int(m["penalidade"]["reputacao"])
        v = max(0, v)
        nv = min(self.MAX_NIVEL_EARL, v // self.NIVEL_EARL)
        topo = nv >= self.MAX_NIVEL_EARL
        return {"nome": "Earl", "valor": v, "nivel": nv, "max": self.MAX_NIVEL_EARL,
                "proximo": None if topo else (nv + 1) * self.NIVEL_EARL,
                "progresso": 1.0 if topo else (v - nv * self.NIVEL_EARL) / self.NIVEL_EARL,
                "contratos": sum(1 for m in self.dados.get("missoes") or [] if m.get("status") == "paga")}

    def vigiar_zonas_novas(self):
        """Zona de necessidade que passou a descoberta vira evento (contrato de reconhecimento)."""
        if not self.em_reserva() or time.time() - getattr(self, "_zn_vista", 0) < 20:
            return
        self._zn_vista = time.time()
        nv = self.nivel()
        zs = self.zonas()
        if not zs:
            return
        achadas = {str(z.get("hash")): z for z in zs if z.get("descoberta") and z.get("hash") is not None}
        salvas = self.dados.setdefault("zonas_descobertas", {})
        if nv not in salvas:                # primeira vez nesta reserva: só guarda a base
            salvas[nv] = sorted(achadas)
            self.salvar_pendente = True
            return
        antes = set(salvas[nv])
        novas = [h for h in achadas if h not in antes]
        if not novas:
            return
        salvas[nv] = sorted(antes | set(novas))
        for h in novas:
            z = achadas[h]
            avaliar_missoes(self.dados, {"tipo": "zona_descoberta", "id": h, "grupo": z.get("grupo"),
                                         "especie": z.get("especie"), "ts": time.time()}, self.reserva())
        self.salvar_pendente = True

    PASTA_TROFEUS = os.path.join(BASE_DIR, "trofeus")

    def print_trofeu(self, reg, manual=False):
        """Print da tela do PC (só no Windows com Pillow). A foto da tecla F9 sempre vence a automática."""
        try:
            from PIL import ImageGrab
            os.makedirs(self.PASTA_TROFEUS, exist_ok=True)
            nome = time.strftime("trofeu_%Y%m%d_%H%M%S.jpg")
            img = ImageGrab.grab(all_screens=False).convert("RGB")
            img.save(os.path.join(self.PASTA_TROFEUS, nome), quality=88)
            with self.lock:
                if manual:
                    if reg.get("arquivo") and not reg.get("manual"):
                        reg["arquivo_auto"] = reg["arquivo"]
                    reg["arquivo"], reg["manual"] = nome, True
                elif not reg.get("manual"):
                    reg["arquivo"] = nome
                else:
                    reg["arquivo_auto"] = nome
                self.salvar_pendente = True
                if manual:
                    self.hud_oculto_ate = 0      # devolve os contratos à tela do jogo
                    self.escrever_hud()
        except Exception as e:
            print("print do troféu falhou:", e)
            self.hud_oculto_ate = 0

    def vigiar_licencas(self):
        """Espécies da reserva atual com 1 ou 0 animal restante na licença (aviso no mapa)."""
        if not self.em_reserva() or time.time() - getattr(self, "_lic_vista", 0) < 5:
            return
        self._lic_vista = time.time()
        lic_mod, todas = self.licencas()
        alerta = []
        for l in (lic_mod or {}).get("licencas") or []:
            info = extras.licenca_da_especie(l.get("tag"), lic_mod, todas)
            if info and info.get("restam") is not None and info["restam"] <= 1:
                alerta.append({"tag": l["tag"], "especie_nome": nome_especie(l["tag"]), "restam": info["restam"], "max": info["max"]})
        self.licencas_alerta = sorted(alerta, key=lambda x: (x["restam"], x["especie_nome"]))

    def trazer_carro(self, corpo):
        """Traz o último carro usado para ~12 m de um ponto (acampamento), do lado de onde você vem."""
        if not self.em_reserva():
            return {"ok": False, "erro": "Entre numa reserva no jogo primeiro."}
        try:
            x, y = float(corpo["x"]), float(corpo["y"])
            z = float(corpo["z"]) if corpo.get("z") not in (None, "") else None
        except (KeyError, TypeError, ValueError):
            return {"ok": False, "erro": "Ponto inválido."}
        p = (self.estado or {}).get("pos") or {}
        dx, dy = (p.get("x", x + 1) - x), (p.get("y", y) - y)
        n = math.hypot(dx, dy) or 1.0
        x, y = x + dx / n * 1200, y + dy / n * 1200
        if not self.enviar_comando([f"carro {x:.0f} {y:.0f}" + (f" {z:.0f}" if z is not None else "")]):
            return {"ok": False, "erro": "O jogo não está respondendo."}
        return {"ok": True}

    def ir_ate(self, corpo):
        """Viagem rápida até um ponto descoberto do mapa (acampamento, torre, agente, cabana...)."""
        if not self.em_reserva():
            return {"ok": False, "erro": "Entre numa reserva no jogo primeiro."}
        try:
            x, y = float(corpo["x"]), float(corpo["y"])
            z = float(corpo["z"]) if corpo.get("z") not in (None, "") else None
        except (KeyError, TypeError, ValueError):
            return {"ok": False, "erro": "Ponto inválido."}
        # chega a 10 m do ponto, do lado de onde você vem (no centro da estrutura o jogo prende o caçador)
        p = (self.estado or {}).get("pos") or {}
        dx, dy = (p.get("x", x + 1) - x), (p.get("y", y) - y)
        n = math.hypot(dx, dy) or 1.0
        x, y = x + dx / n * 1000, y + dy / n * 1000
        self.pausa_pos_ate = time.time() + 45        # não grava "último local" no meio da viagem (o mapa ainda carrega)
        # com a altura do ponto (o traço do chão falha quando o destino está longe e o terreno ainda não carregou)
        self.vigiar_queda(x, y, z)
        if not self.enviar_comando([f"teleport {x:.0f} {y:.0f}" + (f" {z:.0f}" if z is not None else "")]):
            return {"ok": False, "erro": "O jogo não está respondendo."}
        return {"ok": True}

    # ------------------------------------------------------------ câmeras de trilha: saíram (v0.1.72)
    def reembolsar_cameras(self):
        """O jogo só tem animais a ~750 m de você, então as câmeras saíram da loja: devolve o que foi pago, uma vez."""
        d = self.dados
        if d.get("cameras_reembolsadas") or not self.em_reserva():
            return
        cams = [c for lista in (d.get("cameras") or {}).values() for c in lista if not c.get("falhou") and not c.get("pendente")]
        valor = 150 * len(cams)
        if valor and not self.enviar_comando([f"add_credits {valor} reembolso_cameras"]):
            return
        d["cameras_reembolsadas"] = {"valor": valor, "ts": time.time()}
        d.pop("cameras", None)
        d.pop("camera_registros", None)
        if valor:
            self.aviso_app = {"texto": f"As câmeras saíram da loja. Devolvemos ${valor} ({len(cams)} câmera{'s' if len(cams) != 1 else ''}).", "ts": time.time()}
        salvar_json(DADOS_PATH, d)

    # ------------------------------------------------------------ barracas (Loja do Earl)
    PRECO_BARRACA, MAX_BARRACAS = 300, 10

    def barracas(self):
        return [b for b in (self.dados.get("barracas") or {}).get(self.reserva() or "", []) if not b.get("falhou")]

    def acao_barraca(self, corpo):
        if not self.em_reserva():
            return {"ok": False, "erro": "Entre numa reserva no jogo primeiro."}
        reserva = self.reserva()
        lista = self.dados.setdefault("barracas", {}).setdefault(reserva, [])
        lista[:] = [b for b in lista if not b.get("falhou")]
        acao = corpo.get("acao")
        if acao == "comprar":
            if len(lista) >= self.MAX_BARRACAS:
                return {"ok": False, "erro": f"Você já tem {self.MAX_BARRACAS} barracas nesta reserva. Desmonte uma primeiro."}
            cred = (self.estado.get("moedas") or {}).get("Currency.Credits") or 0
            if cred < self.PRECO_BARRACA:
                return {"ok": False, "erro": "Créditos insuficientes."}
            # a barraca é montada onde o caçador está (posição real, com a altura do chão)
            p = (self.estado or {}).get("pos")
            if not p or self.estado.get("chao") is False:
                return {"ok": False, "erro": "Fique parado no chão para montar a barraca."}
            x, y, z = float(p["x"]), float(p["y"]), float(p.get("z") or 0)
            ref = uuid.uuid4().hex[:6]
            if not self.enviar_comando([f"cobrar {self.PRECO_BARRACA} {ref}"]):
                return {"ok": False, "erro": "O jogo não está respondendo."}
            lista.append({"id": ref, "x": x, "y": y, "z": z, "nome": f"Barraca {len(lista) + 1}", "ts": time.time(), "pendente": ref})
        elif acao == "carro":
            b = next((b for b in lista if b["id"] == corpo.get("id")), None)
            if not b:
                return {"ok": False, "erro": "Barraca não encontrada."}
            # 8 m ao lado da barraca (o jogo leva o último carro usado, com o setup dele)
            alvo = f"carro {b['x'] + 800:.0f} {b['y']:.0f}" + (f" {b['z']:.0f}" if b.get("z") is not None else "")
            if not self.enviar_comando([alvo]):
                return {"ok": False, "erro": "O jogo não está respondendo."}
        elif acao == "desmontar":
            lista[:] = [b for b in lista if b["id"] != corpo.get("id")]
        elif acao == "ir":
            b = next((b for b in lista if b["id"] == corpo.get("id")), None)
            if not b:
                return {"ok": False, "erro": "Barraca não encontrada."}
            self.pausa_pos_ate = time.time() + 15
            # exatamente onde você estava ao montar (altura conhecida; barracas antigas sem altura: o mod mede o chão)
            alvo = f"teleport {b['x']:.0f} {b['y']:.0f}" + (f" {b['z']:.0f}" if b.get("z") is not None else "")
            self.pausa_pos_ate = time.time() + 45
            self.vigiar_queda(b["x"], b["y"], b.get("z"))
            if not self.enviar_comando([alvo]):
                return {"ok": False, "erro": "O jogo não está respondendo."}
        else:
            return {"ok": False, "erro": "Ação inválida."}
        salvar_json(DADOS_PATH, self.dados)
        return {"ok": True, "barracas": self.barracas()}

    def recarregar_municao(self):
        """Enche a reserva de munição das armas da mochila (no jogo a munição não custa nada)."""
        if not self.em_reserva():
            return {"ok": False, "erro": "Entre numa reserva no jogo primeiro."}
        ref = uuid.uuid4().hex[:6]
        if not self.enviar_comando([f"municao 0 {ref}"]):
            return {"ok": False, "erro": "O jogo não está respondendo."}
        return {"ok": True, "ref": ref}

    def comprar_licenca(self, tag):
        if not re.fullmatch(r"Animals\.Types\.[\w.]+", tag or ""):
            return {"ok": False, "erro": "Espécie inválida."}
        lic_mod, todas = self.licencas()
        info = extras.licenca_da_especie(tag, lic_mod, todas)
        if not info:
            return {"ok": False, "erro": "Esta espécie não tem licença no jogo."}
        if not self.em_reserva() or not info["comprar_aqui"]:
            return {"ok": False, "erro": "A licença só pode ser comprada dentro da reserva onde a espécie vive."}
        cred = (self.estado.get("moedas") or {}).get("Currency.Credits") or 0
        if info["preco"] > cred:
            return {"ok": False, "erro": "Créditos insuficientes."}
        ref = uuid.uuid4().hex[:6]
        if not self.enviar_comando([f"licenca {tag} {int(info['preco'])} {ref}"]):
            return {"ok": False, "erro": "O jogo não está respondendo."}
        self._licencas_pedidas = 0
        return {"ok": True, "ref": ref}

    def dados_kit(self, tag):
        dados = self.cache.json(self.caminho("jogo_dados.json"), None)
        if not dados:
            return {"pronto": False}
        lida = self._lida_mochila()
        lic_mod, lic_todas = self.licencas()
        with self.lock:
            r = extras.kit_especie(dados, self.tabela_calibres(), self.equipamento(), lida, tag, nome_especie, lic_mod, lic_todas)
        r["pronto"] = True
        r["em_reserva"] = self.em_reserva()
        r["fila"] = getattr(self, "_mochila_fila_ate", 0) > time.time()
        r["sugestao"] = extras.sugestao_kit(r)
        return r

    def dados_mochila(self, ids=None, especies=None):
        agora = time.time()
        dados = self.cache.json(self.caminho("jogo_dados.json"), None)
        lida = self._lida_mochila()
        do_jogo = self.contratos_jogo()
        with self.lock:
            ativas = self.por_status("ativa") + do_jogo
            escolhidas = [m for m in ativas if not ids or m["id"] in ids]
            if not dados:
                return {"pronto": False}
            # espécies escolhidas na Mochila entram como "alvos" junto com os contratos
            validas = {a.get("tag") for a in dados.get("animais", [])}
            alvos = [t for t in (especies or []) if t in validas]
            extras_alvo = [{"id": "esp:" + t, "titulo": nome_especie(t), "tipo": "abater_grupo", "grupo": grupo_de(t)[0], "especie": t}
                           for t in alvos]
            r = extras.mochila(dados, self.tabela_calibres(), self.equipamento(), lida, escolhidas + extras_alvo,
                               nome_especie, grupo_de, nome_grupo)
            reserva = (self.nivel() or "").lower().split("_")[0]
            r["especies"] = sorted(
                [{"tag": a["tag"], "nome": nome_especie(a["tag"]) or a.get("titulo"),
                  "reservas": sorted({extras.nome_mapa(m) for m in a.get("mapas") or []} - {"Rancho"}),
                  "aqui": bool(reserva) and any(reserva in (m or "").lower() for m in a.get("mapas") or []),
                  "escolhida": a["tag"] in alvos}
                 for a in dados.get("animais", []) if a.get("tag") and not a["tag"].endswith(".Hub")],
                key=lambda e: (not e["aqui"], e["nome"] or ""))
            r["pronto"] = True
            r["ativas"] = [{"id": m["id"], "titulo": m["titulo"], "escolhida": m in escolhidas, "do_jogo": bool(m.get("do_jogo")),
                            "vendedor": m.get("vendedor")} for m in ativas]
            r["em_reserva"] = self.em_reserva()
            r["no_jogo"] = r["em_reserva"]
            r["lida_idade"] = round(agora - lida["ts"]) if lida and lida.get("ts") else None
            r["fila"] = getattr(self, "_mochila_fila_ate", 0) > agora
            r["tem_anterior"] = bool(self.dados.get("setup_anterior"))
            r["especies_salvas"] = self.dados.get("mo_especies")
            r["setups"] = [x.get("nome") for x in self.dados.get("setups") or []]
            return r

    def acao_mochila(self, corpo):
        if not self.em_reserva():
            return {"ok": False, "erro": "Entre numa reserva no jogo para mexer na mochila."}
        acao = corpo.get("acao")
        ok_id = lambda x: bool(x) and bool(re.fullmatch(r"[\w:.\-]+", str(x)))
        tipos = ("Inventory.Weapon", "Inventory.Objects", "Inventory.GPS")
        linhas = []
        if acao == "por" and ok_id(corpo.get("item")) and corpo.get("tipo") in tipos:
            linhas = [f"mochila por {corpo['item']} {corpo['tipo']} {max(0, int(corpo.get('idx') or 0))}"]
        elif acao == "tirar" and ok_id(corpo.get("item")):
            linhas = [f"mochila tirar {corpo['item']}"]
        elif acao == "municao" and ok_id(corpo.get("arma")) and ok_id(corpo.get("municao")):
            linhas = [f"mochila municao {corpo['arma']} {corpo['municao']}"]
        elif acao == "acessorio" and ok_id(corpo.get("arma")) and ok_id(corpo.get("acessorio")):
            linhas = [f"mochila acessorio {corpo['arma']} {corpo['acessorio']}"]
        elif acao == "tirar_acessorio" and ok_id(corpo.get("arma")) and ok_id(corpo.get("acessorio")):
            linhas = [f"mochila tirar_acessorio {corpo['arma']} {corpo['acessorio']}"]
        elif acao in ("kit", "kit_auto") and ok_id(corpo.get("tag")):
            kit = self.dados_kit(corpo["tag"])
            if not kit.get("pronto") or not kit.get("lida"):
                return {"ok": False, "erro": "A mochila ainda não foi lida do jogo. Espere alguns segundos."}
            escolha = corpo.get("escolha") if acao == "kit" else extras.sugestao_kit(kit, corpo.get("espaco"))
            linhas, _ = extras.plano_kit(kit, escolha if isinstance(escolha, dict) else {})
            linhas = [l for l in linhas if all(ok_id(x) for x in l.split()[2:])]
            if not linhas:
                return {"ok": True, "nada": True}
        elif acao == "kit_previa" and ok_id(corpo.get("tag")):
            kit = self.dados_kit(corpo["tag"])
            escolha = corpo.get("escolha") if isinstance(corpo.get("escolha"), dict) else extras.sugestao_kit(kit, corpo.get("espaco"))
            _, resumo = extras.plano_kit(kit, escolha)
            return {"ok": True, "resumo": resumo, "escolha": escolha}
        elif acao == "montar":
            ids = [str(x) for x in (corpo.get("missoes") or [])] or None
            esp = [str(x) for x in (corpo.get("especies") or []) if re.fullmatch(r"[\w.]+", str(x))]
            plano = self.dados_mochila(ids, esp).get("plano") or []
            for t in plano:
                if t["acao"] == "por" and ok_id(t["item"]):
                    linhas.append(f"mochila por {t['item']} {t['tipo']} {int(t['idx'])}")
                elif t["acao"] == "municao" and ok_id(t["arma"]) and ok_id(t["municao"]):
                    linhas.append(f"mochila municao {t['arma']} {t['municao']}")
            if not linhas:
                return {"ok": True, "nada": True}
        elif acao == "setup_voltar":
            linhas = self.plano_setup(self.dados.get("setup_anterior"))
            if linhas is None:
                return {"ok": False, "erro": "Ainda não há um setup anterior guardado."}
            if not linhas:
                return {"ok": True, "nada": True}
        elif acao == "setup_aplicar":
            setups = self.dados.get("setups") or []
            i = int(corpo.get("idx") if str(corpo.get("idx", "")).isdigit() else -1)
            if not 0 <= i < len(setups):
                return {"ok": False, "erro": "Setup não encontrado."}
            linhas = self.plano_setup(setups[i].get("foto"))
            if not linhas:
                return {"ok": True, "nada": True}
        else:
            return {"ok": False, "erro": "Ação inválida."}
        linhas, erro = self.com_compras(linhas)
        if erro:
            return {"ok": False, "erro": erro}
        foto = self.foto_setup()
        if foto:
            self.dados["setup_anterior"] = foto      # "Setup anterior" = como estava antes desta troca
        if acao in ("setup_voltar", "setup_aplicar"):
            fase1 = [l for l in linhas if l.split()[0] == "mochila" and l.split()[1] in ("tirar", "por")]
            fase2 = [l for l in linhas if l not in fase1]
            if fase1 and fase2:
                # a arma recém-posta demora para aceitar acessórios: manda munição/acessórios depois
                if not self.enviar_comando(fase1):
                    return {"ok": False, "erro": "O jogo não está respondendo."}
                threading.Timer(len(fase1) + 4, lambda: self.enviar_comando(fase2)).start()
                total = len(fase1) + 4 + len(fase2)
                self._mochila_fila_ate = time.time() + total + 3
                self._mochila_pedida = time.time() + total
                return {"ok": True, "trocas": len(linhas), "segundos": total + 2}
        if not self.enviar_comando(linhas):
            return {"ok": False, "erro": "O jogo não está respondendo."}
        # o mod faz uma troca por segundo e depois salva e relê
        self._mochila_fila_ate = time.time() + len(linhas) + 3
        self._mochila_pedida = time.time() + len(linhas)
        return {"ok": True, "trocas": len(linhas), "segundos": len(linhas) + 2}

    def com_compras(self, linhas):
        """Munição/acessório que você ainda não comprou: compra antes de montar (o jogo não aceita item não comprado)."""
        equip = self.equipamento()
        comprados = {b["id"] for b in equip.get("comprados", [])}
        cat = {c.get("id"): c for c in self.catalogo()}
        cred = (self.estado.get("moedas") or {}).get("Currency.Credits") or 0
        saida, custo = [], 0
        for l in linhas:
            partes = l.split()
            if len(partes) == 4 and partes[1] in ("municao", "acessorio"):
                item = cat.get(partes[3]) or {}
                if item and partes[3] not in comprados and not item.get("padrao"):
                    custo += item.get("preco") or 0
                    if custo > cred:
                        return None, f"Créditos insuficientes para comprar {item.get('nome') or partes[3]}."
                    saida.append(f"comprar {partes[3]} {uuid.uuid4().hex[:6]}")
                    comprados.add(partes[3])
            saida.append(l)
        return saida, None

    # ------------------------------------------------------------ setups da mochila (anterior e salvos)
    def foto_setup(self):
        """Retrato da mochila agora: o que está em cada espaço e munição/acessórios de cada arma."""
        lida = self._lida_mochila()
        if not lida or not lida.get("itens"):
            return None
        itens = [{"tipo": i.get("tipo"), "idx": i.get("idx"), "item": i.get("item")} for i in lida["itens"]
                 if i.get("tipo") in ("Inventory.Weapon", "Inventory.Objects") and i.get("item")]
        mun = lida.get("municao") if isinstance(lida.get("municao"), dict) else {}
        return {"itens": itens, "armas": {k: list(v) for k, v in mun.items()}, "ts": time.time()}

    def plano_setup(self, foto):
        """Comandos para deixar a mochila igual à foto (None = sem foto)."""
        if not foto:
            return None
        agora = self.foto_setup()
        if not agora:
            return []
        ok_id = lambda x: bool(x) and bool(re.fullmatch(r"[\w:.\-]+", str(x)))
        atual = {(i["tipo"], i["idx"]): i["item"] for i in agora["itens"]}
        onde = {i["item"]: (i["tipo"], i["idx"]) for i in agora["itens"]}
        linhas = []
        for i in foto.get("itens") or []:
            chave = (i.get("tipo"), i.get("idx"))
            if atual.get(chave) == i.get("item") or not ok_id(i.get("item")):
                continue
            if i["item"] in onde:
                linhas.append(f"mochila tirar {i['item']}")
            linhas.append(f"mochila por {i['item']} {i['tipo']} {int(i['idx'])}")
        armas_agora = agora.get("armas") or {}
        for arma, quer in (foto.get("armas") or {}).items():
            if not ok_id(arma):
                continue
            tem = set(armas_agora.get(arma) or [])
            for x in quer:
                if x not in tem and ok_id(x):
                    linhas.append(f"mochila {'municao' if '_Ammo_' in x else 'acessorio'} {arma} {x}")
            for x in tem - set(quer):
                if "_Ammo_" not in x and ok_id(x):
                    linhas.append(f"mochila tirar_acessorio {arma} {x}")
        return linhas

    def setups(self, corpo):
        """Predefinições de setup com nome: listar, salvar o atual, apagar."""
        lista = self.dados.setdefault("setups", [])
        acao = corpo.get("acao")
        if acao == "salvar":
            nome = str(corpo.get("nome") or "").strip()[:40] or f"Setup {len(lista) + 1}"
            foto = self.foto_setup()
            if not foto:
                return {"ok": False, "erro": "A mochila ainda não foi lida do jogo."}
            lista.append({"nome": nome, "foto": foto})
            del lista[:-20]
        elif acao == "apagar" and str(corpo.get("idx", "")).isdigit() and int(corpo["idx"]) < len(lista):
            lista.pop(int(corpo["idx"]))
        elif acao == "renomear" and str(corpo.get("idx", "")).isdigit() and int(corpo["idx"]) < len(lista):
            lista[int(corpo["idx"])]["nome"] = str(corpo.get("nome") or "").strip()[:40] or lista[int(corpo["idx"])]["nome"]
        salvar_json(DADOS_PATH, self.dados)
        return {"ok": True, "setups": [{"nome": x["nome"], "armas": [i["item"].split("ID_", 1)[-1].replace("_", " ")
                                                                    for i in x["foto"]["itens"] if i["tipo"] == "Inventory.Weapon"]}
                                       for x in lista],
                "tem_anterior": bool(self.dados.get("setup_anterior"))}

    def dados_loja(self):
        with self.lock:
            lida = self._lida_mochila() or {}
            na_mochila = {i.get("item") for i in lida.get("itens") or [] if i.get("item")}
            r = extras.loja(self.catalogo(), self.equipamento(), na_mochila)
            r["creditos"] = (self.estado.get("moedas") or {}).get("Currency.Credits")
            r["compras"] = self.dados["compras"][-5:]
            return r

    def dados_enciclopedia(self):
        dados = self.cache.json(self.caminho("jogo_dados.json"), None)
        with self.lock:
            if dados:
                return extras.enciclopedia_jogo(dados, self.tabela_calibres(), self.equipamento(), self.dados["abates"],
                                                self.dados["especies_vistas"], nome_especie, grupo_de)
            return {"pronto": False}

    def comprar(self, id_):
        with self.lock:
            item = next((c for c in self.catalogo() if c.get("id") == id_), None)
            if not item:
                return {"ok": False, "erro": "Item não encontrado no catálogo."}
            if not self.em_reserva():
                return {"ok": False, "erro": "Entre numa reserva para comprar."}
            cred = (self.estado.get("moedas") or {}).get("Currency.Credits") or 0
            if (item.get("preco") or 0) > cred:
                return {"ok": False, "erro": "Créditos insuficientes."}
            ref = uuid.uuid4().hex[:6]
            if not self.enviar_comando([f"comprar {id_} {ref}"]):
                return {"ok": False, "erro": "O jogo não está respondendo."}
        return {"ok": True, "ref": ref}

    def resultado_compra(self, ref):
        with self.lock:
            ev = next((e for e in reversed(self.dados["compras"]) if e.get("ref") == ref), None)
        if not ev:
            return {"pronto": False}
        return {"pronto": True, "ok": bool(ev.get("ok")), "saldo": ev.get("depois")}

    # --- ciclo
    def texto_hud(self, m):
        """Linha do objetivo no formato da caixa de contratos do jogo (<Target> destaca o número)."""
        desc = re.sub(r"\s+\([^)]*\)", "", (m.get("descricao") or m.get("titulo") or "")).strip().rstrip(".")
        desc = re.sub(r"(\d+(?:[–-]\d+)?(?:\s*m\b|%)?)", r"<Target>\1</>", desc, count=1)
        texto = f"Earl: {desc}"
        meta = int(m.get("meta") or 1)
        prog = min(int(m.get("progresso") or 0), meta)
        feito = m["status"] != "ativa"
        progresso = f"<Progress>{meta if feito else prog}</> / {meta}"
        limpo = lambda t: str(t).replace("\t", " ").replace("\n", " ").replace("\r", " ")
        return "O\t" + limpo(texto) + "\t" + progresso + "\t" + ("1" if feito else "0")

    def escrever_hud(self):
        linhas = ["T\tContratos do Velho Earl"]
        if self.cfg.get("contratos_no_jogo", True) and time.time() > getattr(self, "hud_oculto_ate", 0):
            agora = time.time()
            r = self.reserva()
            for m in self.dados["missoes"]:
                if m.get("reserva") and m["reserva"] != r:
                    continue
                recente = m["status"] == "concluida" or (m["status"] == "paga" and agora - (m.get("pago_em") or 0) < 5)
                if m["status"] == "ativa" or recente:
                    linhas.append(self.texto_hud(m))
        txt = "\n".join(linhas) + "\n"
        if txt != getattr(self, "_hud_txt", None):
            try:
                with open(self.caminho("hud.txt"), "w", encoding="utf-8") as f:
                    f.write(txt)
                self._hud_txt = txt
            except OSError:
                pass

    def ciclo(self):
        with self.lock:
            self.escrever_hud()
            if (not ARMA_TIPOS or not TITULOS_JOGO) and time.time() - getattr(self, "_armas_em", 0) > 60:
                self._armas_em = time.time()
                try:
                    self.info_gerador()
                except Exception:
                    pass
            self.ler_estado()
            self.vigiar_pino()
            self.separar_por_reserva()
            self.vigiar_jogo_novo()
            self.ler_animais()
            mudou = False
            for ev in self.ler_eventos():
                self.processar(ev)
                mudou = True
            self.cuidar_posicao()
            self.contar_dias()
            self.recontar_marcacoes()
            self.reembolsar_cameras()
            self.vigiar_licencas()
            self.vigiar_zonas_novas()
            self.vigiar_mortos()
            self.marcar_estruturas_perto()
            self.revisar_contratos()
            if self.em_reserva():
                if avaliar_missoes(self.dados, {"tipo": "posicao", "id": "local", "pos": self.estado["pos"], "ts": time.time()}, self.reserva()):
                    mudou = True
            self.pagar_pendentes()
            limite = time.time() - 7200
            self.dados["marcados"] = {k: v for k, v in self.dados["marcados"].items() if v.get("visto_em", 0) > limite}
            self.dados["posicoes"] = {k: v for k, v in self.dados["posicoes"].items() if k in self.dados["marcados"]}
            fim = [m for m in self.dados["missoes"] if m["status"] not in ("ativa", "oferta")]
            if len(fim) > 60:
                remover = {m["id"] for m in fim[:-60]}
                self.dados["missoes"] = [m for m in self.dados["missoes"] if m["id"] not in remover]
            if mudou or self.salvar_pendente or any(m["status"] == "concluida" for m in self.dados["missoes"]):
                salvar_json(DADOS_PATH, self.dados)
                self.salvar_pendente = False
        self.manter_ofertas()

    def loop(self):
        while True:
            try:
                self.ciclo()
            except Exception as e:  # nunca derruba a ponte
                print("erro no ciclo:", e)
            time.sleep(0.5)

    def estatisticas(self):
        ab = self.dados["abates"]
        por_grupo, por_arma = {}, {}
        dist = [a["distancia_m"] for a in ab if a.get("distancia_m")]
        for a in ab:
            por_grupo[a.get("grupo_nome", "?")] = por_grupo.get(a.get("grupo_nome", "?"), 0) + 1
            if a.get("arma"):
                por_arma[a["arma"]] = por_arma.get(a["arma"], 0) + 1
        melhor = max(ab, key=lambda a: a.get("genetica") or 0, default=None)
        return {
            "total_abates": len(ab),
            "por_grupo": sorted(por_grupo.items(), key=lambda x: -x[1]),
            "por_arma": sorted(por_arma.items(), key=lambda x: -x[1]),
            "distancia_media": round(sum(dist) / len(dist), 1) if dist else None,
            "distancia_maxima": round(max(dist), 1) if dist else None,
            "melhor_genetica": melhor and {"especie": melhor.get("especie_nome"), "genetica": melhor.get("genetica")},
            "missoes_concluidas": sum(1 for m in self.dados["missoes"] if m["status"] in ("concluida", "paga")),
            "creditos_ganhos": sum(m.get("creditos_pagos", 0) for m in self.dados["missoes"] if m.get("enviado")),
        }

    def snapshot(self):
        with self.lock:
            st = self.estado
            pos, yaw = st.get("pos"), st.get("yaw")
            agora = time.time()
            rastreados = []
            for id_, m in self.dados["marcados"].items():
                if m.get("reserva") and self.nivel() and m["reserva"] != self.nivel():
                    continue
                item = {k: v for k, v in m.items() if k not in ("seq",)}
                viva = self.dados["posicoes"].get(id_)
                if viva and agora - viva["ts"] < 20:
                    item["pos"], item["ao_vivo"], item["yaw"] = {"x": viva["x"], "y": viva["y"], "z": viva["z"]}, True, viva.get("yaw")
                else:
                    item["ao_vivo"] = False
                    if viva:
                        item["pos"] = {"x": viva["x"], "y": viva["y"], "z": viva["z"]}
                item["distancia_m"] = distancia_m(pos, item.get("pos"))
                item["direcao"] = direcao(pos, item.get("pos"), yaw)
                item["minutos"] = round((agora - m.get("visto_em", agora)) / 60, 1)
                rastreados.append(item)
            # animal baleado que já morreu e ainda não foi recolhido (o jogo marca no mapa): ícone de abatido
            try:
                mortos = (self.cache.json(self.caminho("mortos.json"), None) or {}).get("mortos") or []
                mortos_tiro = {str(x.get("id")): x for x in mortos if isinstance(x, dict) and x.get("tiro")}
            except Exception:
                mortos_tiro = {}
            for item in rastreados:
                mt = mortos_tiro.pop(str(item.get("id")), None)
                if mt:
                    item["morto"] = True
                    item["pos"] = {"x": mt["x"], "y": mt["y"], "z": mt.get("z", 0)}
                    item["distancia_m"] = distancia_m(pos, item["pos"])
            for mt in mortos_tiro.values():     # baleado sem ter sido marcado no binóculo
                rastreados.append({"id": mt.get("id"), "morto": True, "pos": {"x": mt["x"], "y": mt["y"], "z": mt.get("z", 0)},
                                   "especie": mt.get("especie"), "especie_nome": nome_especie(mt.get("especie")) if mt.get("especie") else "Animal",
                                   "grupo": grupo_de(mt.get("especie"))[0] if mt.get("especie") else "outro", "grupo_nome": "",
                                   "distancia_m": distancia_m(pos, {"x": mt["x"], "y": mt["y"], "z": 0}), "ao_vivo": False, "minutos": 0})
            rastreados.sort(key=lambda x: x["distancia_m"] if x["distancia_m"] is not None else 1e9)
            rep = next((r for r in st.get("reputacao", []) or [] if self.nivel() and self.nivel() in (r.get("mapa") or "")), None)
            # os 4 agentes de campo da reserva (níveis do jogo: 200, 400, 600, 800, 1000 pontos)
            agentes = []
            for tag, nome in AGENTES:
                r = next((r for r in st.get("reputacao", []) or [] if r.get("vendedor") == tag
                          and self.nivel() and self.nivel() in (r.get("mapa") or "")), None)
                v = int((r or {}).get("valor") or 0)
                nivel = min(5, v // 200)
                agentes.append({"tag": tag, "nome": nome, "valor": v, "nivel": nivel,
                                "proximo": None if nivel >= 5 else (nivel + 1) * 200,
                                "progresso": 1.0 if nivel >= 5 else (v - nivel * 200) / 200})
            earl = self.pontos_earl()
            r_atual = self.reserva()
            lista = [m for m in self.dados["missoes"] if r_atual and m.get("reserva") == r_atual]
            for m in lista:
                m["agente_nome"] = missoes.AGENTE_NOME.get(missoes.agente_de(m))
            return {
                "versao": VERSAO,
                "atualizacao": ATUALIZADOR.info() if ATUALIZADOR else None,
                "conectado": self.conectado(),
                "em_reserva": self.em_reserva(),
                "estado": st,
                "reputacao_mapa_atual": rep, "agentes": agentes, "earl": earl,
                "mapa": self.info_mapa(),
                "pino_app": self.dados.get("pino_app"),
                "rastreados": rastreados, "ultimo_marcado": getattr(self, "ultimo_marcado", None),
                "barracas": self.barracas(), "preco_barraca": self.PRECO_BARRACA, "max_barracas": self.MAX_BARRACAS,
                "licencas_alerta": getattr(self, "licencas_alerta", []), "aviso_app": getattr(self, "aviso_app", None),
                "carcaca_nova": getattr(self, "carcaca_nova", None), "boletim_novo": getattr(self, "boletim_novo", None),
                "novidade_vista": self.dados.get("novidade_vista"),
                "ofertas": [m for m in lista if m["status"] == "oferta"],
                "ativas": [m for m in lista if m["status"] == "ativa"],
                "contratos_jogo": self.contratos_jogo(),
                # concluído fica à vista só até o pagamento confirmar (+5 s para você ver o "pago"); depois só no histórico
                "finalizadas": [m for m in lista if m["status"] == "concluida" or (m["status"] == "paga"
                                and time.time() - (m.get("pago_em") or m.get("concluida_em") or 0) < 5)][-8:][::-1],
                "gerando": self.gerando,
                "reserva": r_atual,
                "outras_reservas": self.outras_reservas(),
                "abates": self.dados["abates"][-30:][::-1],
                "estatisticas": self.estatisticas(),
                "npc": missoes.NPC,
                "patente": extras.patente(self.dados["abates"], lista),
                "aviso_teleporte": self.aviso_teleporte,
                "config": {"voltar_ao_ultimo_local": self.cfg.get("voltar_ao_ultimo_local"),
                           "contratos_no_jogo": self.cfg.get("contratos_no_jogo", True)},
                "tem_local_salvo": bool(getattr(self, "anterior", None)),
                "chat": [{"role": c["role"], "content": c["content"]} for c in self.dados["chat"][-20:]],
                "pasta_mod": self.cfg["pasta_mod"],
                "pasta_mod_existe": os.path.isdir(self.cfg["pasta_mod"] or ""),
                "jogo_novo": bool(getattr(self, "novo_jogo_suspeito", False)),
            }


def abrir_janela(url):
    """Abre o app numa janela própria (modo aplicativo do Edge/Chrome), sem barra de navegador."""
    candidatos = []
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if not base:
            continue
        candidatos += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                       os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    for exe in candidatos:
        if os.path.isfile(exe):
            perfil = os.path.join(BASE_DIR, "perfil_janela")
            try:
                env = {k: v for k, v in os.environ.items() if not k.startswith(("_PYI", "_MEI"))}
                subprocess.Popen([exe, f"--app={url}", "--window-size=1400,900", f"--user-data-dir={perfil}",
                                  "--no-first-run", "--no-default-browser-check"], env=env)
                return
            except Exception:
                pass
    webbrowser.open(url)


def iniciar_nova_instancia(exe, args):
    """Abre uma cópia nova do programa, independente desta (sem herdar o ambiente do PyInstaller)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("_PYI", "_MEI"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    flags = 0
    for nome in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_BREAKAWAY_FROM_JOB"):
        flags |= getattr(subprocess, nome, 0)
    try:
        subprocess.Popen([exe] + args, env=env, creationflags=flags, close_fds=True, cwd=os.path.dirname(exe))
    except OSError:
        flags &= ~getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
        subprocess.Popen([exe] + args, env=env, creationflags=flags, close_fds=True, cwd=os.path.dirname(exe))


def _apagar(pasta, teste):
    try:
        for nome in os.listdir(pasta):
            if teste(nome):
                try:
                    os.remove(os.path.join(pasta, nome))
                except OSError:
                    pass
    except OSError:
        pass


def limpar_antigos(pasta_mod=None):
    """Apaga sobras de versões antigas: executáveis velhos e arquivos que o mod não usa mais."""
    _apagar(BASE_DIR, lambda n: n.endswith(".old") or n in ("HS3Companion_novo.exe", "ATUALIZAR.cmd"))
    copia = os.path.join(BASE_DIR, "HS3Discovery")   # cópia do mod que sobra ao extrair o zip à mão
    if os.path.isfile(os.path.join(copia, "Scripts", "main.lua")) and os.path.normcase(os.path.abspath(copia)) != os.path.normcase(os.path.abspath(pasta_mod or "")):
        shutil.rmtree(copia, ignore_errors=True)
    if pasta_mod and os.path.isdir(pasta_mod):
        # catálogo antigo (v1) e exportações feitas no acampamento (Hub não é reserva)
        _apagar(pasta_mod, lambda n: n == "catalogo.json" or "_L_Hub." in n or n.endswith(".tmp"))


def porta_em_uso(porta):
    import socket
    with socket.socket() as sk:
        return sk.connect_ex(("127.0.0.1", porta)) == 0

APP = None
ATUALIZADOR = None

TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
         ".json": "application/json", ".webmanifest": "application/manifest+json",
         ".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".woff2": "font/woff2"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, codigo, corpo, tipo="application/json", cache=False):
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    # --- acesso pelo celular: o próprio PC entra direto; outros aparelhos precisam do PIN
    def local(self):
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def liberado(self):
        if self.local():
            return True
        if not APP.cfg.get("celular"):
            return False
        pin = str(APP.cfg.get("pin") or "")
        cookies = dict(c.strip().split("=", 1) for c in (self.headers.get("Cookie") or "").split(";") if "=" in c)
        return bool(pin) and hmac.compare_digest(cookies.get("hs3pin", ""), pin)

    def porteiro(self):
        """True se pode seguir. Senão já respondeu (página do PIN, ou 403 para a API)."""
        if self.liberado():
            return True
        q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        tentado = (q.get("pin") or [""])[0]
        pin = str(APP.cfg.get("pin") or "")
        if APP.cfg.get("celular") and tentado and pin and hmac.compare_digest(tentado, pin):
            self.send_response(302)
            self.send_header("Set-Cookie", f"hs3pin={pin}; Path=/; Max-Age=31536000; SameSite=Lax")
            self.send_header("Location", "/")
            self.end_headers()
            return False
        if tentado:
            time.sleep(1.5)      # freia quem tenta adivinhar
        if self.path.startswith("/api/"):
            self.responder(403, {"erro": "PIN necessário"})
        elif not APP.cfg.get("celular"):
            self.responder(403, "Acesso pelo celular desligado no app do PC.".encode("utf-8"), "text/plain; charset=utf-8")
        else:
            erro = '<p class="erro">PIN errado. Confira no app do PC.</p>' if tentado else ""
            self.responder(200, PAGINA_PIN.replace("__ERRO__", erro).encode("utf-8"), "text/html; charset=utf-8")
        return False

    def arquivo_mod(self, nome, tipo):
        nivel = (APP.nivel() or "").replace("/", "")
        path = APP.caminho(nome.format(nivel=nivel))
        if not nivel or not os.path.isfile(path):
            return self.responder(404, {"erro": "não encontrado"})
        with open(path, "rb") as f:
            return self.responder(200, f.read(), tipo)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/ping":
            # o app Android procura o PC na rede por aqui (sem PIN: só diz que é o HS3 Companion)
            corpo = json.dumps({"app": "hs3companion", "versao": VERSAO, "celular": bool(APP.cfg.get("celular")),
                                "pc": socket.gethostname()}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if not self.porteiro():
            return
        caminho = self.path.split("?")[0]
        if caminho == "/api/celular":
            if not self.local():
                return self.responder(403, {"erro": "só no PC"})
            ip = ip_local()
            porta = APP.cfg["porta"]
            outros = [x for x in ips_locais() if x != ip]
            return self.responder(200, {"ligado": bool(APP.cfg.get("celular")), "ip": ip, "pin": APP.cfg.get("pin"),
                                        "outros": [f"http://{x}:{porta}" for x in outros],
                                        "endereco": f"http://{ip}:{porta}" if ip else None,
                                        "url_qr": f"http://{ip}:{porta}/?pin={APP.cfg.get('pin')}" if ip else None})
        if caminho == "/api/estado":
            return self.responder(200, APP.snapshot())
        if caminho == "/api/pois":
            with APP.lock:
                return self.responder(200, [{k: v for k, v in p.items() if not k.startswith("_")} for p in APP.pois()])
        if caminho == "/api/zonas":
            with APP.lock:
                return self.responder(200, APP.zonas())
        if caminho == "/api/mochila":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            ids = [x for x in (q.get("missoes", [""])[0]).split(",") if x]
            esp = [x for x in (q.get("especies", [""])[0]).split(",") if re.fullmatch(r"[\w.]+", x)]
            return self.responder(200, APP.dados_mochila(ids, esp))
        if caminho == "/api/loja":
            return self.responder(200, APP.dados_loja())
        if caminho == "/api/manejo_mapa":
            return self.responder(200, APP.mapa_manejo())
        if caminho == "/api/manejo":
            return self.responder(200, APP.dados_manejo())
        if caminho == "/api/instalacao":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            return self.responder(200, APP.info_instalacao((q.get("pasta") or [None])[0]))
        if caminho == "/api/compra":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            return self.responder(200, APP.resultado_compra((q.get("ref") or [""])[0]))
        if caminho == "/api/kit":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            tag = (q.get("tag") or [""])[0]
            return self.responder(200, APP.dados_kit(tag) if re.fullmatch(r"[\w.]+", tag or "") else {"pronto": False})
        if caminho == "/api/enciclopedia":
            return self.responder(200, APP.dados_enciclopedia())
        if caminho.startswith("/api/trofeu/"):
            nome = caminho.rsplit("/", 1)[1]
            path = os.path.join(Companion.PASTA_TROFEUS, nome)
            if not re.fullmatch(r"trofeu_[\d_]+\.jpg", nome) or not os.path.isfile(path):
                return self.responder(404, {"erro": "sem imagem"})
            with open(path, "rb") as f:
                return self.responder(200, f.read(), "image/jpeg", cache=True)
        if caminho == "/api/trofeus":
            with APP.lock:
                return self.responder(200, list(reversed(APP.dados.get("trofeus") or []))[:60])
        if caminho.startswith("/api/img/"):
            nome = caminho.rsplit("/", 1)[1]
            path = APP.caminho(os.path.join("img", nome))
            if not re.fullmatch(r"[\w\-]+\.png", nome) or not os.path.isfile(path):
                return self.responder(404, {"erro": "sem imagem"})
            if "p=1" in self.path:      # versão pequena e recortada (listas, mochila, celular)
                try:
                    path = imagens.icone(path, os.path.join(BASE_DIR, "cache", "img")) or path
                except Exception as e:
                    print("ícone leve falhou:", nome, repr(e))
            # revalida sempre (os ícones podem ser refeitos em alta resolução), mas sem baixar de novo se não mudou
            marca = str(int(os.path.getmtime(path)))
            if self.headers.get("If-None-Match") == marca:
                self.send_response(304)
                self.send_header("ETag", marca)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return
            with open(path, "rb") as f:
                corpo = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("ETag", marca)
            # versão pequena: o navegador guarda por 10 min (a mochila redesenha os ícones toda hora)
            self.send_header("Cache-Control", "max-age=600" if "p=1" in self.path else "no-cache")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if caminho == "/api/mapa.jpg":
            nivel = (APP.nivel() or "").replace("/", "")
            origem = APP.caminho(f"mapa_{nivel}.png")
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            try:
                lado = int((q.get("lado") or ["2048"])[0])
                jpg = imagens.mapa_jpeg(origem, os.path.join(BASE_DIR, "cache")) if lado <= 2048 else \
                    imagens.mapa_jpeg(origem, os.path.join(BASE_DIR, "cache"), lado=4096, qualidade=85)
            except Exception as e:
                print("mapa leve falhou:", repr(e))
                jpg = None
            if not jpg:
                return self.arquivo_mod("mapa_{nivel}.png", "image/png")
            with open(jpg, "rb") as f:
                return self.responder(200, f.read(), "image/jpeg", cache=True)
        if caminho == "/api/mapa.png":
            return self.arquivo_mod("mapa_{nivel}.png", "image/png")
        if caminho == "/api/nevoa.png":
            try:
                return self.responder(200, APP.nevoa_png(APP.nivel()), "image/png")
            except Exception:
                return self.responder(404, {"erro": "sem névoa"})
        if caminho == "/":
            caminho = "/index.html"
        arq = os.path.normpath(os.path.join(WEB_DIR, caminho.lstrip("/")))
        if not arq.startswith(os.path.normpath(WEB_DIR)) or not os.path.isfile(arq):
            return self.responder(404, {"erro": "não encontrado"})
        with open(arq, "rb") as f:
            ext = os.path.splitext(arq)[1]
            self.responder(200, f.read(), TIPOS.get(ext, "application/octet-stream"), cache=ext in (".png", ".jpg", ".woff2"))

    def do_POST(self):
        if not self.porteiro():
            return
        if self.path in ("/api/sair", "/api/instalacao", "/api/celular") and not self.local():
            return self.responder(403, {"ok": False, "erro": "Isso só pode ser feito no app do PC."})
        tam = int(self.headers.get("Content-Length") or 0)
        try:
            corpo = json.loads(self.rfile.read(tam) or b"{}")
        except Exception:
            corpo = {}
        p = self.path
        if p == "/api/sair":
            self.responder(200, {"ok": True})
            threading.Timer(0.5, lambda: os._exit(0)).start()
            return
        if p == "/api/celular":
            if corpo.get("acao") == "novo_pin":
                import secrets
                APP.cfg["pin"] = f"{secrets.randbelow(10000):04d}"
            elif "ligado" in corpo:
                APP.cfg["celular"] = bool(corpo["ligado"])
            salvar_json(CONFIG_PATH, APP.cfg)
            return self.responder(200, {"ok": True, "reiniciar": "ligado" in corpo})
        if p == "/api/atualizar":
            return self.responder(200, {"ok": ATUALIZADOR.atualizar()})
        if p == "/api/verificar":
            ATUALIZADOR.verificar()
            return self.responder(200, ATUALIZADOR.info())
        if p.startswith("/api/missoes/"):
            acao = p.rsplit("/", 1)[1]
            if acao == "gerar":
                APP.manter_ofertas()
                return self.responder(200, {"ok": True})
            return self.responder(200, APP.acao_missao(acao, corpo.get("id")))
        if p == "/api/pino":
            return self.responder(200, APP.pino(corpo.get("x"), corpo.get("y"), corpo.get("rotulo") or "Meu pino"))
        if p == "/api/tempo":
            with APP.lock:
                return self.responder(200, APP.passar_tempo(corpo.get("horas"), corpo.get("ate")))
        if p == "/api/pino/remover":
            with APP.lock:
                return self.responder(200, APP.remover_pino())
        if p == "/api/mochila":
            return self.responder(200, APP.acao_mochila(corpo))
        if p == "/api/nevoa":
            ok = APP.em_reserva() and APP.enviar_comando(["nevoa"])
            return self.responder(200, {"ok": bool(ok), "erro": None if ok else "Entre numa reserva no jogo primeiro."})
        if p == "/api/instalacao":
            return self.responder(200, APP.acao_instalacao(corpo))
        if p == "/api/mo_especies":
            lista = [str(x) for x in (corpo.get("lista") or []) if re.fullmatch(r"[\w.]+", str(x))][:40]
            with APP.lock:
                APP.dados["mo_especies"] = lista
                salvar_json(DADOS_PATH, APP.dados)
            return self.responder(200, {"ok": True})
        if p == "/api/setups":
            return self.responder(200, APP.setups(corpo))
        if p == "/api/barraca":
            with APP.lock:
                return self.responder(200, APP.acao_barraca(corpo))
        if p == "/api/carro":
            return self.responder(200, APP.trazer_carro(corpo))
        if p == "/api/ir":
            return self.responder(200, APP.ir_ate(corpo))
        if p == "/api/municao":
            return self.responder(200, APP.recarregar_municao())
        if p == "/api/licenca":
            return self.responder(200, APP.comprar_licenca(str(corpo.get("tag") or "")))
        if p == "/api/comprar":
            return self.responder(200, APP.comprar(corpo.get("id")))
        if p == "/api/voltar":
            return self.responder(200, APP.voltar_agora())
        if p == "/api/config":
            return self.responder(200, APP.configurar(corpo.get("chave"), corpo.get("valor")))
        if p == "/api/novidade_vista":
            with APP.lock:
                APP.dados["novidade_vista"] = str(corpo.get("id") or "")[:40]
                APP.salvar_pendente = True
            return self.responder(200, {"ok": True})
        if p == "/api/chat":
            return self.responder(200, APP.conversar(corpo.get("texto")))
        if p == "/api/exportar_dados":
            if not APP.em_reserva():
                return self.responder(200, {"ok": False, "erro": "Entre numa reserva no jogo primeiro."})
            return self.responder(200, {"ok": APP.enviar_comando(["exportar_dados"])})
        if p == "/api/exportar_mapa":
            return self.responder(200, {"ok": APP.enviar_comando(["export_map"])})
        self.responder(404, {"erro": "não encontrado"})


def main():
    global APP, ATUALIZADOR
    cfg = carregar_config()
    url = f"http://localhost:{cfg['porta']}"
    if "--aguardar-porta" in sys.argv:
        for _ in range(30):
            if not porta_em_uso(cfg["porta"]):
                break
            time.sleep(0.5)
    limpar_antigos()
    if porta_em_uso(cfg["porta"]):
        # já está rodando: só abre a janela de novo
        abrir_janela(url)
        return
    APP = Companion()
    limpar_antigos(APP.cfg.get("pasta_mod"))
    # mod no jogo de outra versão (ex.: copiado à mão de um pacote antigo): acerta com o que veio no programa
    try:
        w = instalador.win64_de(APP.cfg.get("pasta_mod"))
        if w and getattr(sys, "frozen", False) and not instalador.arquivos_mod_iguais(w):
            APP.ler_estado()
            if not APP.conectado():
                instalador.instalar(w)
                print("mod do jogo atualizado para a versão do programa")
    except Exception as e:
        print("não consegui conferir o mod:", repr(e))
    ATUALIZADOR = Atualizador(APP.cfg)
    threading.Thread(target=ATUALIZADOR.loop, daemon=True).start()
    porta = APP.cfg["porta"]
    print(f"HS3 Companion {VERSAO}")
    print(f"Pasta do mod: {APP.cfg['pasta_mod']}")
    if not os.path.isdir(APP.cfg["pasta_mod"] or ""):
        print("Mod ainda não instalado: abra o app e siga a tela Instalação.")
    threading.Thread(target=APP.loop, daemon=True).start()
    # "0.0.0.0" = também a rede de casa (celular, com PIN). Na primeira vez o Windows pergunta se libera: clique em Permitir.
    endereco = "0.0.0.0" if APP.cfg.get("celular") else "127.0.0.1"
    try:
        servidor = ThreadingHTTPServer((endereco, porta), Handler)
    except OSError:
        servidor = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    print(f"App aberto em {url}  (deixe esta janela aberta enquanto joga)")
    if APP.cfg.get("abrir_navegador") and "--sem-navegador" not in sys.argv:
        threading.Timer(1.0, lambda: abrir_janela(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
