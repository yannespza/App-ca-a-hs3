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


# ---------------------------------------------------------------- enciclopédia (diário de campo)
CABECALHOS = {
    "BigGame": "Caça grossa", "SmallGame": "Caça miúda", "Predators": "Predadores", "Predator": "Predadores",
    "Birds": "Aves", "Bird": "Aves", "UplandBirds": "Aves de campo", "Waterfowl": "Aves aquáticas", "Varmint": "Pragas",
}
MEDALHAS = {"Bronze": "Bronze", "Silver": "Prata", "Gold": "Ouro", "Diamond": "Diamante", "Platinum": "Platina"}
ATRIBUTOS_PT = {
    "Recoil": "Recuo", "Sway": "Oscilação", "StandingStability": "Estabilidade em pé", "CrouchingStability": "Estabilidade agachado",
    "ProneStability": "Estabilidade deitado", "Zoom": "Zoom", "RateOfFire": "Cadência", "ReloadSpeed": "Velocidade de recarga",
    "Noise": "Ruído", "Range": "Alcance", "Damage": "Dano", "Accuracy": "Precisão", "Penetration": "Penetração",
    "VisualDetectionFactor": "Camuflagem visual", "SoundDetectionFactor": "Silêncio", "SmellDetectionFactor": "Controle de odor",
    "SprintSpeedFactor": "Velocidade de corrida", "AimSpeed": "Velocidade de mira", "Weight": "Peso",
}


def nome_mapa(m):
    m = m or ""
    for chave, nome in (("Texas", "Texas"), ("Colorado", "Colorado"), ("Poland", "Polônia"), ("Hub", "Rancho")):
        if chave.lower() in m.lower():
            return nome
    return m


def nome_atributo(a):
    if a in ATRIBUTOS_PT:
        return ATRIBUTOS_PT[a]
    out = ""
    for i, c in enumerate(a):
        if i and c.isupper() and not a[i - 1].isupper():
            out += " "
        out += c
    return out.replace("Factor", "").strip()


def _casa_tag(a, b):
    a, b = a or "", b or ""
    return bool(a and b) and (a == b or a.startswith(b + ".") or b.startswith(a + "."))


def _limpo(t):
    t = (t or "").strip()
    return "" if t in ("None", "TBD", "PLACEHOLDER") or t.lower().startswith("lorem") else t


def _categoria_item(tipo):
    t = tipo or ""
    if t.startswith("Inventory.Weapon"):
        return "armas"
    if t.startswith("Inventory.Ammo") or t.endswith("Attachments.Ammo"):
        return "municao"
    if t.startswith("Cosmetics.Character.Clothing") or "Backpack" in t:
        return "roupas"
    if t.startswith("Cosmetics.Companion"):
        return "itens"
    if t.startswith("Companion"):
        return "caes"
    if t.startswith("Inventory.") or t.startswith("Cosmetics.Weapons"):
        return "itens"
    return None


def _sub_item(tipo, categoria):
    p = (tipo or "").split(".")
    if categoria == "armas":
        nomes = {"Rifle": "Rifles", "Shotgun": "Espingardas", "Bow": "Arcos", "Crossbow": "Bestas", "Handgun": "Pistolas / revólveres",
                 "Pistol": "Pistolas / revólveres", "Revolver": "Pistolas / revólveres", "Muzzleloader": "Antecarga"}
        for x in p[3:]:
            if x in nomes:
                return nomes[x]
        return "Outras armas"
    if categoria == "municao":
        return "Munição"
    if categoria == "roupas":
        return nome_parte(tipo)
    if categoria == "itens" and (tipo or "").startswith("Cosmetics.Companion"):
        return "Acessórios do cão"
    if categoria == "itens" and (tipo or "").startswith("Cosmetics.Weapons.Attachments"):
        return {"Scope": "Lunetas / miras", "FrontBarrel": "Cano (supressor/freio)", "UnderBarrel": "Bipés / acessórios"}.get(p[-1], "Acessórios de arma")
    if categoria == "itens":
        return tipo_item(tipo)[1] or (p[-1] if p else "Item")
    return "Cães"


def calibres_item(c):
    l = [t for t in c.get("compat") or [] if t.startswith("Inventory.Ammo")]
    if c.get("calibre") and c["calibre"] not in l:
        l.insert(0, c["calibre"])
    return l


def _sub_municao(cal):
    p = (cal or "").split(".")
    return {"Bullet": "Balas", "Shell": "Cartuchos", "Arrow": "Flechas", "Bolt": "Virotes"}.get(p[2] if len(p) > 2 else "", "Munição")


def enciclopedia_jogo(dados, calibres, catalogo_equip, abates, vistos, nome_especie, grupo_de):
    """Monta o diário de campo completo a partir de jogo_dados.json (exportado pelo mod)."""
    comprados = {b["id"] for b in catalogo_equip.get("comprados", [])}
    vestidos = {r.get("item") for r in catalogo_equip.get("roupa", [])}
    na_mochila = {m.get("item") for m in catalogo_equip.get("mochila", [])}
    esp_cal = especies_por_calibre(calibres)
    calibre_por_arma = {a["arma"]: a["calibre"] for a in abates if a.get("arma") and a.get("calibre")}

    def img(n):
        return f"/api/img/{n}" if n else None

    # ---- animais
    animais = []
    for a in dados.get("animais", []):
        tag = a.get("tag") or ""
        if not tag or tag.endswith(".Hub"):
            continue
        esp = next((e for e in dados.get("especies", []) if e.get("tag") == tag), None) or \
            next((e for e in dados.get("especies", []) if _casa_tag(e.get("tag"), tag)), None) or {}
        cal = next((c for c in calibres if c.get("animal") == tag), None) or next((c for c in calibres if _casa_tag(c.get("animal"), tag)), None) or {}
        mortos = [x for x in abates if _casa_tag(x.get("especie"), tag)]
        dist = [x.get("distancia_m") for x in mortos if x.get("distancia_m")]
        cab = (a.get("grupo") or "").split(".")[-1]
        g, gnome = grupo_de(tag)
        permitidos = cal.get("compativeis", [])
        armas_ok = []
        for c in dados.get("itens", []):
            if _categoria_item(c.get("tipo")) != "armas" or c.get("desativado"):
                continue
            cs = calibres_item(c) or [x for x in [calibre_por_arma.get((c.get("item") or "").split(":")[-1])] if x]
            ok = [x for x in cs if any(p == x or p.startswith(x + ".") for p in permitidos)]
            if ok:
                armas_ok.append({"id": c["id"], "nome": c.get("nome"), "calibre": ", ".join(nome_calibre(x) for x in ok),
                                 "tem": c["id"] in comprados or bool(c.get("padrao"))})
        armas_ok.sort(key=lambda x: (not x["tem"], x["nome"] or ""))
        medalhas = [{"nome": MEDALHAS.get(k.split(".")[-1], k.split(".")[-1]), "pontos": round(v, 1)}
                    for k, v in sorted((esp.get("medalhas") or {}).items(), key=lambda kv: kv[1])]
        animais.append({
            "id": a["id"], "tag": tag, "nome": _limpo(a.get("titulo")) or nome_especie(tag), "grupo": g, "grupo_nome": gnome,
            "cabecalho": CABECALHOS.get(cab, cab or "Animais"), "imagem": img(a.get("imagem")),
            "descricao": _limpo(a.get("descricao")),
            "secoes_titulo": _limpo(a.get("secoes_titulo")), "secoes": [s for s in map(_limpo, a.get("secoes") or []) if s],
            "habitat_titulo": _limpo(a.get("habitat_titulo")), "habitat": [s for s in map(_limpo, a.get("habitat") or []) if s],
            "reservas": sorted({nome_mapa(m) for m in a.get("mapas") or []} - {"Rancho"}),
            "calibres": [nome_calibre(c) for c in permitidos], "proibidos": [nome_calibre(c) for c in cal.get("incompativeis", [])],
            "armas": armas_ok[:40],
            "preco_kg": esp.get("preco_kg"), "taxidermia": esp.get("preco_taxidermia"),
            "chamado_m": round(esp["chamado_m"]) if esp.get("chamado_m") else None,
            "tipo_caca": (esp.get("tipo_caca") or "").split(".")[-1] or None, "medalhas": medalhas,
            "medalha_max": esp.get("medalha_max"),
            "licencas": [{"reserva": nome_mapa(l.get("mapa")), "imagem": img(l.get("imagem"))} for l in esp.get("licencas") or [] if l.get("imagem")],
            "vistos": sum(v for k, v in vistos.items() if _casa_tag(k, tag)), "abates": len(mortos),
            "melhor_genetica": max((x.get("genetica") or 0 for x in mortos), default=None),
            "tiro_mais_longo": max(dist) if dist else None,
            "ultimos_abates": [{"distancia_m": x.get("distancia_m"), "genetica": x.get("genetica"), "calibre": nome_calibre(x.get("calibre")),
                                "ts": x.get("ts"), "reserva": nome_mapa(x.get("reserva"))} for x in mortos[-5:]][::-1],
        })
    ordem_cab = ["Caça grossa", "Predadores", "Caça miúda", "Aves de campo", "Aves aquáticas", "Aves", "Pragas"]
    animais.sort(key=lambda x: (ordem_cab.index(x["cabecalho"]) if x["cabecalho"] in ordem_cab else 99, x["nome"]))

    # ---- itens da loja
    itens = {"armas": [], "municao": [], "roupas": [], "itens": [], "caes": []}
    vistos_nome = set()
    for c in dados.get("itens", []):
        cat = _categoria_item(c.get("tipo"))
        if not cat or c.get("desativado"):
            continue
        chave = (cat, c.get("nome"), c.get("item"))
        if chave in vistos_nome:
            continue
        vistos_nome.add(chave)
        d = {"id": c["id"], "nome": _limpo(c.get("nome")) or c["id"], "sub": _sub_item(c.get("tipo"), cat),
             "imagem": img(c.get("icone")), "descricao": _limpo(c.get("descricao")), "preco": c.get("preco"),
             "moeda": "pontos de campo" if "FieldPoints" in (c.get("moeda") or "") else "créditos",
             "marca": (c.get("marca") or "").split(".")[-1].replace("None", "").replace("Clothes", ""),
             "tem": c["id"] in comprados or bool(c.get("padrao")), "em_uso": c.get("item") in vestidos or c.get("item") in na_mochila,
             "cargas": c.get("cargas") if (c.get("cargas") or 0) > 1 else None}
        cals = calibres_item(c)
        if cat == "armas" and not cals:
            cals = [x for x in [calibre_por_arma.get((c.get("item") or "").split(":")[-1])] if x]
        if cat == "municao":
            d["sub"] = _sub_municao(cals[0] if cals else c.get("tipo"))
        if cals and cat in ("armas", "municao"):
            d["calibre"] = ", ".join(nome_calibre(x) for x in cals)
            def casa(k, x):
                return k == x or k.startswith(x + ".")
            d["calibres"] = [{"nome": nome_calibre(x),
                              "especies": sorted({nome_especie(a) for k, l in esp_cal.items() if casa(k, x) for a in l if a}),
                              "proibidas": sorted({nome_especie(l.get("animal")) for l in calibres
                                                   if any(casa(k, x) for k in l.get("incompativeis", []))} - {None})}
                             for x in cals]
        if c.get("stats"):
            st = {nome: round(c["stats"].get(chave, 0)) for chave, nome in STATS}
            d["stats"] = st
            d["camuflagem"] = round((st["visual"] + st["som"] + st["cheiro"]) / 3)
        if c.get("atributos"):
            d["atributos"] = {nome_atributo(k): round(v, 2) for k, v in c["atributos"].items()}
        itens[cat].append(d)

    # ---- cães (definições + item da loja, se houver)
    caes_loja = {(c.get("item") or "").split(":")[-1]: c for c in itens["caes"]}
    caes = []
    for c in dados.get("caes", []):
        loja = caes_loja.pop(c["id"], None) or {}
        raca = (c.get("raca") or "").split(".")[-1]
        caes.append({"id": c["id"], "nome": _limpo(c.get("nome")) or loja.get("nome") or c["id"], "sub": "Cães",
                     "raca": nome_atributo(raca) if raca else None, "imagem": img(c.get("imagem")) or loja.get("imagem"),
                     "descricao": loja.get("descricao"), "preco": loja.get("preco"), "moeda": loja.get("moeda"), "tem": loja.get("tem")})
    caes += list(caes_loja.values())
    diario_caes = [e for e in dados.get("diario", []) if any(p in (e.get("categoria") or "") + (e.get("grupo") or "") for p in ("Companion", "Dog"))]
    for e in diario_caes:
        alvo = next((c for c in caes if c["nome"].lower() in (e.get("titulo") or "").lower() or (e.get("titulo") or "").lower() in c["nome"].lower()), None)
        if alvo:
            alvo["descricao"] = alvo.get("descricao") or _limpo(e.get("descricao"))
            alvo["imagem"] = alvo.get("imagem") or img(e.get("imagem"))
        else:
            caes.append({"id": e["id"], "nome": _limpo(e.get("titulo")) or e["id"], "sub": "Cães", "imagem": img(e.get("imagem")),
                         "descricao": _limpo(e.get("descricao"))})

    for lista in itens.values():
        lista.sort(key=lambda x: (x["sub"], not x["tem"], x["nome"]))
    return {
        "pronto": True, "versao": dados.get("versao"),
        "categorias": [
            {"id": "animais", "nome": "Animais", "itens": animais},
            {"id": "caes", "nome": "Cães", "itens": caes},
            {"id": "armas", "nome": "Armas", "itens": itens["armas"]},
            {"id": "municao", "nome": "Munição", "itens": itens["municao"]},
            {"id": "roupas", "nome": "Roupas", "itens": itens["roupas"]},
            {"id": "itens", "nome": "Itens e acessórios", "itens": itens["itens"]},
        ],
    }
