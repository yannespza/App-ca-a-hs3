"""Mapa: névoa em PNG, nomes dos pontos de interesse e silhuetas por grupo."""
import re
import struct
import zlib

# inverte a ordem dos bits de cada byte (o jogo guarda o bit menos significativo primeiro; o PNG usa o mais significativo)
_INVERTE = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))


def nevoa_png(bin_path, lado=2048, cor=(236, 228, 210), alfa=165):
    """Converte a névoa do jogo (2048x2048 bits, 1 = explorado) num PNG de 1 bit com transparência.
    Explorado = transparente; não explorado = véu claro (como no mapa do jogo)."""
    with open(bin_path, "rb") as f:
        dados = f.read()
    por_linha = lado // 8
    dados = dados[: por_linha * lado].ljust(por_linha * lado, b"\0").translate(_INVERTE)
    bruto = b"".join(b"\0" + dados[i * por_linha:(i + 1) * por_linha] for i in range(lado))

    def bloco(tipo, conteudo):
        c = tipo + conteudo
        return struct.pack(">I", len(conteudo)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", lado, lado, 1, 3, 0, 0, 0)       # 1 bit, paleta
    plte = bytes(cor) + bytes(cor)                                  # 0 = não explorado, 1 = explorado
    trns = bytes([alfa, 0])
    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", ihdr) + bloco(b"PLTE", plte) + bloco(b"tRNS", trns)
            + bloco(b"IDAT", zlib.compress(bruto, 9)) + bloco(b"IEND", b""))


# ------------------------------------------------------------------ pontos de interesse
CATEGORIAS = {
    "Campsite": ("acampamento", "Acampamento"),
    "HuntingStructure": ("estrutura", "Estrutura de caça"),
    "Lodge": ("sede", "Sede de caça"),
    "TravelPoint": ("viagem", "Ponto de viagem"),
    "Store": ("servico", "Loja"),
    "Customization": ("servico", "Personalização"),
    "LoadoutBench": ("servico", "Bancada de equipamento"),
    "Kennel": ("servico", "Canil"),
    "Wardrobe": ("servico", "Guarda-roupa"),
    "HuntHistory": ("servico", "Histórico de caça"),
    "Garage": ("servico", "Garagem"),
    "Clock": ("servico", "Relógio"),
    "Vehicle": ("veiculo", "Veículo"),
    "Companion": ("cao", "Cão"),
    "Butcher": ("npc", "Açougueiro"),
    "Ranger": ("npc", "Guarda-florestal"),
    "SportsShooter": ("npc", "Atirador esportivo"),
    "QuickWaypoint": ("pino", "Ponto de rota rápido"),
    "Waypoint": ("pino", "Ponto de rota"),
}

LUGARES = {
    "GasStation": "Posto de gasolina", "AbandonedChurch": "Igreja abandonada", "AbandonedHouse": "Casa abandonada",
    "AbandonedMine": "Mina abandonada", "Cabin": "Cabana", "CampGround": "Área de camping", "ChurchRuins": "Ruínas da igreja",
    "Farm": "Fazenda", "FortRuins": "Ruínas do forte", "GhostTown": "Cidade fantasma", "Observatory": "Observatório",
    "OilRigs": "Poços de petróleo", "RadioTower": "Torre de rádio", "RockFormation": "Formação rochosa",
    "SmallShed": "Galpão", "SolarFarm": "Usina solar", "TollBooth": "Pedágio", "Watchtower": "Torre de vigia",
    "WaterfallAndBridge": "Cachoeira e ponte",
}


def descrever_poi(tipo):
    """DA_TX_GasStation_01_MapIconData -> ("lugar", "Posto de gasolina 1")"""
    base = re.sub(r"^DA_|_MapIconData$|_NavigationIcon$", "", tipo)
    base = re.sub(r"^(TX|CO)_", "", base)
    num = re.search(r"(\d+)$", base)
    nome = re.sub(r"_?\d+$", "", base)
    for chave, (cat, rotulo) in CATEGORIAS.items():
        if nome == chave or nome.endswith(chave):
            if nome in LUGARES:
                break
            return cat, rotulo
    if nome.startswith("Watchtower"):
        return "torre", "Torre de observação" + (f" {int(num.group(1))}" if num else "")
    if nome.startswith("Player"):
        return "pino", "Jogador"
    rotulo = LUGARES.get(nome, re.sub(r"(?<!^)([A-Z])", r" \1", nome))
    if num and int(num.group(1)) > 1:
        rotulo += f" {int(num.group(1))}"
    return "lugar", rotulo


def carregar_pois(path):
    import json
    try:
        with open(path, encoding="utf-8") as f:
            lista = json.load(f)
    except Exception:
        return []
    saida = []
    for p in lista:
        cat, nome = descrever_poi(p.get("tipo", ""))
        if cat in ("pino",):
            continue
        p = dict(p)
        p["categoria"], p["nome"] = cat, nome
        # lugares, acampamentos, torres e estruturas de caça só contam depois que você os descobre no jogo
        p["descoberto"] = (p.get("estado") or "").endswith("Discovered") or cat not in ("lugar", "acampamento", "torre", "estrutura")
        saida.append(p)
    return saida
