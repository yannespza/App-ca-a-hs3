"""Gerador de contratos do Velho Earl, sem IA.

Cada contrato combina um ALVO (uma espécie da reserva, qualquer animal, espécies diferentes, marcar no binóculo
ou ir até lugares do mapa) com até três CONDIÇÕES (distância, um tiro só, tipo de arma, genética, sem torre,
atraído por chamariz, sem ser percebido, calibre certo, macho/fêmea). Tudo o que vai no contrato pode ser
conferido pelos eventos que o mod manda (abate, marcação, posição), então o progresso conta sozinho.
"""
import random
import time
import uuid

NPC = {
    "id": "earl",
    "nome": "Earl Whitaker",
    "apelido": "Velho Earl",
    "funcao": "Guia de caça e contratador da região",
    "retrato": "/img/npc_earl.png",
    "frase": "O vento não mente, garoto. Quem mente é caçador apressado.",
}

ESTADOS_CALMOS = {1, 2, 4, 256, 512}   # parado, vagando, andando, comendo, dormindo
# o jogo junta o estado com outras marcas (bits acima de 4096). Contam só os 12 bits de baixo:
# fugindo 8, espreitando 16, atacando 32, investida 64, investigando 1024, acuado 2048 = percebeu você
ESTADOS_ALERTA = 8 | 16 | 32 | 64 | 1024 | 2048


def nao_percebeu(estado):
    """O animal ainda não tinha percebido você quando levou o primeiro tiro?"""
    if not isinstance(estado, int) or estado < 0:
        return False
    base = estado & 4095
    return not (base & ESTADOS_ALERTA) and bool(base & (1 | 2 | 4 | 128 | 256 | 512))

# dificuldade (créditos por animal) de cada grupo
VALOR_GRUPO = {"pato": 220, "ganso": 260, "peru": 380, "faisao": 220, "codorna": 180, "pomba": 160, "antilope": 650,
               "felino": 900, "roedor": 150, "cervo": 450, "alce": 800, "antilocapra": 520, "porco": 380, "coiote": 420,
               "lobo": 850, "raposa": 380, "coelho": 160, "urso": 1100, "carneiro": 700, "bisao": 1000, "outro": 350}
AVES = {"pato", "ganso", "peru", "faisao", "codorna", "pomba"}
PEQUENOS = AVES | {"roedor", "coelho"}

# ------------------------------------------------------------------ textos
TITULOS_GRUPO = [
    "Praga de {g}", "Controle de {g}", "{G} no milharal", "Encomenda do açougue: {g}", "Pedido do fazendeiro",
    "Superpopulação de {g}", "Censo e controle: {g}", "{G} na cerca nova", "Mesa farta", "Carne para o inverno",
    "O fazendeiro não dorme", "Estrago na plantação", "Rastro fresco de {g}", "Problema na represa",
    "A cooperativa paga bem", "Equilíbrio da reserva", "Pedido do restaurante da vila", "Abate de manejo",
    "{G} demais, pasto de menos", "Trabalho de guarda-caça",
]
TITULOS_QUALQUER = [
    "Câmara fria vazia", "Dia de caça", "Carne para o posto", "Caçada livre", "Despensa do acampamento",
    "Feira de domingo", "Encomenda variada", "Saindo para o mato", "O que aparecer", "Sorte de principiante",
]
TITULOS_VARIEDADE = ["Coleção do museu", "Variedade é tudo", "Bicho de todo tipo", "Inventário da reserva", "Catálogo vivo"]
TITULOS_COND = {
    "longa": ["Tiro de elite", "Olho de águia", "Lá do outro lado do vale", "Precisão a distância", "Mão firme, mira longa",
              "Atirador de cumeeira", "Vento e queda", "O tiro da sua vida"],
    "media": ["Olho de lince", "Distância de respeito", "Tiro medido", "Nem perto, nem longe"],
    "curta": ["Distância segura", "Sem encostar no bicho", "Espaço de respeito", "Tiro com folga"],
    "um_tiro": ["Um tiro, um abate", "Sem segunda chance", "Bala única", "Tiro certeiro", "Primeira e última"],
    "arco": ["Caçada à moda antiga", "Corda e flecha", "Silêncio do arco", "Arqueiro do mato"],
    "espingarda": ["Chumbo no ar", "Trabalho de espingarda", "Cano duplo"],
    "rifle": ["Rifle no ombro", "Ferrolho afiado"],
    "curta_arma": ["Arma de cinto", "Revólver de fazendeiro"],
    "genetica": ["Troféu de colecionador", "Só o melhor", "Cabeça de parede", "Linhagem nobre", "Peça de museu"],
    "sem_torre": ["Pé-ante-pé", "Sem escada", "No chão, como antigamente", "Caçador de chão"],
    "atrair": ["Chamando o bicho", "Conversa de chamariz", "Vem pra mim", "Isca e paciência", "Canto de sereia"],
    "nao_detectado": ["Fantasma do mato", "Sombra no capim", "Ninguém te viu", "Vento na cara"],
    "calibre": ["Arma certa, abate limpo", "Calibre de respeito", "Ética em primeiro lugar"],
    "macho": ["O dono do território", "Atrás do macho", "Chefe da manada"],
    "femea": ["Controle de fêmeas", "Manejo de matrizes"],
}
TITULOS_MARCAR = ["Censo da fauna", "Olhos de binóculo", "Contagem de primavera", "Relatório para o guarda", "Quem anda por aí",
                  "Levantamento de campo", "Pesquisa da universidade", "Mapa de bichos"]
TITULOS_VISITAR = ["Conferir o lugar", "Reconhecimento", "Volta de inspeção", "Ronda do guarda", "Trilha de reconhecimento",
                   "Visita de rotina", "Lugar esquecido"]

FALAS_ABRE = [
    "Escuta aqui, garoto.", "Senta aí que eu explico.", "Tenho um serviço pra você.", "Recado do posto:",
    "Não é trabalho pra qualquer um.", "Pega o café que esse é dos bons.", "Ouvi dizer que você anda acertando os tiros.",
    "Chegou um pedido hoje cedo.", "Vou ser direto.", "Coisa rápida, mas bem paga.", "O telefone do posto não parou hoje.",
    "Lembrei de você na hora.", "Tem dinheiro na mesa.", "Isso aqui é sério, rapaz.", "Bom dia, parceiro.",
]
FALAS_GRUPO = [
    "Tem {g} demais derrubando cerca na propriedade do Miller.", "O pessoal da vila reclamou de {g} comendo a horta.",
    "A população de {g} cresceu demais esse ano e o pasto não aguenta.", "O açougue da cidade encomendou {g}.",
    "Um fazendeiro me ligou desesperado com {g} no milharal.", "Tem {g} espantando o gado lá perto do rio.",
    "A associação quer equilibrar o número de {g} antes do inverno.", "Encomenda de carne de {g} pra festa da paróquia.",
    "Achei rastro fresco de {g} perto da estrada de terra.", "O veterinário pediu pra controlar a população de {g} por causa de doença.",
]
FALAS_QUALQUER = [
    "A câmara fria do posto está vazia.", "Os hóspedes do rancho querem carne de caça no jantar.",
    "É fim de mês e a despensa está pelada.", "Quero ver como você se vira sem eu escolher o bicho.",
    "Qualquer animal serve, desde que o tiro seja limpo.", "Tem feira no domingo e a banca de defumados está vazia.",
]
FALAS_COND = {
    "longa": ["Quero ver tiro longo: confira o vento, a queda da bala e respire antes de apertar.", "De longe, sem o bicho desconfiar.",
              "Leve uma luneta boa e o bipé. Paciência vale mais que pressa."],
    "media": ["Tiro de caçador que sabe o que faz: nada de chegar perto demais.", "Uma distância honesta, longe o bastante pro bicho não desconfiar."],
    "curta": ["Não precisa colar no bicho: atire com uma folga de distância.", "Nada de encostar: chegue só até a distância combinada."],
    "um_tiro": ["Um tiro só. Bicho ferido correndo no mato não é caça, é vergonha.", "Sem segundo disparo, entendeu?"],
    "arco": ["Deixa o rifle no carro: é no arco.", "Flecha só. Isso separa os caçadores dos atiradores."],
    "espingarda": ["Vai de espingarda, chumbo certo pra espécie.", "Espingarda no ombro e olho vivo."],
    "rifle": ["Rifle, e nada de improviso.", "Leve o rifle de confiança."],
    "curta_arma": ["Só com arma curta. Coisa de caçador experiente.", "Revólver ou pistola, nada de ombro."],
    "genetica": ["Não atire no primeiro que aparecer: use o binóculo e escolha um bicho de boa genética.",
                 "O cliente é exigente: só bicho de genética alta."],
    "sem_torre": ["Nada de torre ou espera. No chão, pé-ante-pé.", "Quero você andando, não sentado em escada."],
    "atrair": ["Use o chamador ou a isca de cheiro e espere o bicho vir até você.", "Bicho que vem até você é bicho que não te viu."],
    "nao_detectado": ["O animal não pode nem desconfiar que você está lá.", "Se ele te notar, não vale. Vento contra e devagar."],
    "calibre": ["Calibre certo pra espécie, senão é crueldade.", "Confira a tabela de calibres antes de sair."],
    "macho": ["Quero o macho: confirme no binóculo antes de atirar.", "Só macho. Marque com o binóculo pra ter certeza."],
    "femea": ["Desta vez são fêmeas: confirme no binóculo antes do tiro.", "Fêmea, e marque com o binóculo antes."],
}
FALAS_FECHA = ["Volta inteiro.", "Não me decepciona.", "Conto com você.", "Boa caçada.", "Vai com calma.", "Depois me conta como foi.",
               "O pagamento é bom.", "Cuidado com o vento.", ""]
FALAS_MARCAR = ["A universidade quer saber o que anda pela reserva. Marca os bichos no binóculo pra mim.",
                "Preciso de um censo da fauna. Binóculo no olho e anota tudo.", "O guarda pediu uma contagem. Não precisa atirar em nada.",
                "Quero saber quem está circulando por aqui antes da temporada abrir."]
FALAS_VISITAR = ["Tem um lugar que ninguém do posto foi conferir ainda. Dá uma passada lá.",
                 "Faz tempo que ninguém aparece por aqueles lados. Vai lá e me diz como está.",
                 "Preciso de olhos naquela área. Uma volta rápida resolve.", "Faz a ronda e confere se está tudo em ordem."]

DESC_COND = {
    "um_tiro": "com um único tiro", "arco": "usando arco ou besta", "espingarda": "usando espingarda", "rifle": "usando rifle",
    "curta_arma": "usando arma curta", "sem_torre": "sem estar em torre ou espera", "atrair": "atraído por chamador ou isca de cheiro",
    "nao_detectado": "sem que ele perceba você", "calibre": "com o calibre certo para a espécie",
    "macho": "macho (marque no binóculo antes)", "femea": "fêmea (marque no binóculo antes)",
}
MULT = {"longa": 1.7, "media": 1.25, "curta": 1.3, "um_tiro": 1.3, "arco": 1.6, "espingarda": 1.1, "rifle": 1.0, "curta_arma": 1.6,
        "sem_torre": 1.2, "atrair": 1.35, "nao_detectado": 1.4, "calibre": 1.1, "macho": 1.2, "femea": 1.1}
# só distância mínima (sem limite máximo): "a X m ou mais"
FAIXAS = {"curta": [20, 25, 30, 35], "media": [60, 80, 100, 120, 150], "longa": [200, 250, 300, 350]}


def plural(nome, n=2):
    """'coelho' -> 'coelhos', 'bisão' -> 'bisões', 'veado-mula' -> 'veados-mula'."""
    if n == 1 or not nome:
        return nome
    cab, sep, resto = nome.partition("-")
    if cab.endswith("ão"):
        cab = cab[:-2] + "ões"
    elif cab.endswith(("r", "z")):
        cab += "es"
    elif cab.endswith("m"):
        cab = cab[:-1] + "ns"
    elif cab.endswith("l") and not cab.endswith(("il",)):
        cab = cab[:-1] + "is"
    elif not cab.endswith("s"):
        cab += "s"
    return cab + sep + resto


def _g(nome):
    """'Pato / marreca' -> 'pato' (texto mais natural nos contratos)."""
    return nome.split(" / ")[0].lower()


def _arma_tipo(tipo):
    t = tipo or ""
    if "Bow" in t or "Crossbow" in t or "CrossBow" in t:
        return "arco"
    if "Shotgun" in t:
        return "espingarda"
    if "Handgun" in t or "Pistol" in t or "Revolver" in t:
        return "curta_arma"
    return "rifle"


def gerar(dados, pois, nome_grupo, grupos_reserva, cap, quantos=1):
    """Gera `quantos` contratos variados, sem repetir títulos já oferecidos agora.
    cap = extras.capacidade(): grupos que você consegue caçar com as armas e munição que tem, e com que tipo de arma."""
    if isinstance(cap, (list, tuple)):          # chamada antiga: só a lista de tipos de arma
        cap = {"grupos": {g: {"armas": list(cap), "atrair": True} for g in grupos_reserva}, "telemetro": True}
    grupos = [g for g in grupos_reserva if g in cap["grupos"]]
    usados = {m["titulo"] for m in dados.get("missoes", []) if m.get("status") in ("oferta", "ativa")}
    saida = []
    for _ in range(quantos * 8):
        if len(saida) >= quantos:
            break
        m = _um(grupos, pois, nome_grupo, cap)
        if m and m["titulo"] not in usados:
            usados.add(m["titulo"])
            saida.append(m)
    return saida


def _um(grupos, pois, nome_grupo, cap):
    # sem arma+munição para nada da reserva (jogo novo): só censo no binóculo e reconhecimento
    caca = 1 if grupos else 0
    forma = random.choices(["grupo", "qualquer", "variedade", "marcar", "marcar_grupo", "visitar"],
                           weights=[50 * caca, 16 * caca, 7 * caca if len(grupos) > 1 else 0, 10, 7, 7 if pois else 0])[0]
    if forma in ("marcar", "marcar_grupo"):
        return _marcar(grupos if forma == "marcar_grupo" and grupos else None, nome_grupo)
    if forma == "visitar":
        return _visitar(pois) if pois else _marcar(None, nome_grupo)
    grupo = random.choice(grupos) if forma == "grupo" else None
    # tipos de arma que você consegue usar nesse alvo (arma sua + munição sua permitida)
    if grupo:
        armas_tipos = cap["grupos"][grupo]["armas"]
        pode_atrair = cap["grupos"][grupo]["atrair"]
    else:
        armas_tipos = sorted({t for g in grupos for t in cap["grupos"][g]["armas"]})
        pode_atrair = any(cap["grupos"][g]["atrair"] for g in grupos)
    pequeno = grupo in PEQUENOS
    meta = random.choice([1, 1, 2, 2, 3, 4, 5] if pequeno else [1, 1, 1, 2, 2, 3])
    if forma == "variedade":
        meta = random.choice([2, 3, 3, 4])

    # condições: 0 a 3, sem combinações impossíveis
    cond, chaves = {}, []
    n = random.choices([0, 1, 2, 3], weights=[18, 45, 28, 9])[0]
    opcoes = ["dist", "um_tiro", "arma", "genetica", "sem_torre", "atrair", "nao_detectado", "calibre", "sexo"]
    random.shuffle(opcoes)
    for o in opcoes:
        if len(chaves) >= n:
            break
        if o == "dist":
            arma = cond.get("arma")
            faixas = ["curta", "media"] if arma in ("arco", "curta_arma") or pequeno or "rifle" not in armas_tipos else ["curta", "media", "longa", "longa"]
            if arma == "espingarda" or grupo in AVES:      # chumbo não vai longe
                faixas = ["curta"]
            f = random.choice(faixas)
            cond["dist_min"] = random.choice(FAIXAS[f])
            chaves.append(f)
        elif o == "arma":
            tipos = [t for t in armas_tipos if t != "rifle" or not pequeno] or list(armas_tipos)
            if "longa" in chaves:
                tipos = [t for t in tipos if t == "rifle"]
            if not tipos or len(armas_tipos) < 2:      # com um tipo só, exigir o tipo não acrescenta nada
                continue
            t = random.choice(tipos)
            if grupo in AVES and t not in ("espingarda", "arco"):
                continue
            cond["arma"] = t
            chaves.append(t)
        elif o == "genetica":
            cond["genetica"] = random.choice([0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8])
            chaves.append("genetica")
        elif o == "sexo":
            if not grupo or grupo in AVES:
                continue
            s = random.choice(["macho", "macho", "femea"])
            cond["sexo"] = s
            chaves.append(s)
        elif o == "atrair" and not pode_atrair:
            continue
        elif o in ("um_tiro", "sem_torre", "atrair", "nao_detectado", "calibre"):
            cond[o] = True
            chaves.append(o)
    if forma == "variedade":
        cond["variedade"] = True

    # texto
    nome = _g(nome_grupo(grupo)) if grupo else None
    if forma == "variedade":
        alvo = f"{meta} animais de espécies diferentes"
    elif grupo:
        alvo = f"{meta} {plural(nome, meta)}"
    else:
        alvo = "1 animal de qualquer espécie" if meta == 1 else f"{meta} animais de qualquer espécie"
    if cond.get("sexo") and forma != "variedade":
        alvo += " " + ({"macho": "macho", "femea": "fêmea"}[cond["sexo"]] if meta == 1 else
                       {"macho": "machos", "femea": "fêmeas"}[cond["sexo"]]) + " (confirme no binóculo antes)"
    varios = meta > 1
    partes = []
    if "dist_min" in cond:
        partes.append(f"a {cond['dist_min']} m ou mais")
    if "genetica" in cond:
        partes.append(f"com genética de {int(cond['genetica'] * 100)}% ou mais")
    for c in chaves:
        if c in ("macho", "femea"):
            continue
        if c == "nao_detectado":
            partes.append("sem que os animais percebam você" if varios else "sem que o animal perceba você")
        elif c == "atrair":
            partes.append("atraídos por chamador ou isca de cheiro" if varios else "atraído por chamador ou isca de cheiro")
        elif c in DESC_COND:
            partes.append(DESC_COND[c])
    descricao = f"Abata e recolha {alvo}" + (", " + ", ".join(partes) if partes else "") + "."

    if chaves and random.random() < 0.65:
        titulo = random.choice(TITULOS_COND[random.choice(chaves)])
    elif forma == "variedade":
        titulo = random.choice(TITULOS_VARIEDADE)
    elif grupo:
        titulo = random.choice(TITULOS_GRUPO).format(g=nome, G=nome[:1].upper() + nome[1:])
    else:
        titulo = random.choice(TITULOS_QUALQUER)
    fala = " ".join(x for x in [
        random.choice(FALAS_ABRE),
        random.choice(FALAS_GRUPO).format(g=nome) if grupo else random.choice(FALAS_QUALQUER),
        *(random.choice(FALAS_COND[c]) for c in chaves[:2]),
        random.choice(FALAS_FECHA)] if x)

    valor = VALOR_GRUPO.get(grupo or "outro", 350) * meta
    for c in chaves:
        valor *= MULT.get(c, 1.15)
    if "genetica" in cond:
        valor *= 1 + (cond["genetica"] - 0.4) * 2
    valor = int(round(max(200, min(6000, valor)) / 50) * 50)
    m = _base(titulo, fala, descricao, meta, valor)
    m.update({"tipo": "combo", "grupo": grupo, "cond": cond})
    if "dist_min" in cond:
        m["dist_min"] = cond["dist_min"]
    return m


def _marcar(grupos, nome_grupo):
    grupo = random.choice(grupos) if grupos else None
    meta = random.choice([2, 3, 4] if grupo else [4, 5, 6, 8, 10])
    alvo = f"{meta} {plural(_g(nome_grupo(grupo)), meta)} diferentes" if grupo else f"{meta} animais diferentes"
    m = _base(random.choice(TITULOS_MARCAR), random.choice(FALAS_ABRE) + " " + random.choice(FALAS_MARCAR),
              f"Marque {alvo} com o binóculo.", meta, int(round((110 if not grupo else 160) * meta / 10) * 10))
    m.update({"tipo": "combo", "grupo": grupo, "cond": {"marcar": True}})
    return m


def _visitar(pois):
    cand = [p for p in pois if p.get("categoria") in ("lugar", "torre", "acampamento", "estrutura")
            and p.get("nome") and "_" not in p["nome"] and "Contract" not in p["nome"] and "Zone" not in p["nome"]]
    contagem = {}
    for p in cand:
        contagem[p["nome"]] = contagem.get(p["nome"], 0) + 1
    cand = [p for p in cand if contagem[p["nome"]] == 1]      # "Estrutura de caça" repetido não diz onde ir
    novos = [p for p in cand if not p.get("descoberto")]
    cand = novos or cand
    if not cand:
        return None
    n = random.choice([1, 1, 2, 3]) if len(cand) >= 3 else 1
    locais = random.sample(cand, n)
    nomes = ", ".join(p["nome"] for p in locais)
    desc = f"Vá até: {nomes}." if n == 1 else f"Passe por estes {n} lugares: {nomes}."
    m = _base(random.choice(TITULOS_VISITAR), random.choice(FALAS_ABRE) + " " + random.choice(FALAS_VISITAR), desc, n, 450 * n + 150)
    m.update({"tipo": "combo", "cond": {"visitar": True},
              "locais": [{"x": p["x"], "y": p["y"], "z": p.get("z", 0), "nome": p["nome"], "hash": p["hash"]} for p in locais]})
    m["local"] = m["locais"][0]
    return m


def _base(titulo, fala, descricao, meta, creditos):
    return {"titulo": titulo[:60], "fala": fala.strip()[:500], "descricao": descricao, "meta": max(1, int(meta)),
            "creditos": int(creditos), "reputacao": max(5, min(100, int(creditos) // 30)),
            "id": uuid.uuid4().hex[:8], "status": "oferta", "progresso": 0, "contados": [], "criada": time.time(), "origem": "local"}


def conta(m, evento, dentro, arma_tipo_de):
    """True se o evento conta para o contrato `combo` m."""
    c = m.get("cond") or {}
    tipo = evento.get("tipo")
    if c.get("marcar"):
        return tipo == "marcado" and (not m.get("grupo") or evento.get("grupo") == m["grupo"])
    if c.get("visitar"):
        if tipo != "posicao":
            return False
        feitos = set(m.get("visitados") or [])
        for i, loc in enumerate(m.get("locais") or [m.get("local")]):
            if loc and i not in feitos and dentro(evento.get("pos"), loc):
                m.setdefault("visitados", []).append(i)
                proximo = next((l for j, l in enumerate(m.get("locais") or []) if j not in m["visitados"]), None)
                if proximo:
                    m["local"] = proximo
                evento["id"] = f"local{i}"
                return True
        return False
    if tipo != "abate_confirmado":
        return False
    if m.get("grupo") and evento.get("grupo") != m["grupo"]:
        return False
    if c.get("variedade") and evento.get("grupo") in set(m.get("grupos_feitos") or []):
        return False
    d = evento.get("distancia_m") or 0
    if "dist_min" in c and d < c["dist_min"]:      # sem limite máximo
        return False
    if c.get("um_tiro") and (evento.get("tiros") or 1) > 1:
        return False
    if c.get("arma") and arma_tipo_de(evento.get("arma")) != c["arma"]:
        return False
    if "genetica" in c and (evento.get("genetica") or 0) < c["genetica"]:
        return False
    if c.get("sem_torre") and evento.get("torre") is not False:
        return False
    if c.get("atrair") and evento.get("atraido") is not True:
        return False
    if c.get("nao_detectado") and not nao_percebeu(evento.get("estado_animal")):
        return False
    if c.get("calibre") and evento.get("calibre_compativel") is not True:
        return False
    if c.get("sexo"):
        s = (evento.get("sexo_nome") or "").lower()
        if not s.startswith("macho" if c["sexo"] == "macho" else "fêmea"):
            return False
    if c.get("variedade"):
        m.setdefault("grupos_feitos", []).append(evento.get("grupo"))
    return True


# ------------------------------------------------------------------ dicas do Earl (sem IA)
DICAS = {
    "vento": ["O vento manda em tudo, rapaz. Ande sempre com ele batendo no rosto: o cheiro vai pra trás de você.",
              "Use o pó indicador de vento antes de começar a aproximação. Se o pó vai na direção do bicho, dê a volta.",
              "Vento girando no fim da tarde é comum perto de morro. Prefira esperar numa espera e deixar o bicho vir."],
    "cheiro": ["Spray disfarçador de odor antes de sair do carro, e de novo depois de correr ou suar.",
               "Isca de urina funciona a favor do vento: coloque de modo que o cheiro vá para onde o bicho deve vir."],
    "calibre": ["Calibre fraco em bicho grande é crueldade. Confira no Diário de campo quais calibres cada espécie aceita.",
                "Veado e javali: .243 pra cima com rifle, ou bala única/chumbo grosso na espingarda. Ave é chumbo fino.",
                "Na aba Mochila o app já pinta de verde a munição certa para os seus contratos."],
    "distancia": ["Tiro longo: luneta com bastante aumento, bipé, respiração presa na metade e aperta devagar.",
                  "Até uns 200 m quase não precisa compensar a queda. Passou de 300, mire um pouco acima.",
                  "Arco é coisa de 20 a 40 m. Chegue perto antes de pensar em atirar."],
    "chamar": ["Chamador: chame poucas vezes e espere. Quem chama demais espanta o bicho desconfiado.",
               "Combine o chamador com uma boa cobertura. O animal vem olhando para de onde veio o som.",
               "Amanhecer e fim de tarde são as melhores horas pra chamar."],
    "binoculo": ["Marque tudo no binóculo: o app guarda a posição, a genética e o sexo do bicho no mapa.",
                 "Antes de atirar, olhe a genética no binóculo. Troféu bom vale a espera."],
    "cervo": ["Veado gosta de borda de mata no amanhecer e no fim da tarde. Ande devagar e pare muito.",
              "O macho maduro é o mais desconfiado. Se a manada te notar, ele é o primeiro a sumir."],
    "porco": ["Javali anda em grupo e fuça a terra perto de água e de plantação. Procure lama revirada.",
              "Porco tem faro muito bom e enxerga mal. Vento a favor e você chega perto."],
    "pato": ["Pato é perto da água, com chamariz de pato e chamador. Espingarda e chumbo de ave.",
             "Fique escondido na margem e deixe os patos pousarem antes de atirar."],
    "peru": ["Peru responde ao chamador de acasalamento. Fique encostado numa árvore e não se mexa.",
             "O peru enxerga muito bem. Roupa de camuflagem e nada de movimento."],
    "som": ["Roupa barulhenta denuncia. Veja na aba Roupas quanto barulho a sua roupa faz.",
            "Correr faz barulho e espanta tudo num raio grande. Ande agachado na aproximação final."],
    "geral": ["Paciência é a melhor arma do caçador. Quem tem pressa volta de mãos vazias.",
              "Tiro só com o bicho de lado: pulmão e coração. Tiro de frente ou de trás fere e não mata.",
              "Depois do tiro, espere um pouco antes de seguir o rastro de sangue.",
              "Se o bicho te notou, não insista: dê a volta e tente de outro lado.",
              "Use o mapa do app: o pino aparece também no mapa do jogo."],
}
PALAVRAS_DICA = {"vento": ["vento"], "cheiro": ["cheiro", "odor", "spray", "urina", "isca"], "calibre": ["calibre", "munição", "municao", "bala", "chumbo"],
                 "distancia": ["distância", "distancia", "longe", "longo", "luneta", "mira", "arco"],
                 "chamar": ["chama", "apito", "atrair", "atrai", "chamariz"], "binoculo": ["binóculo", "binoculo", "marcar", "genética", "genetica", "troféu"],
                 "cervo": ["cervo", "veado"], "porco": ["porco", "javali", "caititu"], "pato": ["pato", "marreca", "ganso"], "peru": ["peru"],
                 "som": ["barulho", "roupa", "som", "silêncio", "silencio", "perceb"]}


def dica(pergunta):
    t = (pergunta or "").lower()
    temas = [k for k, ps in PALAVRAS_DICA.items() if any(p in t for p in ps)] or ["geral"]
    linhas = [random.choice(DICAS[k]) for k in temas[:2]]
    return " ".join(linhas)
