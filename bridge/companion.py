"""HS3 Companion - ponte entre o mod UE4SS do Hunting Simulator 3 e o app.

Lê state.json e events.jsonl gravados pelo mod, gera e valida missões,
paga recompensas escrevendo comandos em cmd.txt e serve o app em http://localhost.
Só usa a biblioteca padrão do Python.
"""
import json
import re
import math
import os
import random
import sys
import threading
import time
import uuid
import webbrowser
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import extras
import ia
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
    "missoes_ativas": 3,
    "ofertas": 3,
    "ollama_url": "http://localhost:11434",
    "ollama_modelo": "",
    "ollama_usar_gpu": False,
    "voltar_ao_ultimo_local": True,
    "limite_diario_creditos": 20000,
    "github_token": "",
}

# ------------------------------------------------------------------ catálogo
GRUPOS = [
    # (chave, nome em português, palavras que identificam no tag/classe)
    ("pato", "Pato / marreca", ["duck", "mallard", "pintail", "bufflehead", "teal", "wigeon", "canvasback"]),
    ("ganso", "Ganso", ["goose"]),
    ("peru", "Peru-selvagem", ["turkey"]),
    ("faisao", "Faisão / perdiz", ["pheasant", "chukar"]),
    ("codorna", "Codorna", ["quail"]),
    ("pomba", "Pomba", ["dove", "pigeon"]),
    ("antilope", "Antílope", ["antelope", "nilgai", "oryx"]),
    ("felino", "Felino", ["feline", "bobcat", "cougar", "puma", "lion"]),
    ("roedor", "Cão-da-pradaria", ["prairiedog"]),
    ("cervo", "Cervo", ["deer", "cervidae"]),
    ("alce", "Wapiti / Alce", ["elk", "moose", "wapiti"]),
    ("antilocapra", "Antilocapra", ["pronghorn"]),
    ("porco", "Porco-do-mato", ["hog", "boar", "pig", "suidae", "javelina", "peccary"]),
    ("coiote", "Coiote", ["coyote"]),
    ("lobo", "Lobo", ["wolf"]),
    ("raposa", "Raposa", ["fox"]),
    ("coelho", "Coelho / Lebre", ["rabbit", "hare", "jackrabbit", "cottontail"]),
    ("urso", "Urso", ["bear"]),
    ("carneiro", "Carneiro / Cabra", ["sheep", "bighorn", "goat", "ram"]),
    ("bisao", "Bisão", ["bison", "buffalo"]),
]


def grupo_de(texto):
    t = (texto or "").lower().replace("_", "")
    for chave, nome, palavras in GRUPOS:
        if any(p in t for p in palavras):
            return chave, nome
    return "outro", "Outro animal"


NOMES_PT = {
    "Antelope.Nilgai": "Nilgai", "Antelope.ScimitarOryx": "Órix-de-cimitarra", "Bear.Black": "Urso-negro",
    "Bird.Chukar": "Perdiz-chukar", "Bird.Dove.Mourning": "Rolinha-carpideira", "Bird.Duck.Black": "Pato-negro-americano",
    "Bird.Duck.Bufflehead": "Pato-de-cabeça-branca", "Bird.Duck.NorthernPintail": "Arrabio", "Bird.Goose.Canada": "Ganso-do-canadá",
    "Bird.MontezumaQuail": "Codorna-de-montezuma", "Bird.Pheasant": "Faisão", "Bird.Quail": "Codorna",
    "Bird.Teal.GreenWinged": "Marreca-de-asa-verde", "Bird.Turkey.RioGrande": "Peru-selvagem Rio Grande",
    "Bison.American": "Bisão-americano", "Canine.Coyote": "Coiote", "Deer.DesertMule": "Cervo-mula do deserto",
    "Deer.MountainMule": "Cervo-mula da montanha", "Deer.WhiteTail": "Cervo-de-cauda-branca", "Elk": "Wapiti",
    "Feline.Bobcat": "Lince-pardo", "Feline.Cougar": "Puma", "Fox.Red": "Raposa-vermelha", "Hare.JackRabbit": "Lebre jackrabbit",
    "Peccary.Collared": "Cateto", "Pig.Feral": "Porco-selvagem", "PrairieDog.BlackTail": "Cão-da-pradaria",
    "Pronghorn.American": "Antilocapra", "Rabbit.CottonTail": "Coelho-cottontail", "Sheep.Aoudad": "Carneiro-da-barbária",
    "Sheep.Bighorn": "Carneiro-selvagem", "Wolf.Gray": "Lobo-cinzento",
}


def nome_especie(tag):
    """Nome em português da espécie a partir da tag do jogo (Animals.Types.Deer.WhiteTail.Texas -> Cervo-de-cauda-branca)."""
    if not tag:
        return None
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
RESULTADO_OK = {0, 1, 2, 3}
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
    cfg.update(carregar_json(CONFIG_PATH, {}))
    if not os.path.exists(CONFIG_PATH):
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
TEMPLATE_FALAS = {
    "abater_grupo": "Tem um fazendeiro reclamando de {grupo} na propriedade dele. Resolve isso pra mim, mas com tiro limpo.",
    "abater_qualquer": "A câmara fria do posto está vazia, parceiro. Traz carne boa, de preferência sem estragar com tiro ruim.",
    "distancia": "Quero ver essa pontaria. Tiro longo exige paciência: confira o vento e respire antes de apertar o gatilho.",
    "genetica": "Um colecionador quer um troféu de qualidade. Use o binóculo e não atire no primeiro que aparecer.",
    "sem_torre": "Torre é bom, mas caçador de verdade sabe andar pé-ante-pé. Contra o vento, devagar.",
    "marcar": "Preciso de um censo da fauna. Marca os bichos no binóculo e me conta o que viu.",
    "visitar": "Tem um lugar que ninguém do posto foi conferir ainda. Dá uma passada lá e me diz como está.",
    "calibre": "Nada de ferir bicho com arma errada. Leve o calibre certo para a espécie e faça um abate limpo.",
    "atrair": "Bicho que vem até você é bicho que não te viu. Use o chamariz ou o atrativo de cheiro e espere.",
    "nao_detectado": "Quero um abate em que o animal nem saiba que você estava lá. Vento no rosto e paciência.",
}

FAIXAS_DISTANCIA = {"curta": (25, 50), "media": (100, 200), "longa": (300, 500)}
ESTADOS_CALMOS = {1, 2, 4, 256, 512}   # parado, vagando, andando, comendo, dormindo


def nome_grupo(chave):
    return dict((g[0], g[1]) for g in GRUPOS).get(chave, chave)


def normalizar_missao(m, dados, pois):
    """Valida/ajusta uma missão (vinda da IA ou do gerador) e devolve None se for inválida."""
    tipo = m.get("tipo")
    if tipo not in ("abater_grupo", "abater_qualquer", "distancia", "genetica", "sem_torre", "marcar", "visitar",
                    "calibre", "atrair", "nao_detectado"):
        return None
    vistos = set(dados.get("grupos_vistos", [])) - {"outro"}
    saida = {"tipo": tipo, "titulo": str(m.get("titulo") or "Contrato")[:60],
             "fala": str(m.get("fala") or TEMPLATE_FALAS[tipo]).strip()[:500]}
    if tipo == "abater_grupo":
        if m.get("grupo") not in vistos:
            return None
        saida["grupo"] = m["grupo"]
        saida["meta"] = max(1, min(5, int(m.get("meta") or 1)))
        saida["descricao"] = f"Abata e recolha {saida['meta']} {nome_grupo(saida['grupo']).lower()}(s)."
    elif tipo == "abater_qualquer":
        saida["meta"] = max(1, min(6, int(m.get("meta") or 2)))
        saida["descricao"] = f"Abata e recolha {saida['meta']} animais de qualquer espécie."
    elif tipo == "distancia":
        faixa = str(m.get("faixa") or "").lower().replace("é", "e")
        d = int(float(m.get("distancia") or 0))
        if faixa not in FAIXAS_DISTANCIA:
            faixa = "curta" if 0 < d <= 60 else ("longa" if d >= 300 else "media")
        if faixa == "longa":
            d = max(300, min(480, d or 300))
            saida["dist_min"], saida["dist_max"] = d, 500
            saida["descricao"] = f"Tiro longo: abata um animal a {d} m ou mais (limite do jogo: 500 m)."
        else:
            saida["dist_min"], saida["dist_max"] = FAIXAS_DISTANCIA[faixa]
            nome = "curta" if faixa == "curta" else "média"
            saida["descricao"] = f"Distância {nome}: abata um animal entre {saida['dist_min']} e {saida['dist_max']} m."
        saida["faixa"], saida["distancia"], saida["meta"] = faixa, saida["dist_min"], 1
    elif tipo == "genetica":
        g = float(m.get("genetica") or 0.6)
        saida["genetica"] = round(max(0.3, min(0.9, g if g <= 1 else g / 100)), 2)
        saida["meta"] = 1
        saida["descricao"] = f"Abata um animal com genética de {int(saida['genetica'] * 100)}% ou mais."
    elif tipo == "sem_torre":
        saida["meta"] = 1
        saida["descricao"] = "Abata um animal sem estar numa torre ou espera."
    elif tipo == "marcar":
        saida["meta"] = max(2, min(12, int(m.get("meta") or 5)))
        saida["descricao"] = f"Marque {saida['meta']} animais diferentes com o binóculo."
    elif tipo == "visitar":
        saida["meta"] = 1
        saida["descricao"] = "Vá até o local marcado no mapa."
    elif tipo in ("calibre", "atrair", "nao_detectado"):
        g = m.get("grupo") if m.get("grupo") in vistos else None
        if g:
            saida["grupo"] = g
        saida["meta"] = max(1, min(3, int(m.get("meta") or 1)))
        alvo = f"{saida['meta']} {nome_grupo(g).lower()}(s)" if g else (f"{saida['meta']} animais" if saida["meta"] > 1 else "um animal")
        saida["descricao"] = {
            "calibre": f"Abata {alvo} usando munição de calibre compatível com a espécie.",
            "atrair": f"Abata {alvo} atraído por chamariz ou atrativo de cheiro.",
            "nao_detectado": f"Abata {alvo} sem que ele perceba você (animal calmo no momento do tiro).",
        }[tipo]
    poi = next((p for p in pois if str(p.get("hash")) == str(m.get("poi_hash"))), None)
    if tipo == "visitar" and not poi:
        return None
    if poi:
        saida["local"] = {"x": poi["x"], "y": poi["y"], "z": poi.get("z", 0), "nome": poi["nome"], "hash": poi["hash"]}
        if tipo == "visitar":
            saida["descricao"] = f"Vá até: {poi['nome']}."
    saida["creditos"] = max(200, min(4000, int(m.get("creditos") or 600)))
    saida["reputacao"] = max(5, min(100, int(m.get("reputacao") or 20)))
    saida.update({"id": uuid.uuid4().hex[:8], "status": "oferta", "progresso": 0, "contados": [],
                  "criada": time.time(), "origem": m.get("origem", "ia")})
    return saida


def gerar_missao_local(dados, pois):
    """Gerador simples (quando o Ollama não está disponível)."""
    vistos = list(set(dados.get("grupos_vistos", [])) - {"outro"})
    nao_desc = [p for p in pois if not p.get("descoberto") and p.get("categoria") in ("lugar", "torre", "acampamento")]
    opcoes = [
        {"tipo": "abater_qualquer", "titulo": "Carne para o posto", "meta": random.choice([2, 3])},
        {"tipo": "distancia", "titulo": "Tiro de perto", "faixa": "curta"},
        {"tipo": "distancia", "titulo": "Olho de lince", "faixa": "media"},
        {"tipo": "distancia", "titulo": "Tiro de elite", "faixa": "longa", "distancia": random.choice([300, 350, 400, 450, 500])},
        {"tipo": "calibre", "titulo": "Arma certa, abate limpo"},
        {"tipo": "atrair", "titulo": "Chamando o bicho"},
        {"tipo": "nao_detectado", "titulo": "Fantasma do mato"},
        {"tipo": "genetica", "titulo": "Troféu de colecionador", "genetica": random.choice([0.55, 0.6, 0.7])},
        {"tipo": "sem_torre", "titulo": "Pé-ante-pé"},
        {"tipo": "marcar", "titulo": "Censo da fauna", "meta": random.choice([4, 6, 8])},
    ]
    if vistos:
        g = random.choice(vistos)
        opcoes.append({"tipo": "abater_grupo", "titulo": f"Praga de {nome_grupo(g).lower()}", "grupo": g,
                       "meta": random.choice([1, 2, 3])})
    if nao_desc:
        p = random.choice(nao_desc)
        opcoes.append({"tipo": "visitar", "titulo": f"Conferir {p['nome'].lower()}", "poi_hash": p["hash"]})
    m = random.choice(opcoes)
    dif = {"abater_qualquer": 350 * m.get("meta", 1),
           "distancia": {"curta": 500, "media": 900}.get(m.get("faixa"), 1200 + 4 * (m.get("distancia", 300) - 300)),
           "calibre": 600, "atrair": 900, "nao_detectado": 1100,
           "genetica": int(3000 * m.get("genetica", 0)), "sem_torre": 700, "marcar": 120 * m.get("meta", 1),
           "abater_grupo": 450 * m.get("meta", 1), "visitar": 600}[m["tipo"]]
    m.update({"creditos": dif, "reputacao": max(10, dif // 30), "origem": "local"})
    if m["tipo"] == "abater_grupo":
        m["fala"] = TEMPLATE_FALAS["abater_grupo"].format(grupo=nome_grupo(m["grupo"]).lower())
    return normalizar_missao(m, dados, pois)


def dentro(pos, local, raio_m=60):
    d = distancia_m(pos, local)
    return d is not None and d <= raio_m


def avaliar_missoes(dados, evento):
    """Atualiza o progresso das missões ativas com um evento (abate confirmado, marcação ou posição)."""
    concluidas = []
    for m in dados["missoes"]:
        if m["status"] != "ativa" or evento.get("ts", 0) < m.get("aceita_em", m["criada"]) - 2:
            continue
        chave = f"{evento['tipo']}:{evento.get('id')}"
        if chave in m["contados"]:
            continue
        conta = False
        t = m["tipo"]
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
        return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60)

    def _ultima_pelo_site(self):
        """Plano B sem a API: github.com/<repo>/releases/latest redireciona para a tag mais nova."""
        class SemRedirecionar(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        abridor = urllib.request.build_opener(SemRedirecionar)
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
                motivo = getattr(e2, "reason", None) or getattr(e1, "reason", None) or e2
                self.erro = f"Sem conexão com o GitHub: {motivo}"
                print("atualização:", repr(e1), repr(e2))
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
            with self._req(url, accept="application/octet-stream") as r, open(zip_path, "wb") as f:
                shutil.copyfileobj(r, f)
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
            m.setdefault("fala", TEMPLATE_FALAS.get(m.get("tipo"), ""))
        self.ollama = ia.Ollama(self.cfg)
        self.gerando = False
        self.respondendo = False
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

    def calibres(self):
        """Tabela oficial do jogo: calibres compatíveis por espécie (só das espécies já vistas, para não pesar)."""
        tabela = carregar_json(self.caminho("calibres.json"), [])
        vistas = {m.get("especie") for m in self.dados["marcados"].values()} | {a.get("especie") for a in self.dados["abates"]}
        vistas.discard(None)
        saida = {}
        for linha in tabela:
            animal = linha.get("animal", "")
            if not vistas or any(animal and (animal in v or v in animal) for v in vistas):
                saida[nome_especie(animal) or animal] = {"compativeis": [c.split(".")[-1] for c in linha.get("compativeis", [])],
                                                         "incompativeis": [c.split(".")[-1] for c in linha.get("incompativeis", [])]}
        return dict(list(saida.items())[:12])

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
        with open(self.caminho("cmd.txt"), "a", encoding="utf-8") as f:
            for l in linhas:
                f.write(l + "\n")

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
                        m["status"] = "paga"
        return []

    def pagar_pendentes(self):
        if not self.em_reserva():
            return
        hoje = date.today().isoformat()
        dia = self.dados["pagamentos_dia"]
        for m in self.dados["missoes"]:
            if m["status"] != "concluida" or m.get("enviado"):
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

    def contexto(self, curto=False):
        st = self.estado
        pos = st.get("pos")
        rep = next((r for r in st.get("reputacao", []) or [] if self.nivel() and self.nivel() in (r.get("mapa") or "")), None)
        pois = self.pois()
        for p in pois:
            p["_d"] = distancia_m(pos, p) or 0
        nao_desc = sorted((p for p in pois if not p["descoberto"]), key=lambda p: p["_d"])[:12]
        desc = sorted((p for p in pois if p["descoberto"] and p["categoria"] in ("lugar", "torre", "acampamento")),
                      key=lambda p: p["_d"])[:8]
        ctx = {
            "reserva": "Texas" if "Texas" in (self.nivel() or "") else ("Colorado" if "Colorado" in (self.nivel() or "") else self.nivel()),
            "creditos": (st.get("moedas") or {}).get("Currency.Credits"),
            "reputacao": rep and rep.get("valor"),
            "grupos_disponiveis": {g: nome_grupo(g) for g in self.dados["grupos_vistos"] if g != "outro"},
            "animais_marcados_recentes": [
                {"especie": m.get("especie_nome"), "grupo": m.get("grupo"), "sexo": m.get("sexo_nome"),
                 "genetica": round(m.get("genetica") or 0, 2)} for m in list(self.dados["marcados"].values())[-8:]],
            "ultimos_abates": [{"especie": a.get("especie_nome"), "distancia_m": round(a.get("distancia_m") or 0),
                                "arma": a.get("arma"), "municao": a.get("municao")} for a in self.dados["abates"][-5:]],
            "missoes_ativas": [m["titulo"] for m in self.por_status("ativa")],
            "municoes_usadas": sorted({f"{a.get('municao')} ({a.get('calibre')})" for a in self.dados["abates"][-20:] if a.get("municao")}),
        }
        cal = self.calibres()
        if cal:
            ctx["calibres_por_especie"] = cal
        try:
            arm = extras.armario(self.catalogo(), self.equipamento(), self.tabela_calibres(), nome_especie, self.dados["abates"])
            ctx["mochila_atual"] = [f"{i['nome']}" + (f" ({i['calibre']})" if i.get("calibre") else "") for i in arm["mochila"]]
            lj = extras.loja(self.catalogo(), self.equipamento())
            ctx["roupa_atual"] = [f"{i['nome']} (camuflagem {i['camuflagem']}/100)" for i in lj["vestidos"]]
            if lj.get("deteccao"):
                ctx["percepcao_dos_animais_agora"] = {k: f"{round(v * 100)}%" for k, v in lj["deteccao"].items() if k != "na_estrutura"}
        except Exception:
            pass
        if not curto:
            ctx["pontos_nao_descobertos"] = [{"hash": p["hash"], "nome": p["nome"], "distancia_m": round(p["_d"])} for p in nao_desc]
            ctx["pontos_descobertos_proximos"] = [{"hash": p["hash"], "nome": p["nome"], "distancia_m": round(p["_d"])} for p in desc]
        return ctx

    def _gerar_ofertas(self, n):
        try:
            novas = []
            if self.ollama.verificar():
                try:
                    with self.lock:
                        ctx = self.contexto()
                    for m in ia.gerar_missoes(self.ollama, ctx, n):
                        with self.lock:
                            nm = normalizar_missao(dict(m, origem="ia"), self.dados, self.pois())
                        if nm:
                            novas.append(nm)
                except Exception as e:
                    print("IA falhou ao gerar missões:", e)
            while len(novas) < n:
                with self.lock:
                    nm = gerar_missao_local(self.dados, self.pois())
                if nm:
                    novas.append(nm)
            with self.lock:
                self.dados["missoes"].extend(novas[:n])
                self.salvar_pendente = True
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

    # --- chat com o NPC
    def conversar(self, texto):
        texto = (texto or "").strip()[:800]
        if not texto:
            return {"ok": False}
        with self.lock:
            self.dados["chat"].append({"role": "user", "content": texto, "ts": time.time()})
            historico = [{"role": c["role"], "content": c["content"]} for c in self.dados["chat"][-12:-1]]
            ctx = self.contexto(curto=True)
        self.respondendo = True
        try:
            resposta = ia.conversar(self.ollama, historico, texto, ctx)
        except Exception:
            resposta = ("(O Velho Earl está sem rádio agora: abra o Ollama no seu PC para ele responder.) "
                        "Enquanto isso, lembre: contra o vento, devagar, e tiro só com o bicho de lado.")
        finally:
            self.respondendo = False
        with self.lock:
            self.dados["chat"] = (self.dados["chat"] + [{"role": "assistant", "content": resposta, "ts": time.time()}])[-40:]
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
        if chave in ("voltar_ao_ultimo_local", "ollama_usar_gpu"):
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

    def dados_armario(self):
        with self.lock:
            return extras.armario(self.catalogo(), self.equipamento(), self.tabela_calibres(), nome_especie, self.dados["abates"])

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
            return {"pronto": False, "fichas": extras.enciclopedia(self.tabela_calibres(), self.dados["abates"], self.dados["especies_vistas"],
                                       nome_especie, grupo_de)}

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
    def ciclo(self):
        with self.lock:
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
            missoes = self.dados["missoes"]
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
                "ofertas": [m for m in missoes if m["status"] == "oferta"],
                "ativas": [m for m in missoes if m["status"] == "ativa"],
                "finalizadas": [m for m in missoes if m["status"] in ("concluida", "paga")][-8:][::-1],
                "gerando": self.gerando,
                "abates": self.dados["abates"][-30:][::-1],
                "estatisticas": self.estatisticas(),
                "npc": ia.NPC,
                "patente": extras.patente(self.dados["abates"], missoes),
                "aviso_teleporte": self.aviso_teleporte,
                "config": {"voltar_ao_ultimo_local": self.cfg.get("voltar_ao_ultimo_local"),
                           "ollama_usar_gpu": self.cfg.get("ollama_usar_gpu")},
                "tem_local_salvo": bool(getattr(self, "anterior", None)),
                "ollama": self.ollama.status(),
                "chat": [{"role": c["role"], "content": c["content"]} for c in self.dados["chat"][-20:]],
                "respondendo": self.respondendo,
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


def limpar_antigos():
    try:
        for nome in os.listdir(BASE_DIR):
            if nome.endswith(".old"):
                try:
                    os.remove(os.path.join(BASE_DIR, nome))
                except OSError:
                    pass
    except OSError:
        pass


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
        if caminho == "/api/armario":
            return self.responder(200, APP.dados_armario())
        if caminho == "/api/loja":
            return self.responder(200, APP.dados_loja())
        if caminho == "/api/enciclopedia":
            return self.responder(200, APP.dados_enciclopedia())
        if caminho.startswith("/api/img/"):
            nome = caminho.rsplit("/", 1)[1]
            path = APP.caminho(os.path.join("img", nome))
            if not re.fullmatch(r"[\w\-]+\.png", nome) or not os.path.isfile(path):
                return self.responder(404, {"erro": "sem imagem"})
            with open(path, "rb") as f:
                return self.responder(200, f.read(), "image/png", cache=True)
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
        if p == "/api/comprar":
            return self.responder(200, APP.comprar(corpo.get("id")))
        if p == "/api/voltar":
            return self.responder(200, APP.voltar_agora())
        if p == "/api/config":
            return self.responder(200, APP.configurar(corpo.get("chave"), corpo.get("valor")))
        if p == "/api/chat":
            return self.responder(200, APP.conversar(corpo.get("texto")))
        if p == "/api/exportar_mapa":
            APP.enviar_comando(["export_map"])
            return self.responder(200, {"ok": True})
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
