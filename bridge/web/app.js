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
  const pt = d.patente;
  $("p-patente").textContent = pt.patente;
  $("p-patente-barra").style.width = (pt.progresso * 100) + "%";
  $("p-patente-sub").textContent = `${fmt(pt.pontos)} pts` + (pt.proxima ? ` · faltam ${fmt(pt.faltam)} p/ ${pt.proxima}` : "");
  $("f-voltar").checked = !!d.config?.voltar_ao_ultimo_local;
  $("f-hud").checked = d.config?.contratos_no_jogo !== false;
  $("btn-voltar").style.display = d.tem_local_salvo ? "" : "none";
  $("aviso-teleporte").textContent = d.aviso_teleporte || "";
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


// ------------------------------------------------------------------ abas: armário, loja, enciclopédia
let abaAtual = "mapa", filtroLoja = "Todas";
document.querySelectorAll("#abas button").forEach(b => b.onclick = () => {
  abaAtual = b.dataset.aba;
  document.querySelectorAll("#abas button").forEach(x => x.classList.toggle("ativo", x === b));
  ["armario", "loja", "enciclopedia"].forEach(a => $("painel-" + a).classList.toggle("ativo", a === abaAtual));
  document.querySelector(".mapa-papel").classList.toggle("so-mapa", abaAtual === "mapa");
  if (abaAtual === "mapa") setTimeout(() => mapa.invalidateSize(), 50);
  atualizarAba();
});
$("f-voltar").onchange = (e) => post("/api/config", { chave: "voltar_ao_ultimo_local", valor: e.target.checked });
$("f-hud").onchange = (e) => post("/api/config", { chave: "contratos_no_jogo", valor: e.target.checked });
async function voltarAgora() { const r = await post("/api/voltar"); if (!r.ok) alert(r.erro); }

function barraStat(nome, v) {
  return `<div class="st"><span>${nome}</span><span class="b"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></span><b>${Math.round(v)}</b></div>`;
}

function cartaoItem(i) {
  const tags = [i.rotulo && `<span class="item-tag cinza">${esc(i.rotulo)}</span>`, i.calibre && `<span class="item-tag latao">${esc(i.calibre)}</span>`,
    (i.cargas > 1) && `<span class="item-tag">×${i.cargas}</span>`].filter(Boolean).join("");
  const esp = i.especies && i.especies.length ? `<div class="item-sub">Serve para: ${esc(i.especies.slice(0, 8).join(", "))}${i.especies.length > 8 ? "…" : ""}</div>` : "";
  return `<div class="item"><div class="item-nome">${esc(i.nome)}</div><div>${tags}</div>${esp}
    ${i.marca ? `<div class="item-sub">${esc(i.marca)}</div>` : ""}</div>`;
}

// ---------------------------------------------------------------- Mochila
let mochilaMissoes = null;  // ids escolhidos (null = todas as ativas)
let mochilaDados = null;
async function renderArmario() {
  const p = $("painel-armario");
  if (p.contains(document.activeElement) && document.activeElement.tagName === "SELECT") return;
  const q = mochilaMissoes ? `?missoes=${mochilaMissoes.join(",")}` : "";
  const d = await (await fetch("/api/mochila" + q)).json();
  mochilaDados = d;
  if (!d.pronto) { p.innerHTML = `<p class="vazio">Primeiro leia os dados do jogo na aba Diário de campo.</p>`; return; }
  const slots = d.slots, porTipo = (t) => d.mochila.filter(m => m.tipo === t);
  const cartao = (i, botoes) => `<div class="mo-item ${i.serve ? "serve" : i.serve === false ? "nao" : ""}" title="${esc(i.motivo || "")}">
      <span class="mo-foto">${i.imagem ? `<img src="${i.imagem}" onerror="this.remove()">` : ""}</span>
      <div class="mo-txt"><b>${esc(i.nome)}</b>${i.motivo ? `<small>${i.serve ? "✔ " : ""}${esc(i.motivo)}</small>` : ""}${botoes || ""}</div></div>`;
  const vagas = (t, nome) => {
    const itens = porTipo(t), n = slots[t] || itens.length;
    const cel = [];
    for (let k = 0; k < Math.max(n, itens.length); k++) {
      const it = itens.find(x => x.idx === k) || (itens.every(x => x.idx == null) ? itens[k] : null);
      cel.push(it ? cartao(it, `<button class="mo-btn" onclick="moAcao({acao:'tirar',item:'${it.item}'})">Tirar</button>`)
                  : `<div class="mo-item vazio-slot">espaço livre</div>`);
    }
    return `<div class="mo-slot"><h4>${nome} <small>${itens.length}/${n}</small></h4><div class="mo-grade">${cel.join("")}</div></div>`;
  };
  const grupos = {};
  d.possuidos.forEach(i => (grupos[i.grupo] ||= []).push(i));
  const proxIdx = (t) => { const usados = new Set(porTipo(t).map(x => x.idx)); for (let k = 0; k < (slots[t] || 1); k++) if (!usados.has(k)) return k; return (slots[t] || 1) - 1; };
  const botoesPossuido = (i) => {
    let h = `<div class="mo-linha">`;
    if (i.slot && !i.na_mochila) h += `<button class="mo-btn verde" onclick="moAcao({acao:'por',item:'${i.item}',tipo:'${i.slot}',idx:${proxIdx(i.slot)}})">Pôr na mochila</button>`;
    if (i.na_mochila) h += `<span class="chip">Na mochila</span>`;
    if (i.sugerido) h += `<span class="chip latao">Sugerido</span>`;
    h += `</div>`;
    if (i.calibres) h += `<div class="mo-cal">${i.calibres.map(c => `<span class="chip ${c.serve ? "" : "cinza"}">${esc(c.nome)}</span>`).join("")}</div>`;
    if (i.municoes && i.municoes.length) h += `<div class="mo-mun"><select id="mun-${i.id}">${i.municoes.map(m =>
        `<option value="${m.id}" ${(m.atual || (!i.municoes.some(x => x.atual) && m === i.municoes.find(x => x.serve))) ? "selected" : ""}>${m.serve ? "✔ " : "✖ "}${esc(m.nome)}${m.atual ? " (atual)" : ""}</option>`).join("")}</select>
        <button class="mo-btn" onclick="moAcao({acao:'municao',arma:'${i.id}',municao:$('mun-${i.id}').value})">Usar munição</button></div>`;
    return h;
  };
  const sug = d.sugestao, nSug = sug.armas.length + sug.objetos.length;
  p.innerHTML = `
    <h3>Missões para montar a mochila</h3>
    <div class="filtros">${d.ativas.length ? d.ativas.map(m => `<button class="${m.escolhida ? "ativo" : ""}" onclick="moMissao('${m.id}')">${m.escolhida ? "☑" : "☐"} ${esc(m.titulo)}</button>`).join("")
      : `<span class="item-sub">Nenhum contrato ativo — aceite um contrato do Velho Earl. Sem missão, a sugestão vale para qualquer animal.</span>`}</div>
    <div class="mo-req">${d.requisitos.map(r => `<span class="chip latao">${esc(r)}</span>`).join("")}</div>
    <div class="mo-acoes"><button class="btn-papel verde" ${nSug ? "" : "disabled"} onclick="moMontar()">Montar mochila sugerida (${nSug} itens)</button>
      <span class="item-sub">${d.lida_ts ? "Mochila lida do jogo." : "Abra o jogo numa reserva para ler os espaços da mochila."} Verde = serve para as missões escolhidas.</span></div>
    <h3>Na mochila agora</h3>
    <div class="mo-slots">${vagas("Inventory.Weapon", "Armas")}${vagas("Inventory.Objects", "Objetos")}${vagas("Inventory.GPS", "GPS")}</div>
    <h3>Seus itens</h3>
    ${Object.entries(grupos).map(([g, its]) => {
      const sim = its.filter(x => x.serve), nao = its.filter(x => !x.serve);
      return `<h4 class="mo-grupo">${esc(g)} <small>${sim.length} de ${its.length} servem</small></h4>
        ${sim.length ? `<div class="mo-grade larga">${sim.map(i => cartao(i, botoesPossuido(i))).join("")}</div>` : `<p class="item-sub">Nenhum serve para as missões escolhidas.</p>`}
        ${nao.length ? `<details class="mo-nao"><summary>Ver os que não servem (${nao.length})</summary><div class="mo-grade larga">${nao.map(i => cartao(i, botoesPossuido(i))).join("")}</div></details>` : ""}`;
    }).join("")}`;
}
function moMissao(id) {
  const todas = mochilaDados.ativas.map(m => m.id);
  let sel = mochilaMissoes || todas.slice();
  sel = sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id];
  mochilaMissoes = sel.length === todas.length ? null : (sel.length ? sel : ["nenhuma"]);
  renderArmario();
}
async function moAcao(corpo) {
  const r = await post("/api/mochila", corpo);
  if (!r.ok) return alert(r.erro);
  setTimeout(renderArmario, 2500);
}
async function moMontar() {
  if (!confirm("Montar a mochila no jogo com os itens sugeridos? Os espaços serão trocados pelos itens verdes.")) return;
  moAcao({ acao: "montar", sugestao: mochilaDados.sugestao });
}

async function renderLoja() {
  const d = await (await fetch("/api/loja")).json();
  const det = d.deteccao || {};
  const med = (nome, v, dica) => `<div class="medidor"><div class="item-sub">${nome}</div><div class="v">${v == null ? "–" : Math.round(v * 100) + "%"}</div>
      <div class="b"><i style="width:${(v || 0) * 100}%"></i></div><div class="item-sub">${dica}</div></div>`;
  let html = `<h3>Como os animais te percebem agora</h3><div class="medidores">
      ${med("Visão", det.visual, "quanto menor, mais camuflado")}${med("Audição", det.som, "barulho da roupa e dos passos")}${med("Olfato", det.cheiro, "use spray e vento a favor")}</div>`;
  html += `<h3>Você está vestindo</h3>` + (d.vestidos.length ? `<div class="grade-itens">${d.vestidos.map(itemLoja).join("")}</div>` : `<p class="vazio">–</p>`);
  const partes = ["Todas", ...new Set(d.itens.map(i => i.parte))];
  html += `<h3>Catálogo (${d.itens.length} peças) · saldo $${fmt(d.creditos)}</h3><div class="filtros">${partes.map(p =>
      `<button class="${p === filtroLoja ? "ativo" : ""}" onclick="filtroLoja='${p}';renderLoja()">${esc(p)}</button>`).join("")}</div>`;
  const lista = d.itens.filter(i => filtroLoja === "Todas" || i.parte === filtroLoja);
  html += `<div class="grade-itens">${lista.map(itemLoja).join("")}</div>
    <p class="item-sub">Os números de camuflagem (0 a 100) vêm do próprio jogo: quanto maior, menos o animal te vê, ouve ou sente. A compra é feita na loja do jogo com seus créditos.</p>`;
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
  if (!confirm(`Comprar "${nome}" por $${fmt(preco)} na loja do jogo?`)) return;
  const r = await post("/api/comprar", { id });
  if (!r.ok) alert(r.erro); else setTimeout(renderLoja, 2500);
}

// ---------------------------------------------------------------- Diário de campo
let diario = null, diarioCat = "animais", diarioSel = null, diarioBusca = "";
const moedaFmt = (i) => i.preco == null ? "" : (i.moeda === "pontos de campo" ? `${fmt(i.preco)} pts de campo` : `$${fmt(i.preco)}`);
const chips = (l, cls = "") => (l || []).map(x => `<span class="chip ${cls}">${esc(x)}</span>`).join("") || `<span class="item-sub">–</span>`;
const quando = (ts) => ts ? new Date(ts * 1000).toLocaleDateString("pt-BR") : "";

function semFoto(i, cat, grande) {
  if (cat === "animais") return silhueta(i.grupo || "outro");
  const ic = { armas: "🎯", municao: "•", roupas: "🧥", itens: "🎒", caes: "🐕", guia: "📖" }[cat] || "?";
  return `<span class="ic-vazio${grande ? " g" : ""}">${ic}</span>`;
}
function fotoDiario(i, cat, grande) {
  if (!i.imagem) return semFoto(i, cat, grande);
  return `<img src="${i.imagem}" alt="" loading="lazy" onerror="this.outerHTML=this.dataset.sil" data-sil="${esc(semFoto(i, cat, grande))}">`;
}

async function renderEnciclopedia() {
  const d = await (await fetch("/api/enciclopedia")).json();
  if (!d.pronto) {
    $("painel-enciclopedia").innerHTML = `<div class="diario-vazio"><h3>Diário de campo</h3>
      <p>Os dados do diário (fotos, hábitos, calibres, armas, roupas, cães) são lidos do jogo uma única vez.</p>
      <p>Com o jogo aberto <b>dentro de uma reserva</b>, clique no botão abaixo. A leitura é feita aos poucos (uns 10 a 15 minutos,
      sem travar o jogo) e esta página se completa sozinha no fim. Se sair da reserva no meio, é só clicar de novo: continua de onde parou.</p>
      <button class="btn-papel verde" onclick="post('/api/exportar_dados',{}).then(()=>this.textContent='Lendo dados do jogo…')">Ler dados do jogo</button></div>`;
    setTimeout(() => { if (abaAtual === "enciclopedia") renderEnciclopedia(); }, 15000);
    return;
  }
  diario = d;
  desenharDiario();
}

function desenharDiario() {
  const cat = diario.categorias.find(c => c.id === diarioCat) || diario.categorias[0];
  const q = diarioBusca.trim().toLowerCase();
  const lista = cat.itens.filter(i => !q || (i.nome + " " + (i.sub || i.cabecalho || "") + " " + (i.calibre || "")).toLowerCase().includes(q));
  if (!diarioSel || !cat.itens.some(i => i.id === diarioSel)) diarioSel = (lista[0] || cat.itens[0] || {}).id;
  const grupos = {};
  lista.forEach(i => (grupos[i.cabecalho || i.sub || cat.nome] ||= []).push(i));
  const menu = Object.entries(grupos).map(([g, its]) => `<div class="dm-grupo">${esc(g)} <small>${its.length}</small></div>` + its.map(i => `
      <button class="dm-item ${i.id === diarioSel ? "sel" : ""}" data-id="${esc(i.id)}">
        <span class="dm-foto">${fotoDiario(i, cat.id)}</span>
        <span class="dm-nome">${esc(i.nome)}${i.tem ? ` <i class="dm-tem" title="Você tem">✔</i>` : ""}${i.abates ? ` <i class="dm-tem" title="Abatidos">${i.abates}</i>` : ""}</span>
      </button>`).join("")).join("") || `<p class="item-sub" style="padding:8px">Nada encontrado.</p>`;
  const it = cat.itens.find(i => i.id === diarioSel);
  $("painel-enciclopedia").innerHTML = `<div class="diario">
    <aside class="diario-menu">
      <div class="dm-cats">${diario.categorias.map(c => `<button data-cat="${c.id}" class="${c.id === cat.id ? "ativo" : ""}">${esc(c.nome)} <small>${c.itens.length}</small></button>`).join("")}</div>
      <input class="dm-busca" placeholder="Buscar…" value="${esc(diarioBusca)}">
      <div class="dm-lista">${menu}</div>
    </aside>
    <article class="diario-pagina">${it ? (cat.id === "animais" ? paginaAnimal(it) : paginaItem(it, cat)) : ""}</article>
  </div>`;
  const p = $("painel-enciclopedia");
  p.querySelectorAll(".dm-cats button").forEach(b => b.onclick = () => { diarioCat = b.dataset.cat; diarioSel = null; diarioBusca = ""; desenharDiario(); });
  p.querySelectorAll(".dm-item").forEach(b => b.onclick = () => { diarioSel = b.dataset.id; desenharDiario(); p.querySelector(".diario-pagina").scrollTop = 0; });
  const busca = p.querySelector(".dm-busca");
  busca.oninput = () => { diarioBusca = busca.value; const pos = busca.selectionStart; desenharDiario(); const n = $("painel-enciclopedia").querySelector(".dm-busca"); n.focus(); n.setSelectionRange(pos, pos); };
  const sel = p.querySelector(".dm-item.sel"); if (sel) sel.scrollIntoView({ block: "nearest" });
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
    <div class="dp-colunas">
      <div>
        ${secao(a.secoes_titulo || "Aparência e hábitos", paragrafos(a.secoes))}
        ${secao(a.habitat_titulo || "Habitat / bioma preferido", paragrafos(a.habitat))}
        ${secao("Calibres permitidos", chips(a.calibres))}
        ${a.proibidos.length ? secao("Calibres proibidos (não conta / penaliza)", chips(a.proibidos, "vermelho")) : ""}
        ${secao("Armas que servem", a.armas.length ? `<div class="dp-armas">${a.armas.map(w => `<span class="chip ${w.tem ? "" : "cinza"}" title="${w.tem ? "Você tem" : "Na loja"}">${w.tem ? "✔ " : ""}${esc(w.nome)} <small>${esc(w.calibre)}</small></span>`).join("")}</div>` : "")}
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
