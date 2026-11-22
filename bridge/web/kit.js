// ---------------------------------------------------------------- Caçada por espécie (Diário de campo)
// Balística, armas (com munição e acessórios), chamadores, chamarizes e iscas da espécie, com botões que
// arrumam a mochila do jogo. Espaços numerados: 1 e 2 armas, 3 a 8 equipamentos.
let kit = null, kitTag = null, kitPedido = 0, kitOcupadoAte = 0;

async function carregarKit(tag, forcar) {
  const caixa = $("kit");
  if (!caixa || caixa.dataset.tag !== tag) return;
  if (!forcar && document.querySelector(".mo-modal")) return;
  const n = ++kitPedido;
  let d;
  try { d = await (await fetch("/api/kit?tag=" + encodeURIComponent(tag))).json(); } catch { return; }
  if (n !== kitPedido || !$("kit") || $("kit").dataset.tag !== tag) return;
  kit = d; kitTag = tag;
  desenharKit();
}
setInterval(() => { if (abaAtual === "enciclopedia" && kitTag && $("kit")) carregarKit(kitTag); }, 8000);

const kitPode = () => kit && kit.em_reserva && kit.lida && !kit.fila && Date.now() > kitOcupadoAte;
const kitSlot = (n) => kit.slots.find(s => s.n === n);
const kitFoto = (i, larga) => moFoto(i, larga ? "larga" : "");

function desenharKit() {
  const caixa = $("kit");
  if (!caixa || !kit) return;
  if (!kit.pronto) { caixa.innerHTML = ""; return; }
  const pode = kitPode();
  const servemItens = new Set([...kit.armas.filter(a => a.tem).map(a => a.item), ...kit.objetos.map(o => o.item)]);
  const status = !kit.em_reserva ? `<span class="mo-status off">● Entre numa reserva no jogo para mexer na mochila</span>`
    : !kit.lida ? `<span class="mo-status ocupado">● Lendo a mochila do jogo…</span>`
    : !pode ? `<span class="mo-status ocupado">● Arrumando a mochila no jogo…</span>`
    : `<span class="mo-status on">● Mochila do jogo ao vivo</span>`;

  // faixa com os 8 espaços
  const faixa = kit.lida ? `<div class="kit-faixa">${["Inventory.Weapon", "Inventory.Objects"].map(t => `
      <div class="kit-grupo ${t === "Inventory.Weapon" ? "armas" : ""}"><span class="kit-grupo-rot">${t === "Inventory.Weapon" ? "Armas" : "Equipamentos"}</span>
        <div class="kit-espacos">${kit.slots.filter(s => s.tipo === t).map(s => `
          <div class="kit-esp ${s.item ? (servemItens.has(s.item) ? "serve" : "") : "vazio"}" title="${esc(s.nome || "Espaço livre")}">
            <b class="kit-num">${s.n}</b>${s.item ? kitFoto(s, t === "Inventory.Weapon") : `<div class="kit-livre">livre</div>`}
            <span class="kit-esp-nome">${esc(s.nome || "")}</span></div>`).join("")}</div></div>`).join("")}</div>` : "";

  // balística
  const grupos = {};
  kit.balistica.forEach(b => (grupos[b.grupo] ||= []).push(b));
  const balistica = Object.entries(grupos).map(([g, l]) => `<div class="kit-bal-grupo"><span>${esc(g)}</span>
      ${l.map(b => `<button class="kit-cal ${b.armas_suas ? "" : "sem"}" onclick="kitArmas('${esc(b.id)}','${esc(b.nome)}')" data-dica="${dicaEspecies(b.nome, b.especies)}">
        ${esc(b.nome)}<small>${b.armas_suas ? b.armas_suas + " arma" + (b.armas_suas > 1 ? "s" : "") : "sem arma"}</small></button>`).join("")}</div>`).join("");
  const proib = kit.proibidos.length ? `<div class="dp-proib"><b>Proibido para esta espécie:</b> ${chips(kit.proibidos, "vermelho")}</div>` : "";

  // armas na mochila que servem
  const armasNaMochila = kit.armas.filter(a => a.slot);
  const armasTxt = armasNaMochila.length
    ? armasNaMochila.map(a => `<div class="kit-arma-mochila"><b class="kit-num">${a.slot}</b>${kitFoto(a, true)}<div><b>${esc(a.nome)}</b>
        <small>${esc(a.tipo)} · ${!a.municao_atual ? "munição: não lida ainda" : a.municao_atual_serve
          ? "munição: " + esc(a.municao_atual_nome) : `<span class="kit-ruim">munição ${esc(a.municao_atual_nome || "?")} não serve</span>`}</small></div>
        ${pode ? `<button class="kit-btn sec" onclick="kitArma('${esc(a.id)}')">Munição e acessórios</button>` : ""}</div>`).join("")
    : `<p class="mo-dica">Nenhuma arma da mochila serve para esta espécie. Clique num calibre acima ou em “Escolher arma”.</p>`;

  // chamadores, chamarizes e iscas
  const objetos = kit.objetos.length ? kit.objetos.map(o => {
    const acao = o.slot ? `<span class="mo-selo sim">no espaço ${o.slot}</span>`
      : o.tem ? (pode ? `<button class="kit-btn" onclick="kitPorObjeto('${esc(o.item)}')">Pôr na mochila</button>` : `<span class="mo-dica">Você tem</span>`)
      : o.dlc ? `<span class="mo-dica" data-dica="${esc("Item do pacote extra (DLC) " + o.dlc + ". O jogo só vende se você tiver esse DLC.")}">DLC ${esc(o.dlc)}</span>`
      : `<button class="kit-btn sec" onclick="comprarItem('${esc(o.id)}','${esc(o.nome).replace(/'/g, "")}',${o.preco || 0})">Comprar $${fmt(o.preco)}</button>`;
    return `<div class="kit-obj ${o.slot ? "na" : ""} ${o.tem ? "" : "loja"}">${kitFoto(o)}<div class="kit-obj-info">
        <span class="kit-papel ${o.papel}">${{ chamador: "Chamador", chamariz: "Chamariz", isca: "Isca de cheiro" }[o.papel]}</span>
        <b>${esc(o.nome)}</b><small>${esc(o.efeito)}${o.cargas ? ` · ${o.cargas} usos` : ""}</small></div><div class="kit-obj-acao">${acao}</div></div>`;
  }).join("") : `<p class="mo-dica">Nenhum chamador, chamariz ou isca do jogo funciona com esta espécie.</p>`;

  const suas = kit.armas.filter(a => a.tem).length;
  caixa.innerHTML = `<section class="kit-painel">
    <header class="kit-topo"><div><h3>Montar a caçada ${ajuda("kit")}</h3>${status}</div>
      <button class="mo-principal" ${pode ? "" : "disabled"} onclick="kitAuto()"><span class="mo-principal-ico">★</span>
        <span><b>Montar para esta espécie</b><small>arma, munição, chamador e isca de uma vez</small></span></button></header>
    ${faixa}
    <div class="kit-colunas">
      <div class="kit-bloco"><h4>Balística ${ajuda("balistica")}<small>clique num calibre para ver as armas</small></h4>${balistica || `<p class="mo-dica">O jogo não lista calibres para esta espécie.</p>`}${proib}</div>
      <div class="kit-bloco"><h4>Arma na mochila ${ajuda("arma_mochila")}<small>${suas} arma${suas === 1 ? "" : "s"} sua${suas === 1 ? "" : "s"} servem</small></h4>${armasTxt}
        ${pode && suas ? `<button class="kit-btn" onclick="kitArmas('','')">Escolher arma</button>` : ""}</div>
      ${kitLicenca()}
      <div class="kit-bloco largo"><h4>Chamadores, chamarizes e iscas ${ajuda("atrair")}</h4><div class="kit-objs">${objetos}</div></div>
    </div></section>`;
}

// ---- licença de caça da espécie
function kitLicenca() {
  const l = kit.licenca;
  if (!l) return "";
  const n = l.max;
  const marcas = l.ilimitada ? "" : `<div class="kit-lic-marcas">${Array.from({ length: n }, (_, i) =>
      `<i class="${l.tem && i < l.usados ? "usada" : l.tem ? "livre" : "nao"}"></i>`).join("")}</div>`;
  const situacao = !l.tem ? "Você não tem licença para esta espécie"
    : l.ilimitada ? "Licença ilimitada"
    : l.restam > 0 ? `Restam <b>${l.restam}</b> de ${n} animais` : "<b>Licença esgotada</b>: você já usou os " + n + " animais";
  const precisa = !l.tem || (!l.ilimitada && l.restam === 0);
  const botao = !precisa ? "" : l.comprar_aqui
    ? `<button class="kit-btn" ${kitPode() || kit.em_reserva ? "" : "disabled"} onclick="kitComprarLicenca()">Comprar licença · $${fmt(l.preco)}</button>`
    : `<span class="mo-dica">Para comprar, entre numa reserva onde esta espécie vive.</span>`;
  return `<div class="kit-bloco largo kit-lic ${precisa ? "acabou" : ""}">
      ${kit.licenca_imagem ? `<img src="${kit.licenca_imagem}" alt="" onerror="this.remove()">` : ""}
      <div class="kit-lic-info"><h4>Licença de caça ${ajuda("licenca")}<small>${n} animais por licença · $${fmt(l.preco)}</small></h4>
        <div class="kit-lic-sit">${situacao}${l.tem && l.reserva && !l.comprar_aqui ? ` <small>(leitura de ${esc(nomeMapa(l.reserva))})</small>` : ""}</div>
        ${marcas}${botao}</div></div>`;
}
async function kitComprarLicenca() {
  const l = kit.licenca;
  if (!confirm(`Comprar a licença de ${kit.nome} por $${fmt(l.preco)}? Ela vale para ${l.max} animais nesta reserva.`)) return;
  let r;
  try { r = await post("/api/licenca", { tag: kit.tag }); } catch { return moAviso("O app não respondeu.", "erro"); }
  if (!r.ok) return moAviso(r.erro || "Não deu certo.", "erro");
  moAviso("Comprando a licença no jogo…");
  for (let i = 0; i < 12; i++) {
    await new Promise(ok => setTimeout(ok, 1000));
    let s;
    try { s = await (await fetch("/api/compra?ref=" + r.ref)).json(); } catch { continue; }
    if (!s.pronto) continue;
    moAviso(s.ok ? `Licença comprada. Saldo agora $${fmt(s.saldo)}.` : "O jogo não aceitou a compra da licença.", s.ok ? "ok" : "erro");
    setTimeout(() => carregarKit(kitTag, true), 1500);
    return;
  }
  moAviso("O jogo não confirmou a compra. Confira as licenças no jogo.", "erro");
}

// ---- escolher arma (todas ou só de um calibre)
function kitArmas(carga, calibre) {
  const lista = kit.armas.filter(a => !carga || a.cargas.includes(carga));
  const suas = lista.filter(a => a.tem), loja = lista.filter(a => !a.tem);
  const cartao = (a) => `<button class="mo-opcao ${a.indicada ? "serve" : ""}" ${a.tem ? `onclick="kitArma('${esc(a.id)}')"` : "disabled"}>
      ${kitFoto(a, true)}<span class="mo-opcao-nome">${esc(a.nome)}</span>
      <span class="mo-opcao-sub">${esc(a.tipo)} · ${esc(a.calibres.join(", "))}</span>
      ${a.slot ? `<span class="mo-selo sim">no espaço ${a.slot}</span>` : a.indicada ? `<span class="mo-selo rec">indicada</span>` : ""}
      ${a.tem && !a.municoes.some(m => m.tem) ? `<span class="mo-opcao-sub aviso">sem munição sua para esta espécie</span>` : ""}
      ${a.tem ? "" : `<span class="mo-opcao-sub">na loja · $${fmt(a.preco)}</span>`}</button>`;
  moModal(`<header class="mo-jan-topo"><div><h3>${calibre ? "Armas " + esc(calibre) : "Escolher arma"}</h3>
      <small>${esc(kit.nome)} · “indicada” = o tipo de arma mais usado para esta espécie</small>
      ${carga ? (() => { const b = kit.balistica.find(x => x.id === carga); return b && b.especies.length ? `<small class="kit-serve">Esta munição serve para: ${esc(b.especies.join(", "))}</small>` : ""; })() : ""}</div>
      <input class="mo-busca" placeholder="Procurar…" oninput="moFiltrar(this.value)"><button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo">
      ${suas.length ? `<h4>Suas armas (${suas.length})</h4><div class="mo-opcoes">${suas.map(cartao).join("")}</div>` : `<p class="mo-dica">Você não tem arma para este calibre.</p>`}
      ${loja.length ? `<h4>Na loja do jogo (${loja.length})</h4><div class="mo-opcoes">${loja.map(cartao).join("")}</div>` : ""}
    </div>`);
  document.querySelectorAll(".mo-opcao").forEach(b => { b.dataset.nome = b.textContent.toLowerCase(); b.dataset.cat = ""; });
  moFiltroCat = ""; moFiltroTxt = "";
}

// ---- arma escolhida: espaço, munição e acessórios
let kitEscolha = null;
function kitArma(id) {
  const a = kit.armas.find(x => x.id === id);
  if (!a) return;
  const armas = kit.slots.filter(s => s.tipo === "Inventory.Weapon");
  const livre = armas.find(s => !s.item);
  const serveIds = new Set(kit.armas.filter(x => x.slot).map(x => x.item));
  kitEscolha = { arma: a.id, espaco: a.slot || (livre || armas.find(s => !serveIds.has(s.item)) || armas[armas.length - 1]).n,
                 municao: a.municao_atual || (a.municoes.find(m => m.tem) || {}).id || "", acessorios: {} };
  desenharKitArma();
}
function desenharKitArma() {
  const e = kitEscolha, a = kit.armas.find(x => x.id === e.arma);
  const armas = kit.slots.filter(s => s.tipo === "Inventory.Weapon");
  const espacos = armas.map(s => `<button class="kit-escolha ${e.espaco === s.n ? "on" : ""}" onclick="kitEscolha.espaco=${s.n};desenharKitArma()">
      <b class="kit-num">${s.n}</b><span>${s.item === a.item ? "fica aqui" : s.item ? "sai: " + esc(s.nome) : "espaço livre"}</span></button>`).join("");
  const minhas = a.municoes.filter(m => m.tem);
  const muni = minhas.length ? minhas.map(m => `<button class="kit-escolha ${e.municao === m.id ? "on" : ""}" data-dica="${dicaEspecies(m.nome, m.especies)}" onclick="kitEscolha.municao='${esc(m.id)}';desenharKitArma()">
      <span>${esc(m.nome)}</span>${m.atual ? `<small>carregada</small>` : ""}</button>`).join("")
    : `<p class="mo-aviso">Você não tem munição desta arma que sirva para ${esc(kit.nome)}. Compre na loja do jogo.</p>`;
  const aces = (a.acessorios || []).map(enc => {
    const quer = e.acessorios[enc.encaixe];
    const op = (id, nome, sub, foto) => `<button class="mo-opcao ${(quer === undefined ? id === null : quer === id) ? "montado" : ""}"
        onclick="kitEscolha.acessorios['${esc(enc.encaixe)}']=${id === null ? "undefined" : `'${esc(id)}'`};desenharKitArma()">
        ${foto || `<div class="mo-foto"><span class="mo-foto-ini">${id === null ? "=" : "∅"}</span></div>`}<span class="mo-opcao-nome">${esc(nome)}</span><span class="mo-opcao-sub">${esc(sub)}</span></button>`;
    const atual = a.montados_conhecidos ? (enc.atual_nome ? "montado: " + enc.atual_nome : "nada montado") : "o que está montado aparece depois que a arma estiver na mochila";
    return `<h4>${esc(enc.nome)} <small>${esc(atual)}</small></h4><div class="mo-opcoes">
      ${op(null, "Manter como está", "não mexe")}${op("", "Sem " + enc.nome.toLowerCase(), "tira o que estiver montado")}
      ${enc.opcoes.filter(o => !o.atual).map(o => op(o.id, o.nome, o.tipo + (_zoomTxt(o.nome)), kitFoto(o))).join("")}</div>`;
  }).join("");
  moModal(`<header class="mo-jan-topo"><div><h3>${esc(a.nome)}</h3><small>${esc(a.tipo)} · ${esc(a.calibres.join(", "))} · para ${esc(kit.nome)}</small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo">
      <h4>1 · Em qual espaço?</h4><div class="kit-escolhas">${espacos}</div>
      <h4>2 · Munição</h4><div class="kit-escolhas">${muni}</div>
      ${(() => { const m = minhas.find(x => x.id === e.municao); return m && m.especies && m.especies.length ? `<p class="kit-serve">${esc(m.nome)} serve para: ${esc(m.especies.join(", "))}</p>` : ""; })()}
      ${aces ? `<h4 class="kit-sub">3 · Acessórios</h4>${aces}` : ""}
    </div>
    <footer class="mo-jan-rodape"><button class="sec" onclick="moFecharModal()">Cancelar</button>
      <button class="ok" onclick="kitConfirmarArma()">Levar para a caçada</button></footer>`);
}
const _zoomTxt = (n) => { const m = /(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+)\s*x/.exec(n || ""); return m ? ` · ${m[1]}–${m[2]}x` : ""; };
function kitConfirmarArma() {
  const e = kitEscolha, acess = {};
  Object.entries(e.acessorios).forEach(([k, v]) => { if (v !== undefined) acess[k] = v; });
  moFecharModal();
  kitEnviar({ acao: "kit", tag: kit.tag, escolha: { arma: e.arma, espaco: e.espaco, municao: e.municao, acessorios: acess } });
}

// ---- chamador / chamariz / isca: espaço livre ou trocar um dos espaços 3-8
function kitPorObjeto(item) {
  const o = kit.objetos.find(x => x.item === item);
  const espacos = kit.slots.filter(s => s.tipo === "Inventory.Objects");
  const livre = espacos.find(s => !s.item);
  if (livre) return kitEnviar({ acao: "kit", tag: kit.tag, escolha: { objetos: [{ item, espaco: livre.n }] } });
  const servem = new Set(kit.objetos.map(x => x.item));
  moModal(`<header class="mo-jan-topo"><div><h3>Mochila cheia</h3><small>Escolha o espaço onde entra: <b>${esc(o.nome)}</b></small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo"><div class="mo-opcoes">${espacos.map(s => `<button class="mo-opcao ${servem.has(s.item) ? "serve" : ""}"
        onclick="moFecharModal();kitEnviar({acao:'kit',tag:kit.tag,escolha:{objetos:[{item:'${esc(item)}',espaco:${s.n}}]}})">
        ${kitFoto(s)}<span class="mo-opcao-nome">${s.n} · ${esc(s.nome)}</span>
        <span class="mo-opcao-sub">${servem.has(s.item) ? "também serve para esta espécie" : "sai da mochila"}</span></button>`).join("")}</div></div>`);
}

// ---- montar tudo
async function kitAuto() {
  let r;
  try { r = await post("/api/mochila", { acao: "kit_previa", tag: kit.tag }); } catch { return moAviso("O app não respondeu.", "erro"); }
  if (!r.ok) return moAviso(r.erro || "Não deu certo.", "erro");
  if (!r.resumo.length) return moAviso("A mochila já está pronta para esta espécie.", "ok");
  const linhas = r.resumo.map(x => `<li><span class="mo-li-onde">${esc(x.onde)}</span>${x.sai ? `<s>${esc(x.sai)}</s> → ` : ""}<b>${esc(x.entra)}</b></li>`).join("");
  kitEscolha = r.escolha;
  moModal(`<header class="mo-jan-topo"><div><h3>Montar para ${esc(kit.nome)}</h3><small>O que vai mudar no jogo</small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo"><ul class="mo-lista-plano">${linhas}</ul>
      <p class="mo-dica">Os acessórios da arma ficam como estão. Para trocar luneta, silenciador ou bipé, use “Munição e acessórios” depois.
      As trocas são feitas uma por segundo para o jogo não travar.</p></div>
    <footer class="mo-jan-rodape"><button class="sec" onclick="moFecharModal()">Cancelar</button>
      <button class="ok" onclick="moFecharModal();kitEnviar({acao:'kit',tag:kit.tag,escolha:kitEscolha})">Montar agora</button></footer>`);
}

async function kitEnviar(corpo) {
  let r;
  try { r = await post("/api/mochila", corpo); } catch { return moAviso("O app não respondeu.", "erro"); }
  if (!r.ok) return moAviso(r.erro || "Não deu certo.", "erro");
  if (r.nada) return moAviso("Nada para mudar: já está assim no jogo.");
  const seg = r.segundos || 3;
  kitOcupadoAte = Date.now() + seg * 1000;
  moAviso(r.trocas > 1 ? `Enviando ${r.trocas} trocas para o jogo…` : "Enviado para o jogo…", "ok");
  desenharKit();
  setTimeout(() => { kitOcupadoAte = 0; carregarKit(kitTag, true); }, (seg + 1.5) * 1000);
  setTimeout(() => carregarKit(kitTag, true), (seg + 6) * 1000);
}
