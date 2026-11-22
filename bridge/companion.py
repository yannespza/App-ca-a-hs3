"""HS3 Companion - ponte entre o mod UE4SS do Hunting Simulator 3 e o app.

Lê state.json e events.jsonl gravados pelo mod, gera e valida missões,
paga recompensas escrevendo comandos em cmd.txt e serve o app em http://localhost.
Só usa a biblioteca padrão do Python.
"""
import json
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
import missoes
import mapa


# ------------------------------------------------------------------ caminhos
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    WEB_DIR = os.path.join(sys._MEIPASS, "web")  # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    WEB_DIR = os.path.join(BASE_DIR, "web")

if getattr(sys, "frozen", False) and (sys.stdout is None or sys.stderr is None):
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
    "pasta_mod": r"D:\SteamLibrary\steamapps\common\HS3\HS3\Binaries\Win64\ue4ss\Mods\HS3Discovery",
    "porta": 8765,
    "abrir_navegador": True,
    "missoes_ativas": 6,
    "ofertas": 8,
    "voltar_ao_ultimo_local": True,
    "contratos_no_jogo": True,
    "limite_diario_creditos": 20000,
    "github_token": "",
    "versao_config": 2,
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
    if salvo.get("versao_config", 1) < 2:
        # versões antigas gravaram 3 ofertas / 3 ativos: passa para os limites novos
        cfg["missoes_ativas"], cfg["ofertas"] = CONFIG_PADRAO["missoes_ativas"], CONFIG_PADRAO["ofertas"]
    if cfg != {k: v for k, v in salvo.items()}:
        salvar_json(CONFIG_PATH, cfg)
    return cfg


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


def avaliar_missoes(dados, evento):
    """Atualiza o progresso das missões ativas com um evento (abate confirmado, marcação ou posição)."""
    concluidas = []
    for m in dados["missoes"]:
        if m["status"] != "ativa" or evento.get("ts", 0) < m.get("aceita_em", m["criada"]) - 2:
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
                conta = m.get("dist_min", m.get("distancia", 0)) <= d <= m.get("dist_max", 500)
            elif t in ("calibre", "atrair", "nao_detectado") and (not m.get("grupo") or evento.get("grupo") == m["grupo"]):
                if t == "calibre":
                    conta = evento.get("calibre_compativel") is True
                elif t == "atrair":
                    conta = evento.get("atraido") is True
                else:
                    conta = evento.get("estado_animal") in ESTADOS_CALMOS
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
        for chave, padrao in (("missoes", []), ("abates", []), ("marcados", {}), ("grupos_vistos", []),
                              ("eventos_offset", 0), ("pagamentos_dia", {}), ("recompensas", []),
                              ("chat", []), ("pino_app", None), ("posicoes", {}), ("ultima_pos", {}),
                              ("especies_vistas", {}), ("compras", [])):
            d.setdefault(chave, padrao)
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

    # --- arquivos do mod
    def caminho(self, nome):
        return os.path.join(self.cfg["pasta_mod"], nome)

    def nivel(self):
        return self.estado.get("mapa")

    def ler_estado(self):
        try:
            with open(self.caminho("state.json"), "r", encoding="utf-8") as f:
                self.estado = json.load(f)
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
        return self._pois_cache[2]

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
            chave, nome = grupo_de(ev.get("especie"))
            ev.update({"grupo": chave, "grupo_nome": nome, "especie_nome": nome_especie(ev.get("especie")),
                       "sexo_nome": SEXO.get(ev.get("sexo"), "?"), "visto_em": time.time(), "reserva": self.nivel()})
            novo = str(ev.get("id")) not in d["marcados"]
            if novo and ev.get("especie"):
                d["especies_vistas"][ev["especie"]] = d["especies_vistas"].get(ev["especie"], 0) + 1
            d["marcados"][str(ev.get("id"))] = ev
            self.registrar_grupo(chave)
            if novo:
                return avaliar_missoes(d, {"tipo": "marcado", "id": ev.get("id"), "ts": time.time()})
        elif tipo in ("abate", "abate_final"):
            id_ = str(ev.get("id"))
            if any(str(a.get("id")) == id_ for a in d["abates"]):
                return []
            ab = dict(ev)
            marc = d["marcados"].get(id_)
            especie = (marc or {}).get("especie")
            chave, nome = grupo_de(especie or ab.get("classe"))
            ab.update({"grupo": chave, "grupo_nome": nome, "especie": especie,
                       "especie_nome": nome_especie(especie) or nome, "sexo_nome": (marc or {}).get("sexo_nome"),
                       "acao_nome": ACOES.get(ab.get("acao"), "Recolhido"), "ts": time.time(), "reserva": self.nivel()})
            self.registrar_grupo(chave)
            d["abates"].append(ab)
            d["marcados"].pop(id_, None)
            d["posicoes"].pop(id_, None)
            return avaliar_missoes(d, dict(ab, tipo="abate_confirmado"))
        elif tipo == "compra":
            d["compras"] = (d["compras"] + [ev])[-50:]
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
                        linhas.append(f"add_rep {m['reputacao']} {m['id']}")
                    if linhas and self.enviar_comando(linhas):
                        m["enviado"] = agora
                continue
            pago_hoje = dia.get(hoje, 0)
            cred = min(m["creditos"], max(0, self.cfg["limite_diario_creditos"] - pago_hoje))
            linhas = [f"add_credits {cred} {m['id']}"] if cred > 0 else []
            if cred <= 0:
                m.setdefault("pago", {})["creditos"] = True
            linhas.append(f"add_rep {m['reputacao']} {m['id']}")
            self.enviar_comando(linhas)
            dia[hoje] = pago_hoje + cred
            m["enviado"] = time.time()
            m["creditos_pagos"] = cred
            if self.dados.get("pino_app") and self.dados["pino_app"].get("missao") == m["id"]:
                self.remover_pino()

    # --- missões
    def por_status(self, *status):
        return [m for m in self.dados["missoes"] if m["status"] in status]

    def manter_ofertas(self):
        if self.gerando or not self.nivel():
            return
        faltam = self.cfg["ofertas"] - len(self.por_status("oferta"))
        if faltam <= 0:
            return
        self.gerando = True
        threading.Thread(target=self._gerar_ofertas, args=(faltam,), daemon=True).start()

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
        comprados = {b["id"] for b in self.equipamento().get("comprados", [])}
        tipos = set()
        for i in dados.get("itens", []):
            if (i.get("tipo") or "").startswith("Inventory.Weapon"):
                t = missoes._arma_tipo(i["tipo"])
                ARMA_TIPOS[(i.get("item") or "").split(":")[-1]] = t
                if i["id"] in comprados or i.get("padrao"):
                    tipos.add(t)
        return grupos, sorted(tipos) or ["rifle"]

    def _gerar_ofertas(self, n):
        try:
            grupos, armas = self.info_gerador()
            with self.lock:
                novas = missoes.gerar(self.dados, self.pois(), nome_grupo, grupos, armas, n)
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
            if acao == "aceitar" and m["status"] == "oferta":
                if len(self.por_status("ativa")) >= self.cfg["missoes_ativas"]:
                    return {"ok": False, "erro": f"Você já tem {self.cfg['missoes_ativas']} contratos ativos. Abandone um antes."}
                m["status"], m["aceita_em"] = "ativa", time.time()
                if m.get("local"):
                    self._pino(m["local"], m["titulo"], m["id"])
            elif acao == "recusar" and m["status"] == "oferta":
                m["status"] = "recusada"
            elif acao == "abandonar" and m["status"] == "ativa":
                m["status"] = "abandonada"
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
        self.dados["pino_app"] = {"x": pos["x"], "y": pos["y"], "z": pos.get("z", 0), "rotulo": rotulo,
                                  "missao": missao, "ts": time.time()}
        self.enviar_comando([f"pin {pos['x']:.0f} {pos['y']:.0f} {pos.get('z', 0):.0f}"])
        self.salvar_pendente = True

    def pino(self, x, y, rotulo="Meu pino"):
        with self.lock:
            z = (self.estado.get("pos") or {}).get("z", 0)
            self._pino({"x": float(x), "y": float(y), "z": z}, rotulo)
        return {"ok": True}

    def remover_pino(self):
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
    def cuidar_posicao(self):
        nivel = self.nivel() if self.em_reserva() else None
        agora = time.time()
        if nivel and nivel != self.estava_em and "Hub" not in nivel:
            destino = self.dados["ultima_pos"].get(nivel)
            self.anterior = destino if destino and (distancia_m(self.estado["pos"], destino) or 0) > 150 else None
            if self.cfg.get("voltar_ao_ultimo_local") and destino and (distancia_m(self.estado["pos"], destino) or 0) > 150:
                self.teleporte = (destino, agora + 6)
                self.aviso_teleporte = "Voltando ao último local em instantes…"
        self.estava_em = nivel
        if self.teleporte:
            destino, hora = self.teleporte
            if agora >= hora:
                self.enviar_comando([f"teleport {destino['x']:.0f} {destino['y']:.0f} {destino['z']:.0f}"])
                self.teleporte = None
                self.aviso_teleporte = None
                self.pausa_pos_ate = agora + 8
            return
        if nivel and "Hub" not in nivel and agora >= getattr(self, "pausa_pos_ate", 0):
            p = self.estado["pos"]
            self.dados["ultima_pos"][nivel] = {"x": p["x"], "y": p["y"], "z": p["z"], "ts": agora}

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
        return self.cache.json(self.caminho("calibres.json"), [])

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
                          "tipo": tipo, "grupo": grupo, "dist_min": int(dist.group(1)) if tipo == "distancia" else 0,
                          "dist_max": 9999 if tipo == "distancia" else 0})
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
            faltam = nas - set(mun)
            velho = agora - (armas.get("ts") or 0) > 300
            if self.em_reserva() and (faltam or velho) and agora - getattr(self, "_armas_pedidas", 0) > 30:
                self._armas_pedidas = agora
                self.enviar_comando(["mochila armas"])
        return lida

    def dados_kit(self, tag):
        dados = self.cache.json(self.caminho("jogo_dados.json"), None)
        if not dados:
            return {"pronto": False}
        lida = self._lida_mochila()
        with self.lock:
            r = extras.kit_especie(dados, self.tabela_calibres(), self.equipamento(), lida, tag, nome_especie)
        r["pronto"] = True
        r["em_reserva"] = self.em_reserva()
        r["fila"] = getattr(self, "_mochila_fila_ate", 0) > time.time()
        r["sugestao"] = extras.sugestao_kit(r)
        return r

    def dados_mochila(self, ids=None):
        agora = time.time()
        dados = self.cache.json(self.caminho("jogo_dados.json"), None)
        lida = self._lida_mochila()
        do_jogo = self.contratos_jogo()
        with self.lock:
            ativas = self.por_status("ativa") + do_jogo
            escolhidas = [m for m in ativas if not ids or m["id"] in ids]
            if not dados:
                return {"pronto": False}
            r = extras.mochila(dados, self.tabela_calibres(), self.equipamento(), lida, escolhidas,
                               nome_especie, grupo_de, nome_grupo)
            r["pronto"] = True
            r["ativas"] = [{"id": m["id"], "titulo": m["titulo"], "escolhida": m in escolhidas, "do_jogo": bool(m.get("do_jogo")),
                            "vendedor": m.get("vendedor")} for m in ativas]
            r["em_reserva"] = self.em_reserva()
            r["no_jogo"] = r["em_reserva"]
            r["lida_idade"] = round(agora - lida["ts"]) if lida and lida.get("ts") else None
            r["fila"] = getattr(self, "_mochila_fila_ate", 0) > agora
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
            plano = self.dados_mochila(ids).get("plano") or []
            for t in plano:
                if t["acao"] == "por" and ok_id(t["item"]):
                    linhas.append(f"mochila por {t['item']} {t['tipo']} {int(t['idx'])}")
                elif t["acao"] == "municao" and ok_id(t["arma"]) and ok_id(t["municao"]):
                    linhas.append(f"mochila municao {t['arma']} {t['municao']}")
            if not linhas:
                return {"ok": True, "nada": True}
        else:
            return {"ok": False, "erro": "Ação inválida."}
        if not self.enviar_comando(linhas):
            return {"ok": False, "erro": "O jogo não está respondendo."}
        # o mod faz uma troca por segundo e depois salva e relê
        self._mochila_fila_ate = time.time() + len(linhas) + 3
        self._mochila_pedida = time.time() + len(linhas)
        return {"ok": True, "trocas": len(linhas), "segundos": len(linhas) + 2}

    def dados_loja(self):
        with self.lock:
            r = extras.loja(self.catalogo(), self.equipamento())
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
            self.enviar_comando([f"comprar {id_} {uuid.uuid4().hex[:6]}"])
        return {"ok": True}

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
        if self.cfg.get("contratos_no_jogo", True):
            agora = time.time()
            for m in self.dados["missoes"]:
                recente = m["status"] in ("concluida", "paga") and agora - (m.get("concluida_em") or m.get("pago_em") or 0) < 120
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
            self.ler_animais()
            mudou = False
            for ev in self.ler_eventos():
                self.processar(ev)
                mudou = True
            self.cuidar_posicao()
            if self.em_reserva():
                if avaliar_missoes(self.dados, {"tipo": "posicao", "id": "local", "pos": self.estado["pos"], "ts": time.time()}):
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
            time.sleep(1)

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
            rastreados.sort(key=lambda x: x["distancia_m"] if x["distancia_m"] is not None else 1e9)
            rep = next((r for r in st.get("reputacao", []) or [] if self.nivel() and self.nivel() in (r.get("mapa") or "")), None)
            lista = self.dados["missoes"]
            return {
                "versao": VERSAO,
                "atualizacao": ATUALIZADOR.info() if ATUALIZADOR else None,
                "conectado": self.conectado(),
                "em_reserva": self.em_reserva(),
                "estado": st,
                "reputacao_mapa_atual": rep,
                "mapa": self.info_mapa(),
                "pino_app": self.dados.get("pino_app"),
                "rastreados": rastreados,
                "ofertas": [m for m in lista if m["status"] == "oferta"],
                "ativas": [m for m in lista if m["status"] == "ativa"],
                "contratos_jogo": self.contratos_jogo(),
                "finalizadas": [m for m in lista if m["status"] in ("concluida", "paga")][-8:][::-1],
                "gerando": self.gerando,
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
                "pasta_mod_existe": os.path.isdir(self.cfg["pasta_mod"]),
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

    def arquivo_mod(self, nome, tipo):
        nivel = (APP.nivel() or "").replace("/", "")
        path = APP.caminho(nome.format(nivel=nivel))
        if not nivel or not os.path.isfile(path):
            return self.responder(404, {"erro": "não encontrado"})
        with open(path, "rb") as f:
            return self.responder(200, f.read(), tipo)

    def do_GET(self):
        caminho = self.path.split("?")[0]
        if caminho == "/api/estado":
            return self.responder(200, APP.snapshot())
        if caminho == "/api/pois":
            with APP.lock:
                return self.responder(200, [{k: v for k, v in p.items() if not k.startswith("_")} for p in APP.pois()])
        if caminho == "/api/mochila":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            ids = [x for x in (q.get("missoes", [""])[0]).split(",") if x]
            return self.responder(200, APP.dados_mochila(ids))
        if caminho == "/api/loja":
            return self.responder(200, APP.dados_loja())
        if caminho == "/api/kit":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            tag = (q.get("tag") or [""])[0]
            return self.responder(200, APP.dados_kit(tag) if re.fullmatch(r"[\w.]+", tag or "") else {"pronto": False})
        if caminho == "/api/enciclopedia":
            return self.responder(200, APP.dados_enciclopedia())
        if caminho.startswith("/api/img/"):
            nome = caminho.rsplit("/", 1)[1]
            path = APP.caminho(os.path.join("img", nome))
            if not re.fullmatch(r"[\w\-]+\.png", nome) or not os.path.isfile(path):
                return self.responder(404, {"erro": "sem imagem"})
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
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
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
        if p == "/api/pino/remover":
            with APP.lock:
                return self.responder(200, APP.remover_pino())
        if p == "/api/mochila":
            return self.responder(200, APP.acao_mochila(corpo))
        if p == "/api/comprar":
            return self.responder(200, APP.comprar(corpo.get("id")))
        if p == "/api/voltar":
            return self.responder(200, APP.voltar_agora())
        if p == "/api/config":
            return self.responder(200, APP.configurar(corpo.get("chave"), corpo.get("valor")))
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
    ATUALIZADOR = Atualizador(APP.cfg)
    threading.Thread(target=ATUALIZADOR.loop, daemon=True).start()
    porta = APP.cfg["porta"]
    print(f"HS3 Companion {VERSAO}")
    print(f"Pasta do mod: {APP.cfg['pasta_mod']}")
    if not os.path.isdir(APP.cfg["pasta_mod"]):
        print("ATENÇÃO: pasta do mod não encontrada. Ajuste 'pasta_mod' em", CONFIG_PATH)
    threading.Thread(target=APP.loop, daemon=True).start()
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
