// ---------------------------------------------------------------- Ajuda: botão "?" ao lado de cada função
// Funciona com clique (PC) e toque (celular). Os textos ficam todos aqui.
const AJUDA = {
  creditos: ["Créditos", "O dinheiro do jogo, lido ao vivo. Os contratos do Earl pagam em créditos direto no jogo."],
  patente: ["Patente", "Seu nível no app. Sobe com animais abatidos (vale mais quem tem genética alta e tiro longo) e com contratos concluídos."],
  reputacao: ["Reputação na reserva", "A reputação com o vendedor da reserva em que você está. Os contratos do Earl também dão reputação."],
  campo: ["Pontos de campo", "Pontos da reserva atual que o jogo dá ao explorar e caçar. Servem para desbloquear coisas na loja da reserva."],
  atualizar: ["Procurar atualização", "Procura uma versão nova do app na internet. Se tiver, baixa, troca o programa e o mod e reabre sozinho. Depois feche e abra o jogo uma vez."],
  celular: ["Usar no celular", "Mostra o QR code para abrir este app no celular, pela mesma rede Wi-Fi. O PC continua ligado com o jogo e o app abertos; o celular vira uma segunda tela."],
  camadas: ["Camadas do mapa", "Liga e desliga o que aparece no mapa: pontos da reserva (torres, acampamentos, lugares), estruturas, névoa (áreas que você ainda não explorou) e os animais marcados no binóculo."],
  nevoa: ["Névoa", "Lê do jogo as áreas que você já explorou. O jogo dá uma travadinha de 1 segundo nessa leitura, por isso ela só acontece quando você toca aqui."],
  pino: ["Pino no mapa", "Toque/clique num ponto do mapa para marcar um pino. Ele aparece também no mapa do jogo, para você ir até lá."],
  voltar: ["Voltar ao último local", "Ao entrar numa reserva, o jogo te leva de volta para onde você estava quando saiu (por viagem rápida)."],
  contratos: ["Contratos do Earl", "Trabalhos com recompensa em créditos e reputação. Aceite em Ofertas, cumpra no jogo (o app confere sozinho pelos abates, marcações e lugares) e o pagamento cai no jogo."],
  ofertas: ["Ofertas", "Contratos disponíveis. Aceitar coloca em andamento; Outro troca por um novo; Trocar todos renova a mesa inteira."],
  andamento: ["Em andamento", "Contratos aceitos e o progresso de cada um. Os contratos do próprio jogo também aparecem aqui, marcados como JOGO."],
  dicas: ["Dicas", "Pergunte ao Earl sobre vento, calibre, chamador, distância, roupa ou uma espécie. As respostas são prontas e não pesam no PC."],
  hud: ["Contratos dentro do jogo", "Mostra os contratos do app na caixa de objetivos do próprio jogo, com o progresso."],
  mochila: ["Mochila", "A mochila que você leva para a caçada, lida ao vivo do jogo: espaços 1 e 2 são armas, 3 a 8 equipamentos, mais o GPS. Dá para trocar itens daqui; o jogo precisa estar numa reserva."],
  mochila_contratos: ["Para quais contratos?", "Escolha os contratos que vai fazer. O app pinta de verde o que serve para eles e monta uma sugestão de mochila."],
  mochila_montar: ["Montar mochila sugerida", "Faz no jogo as trocas sugeridas (armas, munição e equipamentos), uma por segundo para o jogo não travar."],
  loja: ["Roupas", "Quanto os animais te veem, ouvem e sentem com a roupa de agora, e o catálogo com a camuflagem de cada peça. Comprar daqui compra na loja do jogo."],
  diario: ["Diário de campo", "Tudo do jogo: animais, armas, munição, roupas, itens, cães e o guia. Em cada animal você monta a caçada e vê a licença."],
  ler_dados: ["Ler dados do jogo", "Copia do jogo as fotos e as informações do diário. Só precisa uma vez (10 a 15 minutos, aos poucos, sem travar o jogo)."],
  kit: ["Montar a caçada", "Tudo o que serve para caçar esta espécie, com botões que arrumam a mochila do jogo. “Montar para esta espécie” escolhe arma, munição, chamador e isca de uma vez e mostra antes o que vai mudar."],
  balistica: ["Balística", "Os calibres que o jogo permite para esta espécie. Toque num calibre para ver as armas dele; passe o mouse (ou toque) para ver em quais outras espécies a munição também serve."],
  arma_mochila: ["Arma na mochila", "As armas da mochila que servem para esta espécie. Em “Munição e acessórios” você troca a munição carregada, a luneta, o silenciador e o bipé."],
  licenca: ["Licença de caça", "Cada licença vale para um número de animais da espécie naquela reserva. Os quadradinhos verdes são os que ainda restam. Quando acaba, compre outra aqui (só dentro da reserva da espécie)."],
  atrair: ["Chamadores, chamarizes e iscas", "Chamador atrai a espécie até você (uns 500 m). Chamariz (boneco) deixa a espécie mais calma por perto. Isca de cheiro atrai pelo faro, a favor do vento."],
  cacadas: ["Caçadas", "Tudo o que o app registrou: abates por espécie e por arma, distâncias, genética e os últimos abates."],
  ajustes: ["Ajustes", "Pasta do jogo, instalação do mod e “começar do zero” para quando você inicia um jogo novo."],
};

const ajuda = (chave) => AJUDA[chave] ? `<button type="button" class="ajuda" aria-label="O que é isto?" onclick="event.stopPropagation();event.preventDefault();mostrarAjuda('${chave}', this)">?</button>` : "";

function mostrarAjuda(chave, el) {
  document.querySelectorAll(".ajuda-pop").forEach(p => p.remove());
  const [titulo, texto] = AJUDA[chave] || ["", ""];
  const p = document.createElement("div");
  p.className = "ajuda-pop";
  p.innerHTML = `<b>${esc(titulo)}</b><p>${esc(texto)}</p><button type="button" onclick="this.parentElement.remove()">Entendi</button>`;
  document.body.appendChild(p);
  if (el && innerWidth > 820) {        // no PC aparece perto do botão; no celular, embaixo, em largura cheia
    const r = el.getBoundingClientRect(), w = p.offsetWidth, h = p.offsetHeight;
    p.style.left = Math.min(Math.max(10, r.left - 20), innerWidth - w - 10) + "px";
    p.style.top = (r.bottom + h + 12 > innerHeight ? r.top - h - 8 : r.bottom + 8) + "px";
  } else p.classList.add("baixo");
}
document.addEventListener("click", (e) => {
  if (!e.target.closest(".ajuda-pop") && !e.target.closest(".ajuda")) document.querySelectorAll(".ajuda-pop").forEach(p => p.remove());
});

// botões "?" das partes fixas da página
document.querySelectorAll("[data-ajuda]").forEach(el => el.insertAdjacentHTML("beforeend", ajuda(el.dataset.ajuda)));

// primeira vez: avisa que existem os "?"
try {
  if (!localStorage.getItem("hs3_ajuda_vista")) {
    localStorage.setItem("hs3_ajuda_vista", "1");
    setTimeout(() => moAviso("Dica: toque nos “?” para saber o que cada parte do app faz."), 2500);
  }
} catch {}
