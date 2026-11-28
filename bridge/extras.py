"""Armário, loja de roupas, patente e enciclopédia (dados vindos do jogo)."""
import json
import re
import os


PARTES = {
    "Top": "Blusa / jaqueta", "Bottom": "Calça", "Gloves": "Luvas", "Shoes": "Calçado", "Backpack": "Mochila",
    "Cap": "Boné", "Hat": "Chapéu", "Beanie": "Touca", "Balaclava": "Balaclava", "Headwear": "Cabeça",
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
    """Inventory.Ammo.Bullet.308.Win -> .308 Win ; Inventory.Ammo.Shell.12G.Slug -> Cal. 12 bala única (nomes como na loja do jogo)"""
    if not tag:
        return None
    p = tag.split(".")
    if "Ammo" in p:
        p = p[p.index("Ammo") + 1:]
    if not p:
        return tag
    if p[0] == "Shell":
        cal = "Cal. " + (p[1].rstrip("G") if len(p) > 1 else "?")
        carga = {"Slug": "bala única", "Buck": "chumbo grosso", "Bird": "chumbo para aves"}.get(p[2] if len(p) > 2 else "", "")
        if len(p) > 3 and p[3] == "Medium":
            carga += " médio"
        return f"{cal} {carga}".strip()
    if p[0] in ("Arrow", "Bolt"):
        return ("Flecha " if p[0] == "Arrow" else "Virote ") + " ".join(p[1:]).replace("gr", " gr").strip()
    resto = " ".join(p[1:])
    if p[0] == "Bullet" and resto[:1].isdigit():
        resto = "." + resto
    resto = {".9-3x62": "9.3x62", ".27 Nosler": "Nosler 27", ".300 Win": ".300 Win Mag"}.get(resto, resto)
    return resto.strip()


def tipo_item(tag):
    t = tag or ""
    if t.startswith("Inventory.Weapon"):
        partes = t.split(".")
        return "arma", " ".join(partes[3:]) if len(partes) > 3 else "Arma"
    if "Caller" in t:
        return "chamador", "Chamadores"
    if "Spray" in t:
        return "cheiro", "Sprays e iscas de cheiro"
    if "Decoy" in t:
        return "chamariz", "Chamarizes"
    if "Opticals" in t:
        return "otica", "Binóculos e telêmetros"
    if "Blind" in t:
        return "espera", "Esconderijos"
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


def loja(catalogo, equip, na_mochila=None, icones=None):
    comprados = {b["id"] for b in equip.get("comprados", [])}
    vestidos = {r.get("item") for r in equip.get("roupa", [])}
    itens = []
    for c in catalogo:
        st = c.get("stats")
        if not st or not (c.get("tipo") or "").startswith("Cosmetics.Character.Clothing") or c.get("desativado"):
            continue
        stats = {nome: st.get(chave, 0) for chave, nome in STATS}
        camuflagem = round((stats["visual"] + stats["som"] + stats["cheiro"]) / 3)
        ic = c.get("icone") or (icones or {}).get(c["id"])
        itens.append({"id": c["id"], "nome": c.get("nome") or c["id"], "parte": nome_parte(c.get("parte") or c.get("tipo")),
                      "imagem": f"/api/img/{ic}?p=1" if ic else None,
                      "preco": c.get("preco") or 0, "marca": (c.get("marca") or "").split(".")[-1].replace("Clothes", "").replace("None", ""),
                      "stats": stats, "camuflagem": camuflagem, "comprado": c["id"] in comprados or c.get("padrao"),
                      "vestido": c.get("item") in vestidos})
    itens.sort(key=lambda x: (x["parte"], -x["camuflagem"], x["preco"]))
    vestidos_info = [i for i in itens if i["vestido"]]
    return {"itens": itens, "vestidos": vestidos_info, "deteccao": equip.get("deteccao"),
            "equipamentos": loja_equipamentos(catalogo, comprados, na_mochila or set(), icones or {})}


CATEGORIAS_LOJA = [("Armas", ("Inventory.Weapon.Type.",)), ("Munição", ("Cosmetics.Weapons.Attachments.Ammo",)),
                   ("Acessórios", ("Cosmetics.Weapons.Attachments.Scope", "Cosmetics.Weapons.Attachments.FrontBarrel",
                                   "Cosmetics.Weapons.Attachments.UnderBarrel")),
                   ("Equipamentos", ("Inventory.Objects.", "Inventory.GPS"))]


def _sub_loja(tipo):
    t = tipo or ""
    for chave, nome in (("Rifle.Bolt", "Rifle de ferrolho"), ("Rifle.SemiAuto", "Rifle semiautomático"), ("Rifle.Lever", "Rifle de alavanca"),
                        ("Shotgun.DoubleBarrel", "Espingarda de dois canos"), ("Shotgun.SemiAuto", "Espingarda semiautomática"),
                        ("Shotgun.PumpAction", "Espingarda de bomba"), ("CrossBow", "Besta"), ("Bow.Recurved", "Arco recurvo"),
                        ("Bow.Compound", "Arco composto"), ("Scope", "Mira"), ("Suppressor", "Silenciador"), ("MuzzleBrake", "Freio de boca"),
                        ("Bipod", "Bipé"), ("Ammo", "Munição"), ("Caller.Duck", "Chamador de pato"), ("Caller", "Chamador"), ("Decoy", "Chamariz"),
                        ("Spray", "Spray de cheiro"), ("Binoculars", "Binóculo"), ("RangeFinder", "Telêmetro"), ("Blind", "Esconderijo"),
                        ("GPS", "GPS"), ("Misc", "Diversos")):
        if chave in t:
            return nome
    return "Outros"


def loja_equipamentos(catalogo, comprados, na_mochila, icones=None):
    """Tudo o que se compra com créditos fora as roupas: armas, munição, acessórios e equipamentos."""
    saida = []
    for c in catalogo:
        tipo = c.get("tipo") or ""
        cat = next((n for n, pref in CATEGORIAS_LOJA if tipo.startswith(pref)), None)
        if not cat or c.get("desativado") or "Credits" not in (c.get("moeda") or "Currency.Credits"):
            continue
        tem = c["id"] in comprados or bool(c.get("padrao")) or c.get("item") in na_mochila
        saida.append({"id": c["id"], "nome": c.get("nome") or c["id"], "categoria": cat, "sub": _sub_loja(tipo),
                      "preco": c.get("preco") or 0, "descricao": c.get("descricao") or "",
                      "marca": (c.get("marca") or "").split(".")[-1].replace("None", ""),
                      "imagem": (lambda ic: f"/api/img/{ic}?p=1" if ic else None)(c.get("icone") or (icones or {}).get(c["id"])),
                      "cargas": c.get("cargas") if (c.get("cargas") or -1) > 0 else None,
                      "comprado": tem, "dlc": DLC.get(c["id"])})
    saida.sort(key=lambda x: (x["comprado"], x["sub"], x["preco"], x["nome"]))
    return saida


def pontos_abate(a):
    p = 100 + int((a.get("genetica") or 0) * 150) + int((a.get("distancia_m") or 0) / 5)
    if a.get("calibre_compativel") is True:
        p += 50
    elif a.get("calibre_compativel") is False:
        p -= 150
    e = a.get("estado_animal")
    if isinstance(e, int) and e >= 0 and not (e & 4095 & (8 | 16 | 32 | 64 | 1024 | 2048)):
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


CABECALHOS = {
    "BigGame": "Animais de grande porte", "SmallGame": "Animais de pequeno porte", "Predators": "Predadores", "Predator": "Predadores",
    "Birds": "Aves", "Bird": "Aves", "UplandBirds": "Aves de campo", "UplandGame": "Aves de campo", "Waterfowl": "Aves aquáticas", "Varmint": "Pragas",
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
    if "DEV" in m or "Lobby" in m:
        return "Rancho"
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
    comprados |= {c.get("id") for c in dados.get("itens", []) if c.get("item") in na_mochila}   # itens de DLC
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
            "secoes_titulo": "Aparência e comportamento", "secoes": [s for s in map(_limpo, a.get("secoes") or []) if s],
            "habitat_titulo": _limpo(a.get("habitat_titulo")),
            "habitat": [s for s in map(_limpo, a.get("habitat") or []) if s and s not in (a.get("secoes") or [])],
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
    contagem = {}
    for x in animais:
        contagem[x["nome"]] = contagem.get(x["nome"], 0) + 1
    for x in animais:
        if contagem[x["nome"]] > 1 and x["reservas"]:
            x["nome"] = f'{x["nome"]} ({", ".join(x["reservas"])})'
    ordem_cab = ["Animais de grande porte", "Predadores", "Animais de pequeno porte", "Aves de campo", "Aves aquáticas", "Aves", "Pragas"]
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
                     "raca": nome_atributo(raca) if raca else None, "imagem": loja.get("imagem"),
                     "descricao": loja.get("descricao"), "preco": loja.get("preco"), "moeda": loja.get("moeda"), "tem": loja.get("tem")})
    caes += list(caes_loja.values())
    def palavras(t):
        return {w for w in (t or "").lower().replace("-", " ").split() if len(w) > 4}
    usados = set()
    for c in caes:
        e = next((e for e in dados.get("diario", []) if "Dogs.Header.Race" in (e.get("grupo") or "")
                  and palavras(e.get("titulo")) & palavras(c["nome"])), None)
        if e:
            usados.add(e["id"])
            c["descricao"] = c.get("descricao") or _limpo(e.get("descricao"))
            c["imagem"] = c.get("imagem") or img(e.get("imagem"))

    # ---- guia (demais páginas do diário do jogo)
    nomes_guia = {"FireArms": "Armas e óticas", "Gameplay": "Jogabilidade", "EcoSim": "Comportamento animal",
                  "Gear": "Equipamento", "Dogs": "Cães"}
    guia = []
    for e in dados.get("diario", []):
        if e["id"] in usados:
            continue
        cat = e.get("categoria") or ""
        if cat.startswith("World.Region."):
            sub = "Lugares – " + nome_mapa(cat.split(".")[-1])
        else:
            sub = nomes_guia.get(cat.split(".")[-1], "Outros")
        guia.append({"id": e["id"], "nome": _limpo(e.get("titulo")) or e["id"], "sub": sub, "imagem": img(e.get("imagem")),
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
            {"id": "guia", "nome": "Guia do jogo", "itens": sorted(guia, key=lambda x: (x["sub"], x["nome"]))},
        ],
    }


# ---------------------------------------------------------------- mochila por missão
# Espécies de cada chamador, chamariz e isca de cheiro.
# Chamadores: lido do jogo em 22/11/2026 (AnimalTags de B_CallerInstance_*, todos com alcance de 500 m e para os dois sexos).
# Chamarizes e iscas de urina: o jogo não guarda a espécie no item; vale pelo nome do produto.
ATRAI_TAGS = {
    "Caller_Deer": ["Animals.Types.Deer"], "Caller_Elk": ["Animals.Types.Elk"],
    "Caller_WildBoar": ["Animals.Types.Boar", "Animals.Types.Pig.Feral"],
    "Caller_Predator": ["Animals.Types.Feline.Bobcat", "Animals.Types.Wolf.Gray", "Animals.Types.Bear.Black", "Animals.Types.Canine.Coyote",
                        "Animals.Types.Feline.Lynx", "Animals.Types.Feline.Cougar"],
    "Caller_Turkey": ["Animals.Types.Bird.Turkey"], "Caller_Pheasant": ["Animals.Types.Bird.Pheasant"],
    "Caller_Goose": ["Animals.Types.Bird.Goose"], "Caller_Duck": ["Animals.Types.Bird.Duck"],
    "UrineSpray_Wolf": ["Animals.Types.Wolf"], "UrineSpray_WhitetailDeer": ["Animals.Types.Deer.WhiteTail"],
    "UrineSpray_MuleDeer": ["Animals.Types.Deer.DesertMule", "Animals.Types.Deer.MountainMule"],
    "UrineSpray_Elk": ["Animals.Types.Elk"], "UrineSpray_Rabbit": ["Animals.Types.Rabbit", "Animals.Types.Hare"],
    "UrineSpray_Boar": ["Animals.Types.Boar", "Animals.Types.Pig.Feral"],
    "DecoyWalkingTom": ["Animals.Types.Bird.Turkey"], "DecoyMagnumFloater": ["Animals.Types.Bird.Duck"],
    "DecoyMasterSeriesBossBuck": ["Animals.Types.Deer.WhiteTail"], "DecoyLoneHowler": ["Animals.Types.Canine.Coyote"],
    "DecoyElk": ["Animals.Types.Elk"],
}
# grupos do app (para os contratos) de cada item
ATRAI = {
    "Caller_Deer": ["cervo"], "Caller_Elk": ["alce"], "Caller_WildBoar": ["porco"],
    "Caller_Predator": ["coiote", "lobo", "felino", "urso"], "Caller_Turkey": ["peru"], "Caller_Pheasant": ["faisao"],
    "Caller_Goose": ["ganso"], "Caller_Duck": ["pato"],
    "UrineSpray_Wolf": ["lobo"], "UrineSpray_WhitetailDeer": ["cervo"], "UrineSpray_MuleDeer": ["cervo"],
    "UrineSpray_Elk": ["alce"], "UrineSpray_Rabbit": ["coelho"], "UrineSpray_Boar": ["porco"],
    "DecoyWalkingTom": ["peru"], "DecoyMagnumFloater": ["pato"], "DecoyMasterSeriesBossBuck": ["cervo"],
    "DecoyLoneHowler": ["coiote"], "DecoyElk": ["alce"],
}


def atrai_tags(item_id):
    n = item_id or ""
    for chave in sorted(ATRAI_TAGS, key=len, reverse=True):
        if chave in n:
            return ATRAI_TAGS[chave]
    return []


TIPOS_MOCHILA = ("Inventory.Weapon", "Inventory.Objects", "Inventory.GPS")


def _papel_objeto(item_id, tipo):
    """Classifica um objeto da mochila: (papel, grupos atraídos)."""
    n = item_id or ""
    for chave, grupos in ATRAI.items():
        if chave in n:
            papel = "isca" if "Spray" in n else ("chamariz" if "Decoy" in n else "chamador")
            return papel, grupos
    if "ScentKiller" in n:
        return "odor", []
    if "WindPowder" in n:
        return "vento", []
    if "Blind" in tipo or "Stakeout" in n:
        return "esconderijo", []
    if "RangeFinder" in tipo or "Fusion" in n:
        return "telemetro", []
    if "Binoculars" in tipo:
        return "binoculo", []
    if "GPS" in tipo:
        return "gps", []
    return "outro", []


def _tipos_combo(m):
    """Contratos novos (tipo combo) viram os tipos antigos para a Mochila entender o que precisa."""
    c = m.get("cond") or {}
    if c.get("marcar"):
        return ["marcar"]
    if c.get("visitar"):
        return ["visitar"]
    t = ["abater_grupo" if m.get("grupo") else "abater_qualquer"]
    for k in ("atrair", "nao_detectado", "calibre", "sem_torre"):
        if c.get(k):
            t.append(k)
    if "dist_min" in c:
        t.append("distancia")
    if "genetica" in c:
        t.append("genetica")
    return t


def requisitos_missoes(missoes, grupo_nome):
    expandidas = []
    for m in missoes:
        if m.get("tipo") == "combo":
            for t in _tipos_combo(m):
                expandidas.append(dict(m, tipo=t, dist_min=m.get("dist_min", 0),
                                       grupo=m.get("grupo") if t not in ("marcar", "visitar") else None))
        else:
            expandidas.append(m)
    missoes = expandidas
    armas = {(m.get("cond") or {}).get("arma") for m in missoes} - {None}
    grupos, qualquer = [], False
    tipos = {m["tipo"] for m in missoes}
    dist = [m for m in missoes if m["tipo"] == "distancia"]
    for m in missoes:
        if m.get("grupo"):
            if m["grupo"] not in grupos:
                grupos.append(m["grupo"])
        elif m["tipo"] not in ("marcar", "visitar"):
            qualquer = True
    grupos_contrato = {m["grupo"] for m in missoes if m.get("grupo") and not m.get("especie")}
    chips = [grupo_nome(g) for g in grupos if g in grupos_contrato]
    chips += list(dict.fromkeys(m["titulo"] for m in missoes if m.get("especie")))
    chips += ["Qualquer animal"] if qualquer and not grupos else []
    if dist:
        chips += [f"Tiro de {m['dist_min']} m ou mais" for m in dist if m.get("dist_min")]
    rotulos = {"calibre": "Calibre certo", "atrair": "Atrair (chamador/cheiro)", "nao_detectado": "Sem ser percebido",
               "sem_torre": "Sem torre/espera", "marcar": "Marcar com binóculo", "genetica": "Genética alta"}
    chips += [rotulos[t] for t in tipos if t in rotulos]
    nomes_arma = {"arco": "Arco ou besta", "espingarda": "Espingarda", "rifle": "Rifle", "curta_arma": "Arma curta"}
    chips += [nomes_arma[a] for a in armas if a in nomes_arma]
    return {"grupos": grupos, "qualquer": qualquer or not grupos, "tipos": tipos, "armas": armas,
            "dist_min": min((m["dist_min"] for m in dist), default=0),
            "chips": chips}


def mochila(dados, calibres, equip, lida, missoes, nome_especie, grupo_de, grupo_nome):
    """Itens que você tem, o que está na mochila e o que serve para as missões escolhidas."""
    req = requisitos_missoes(missoes, grupo_nome)
    comprados = {b["id"] for b in equip.get("comprados", [])}
    itens = dados.get("itens", [])
    por_def = {c.get("item"): c for c in itens}
    por_id = {c.get("id"): c for c in itens}
    img = lambda n: f"/api/img/{n}" if n else None

    # espécies (tags) de cada grupo, pela tabela de calibres do jogo
    especies_grupo = {}
    for linha in calibres:
        g = grupo_de(linha.get("animal"))[0]
        especies_grupo.setdefault(g, []).append(linha)
    # espécie escolhida (Mochila) vale só ela; contrato de grupo vale o grupo todo
    alvo_especies = [m["especie"] for m in missoes if m.get("especie")]
    grupos_contrato = [m.get("grupo") for m in missoes if m.get("grupo") and not m.get("especie")]
    # cada alvo (espécie escolhida ou grupo de um contrato) é coberto à parte: o setup inteiro
    # (2 armas, cada uma com a sua munição) é que precisa cobrir todos, não cada munição sozinha
    alvos_u = []
    for g in dict.fromkeys(grupos_contrato):
        alvos_u.append({"chave": "g:" + g, "nome": grupo_nome(g), "linhas": especies_grupo.get(g, [])})
    for t in dict.fromkeys(alvo_especies):
        nome = nome_especie(t) or t.split(".")[-1]
        linhas = [l for l in calibres if _casa_tag(l.get("animal"), t)]
        mesmo = next((u for u in alvos_u if u["nome"] == nome), None)   # mesma espécie em outra reserva: um alvo só
        if mesmo:
            mesmo["linhas"] += [l for l in linhas if l not in mesmo["linhas"]]
            mesmo.setdefault("tags", []).append(t)
        else:
            alvos_u.append({"chave": t, "nome": nome, "linhas": linhas, "tags": [t]})

    def _casa_cal(p, cal, exato):
        # munição (exato): a tabela lista a própria carga ou o "pai" dela (Shell.12G.Bird vale para Shell.12G.Bird.Medium)
        # calibre da arma: a arma lista o "pai" (12G) e aceita qualquer carga dele
        return p == cal or cal.startswith(p + ".") or (not exato and p.startswith(cal + "."))

    def cobre(cal, exato=False):
        """Chaves dos alvos em que esse calibre (arma) ou essa munição (exato) é permitido."""
        if not cal:
            return set()
        return {u["chave"] for u in alvos_u if any(_casa_cal(p, cal, exato) for l in u["linhas"] for p in l.get("compativeis", []))}

    def calibre_serve(cal, exato=False):
        if alvos_u:
            return bool(cobre(cal, exato))
        return any(_casa_cal(p, cal, exato) for l in calibres for p in l.get("compativeis", []))

    nome_alvo = {u["chave"]: u["nome"] for u in alvos_u}

    def tipo_arma(t):
        t = t or ""
        return "arco" if ("Bow" in t or "Crossbow" in t) else ("espingarda" if "Shotgun" in t else "rifle")

    def arma_serve(c):
        cals = calibres_item(c)
        boas = [x for x in cals if calibre_serve(x)]
        motivo = []
        if not boas:
            return False, "nenhum calibre desta arma é permitido para o alvo", []
        ta = tipo_arma(c.get("tipo"))
        exigida = req.get("armas") or set()
        nome_t = {"arco": "arco", "espingarda": "espingarda", "rifle": "rifle"}.get(ta, ta)
        if exigida and not ({"arco": "arco", "espingarda": "espingarda", "rifle": "rifle"}.get(ta) in exigida
                            or ("curta_arma" in exigida and "Handgun" in (c.get("tipo") or ""))):
            return False, f"o contrato pede {', '.join(sorted(exigida)).replace('curta_arma', 'arma curta')}, não {nome_t}", boas
        if req["dist_min"] >= 300 and ta != "rifle":
            return False, "tiro longo pede rifle", boas
        if req["dist_min"] >= 100 and ta == "arco":
            return False, "arco não alcança essa distância", boas
        if alvos_u:
            cob = set().union(*(cobre(x) for x in boas))
            motivo.append("serve para " + ", ".join(nome_alvo[k] for k in nome_alvo if k in cob))
        else:
            motivo.append("calibre " + ", ".join(nome_calibre(x) for x in boas))
        return True, " · ".join(motivo), boas

    na_mochila = {i["item"]: i for i in (lida or {}).get("itens", [])} or \
        {m["item"]: {"item": m["item"], "tipo": m.get("tipo"), "idx": None} for m in equip.get("mochila", [])}
    municao_atual = (lida or {}).get("municao") or {}
    if not isinstance(municao_atual, dict):
        municao_atual = {}

    possuidos = []
    for c in itens:
        tipo = c.get("tipo") or ""
        if c.get("desativado") or not (c["id"] in comprados or c.get("padrao") or c.get("item") in na_mochila):
            continue
        if not (tipo.startswith("Inventory.") or tipo.endswith("Attachments.Ammo")):
            continue
        d = {"id": c["id"], "item": c.get("item"), "nome": c.get("nome") or c["id"], "imagem": img(c.get("icone")),
             "tipo": tipo, "na_mochila": c.get("item") in na_mochila}
        if tipo.startswith("Inventory.Weapon"):
            d["grupo"], d["slot"] = "Armas", "Inventory.Weapon"
            d["serve"], d["motivo"], boas = arma_serve(c)
            d["calibres"] = [{"id": x, "nome": nome_calibre(x), "serve": x in boas} for x in calibres_item(c)]
            atual = municao_atual.get(c["id"])
            if isinstance(atual, dict) or atual is False:
                atual = None
            if isinstance(atual, list):
                atual = next((x for x in atual if (por_id.get(x) or {}).get("tipo", "").endswith("Attachments.Ammo")), None)
            if atual:
                d["municao_atual"] = atual.split(":")[-1]
        elif tipo.endswith("Attachments.Ammo"):
            cals = calibres_item(c)
            d["grupo"], d["slot"] = "Munição", None
            d["calibre"] = cals[0] if cals else None
            d["serve"] = bool(cals) and calibre_serve(cals[0], True)
            d["cobre"] = sorted(cobre(d["calibre"], True)) if alvos_u else []
            d["motivo"] = ("serve para " + ", ".join(nome_alvo[k] for k in nome_alvo if k in d["cobre"])) if d["cobre"] \
                else ("permitido para o alvo" if d["serve"] else "não permitido para o alvo")
        else:
            papel, atrai = _papel_objeto(c.get("item"), tipo)
            d["slot"] = "Inventory.GPS" if papel == "gps" else "Inventory.Objects"
            d["grupo"] = {"chamador": "Chamadores", "isca": "Iscas de cheiro", "chamariz": "Chamarizes", "odor": "Disfarce de odor",
                          "vento": "Vento", "esconderijo": "Esconderijos", "telemetro": "Telêmetros", "binoculo": "Binóculos",
                          "gps": "GPS"}.get(papel, "Outros")
            d["papel"] = papel
            alvo_atrai = [g for g in atrai if g in grupos_contrato]
            if alvo_especies and atrai_tags(c.get("item")):
                if any(_casa_tag(t, e) for t in atrai_tags(c.get("item")) for e in alvo_especies):
                    alvo_atrai = alvo_atrai or atrai
            if atrai:
                d["serve"] = bool(alvo_atrai) or (not req["grupos"] and "atrair" in req["tipos"])
                d["motivo"] = ("atrai " + ", ".join(grupo_nome(g) for g in (alvo_atrai or atrai)))
            elif papel in ("odor", "vento", "esconderijo"):
                d["serve"] = bool({"nao_detectado", "atrair"} & req["tipos"])
                d["motivo"] = "ajuda a não ser percebido"
            elif papel == "telemetro":
                d["serve"] = "distancia" in req["tipos"]
                d["motivo"] = "mede a distância do tiro"
            elif papel in ("binoculo", "gps"):
                d["serve"], d["motivo"] = True, "essencial"
            else:
                d["serve"], d["motivo"] = False, ""
            if not missoes and papel not in ("binoculo", "gps"):
                d["serve"] = None          # sem contrato: nada a cobrar dos equipamentos
        possuidos.append(d)

    # acessórios (miras, silenciadores, freios de boca, bipé) que você tem
    acessorios_seus = [c for c in itens if (c.get("tipo") or "").startswith(PREFIXO_ACESSORIO) and not c["tipo"].endswith(".Ammo")
                       and c.get("compat") and not c.get("desativado") and (c["id"] in comprados or c.get("padrao"))]
    ids_seus_ac = {c["id"] for c in acessorios_seus}
    acessorios_venda = [c for c in itens if (c.get("tipo") or "").startswith(PREFIXO_ACESSORIO) and not c["tipo"].endswith(".Ammo")
                        and not c.get("desativado") and c["id"] not in ids_seus_ac and (c.get("preco") or 0) > 0
                        and "Credits" in (c.get("moeda") or "Currency.Credits")]
    # munição de cada arma: a que você tem e que serve
    municoes = [p for p in possuidos if p["grupo"] == "Munição"]
    for a in possuidos:
        if a["grupo"] != "Armas":
            continue
        ids_cal = [x["id"] for x in a["calibres"]]
        cabe = lambda c: bool(c) and any(c == w or c.startswith(w + ".") or w.startswith(c + ".") for w in ids_cal)
        opcoes = [m for m in municoes if cabe(m.get("calibre"))]
        opcoes.sort(key=lambda m: (not m["serve"], -len(m.get("cobre") or []), m["nome"]))
        a["municoes"] = [{"id": m["id"], "nome": m["nome"], "serve": m["serve"], "atual": m["id"] == a.get("municao_atual"),
                          "cobre": m.get("cobre") or [],
                          "especies": especies_da_carga(m.get("calibre"), calibres, nome_especie)} for m in opcoes]
        # o que esta arma consegue cobrir com a munição que você tem
        a["cobre"] = sorted(set().union(*(set(m["cobre"]) for m in a["municoes"]))) if a["municoes"] else []
        a["acessorios"] = acessorios_da_arma(por_id.get(a["id"]) or {}, municao_atual.get(a["id"]), acessorios_seus, req, por_id, acessorios_venda)

    # sugestão de mochila
    slots = dict((lida or {}).get("slots") or {})
    slots.setdefault("Inventory.Weapon", 2)
    slots.setdefault("Inventory.Objects", 6)
    slots.setdefault("Inventory.GPS", 1)

    def cargas(p):
        m = re.search(r"×\s*(\d+)", p["nome"])
        return int(m.group(1)) if m else 0

    def melhor(lista, n):
        lista = sorted(lista, key=lambda p: (not p["serve"], not p["na_mochila"], -cargas(p), p["nome"]))
        return lista[:n]

    armas_ok = [p for p in possuidos if p["grupo"] == "Armas" and p["serve"]]
    municao_sug = {}
    if alvos_u:
        # escolhe arma + munição que cobrem mais alvos ainda descobertos, uma vaga de arma por vez
        armas, falta = [], {u["chave"] for u in alvos_u if u["linhas"]}
        for _ in range(int(slots["Inventory.Weapon"] or 0)):
            melhor_par = None
            for a in armas_ok:
                if a in armas:
                    continue
                for m in a.get("municoes") or []:
                    ganho = len(set(m["cobre"]) & falta)
                    chave = (ganho, len(m["cobre"]), a["na_mochila"], m["atual"], cargas(a))
                    if ganho and (melhor_par is None or chave > melhor_par[0]):
                        melhor_par = (chave, a, m)
            if not melhor_par:
                break
            _, a, m = melhor_par
            armas.append(a)
            municao_sug[a["id"]] = m["id"]
            falta -= set(m["cobre"])
        # sobrou vaga: completa com a melhor arma que serve
        for a in melhor(armas_ok, slots["Inventory.Weapon"]):
            if len(armas) < int(slots["Inventory.Weapon"] or 0) and a not in armas:
                armas.append(a)
    else:
        armas = melhor(armas_ok, slots["Inventory.Weapon"])
    objetos = []
    prioridade = ["binoculo", "chamador", "isca", "chamariz", "telemetro", "odor", "esconderijo", "vento"]
    for papel in prioridade:
        cand = [p for p in possuidos if p.get("papel") == papel and p["serve"]]
        quantos = 1 if papel in ("binoculo", "telemetro", "odor", "esconderijo", "vento") else 2
        for p in melhor(cand, quantos):
            if len(objetos) < slots["Inventory.Objects"] and p not in objetos:
                objetos.append(p)
    for a in armas:
        if a["id"] in municao_sug:
            continue
        boa = next((m for m in a["municoes"] if m["serve"] and m["atual"]), None) or next((m for m in a["municoes"] if m["serve"]), None)
        if boa:
            municao_sug[a["id"]] = boa["id"]
    for p in possuidos:
        p["sugerido"] = p in armas or p in objetos or p["id"] in municao_sug.values()

    por_item = {x["item"]: x for x in possuidos}
    mochila_atual = []
    for it, info in na_mochila.items():
        c = por_def.get(it) or {}
        p = por_item.get(it)
        e = {"item": it, "tipo": info.get("tipo"), "idx": info.get("idx"), "nome": c.get("nome") or it.split(":")[-1].replace("ID_", "").replace("_", " "),
             "imagem": img(c.get("icone")), "serve": p["serve"] if p else None, "motivo": p["motivo"] if p else "",
             "grupo": p["grupo"] if p else None, "id": c.get("id")}
        if p and p["grupo"] == "Armas":
            e["municoes"], e["calibres"], e["municao_atual"] = p.get("municoes", []), p.get("calibres", []), p.get("municao_atual")
            e["acessorios"] = p.get("acessorios", [])
        mochila_atual.append(e)
    mochila_atual.sort(key=lambda x: (TIPOS_MOCHILA.index(x["tipo"]) if x["tipo"] in TIPOS_MOCHILA else 9, x["idx"] if x["idx"] is not None else 99))

    # cobertura do setup que está na mochila: arma + a munição carregada nela
    cobertos = {}
    for e in mochila_atual:
        if e.get("grupo") == "Armas":
            m = next((x for x in e.get("municoes") or [] if x.get("atual")), None)
            for k in (m or {}).get("cobre", []):
                cobertos.setdefault(k, []).append(e["nome"])
    alvos_saida = [{"chave": u["chave"], "tags": u.get("tags", []), "nome": u["nome"], "coberta": u["chave"] in cobertos,
                    "por": cobertos.get(u["chave"], []), "sem_dados": not u["linhas"]} for u in alvos_u]
    # em cada arma da mochila: o que cada munição acrescenta além do que as outras armas já cobrem
    for e in mochila_atual:
        if e.get("grupo") != "Armas":
            continue
        outras = set()
        for o in mochila_atual:
            if o is not e and o.get("grupo") == "Armas":
                m = next((x for x in o.get("municoes") or [] if x.get("atual")), None)
                outras |= set((m or {}).get("cobre", []))
        novas = []
        for m in e.get("municoes") or []:
            m2 = dict(m)
            m2["ganha"] = [nome_alvo[k] for k in nome_alvo if k in set(m["cobre"]) - outras]
            m2["cobre_nomes"] = [nome_alvo[k] for k in nome_alvo if k in m["cobre"]]
            novas.append(m2)
        novas.sort(key=lambda m: (not m["serve"], -len(m["ganha"]), -len(m["cobre"]), m["nome"]))
        e["municoes"] = novas

    grupos_ordem = ["Armas", "Munição", "Chamadores", "Iscas de cheiro", "Chamarizes", "Binóculos", "Telêmetros",
                    "Disfarce de odor", "Esconderijos", "Vento", "GPS", "Outros"]
    possuidos.sort(key=lambda p: (grupos_ordem.index(p["grupo"]) if p["grupo"] in grupos_ordem else 99, not p["serve"], p["nome"]))
    sugestao = {"armas": [a["item"] for a in armas], "objetos": [o["item"] for o in objetos], "municao": municao_sug}
    return {
        "missoes": [{"id": m["id"], "titulo": m["titulo"], "descricao": m.get("descricao")} for m in missoes],
        "requisitos": req["chips"], "slots": slots, "lida_ts": (lida or {}).get("ts"), "mochila": mochila_atual,
        "possuidos": possuidos, "sugestao": sugestao, "alvos": alvos_saida,
        "plano": plano_mochila(sugestao, lida, slots, por_def, possuidos),
    }


PREFIXO_ACESSORIO = "Cosmetics.Weapons.Attachments."
ENCAIXES = [("Cosmetics.Weapons.Attachments.Scope", "Mira"), ("Cosmetics.Weapons.Attachments.FrontBarrel", "Ponta do cano"),
            ("Cosmetics.Weapons.Attachments.UnderBarrel", "Bipé")]


def _zoom_max(nome):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+)\s*x", nome or "")
    return int(m.group(2)) if m else 1


def acessorios_da_arma(arma, montados, seus, req, por_id, a_venda=()):
    """Encaixes que a arma aceita, o que está montado em cada um e as opções que você tem."""
    compat = [t for t in (arma.get("compat") or []) if t.startswith(PREFIXO_ACESSORIO)]
    montados = montados if isinstance(montados, list) else []
    img = lambda n: f"/api/img/{n}" if n else None
    saida = []
    for base, nome in ENCAIXES:
        aceitos = [t for t in compat if t == base or t.startswith(base + ".")]
        if not aceitos:
            continue
        cabe = lambda c: any(c["tipo"] == t or c["tipo"].startswith(t + ".") for t in aceitos)
        opcoes = [c for c in seus if cabe(c)]
        atual = next((m for m in montados if (por_id.get(m) or {}).get("tipo", "").startswith(base)), None)
        if atual and not any(c["id"] == atual for c in opcoes) and por_id.get(atual):
            opcoes.append(por_id[atual])          # montado na arma, mesmo que não apareça como comprado

        def recomendado(c):
            t = c["tipo"]
            if t.endswith("Suppressor") and "nao_detectado" in req["tipos"]:
                return "silencia o tiro: bom para não ser percebido"
            if base.endswith("Scope") and req["dist_min"] >= 200 and _zoom_max(c.get("nome")) >= 12:
                return f"aumento de até {_zoom_max(c.get('nome'))}x: bom para tiro longo"
            if t.endswith("Bipod") and req["dist_min"] >= 200:
                return "apoio firme para tiro longo"
            return None
        ids_seus = {c["id"] for c in opcoes}
        venda = [c for c in a_venda if cabe(c) and c["id"] not in ids_seus]
        lista = []
        for c in sorted(opcoes, key=lambda c: (c["tipo"], _zoom_max(c.get("nome")), c.get("nome") or "")) + \
                sorted(venda, key=lambda c: (c.get("preco") or 0, c.get("nome") or "")):
            lista.append({"id": c["id"], "nome": c.get("nome") or c["id"], "imagem": img(c.get("icone")),
                          "comprar": c["id"] not in ids_seus, "preco": c.get("preco") or 0, "dlc": DLC.get(c["id"]),
                          "tipo": "Silenciador" if c["tipo"].endswith("Suppressor") else ("Freio de boca" if c["tipo"].endswith("MuzzleBrake")
                                                                                        else ("Bipé" if "Bipod" in c["tipo"] else "Mira")),
                          "atual": c["id"] == atual, "recomendado": recomendado(c)})
        atual_nome = next((o["nome"] for o in lista if o["atual"]), None)
        saida.append({"encaixe": base, "nome": nome, "atual": atual, "atual_nome": atual_nome, "opcoes": lista})
    return saida


def plano_mochila(sug, lida, slots, por_def, possuidos):
    """Trocas mínimas para deixar a mochila como a sugestão: não mexe no que já está certo."""
    if not lida or not lida.get("itens"):
        return []
    nome = lambda it: (por_def.get(it) or {}).get("nome") or it.split(":")[-1]
    itens = lida["itens"]
    plano = []
    for tipo, desejados in (("Inventory.Weapon", sug.get("armas", [])), ("Inventory.Objects", sug.get("objetos", []))):
        n = int(slots.get(tipo) or 0)
        atual = {i["idx"]: i["item"] for i in itens if i.get("tipo") == tipo and isinstance(i.get("idx"), int)}
        presentes = set(atual.values())
        faltam = [x for x in desejados if x not in presentes]
        livres = [k for k in range(n) if k not in atual] + [k for k in range(n) if k in atual and atual[k] not in desejados]
        for item, k in zip(faltam, livres):
            plano.append({"acao": "por", "item": item, "tipo": tipo, "idx": k, "nome": nome(item),
                          "sai": nome(atual[k]) if k in atual else None})
    mun_atual = {p["id"]: p.get("municao_atual") for p in possuidos if p["grupo"] == "Armas"}
    nomes_id = {p["id"]: p["nome"] for p in possuidos}
    for arma, mun in (sug.get("municao") or {}).items():
        if mun_atual.get(arma) != mun:
            plano.append({"acao": "municao", "arma": arma, "municao": mun, "nome": nomes_id.get(mun, mun),
                          "arma_nome": nomes_id.get(arma, arma)})
    return plano


# ---------------------------------------------------------------- licenças e DLC (lidos do jogo)
LICENCAS = {  # tag da espécie -> (licença na loja, animais por licença, preço) — lido do jogo em 22/11/2026
    "Antelope.Nilgai": ("DA_Nilgai_License", 4, 67), "Antelope.ScimitarOryx": ("DA_ScimitarOryx_License", 4, 48),
    "Bear.Black": ("DA_Bear_Black_License", 6, 66), "Bear.Black.Alaska": ("DA_Bear_Glazier_Black_License", 6, 66),
    "Bear.Brown.Poland": ("DA_Bear_Brown_License", 4, 66), "Bear.Grizzly": ("DA_Bear_Grizzly_License", 4, 66),
    "Bird.Chukar": ("DA_Chukar_License", 15, 32), "Bird.Dove.Mourning": ("DA_MourningDove_License", 10, 20),
    "Bird.Duck.Black": ("DA_Duck_Black_License", 10, 20), "Bird.Duck.Bufflehead": ("DA_Duck_Bufflehead_License", 20, 100),
    "Bird.Duck.Harlequin": ("DA_Duck_Harlequin_License", 20, 100),
    "Bird.Duck.Mallard.Poland": ("DA_Duck_Mallard_License", 10, 20),
    "Bird.Duck.NorthernPintail": ("DA_Duck_NorthernPintail_License", 10, 20),
    "Bird.Duck.NorthernPintail.Alaska": ("DA_Duck_NorthernPintail_Alaska_License", 10, 20),
    "Bird.Duck.Tufted.Poland": ("DA_TuftedDuck_License", 10, 28), "Bird.Goose.Canada": ("DA_Goose_Canada_License", 10, 24),
    "Bird.Goose.Canada.Alaska": ("DA_Goose_Canada_Alaska_License", 10, 24),
    "Bird.Goose.Graylag.Poland": ("DA_GreylagGoose_License", 10, 24),
    "Bird.Grouse.Black.Poland": ("DA_BlackGrouse_License", 10, 28), "Bird.Grouse.Ptarmigan": ("DA_RockPtarmigan_License", 10, 28),
    "Bird.Grouse.Ruffed": ("DA_RuffedGrouse_License", 10, 28), "Bird.Grouse.Sooty": ("DA_SootyGrouse_License", 10, 28),
    "Bird.MontezumaQuail": ("DA_Montezuma_Quail_License", 10, 28),
    "Bird.Partridge.Gray.Poland": ("DA_Partridge_Gray_License", 10, 24), "Bird.Pheasant": ("DA_Pheasant_License", 10, 24),
    "Bird.Pheasant.Poland": ("DA_Pheasant_Poland_License", 10, 24), "Bird.Quail": ("DA_Quail_License", 10, 28),
    "Bird.Teal.GreenWinged": ("DA_Teal_GreenWinged_License", 10, 28),
    "Bird.Turkey.RioGrande": ("DA_Turkey_RioGrande_License", 8, 64), "Bird.Woodcock.Poland": ("DA_Woodcock_License", 10, 32),
    "Bison.Alaska": ("DA_Bison_Alaskan_License", 4, 67), "Bison.American.Plains": ("DA_Bison_American_License", 4, 67),
    "Bison.Poland": ("DA_Bison_European_License", 4, 78), "Boar.Poland": ("DA_Boar_European_License", 8, 64),
    "Canine.Coyote.Plains": ("DA_Coyote_Plains_License", 6, 66), "Deer.BlackSitka": ("DA_SitkaBlacktailDeer_License", 8, 64),
    "Deer.Caribou": ("DA_Caribou_License", 8, 64), "Deer.DesertMule": ("DA_DesertMule_License", 10, 89),
    "Deer.MountainMule": ("DA_MountainMule_License", 8, 89), "Deer.Red.Poland": ("DA_RedDeer_License", 6, 72),
    "Deer.Roe.Poland": ("DA_WesternRoeDeer_License", 8, 64),
    "Deer.WhiteTail.Colorado": ("DA_WhiteTailDeer_Colorado_License", 8, 89),
    "Deer.WhiteTail.Texas": ("DA_WhiteTailDeer_Texas_License", 8, 89), "Elk": ("DA_Elk_License", 4, 48),
    "Feline.Bobcat.Colorado": ("DA_ColoradoBobcat_License", 4, 70), "Feline.Bobcat.Texas": ("DA_TexasBobcat_License", 4, 70),
    "Feline.Cougar": ("DA_Cougar_License", 5, 70), "Feline.Lynx.Alaska": ("DA_CanadaLynx_License", 4, 70),
    "Feline.Lynx.Poland": ("DA_Lynx_License", 4, 70), "Fox.Alaska": ("DA_ArticFox_License", 8, 78),
    "Fox.Red": ("DA_RedFox_License", 6, 48), "Fox.Red.Poland": ("DA_RedFox_Poland_License", 8, 78),
    "Goat.Mountain": ("DA_MountainGoat_License", 10, 10), "Hare.Alaska": ("DA_AlaskanHare_License", 10, 30),
    "Hare.Brown.Poland": ("DA_BrownHare_License", 10, 30), "Hare.JackRabbit": ("DA_Jackrabbit_License", 10, 36),
    "Hare.Snowshoe": ("DA_SnowshoeHare_License", 10, 30), "Marten.Poland": ("DA_PineMarten_Poland_License", 10, 48),
    "Moose.Poland": ("DA_Moose_License", 4, 67), "Peccary.Collared": ("DA_Peccarry_Collared_License", 10, 64),
    "Pig.Feral": ("DA_Pig_Feral_License", 8, 89), "PrairieDog.BlackTail": ("DA_PrairieDog_BlackTail_License", 10, 36),
    "Pronghorn.American": ("DA_Pronghorn_American_License", 6, 76),
    "Rabbit.CottonTail.Colorado": ("DA_Rabbit_CottonTail_Colorado_License", 10, 30),
    "Rabbit.CottonTail.Texas": ("DA_Rabbit_CottonTail_Texas_License", 10, 30),
    "Rabbit.European": ("DA_Rabbit_European_License", 10, 10), "RaccoonDog.Poland": ("DA_RaccoonDog_Poland_License", 6, 92),
    "Sheep.Aoudad": ("DA_Sheep_Aoudad_License", 8, 76), "Sheep.Bighorn.Colorado": ("DA_Sheep_Bighorn_Colorado_License", 8, 76),
    "Sheep.Bighorn.Texas": ("DA_Sheep_Bighorn_Texas_License", 8, 76), "Sheep.Dall": ("DA_DallSheep_License", 8, 76),
    "Sheep.Mouflon.Poland": ("DA_Sheep_Mouflon_License", 8, 76), "Wolf.Gray": ("DA_Wolf_Gray_License", 6, 79),
    "Wolf.Gray.Poland": ("DA_Eurasian_GrayWolf_License", 4, 61),
}
DLC = {"DA_LabradorStoreItem": "MyNaconGift", "DA_FloorStand_Large_TX_Predators_Deluxe": "ApexPredator", "DA_CompositionStand_Small_TX_Bobcat_Deluxe": "ApexPredator", "DA_CompositionStand_Medium_TX_Coyote_Deluxe": "ApexPredator", "DA_LargeCompositionStand_TX_Predators_DeluxeComposition": "ApexPredator", "DA_LargeCompositionStand_TX_MuleDeer_Defense_DeluxeComposition": "ApexPredator", "DA_FloorstandLarge_CO_Bobcat_DeluxeComposition": "ApexPredator", "DA_CornerStandLarge_CO_Predators_DeluxeComposition": "ApexPredator", "DA_SmallCompositionStand_CO_Bobcat_DeluxeComposition": "ApexPredator", "DA_MediumCompositionStand_CO_Predators_DeluxeComposition": "ApexPredator", "DA_LargeCompositionStand_CO_Predators_DeluxeComposition": "ApexPredator", "DA_LargeCompositionStand_CO_Bison_Defense_DeluxeComposition": "ApexPredator", "DA_AmericanFoxHoundStoreItem": "ClassicAmerican", "DA_Winchester_Model1892_ShortRifle_StoreItem": "ClassicAmerican", "D_Cap_VerneyCarron_Woolchap_StoreItem_Orange": "ClassicAmerican", "D_Cap_VerneyCarron_Woolchap_StoreItem_Khaki": "ClassicAmerican", "D_Cap_VerneyCarron_Woolchap_StoreItem_Fox": "ClassicAmerican", "DA_Remington_Model783_StoreItem": "ApexPredator", "D_DogGoggles_RexSpecs_Orange_StoreItem": "ApexPredator", "DA_Remington_870_SPS_SMTP_StoreItem": "ApexPredator", "D_DogVest_Browning_ProtectPro_Orange_StoreItem": "ApexPredator", "PolarisRangerEV_Camo_StoreDataAsset": "ApexPredator", "D_HubCustom_CO_Armory_Fancy": "ApexPredator", "D_HubCustom_CO_Balcony_Fancy": "ApexPredator", "D_HubCustom_CO_Bedroom_Fancy": "ApexPredator", "D_HubCustom_CO_Garage_Fancy": "ApexPredator", "D_HubCustom_CO_Hallway_Fancy": "ApexPredator", "D_HubCustom_CO_Kitchen_Fancy": "ApexPredator", "D_HubCustom_CO_LivingRoom_Fancy": "ApexPredator", "D_HubCustom_CO_Study_Fancy": "ApexPredator", "D_HubCustom_PL_Armory_Fancy": "ApexPredator", "D_HubCustom_PL_Balcony_Fancy": "ApexPredator", "D_HubCustom_PL_Bedroom_Fancy": "ApexPredator", "D_HubCustom_PL_Garage_Fancy": "ApexPredator", "D_HubCustom_PL_Hallway_Fancy": "ApexPredator", "D_HubCustom_PL_Kitchen_Fancy": "ApexPredator", "D_HubCustom_PL_LivingRoom_Fancy": "ApexPredator", "D_HubCustom_PL_Study_Fancy": "ApexPredator", "D_HubCustom_TX_Armory_Fancy": "ApexPredator", "D_HubCustom_TX_Balcony_Fancy": "ApexPredator", "D_HubCustom_TX_Bedroom_Fancy": "ApexPredator", "D_HubCustom_TX_Garage_Fancy": "ApexPredator", "D_HubCustom_TX_Hallway_Fancy": "ApexPredator", "D_HubCustom_TX_Kitchen_Fancy": "ApexPredator", "D_HubCustom_TX_LivingRoom_Fancy": "ApexPredator", "D_HubCustom_TX_Study_Fancy": "ApexPredator", "D_StoreItemAsset_HBC_ArmoryCabinetsSet_b": "ApexPredator", "DA_Caller_Turkey_Bombshell_StoreItem": "ApexPredator", "DA_Bushnell_Fusion_12x50_StoreItem": "ApexPredator"}  # item da loja -> pacote (ContentIdentifier)


def licenca_da_especie(tag, lic_mod, lic_todas):
    """Situação da licença: lic_mod = licencas.json da reserva atual; lic_todas = última leitura de cada reserva."""
    chave = (tag or "").replace("Animals.Types.", "")
    info = LICENCAS.get(chave)
    if not info:
        return None
    loja, maximo, preco = info
    r = {"loja": loja, "max": maximo, "preco": preco, "comprar_aqui": False, "tem": False, "usados": None, "restam": None,
         "ilimitada": False, "reserva": None}
    fontes = ([lic_mod] if lic_mod else []) + [x for x in (lic_todas or {}).values() if x is not lic_mod]
    for f in fontes:
        l = next((x for x in f.get("licencas") or [] if x.get("tag") == tag), None)
        if l:
            r.update(tem=True, usados=l.get("usados") or 0, ilimitada=bool(l.get("ilimitada")), reserva=f.get("mapa"))
            r["restam"] = None if r["ilimitada"] else max(0, maximo - r["usados"])
            break
    if lic_mod and tag in (lic_mod.get("permitidas") or []):
        r["comprar_aqui"] = True
    return r


# ---------------------------------------------------------------- caçada por espécie (Diário de campo)
NOME_TIPO_ARMA = [("CrossBow", "Besta"), ("Crossbow", "Besta"), ("Bow", "Arco"), ("Shotgun", "Espingarda"),
                  ("Handgun", "Arma curta"), ("Pistol", "Arma curta"), ("Revolver", "Arma curta"), ("Rifle", "Rifle")]


def _nome_tipo_arma(t):
    return next((n for k, n in NOME_TIPO_ARMA if k in (t or "")), "Arma")


def _casa_cal(a, b):
    return bool(a and b) and (a == b or a.startswith(b + ".") or b.startswith(a + "."))


def slots_mochila(dados, lida, equip):
    """Os 8 espaços numerados: 1-2 armas, 3-8 equipamentos (e o GPS à parte)."""
    por_def = {c.get("item"): c for c in dados.get("itens", [])}
    img = lambda n: f"/api/img/{n}" if n else None
    sl = dict((lida or {}).get("slots") or {})
    n_arma, n_obj = int(sl.get("Inventory.Weapon") or 2), int(sl.get("Inventory.Objects") or 6)
    itens = (lida or {}).get("itens") or []
    saida = []
    for tipo, n, base in (("Inventory.Weapon", n_arma, 1), ("Inventory.Objects", n_obj, 1 + n_arma)):
        for k in range(n):
            it = next((i for i in itens if i.get("tipo") == tipo and i.get("idx") == k), None)
            c = por_def.get((it or {}).get("item")) or {}
            saida.append({"n": base + k, "tipo": tipo, "idx": k, "item": (it or {}).get("item"), "id": c.get("id"),
                          "nome": c.get("nome") or ((it or {}).get("item") or "").split("ID_")[-1].replace("_", " ") or None,
                          "imagem": img(c.get("icone")), "cargas": (it or {}).get("cargas"), "categoria": c.get("tipo")})
    return saida


def especies_da_carga(carga, calibres, nome_especie):
    """Nomes das espécies em que uma munição (ex.: Inventory.Ammo.Shell.12G.Slug) é permitida."""
    if not carga:
        return []
    nomes = {nome_especie(l.get("animal")) for l in calibres if not (l.get("animal") or "").endswith(".Hub")
             and any(p == carga or carga.startswith(p + ".") for p in l.get("compativeis", []))}
    return sorted(n for n in nomes if n)


def kit_especie(dados, calibres, equip, lida, tag, nome_especie, lic_mod=None, lic_todas=None):
    """Tudo o que serve para caçar uma espécie: balística, armas (com munição e acessórios), chamadores, chamarizes e iscas."""
    animal = next((a for a in dados.get("animais", []) if a.get("tag") == tag), None) or {}
    linha = next((c for c in calibres if c.get("animal") == tag), None) or next((c for c in calibres if _casa_tag(c.get("animal"), tag)), None) or {}
    permitidos = linha.get("compativeis", [])
    comprados = {b["id"] for b in equip.get("comprados", [])}
    itens = dados.get("itens", [])
    por_id = {c.get("id"): c for c in itens}
    img = lambda n: f"/api/img/{n}" if n else None
    lida_itens = (lida or {}).get("itens") or []
    na_mochila_kit = {i.get("item") for i in lida_itens} | {m.get("item") for m in equip.get("mochila", [])}
    tem = lambda c: c["id"] in comprados or bool(c.get("padrao")) or c.get("item") in na_mochila_kit
    n_arma = int(((lida or {}).get("slots") or {}).get("Inventory.Weapon") or 2)
    onde = {}
    for i in lida_itens:
        if i.get("tipo") == "Inventory.Weapon":
            onde[i.get("item")] = 1 + int(i.get("idx") or 0)
        elif i.get("tipo") == "Inventory.Objects":
            onde[i.get("item")] = 1 + n_arma + int(i.get("idx") or 0)
    montados_todos = (lida or {}).get("municao") or {}
    if not isinstance(montados_todos, dict):
        montados_todos = {}
    cab = (animal.get("grupo") or "").split(".")[-1]
    ave = cab in ("Waterfowl", "UplandGame", "UplandBirds", "Birds", "Bird")
    pequeno = cab == "SmallGame"

    def serve_especie(cal, exato=False):
        # munição (exato): a própria carga ou o "pai" dela na tabela; arma: qualquer carga do calibre
        return any(p == cal or cal.startswith(p + ".") or (not exato and p.startswith(cal + ".")) for p in permitidos)

    # munição que você tem
    municoes = []
    for c in itens:
        if not (c.get("tipo") or "").endswith("Attachments.Ammo") or c.get("desativado"):
            continue
        cals = calibres_item(c)
        if cals:
            municoes.append({"id": c["id"], "nome": c.get("nome") or c["id"], "calibre": cals[0], "tem": tem(c),
                             "serve": serve_especie(cals[0], True), "preco": c.get("preco"), "imagem": img(c.get("icone"))})

    acessorios_seus = [c for c in itens if (c.get("tipo") or "").startswith(PREFIXO_ACESSORIO) and not c["tipo"].endswith(".Ammo")
                       and c.get("compat") and not c.get("desativado") and tem(c)]
    req = {"tipos": set(), "dist_min": 0}

    armas = []
    vistos = set()
    for c in itens:
        t = c.get("tipo") or ""
        if not t.startswith("Inventory.Weapon") or c.get("desativado") or c.get("item") in vistos:
            continue
        cals = calibres_item(c)
        boas = [x for x in cals if serve_especie(x)]
        if not boas:
            continue
        vistos.add(c.get("item"))
        cargas_ok = [p for p in permitidos if any(_casa_cal(p, x) for x in boas)]   # ex.: Shell.12G -> Shell.12G.Bird
        tipo = _nome_tipo_arma(t)
        opcoes = [m for m in municoes if m["serve"] and any(_casa_cal(m["calibre"], w) for w in boas)]
        opcoes.sort(key=lambda m: (not m["tem"], m["nome"]))
        montados = montados_todos.get(c["id"]) if c.get("item") in onde else None
        atual_mun = next((x for x in (montados or []) if (por_id.get(x) or {}).get("tipo", "").endswith("Attachments.Ammo")), None)
        # indicada: espingarda com chumbo para aves; calibre leve para caça miúda; rifle para caça grossa
        if ave:
            indicada = tipo == "Espingarda" and any("Bird" in x for x in cargas_ok)
        elif pequeno:
            indicada = any(k in x for x in cargas_ok for k in (".22.", ".22-", ".223", "Bird", "Buck", "Arrow.350", "Bolt.350"))
        else:
            indicada = tipo in ("Rifle", "Arco", "Besta")
        a = {"id": c["id"], "item": c.get("item"), "nome": c.get("nome") or c["id"], "imagem": img(c.get("icone")), "tipo": tipo,
             "calibres": [nome_calibre(x) for x in boas], "tem": tem(c), "slot": onde.get(c.get("item")), "indicada": indicada,
             "preco": c.get("preco"), "moeda": "créditos" if "Credits" in (c.get("moeda") or "") else "pontos de campo", "dlc": DLC.get(c["id"]),
             "municoes": [{"id": m["id"], "nome": m["nome"], "tem": m["tem"], "atual": m["id"] == atual_mun,
                           "especies": especies_da_carga(m["calibre"], calibres, nome_especie)} for m in opcoes],
             "municao_atual": atual_mun, "montados_conhecidos": montados is not None, "cargas": cargas_ok,
             "municao_atual_nome": (por_id.get(atual_mun) or {}).get("nome") if atual_mun else None,
             "municao_atual_serve": any(m["id"] == atual_mun for m in opcoes) if atual_mun else None}
        if a["tem"]:
            a["acessorios"] = acessorios_da_arma(c, montados, acessorios_seus, req, por_id)
            if montados is None:
                for e in a["acessorios"]:
                    e["atual"] = e["atual_nome"] = None
                    for o in e["opcoes"]:
                        o["atual"] = False
        armas.append(a)
    armas.sort(key=lambda a: (not a["tem"], a["slot"] is None, not a["indicada"], a["tipo"], a["nome"]))

    objetos = []
    for c in itens:
        t = c.get("tipo") or ""
        if c.get("desativado") or not t.startswith("Inventory.Objects"):
            continue
        alvo = atrai_tags(c.get("item"))
        if not alvo or not any(_casa_tag(x, tag) for x in alvo):
            continue
        n = c.get("item") or ""
        papel = "chamariz" if "Decoy" in n else ("isca" if "Spray" in n else "chamador")
        efeito = {"chamador": "Atrai a espécie até você (alcance de uns 500 m)",
                  "chamariz": "Deixa a espécie mais calma perto de você",
                  "isca": "Isca de cheiro: atrai pelo faro, a favor do vento"}[papel]
        objetos.append({"id": c["id"], "item": n, "nome": c.get("nome") or c["id"], "imagem": img(c.get("icone")), "papel": papel,
                        "efeito": efeito, "tem": tem(c), "slot": onde.get(n), "preco": c.get("preco"), "dlc": DLC.get(c["id"]),
                        "cargas": c.get("cargas") if (c.get("cargas") or 0) > 1 else None})
    ordem = {"chamador": 0, "chamariz": 1, "isca": 2}
    objetos.sort(key=lambda o: (ordem[o["papel"]], not o["tem"], o["slot"] is None, o["nome"]))

    tipos_bal = {"Bullet": "Balas de rifle", "Shell": "Cartuchos de espingarda", "Arrow": "Flechas", "Bolt": "Virotes"}
    balistica = []
    for p in permitidos:
        partes = p.split(".")
        grupo = tipos_bal.get(partes[2] if len(partes) > 2 else "", "Outros")
        n_armas = sum(1 for a in armas if a["tem"] and p in a["cargas"])
        balistica.append({"id": p, "nome": nome_calibre(p), "grupo": grupo, "especies": especies_da_carga(p, calibres, nome_especie),
                          "tem_municao": any(m["tem"] and m["calibre"] == p for m in municoes), "armas_suas": n_armas})
    return {
        "tag": tag, "nome": nome_especie(tag) or animal.get("titulo") or tag, "imagem": img(animal.get("imagem")),
        "cabecalho": CABECALHOS.get(cab, cab or "Animais"),
        "balistica": balistica, "proibidos": [nome_calibre(x) for x in linha.get("incompativeis", [])],
        "armas": armas, "objetos": objetos, "slots": slots_mochila(dados, lida, equip), "lida": bool(lida_itens),
        "licenca": licenca_da_especie(tag, lic_mod, lic_todas),
        "licenca_imagem": next((img(l.get("imagem")) for e in dados.get("especies", []) if e.get("tag") == tag
                                for l in e.get("licencas") or [] if l.get("imagem")), None),
    }


def plano_kit(kit, escolha):
    """Lista de comandos para o mod a partir da escolha feita na tela (arma, espaço, munição, acessórios, objetos).
    escolha = {"arma": id_loja, "espaco": 1|2, "municao": id, "acessorios": {encaixe: id|""}, "objetos": [{"item":..., "espaco": n}]}"""
    linhas, resumo = [], []
    slots = kit["slots"]
    arma = next((a for a in kit["armas"] if a["id"] == escolha.get("arma") and a["tem"]), None)
    if arma:
        n = int(escolha.get("espaco") or arma.get("slot") or 1)
        destino = next((s for s in slots if s["n"] == n and s["tipo"] == "Inventory.Weapon"), None)
        if destino and arma["slot"] != n:
            if arma["slot"]:
                linhas.append(f"mochila tirar {arma['item']}")
            linhas.append(f"mochila por {arma['item']} Inventory.Weapon {destino['idx']}")
            resumo.append({"onde": f"Espaço {n}", "sai": destino.get("nome"), "entra": arma["nome"]})
        mun = escolha.get("municao")
        if mun and mun != arma.get("municao_atual") and any(m["id"] == mun and m["tem"] for m in arma["municoes"]):
            linhas.append(f"mochila municao {arma['id']} {mun}")
            resumo.append({"onde": f"Munição · {arma['nome']}", "entra": next(m["nome"] for m in arma["municoes"] if m["id"] == mun)})
        for enc in arma.get("acessorios") or []:
            quer = (escolha.get("acessorios") or {}).get(enc["encaixe"])
            if quer is None:
                continue
            if quer == "":
                if enc.get("atual"):
                    linhas.append(f"mochila tirar_acessorio {arma['id']} {enc['atual']}")
                    resumo.append({"onde": enc["nome"], "sai": enc.get("atual_nome"), "entra": "nada"})
            elif quer != enc.get("atual") and any(o["id"] == quer for o in enc["opcoes"]):
                linhas.append(f"mochila acessorio {arma['id']} {quer}")
                resumo.append({"onde": enc["nome"], "entra": next(o["nome"] for o in enc["opcoes"] if o["id"] == quer)})
    usados = set()
    for o in escolha.get("objetos") or []:
        obj = next((x for x in kit["objetos"] if x["item"] == o.get("item") and x["tem"]), None)
        if not obj or obj["slot"]:
            continue
        n = int(o.get("espaco") or 0)
        destino = next((s for s in slots if s["n"] == n and s["tipo"] == "Inventory.Objects"), None)
        if not destino or n in usados:
            continue
        usados.add(n)
        linhas.append(f"mochila por {obj['item']} Inventory.Objects {destino['idx']}")
        resumo.append({"onde": f"Espaço {n}", "sai": destino.get("nome"), "entra": obj["nome"]})
    return linhas, resumo


def sugestao_kit(kit, espaco_arma=None):
    """'Montar para esta espécie': melhor arma sua, munição, acessórios como estão, e chamadores/chamarizes/iscas nos espaços livres
    (ou no lugar de itens que não servem para a espécie). Binóculo e telêmetro não saem."""
    suas = [a for a in kit["armas"] if a["tem"] and a["municoes"] and any(m["tem"] for m in a["municoes"])]
    suas.sort(key=lambda a: (a["slot"] is None, not a["indicada"]))
    escolha = {"objetos": []}
    if suas:
        a = suas[0]
        escolha["arma"] = a["id"]
        if a["slot"]:
            escolha["espaco"] = a["slot"]
        else:
            armas_mochila = {s["n"]: s for s in kit["slots"] if s["tipo"] == "Inventory.Weapon"}
            serve = {x["slot"] for x in kit["armas"] if x["slot"]}
            livre = next((n for n, s in armas_mochila.items() if not s["item"]), None)
            ruim = next((n for n, s in armas_mochila.items() if s["item"] and n not in serve), None)
            escolha["espaco"] = espaco_arma or livre or ruim or max(armas_mochila or {2: 0})
        boa = next((m for m in a["municoes"] if m["tem"] and m["atual"]), None) or next((m for m in a["municoes"] if m["tem"]), None)
        if boa:
            escolha["municao"] = boa["id"]
    objs = kit["slots"]
    ja = {o["item"] for o in kit["objetos"] if o["slot"]}
    servem = {o["item"] for o in kit["objetos"]}
    livres = [s["n"] for s in objs if s["tipo"] == "Inventory.Objects" and not s["item"]]
    trocaveis = [s["n"] for s in objs if s["tipo"] == "Inventory.Objects" and s["item"] and s["item"] not in servem
                 and not any(k in (s.get("categoria") or "") for k in ("Opticals", "Blind"))
                 and not any(k in (s["item"] or "") for k in ("ScentKiller", "WindPowder"))]
    papeis = set()
    for o in kit["objetos"]:
        if not o["tem"] or o["item"] in ja or o["papel"] in papeis:
            continue
        espaco = livres.pop(0) if livres else (trocaveis.pop(0) if trocaveis else None)
        if not espaco:
            break
        papeis.add(o["papel"])
        escolha["objetos"].append({"item": o["item"], "espaco": espaco})
    return escolha


# ---------------------------------------------------------------- o que dá para caçar com o que você tem (contratos)
def capacidade(dados, calibres, equip, nivel, grupo_de, tipo_arma):
    """Por grupo de animal da reserva: tipos de arma com que você consegue caçar (arma sua + munição sua permitida)
    e se você tem chamador/chamariz/isca para ele. Jogo novo = só o que você já tem."""
    comprados = {b["id"] for b in equip.get("comprados", [])}
    tem = lambda c: c["id"] in comprados or bool(c.get("padrao"))
    itens = [c for c in dados.get("itens", []) if not c.get("desativado") and tem(c)]
    municoes = [calibres_item(c)[0] for c in itens if (c.get("tipo") or "").endswith("Attachments.Ammo") and calibres_item(c)]
    armas = [(tipo_arma(c.get("tipo")), calibres_item(c)) for c in itens if (c.get("tipo") or "").startswith("Inventory.Weapon")]
    objetos = [c for c in itens if (c.get("tipo") or "").startswith("Inventory.Objects")]
    nivel = (nivel or "").lower().split("_")[0]
    r = {}
    for a in dados.get("animais", []):
        tag = a.get("tag") or ""
        if not tag or tag.endswith(".Hub") or not (nivel and any(nivel in (m or "").lower() for m in a.get("mapas") or [])):
            continue
        g = grupo_de(tag)[0]
        if g == "outro":
            continue
        linha = next((l for l in calibres if l.get("animal") == tag), None) or next((l for l in calibres if _casa_tag(l.get("animal"), tag)), None)
        permitidos = (linha or {}).get("compativeis", [])
        ok_mun = [m for m in municoes if any(p == m or p.startswith(m + ".") for p in permitidos)]
        info = r.setdefault(g, {"armas": set(), "atrair": False, "especies": []})
        info["especies"].append(tag)
        for t, cals in armas:
            if any(_casa_cal(m, w) for m in ok_mun for w in cals):
                info["armas"].add(t)
        if any(_casa_tag(x, tag) for o in objetos for x in atrai_tags(o.get("item"))):
            info["atrair"] = True
    tem_telemetro = any("RangeFinder" in (c.get("tipo") or "") for c in objetos)
    return {"grupos": {g: {"armas": sorted(v["armas"]), "atrair": v["atrair"]} for g, v in r.items() if v["armas"]},
            "telemetro": tem_telemetro}
