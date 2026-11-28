const $ = (id) => document.getElementById(id);
const fmt = (n) => (n === null || n === undefined) ? "–" : Number(n).toLocaleString("pt-BR");
const pct = (n) => (n === null || n === undefined) ? "–" : Math.round(n * 100) + "%";
const metros = (n) => (n === null || n === undefined) ? "–" : (n >= 1000 ? (n / 1000).toFixed(2).replace(".", ",") + " km" : Math.round(n) + " m");
// dica flutuante: qualquer elemento com data-dica (texto já escapado) mostra a caixa ao passar o mouse
const dicaEspecies = (nome, l) => esc(`<b>${esc(nome)}</b> serve para ${l && l.length ? l.length + " espécie" + (l.length > 1 ? "s" : "") + ":<br>" + l.map(esc).join(", ") : "nenhuma espécie da tabela do jogo"}`);
const dicaCaixa = document.createElement("div");
dicaCaixa.className = "dica-flut";
document.body.appendChild(dicaCaixa);
// dica: passar o mouse (PC) ou tocar (celular)
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("[data-dica]")) mostrarDica(e); });
document.addEventListener("mouseover", mostrarDica);
function mostrarDica(e) {
  const el = e.target.closest && e.target.closest("[data-dica]");
  if (!el || !el.dataset.dica) { dicaCaixa.style.display = "none"; return; }
  dicaCaixa.innerHTML = el.dataset.dica;
  dicaCaixa.style.display = "block";
  const r = el.getBoundingClientRect(), w = dicaCaixa.offsetWidth, h = dicaCaixa.offsetHeight;
  let x = Math.min(Math.max(8, r.left), innerWidth - w - 8), y = r.bottom + 8;
  if (y + h > innerHeight - 8) y = r.top - h - 8;
  dicaCaixa.style.left = x + "px"; dicaCaixa.style.top = y + "px";
}
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const post = (url, body) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(r => r.json());

// ------------------------------------------------------------------ mapa
const S = 4096;                         // unidades do mapa (pixels da imagem exportada)
let MUNDO = 1224000;                    // largura do mundo em cm (vem do jogo)
const toLL = (p) => [-(p.y / MUNDO + 0.5) * S, (p.x / MUNDO + 0.5) * S];
const fromLL = (ll) => ({ x: (ll.lng / S - 0.5) * MUNDO, y: (-ll.lat / S - 0.5) * MUNDO });

const mapa = L.map("mapa", { crs: L.CRS.Simple, minZoom: -3, maxZoom: 2, zoomSnap: 0.25, attributionControl: false, zoomControl: false });
L.control.zoom({ position: "bottomright" }).addTo(mapa);
const limites = [[-S, 0], [0, S]];
mapa.fitBounds(limites);
let camadaImagem = null, camadaNevoa = null, nivelAtual = null, nevoaVersao = 0;
const grupoPois = L.layerGroup().addTo(mapa);
const grupoEstr = L.layerGroup();
const grupoZonas = L.layerGroup().addTo(mapa);
// zonas de necessidade descobertas (como no mapa do jogo): silhueta da espécie + cor do tipo
const TIPO_ZONA = { Eating: ["Comer", "comer"], Drinking: ["Beber", "beber"], Sleeping: ["Descansar", "dormir"] };
let zonasTexto = "";
async function carregarZonas() {
  let texto = "", lista = [];
  try { texto = await (await fetch("/api/zonas")).text(); lista = JSON.parse(texto); } catch { return; }
  if (texto === zonasTexto) return;
  zonasTexto = texto;
  grupoZonas.clearLayers();
  for (const z of lista) {
    if (!z.descoberta) continue;
    const [nome, cls] = TIPO_ZONA[z.tipo] || [z.tipo, "comer"];
    L.marker(toLL(z), { icon: L.divIcon({ className: "", html: `<div class="mk-zona ${cls}">${silhueta(z.grupo || "outro", z.especie)}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] }) })
      .bindTooltip(`<b>${esc(z.especie_nome || "")}</b><br>Zona de ${nome.toLowerCase()}`)
      .bindPopup(() => popupZona(z, nome), { maxWidth: 300, autoPanPadding: [20, 60] })
      .on("click", () => marcarSeguindo(false))
      .addTo(grupoZonas);
  }
}
const NOME_TIPO = { Eating: "comer", Drinking: "beber", Sleeping: "descansar" };
function popupZona(z, nome) {
  const horas = (z.horas || []);
  const faixas = horas.length ? horas.map(h => `${String(h).padStart(2, "0")}h`).join(", ") : "ainda sem registro (marque animais aqui com o binóculo)";
  const bando = (z.bando_tipos || []).map(t => NOME_TIPO[t] || t);
  return `<div class="pop-zona">
    <div class="pz-cab"><span class="mk-zona ${(TIPO_ZONA[z.tipo] || [])[1] || "comer"}">${silhueta(z.grupo || "outro", z.especie)}</span>
      <div><b>${esc(z.especie_nome || "")}</b><small>Zona de ${esc(nome.toLowerCase())} · raio ~${Math.round((z.raio || 0) / 100)} m</small></div></div>
    <div class="ficha-lin"><span>Bando nº</span><b>${z.bando ?? "–"}</b></div>
    <div class="ficha-lin"><span>Zonas do bando que você achou</span><b>${bando.length ? esc(bando.join(", ")) : "–"}</b></div>
    <div class="ficha-lin"><span>Animais vistos aqui</span><b>${z.vistos || 0}${z.vistos ? ` (${z.machos || 0} ♂ · ${z.femeas || 0} ♀)` : ""}</b></div>
    <div class="ficha-lin"><span>Horários em que você viu</span><b>${esc(faixas)}</b></div>
    ${z.ultimo_dia != null && z.vistos ? `<div class="ficha-lin"><span>Última visita</span><b>dia ${z.ultimo_dia} do jogo</b></div>` : ""}
    <button class="btn-papel" style="margin-top:8px;width:100%" onclick="abrirZona(${esc(JSON.stringify({ especie: z.especie }))})">Ver espécie no Diário</button>
  </div>`;
}
let diarioPedido = null;
function abrirZona(z) {
  if (!z.especie) return;
  diarioPedido = z.especie; diarioCat = "animais"; diarioBusca = "";
  document.querySelector('#abas button[data-aba="enciclopedia"]')?.click();
  if (diario) desenharDiario();
}
const grupoAnimais = L.layerGroup().addTo(mapa);
const grupoMissoes = L.layerGroup().addTo(mapa);
let marcJogador = null, marcPino = null;
const marcAnimais = {};
let jaCentralizou = false, ultimoEstado = null;

// ícones no estilo do mapa do jogo: desenho branco dentro de um círculo colorido
const SVG_POI = {
  lugar: '<path d="M12 21s-6-5.6-6-10.5a6 6 0 0 1 12 0C18 15.4 12 21 12 21z"/><circle cx="12" cy="10.5" r="2.2"/>',
  torre: '<path d="M7 21l2-11h6l2 11M9 10V6h6v4M8 6l4-3 4 3M10 15h4M9.5 18h5"/>',
  acampamento: '<path d="M3 20L12 5l9 15zM12 20v-6l-3 6M12 14l3 6"/>',
  estrutura: '<path d="M7 21l1.5-9h7L17 21M8 12V8h8v4M7 8h10M10 16h4"/>',
  sede: '<path d="M4 11l8-6 8 6M6 10v10h12V10M10 20v-5h4v5"/>',
  loja: '<path d="M4 5h2l2 10h10l2-7H7"/><circle cx="9" cy="19" r="1.4"/><circle cx="17" cy="19" r="1.4"/>',
  servico: '<path d="M12 4l2.4 5 5.6.6-4.2 3.8 1.2 5.6L12 16.3 7 19l1.2-5.6L4 9.6 9.6 9z"/>',
  relogio: '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
  garagem: '<path d="M3 11l9-6 9 6v9H3zM7 20v-6h10v6M7 17h10"/>',
  roupa: '<path d="M8 4l4 2 4-2 4 4-3 3v9H7v-9L4 8z"/>',
  npc: '<circle cx="12" cy="8" r="3.4"/><path d="M5 20c.8-4 3.6-6 7-6s6.2 2 7 6"/>',
  veiculo: '<path d="M3 16V11l2-4h8l3 4h4a1 1 0 0 1 1 1v4M3 16h18"/><circle cx="7.5" cy="17" r="2"/><circle cx="16.5" cy="17" r="2"/>',
  cao: '<circle cx="7" cy="9" r="1.8"/><circle cx="12" cy="6.5" r="1.8"/><circle cx="17" cy="9" r="1.8"/><path d="M12 12c3 0 5.5 3.4 5.5 5.5 0 1.6-1.4 2.5-3 2.5-1 0-1.6-.6-2.5-.6s-1.5.6-2.5.6c-1.6 0-3-.9-3-2.5C6.5 15.4 9 12 12 12z"/>',
  viagem: '<path d="M4 9h13l-3-3M20 15H7l3 3"/>',
  oculto: '<path d="M9.2 9.2a2.9 2.9 0 1 1 3.9 2.7c-.7.3-1.1.9-1.1 1.6v.8"/><circle cx="12" cy="17.6" r=".6"/>',
};
function chaveIcone(p) {
  if (!p.descoberto) return "oculto";
  if (p.categoria === "servico") {
    const t = p.tipo || "";
    if (/Store/.test(t)) return "loja";
    if (/Clock/.test(t)) return "relogio";
    if (/Garage/.test(t)) return "garagem";
    if (/Wardrobe|Customization/.test(t)) return "roupa";
  }
  return SVG_POI[p.categoria] ? p.categoria : "lugar";
}
function iconePoi(p) {
  const k = chaveIcone(p), peq = p.categoria === "estrutura" || !p.descoberto;
  const lado = peq ? 22 : 28;
  return L.divIcon({ className: "", html: `<div class="mk-poi ${p.descoberto ? p.categoria : "oculto"} ic-${k}" style="width:${lado}px;height:${lado}px">
      <svg viewBox="0 0 24 24">${SVG_POI[k]}</svg></div>`, iconSize: [lado, lado], iconAnchor: [lado / 2, lado / 2] });
}

let poisTexto = "";
async function carregarPois() {
  let lista = [];
  let texto = "";
  try { texto = await (await fetch("/api/pois")).text(); lista = JSON.parse(texto); } catch { return; }
  if (texto === poisTexto) return;      // nada mudou: não redesenha
  poisTexto = texto;
  grupoPois.clearLayers(); grupoEstr.clearLayers();
  for (const p of lista) {
    const m = L.marker(toLL(p), { icon: iconePoi(p), riseOnHover: true })
      .bindTooltip(`<b>${esc(p.descoberto ? p.nome : "Local não descoberto")}</b>${p.descoberto ? "" : "<br><i>Explore para revelar</i>"}`, { direction: "top", offset: [0, -12] });
    m.on("click", () => perguntarPino(L.latLng(toLL(p)), p.descoberto ? p.nome : "Local não descoberto", p.descoberto && PODE_IR.has(p.categoria) ? { x: p.x, y: p.y, z: p.z || 0 } : null));
    // estruturas de caça descobertas aparecem com os pontos; as que faltam descobrir ficam na camada "Estruturas"
    (p.categoria === "estrutura" && !p.descoberto ? grupoEstr : grupoPois).addLayer(m);
  }
}

function atualizarMapaBase(info) {
  if (!info || !info.nivel) return;
  MUNDO = info.tamanho_mundo || MUNDO;
  if (info.nivel !== nivelAtual && info.imagem) {
    nivelAtual = info.nivel;
    if (camadaImagem) mapa.removeLayer(camadaImagem);
    // JPEG leve: 2048 px no celular, 4096 px no PC (o PNG original tem ~22 MB)
    const lado = innerWidth <= 820 ? 2048 : 4096;
    camadaImagem = L.imageOverlay(`/api/mapa.jpg?n=${encodeURIComponent(nivelAtual)}&lado=${lado}`, limites, { className: "mapa-img" }).addTo(mapa);
    camadaImagem.bringToBack();
    nevoaVersao = -1;
    carregarPois(); carregarZonas();
  }
  if (info.nevoa && info.nevoa_versao !== nevoaVersao) {
    nevoaVersao = info.nevoa_versao;
    const nova = L.imageOverlay("/api/nevoa.png?v=" + nevoaVersao, limites, { opacity: 1, interactive: false });
    if ($("f-nevoa").checked) nova.addTo(mapa);
    if (camadaNevoa) mapa.removeLayer(camadaNevoa);
    camadaNevoa = nova;
    carregarPois(); carregarZonas();
  }
}

function setaJogador(yaw) {
  return L.divIcon({ className: "", iconSize: [30, 30], iconAnchor: [15, 15],
    html: `<div class="mk-jogador" style="transform:rotate(${yaw || 0}deg)"><svg viewBox="0 0 30 30"><path d="M28 15 L4 4 L10 15 L4 26 Z" fill="#d0661f" stroke="#2b1e12" stroke-width="1.5"/></svg></div>` });
}

let pinoPendente = null;
// animal clicado: no celular o ícone vai para a esquerda da tela, sobrando espaço para o cartão à direita
function centrarAnimal(ll) {
  marcarSeguindo(false);
  const w = mapa.getSize().x;
  const deslocar = w < 820 ? w * 0.3 : 0;
  mapa.panTo(mapa.unproject(mapa.project(ll).add([deslocar, 0])));
}
let destinoIr = null;
// viagem rápida só para pontos com função: agentes, acampamentos e torres (e as barracas do app)
const PODE_IR = new Set(["npc", "acampamento", "torre"]);
async function irAte(ev) {
  ev?.stopPropagation();
  if (!destinoIr) return;
  let r;
  try { r = await post("/api/ir", destinoIr); } catch { r = { ok: false, erro: "Sem resposta do app." }; }
  mapa.closePopup();
  if (!r.ok) await perguntar(r.erro || "Não deu para viajar.", "Ok");
  else marcarSeguindo(true);
}
function perguntarPino(ll, rotulo, destino) {
  marcarSeguindo(false);
  pinoPendente = { ll, rotulo };
  destinoIr = destino || null;
  const html = `<div class="pp-caixa" style="text-align:center"><b>${esc(rotulo || "Novo pino")}</b><br>
    <button class="btn-papel verde" id="pp-ok" style="margin-top:6px;padding:10px 14px" onclick="confirmarPino(event)">📍 Colocar pino aqui</button>
    ${destino ? `<button class="btn-papel" style="margin-top:6px;padding:10px 14px" onclick="irAte(event)" title="Viagem rápida até este ponto (como no mapa do jogo)">🚶 Ir até aqui</button>` : ""}</div>`;
  // no celular a telemetria fica no alto: o mapa se ajeita para o balão não ficar escondido atrás dela
  const celular = window.matchMedia("(max-width: 820px)").matches;
  L.popup({ autoPanPaddingTopLeft: celular ? [12, 180] : [12, 12], autoPanPaddingBottomRight: celular ? [12, 150] : [12, 12] })
    .setLatLng(ll).setContent(html).openOn(mapa);
  const caixa = document.querySelector(".pp-caixa");
  if (caixa) { L.DomEvent.disableClickPropagation(caixa); L.DomEvent.disableScrollPropagation(caixa); }
}
async function confirmarPino(ev) {
  if (ev) { ev.preventDefault(); ev.stopPropagation(); }
  if (!pinoPendente) return;
  const { ll, rotulo } = pinoPendente; pinoPendente = null;
  const w = fromLL(ll);
  mapa.closePopup();
  await post("/api/pino", { x: w.x, y: w.y, rotulo });
  atualizar();
}
mapa.on("click", (e) => perguntarPino(e.latlng, "Meu pino"));

// ---- barracas (Loja do Earl): até 10 por reserva, pagas com o dinheiro do jogo, viram ponto de viagem
const grupoBarracas = L.layerGroup().addTo(mapa);
let barracasTexto = "", barracasInfo = { preco: 300, max: 10, n: 0 };
// a barraca é montada onde você está agora no jogo
async function modoBarraca() {
  const n = barracasInfo.n;
  if (n >= barracasInfo.max) return perguntar(`Você já tem ${barracasInfo.max} barracas nesta reserva. Desmonte uma primeiro.`, "Ok");
  if (!await perguntar(`Montar uma barraca aqui, onde você está agora, por $${fmt(barracasInfo.preco)}?\n(${n} de ${barracasInfo.max} nesta reserva)\n\nDepois é só clicar nela no mapa e escolher "Ir até a barraca".`, "Montar")) return;
  const r = await post("/api/barraca", { acao: "comprar" }).catch(() => ({ ok: false, erro: "Sem resposta do app." }));
  if (!r.ok) perguntar(r.erro || "Não deu para montar.", "Ok");
}
async function barraca(acao, id) {
  if (acao === "desmontar" && !await perguntar("Desmontar esta barraca? O dinheiro não volta.", "Desmontar")) return;
  mapa.closePopup();
  const r = await post("/api/barraca", { acao, id }).catch(() => ({ ok: false, erro: "Sem resposta do app." }));
  if (!r.ok) perguntar(r.erro || "Não deu certo.", "Ok");
  else if (acao === "ir") marcarSeguindo(true);
}
function desenharBarracas(d) {
  barracasInfo = { preco: d.preco_barraca || 300, max: d.max_barracas || 10, n: (d.barracas || []).length };
  const cont = $("barraca-n");
  if (cont) cont.textContent = `${barracasInfo.n}/${barracasInfo.max}`;
  const t = JSON.stringify(d.barracas || []);
  if (t === barracasTexto) return;
  barracasTexto = t;
  grupoBarracas.clearLayers();
  for (const b of d.barracas || []) {
    L.marker(toLL(b), { icon: L.divIcon({ className: "", html: `<div class="mk-barraca ${b.pendente ? "pendente" : ""}">⛺</div>`, iconSize: [28, 28], iconAnchor: [14, 14] }), zIndexOffset: 800 })
      .bindTooltip(esc(b.nome) + (b.pendente ? " (pagando…)" : ""))
      .bindPopup(`<div class="pp-caixa" style="text-align:center"><b>${esc(b.nome)}</b><br>
        <button class="btn-papel verde" style="margin-top:6px;padding:10px 14px" onclick="barraca('ir','${esc(b.id)}')">🚶 Ir até a barraca</button><br>
        <button class="btn-papel" style="margin-top:6px" onclick="barraca('desmontar','${esc(b.id)}')">Desmontar</button></div>`)
      .addTo(grupoBarracas);
  }
}

async function tirarPino() {
  $("btn-tirar-pino").style.display = "none";
  if (marcPino) { mapa.removeLayer(marcPino); marcPino = null; }
  await post("/api/pino/remover"); atualizar();
}

// ---- passar o tempo (igual dormir na cama do acampamento)
function horaTexto(h) { if (h == null) return "–"; h = ((h % 24) + 24) % 24; const m = Math.floor((h % 1) * 60); return `${Math.floor(h)}h${String(m).padStart(2, "0")}`; }
function abrirTempo() {
  const h = ultimoEstado?.estado?.hora;
  const op = (rot, sub, corpo) => `<button class="tempo-op" onclick='passarTempo(${JSON.stringify(corpo)})'><b>${rot}</b><small>${sub}</small></button>`;
  moModal(`<header class="mo-jan-topo"><div><h3>Passar o tempo</h3><small>${h != null ? `Agora no jogo: ${horaTexto(h)}. ` : ""}O jogo mostra a tela do tempo passando, como quando você dorme no acampamento.</small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo"><div class="tempo-grade">
      ${op("+1 hora", "um cochilo", { horas: 1 })}${op("+2 horas", "", { horas: 2 })}${op("+4 horas", "", { horas: 4 })}${op("+8 horas", "uma noite de sono", { horas: 8 })}
      ${op("Amanhecer", "até 5h30, animais ativos", { ate: 5.5 })}${op("Meio-dia", "até 12h", { ate: 12 })}
      ${op("Fim de tarde", "até 17h, animais ativos", { ate: 17 })}${op("Noite", "até 21h", { ate: 21 })}
    </div></div>`);
}
async function passarTempo(corpo) {
  const r = await post("/api/tempo", corpo);
  moFecharModal();
  if (!r.ok) alert(r.erro || "Não consegui passar o tempo.");
}
// o mapa segue o jogador; arrastar solta, o botão "Eu" volta a seguir
let seguindo = true;
function marcarSeguindo(v) { seguindo = v; const b = $("btn-eu"); if (b) b.classList.toggle("ativo", v); }
function centralizar() {
  marcarSeguindo(true);
  if (ultimoEstado?.estado?.pos) mapa.setView(toLL(ultimoEstado.estado.pos), Math.max(mapa.getZoom(), -1));
}
mapa.on("dragstart", () => marcarSeguindo(false));

$("f-pois").onchange = (e) => e.target.checked ? grupoPois.addTo(mapa) : mapa.removeLayer(grupoPois);
$("f-zonas").onchange = (e) => e.target.checked ? grupoZonas.addTo(mapa) : mapa.removeLayer(grupoZonas);
$("f-estr").onchange = (e) => e.target.checked ? grupoEstr.addTo(mapa) : mapa.removeLayer(grupoEstr);
$("f-animais").onchange = (e) => e.target.checked ? grupoAnimais.addTo(mapa) : mapa.removeLayer(grupoAnimais);
$("f-nevoa").onchange = (e) => {
  try { localStorage.setItem("hs3_nevoa", e.target.checked ? "1" : "0"); } catch {}
  if (camadaNevoa) e.target.checked ? camadaNevoa.addTo(mapa) : mapa.removeLayer(camadaNevoa);
};
try { $("f-nevoa").checked = localStorage.getItem("hs3_nevoa") === "1"; } catch {}
// a névoa não é mais lida sozinha (pesava no jogo): só quando você clica
async function atualizarNevoa() {
  let r;
  try { r = await post("/api/nevoa", {}); } catch { return moAviso("O app não respondeu.", "erro"); }
  if (!r.ok) return moAviso(r.erro || "Entre numa reserva primeiro.", "erro");
  $("f-nevoa").checked = true;
  try { localStorage.setItem("hs3_nevoa", "1"); } catch {}
  moAviso("Lendo a névoa do jogo…", "ok");
}

function idadeTexto(dias) {
  if (!dias && dias !== 0) return "–";
  const anos = dias / 365;
  return anos >= 1 ? `${anos.toFixed(1).replace(".", ",")} anos (${fmt(dias)} dias)` : `${fmt(dias)} dias`;
}
function direcaoTexto(g) {
  if (g === null || g === undefined) return "–";
  const a = Math.abs(g), lr = g > 0 ? "direita" : "esquerda";
  return a < 15 ? "à frente" : a > 165 ? "atrás" : a > 110 ? `atrás, à ${lr}` : a < 60 ? `à frente, à ${lr}` : `à ${lr}`;
}

function fichaAnimal(a) {
  const pot = a.potencial ?? a.genetica;
  return `<div class="ficha">
    <div class="ficha-cab"><div class="ficha-sil">${silhueta(a.grupo, a.especie)}</div>
      <div><div class="ficha-grupo">${esc(a.grupo_nome)}${a.lendario ? " · 👑 Lendário" : ""}</div>
      <div class="ficha-nome">${esc(a.especie_nome || a.grupo_nome)}</div>
      <div>${esc(a.sexo_nome)} · ${idadeTexto(a.idade_dias)}</div></div></div>
    <div class="ficha-lin"><span>Genética</span><b>${pct(a.genetica)}</b></div>
    <div class="ficha-barra"><i style="width:${(a.genetica || 0) * 100}%"></i><em style="left:${(pot || 0) * 100}%"></em></div>
    <div class="ficha-lin"><span>Potencial genético</span><b>${pct(pot)}</b></div>
    ${a.peso_faixa ? `<div class="ficha-lin"><span>Peso estimado</span><b>${a.peso_faixa.map(x => String(x).replace(".", ",")).join("–")} kg</b></div>` : ""}
    <div class="ficha-lin"><span>Distância</span><b>${metros(a.distancia_m)}</b></div>
    <div class="ficha-lin"><span>Direção</span><b>${direcaoTexto(a.direcao)}</b></div>
    <div class="ficha-lin"><span>Posição</span><b>${a.ao_vivo ? "🟢 ao vivo" : "⚪ última conhecida"}</b></div>
    <div class="ficha-lin"><span>Marcado há</span><b>${a.minutos} min</b></div>
    <div class="ficha-rod">Nº ${esc(a.id)}</div>
  </div>`;
}

function atualizarAnimais(lista) {
  const vistos = new Set();
  for (const a of lista) {
    if (!a.pos) continue;
    vistos.add(String(a.id));
    const cls = `mk-animal${a.lendario ? " lendario" : ""}${a.ao_vivo ? "" : " velho"}`;
    const icone = L.divIcon({ className: "", html: `<div class="${cls}">${silhueta(a.grupo, a.especie)}</div>`, iconSize: [34, 34], iconAnchor: [17, 17] });
    let m = marcAnimais[a.id];
    if (!m) {
      m = L.marker(toLL(a.pos), { icon: icone, riseOnHover: true });
      m.bindTooltip("", { className: "cartao-animal", direction: "right", offset: [16, 0], opacity: 1 });
      m.on("click", () => { centrarAnimal(m.getLatLng()); m.openTooltip(); });
      grupoAnimais.addLayer(m);
      marcAnimais[a.id] = m;
    } else {
      m.setLatLng(toLL(a.pos));
      if (m._cls !== cls) m.setIcon(icone);
    }
    m._cls = cls;
    m._rotulo = a.especie_nome || a.grupo_nome;
    m.setTooltipContent(fichaAnimal(a));
  }
  for (const id of Object.keys(marcAnimais)) {
    if (!vistos.has(id)) { grupoAnimais.removeLayer(marcAnimais[id]); delete marcAnimais[id]; }
  }
}

function atualizarMarcadores(d) {
  const st = d.estado || {};
  if (st.pos) {
    if (!marcJogador) marcJogador = L.marker(toLL(st.pos), { icon: setaJogador(st.yaw), zIndexOffset: 1000 }).addTo(mapa).bindTooltip("Você");
    else { marcJogador.setLatLng(toLL(st.pos)); marcJogador.setIcon(setaJogador(st.yaw)); }
    if (seguindo && jaCentralizou) mapa.panTo(toLL(st.pos), { animate: true, duration: 0.5 });
    if (!jaCentralizou && nivelAtual) { mapa.setView(toLL(st.pos), -1); jaCentralizou = true; }
  }
  const pino = st.pino_jogo || d.pino_app;
  $("btn-tirar-pino").style.display = pino ? "" : "none";
  $("btn-tempo").style.display = d.em_reserva && d.reserva ? "" : "none";
  if (st.hora != null) $("btn-tempo-hora").textContent = horaTexto(st.hora);
  if (pino) {
    const rot = (d.pino_app && Math.abs(d.pino_app.x - pino.x) < 200 && Math.abs(d.pino_app.y - pino.y) < 200) ? d.pino_app.rotulo : "Ponto de rota rápido";
    if (!marcPino) marcPino = L.marker(toLL(pino), { icon: L.divIcon({ className: "", html: '<div class="mk-pino">📍</div>', iconSize: [30, 30], iconAnchor: [15, 30] }), zIndexOffset: 900 }).addTo(mapa);
    marcPino.setLatLng(toLL(pino)).bindTooltip(`${esc(rot)} · ${metros(distancia(st.pos, pino))}`);
  } else if (marcPino) { mapa.removeLayer(marcPino); marcPino = null; }
  desenharBarracas(d);
  grupoMissoes.clearLayers();
  for (const m of d.ativas) if (m.local && m.local.raio_m) {
    // área de busca (carcaça): círculo no tamanho real
    const c = toLL(m.local), borda = toLL({ x: m.local.x + m.local.raio_m * 100, y: m.local.y });
    L.circle(c, { radius: Math.abs(borda[1] - c[1]), color: "#d39a32", weight: 2, dashArray: "6 5", fillOpacity: 0.12 })
      .bindTooltip(`<b>${esc(m.titulo)}</b><br>${esc(m.local.nome)}`).addTo(grupoMissoes);
  }
  for (const m of d.ativas) if (m.local) {
    L.marker(toLL(m.local), { icon: L.divIcon({ className: "", html: '<div class="mk-missao">🚩</div>', iconSize: [24, 24], iconAnchor: [4, 24] }) })
      .bindTooltip(`<b>${esc(m.titulo)}</b><br>${esc(m.local.nome)}`).addTo(grupoMissoes);
  }
  atualizarAnimais(d.rastreados || []);
}

function distancia(a, b) { if (!a || !b) return null; return Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0)) / 100; }

// ------------------------------------------------------------------ contratos
function recompensa(m) { return `$${fmt(m.creditos_pagos ?? m.creditos)} <small>+${fmt(m.reputacao)} rep.${m.agente_nome ? ` · ${esc(m.agente_nome)}` : ""}</small>`; }

function renderOfertas(d) {
  const of = d.ofertas;
  let html = of.map(m => `<div class="oferta">
      <div class="of-titulo">${esc(m.titulo)}</div>
      <div class="of-fala">“${esc(m.fala)}”</div>
      <div class="of-meta">${esc(m.descricao)}${m.local ? ` · 🚩 ${esc(m.local.nome)}` : ""}</div>
      <div class="of-rodape"><span class="recomp">${recompensa(m)}</span>
        <span><button class="btn-papel cinza" onclick="acao('recusar','${m.id}')">Outro</button>
        <button class="btn-papel verde" onclick="acao('aceitar','${m.id}')">Aceitar</button></span></div>
    </div>`).join("");
  if (of.length) html = `<div class="of-topo"><span>${of.length} contratos ${d.reserva ? "de " + esc(d.reserva) : "na mesa"}</span><button class="btn-papel cinza" onclick="renovarOfertas()">Trocar todos</button></div>` + html;
  if (!of.length) html = `<div class="vazio">${d.gerando ? "O Velho Earl está pensando em novos contratos…" : (d.em_reserva ? "Sem contratos no momento." : "Entre numa reserva para receber contratos.")}</div>`;
  else if (d.gerando) html += `<div class="sub">Preparando mais contratos…</div>`;
  $("ofertas").innerHTML = html + outrasReservas(d);
}

// cada reserva guarda os próprios contratos; aqui só um resumo das outras
function outrasReservas(d) {
  const o = d.outras_reservas || [];
  if (!o.length) return "";
  return `<div class="outras-res">Guardados em outras reservas: ${o.map(c => `<b>${esc(c.reserva)}</b> ${c.ativas} ativo${c.ativas === 1 ? "" : "s"}, ${c.ofertas} na mesa`).join(" · ")}</div>`;
}

function renderAtivas(d) {
  const lista = d.ativas.map(m => `<div class="ativa">
      <div class="at-titulo"><span>${esc(m.titulo)}</span><span class="recomp">${recompensa(m)}</span></div>
      <div class="of-meta">${esc(m.descricao)}</div>
      <div class="barra"><div style="width:${Math.min(100, 100 * m.progresso / m.meta)}%"></div></div>
      <div class="at-acoes"><span class="sub" style="margin-right:auto">${m.progresso}/${m.meta}</span>
        ${m.local ? `<button class="btn-papel" onclick="acao('focar','${m.id}')">📍 Pino</button>` : ""}
        <button class="btn-papel cinza" onclick="abandonar('${m.id}')" title="Abortar tem penalidade de reputação e multa">Abortar</button></div>
    </div>`);
  const fim = d.finalizadas.slice(0, 3).map(m => `<div class="ativa concl"><div class="at-titulo"><span>${esc(m.titulo)}</span>
      <span class="estado-pg ${m.status === "paga" ? "ok" : ""}">${m.status === "paga" ? "Pago" : (m.enviado ? "Pagando…" : "Concluído")}</span></div></div>`);
  const jogo = (d.contratos_jogo || []).map(c => `<div class="ativa do-jogo">
      <div class="at-titulo"><span><span class="selo-jogo">JOGO</span> ${esc(c.titulo)}</span>${c.rastreado ? `<span class="selo-rastreio">Rastreando</span>` : ""}</div>
      <div class="of-meta">${esc(c.vendedor)}${c.tempo_min != null ? ` · ⏱ ${c.tempo_min} min restantes` : ""}</div>
      ${c.objetivos.map(o => `<div class="obj-jogo ${o.feito ? "feito" : ""}"><span>${o.feito ? "✔" : "▸"} ${esc(o.texto)}</span><b>${o.progresso} / ${o.meta}</b></div>
        <div class="barra"><div style="width:${Math.min(100, 100 * o.progresso / o.meta)}%"></div></div>`).join("")}
    </div>`);
  const partes = lista.concat(fim);
  if (jogo.length) partes.push(`<div class="sep-jogo">Contratos do jogo</div>`, ...jogo);
  $("ativas").innerHTML = (partes.join("") || `<div class="vazio">${d.reserva ? "Aceite um contrato do Velho Earl." : "Entre numa reserva: cada reserva tem os próprios contratos."}</div>`) + outrasReservas(d);
}

async function renovarOfertas() {
  const ids = (ultimoEstado?.ofertas || []).map(m => m.id);
  for (const id of ids) await post("/api/missoes/recusar", { id });
  await post("/api/missoes/gerar");
  moAviso("O Earl está preparando contratos novos.", "ok");
  atualizar();
}
async function acao(tipo, id) {
  const r = await post("/api/missoes/" + tipo, { id });
  if (!r.ok && r.erro) return moAviso(r.erro, "erro");
  if (tipo === "aceitar") { moAviso("Contrato aceito. Ele está em Em andamento.", "ok"); document.querySelector('.segmentos [data-seg="ativas"]').click(); }
  atualizar();
}

// ------------------------------------------------------------------ chat
let chatQtd = -1;
function renderChat(d) {
  const msgs = d.chat || [];
  if (msgs.length === chatQtd) return;
  chatQtd = msgs.length;
  const log = $("chat-log");
  log.innerHTML = (msgs.length ? "" : `<div class="msg assistant">Pergunte sobre vento, calibre, chamador, distância, roupa ou uma espécie (veado, javali, pato, peru…) que eu te dou a dica, rapaz.</div>`)
    + msgs.map(m => `<div class="msg ${m.role === "user" ? "user" : "assistant"}">${esc(m.content)}</div>`).join("");
  log.scrollTop = log.scrollHeight;
}
$("chat-form").onsubmit = async (e) => {
  e.preventDefault();
  const t = $("chat-txt").value.trim();
  if (!t) return;
  $("chat-txt").value = "";
  post("/api/chat", { texto: t }).then(atualizar);
};

// ------------------------------------------------------------------ atualização do programa
let ultimaAtualizacao = null, atualizando = false, versaoAntes = null;
function mostrarAtualizacao(a, versao) {
  ultimaAtualizacao = a;
  $("versao").textContent = "v" + versao;
  const b = $("btn-atualizar");
  if (!a) return;
  b.classList.toggle("nova", !!a.disponivel);
  b.disabled = ["baixando", "reiniciando", "verificando"].includes(a.estado);
  b.title = a.erro || "";
  b.textContent = a.estado === "baixando" ? "Baixando…" : a.estado === "reiniciando" ? "Reiniciando…"
    : a.estado === "verificando" ? "Verificando…" : a.disponivel ? `Atualizar para v${a.nova}` : "Procurar atualização";
}
async function clicarAtualizar() {
  const a = ultimaAtualizacao;
  if (a && a.disponivel) {
    if (!await perguntar(`Atualizar para a versão ${a.nova}?\n\nO programa reinicia sozinho em alguns segundos. A parte do mod vale na próxima vez que você abrir o jogo.`)) return;
    atualizando = true; versaoAntes = ultimoEstado && ultimoEstado.versao;
    await post("/api/atualizar");
  } else {
    $("btn-atualizar").textContent = "Verificando…";
    const r = await post("/api/verificar");
    mostrarAtualizacao(r, r.atual);
    if (r.erro) moAviso(r.erro, "erro");
    else if (!r.disponivel) moAviso(`Você já está na versão mais recente (v${r.atual}).`, "ok");
  }
}
async function abandonar(id) {
  const m = (ultimoEstado?.ativas || []).find(x => x.id === id) || {};
  const perda = Math.max(3, Math.floor((m.reputacao || 0) / 2)), multa = Math.max(20, Math.round((m.creditos || 0) * 0.1));
  if (await perguntar(`Abortar "${m.titulo || "este contrato"}"?\n\nPenalidades:\n• −${perda} de reputação com ${m.agente_nome || "o agente"}\n• multa de $${fmt(multa)}\n• o Earl não oferece contratos de ${m.agente_nome || "desse agente"} até o próximo dia do jogo`, "Abortar contrato")) acao("abandonar", id);
}
// confirmação dentro do app (o confirm() do navegador não aparece no app do celular)
function perguntar(texto, sim = "Confirmar") {
  return new Promise((fim) => {
    const fundo = document.createElement("div");
    fundo.className = "pergunta-fundo";
    fundo.innerHTML = `<div class="pergunta" role="dialog" aria-modal="true"><p></p>
      <div class="pergunta-botoes"><button class="btn-papel cinza" data-r="0">Cancelar</button><button class="btn-papel verde" data-r="1"></button></div></div>`;
    fundo.querySelector("p").textContent = texto;
    fundo.querySelector('[data-r="1"]').textContent = sim;
    const fechar = (r) => { fundo.remove(); document.removeEventListener("keydown", tecla); fim(r); };
    const tecla = (e) => { if (e.key === "Escape") fechar(false); if (e.key === "Enter") fechar(true); };
    fundo.addEventListener("click", (e) => { if (e.target === fundo) fechar(false); const r = e.target.dataset && e.target.dataset.r; if (r) fechar(r === "1"); });
    document.addEventListener("keydown", tecla);
    document.body.appendChild(fundo);
    fundo.querySelector('[data-r="1"]').focus();
  });
}
async function sair() {
  if (!await perguntar("Fechar o HS3 Companion?")) return;
  try { await post("/api/sair"); } catch {}
  document.body.innerHTML = '<div style="padding:60px;text-align:center;font-family:Georgia;font-size:22px;color:#e9dcbc">HS3 Companion fechado. Pode fechar esta janela.</div>';
  setTimeout(() => window.close(), 800);
}

// ------------------------------------------------------------------ painel
function nomeMapa(m) {
  const t = (m || "").toLowerCase();
  return t.includes("texas") ? "Texas" : t.includes("colorado") ? "Colorado" : (t.includes("hub") ? "Cabana" : (m || "–"));
}

async function atualizar() {
  let d;
  try { d = await (await fetch("/api/estado")).json(); }
  catch {
    $("led").className = "led";
    $("conexao-txt").textContent = atualizando ? "Atualizando, aguarde…" : "HS3Companion.exe fechado";
    return;
  }
  if (atualizando && versaoAntes && d.versao !== versaoAntes) { location.reload(); return; }
  ultimoEstado = d;
  mostrarAtualizacao(d.atualizacao, d.versao);
  if (typeof avisoJogoNovo === "function") avisoJogoNovo(d.jogo_novo);
  const st = d.estado || {};
  $("led").className = "led " + (d.em_reserva ? "on" : d.conectado ? "meio" : "");
  $("conexao-txt").textContent = d.em_reserva ? "Conectado ao jogo" : d.conectado ? "Jogo aberto, fora da reserva" : "Jogo fechado";
  $("nome-reserva").textContent = d.em_reserva ? nomeMapa(st.mapa) : d.conectado ? "No acampamento" : "Aguardando o jogo";

  // placas
  const moedas = st.moedas || {};
  $("p-saldo").textContent = moedas["Currency.Credits"] !== undefined ? "$" + fmt(moedas["Currency.Credits"]) : "–";
  const pt = d.patente;
  $("p-patente").textContent = pt.patente;
  $("p-patente-barra").style.width = (pt.progresso * 100) + "%";
  $("p-patente-sub").textContent = pt.proxima ? `faltam ${fmt(pt.faltam)} pts para ${pt.proxima}` : `${fmt(pt.pontos)} pts`;
  $("f-voltar").checked = !!d.config?.voltar_ao_ultimo_local;
  $("f-hud").checked = d.config?.contratos_no_jogo !== false;
  $("btn-voltar").style.display = d.tem_local_salvo ? "" : "none";
  $("aviso-teleporte").textContent = d.aviso_teleporte || "";
  const ag = d.agentes || [];
  agentesDados = ag;
  const total = ag.reduce((t, a) => t + a.valor, 0);
  $("p-rep").textContent = ag.length ? `${fmt(total)}` : "–";
  $("p-rep").title = ag.map(a => `${a.nome}: nível ${a.nivel} (${a.valor})`).join("\n");
  const nAndamento = d.ativas.length + (d.contratos_jogo || []).length;
  $("p-contratos").textContent = nAndamento || "";
  $("n-ofertas").textContent = d.ofertas.length || "";
  const campo = Object.entries(st.pontos_campo || {}).find(([k]) => st.mapa && k.toLowerCase().includes(nomeMapa(st.mapa).toLowerCase()));
  $("p-campo").textContent = campo ? fmt(campo[1]) : "–";

  // mapa
  atualizarMapaBase(d.mapa);
  let aviso = "";
  if (!d.pasta_mod_existe) aviso = `Pasta do mod não encontrada:<br><small>${esc(d.pasta_mod)}</small>`;
  else if (!d.conectado) aviso = "Abra o jogo para carregar o mapa.";
  else if (!d.mapa?.imagem) aviso = d.em_reserva ? "Preparando o mapa da reserva…" : "Entre numa reserva para ver o mapa.";
  $("mapa-aviso").innerHTML = aviso;
  atualizarMarcadores(d);

  // NPC
  const npc = d.npc;
  $("npc-nome").textContent = npc.nome;
  $("npc-funcao").textContent = npc.funcao;
  $("npc-frase").textContent = "“" + npc.frase + "”";
  renderOfertas(d); renderAtivas(d); renderChat(d);

  // telemetria
  const prox = (d.rastreados || []).find(a => a.distancia_m !== null);
  const pino = st.pino_jogo && st.pino_jogo.x ? st.pino_jogo : d.pino_app;
  const hud = [
    ["Posição", st.pos ? `${Math.round(st.pos.x / 100)} · ${Math.round(st.pos.y / 100)}` : "–", st.pos ? `altitude ${Math.round(st.pos.z / 100)} m` : ""],
    ["Animais rastreados", fmt((d.rastreados || []).length), prox ? `mais perto: ${esc(prox.especie_nome || prox.grupo_nome)}, ${metros(prox.distancia_m)}` : "marque com o binóculo"],
    ["Pino", pino && pino.x ? metros(distancia(st.pos, pino)) : "–", pino && pino.x ? "até o pino" : "nenhum pino"],
  ];
  $("telemetria").innerHTML = d.em_reserva ? hud.map(([k, v, s]) => `<div class="hud-item"><span>${k}</span><b>${v}</b><small>${s}</small></div>`).join("") : "";
  const s = d.estatisticas;
  $("diario").innerHTML = [
    ["Abates", fmt(s.total_abates)], ["Distância média", metros(s.distancia_media)], ["Tiro mais longo", metros(s.distancia_maxima)],
    ["Melhor genética", s.melhor_genetica ? `${pct(s.melhor_genetica.genetica)} · ${esc(s.melhor_genetica.especie)}` : "–"],
    ["Contratos concluídos", fmt(s.missoes_concluidas)], ["Créditos de contratos", fmt(s.creditos_ganhos)],
  ].map(([k, v]) => `<span>${k}</span><b>${v}</b>`).join("");
  const barras = (lista, id) => {
    const max = Math.max(1, ...lista.map(x => x[1]));
    $(id).innerHTML = lista.slice(0, 8).map(([n, v]) => `<div class="barra-lin"><span>${esc(n)}</span><i style="--p:${100 * v / max}%"></i><b>${v}</b></div>`).join("")
      || `<p class="vazio">Nenhum abate ainda.</p>`;
  };
  barras(s.por_grupo || [], "cac-especies");
  barras((s.por_arma || []).map(([n, v]) => [n.replace(/^ID_/, "").replace(/_/g, " "), v]), "cac-armas");
  $("ultimos").innerHTML = d.abates.length ? `<table class="tabela"><thead><tr><th>Animal</th><th>Peso</th><th>Troféu</th><th>Genética</th><th>Distância</th><th>Morte</th><th>Arma</th><th>Reserva</th></tr></thead><tbody>` +
    d.abates.slice(0, 15).map(a => `<tr><td><b>${esc(a.especie_nome || a.grupo_nome)}</b>${a.sexo_nome && a.sexo_nome !== "?" ? ` <small>${esc(a.sexo_nome)}</small>` : ""}</td>
      <td>${a.peso_kg ? `${a.peso_kg.toFixed(1).replace(".", ",")} kg` : "–"}</td>
      <td>${a.pontos_trofeu ? `${a.pontos_trofeu.toFixed(1).replace(".", ",")}${a.lendario ? " ★" : ""}` : "–"}</td>
      <td>${pct(a.genetica)}</td><td>${metros(a.distancia_m)}</td>
      <td title="Tempo entre o tiro e a morte">${a.segundos_ate_morte != null ? `${a.segundos_ate_morte < 10 ? a.segundos_ate_morte.toFixed(1).replace(".", ",") : Math.round(a.segundos_ate_morte)} s` : "–"}</td><td>${esc((a.arma || "").replace(/^ID_/, "").replace(/_/g, " "))}</td><td>${esc(a.reserva ? nomeMapa(a.reserva) : "–")}</td></tr>`).join("") + `</tbody></table>`
    : `<p class="vazio">Nenhum abate ainda. Cada animal recolhido no jogo aparece aqui.</p>`;
}

atualizar();
setInterval(atualizar, 2000);
setInterval(() => { if (nivelAtual) carregarPois(); }, 15000);
setInterval(() => { if (nivelAtual) carregarZonas(); }, 20000);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");


// ------------------------------------------------------------------ abas: armário, loja, enciclopédia
let abaAtual = "mapa", filtroLoja = "Todas";
document.body.dataset.aba = "mapa";
document.querySelectorAll(".segmentos button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".segmentos button").forEach(x => x.classList.toggle("ativo", x === b));
  document.querySelectorAll(".seg").forEach(s => s.classList.toggle("ativo", s.id === "seg-" + b.dataset.seg));
  if (b.dataset.seg === "chat") { const l = $("chat-log"); l.scrollTop = l.scrollHeight; }
});
document.querySelectorAll("#abas button[data-aba]").forEach(b => b.onclick = () => {
  abaAtual = b.dataset.aba;
  document.body.dataset.aba = abaAtual;
  document.querySelectorAll("#abas button[data-aba]").forEach(x => x.classList.toggle("ativo", x === b));
  ["armario", "loja", "enciclopedia", "cacadas"].forEach(a => $("painel-" + a).classList.toggle("ativo", a === abaAtual));
  document.querySelector(".mapa-papel").classList.toggle("so-mapa", abaAtual === "mapa");
  if (abaAtual === "mapa") setTimeout(() => mapa.invalidateSize(), 50);
  atualizarAba();
});
$("f-voltar").onchange = (e) => post("/api/config", { chave: "voltar_ao_ultimo_local", valor: e.target.checked });
$("f-hud").onchange = (e) => post("/api/config", { chave: "contratos_no_jogo", valor: e.target.checked });
async function voltarAgora() { const r = await post("/api/voltar"); if (!r.ok) moAviso(r.erro, "erro"); }

function barraStat(nome, v) {
  // degradê fixo do vermelho (exposto) ao verde (camuflado); a parte que falta fica coberta
  return `<div class="st"><span>${nome}</span><span class="b"><i style="left:${Math.max(0, Math.min(100, v))}%"></i></span><b>${Math.round(v)}</b></div>`;
}

// ---------------------------------------------------------------- Mochila
let mochilaMissoes = null;  // ids escolhidos (null = todas as ativas)
let mochilaEspecies = [];    // espécies escolhidas para caçar (tags), guardadas neste aparelho
try { mochilaEspecies = JSON.parse(localStorage.getItem("hs3_mo_esp") || "[]"); } catch {}
let mochilaDados = null;
const MO_TIPOS = [
  { tipo: "Inventory.Weapon", nome: "Armas", classe: "armas" },
  { tipo: "Inventory.Objects", nome: "Equipamentos", classe: "objetos" },
  { tipo: "Inventory.GPS", nome: "GPS", classe: "gps" },
];
let moAssinatura = "", moOcupadoAte = 0;
const moTxtIdade = (s) => s == null ? "" : s < 60 ? `há ${s} s` : `há ${Math.round(s / 60)} min`;
// ícones pequenos e já recortados pelo programa (?p=1): leve no celular, sem recorte no navegador
const moFoto = (i, cls) => `<div class="mo-foto ${cls || ""}">${i && i.imagem ? `<img src="${i.imagem}?p=1" alt="" loading="lazy" decoding="async" onload="this.parentElement.classList.add('tem')" onerror="this.remove()">` : ""}
  <span class="mo-foto-ini">${esc(((i && i.nome) || "?").trim()[0] || "?")}</span></div>`;
const moSelo = (i) => i.serve ? `<span class="mo-selo sim">✔ serve</span>` : i.serve === false ? `<span class="mo-selo nao">não serve</span>` : "";

function lidaJa(d) { return d.lida_ts && d.mochila.length; }
async function moRecarregar() {
  const b = document.querySelector(".mo-recarregar");
  if (b) { b.disabled = true; b.textContent = "Recarregando…"; }
  let r;
  try { r = await (await fetch("/api/municao", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })).json(); } catch { r = { ok: false, erro: "Sem resposta do app." }; }
  if (b) b.textContent = r.ok ? "✔ Pedido enviado ao jogo" : (r.erro || "Não deu");
  setTimeout(() => renderArmario(true), 2500);
}
let agentesDados = [];
function abrirAgentes() {
  const linhas = agentesDados.map(a => `<div class="ag-lin"><div class="ag-cab"><b>${esc(a.nome)}</b><span>Nível ${a.nivel}${a.nivel >= 5 ? " (máximo)" : ""}</span></div>
    <div class="ag-barra"><i style="width:${Math.round(a.progresso * 100)}%"></i></div>
    <small>${fmt(a.valor)} pontos${a.proximo ? ` · faltam ${fmt(a.proximo - a.valor)} para o nível ${a.nivel + 1}` : ""}</small></div>`).join("");
  moModal(`<header class="mo-jan-topo"><div><h3>Reputação nesta reserva</h3><small>Os quatro agentes de campo do jogo</small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo ag-lista">${linhas || "<p>Entre numa reserva para ver a reputação dos agentes.</p>"}
    <p class="mo-dica">Cada nível pede 200 pontos (até 1000). Os contratos do Earl dizem antes de aceitar qual agente recebe os pontos.</p></div>`);
}
const moMunSel = {};   // munição escolhida no carrossel (ainda não mandada para o jogo), por arma
function moMunPassar(arma, n, passo, k) { moMunSel[arma] = (k + passo + n) % n; renderArmario(true); }
async function renderArmario(forcar) {
  const p = $("painel-armario");
  if (!forcar && (document.querySelector(".mo-modal") || p.contains(document.activeElement) && ["SELECT", "INPUT"].includes(document.activeElement.tagName))) return;
  const params = [];
  if (mochilaMissoes) params.push("missoes=" + encodeURIComponent(mochilaMissoes.join(",")));
  if (mochilaEspecies.length) params.push("especies=" + encodeURIComponent(mochilaEspecies.join(",")));
  const q = params.length ? "?" + params.join("&") : "";
  let d;
  try { d = await (await fetch("/api/mochila" + q)).json(); } catch { return; }
  const assin = JSON.stringify(d);
  if (!forcar && assin === moAssinatura && p.innerHTML) return;
  moAssinatura = assin;
  mochilaDados = d;
  // espécies escolhidas ficam guardadas no app do PC: valem no PC e no celular
  if (!moEspSincronizado && Array.isArray(d.especies_salvas)) {
    moEspSincronizado = true;
    if (JSON.stringify(d.especies_salvas) !== JSON.stringify(mochilaEspecies)) {
      mochilaEspecies = d.especies_salvas;
      try { localStorage.setItem("hs3_mo_esp", JSON.stringify(mochilaEspecies)); } catch {}
      return renderArmario(true);
    }
  }
  if (!d.pronto) {
    p.innerHTML = `<div class="mo-vazio-grande"><b>Falta ler os dados do jogo</b><span>Abra a aba <b>Diário de campo</b> e clique em “Ler dados do jogo” com o jogo aberto numa reserva.</span></div>`;
    return;
  }
  const ocupado = Date.now() < moOcupadoAte || d.fila;
  const lida = d.lida_ts && d.mochila.length;
  const status = !d.em_reserva ? `<span class="mo-status off">● Jogo fora da reserva — entre numa reserva para mexer na mochila</span>`
    : ocupado ? `<span class="mo-status ocupado">● Arrumando a mochila no jogo…</span>`
    : lida ? `<span class="mo-status on">● Mochila do jogo · atualizada ${moTxtIdade(d.lida_idade)}</span>`
    : `<span class="mo-status ocupado">● Lendo a mochila do jogo…</span>`;
  const plano = d.plano || [];
  const pode = d.em_reserva && lida && !ocupado;
  const botaoMontar = !lida ? "" : plano.length
    ? `<button class="mo-principal" ${pode ? "" : "disabled"} onclick="moConfirmarMontar()"><span class="mo-principal-ico">★</span>
         <span><b>Montar mochila sugerida</b><small>${plano.length} troca${plano.length > 1 ? "s" : ""} para os contratos escolhidos</small></span></button>`
    : `<div class="mo-pronta">✔ A mochila já está pronta para os contratos escolhidos</div>`;

  const contratos = d.ativas.length ? d.ativas.map(m => `<button class="mo-contrato ${m.escolhida ? "on" : ""}" onclick="moMissao('${esc(m.id)}')">
      <span class="mo-check">${m.escolhida ? "✔" : ""}</span><span class="mo-origem ${m.do_jogo ? "jogo" : "earl"}">${m.do_jogo ? "JOGO" : "EARL"}</span>${esc(m.titulo)}</button>`).join("")
    : `<span class="mo-dica">Nenhum contrato ativo.</span>`;
  const escolhidas = (d.especies || []).filter(e => e.escolhida);
  // o que o setup da mochila (arma + munição carregada) cobre; o que fica de fora aparece apagado
  const cobertura = {};
  (d.alvos || []).forEach(a => { if (!a.sem_dados) [a.chave, ...(a.tags || [])].forEach(t => cobertura[t] = a.coberta); });
  const alvosValidos = (d.alvos || []).filter(a => !a.sem_dados);
  const nCobertos = alvosValidos.filter(a => a.coberta).length;
  const coberturaHtml = alvosValidos.length && lidaJa(d) ? `<div class="mo-cobertura"><span>Seu setup cobre ${nCobertos} de ${alvosValidos.length}:</span>
      ${alvosValidos.map(a => `<b class="${a.coberta ? "ok" : "fora"}" title="${a.coberta ? "Coberto por " + esc(a.por.join(" e ")) : "Nenhuma arma da mochila, com a munição carregada, serve para este animal"}">${a.coberta ? "✔" : "○"} ${esc(a.nome)}</b>`).join("")}</div>` : "";
  const especiesHtml = `<div class="mo-esp">
      <div class="mo-esp-linha"><input class="mo-esp-busca" placeholder="Procurar espécie (ex.: veado, pato, javali)…" oninput="moEspFiltrar(this.value)" autocomplete="off">
        <button class="kit-btn sec" onclick="moEspVarias()">Escolher várias</button></div>
      <div id="mo-esp-res" class="mo-esp-res"></div>
      ${escolhidas.length ? `<div class="mo-esp-chips">${escolhidas.map(e => `<button class="mo-esp-chip ${cobertura[e.tag] === false ? "fora" : ""}" onclick="moEspAlternar('${esc(e.tag)}')" title="${cobertura[e.tag] === false ? "Nenhuma arma da mochila com a munição carregada serve para esta espécie. Toque para tirar da lista." : "Tirar da lista"}">${esc(e.nome)}${e.reservas.length ? ` <small>${esc(e.reservas.join(", "))}</small>` : ""} <b>×</b></button>`).join("")}
        <button class="mo-esp-limpar" onclick="mochilaEspecies=[];moEspSalvar()">Limpar</button></div>`
        : `<span class="mo-dica">Nenhuma espécie escolhida. Sem espécie e sem contrato, a sugestão vale para qualquer animal.</span>`}
    </div>`;

  // espaços da mochila
  const porTipo = (t) => d.mochila.filter(m => m.tipo === t);
  const mudancas = {};
  plano.filter(x => x.acao === "por").forEach(x => mudancas[x.tipo + ":" + x.idx] = x);
  const secao = (T) => {
    const itens = porTipo(T.tipo), n = Math.max(d.slots[T.tipo] || 0, itens.length);
    const cel = [];
    for (let k = 0; k < n; k++) {
      const num = moNumero(T.tipo, k);
      const selo = num ? `<b class="kit-num mo-num">${num}</b>` : "";
      const it = itens.find(x => x.idx === k);
      const mud = mudancas[T.tipo + ":" + k];
      const sug = mud ? `<div class="mo-sugere">Sugestão: <b>${esc(mud.nome)}</b></div>` : "";
      if (!it) {
        cel.push(`<div class="mo-slot vazio ${pode ? "clic" : ""}" ${pode ? `onclick="moEscolher('${T.tipo}',${k})"` : ""}>${selo}
          <div class="mo-mais">+</div><div class="mo-slot-nome">Espaço livre</div>${pode ? `<small>Clique para escolher</small>` : ""}${sug}</div>`);
        continue;
      }
      let mun = "";
      if (it.municoes) {
        const ruim = it.municoes.some(m => m.atual && !m.serve) || !it.municoes.some(m => m.atual);
        const carregada = it.municoes.find(m => m.atual);
        // carrossel: ◀ munição ▶ só escolhe aqui; "Mandar para o jogo" troca de verdade
        const ms = it.municoes, kAtual = ms.findIndex(m => m.atual);
        let k = moMunSel[it.id] ?? kAtual;
        if (k < 0 || k >= ms.length) k = Math.max(0, kAtual);
        const m = ms[k], mudou = k !== kAtual;
        const esp = (m.especies || []);
        mun = ms.length ? `<div class="mo-municao mo-carrossel ${!m.serve ? "ruim" : ""}" onclick="event.stopPropagation()">
            <button class="mo-seta" ${ms.length > 1 ? "" : "disabled"} onclick="moMunPassar('${esc(it.id)}', ${ms.length}, -1, ${k})">◀</button>
            <div class="mo-mun-nome"><b>${m.serve ? "✔" : "✖"} ${esc(m.nome)}</b> <small class="mo-mun-n">${k + 1}/${ms.length}${m.atual ? " · carregada" : ""}</small>
              <small class="mo-mun-esp">${esp.length ? "Serve para: " + esc(esp.join(", ")) : "Não serve para nenhum animal desta lista"}</small></div>
            <button class="mo-seta" ${ms.length > 1 ? "" : "disabled"} onclick="moMunPassar('${esc(it.id)}', ${ms.length}, 1, ${k})">▶</button></div>
            ${mudou ? `<button class="btn-papel verde mo-mun-ok" ${pode ? "" : "disabled"} onclick="event.stopPropagation();delete moMunSel['${esc(it.id)}'];moAcao({acao:'municao',arma:'${esc(it.id)}',municao:'${esc(m.id)}'})">Mandar ${esc(m.nome)} para o jogo</button>` : ""}`
          : `<div class="mo-aviso">Você não tem munição para esta arma</div>`;
      }
      const aces = (it.acessorios || []).length ? `<div class="mo-aces">${it.acessorios.map(e =>
          `<span class="${e.atual ? "tem" : ""}"><em>${esc(e.nome)}</em>${e.atual ? esc(e.atual_nome || "montado") : "nada"}</span>`).join("")}</div>` : "";
      cel.push(`<div class="mo-slot ${it.serve ? "serve" : it.serve === false ? "nao" : ""}">${selo}
          ${moFoto(it, T.classe === "armas" ? "larga" : "")}
          <div class="mo-slot-info"><div class="mo-slot-nome">${esc(it.nome)}</div>${moSelo(it)}
            ${it.motivo ? `<small class="mo-motivo">${esc(it.motivo)}</small>` : ""}${mun}${aces}${sug}</div>
          ${pode ? `<div class="mo-slot-botoes">${(it.acessorios || []).length ? `<button class="aces" onclick="moAcessorios('${esc(it.item)}')">Acessórios</button>` : ""}<button onclick="moEscolher('${T.tipo}',${k})">Trocar</button>
            <button class="sec" onclick="moAcao({acao:'tirar',item:'${esc(it.item)}'})">Tirar</button></div>` : ""}
        </div>`);
    }
    return `<section class="mo-sec ${T.classe}"><header><h4>${T.nome}</h4><span>${itens.length}/${n}</span></header><div class="mo-grade">${cel.join("")}</div></section>`;
  };

  p.innerHTML = `<div class="mochila">
    <div class="mo-topo">
      <div><h2>Mochila ${ajuda("mochila")}</h2>${status}${d.em_reserva ? ` <button class="btn-papel mo-recarregar" onclick="moRecarregar()" title="Enche a reserva de munição das armas da mochila até o máximo do jogo">↻ Recarregar munição</button>` : ""}</div>
      <div class="mo-montar">${botaoMontar}${plano.length ? ajuda("mochila_montar") : ""}</div>
      <div class="mo-setups">
        <button class="btn-papel" ${pode && d.tem_anterior ? "" : "disabled"} onclick="moAcao({acao:'setup_voltar'})" title="Desfaz a última troca feita pelo app">↶ Setup anterior</button>
        ${(d.setups || []).map((n, i) => `<span class="mo-setup"><button class="btn-papel" ${pode ? "" : "disabled"} onclick="moAcao({acao:'setup_aplicar', idx:${i}})" title="Enviar este setup para a mochila">${esc(n)}</button><button class="mo-setup-x" onclick="moSetup('apagar', ${i})" title="Apagar">×</button></span>`).join("")}
        <span class="mo-setup-novo"><input id="mo-setup-nome" maxlength="40" placeholder="Nome do setup (ex.: Cervos Colorado)"><button class="btn-papel" ${lida ? "" : "disabled"} onclick="moSetup('salvar')">Salvar setup atual</button></span>
      </div>
    </div>
    <div class="mo-bloco">
      <div class="mo-rotulo">1 · O que você vai caçar? ${ajuda("mochila_especies")}</div>
      ${especiesHtml}
      <div class="mo-sub-rotulo">Contratos ${ajuda("mochila_contratos")}</div>
      <div class="mo-contratos">${contratos}</div>
      ${coberturaHtml}
      ${d.requisitos.length ? `<div class="mo-precisa"><span>O que precisa:</span>${d.requisitos.map(r => `<b>${esc(r)}</b>`).join("")}</div>` : ""}
    </div>
    <div class="mo-bloco">
      <div class="mo-rotulo">2 · Sua mochila no jogo <span class="mo-dica">verde = serve para os contratos · para montar a caçada de um animal, abra o <b>Diário</b> e escolha a espécie</span></div>
      ${lida ? `<div class="mo-tabuleiro">${secao(MO_TIPOS[0])}${secao(MO_TIPOS[1])}${secao(MO_TIPOS[2])}</div>`
             : `<div class="mo-vazio-grande"><b>${d.em_reserva ? "Lendo a mochila…" : "Entre numa reserva no jogo"}</b><span>Os espaços aparecem aqui assim que o jogo responder.</span></div>`}
    </div>
  </div>`;
}

// espaços numerados como no Diário: 1 e 2 armas, 3 a 8 equipamentos (o GPS fica à parte)
function moNumero(tipo, idx) {
  const nArmas = (mochilaDados && mochilaDados.slots && mochilaDados.slots["Inventory.Weapon"]) || 2;
  return tipo === "Inventory.Weapon" ? idx + 1 : tipo === "Inventory.Objects" ? nArmas + idx + 1 : null;
}
const moOnde = (tipo, idx) => { const n = moNumero(tipo, idx); return n ? `espaço ${n}` : "GPS"; };

// ---- espécies escolhidas para a mochila
let moEspSincronizado = false;
function moEspSalvar() {
  try { localStorage.setItem("hs3_mo_esp", JSON.stringify(mochilaEspecies)); } catch {}
  moEspSincronizado = true;
  post("/api/mo_especies", { lista: mochilaEspecies }).catch(() => {});
  renderArmario(true);
}
function moEspAlternar(tag) {
  mochilaEspecies = mochilaEspecies.includes(tag) ? mochilaEspecies.filter(t => t !== tag) : [...mochilaEspecies, tag];
  moEspSalvar();
}
const semAcento = (t) => (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
function moEspFiltrar(txt) {
  const caixa = $("mo-esp-res");
  const q = semAcento(txt.trim());
  if (!q) { caixa.innerHTML = ""; return; }
  const lista = (mochilaDados.especies || []).filter(e => semAcento(e.nome + " " + e.reservas.join(" ")).includes(q)).slice(0, 12);
  caixa.innerHTML = lista.length ? lista.map(e => `<button class="mo-esp-op ${mochilaEspecies.includes(e.tag) ? "on" : ""}" onmousedown="event.preventDefault()" onclick="moEspAlternar('${esc(e.tag)}')">
      <span class="mo-check">${mochilaEspecies.includes(e.tag) ? "✔" : ""}</span>${esc(e.nome)} <small>${esc(e.reservas.join(", "))}${e.aqui ? " · nesta reserva" : ""}</small></button>`).join("")
    : `<span class="mo-dica">Nenhuma espécie com esse nome.</span>`;
}
function moEspVarias() {
  const grupos = {};
  (mochilaDados.especies || []).forEach(e => (grupos[e.aqui ? "Nesta reserva" : (e.reservas[0] || "Outras")] ||= []).push(e));
  const ordem = Object.keys(grupos).sort((a, b) => (a === "Nesta reserva" ? -1 : b === "Nesta reserva" ? 1 : a.localeCompare(b)));
  moModal(`<header class="mo-jan-topo"><div><h3>O que você vai caçar?</h3><small>Toque em quantas espécies quiser; a mochila é sugerida para todas juntas</small></div>
      <button class="mo-x" onclick="moFecharModal();renderArmario(true)">✕</button></header>
    <div class="mo-jan-corpo">${ordem.map(g => `<h4>${esc(g)}</h4><div class="mo-esp-grade">${grupos[g].map(e => `
        <label class="mo-esp-card"><input type="checkbox" ${mochilaEspecies.includes(e.tag) ? "checked" : ""} onchange="moEspMarcar('${esc(e.tag)}', this.checked)">
          <span>${esc(e.nome)}</span></label>`).join("")}</div>`).join("")}</div>
    <footer class="mo-jan-rodape"><button class="sec" onclick="mochilaEspecies=[];document.querySelectorAll('.mo-esp-card input').forEach(i=>i.checked=false)">Desmarcar todas</button>
      <button class="ok" onclick="moFecharModal();moEspSalvar()">Pronto</button></footer>`);
}
function moEspMarcar(tag, sim) {
  mochilaEspecies = sim ? [...new Set([...mochilaEspecies, tag])] : mochilaEspecies.filter(t => t !== tag);
}

function moMissao(id) {
  const todas = mochilaDados.ativas.map(m => m.id);
  let sel = mochilaMissoes || todas.slice();
  sel = sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id];
  mochilaMissoes = sel.length === todas.length ? null : (sel.length ? sel : ["nenhuma"]);
  renderArmario(true);
}

function moFecharModal() { document.querySelectorAll(".mo-modal").forEach(m => m.remove()); }
function moModal(html) {
  moFecharModal();
  const m = document.createElement("div");
  m.className = "mo-modal";
  m.innerHTML = `<div class="mo-janela">${html}</div>`;
  m.onclick = (e) => { if (e.target === m) moFecharModal(); };
  document.body.appendChild(m);
  return m;
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") moFecharModal(); });

function moAviso(txt, tipo) {
  const t = document.createElement("div");
  t.className = "mo-toast " + (tipo || "");
  t.textContent = txt;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add("sai"), 3200);
  setTimeout(() => t.remove(), 3800);
}

function moEscolher(tipo, idx) {
  const d = mochilaDados;
  const T = MO_TIPOS.find(x => x.tipo === tipo);
  const atual = d.mochila.find(x => x.tipo === tipo && x.idx === idx);
  const lista = d.possuidos.filter(i => i.slot === tipo);
  const naMochila = new Set(d.mochila.map(x => x.item));
  const cat = (i) => {
    if (tipo !== "Inventory.Weapon") return i.grupo;
    const t = i.tipo || "";
    return /Bow|Crossbow/.test(t) ? "Arcos" : /Shotgun/.test(t) ? "Espingardas" : /Handgun|Pistol|Revolver/.test(t) ? "Pistolas" : "Rifles";
  };
  const cats = [...new Set(lista.map(cat))];
  const cartao = (i) => {
    const ja = naMochila.has(i.item);
    return `<button class="mo-opcao ${i.serve ? "serve" : ""} ${ja ? "ja" : ""}" data-nome="${esc(i.nome.toLowerCase())}" data-cat="${esc(cat(i))}" ${ja ? "disabled" : `onclick="moPor('${esc(i.item)}','${tipo}',${idx})"`}>
      ${moFoto(i, T.classe === "armas" ? "larga" : "")}
      <span class="mo-opcao-nome">${esc(i.nome)}</span>
      <span class="mo-opcao-sub">${ja ? "já está na mochila" : esc(i.motivo || i.grupo)}</span>${i.serve && !ja ? `<span class="mo-selo sim">✔ serve</span>` : ""}
    </button>`;
  };
  const porUso = (a, b) => naMochila.has(a.item) - naMochila.has(b.item);   // o que já está na mochila vai para o fim
  const servem = lista.filter(i => i.serve).sort(porUso), outros = lista.filter(i => !i.serve).sort(porUso);
  moModal(`<header class="mo-jan-topo"><div><h3>Escolher ${T.classe === "armas" ? "arma" : T.classe === "gps" ? "GPS" : "equipamento"}</h3>
      <small>${T.nome} · ${moOnde(tipo, idx)}${atual ? ` · hoje: ${esc(atual.nome)}` : ""}</small></div>
      <input class="mo-busca" placeholder="Procurar…" oninput="moFiltrar(this.value)"><button class="mo-x" onclick="moFecharModal()">✕</button></header>
    ${cats.length > 1 ? `<div class="mo-cats"><button class="on" onclick="moCat(this,'')">Todos</button>${cats.map(c => `<button onclick="moCat(this,'${esc(c)}')">${esc(c)}</button>`).join("")}</div>` : ""}
    <div class="mo-jan-corpo">
      ${servem.length ? `<h4>Servem para os contratos (${servem.length})</h4><div class="mo-opcoes">${servem.map(cartao).join("")}</div>` : ""}
      ${outros.length ? `<h4>${servem.length ? "Outros itens seus" : "Seus itens"} (${outros.length})</h4><div class="mo-opcoes">${outros.map(cartao).join("")}</div>` : ""}
      ${lista.length ? "" : `<p class="mo-dica">Você não tem itens deste tipo.</p>`}
    </div>`);
  moFiltroCat = ""; moFiltroTxt = "";
  setTimeout(() => document.querySelector(".mo-busca")?.focus(), 30);
}
let moFiltroCat = "", moFiltroTxt = "";
function moAplicarFiltro() {
  document.querySelectorAll(".mo-opcao").forEach(b => b.style.display =
    (!moFiltroTxt || b.dataset.nome.includes(moFiltroTxt)) && (!moFiltroCat || b.dataset.cat === moFiltroCat) ? "" : "none");
  document.querySelectorAll(".mo-jan-corpo h4").forEach(h => {
    const g = h.nextElementSibling;
    h.style.display = g && [...g.children].some(c => c.style.display !== "none") ? "" : "none";
  });
}
function moFiltrar(t) { moFiltroTxt = t.trim().toLowerCase(); moAplicarFiltro(); }
function moCat(btn, c) {
  moFiltroCat = c;
  btn.parentElement.querySelectorAll("button").forEach(b => b.classList.toggle("on", b === btn));
  moAplicarFiltro();
}
function moAcessorios(item) {
  const a = mochilaDados.mochila.find(x => x.item === item);
  if (!a) return;
  const secao = (e) => {
    const sem = `<button class="mo-opcao ${!e.atual ? "montado" : ""}" ${!e.atual ? "disabled" : `onclick="moAcessorio('${esc(a.id)}','${esc(e.atual)}',true)"`}>
        <div class="mo-foto"><span class="mo-foto-ini">∅</span></div><span class="mo-opcao-nome">Sem ${esc(e.nome.toLowerCase())}</span>
        <span class="mo-opcao-sub">${!e.atual ? "assim está agora" : "tira o que está montado"}</span></button>`;
    return `<h4>${esc(e.nome)} <small>${e.atual ? "montado: " + esc(e.atual_nome || "") : "nada montado"}</small></h4>
      <div class="mo-opcoes">${sem}${e.opcoes.map(o => `<button class="mo-opcao ${o.atual ? "montado" : ""} ${o.recomendado ? "serve" : ""}"
          ${o.atual ? "disabled" : `onclick="moAcessorio('${esc(a.id)}','${esc(o.id)}')"`} title="${esc(o.recomendado || "")}">
        ${moFoto(o)}<span class="mo-opcao-nome">${esc(o.nome)}</span><span class="mo-opcao-sub">${esc(o.tipo)}</span>
        ${o.atual ? `<span class="mo-selo sim">montado</span>` : o.recomendado ? `<span class="mo-selo rec">recomendado</span>` : ""}</button>`).join("")
        || `<p class="mo-dica">Você não tem acessórios deste tipo. Compre na loja do jogo.</p>`}</div>`;
  };
  moModal(`<header class="mo-jan-topo"><div><h3>Acessórios da arma</h3><small>${esc(a.nome)} · clique para montar; a troca vale no jogo na hora</small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo">${a.acessorios.map(secao).join("")}</div>`);
}
function moAcessorio(arma, acessorio, tirar) {
  moFecharModal();
  moAcao({ acao: tirar ? "tirar_acessorio" : "acessorio", arma, acessorio });
}
function moPor(item, tipo, idx) { moFecharModal(); moAcao({ acao: "por", item, tipo, idx }); }

async function moAcao(corpo) {
  let r;
  try { r = await post("/api/mochila", corpo); } catch { return moAviso("O app não respondeu.", "erro"); }
  if (!r.ok) return moAviso(r.erro || "Não deu certo.", "erro");
  if (r.nada) return moAviso("A mochila já está pronta.");
  const seg = r.segundos || 3;
  moOcupadoAte = Date.now() + seg * 1000;
  moAviso(r.trocas > 1 ? `Enviando ${r.trocas} trocas para o jogo…` : "Enviado para o jogo…", "ok");
  renderArmario(true);
  setTimeout(() => { moOcupadoAte = 0; renderArmario(true); }, (seg + 1.5) * 1000);
  setTimeout(() => renderArmario(true), (seg + 5) * 1000);
}

async function moSetup(acao, idx) {
  if (acao === "apagar" && !await perguntar("Apagar este setup salvo?", "Apagar")) return;
  const nome = acao === "salvar" ? ($("mo-setup-nome")?.value || "") : undefined;
  let r;
  try { r = await post("/api/setups", { acao, idx, nome }); } catch { return moAviso("O app não respondeu.", "erro"); }
  moAviso(r.ok ? (acao === "salvar" ? "Setup salvo." : "Setup apagado.") : (r.erro || "Não deu certo."), r.ok ? "ok" : "erro");
  renderArmario(true);
}
function moConfirmarMontar() {
  const plano = mochilaDados.plano || [];
  const tipoNome = (t) => (MO_TIPOS.find(x => x.tipo === t) || {}).nome || t;
  const linhas = plano.map(x => x.acao === "por"
    ? `<li><span class="mo-li-onde">${tipoNome(x.tipo)} · ${moOnde(x.tipo, x.idx)}</span>${x.sai ? `<s>${esc(x.sai)}</s> → ` : ""}<b>${esc(x.nome)}</b></li>`
    : `<li><span class="mo-li-onde">Munição · ${esc(x.arma_nome)}</span><b>${esc(x.nome)}</b></li>`).join("");
  moModal(`<header class="mo-jan-topo"><div><h3>Montar mochila sugerida</h3><small>O que vai mudar no jogo</small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo"><ul class="mo-lista-plano">${linhas}</ul>
      <p class="mo-dica">As trocas são feitas uma por segundo para o jogo não travar. Leva uns ${plano.length + 2} segundos.</p></div>
    <footer class="mo-jan-rodape"><button class="sec" onclick="moFecharModal()">Cancelar</button>
      <button class="ok" onclick="moFecharModal();moAcao({acao:'montar',missoes:mochilaMissoes||[],especies:mochilaEspecies})">Montar agora</button></footer>`);
}

async function renderLoja() {
  const d = await (await fetch("/api/loja")).json();
  const det = d.deteccao || {};
  const med = (nome, v, dica) => `<div class="medidor"><div class="item-sub">${nome}</div><div class="v">${v == null ? "–" : Math.round(v * 100) + "%"}</div>
      <div class="b"><i style="left:${Math.min(100, (v || 0) * 100)}%"></i></div><div class="item-sub">${dica}</div></div>`;
  let html = `<header class="pag-topo"><h2>Roupas e camuflagem ${ajuda("loja")}</h2><p>Sua camuflagem agora e o que dá para comprar. Em tudo aqui, <b>quanto maior, melhor</b>: mais escondido, mais silencioso, menos cheiro, mais rápido.</p></header>
    <h3>Sua camuflagem agora</h3><div class="medidores">
      ${med("Visual", det.visual, "quanto maior, menos os animais te veem")}${med("Silêncio", det.som, "quanto maior, menos te ouvem")}${med("Cheiro", det.cheiro, "quanto maior, menos te sentem pelo faro")}</div>
    <p class="item-sub">O jogo soma as 6 peças que você veste (blusa, calça, calçado, luvas, cabeça e mochila) e transforma em porcentagem.
      Postura, movimento, vento e vegetação contam por fora: agachado, devagar e com o vento no rosto você some ainda mais.</p>`;
  html += `<h3>Você está vestindo</h3>` + (d.vestidos.length ? `<div class="grade-itens">${d.vestidos.map(itemLoja).join("")}</div>` : `<p class="vazio">–</p>`);
  const partes = ["Todas", ...new Set(d.itens.map(i => i.parte))];
  html += `<h3>Catálogo (${d.itens.length} peças) · saldo $${fmt(d.creditos)}</h3><div class="filtros">${partes.map(p =>
      `<button class="${p === filtroLoja ? "ativo" : ""}" onclick="filtroLoja='${p}';renderLoja()">${esc(p)}</button>`).join("")}</div>`;
  const lista = d.itens.filter(i => filtroLoja === "Todas" || i.parte === filtroLoja);
  html += `<div class="grade-itens">${lista.map(itemLoja).join("")}</div>
    <p class="item-sub">Os números (0 a 100) vêm do próprio jogo: quanto maior, melhor (menos o animal te vê, ouve ou sente; “Corrida” = mais rápido). A compra é feita na loja do jogo com seus créditos.</p>`;
  $("painel-loja").innerHTML = html;
}
function itemLoja(i) {
  const acao = i.vestido ? `<span class="item-tag">Vestindo</span>` : i.comprado ? `<span class="item-tag cinza">Já é seu · vista no guarda-roupa</span>`
    : `<button class="btn-papel verde" onclick="comprarItem('${i.id}','${esc(i.nome).replace(/'/g, "")}',${i.preco})">Comprar $${fmt(i.preco)}</button>`;
  return `<div class="item ${i.vestido ? "vestido" : ""}"><div class="item-nome">${esc(i.nome)}</div>
    <div class="item-sub">${esc(i.parte)}${i.marca ? " · " + esc(i.marca) : ""} · camuflagem <b>${i.camuflagem}</b></div>
    ${barraStat("Visual", i.stats.visual)}${barraStat("Som", i.stats.som)}${barraStat("Cheiro", i.stats.cheiro)}${barraStat("Corrida", i.stats.corrida)}
    <div style="margin-top:6px">${acao}</div></div>`;
}
async function comprarItem(id, nome, preco) {
  if (!await perguntar(`Comprar "${nome}" por $${fmt(preco)} na loja do jogo?`)) return;
  let r;
  try { r = await post("/api/comprar", { id }); } catch { return moAviso("O app não respondeu.", "erro"); }
  if (!r.ok) return moAviso(r.erro, "erro");
  moAviso("Comprando no jogo…");
  for (let i = 0; i < 12; i++) {           // o jogo responde em 1–3 s
    await new Promise(ok => setTimeout(ok, 1000));
    let s;
    try { s = await (await fetch("/api/compra?ref=" + r.ref)).json(); } catch { continue; }
    if (!s.pronto) continue;
    if (s.ok) moAviso(`Comprado: ${nome}. Saldo agora $${fmt(s.saldo)}.`, "ok");
    else moAviso(`O jogo recusou a compra de ${nome}. Ele pode ser de um DLC que você não tem.`, "erro");
    setTimeout(() => { if (abaAtual === "loja") renderLoja(); if (abaAtual === "enciclopedia" && diario) renderEnciclopedia(); if (kitTag) carregarKit(kitTag, true); }, 1500);
    return;
  }
  moAviso("O jogo não confirmou a compra. Confira na loja do jogo.", "erro");
}

// ---------------------------------------------------------------- Diário de campo
let diario = null, diarioCat = "animais", diarioSel = null, diarioBusca = "", diarioAberto = false, diarioReserva = null;   // aberto: no celular mostra a página no lugar da lista
const moedaFmt = (i) => i.preco == null ? "" : (i.moeda === "pontos de campo" ? `${fmt(i.preco)} pts de campo` : `$${fmt(i.preco)}`);
const chips = (l, cls = "") => (l || []).map(x => `<span class="chip ${cls}">${esc(x)}</span>`).join("") || `<span class="item-sub">–</span>`;
const quando = (ts) => ts ? new Date(ts * 1000).toLocaleDateString("pt-BR") : "";

function semFoto(i, cat, grande) {
  if (cat === "animais") return silhueta(i.grupo || "outro", i.tag);
  const ic = { armas: "🎯", municao: "•", roupas: "🧥", itens: "🎒", caes: "🐕", guia: "📖" }[cat] || "?";
  return `<span class="ic-vazio${grande ? " g" : ""}">${ic}</span>`;
}
function fotoDiario(i, cat, grande) {
  if (!i.imagem) return semFoto(i, cat, grande);
  return `<img src="${i.imagem}${grande ? "" : "?p=1"}" alt="" loading="lazy" onerror="this.outerHTML=this.dataset.sil" data-sil="${esc(semFoto(i, cat, grande))}">`;
}

async function renderEnciclopedia() {
  const d = await (await fetch("/api/enciclopedia")).json();
  if (!d.pronto) {
    $("painel-enciclopedia").innerHTML = `<div class="diario-vazio"><h3>Diário de campo ${ajuda("ler_dados")}</h3>
      <p>Os dados do diário (fotos, hábitos, calibres, armas, roupas, cães) são lidos do jogo uma única vez.</p>
      <p>Com o jogo aberto <b>dentro de uma reserva</b>, clique no botão abaixo. A leitura é feita aos poucos (uns 10 a 15 minutos,
      sem travar o jogo) e esta página se completa sozinha no fim. Se sair da reserva no meio, é só clicar de novo: continua de onde parou.</p>
      <button class="btn-papel verde" onclick="post('/api/exportar_dados',{}).then(r=>{if(r.ok)this.textContent='Lendo dados do jogo… (uns 10 a 15 minutos)';else moAviso(r.erro||'O jogo não respondeu.','erro')})">Ler dados do jogo</button></div>`;
    setTimeout(() => { if (abaAtual === "enciclopedia") renderEnciclopedia(); }, 15000);
    return;
  }
  diario = d;
  desenharDiario();
}

function desenharDiario() {
  const cat = diario.categorias.find(c => c.id === diarioCat) || diario.categorias[0];
  const q = diarioBusca.trim().toLowerCase();
  // animais: primeiro a reserva (começa na reserva em que você está)
  const reservas = cat.id === "animais" ? [...new Set(cat.itens.flatMap(i => i.reservas || []))].sort() : [];
  if (reservas.length && !reservas.includes(diarioReserva)) {
    const aqui = nomeMapa((ultimoEstado && ultimoEstado.estado && ultimoEstado.estado.mapa) || "");
    diarioReserva = reservas.includes(aqui) ? aqui : reservas[0];
  }
  const daReserva = (i) => !reservas.length || (i.reservas || []).includes(diarioReserva);
  const lista = cat.itens.filter(i => daReserva(i) && (!q || (i.nome + " " + (i.sub || i.cabecalho || "") + " " + (i.calibre || "")).toLowerCase().includes(q)));
  if (diarioPedido && cat.id === "animais") {      // aberto pelo mapa (zona de um animal)
    const alvo = cat.itens.find(i => i.tag === diarioPedido);
    if (alvo) { diarioSel = alvo.id; diarioAberto = true; if (!lista.includes(alvo)) lista.unshift(alvo); }
    diarioPedido = null;
  }
  if (!diarioSel || !lista.some(i => i.id === diarioSel)) diarioSel = (lista[0] || {}).id;
  const grupos = {};
  lista.forEach(i => (grupos[i.cabecalho || i.sub || cat.nome] ||= []).push(i));
  const menu = Object.entries(grupos).map(([g, its]) => `<div class="dm-grupo">${esc(g)} <small>${its.length}</small></div>` + its.map(i => `
      <button class="dm-item ${i.id === diarioSel ? "sel" : ""}" data-id="${esc(i.id)}">
        <span class="dm-foto">${fotoDiario(i, cat.id)}</span>
        <span class="dm-nome">${esc(i.nome)}${i.tem ? ` <i class="dm-tem" title="Você tem">✔</i>` : ""}${i.abates ? ` <i class="dm-tem" title="Abatidos">${i.abates}</i>` : ""}</span>
      </button>`).join("")).join("") || `<p class="item-sub" style="padding:8px">Nada encontrado.</p>`;
  const it = cat.itens.find(i => i.id === diarioSel);
  $("painel-enciclopedia").innerHTML = `<div class="diario ${diarioAberto ? "aberto" : ""}">
    <aside class="diario-menu">
      <div class="dm-cats">${ajuda("diario")}${diario.categorias.map(c => `<button data-cat="${c.id}" class="${c.id === cat.id ? "ativo" : ""}">${esc(c.nome)} <small>${c.itens.length}</small></button>`).join("")}</div>
      ${reservas.length ? `<div class="dm-reservas">${reservas.map(r => `<button data-res="${esc(r)}" class="${r === diarioReserva ? "ativo" : ""}">${esc(r)} <small>${cat.itens.filter(i => (i.reservas || []).includes(r)).length}</small></button>`).join("")}</div>` : ""}
      <input class="dm-busca" placeholder="Buscar…" value="${esc(diarioBusca)}">
      <div class="dm-lista">${menu}</div>
    </aside>
    <article class="diario-pagina"><button class="dp-voltar" onclick="diarioAberto=false;desenharDiario()">← ${esc(cat.nome)}</button>${it ? (cat.id === "animais" ? paginaAnimal(it) : paginaItem(it, cat)) : ""}</article>
  </div>`;
  const p = $("painel-enciclopedia");
  p.querySelectorAll(".dm-cats button").forEach(b => b.onclick = () => { diarioCat = b.dataset.cat; diarioSel = null; diarioBusca = ""; diarioAberto = false; desenharDiario(); });
  p.querySelectorAll(".dm-reservas button").forEach(b => b.onclick = () => { diarioReserva = b.dataset.res; diarioSel = null; diarioAberto = false; desenharDiario(); });
  p.querySelectorAll(".dm-item").forEach(b => b.onclick = () => { diarioSel = b.dataset.id; diarioAberto = true; desenharDiario(); p.querySelector(".diario-pagina").scrollTop = 0; });
  const busca = p.querySelector(".dm-busca");
  busca.oninput = () => { diarioBusca = busca.value; const pos = busca.selectionStart; desenharDiario(); const n = $("painel-enciclopedia").querySelector(".dm-busca"); n.focus(); n.setSelectionRange(pos, pos); };
  const sel = p.querySelector(".dm-item.sel"); if (sel) sel.scrollIntoView({ block: "nearest" });
  if (cat.id === "animais" && it) carregarKit(it.tag);
}

function secao(titulo, corpo) { return corpo ? `<section class="dp-sec"><h4>${esc(titulo)}</h4>${corpo}</section>` : ""; }
function paragrafos(l) { return (l || []).filter(Boolean).map(t => `<p>${esc(t)}</p>`).join(""); }

function paginaAnimal(a) {
  const dados = [
    a.preco_kg != null && ["Preço por kg", `$${a.preco_kg.toFixed(2)}`],
    a.taxidermia != null && ["Taxidermia", `$${fmt(a.taxidermia)}`],
    a.chamado_m && ["Chamado ouvido a", `${fmt(a.chamado_m)} m`],
    a.tipo_caca && ["Tipo de caça", esc(a.tipo_caca)],
  ].filter(Boolean);
  const meus = [["Avistados", a.vistos], ["Abatidos", a.abates],
    a.melhor_genetica != null && ["Melhor genética", pct(a.melhor_genetica)],
    a.tiro_mais_longo && ["Tiro mais longo", metros(a.tiro_mais_longo)]].filter(Boolean);
  return `<header class="dp-topo">
      <div class="dp-foto animal">${fotoDiario(a, "animais", true)}</div>
      <div><div class="dp-cab">${esc(a.cabecalho)}</div><h2>${esc(a.nome)}</h2>
        <div>${(a.reservas || []).map(r => `<span class="chip latao">${esc(r)}</span>`).join("")}</div>
        ${a.descricao ? `<p class="dp-desc">${esc(a.descricao)}</p>` : ""}</div>
    </header>
    <div id="kit" class="kit" data-tag="${esc(a.tag)}"><div class="kit-carregando">Montando a lista do que serve para esta espécie…</div></div>
    <div class="dp-colunas">
      <div>
        ${secao(a.secoes_titulo || "Aparência e hábitos", paragrafos(a.secoes))}
        ${secao(a.habitat_titulo || "Habitat / bioma preferido", paragrafos(a.habitat))}
      </div>
      <div>
        ${secao("Dados de caça", dados.length ? `<table class="dp-tab">${dados.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}</table>` : "")}
        ${a.medalhas.length ? secao("Medalhas (pontuação do troféu)", `<table class="dp-tab">${a.medalhas.map(m => `<tr><td><span class="medalha ${esc(m.nome)}"></span>${esc(m.nome)}</td><td>${m.pontos}+</td></tr>`).join("")}</table>`) : ""}
        ${secao("Seus registros", `<table class="dp-tab">${meus.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}</table>` +
          (a.ultimos_abates.length ? `<div class="item-sub" style="margin-top:6px">${a.ultimos_abates.map(x => `${quando(x.ts)} · ${metros(x.distancia_m)} · ${x.calibre || "?"} · genética ${pct(x.genetica || 0)}`).join("<br>")}</div>` : ""))}
        ${a.licencas.length ? secao("Licenças", `<div class="dp-licencas">${a.licencas.map(l => `<figure><img src="${l.imagem}" loading="lazy" onerror="this.closest('figure').remove()"><figcaption>${esc(l.reserva)}</figcaption></figure>`).join("")}</div>`) : ""}
      </div>
    </div>`;
}

function paginaItem(i, cat) {
  const linhas = [
    i.sub && ["Tipo", esc(i.sub)], i.raca && ["Raça", esc(i.raca)], i.marca && ["Marca", esc(i.marca)],
    i.preco != null && ["Preço", moedaFmt(i)], i.cargas && ["Quantidade por compra", i.cargas],
    i.calibre && ["Calibre", esc(i.calibre)],
    i.tem != null && ["Situação", i.em_uso ? "Em uso agora" : i.tem ? "Você tem" : "Não tem"],
  ].filter(Boolean);
  if (cat.id === "guia") return `<header class="dp-topo"><div class="dp-foto">${fotoDiario(i, cat.id, true)}</div>
      <div><div class="dp-cab">${esc(i.sub)}</div><h2>${esc(i.nome)}</h2>${i.descricao ? `<p class="dp-desc">${esc(i.descricao)}</p>` : ""}</div></header>`;
  const compravel = !i.tem && i.preco && i.moeda === "créditos" && (cat.id === "roupas" || cat.id === "itens" || cat.id === "armas" || cat.id === "municao");
  return `<header class="dp-topo">
      <div class="dp-foto">${fotoDiario(i, cat.id, true)}</div>
      <div><div class="dp-cab">${esc(cat.nome)} · ${esc(i.sub || "")}</div><h2>${esc(i.nome)}</h2>
        ${i.tem ? `<span class="chip">✔ ${i.em_uso ? "Em uso" : "Você tem"}</span>` : ""}
        ${i.descricao ? `<p class="dp-desc">${esc(i.descricao)}</p>` : ""}
        ${compravel ? `<button class="btn-papel verde" onclick="comprarItem('${esc(i.id)}','${esc(i.nome).replace(/'/g, "")}',${i.preco})">Comprar ${moedaFmt(i)}</button>` : ""}</div>
    </header>
    <div class="dp-colunas">
      <div>
        ${secao("Ficha", `<table class="dp-tab">${linhas.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}</table>`)}
        ${i.stats ? secao(`Camuflagem ${i.camuflagem}/100`, barraStat("Visual", i.stats.visual) + barraStat("Som", i.stats.som) + barraStat("Cheiro", i.stats.cheiro) + barraStat("Corrida", i.stats.corrida)) : ""}
        ${i.atributos ? secao("Características", `<table class="dp-tab">${Object.entries(i.atributos).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join("")}</table>`) : ""}
      </div>
      <div>
        ${(i.calibres || []).map(c => secao(`${cat.id === "armas" ? "Calibre " : ""}${c.nome} — espécies permitidas`, chips(c.especies)) +
          (c.proibidas.length ? `<div class="dp-proib"><b>Proibido para:</b> ${chips(c.proibidas, "vermelho")}</div>` : "")).join("")}
      </div>
    </div>`;
}

function atualizarAba() {
  if (abaAtual === "armario") renderArmario();
  else if (abaAtual === "loja") renderLoja();
  else if (abaAtual === "enciclopedia") renderEnciclopedia();
}
setInterval(() => { if (abaAtual === "armario" || abaAtual === "loja") atualizarAba(); }, 8000);
