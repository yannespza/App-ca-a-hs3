"""Manejo de fauna: censo, equilíbrio, pressão de caça, demanda de carne, índice da reserva e boletins.

Tudo é calculado só com o que o app já guarda (avistamentos pelo binóculo e abates). Nada aqui mexe no jogo.
Sexo no jogo: 0 = macho, 1 = fêmea.
"""

JANELA_DIAS = 7


def _sexo(x):
    s = x.get("sexo")
    if s in (0, 1):
        return s
    n = (x.get("sexo_nome") or "").lower()
    return 0 if n.startswith("mach") else 1 if n.startswith("fêm") or n.startswith("fem") else None


def _dia(x):
    d = x.get("dia") if "dia" in x else x.get("dia_jogo")
    return d if isinstance(d, int) else None


def _limpo(a):
    """Abate limpo: um tiro só e calibre certo para a espécie."""
    return (a.get("tiros") or 1) == 1 and a.get("calibre_compativel") is not False


def _nivel(v, baixo, alto):
    return "baixa" if v < baixo else "alta" if v >= alto else "média"


def especies(avist, abates, dia, nome_especie, grupo_de):
    """Uma linha por espécie vista ou abatida nesta reserva."""
    ini = dia - JANELA_DIAS + 1
    esp = {}

    def linha(tag):
        if tag not in esp:
            esp[tag] = {"tag": tag, "nome": nome_especie(tag), "grupo": grupo_de(tag)[0],
                        "ids": {}, "abates": 0, "abates_7d": 0, "abates_femeas_7d": 0, "abates_limpos": 0,
                        "ultimo_abate_dia": None, "ultimo_visto_dia": None, "trofeu_max": 0}
        return esp[tag]

    for a in avist:
        if not a.get("especie"):
            continue
        l = linha(a["especie"])
        d = _dia(a)
        if d is not None and d < ini:
            continue
        l["ids"][a.get("id")] = a          # o mais recente de cada animal
        if d is not None:
            l["ultimo_visto_dia"] = max(l["ultimo_visto_dia"] or d, d)
    for a in abates:
        if not a.get("especie"):
            continue
        l = linha(a["especie"])
        l["abates"] += 1
        l["abates_limpos"] += 1 if _limpo(a) else 0
        l["trofeu_max"] = max(l["trofeu_max"], a.get("pontos_trofeu") or 0)
        d = _dia(a)
        if d is not None:
            l["ultimo_abate_dia"] = max(l["ultimo_abate_dia"] or d, d)
            if d >= ini:
                l["abates_7d"] += 1
                l["abates_femeas_7d"] += 1 if _sexo(a) == 1 else 0

    saida = []
    for l in esp.values():
        vistos = list(l.pop("ids").values())
        m = sum(1 for v in vistos if _sexo(v) == 0)
        f = sum(1 for v in vistos if _sexo(v) == 1)
        gen = [v.get("genetica") for v in vistos if isinstance(v.get("genetica"), (int, float))]
        pot = [v.get("potencial") for v in vistos if isinstance(v.get("potencial"), (int, float))]
        n = len(vistos)
        pressao_v = l["abates_7d"] / max(1, n)
        pressao = "sem dados" if not n and not l["abates_7d"] else _nivel(pressao_v, 0.34, 0.75)
        if pressao == "alta" and l["abates_7d"] < 3:
            pressao = "média"          # poucos abates: ainda não é pressão de verdade
        alertas = []
        if n >= 4 and m == 0:
            alertas.append("Bando estagnado: só fêmeas vistas. Evite abater fêmeas até aparecer macho.")
        elif f and m / f < 0.25 and n >= 5:
            alertas.append("Poucos machos para as fêmeas. Prefira descarte de fêmea velha ou genética fraca.")
        elif f and m / f > 1.5 and n >= 5:
            alertas.append("Machos demais: bom momento para colher machos maduros.")
        if pressao == "alta":
            alertas.append(f"Pressão de caça alta ({l['abates_7d']} abates em 7 dias para {n} animais vistos). Sugestão: 2 dias de defeso.")
        if l["abates_femeas_7d"] >= 3 and l["abates_femeas_7d"] > l["abates_7d"] / 2:
            alertas.append("Muitas fêmeas abatidas nesta semana.")
        if pot and max(pot) >= 0.85:
            alertas.append(f"Tem animal com potencial genético de {round(max(pot) * 100)}% circulando.")
        # Bolsa de carne: quanto mais dias sem abate da espécie, mais o açougue quer (80% a 150%)
        sem = None if l["ultimo_abate_dia"] is None else max(0, dia - l["ultimo_abate_dia"])
        if sem is not None:
            demanda = min(1.5, 0.8 + 0.1 * sem)
        else:
            demanda = 1.5 if not l["abates"] else 1.0     # abates antigos (antes do contador de dias): neutro
        if l["abates_7d"] >= 4:
            demanda = min(demanda, 0.9)
        saida.append({**l, "vistos": n, "machos": m, "femeas": f,
                      "razao": None if not f else round(m / f, 2),
                      "genetica_media": round(sum(gen) / len(gen), 3) if gen else None,
                      "potencial_max": round(max(pot), 3) if pot else None,
                      "pressao": pressao, "pressao_valor": round(pressao_v, 2),
                      "demanda": round(demanda, 2), "dias_sem_abate": sem, "alertas": alertas,
                      "defeso": pressao == "alta"})
    saida.sort(key=lambda x: (-len(x["alertas"]), -x["vistos"], x["nome"]))
    return saida


def indice(abates, linhas):
    """Índice de Sustentabilidade da reserva (0–100) e selo Reserva Modelo (≥ 80)."""
    ult = abates[-20:]
    if not ult:
        return {"valor": None, "partes": [], "selo": False}
    limpos = sum(1 for a in ult if _limpo(a)) / len(ult)
    com_pressao = [l for l in linhas if l["pressao"] != "sem dados"]
    alta = sum(1 for l in com_pressao if l["pressao"] == "alta")
    equilibrio = 1 - alta / max(1, len(com_pressao))
    # seleção: machos maduros (faixa 3+), genética fraca (descarte) ou troféu bom contam como boa escolha
    boa = 0
    for a in ult:
        if _sexo(a) == 0 and (a.get("faixa_idade") or 0) >= 3:
            boa += 1
        elif (a.get("genetica") or 1) < 0.45:
            boa += 1
        elif (a.get("pontos_trofeu") or 0) >= 60:
            boa += 1
    selecao = boa / len(ult)
    partes = [{"nome": "Abates limpos", "valor": round(limpos * 40), "max": 40, "dica": "um tiro e calibre certo"},
              {"nome": "Equilíbrio das espécies", "valor": round(equilibrio * 30), "max": 30, "dica": "nenhuma espécie com pressão alta"},
              {"nome": "Seleção", "valor": round(selecao * 30), "max": 30, "dica": "machos maduros, descarte de genética fraca ou troféus"}]
    v = sum(p["valor"] for p in partes)
    return {"valor": v, "partes": partes, "selo": v >= 80, "base": len(ult)}


def boletim(dia, avist, abates, linhas):
    """Resumo de um dia do jogo nesta reserva (o boletim da manhã fala do dia anterior)."""
    ab = [a for a in abates if _dia(a) == dia]
    av = [a for a in avist if _dia(a) == dia]
    melhor = max(ab, key=lambda a: a.get("pontos_trofeu") or 0, default=None)
    alertas = [f"{l['nome']}: {l['alertas'][0]}" for l in linhas if l["alertas"]][:4]
    procura = sorted([l for l in linhas if l["demanda"] >= 1.2], key=lambda l: -l["demanda"])[:3]
    return {"dia": dia, "abates": len(ab), "limpos": sum(1 for a in ab if _limpo(a)), "avistados": len({a.get("id") for a in av}),
            "especies_abatidas": sorted({a.get("especie_nome") or "" for a in ab if a.get("especie_nome")}),
            "melhor": {"especie": melhor.get("especie_nome"), "pontos": melhor.get("pontos_trofeu"), "peso_kg": melhor.get("peso_kg")}
            if melhor and melhor.get("pontos_trofeu") else None,
            "alertas": alertas, "procura": [{"nome": l["nome"], "demanda": l["demanda"]} for l in procura]}


def semana(dia, abates, avist):
    """Os últimos 7 dias, um número por dia (para o gráfico do boletim semanal)."""
    dias = list(range(max(0, dia - JANELA_DIAS + 1), dia + 1))
    return [{"dia": d, "abates": sum(1 for a in abates if _dia(a) == d),
             "avistados": len({a.get("id") for a in avist if _dia(a) == d})} for d in dias]


def painel(dados, reserva, nome_especie, grupo_de):
    dia = dados.get("dia_jogo", 0)
    avist = [a for a in dados.get("avistamentos") or [] if reserva and a.get("reserva") and reserva in a["reserva"]]
    abates = [a for a in dados.get("abates") or [] if reserva and a.get("reserva") and reserva in a["reserva"]]
    linhas = especies(avist, abates, dia, nome_especie, grupo_de)
    bol = [b for b in dados.get("boletins") or [] if b.get("reserva") and reserva and reserva in b["reserva"]]
    return {"dia": dia, "reserva": reserva, "especies": linhas, "indice": indice(abates, linhas),
            "hoje": boletim(dia, avist, abates, linhas), "boletins": bol[-7:][::-1], "semana": semana(dia, abates, avist),
            "totais": {"avistados": len({a.get("id") for a in avist}), "abates": len(abates)}}
