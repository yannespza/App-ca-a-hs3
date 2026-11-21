"""HS3 Companion - ponte entre o mod UE4SS do Hunting Simulator 3 e o app.

Lê state.json e events.jsonl gravados pelo mod, gera e valida missões,
paga recompensas escrevendo comandos em cmd.txt e serve o app em http://localhost.
Só usa a biblioteca padrão do Python.
"""
import json
import math
import os
import random
import sys
import threading
import time
import uuid
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSAO = "0.1.0"

# ------------------------------------------------------------------ caminhos
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    WEB_DIR = os.path.join(sys._MEIPASS, "web")  # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    WEB_DIR = os.path.join(BASE_DIR, "web")

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DADOS_PATH = os.path.join(BASE_DIR, "dados_hs3.json")

CONFIG_PADRAO = {
    "pasta_mod": r"D:\SteamLibrary\steamapps\common\HS3\HS3\Binaries\Win64\ue4ss\Mods\HS3Discovery",
    "porta": 8765,
    "abrir_navegador": True,
    "missoes_ativas": 3,
    "limite_diario_creditos": 20000,
}

# ------------------------------------------------------------------ catálogo
GRUPOS = [
    # (chave, nome em português, palavras que identificam no tag/classe)
    ("pato", "Pato", ["duck", "mallard", "pintail", "bufflehead", "teal", "wigeon", "canvasback"]),
    ("ganso", "Ganso", ["goose"]),
    ("peru", "Peru-selvagem", ["turkey"]),
    ("faisao", "Faisão", ["pheasant"]),
    ("codorna", "Codorna", ["quail"]),
    ("pomba", "Pomba", ["dove", "pigeon"]),
    ("cervo", "Cervo", ["deer", "cervidae"]),
    ("alce", "Wapiti / Alce", ["elk", "moose", "wapiti"]),
    ("antilocapra", "Antilocapra", ["pronghorn"]),
    ("porco", "Porco-do-mato", ["hog", "boar", "suidae", "javelina", "peccary"]),
    ("coiote", "Coiote", ["coyote"]),
    ("lobo", "Lobo", ["wolf"]),
    ("raposa", "Raposa", ["fox"]),
    ("coelho", "Coelho / Lebre", ["rabbit", "hare", "jackrabbit", "cottontail"]),
    ("urso", "Urso", ["bear"]),
    ("puma", "Puma", ["puma", "cougar", "mountainlion", "lion"]),
    ("carneiro", "Carneiro / Cabra", ["sheep", "bighorn", "goat", "ram"]),
    ("bisao", "Bisão", ["bison", "buffalo"]),
]


def grupo_de(texto):
    t = (texto or "").lower().replace("_", "")
    for chave, nome, palavras in GRUPOS:
        if any(p in t for p in palavras):
            return chave, nome
    return "outro", "Outro animal"


def nome_especie(tag):
    """Animals.Types.Bird.Duck.NorthernPintail -> Northern Pintail"""
    if not tag:
        return None
    ultimo = tag.split(".")[-1]
    out = ""
    for i, c in enumerate(ultimo):
        if i and c.isupper() and not ultimo[i - 1].isupper():
            out += " "
        out += c
    return out


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
def gerar_missao(dados, evitar_tipos=()):
    vistos = set(dados.get("grupos_vistos", []))
    vistos.discard("outro")
    opcoes = []

    for chave in vistos:
        nome = dict((g[0], g[1]) for g in GRUPOS).get(chave, chave)
        n = random.choice([1, 2, 3])
        opcoes.append({
            "tipo": "abater_grupo", "grupo": chave, "meta": n,
            "titulo": f"Abater {n} {nome.lower()}{'s' if n > 1 else ''}",
            "descricao": f"Abata e recolha {n} animal(is) do grupo {nome}.",
            "creditos": 400 * n, "reputacao": 20 * n,
        })
    d = random.choice([50, 100, 150, 200])
    opcoes.append({
        "tipo": "distancia", "meta": 1, "distancia": d,
        "titulo": f"Tiro de {d} m",
        "descricao": f"Abata qualquer animal a {d} metros ou mais.",
        "creditos": 300 + d * 6, "reputacao": 15 + d // 10,
    })
    n = random.choice([3, 5, 8])
    opcoes.append({
        "tipo": "marcar", "meta": n,
        "titulo": f"Olho de águia: marcar {n} animais",
        "descricao": f"Marque {n} animais diferentes com o binóculo.",
        "creditos": 120 * n, "reputacao": 5 * n,
    })
    g = random.choice([0.5, 0.6, 0.7])
    opcoes.append({
        "tipo": "genetica", "meta": 1, "genetica": g,
        "titulo": f"Troféu de genética {int(g * 100)}%+",
        "descricao": f"Abata um animal com genética de {int(g * 100)}% ou mais.",
        "creditos": int(1500 * g * 2), "reputacao": int(60 * g),
    })
    n = random.choice([2, 3, 4])
    opcoes.append({
        "tipo": "abater_qualquer", "meta": n,
        "titulo": f"Dia de caça: {n} abates",
        "descricao": f"Abata e recolha {n} animais de qualquer espécie.",
        "creditos": 350 * n, "reputacao": 15 * n,
    })
    opcoes.append({
        "tipo": "sem_torre", "meta": 1,
        "titulo": "Caçada a pé",
        "descricao": "Abata um animal sem estar numa torre/espera.",
        "creditos": 700, "reputacao": 30,
    })

    ativos = {m.get("tipo") + str(m.get("grupo", "")) for m in dados["missoes"] if m["status"] == "ativa"}
    candidatas = [o for o in opcoes if (o["tipo"] + str(o.get("grupo", ""))) not in ativos and o["tipo"] not in evitar_tipos]
    m = dict(random.choice(candidatas or opcoes))
    m.update({"id": uuid.uuid4().hex[:8], "status": "ativa", "progresso": 0,
              "criada": time.time(), "contados": []})
    return m


def avaliar_missoes(dados, evento):
    """Atualiza o progresso das missões ativas com um evento (abate confirmado ou marcação)."""
    concluidas = []
    for m in dados["missoes"]:
        if m["status"] != "ativa" or evento.get("ts", 0) < m["criada"] - 2:
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
                conta = (evento.get("distancia_m") or 0) >= m["distancia"]
            elif t == "genetica":
                conta = (evento.get("genetica") or 0) >= m["genetica"]
            elif t == "sem_torre":
                conta = evento.get("torre") is False
        elif evento["tipo"] == "marcado" and t == "marcar":
            conta = True
        if conta:
            m["contados"].append(chave)
            m["progresso"] = len(m["contados"])
            if m["progresso"] >= m["meta"]:
                m["status"] = "concluida"
                m["concluida_em"] = time.time()
                concluidas.append(m)
    return concluidas


# ------------------------------------------------------------------ núcleo
class Companion:
    def __init__(self):
        self.cfg = carregar_config()
        self.lock = threading.Lock()
        self.estado = {}
        self.estado_lido_em = 0
        self.dados = carregar_json(DADOS_PATH, {})
        d = self.dados
        d.setdefault("missoes", [])
        d.setdefault("abates", [])
        d.setdefault("marcados", {})
        d.setdefault("grupos_vistos", [])
        d.setdefault("pendentes", {})
        d.setdefault("eventos_offset", 0)
        d.setdefault("pagamentos_dia", {})
        d.setdefault("recompensas", [])
        self.completar_missoes()

    # --- arquivos do mod
    def caminho(self, nome):
        return os.path.join(self.cfg["pasta_mod"], nome)

    def ler_estado(self):
        try:
            with open(self.caminho("state.json"), "r", encoding="utf-8") as f:
                st = json.load(f)
            self.estado = st
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

    def enviar_comando(self, linhas):
        path = self.caminho("cmd.txt")
        with open(path, "a", encoding="utf-8") as f:
            for l in linhas:
                f.write(l + "\n")

    # --- processamento
    def registrar_grupo(self, chave):
        if chave and chave not in self.dados["grupos_vistos"]:
            self.dados["grupos_vistos"].append(chave)

    def processar(self, ev):
        d = self.dados
        tipo = ev.get("tipo")
        if tipo == "marcado":
            chave, nome = grupo_de(ev.get("especie"))
            ev["grupo"], ev["grupo_nome"] = chave, nome
            ev["especie_nome"] = nome_especie(ev.get("especie"))
            ev["sexo_nome"] = SEXO.get(ev.get("sexo"), "?")
            ev["visto_em"] = time.time()
            novo = str(ev.get("id")) not in d["marcados"]
            d["marcados"][str(ev.get("id"))] = ev
            self.registrar_grupo(chave)
            if novo:
                return avaliar_missoes(d, {"tipo": "marcado", "id": ev.get("id"), "ts": time.time()})
        elif tipo == "abate":
            d["pendentes"][str(ev.get("id"))] = ev
        elif tipo == "abate_final":
            if ev.get("resultado") not in RESULTADO_OK:
                return []
            id_ = str(ev.get("id"))
            if any(str(a.get("id")) == id_ for a in d["abates"]):
                return []
            base = d["pendentes"].pop(id_, {})
            ab = dict(base)
            ab.update({k: v for k, v in ev.items() if v is not None})
            if base.get("distancia_m") is not None:
                ab["distancia_m"] = base["distancia_m"]
            marc = d["marcados"].get(id_)
            especie = (marc or {}).get("especie")
            chave, nome = grupo_de(especie or ab.get("classe"))
            ab.update({"grupo": chave, "grupo_nome": nome, "especie": especie,
                       "especie_nome": nome_especie(especie) or nome,
                       "acao_nome": ACOES.get(ab.get("acao"), "?"), "ts": time.time()})
            self.registrar_grupo(chave)
            d["abates"].append(ab)
            return avaliar_missoes(d, dict(ab, tipo="abate_confirmado"))
        elif tipo == "recompensa":
            d["recompensas"].append(ev)
            d["recompensas"] = d["recompensas"][-100:]
            ref = ev.get("ref")
            for m in d["missoes"]:
                if m["id"] == ref:
                    m.setdefault("pago", {})[ev.get("recurso")] = bool(ev.get("ok"))
                    if all(m["pago"].get(r) for r in ("creditos", "reputacao")):
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
            linhas = []
            if cred > 0:
                linhas.append(f"add_credits {cred} {m['id']}")
            else:
                m.setdefault("pago", {})["creditos"] = True
            linhas.append(f"add_rep {m['reputacao']} {m['id']}")
            self.enviar_comando(linhas)
            dia[hoje] = pago_hoje + cred
            m["enviado"] = time.time()
            m["creditos_pagos"] = cred

    def completar_missoes(self):
        ativas = [m for m in self.dados["missoes"] if m["status"] == "ativa"]
        while len(ativas) < self.cfg["missoes_ativas"]:
            m = gerar_missao(self.dados)
            self.dados["missoes"].append(m)
            ativas.append(m)
        # mantém histórico curto
        fim = [m for m in self.dados["missoes"] if m["status"] != "ativa"]
        if len(fim) > 60:
            remover = {m["id"] for m in fim[:-60]}
            self.dados["missoes"] = [m for m in self.dados["missoes"] if m["id"] not in remover]

    def ciclo(self):
        with self.lock:
            self.ler_estado()
            mudou = False
            for ev in self.ler_eventos():
                self.processar(ev)
                mudou = True
            antes = len(self.dados["missoes"])
            self.pagar_pendentes()
            self.completar_missoes()
            # limpa marcações com mais de 2 h
            limite = time.time() - 7200
            self.dados["marcados"] = {k: v for k, v in self.dados["marcados"].items() if v.get("visto_em", 0) > limite}
            if mudou or len(self.dados["missoes"]) != antes or any(
                    m["status"] == "concluida" for m in self.dados["missoes"]):
                salvar_json(DADOS_PATH, self.dados)

    def loop(self):
        while True:
            try:
                self.ciclo()
            except Exception as e:  # nunca derruba a ponte
                print("erro no ciclo:", e)
            time.sleep(1)

    # --- API
    def trocar_missao(self, id_):
        with self.lock:
            for m in self.dados["missoes"]:
                if m["id"] == id_ and m["status"] == "ativa":
                    m["status"] = "trocada"
                    self.completar_missoes()
                    salvar_json(DADOS_PATH, self.dados)
                    return True
        return False

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
            marcados = []
            for m in self.dados["marcados"].values():
                item = dict(m)
                item["distancia_m"] = distancia_m(pos, m.get("pos"))
                item["direcao"] = direcao(pos, m.get("pos"), yaw)
                item["minutos"] = round((time.time() - m.get("visto_em", time.time())) / 60, 1)
                marcados.append(item)
            marcados.sort(key=lambda x: x["distancia_m"] if x["distancia_m"] is not None else 1e9)
            mapa = st.get("mapa")
            rep = [r for r in st.get("reputacao", []) or []]
            return {
                "versao": VERSAO,
                "conectado": self.conectado(),
                "em_reserva": self.em_reserva(),
                "estado": st,
                "reputacao_mapa_atual": next((r for r in rep if mapa and mapa in (r.get("mapa") or "")), None),
                "marcados": marcados,
                "missoes": [m for m in self.dados["missoes"] if m["status"] == "ativa"]
                + [m for m in self.dados["missoes"] if m["status"] in ("concluida", "paga")][-8:][::-1],
                "abates": self.dados["abates"][-30:][::-1],
                "estatisticas": self.estatisticas(),
                "pasta_mod": self.cfg["pasta_mod"],
                "pasta_mod_existe": os.path.isdir(self.cfg["pasta_mod"]),
            }


APP = None

TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
         ".json": "application/json", ".webmanifest": "application/manifest+json",
         ".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".woff2": "font/woff2"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, codigo, corpo, tipo="application/json"):
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        caminho = self.path.split("?")[0]
        if caminho == "/api/estado":
            return self.responder(200, APP.snapshot())
        if caminho == "/":
            caminho = "/index.html"
        arq = os.path.normpath(os.path.join(WEB_DIR, caminho.lstrip("/")))
        if not arq.startswith(os.path.normpath(WEB_DIR)) or not os.path.isfile(arq):
            return self.responder(404, {"erro": "não encontrado"})
        with open(arq, "rb") as f:
            self.responder(200, f.read(), TIPOS.get(os.path.splitext(arq)[1], "application/octet-stream"))

    def do_POST(self):
        tam = int(self.headers.get("Content-Length") or 0)
        try:
            corpo = json.loads(self.rfile.read(tam) or b"{}")
        except Exception:
            corpo = {}
        if self.path == "/api/missoes/trocar":
            return self.responder(200, {"ok": APP.trocar_missao(corpo.get("id"))})
        self.responder(404, {"erro": "não encontrado"})


def main():
    global APP
    APP = Companion()
    porta = APP.cfg["porta"]
    print(f"HS3 Companion {VERSAO}")
    print(f"Pasta do mod: {APP.cfg['pasta_mod']}")
    if not os.path.isdir(APP.cfg["pasta_mod"]):
        print("ATENÇÃO: pasta do mod não encontrada. Ajuste 'pasta_mod' em", CONFIG_PATH)
    threading.Thread(target=APP.loop, daemon=True).start()
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    url = f"http://localhost:{porta}"
    print(f"App aberto em {url}  (deixe esta janela aberta enquanto joga)")
    if APP.cfg.get("abrir_navegador"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
