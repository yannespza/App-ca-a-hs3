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

const mapa = L.map("mapa", { crs: L.CRS.Simple, minZoom: -3, maxZoom: 2, zoomSnap: 0.25, attributionControl: false, zoomControl: false });
L.control.zoom({ position: "bottomright" }).addTo(mapa);
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
function recompensa(m) { return `$${fmt(m.creditos_pagos ?? m.creditos)} <small>+${fmt(m.reputacao)} rep.</small>`; }

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
      <span class="estado-pg ${m.status === "paga" ? "ok" : ""}">${m.status === "paga" ? "Pago" : (m.enviado ? "Pagando…" : "Concluído")}</span></div></div>`);
  const jogo = (d.contratos_jogo || []).map(c => `<div class="ativa do-jogo">
      <div class="at-titulo"><span><span class="selo-jogo">JOGO</span> ${esc(c.titulo)}</span>${c.rastreado ? `<span class="selo-rastreio">Rastreando</span>` : ""}</div>
      <div class="of-meta">${esc(c.vendedor)}${c.tempo_min != null ? ` · ⏱ ${c.tempo_min} min restantes` : ""}</div>
      ${c.objetivos.map(o => `<div class="obj-jogo ${o.feito ? "feito" : ""}"><span>${o.feito ? "✔" : "▸"} ${esc(o.texto)}</span><b>${o.progresso} / ${o.meta}</b></div>
        <div class="barra"><div style="width:${Math.min(100, 100 * o.progresso / o.meta)}%"></div></div>`).join("")}
    </div>`);
  const partes = lista.concat(fim);
  if (jogo.length) partes.push(`<div class="sep-jogo">Contratos do jogo</div>`, ...jogo);
  $("ativas").innerHTML = partes.join("") || `<div class="vazio">Aceite um contrato do Velho Earl.</div>`;
}

async function acao(tipo, id) {
  const r = await post("/api/missoes/" + tipo, { id });
  if (!r.ok && r.erro) return moAviso(r.erro, "erro");
  if (tipo === "aceitar") { moAviso("Contrato aceito. Ele está em Em andamento.", "ok"); document.querySelector('.segmentos [data-seg="ativas"]').click(); }
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
    if (r.erro) moAviso(r.erro, "erro");
    else if (!r.disponivel) moAviso(`Você já está na versão mais recente (v${r.atual}).`, "ok");
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
  const rep = d.reputacao_mapa_atual;
  $("p-rep").textContent = rep ? fmt(rep.valor) : "–";
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
  $("npc-apelido").textContent = npc.apelido;
  renderOfertas(d); renderAtivas(d); renderChat(d);
  $("ollama-status").textContent = d.ollama.ok ? `IA: ${d.ollama.modelo}` : `IA desligada: ${d.ollama.erro || "Ollama não encontrado"} (contratos simples continuam funcionando)`;

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
  $("ultimos").innerHTML = d.abates.length ? `<table class="tabela"><thead><tr><th>Animal</th><th>Genética</th><th>Distância</th><th>Arma</th><th>Reserva</th></tr></thead><tbody>` +
    d.abates.slice(0, 15).map(a => `<tr><td><b>${esc(a.especie_nome || a.grupo_nome)}</b>${a.sexo_nome && a.sexo_nome !== "?" ? ` <small>${esc(a.sexo_nome)}</small>` : ""}</td>
      <td>${pct(a.genetica)}</td><td>${metros(a.distancia_m)}</td><td>${esc((a.arma || "").replace(/^ID_/, "").replace(/_/g, " "))}</td><td>${esc(a.reserva ? nomeMapa(a.reserva) : "–")}</td></tr>`).join("") + `</tbody></table>`
    : `<p class="vazio">Nenhum abate ainda. Cada animal recolhido no jogo aparece aqui.</p>`;
}

atualizar();
setInterval(atualizar, 2000);
setInterval(() => { if (nivelAtual) carregarPois(); }, 60000);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");


// ------------------------------------------------------------------ abas: armário, loja, enciclopédia
let abaAtual = "mapa", filtroLoja = "Todas";
document.querySelectorAll(".segmentos button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".segmentos button").forEach(x => x.classList.toggle("ativo", x === b));
  document.querySelectorAll(".seg").forEach(s => s.classList.toggle("ativo", s.id === "seg-" + b.dataset.seg));
  if (b.dataset.seg === "chat") { const l = $("chat-log"); l.scrollTop = l.scrollHeight; }
});
document.querySelectorAll("#abas button").forEach(b => b.onclick = () => {
  abaAtual = b.dataset.aba;
  document.querySelectorAll("#abas button").forEach(x => x.classList.toggle("ativo", x === b));
  ["armario", "loja", "enciclopedia", "cacadas"].forEach(a => $("painel-" + a).classList.toggle("ativo", a === abaAtual));
  document.querySelector(".mapa-papel").classList.toggle("so-mapa", abaAtual === "mapa");
  if (abaAtual === "mapa") setTimeout(() => mapa.invalidateSize(), 50);
  atualizarAba();
});
$("f-voltar").onchange = (e) => post("/api/config", { chave: "voltar_ao_ultimo_local", valor: e.target.checked });
$("f-hud").onchange = (e) => post("/api/config", { chave: "contratos_no_jogo", valor: e.target.checked });
async function voltarAgora() { const r = await post("/api/voltar"); if (!r.ok) moAviso(r.erro, "erro"); }

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
const MO_TIPOS = [
  { tipo: "Inventory.Weapon", nome: "Armas", classe: "armas" },
  { tipo: "Inventory.Objects", nome: "Equipamentos", classe: "objetos" },
  { tipo: "Inventory.GPS", nome: "GPS", classe: "gps" },
];
let moAssinatura = "", moOcupadoAte = 0;
const moTxtIdade = (s) => s == null ? "" : s < 60 ? `há ${s} s` : `há ${Math.round(s / 60)} min`;
// recorta a parte transparente dos ícones do jogo (armas ocupam só uma faixa do quadrado)
const moRecortes = {};
function moRecortar(img) {
  const src = img.dataset.src;
  img.parentElement.classList.add("tem");
  if (moRecortes[src]) { if (img.src !== moRecortes[src]) img.src = moRecortes[src]; return; }
  try {
    const c = document.createElement("canvas"), w = img.naturalWidth, h = img.naturalHeight;
    if (!w || !h) return;
    c.width = w; c.height = h;
    const g = c.getContext("2d"); g.drawImage(img, 0, 0);
    const px = g.getImageData(0, 0, w, h).data;
    let x0 = w, y0 = h, x1 = -1, y1 = -1;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (px[(y * w + x) * 4 + 3] > 12) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    if (x1 < 0) return;
    const m = 3, cw = x1 - x0 + 1 + 2 * m, ch = y1 - y0 + 1 + 2 * m;
    const c2 = document.createElement("canvas"); c2.width = cw; c2.height = ch;
    c2.getContext("2d").drawImage(c, x0, y0, x1 - x0 + 1, y1 - y0 + 1, m, m, x1 - x0 + 1, y1 - y0 + 1);
    moRecortes[src] = c2.toDataURL();
    img.src = moRecortes[src];
  } catch { moRecortes[src] = src; }
}
const moFoto = (i, cls) => `<div class="mo-foto ${cls || ""}">${i && i.imagem ? `<img src="${moRecortes[i.imagem] || i.imagem}" data-src="${i.imagem}" alt="" onload="moRecortar(this)" onerror="this.remove()">` : ""}
  <span class="mo-foto-ini">${esc(((i && i.nome) || "?").trim()[0] || "?")}</span></div>`;
const moSelo = (i) => i.serve ? `<span class="mo-selo sim">✔ serve</span>` : i.serve === false ? `<span class="mo-selo nao">não serve</span>` : "";

async function renderArmario(forcar) {
  const p = $("painel-armario");
  if (!forcar && (document.querySelector(".mo-modal") || p.contains(document.activeElement) && document.activeElement.tagName === "SELECT")) return;
  const q = mochilaMissoes ? `?missoes=${encodeURIComponent(mochilaMissoes.join(","))}` : "";
  let d;
  try { d = await (await fetch("/api/mochila" + q)).json(); } catch { return; }
  const assin = JSON.stringify(d);
  if (!forcar && assin === moAssinatura && p.innerHTML) return;
  moAssinatura = assin;
  mochilaDados = d;
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
    : `<span class="mo-dica">Nenhum contrato ativo. Sem contrato, a sugestão vale para qualquer animal.</span>`;

  // espaços da mochila
  const porTipo = (t) => d.mochila.filter(m => m.tipo === t);
  const mudancas = {};
  plano.filter(x => x.acao === "por").forEach(x => mudancas[x.tipo + ":" + x.idx] = x);
  const secao = (T) => {
    const itens = porTipo(T.tipo), n = Math.max(d.slots[T.tipo] || 0, itens.length);
    const cel = [];
    for (let k = 0; k < n; k++) {
      const it = itens.find(x => x.idx === k);
      const mud = mudancas[T.tipo + ":" + k];
      const sug = mud ? `<div class="mo-sugere">Sugestão: <b>${esc(mud.nome)}</b></div>` : "";
      if (!it) {
        cel.push(`<div class="mo-slot vazio ${pode ? "clic" : ""}" ${pode ? `onclick="moEscolher('${T.tipo}',${k})"` : ""}>
          <div class="mo-mais">+</div><div class="mo-slot-nome">Espaço livre</div>${pode ? `<small>Clique para escolher</small>` : ""}${sug}</div>`);
        continue;
      }
      let mun = "";
      if (it.municoes) {
        const ruim = it.municoes.some(m => m.atual && !m.serve) || !it.municoes.some(m => m.atual);
        mun = it.municoes.length ? `<label class="mo-municao ${ruim ? "ruim" : ""}" onclick="event.stopPropagation()"><span>Munição</span>
            <select ${pode ? "" : "disabled"} onchange="moAcao({acao:'municao',arma:'${esc(it.id)}',municao:this.value})">
              ${it.municoes.some(m => m.atual) ? "" : `<option value="">— escolha —</option>`}
              ${it.municoes.map(m => `<option value="${esc(m.id)}" ${m.atual ? "selected" : ""}>${m.serve ? "✔" : "✖"} ${esc(m.nome)}</option>`).join("")}
            </select></label>` : `<div class="mo-aviso">Você não tem munição para esta arma</div>`;
      }
      cel.push(`<div class="mo-slot ${it.serve ? "serve" : it.serve === false ? "nao" : ""}">
          ${moFoto(it, T.classe === "armas" ? "larga" : "")}
          <div class="mo-slot-info"><div class="mo-slot-nome">${esc(it.nome)}</div>${moSelo(it)}
            ${it.motivo ? `<small class="mo-motivo">${esc(it.motivo)}</small>` : ""}${mun}${sug}</div>
          ${pode ? `<div class="mo-slot-botoes"><button onclick="moEscolher('${T.tipo}',${k})">Trocar</button>
            <button class="sec" onclick="moAcao({acao:'tirar',item:'${esc(it.item)}'})">Tirar</button></div>` : ""}
        </div>`);
    }
    return `<section class="mo-sec ${T.classe}"><header><h4>${T.nome}</h4><span>${itens.length}/${n}</span></header><div class="mo-grade">${cel.join("")}</div></section>`;
  };

  p.innerHTML = `<div class="mochila">
    <div class="mo-topo">
      <div><h2>Mochila</h2>${status}</div>
      ${botaoMontar}
    </div>
    <div class="mo-bloco">
      <div class="mo-rotulo">1 · Para quais contratos?</div>
      <div class="mo-contratos">${contratos}</div>
      ${d.requisitos.length ? `<div class="mo-precisa"><span>O que precisa:</span>${d.requisitos.map(r => `<b>${esc(r)}</b>`).join("")}</div>` : ""}
    </div>
    <div class="mo-bloco">
      <div class="mo-rotulo">2 · Sua mochila no jogo <span class="mo-dica">verde = serve para os contratos · clique em Trocar ou num espaço livre para escolher o item</span></div>
      ${lida ? `<div class="mo-tabuleiro">${secao(MO_TIPOS[0])}${secao(MO_TIPOS[1])}${secao(MO_TIPOS[2])}</div>`
             : `<div class="mo-vazio-grande"><b>${d.em_reserva ? "Lendo a mochila…" : "Entre numa reserva no jogo"}</b><span>Os espaços aparecem aqui assim que o jogo responder.</span></div>`}
    </div>
  </div>`;
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
  const servem = lista.filter(i => i.serve), outros = lista.filter(i => !i.serve);
  moModal(`<header class="mo-jan-topo"><div><h3>Escolher ${T.classe === "armas" ? "arma" : T.classe === "gps" ? "GPS" : "equipamento"}</h3>
      <small>${T.nome} · espaço ${idx + 1}${atual ? ` · hoje: ${esc(atual.nome)}` : ""}</small></div>
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

function moConfirmarMontar() {
  const plano = mochilaDados.plano || [];
  const tipoNome = (t) => (MO_TIPOS.find(x => x.tipo === t) || {}).nome || t;
  const linhas = plano.map(x => x.acao === "por"
    ? `<li><span class="mo-li-onde">${tipoNome(x.tipo)} · espaço ${x.idx + 1}</span>${x.sai ? `<s>${esc(x.sai)}</s> → ` : ""}<b>${esc(x.nome)}</b></li>`
    : `<li><span class="mo-li-onde">Munição · ${esc(x.arma_nome)}</span><b>${esc(x.nome)}</b></li>`).join("");
  moModal(`<header class="mo-jan-topo"><div><h3>Montar mochila sugerida</h3><small>O que vai mudar no jogo</small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo"><ul class="mo-lista-plano">${linhas}</ul>
      <p class="mo-dica">As trocas são feitas uma por segundo para o jogo não travar. Leva uns ${plano.length + 2} segundos.</p></div>
    <footer class="mo-jan-rodape"><button class="sec" onclick="moFecharModal()">Cancelar</button>
      <button class="ok" onclick="moFecharModal();moAcao({acao:'montar',missoes:mochilaMissoes||[]})">Montar agora</button></footer>`);
}

async function renderLoja() {
  const d = await (await fetch("/api/loja")).json();
  const det = d.deteccao || {};
  const med = (nome, v, dica) => `<div class="medidor"><div class="item-sub">${nome}</div><div class="v">${v == null ? "–" : Math.round(v * 100) + "%"}</div>
      <div class="b"><i style="width:${(v || 0) * 100}%"></i></div><div class="item-sub">${dica}</div></div>`;
  let html = `<header class="pag-topo"><h2>Roupas e camuflagem</h2><p>O quanto os animais te veem, ouvem e sentem com a roupa de agora, e o que dá para comprar.</p></header>
    <h3>Como os animais te percebem agora</h3><div class="medidores">
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
  if (!r.ok) moAviso(r.erro, "erro"); else { moAviso("Compra enviada ao jogo.", "ok"); setTimeout(renderLoja, 2500); }
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
