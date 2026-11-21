const $ = (id) => document.getElementById(id);
const fmt = (n) => (n === null || n === undefined) ? "–" : Number(n).toLocaleString("pt-BR");
const pct = (n) => (n === null || n === undefined) ? "–" : Math.round(n * 100) + "%";
const metros = (n) => (n === null || n === undefined) ? "–" : (n >= 1000 ? (n / 1000).toFixed(2).replace(".", ",") + " km" : Math.round(n) + " m");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const post = (url, body) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(r => r.json());

// ------------------------------------------------------------------ mapa
const S = 4096;                         // unidades do mapa (pixels da imagem exportada)
let MUNDO = 1224000;                    // largura do mundo em cm (vem do jogo)
const toLL = (p) => [-(p.y / MUNDO + 0.5) * S, (p.x / MUNDO + 0.5) * S];
const fromLL = (ll) => ({ x: (ll.lng / S - 0.5) * MUNDO, y: (-ll.lat / S - 0.5) * MUNDO });

const mapa = L.map("mapa", { crs: L.CRS.Simple, minZoom: -3, maxZoom: 2, zoomSnap: 0.25, attributionControl: false, zoomControl: true });
const limites = [[-S, 0], [0, S]];
mapa.fitBounds(limites);
let camadaImagem = null, camadaNevoa = null, nivelAtual = null, nevoaVersao = 0;
const grupoPois = L.layerGroup().addTo(mapa);
const grupoEstr = L.layerGroup();
const grupoAnimais = L.layerGroup().addTo(mapa);
const grupoMissoes = L.layerGroup().addTo(mapa);
let marcJogador = null, marcPino = null;
const marcAnimais = {};
let jaCentralizou = false, ultimoEstado = null;

const ICONE_POI = { lugar: "◆", torre: "♜", acampamento: "▲", estrutura: "⌂", sede: "⌂", servico: "★", npc: "☻", veiculo: "⛟", cao: "✦", viagem: "⇄" };

function iconePoi(p) {
  const cls = p.descoberto ? p.categoria : "oculto";
  return L.divIcon({ className: "", html: `<div class="mk-poi ${cls}">${p.descoberto ? (ICONE_POI[p.categoria] || "•") : "?"}</div>`, iconSize: [26, 28], iconAnchor: [13, 14] });
}

async function carregarPois() {
  let lista = [];
  try { lista = await (await fetch("/api/pois")).json(); } catch { return; }
  grupoPois.clearLayers(); grupoEstr.clearLayers();
  for (const p of lista) {
    const m = L.marker(toLL(p), { icon: iconePoi(p), riseOnHover: true })
      .bindTooltip(`<b>${esc(p.descoberto ? p.nome : "Local não descoberto")}</b>${p.descoberto ? "" : "<br><i>Explore para revelar</i>"}`, { direction: "top", offset: [0, -12] });
    m.on("click", () => perguntarPino(L.latLng(toLL(p)), p.descoberto ? p.nome : "Local não descoberto"));
    (p.categoria === "estrutura" ? grupoEstr : grupoPois).addLayer(m);
  }
}

function atualizarMapaBase(info) {
  if (!info || !info.nivel) return;
  MUNDO = info.tamanho_mundo || MUNDO;
  if (info.nivel !== nivelAtual && info.imagem) {
    nivelAtual = info.nivel;
    if (camadaImagem) mapa.removeLayer(camadaImagem);
    camadaImagem = L.imageOverlay("/api/mapa.png?n=" + encodeURIComponent(nivelAtual), limites, { className: "mapa-img" }).addTo(mapa);
    camadaImagem.bringToBack();
    nevoaVersao = -1;
    carregarPois();
  }
  if (info.nevoa && info.nevoa_versao !== nevoaVersao) {
    nevoaVersao = info.nevoa_versao;
    const nova = L.imageOverlay("/api/nevoa.png?v=" + nevoaVersao, limites, { opacity: 1, interactive: false });
    if ($("f-nevoa").checked) nova.addTo(mapa);
    if (camadaNevoa) mapa.removeLayer(camadaNevoa);
    camadaNevoa = nova;
    carregarPois();
  }
}

function setaJogador(yaw) {
  return L.divIcon({ className: "", iconSize: [30, 30], iconAnchor: [15, 15],
    html: `<div class="mk-jogador" style="transform:rotate(${yaw || 0}deg)"><svg viewBox="0 0 30 30"><path d="M28 15 L4 4 L10 15 L4 26 Z" fill="#d0661f" stroke="#2b1e12" stroke-width="1.5"/></svg></div>` });
}

function perguntarPino(ll, rotulo) {
  const html = `<div style="text-align:center"><b>${esc(rotulo || "Novo pino")}</b><br>
    <button class="btn-papel verde" id="pp-ok" style="margin-top:6px">📍 Colocar pino aqui</button></div>`;
  const pop = L.popup().setLatLng(ll).setContent(html).openOn(mapa);
  setTimeout(() => {
    const b = document.getElementById("pp-ok");
    if (b) b.onclick = async () => { const w = fromLL(ll); await post("/api/pino", { x: w.x, y: w.y, rotulo }); mapa.closePopup(pop); atualizar(); };
  }, 30);
}
mapa.on("click", (e) => perguntarPino(e.latlng, "Meu pino"));

async function tirarPino() { await post("/api/pino/remover"); atualizar(); }
function centralizar() { if (ultimoEstado?.estado?.pos) mapa.setView(toLL(ultimoEstado.estado.pos), 0); }

$("f-pois").onchange = (e) => e.target.checked ? grupoPois.addTo(mapa) : mapa.removeLayer(grupoPois);
$("f-estr").onchange = (e) => e.target.checked ? grupoEstr.addTo(mapa) : mapa.removeLayer(grupoEstr);
$("f-animais").onchange = (e) => e.target.checked ? grupoAnimais.addTo(mapa) : mapa.removeLayer(grupoAnimais);
$("f-nevoa").onchange = (e) => { if (camadaNevoa) e.target.checked ? camadaNevoa.addTo(mapa) : mapa.removeLayer(camadaNevoa); };

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
    <div class="ficha-cab"><div class="ficha-sil">${silhueta(a.grupo)}</div>
      <div><div class="ficha-grupo">${esc(a.grupo_nome)}${a.lendario ? " · 👑 Lendário" : ""}</div>
      <div class="ficha-nome">${esc(a.especie_nome || a.grupo_nome)}</div>
      <div>${esc(a.sexo_nome)} · ${idadeTexto(a.idade_dias)}</div></div></div>
    <div class="ficha-lin"><span>Genética</span><b>${pct(a.genetica)}</b></div>
    <div class="ficha-barra"><i style="width:${(a.genetica || 0) * 100}%"></i><em style="left:${(pot || 0) * 100}%"></em></div>
    <div class="ficha-lin"><span>Potencial genético</span><b>${pct(pot)}</b></div>
    <div class="ficha-lin"><span>Distância</span><b>${metros(a.distancia_m)}</b></div>
    <div class="ficha-lin"><span>Direção</span><b>${direcaoTexto(a.direcao)}</b></div>
    <div class="ficha-lin"><span>Posição</span><b>${a.ao_vivo ? "🟢 ao vivo" : "⚪ última conhecida"}</b></div>
    <div class="ficha-lin"><span>Marcado há</span><b>${a.minutos} min</b></div>
    <div class="ficha-rod">Nº ${esc(a.id)} · clique para colocar um pino até ele</div>
  </div>`;
}

function atualizarAnimais(lista) {
  const vistos = new Set();
  for (const a of lista) {
    if (!a.pos) continue;
    vistos.add(String(a.id));
    const cls = `mk-animal${a.lendario ? " lendario" : ""}${a.ao_vivo ? "" : " velho"}`;
    const icone = L.divIcon({ className: "", html: `<div class="${cls}">${silhueta(a.grupo)}</div>`, iconSize: [34, 34], iconAnchor: [17, 17] });
    let m = marcAnimais[a.id];
    if (!m) {
      m = L.marker(toLL(a.pos), { icon: icone, riseOnHover: true });
      m.bindTooltip("", { className: "cartao-animal", direction: "right", offset: [16, 0], opacity: 1 });
      m.on("click", () => perguntarPino(m.getLatLng(), m._rotulo));
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
    if (!jaCentralizou && nivelAtual) { mapa.setView(toLL(st.pos), -1); jaCentralizou = true; }
  }
  const pino = st.pino_jogo || d.pino_app;
  $("btn-tirar-pino").style.display = pino ? "" : "none";
  if (pino) {
    const rot = (d.pino_app && Math.abs(d.pino_app.x - pino.x) < 200 && Math.abs(d.pino_app.y - pino.y) < 200) ? d.pino_app.rotulo : "Ponto de rota rápido";
    if (!marcPino) marcPino = L.marker(toLL(pino), { icon: L.divIcon({ className: "", html: '<div class="mk-pino">📍</div>', iconSize: [30, 30], iconAnchor: [15, 30] }), zIndexOffset: 900 }).addTo(mapa);
    marcPino.setLatLng(toLL(pino)).bindTooltip(`${esc(rot)} · ${metros(distancia(st.pos, pino))}`);
  } else if (marcPino) { mapa.removeLayer(marcPino); marcPino = null; }
  grupoMissoes.clearLayers();
  for (const m of d.ativas) if (m.local) {
    L.marker(toLL(m.local), { icon: L.divIcon({ className: "", html: '<div class="mk-missao">🚩</div>', iconSize: [24, 24], iconAnchor: [4, 24] }) })
      .bindTooltip(`<b>${esc(m.titulo)}</b><br>${esc(m.local.nome)}`).addTo(grupoMissoes);
  }
  atualizarAnimais(d.rastreados || []);
}

function distancia(a, b) { if (!a || !b) return null; return Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0)) / 100; }

// ------------------------------------------------------------------ contratos
function recompensa(m) { return `💰 ${fmt(m.creditos_pagos ?? m.creditos)} · ⭐ ${fmt(m.reputacao)}`; }

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
  if (!of.length) html = `<div class="vazio">${d.gerando ? "O Velho Earl está pensando em novos contratos…" : (d.em_reserva ? "Sem contratos no momento." : "Entre numa reserva para receber contratos.")}</div>`;
  else if (d.gerando) html += `<div class="sub">Preparando mais contratos…</div>`;
  $("ofertas").innerHTML = html;
}

function renderAtivas(d) {
  const lista = d.ativas.map(m => `<div class="ativa">
      <div class="at-titulo"><span>${esc(m.titulo)}</span><span class="recomp">${recompensa(m)}</span></div>
      <div class="of-meta">${esc(m.descricao)}</div>
      <div class="barra"><div style="width:${Math.min(100, 100 * m.progresso / m.meta)}%"></div></div>
      <div class="at-acoes"><span class="sub" style="margin-right:auto">${m.progresso}/${m.meta}</span>
        ${m.local ? `<button class="btn-papel" onclick="acao('focar','${m.id}')">📍 Pino</button>` : ""}
        <button class="btn-papel cinza" onclick="if(confirm('Abandonar este contrato?'))acao('abandonar','${m.id}')">Abandonar</button></div>
    </div>`);
  const fim = d.finalizadas.slice(0, 3).map(m => `<div class="ativa concl"><div class="at-titulo"><span>${esc(m.titulo)}</span>
      <span class="recomp">${m.status === "paga" ? "✅ Pago" : (m.enviado ? "⏳ Pagando…" : "✔ Concluída")}</span></div></div>`);
  $("ativas").innerHTML = lista.concat(fim).join("") || `<div class="vazio">Aceite um contrato do Velho Earl.</div>`;
}

async function acao(tipo, id) {
  const r = await post("/api/missoes/" + tipo, { id });
  if (!r.ok && r.erro) alert(r.erro);
  atualizar();
}

// ------------------------------------------------------------------ chat
let chatQtd = -1, chatPendente = false;
function renderChat(d) {
  const msgs = d.chat || [];
  if (msgs.length === chatQtd && chatPendente === d.respondendo) return;
  chatQtd = msgs.length; chatPendente = d.respondendo;
  const log = $("chat-log");
  log.innerHTML = (msgs.length ? "" : `<div class="msg assistant">Pergunte o que quiser sobre caça, rapaz. Vento, rastros, calibre… o Velho Earl ajuda.</div>`)
    + msgs.map(m => `<div class="msg ${m.role}">${esc(m.content)}</div>`).join("")
    + (d.respondendo ? `<div class="msg assistant pensando">Earl está pensando…</div>` : "");
  log.scrollTop = log.scrollHeight;
}
$("chat-form").onsubmit = async (e) => {
  e.preventDefault();
  const t = $("chat-txt").value.trim();
  if (!t) return;
  $("chat-txt").value = "";
  post("/api/chat", { texto: t }).then(atualizar);
  setTimeout(atualizar, 300);
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
    if (!confirm(`Atualizar para a versão ${a.nova}?\n\nO programa reinicia sozinho em alguns segundos. A parte do mod vale na próxima vez que você abrir o jogo.`)) return;
    atualizando = true; versaoAntes = ultimoEstado && ultimoEstado.versao;
    await post("/api/atualizar");
  } else {
    $("btn-atualizar").textContent = "Verificando…";
    const r = await post("/api/verificar");
    mostrarAtualizacao(r, r.atual);
    if (r.erro) alert(r.erro);
    else if (!r.disponivel) alert(`Você já está na versão mais recente (v${r.atual}).`);
  }
}
async function sair() {
  if (!confirm("Fechar o HS3 Companion?")) return;
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
  const st = d.estado || {};
  $("led").className = "led " + (d.em_reserva ? "on" : d.conectado ? "meio" : "");
  $("conexao-txt").textContent = d.em_reserva ? `Conectado · ${nomeMapa(st.mapa)}` : d.conectado ? "Conectado · fora da reserva" : "Jogo não detectado";

  // placas
  const moedas = st.moedas || {};
  $("p-saldo").textContent = moedas["Currency.Credits"] !== undefined ? "$" + fmt(moedas["Currency.Credits"]) : "–";
  $("p-ponte").textContent = d.em_reserva ? "Ativa" : d.conectado ? "Em espera" : "Desligada";
  const rep = d.reputacao_mapa_atual;
  $("p-rep").textContent = rep ? fmt(rep.valor) : "–";
  $("p-contratos").textContent = `${d.ativas.length} ativo${d.ativas.length === 1 ? "" : "s"}`;
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
  $("npc-apelido").textContent = npc.apelido;
  renderOfertas(d); renderAtivas(d); renderChat(d);
  $("ollama-status").textContent = d.ollama.ok ? `IA: ${d.ollama.modelo}` : `IA desligada: ${d.ollama.erro || "Ollama não encontrado"} (contratos simples continuam funcionando)`;

  // telemetria
  const prox = (d.rastreados || []).find(a => a.distancia_m !== null);
  const pino = st.pino_jogo;
  $("telemetria").innerHTML = [
    ["Reserva", nomeMapa(st.mapa)],
    ["Posição", st.pos ? `${Math.round(st.pos.x / 100)} / ${Math.round(st.pos.y / 100)} · alt ${Math.round(st.pos.z / 100)} m` : "–"],
    ["Animais rastreados", fmt((d.rastreados || []).length)],
    ["Mais próximo", prox ? `${esc(prox.especie_nome || prox.grupo_nome)} · ${metros(prox.distancia_m)}` : "–"],
    ["Pino", pino ? metros(distancia(st.pos, pino)) : "–"],
  ].map(([k, v]) => `<span>${k}</span><b>${v}</b>`).join("");
  const s = d.estatisticas;
  $("diario").innerHTML = [
    ["Abates", fmt(s.total_abates)], ["Distância média", metros(s.distancia_media)], ["Tiro mais longo", metros(s.distancia_maxima)],
    ["Melhor genética", s.melhor_genetica ? `${pct(s.melhor_genetica.genetica)} · ${esc(s.melhor_genetica.especie)}` : "–"],
    ["Contratos concluídos", fmt(s.missoes_concluidas)], ["Créditos de contratos", fmt(s.creditos_ganhos)],
  ].map(([k, v]) => `<span>${k}</span><b>${v}</b>`).join("");
  $("ultimos").innerHTML = d.abates.slice(0, 5).map(a =>
    `<div><span>${esc(a.especie_nome || a.grupo_nome)} ${a.sexo_nome ? "· " + esc(a.sexo_nome) : ""}</span><span>${pct(a.genetica)} · ${metros(a.distancia_m)} · ${esc((a.arma || "").replace(/^ID_/, "").replace(/_/g, " "))}</span></div>`
  ).join("") || `<div><span>Nenhum abate ainda.</span></div>`;
}

atualizar();
setInterval(atualizar, 2000);
setInterval(() => { if (nivelAtual) carregarPois(); }, 60000);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
