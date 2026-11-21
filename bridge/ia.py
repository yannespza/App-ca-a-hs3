"""Integração com o Ollama: personagem, missões geradas por IA e dicas de caça."""
import json
import time
import urllib.request

NPC = {
    "id": "earl",
    "nome": "Earl Whitaker",
    "apelido": "Velho Earl",
    "idade": 64,
    "funcao": "Guia de caça e contratador da região",
    "origem": "Nascido em Alpine, Texas. Trinta anos como guarda-florestal antes de abrir o próprio posto de contratos.",
    "retrato": "/img/npc_earl.png",
    "frase": "O vento não mente, garoto. Quem mente é caçador apressado.",
}

PERSONA = f"""Você é {NPC['nome']}, conhecido como "{NPC['apelido']}", {NPC['idade']} anos, {NPC['funcao'].lower()} no jogo Hunting Simulator 3.
{NPC['origem']}
Personalidade: experiente, paciente, bem-humorado, rabugento com pressa e desrespeito à caça ética. Fala português do Brasil
de forma simples e calorosa, com uma ou outra expressão de velho caçador do Texas (ex.: "rapaz", "parceiro", "pé-ante-pé").
Respostas curtas e práticas (no máximo 6 frases), a menos que o caçador peça detalhes. Nunca invente números exatos do jogo
(preços, distâncias de detecção, porcentagens) que você não recebeu no contexto."""

REGRAS_JOGO = """Regras e diretrizes de Hunting Simulator 3 que você conhece:
- Reservas: Texas e Colorado. Cada uma tem espécies, pontos de interesse, torres de observação, acampamentos e estruturas de caça.
- Licenças: é preciso licença da espécie para caçar na reserva; abater sem licença ou o animal errado gera multa.
- Fauna (SimFauna): animais têm rotinas (alimentação, descanso, bebedouros), reagem a cheiro, barulho e visão. Rebanhos fogem juntos.
- Vento e cheiro: aproxime-se sempre contra o vento; o cheiro do caçador espalha na direção do vento. Produtos que reduzem cheiro ajudam.
- Barulho: correr, andar em mato seco e roupas barulhentas denunciam. Agachado e deitado são mais silenciosos.
- Visibilidade: camuflagem adequada ao bioma e estação reduz a percepção; ficar parado e usar sombra/vegetação ajuda.
- Melhores horários: amanhecer e entardecer têm mais atividade. Clima e vento mudam ao longo do dia (veja a previsão no mapa).
- Rastros: pegadas, fezes e trilhas de sangue indicam espécie, direção e estado do animal; o cão de caça ajuda a seguir rastros.
- Binóculo: marcar o animal revela espécie, sexo, idade e potencial genético; ótimo para escolher troféus e evitar fêmeas/jovens.
- Tiro ético: mire em órgãos vitais (coração/pulmões), atrás da paleta, com o animal de lado. Tiros ruins estragam carne e troféu.
- Calibre certo: chumbo/espingarda para aves (patos, perus), calibres médios de rifle para cervos e porcos-do-mato. Calibre fraco fere e
  o animal foge; calibre exagerado estraga a carne.
- Patos e aves aquáticas ficam perto de água; porcos-do-mato andam em grupo em áreas de mato e lama; cervos-de-cauda-branca usam bordas de mata.
- Estruturas de caça (torres/esperas) reduzem a chance de ser detectado; caçar a pé exige mais cuidado.
- Recompensas: créditos (dinheiro), reputação com o vendedor e pontos de campo. Venda de carne e troféus depende da qualidade do abate.
- Medalhas de troféu dependem da genética e da pontuação do animal."""


class Ollama:
    def __init__(self, cfg):
        self.cfg = cfg
        self.modelo = None
        self.ok = False
        self.erro = None
        self.verificado_em = 0

    def _url(self, caminho):
        return self.cfg.get("ollama_url", "http://localhost:11434").rstrip("/") + caminho

    def verificar(self, forcar=False):
        if not forcar and time.time() - self.verificado_em < (60 if self.ok else 10):
            return self.ok
        self.verificado_em = time.time()
        try:
            with urllib.request.urlopen(self._url("/api/tags"), timeout=3) as r:
                modelos = [m["name"] for m in json.load(r).get("models", [])]
            pedido = self.cfg.get("ollama_modelo") or ""
            if pedido and any(m == pedido or m.startswith(pedido + ":") for m in modelos):
                self.modelo = next(m for m in modelos if m == pedido or m.startswith(pedido + ":"))
            else:
                preferidos = ("qwen2.5", "qwen3", "llama3.1", "llama3.2", "gemma", "mistral")
                self.modelo = next((m for p in preferidos for m in modelos if m.startswith(p)), modelos[0] if modelos else None)
            self.ok = self.modelo is not None
            self.erro = None if self.ok else "Nenhum modelo instalado no Ollama (rode: ollama pull qwen2.5:7b)"
        except Exception:
            self.ok, self.modelo = False, None
            self.erro = "Ollama não está rodando"
        return self.ok

    def status(self):
        return {"ok": self.ok, "modelo": self.modelo, "erro": self.erro}

    def chat(self, mensagens, formato_json=False, temperatura=0.8, timeout=180):
        if not self.verificar():
            raise RuntimeError(self.erro or "Ollama indisponível")
        corpo = {"model": self.modelo, "messages": mensagens, "stream": False,
                 "options": {"temperature": temperatura, "num_ctx": 8192}}
        if formato_json:
            corpo["format"] = "json"
        req = urllib.request.Request(self._url("/api/chat"), data=json.dumps(corpo).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)["message"]["content"]


TIPOS_MISSAO = {
    "abater_grupo": "abater N animais de um grupo (campo 'grupo' obrigatório, 'meta' = N)",
    "abater_qualquer": "abater N animais de qualquer espécie ('meta' = N)",
    "distancia": "abater 1 animal a pelo menos D metros ('distancia' = D entre 50 e 300)",
    "genetica": "abater 1 animal com genética mínima G ('genetica' = G entre 0.4 e 0.85)",
    "sem_torre": "abater 1 animal a pé, sem usar torre/espera",
    "marcar": "marcar N animais diferentes com o binóculo ('meta' = N entre 3 e 10)",
    "visitar": "ir até um ponto de interesse ('poi_hash' obrigatório, de preferência um ainda não descoberto)",
}


def gerar_missoes(ollama, contexto, quantidade=3):
    sistema = PERSONA + "\n\n" + REGRAS_JOGO + """

Agora você vai oferecer contratos de caça ao jogador. Responda SOMENTE com JSON no formato:
{"missoes": [{"tipo": "...", "titulo": "...", "fala": "...", "grupo": "...", "meta": 1, "distancia": 0, "genetica": 0,
  "poi_hash": 0, "creditos": 0, "reputacao": 0}]}
Regras:
- "tipo" deve ser um destes: """ + "; ".join(f"{k} = {v}" for k, v in TIPOS_MISSAO.items()) + """
- "grupo" só pode ser uma das chaves de grupos disponíveis informadas no contexto.
- "poi_hash" só pode ser um hash da lista de pontos de interesse informada; use em missões 'visitar' e, se fizer sentido,
  também para indicar a região de caça de outras missões (o jogador recebe um pino no mapa).
- "titulo": curto e com personalidade (máx. 6 palavras). "fala": 2 a 3 frases suas contando o motivo do contrato e uma dica.
- Créditos entre 300 e 3000 e reputação entre 10 e 80, proporcionais à dificuldade.
- Varie os tipos; não repita missões que já estão ativas."""
    usuario = "Contexto do jogador (JSON):\n" + json.dumps(contexto, ensure_ascii=False) + \
              f"\n\nCrie {quantidade} contratos diferentes."
    texto = ollama.chat([{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                        formato_json=True, temperatura=0.9)
    dados = json.loads(texto)
    return dados.get("missoes", dados if isinstance(dados, list) else [])


def conversar(ollama, historico, pergunta, contexto):
    sistema = PERSONA + "\n\n" + REGRAS_JOGO + "\n\nSituação atual do caçador (use se for útil):\n" + \
        json.dumps(contexto, ensure_ascii=False)
    msgs = [{"role": "system", "content": sistema}] + historico[-10:] + [{"role": "user", "content": pergunta}]
    return ollama.chat(msgs, temperatura=0.7).strip()
