"""Armário, loja de roupas, patente e enciclopédia (dados vindos do jogo)."""
import json
import os


PARTES = {
    "Top": "Blusa / jaqueta", "Bottom": "Calça", "Gloves": "Luvas", "Shoes": "Calçado", "Backpack": "Mochila",
    "Cap": "Boné", "Hat": "Chapéu", "Beanie": "Gorro", "Balaclava": "Balaclava", "Headwear": "Cabeça",
}
STATS = [("VisualDetectionFactor", "visual"), ("SoundDetectionFactor", "som"), ("SmellDetectionFactor", "cheiro"),
         ("SprintSpeedFactor", "corrida")]

PATENTES = [(0, "Novato"), (1000, "Aprendiz"), (3000, "Mateiro"), (6000, "Rastreador"), (10000, "Caçador"),
            (16000, "Veterano"), (25000, "Mestre caçador"), (40000, "Lenda do Texas")]


def ler(path, padrao):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


class Cache:
    def __init__(self):
        self._c = {}

    def json(self, path, padrao):
        try:
            mt = os.path.getmtime(path)
        except OSError:
            return padrao
        if self._c.get(path, (None,))[0] != mt:
            self._c[path] = (mt, ler(path, padrao))
        return self._c[path][1]


def nome_parte(tag):
    t = (tag or "").split(".")
    for chave in reversed(t):
        if chave in PARTES:
            return PARTES[chave]
    return t[-1] if t else "?"


def nome_calibre(tag):
    """Inventory.Ammo.Bullet.308.Win -> .308 Win ; Inventory.Ammo.Shell.12G.Slug -> 12G Slug"""
    if not tag:
        return None
    p = tag.split(".")
    if "Ammo" in p:
        p = p[p.index("Ammo") + 1:]
    tipo = {"Bullet": "", "Shell": "", "Arrow": "Flecha ", "Bolt": "Virote "}.get(p[0], p[0] + " ") if p else ""
    resto = " ".join(p[1:])
    if p and p[0] == "Bullet" and resto[:1].isdigit():
        resto = "." + resto
    return (tipo + resto).strip()


def tipo_item(tag):
    t = tag or ""
    if t.startswith("Inventory.Weapon"):
        partes = t.split(".")
        return "arma", " ".join(partes[3:]) if len(partes) > 3 else "Arma"
    if "Caller" in t:
        return "chamariz", "Chamariz"
    if "Spray" in t:
        return "cheiro", "Spray / cheiro"
    if "Decoy" in t:
        return "decoy", "Isca / decoy"
    if "Opticals" in t:
        return "otica", "Ótica"
    if "Blind" in t:
        return "espera", "Espera / blind"
    if t.startswith("Inventory.Objects"):
        return "acessorio", "Acessório"
    if t.startswith("Cosmetics.Weapons.Attachments"):
        return "acessorio_arma", "Acessório de arma"
    return None, None


def especies_por_calibre(calibres):
    mapa = {}
    for linha in calibres:
        for c in linha.get("compativeis", []):
            mapa.setdefault(c, []).append(linha.get("animal"))
    return mapa


def armario(catalogo, equip, calibres, nome_especie, abates):
    por_item = {c.get("item"): c for c in catalogo}
    por_id = {c.get("id"): c for c in catalogo}
    comprados = {b["id"]: b.get("cargas") for b in equip.get("comprados", [])}
    esp_cal = especies_por_calibre(calibres)
    calibre_por_arma = {}
    for a in abates:
        if a.get("arma") and a.get("calibre"):
            calibre_por_arma[a["arma"]] = a["calibre"]

    def info(c, extra=None):
        cat, rot = tipo_item(c.get("tipo"))
        d = {"id": c.get("id"), "nome": c.get("nome") or c.get("id"), "categoria": cat, "rotulo": rot,
             "preco": c.get("preco"), "marca": (c.get("marca") or "").split(".")[-1].replace("None", ""),
             "descricao": c.get("descricao")}
        cal = (c.get("calibre") if c.get("calibre") not in (None, "None") else None) or next((t for t in c.get("compat") or [] if t and t.startswith("Inventory.Ammo")), None)
        if not cal:
            cal = calibre_por_arma.get((c.get("item") or "").split(":")[-1])
        if cal:
            d["calibre"] = nome_calibre(cal)
            d["especies"] = sorted({nome_especie(a) for a in esp_cal.get(cal, []) if a})
        d.update(extra or {})
        return d

    mochila = []
    for m in equip.get("mochila", []):
        c = por_item.get(m.get("item"))
        if c:
            mochila.append(info(c, {"cargas": m.get("cargas")}))
        else:
            nome = (m.get("item") or "").split(":")[-1].replace("ID_", "").replace("_", " ")
            mochila.append({"nome": nome, "rotulo": (m.get("tipo") or "").split(".")[-1]})
    possuidos = []
    for sid, cargas in comprados.items():
        c = por_id.get(sid)
        if c and tipo_item(c.get("tipo"))[0]:
            possuidos.append(info(c, {"cargas": cargas}))
    possuidos.sort(key=lambda x: (x["categoria"] or "", x["nome"]))
    return {"mochila": mochila, "possuidos": possuidos}


def loja(catalogo, equip):
    comprados = {b["id"] for b in equip.get("comprados", [])}
    vestidos = {r.get("item") for r in equip.get("roupa", [])}
    itens = []
    for c in catalogo:
        st = c.get("stats")
        if not st or not (c.get("tipo") or "").startswith("Cosmetics.Character.Clothing") or c.get("desativado"):
            continue
        stats = {nome: st.get(chave, 0) for chave, nome in STATS}
        camuflagem = round((stats["visual"] + stats["som"] + stats["cheiro"]) / 3)
        itens.append({"id": c["id"], "nome": c.get("nome") or c["id"], "parte": nome_parte(c.get("parte") or c.get("tipo")),
                      "preco": c.get("preco") or 0, "marca": (c.get("marca") or "").split(".")[-1].replace("Clothes", "").replace("None", ""),
                      "stats": stats, "camuflagem": camuflagem, "comprado": c["id"] in comprados or c.get("padrao"),
                      "vestido": c.get("item") in vestidos})
    itens.sort(key=lambda x: (x["parte"], -x["camuflagem"], x["preco"]))
    vestidos_info = [i for i in itens if i["vestido"]]
    return {"itens": itens, "vestidos": vestidos_info, "deteccao": equip.get("deteccao")}


def pontos_abate(a):
    p = 100 + int((a.get("genetica") or 0) * 150) + int((a.get("distancia_m") or 0) / 5)
    if a.get("calibre_compativel") is True:
        p += 50
    elif a.get("calibre_compativel") is False:
        p -= 150
    if a.get("estado_animal") in (1, 2, 4, 256, 512):
        p += 60
    if a.get("atraido"):
        p += 30
    if a.get("torre") is False:
        p += 20
    if (a.get("tiros") or 1) == 1:
        p += 40
    return max(10, p)


def patente(abates, missoes):
    pts = sum(pontos_abate(a) for a in abates) + 250 * sum(1 for m in missoes if m.get("status") in ("concluida", "paga"))
    atual, prox = PATENTES[0], None
    for i, (minimo, nome) in enumerate(PATENTES):
        if pts >= minimo:
            atual = (minimo, nome)
            prox = PATENTES[i + 1] if i + 1 < len(PATENTES) else None
    progresso = 1.0 if not prox else (pts - atual[0]) / (prox[0] - atual[0])
    return {"pontos": pts, "patente": atual[1], "proxima": prox and prox[1], "faltam": prox and prox[0] - pts,
            "progresso": round(progresso, 3), "nivel": PATENTES.index(atual) + 1}


def enciclopedia(calibres, abates, vistos, nome_especie, grupo_de):
    fichas = []
    for linha in calibres:
        tag = linha.get("animal") or ""
        if tag.endswith(".Hub"):
            continue
        mortos = [a for a in abates if a.get("especie") == tag]
        dist = [a.get("distancia_m") for a in mortos if a.get("distancia_m")]
        g, gnome = grupo_de(tag)
        fichas.append({
            "tag": tag, "nome": nome_especie(tag), "grupo": g, "grupo_nome": gnome,
            "variante": tag.split(".")[-1] if tag.split(".")[-1] in ("Texas", "Colorado") else None,
            "calibres": [nome_calibre(c) for c in linha.get("compativeis", [])],
            "proibidos": [nome_calibre(c) for c in linha.get("incompativeis", [])],
            "vistos": vistos.get(tag, 0), "abates": len(mortos),
            "melhor_genetica": max((a.get("genetica") or 0 for a in mortos), default=None),
            "tiro_mais_longo": max(dist) if dist else None,
        })
    fichas.sort(key=lambda f: (-(f["abates"] + f["vistos"]), f["grupo_nome"], f["nome"]))
    return fichas
