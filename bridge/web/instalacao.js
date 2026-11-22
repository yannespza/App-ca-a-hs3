// ---------------------------------------------------------------- Instalação e ajustes
// Primeira vez num PC: acha o jogo, instala o UE4SS e o mod, e guarda a pasta. Também: jogo novo do zero.
let inst = null, instPasta = "";

async function verificarInstalacao() {
  try { inst = await (await fetch("/api/instalacao")).json(); } catch { return; }
  if (!inst.pronto && !sessionStorage.getItem("hs3_inst_pulou")) abrirInstalacao();
}

async function abrirInstalacao() {
  try { inst = await (await fetch("/api/instalacao")).json(); } catch { return moAviso("O app não respondeu.", "erro"); }
  instPasta = instPasta || inst.raiz || "";
  desenharInstalacao();
}

function desenharInstalacao() {
  const s = inst || {};
  const passo = (ok, n, titulo, corpo) => `<div class="inst-passo ${ok ? "ok" : ""}"><span class="inst-marca">${ok ? "✔" : n}</span><div><h4>${titulo}</h4>${corpo}</div></div>`;
  const jogo = passo(s.jogo, 1, "Pasta do jogo",
    `<p>${s.jogo ? (s.achado_sozinho ? "Achei o jogo sozinho:" : "Jogo encontrado em:") : "Não achei o Hunting Simulator 3. Clique em <b>Procurar…</b> e escolha a pasta <code>HS3</code> dentro de <code>steamapps\\common</code> (na Steam: botão direito no jogo › Gerenciar › Ver arquivos locais)."}</p>
     <div class="inst-caminho"><input id="inst-pasta" value="${esc(instPasta)}" placeholder="Ex.: D:\\SteamLibrary\\steamapps\\common\\HS3">
       <button class="kit-btn sec" onclick="instProcurar()">Procurar…</button><button class="kit-btn sec" onclick="instConferir()">Conferir</button></div>`);
  const mod = passo(s.mod && s.ue4ss, 2, "Mod no jogo",
    `<p>O app precisa do <b>UE4SS</b> (carregador de mods) e do mod <b>HS3Discovery</b> dentro do jogo. Os dois vêm dentro deste programa.
      ${s.ue4ss ? "UE4SS: instalado ✔" : "UE4SS: falta"} · ${s.mod ? (s.atualizado ? "mod: instalado e atualizado ✔" : "mod: instalado, mas é de outra versão") : "mod: falta"}</p>
     ${s.jogo_aberto ? `<p class="inst-aviso">Feche o jogo para instalar.</p>` : ""}
     <button class="kit-btn" ${s.jogo && !s.jogo_aberto ? "" : "disabled"} onclick="instInstalar()">${s.mod ? "Reinstalar / atualizar o mod" : "Instalar no jogo"}</button>`);
  const usar = passo(s.pronto, 3, "Pronto",
    s.pronto ? `<p>Tudo certo. Abra o jogo pela Steam e entre numa reserva: o app conecta sozinho. Na primeira vez, abra o <b>Diário</b> e clique em “Ler dados do jogo”.</p>
                <p>Save do jogo: ${s.save ? `<code>${esc(s.save)}</code> (o app não mexe nele)` : "não encontrado ainda (aparece depois de jogar a primeira vez)"}</p>`
             : `<p>Depois de instalar, o app guarda a pasta e não pergunta mais.</p>`);
  const zero = `<div class="inst-passo"><span class="inst-marca">↺</span><div><h4>Começar um jogo novo do zero</h4>
      <p>Use quando apagar o save ou começar outra carreira no jogo. O app guarda uma cópia do histórico (contratos, abates, patente)
      e recomeça limpo. O jogo, o mod e o Diário não são apagados.</p>
      <button class="kit-btn sec" onclick="instZerar()">Começar do zero no app</button></div></div>`;
  moModal(`<header class="mo-jan-topo"><div><h3>Instalação e ajustes</h3><small>HS3 Companion ${esc((ultimoEstado || {}).versao || "")} · as atualizações chegam pelo botão “Procurar atualização”</small></div>
      <button class="mo-x" onclick="instFechar()">✕</button></header>
    <div class="mo-jan-corpo inst">${jogo}${mod}${usar}${zero}</div>
    <footer class="mo-jan-rodape">${s.pronto ? `<button class="ok" onclick="instFechar()">Fechar</button>` : `<button class="sec" onclick="instFechar()">Fazer isso depois</button>`}</footer>`);
}
function instFechar() { if (!inst || !inst.pronto) sessionStorage.setItem("hs3_inst_pulou", "1"); moFecharModal(); }

async function instProcurar() {
  moAviso("Escolha a pasta na janela do Windows (pode estar atrás deste app)…");
  const r = await post("/api/instalacao", { acao: "procurar" });
  if (!r.ok) return moAviso(r.erro, "erro");
  instPasta = r.pasta; inst = r.situacao; desenharInstalacao();
}
async function instConferir() {
  instPasta = $("inst-pasta").value.trim();
  const r = await post("/api/instalacao", { acao: "usar", pasta: instPasta });
  if (r.ok) { inst = r.situacao; moAviso("Pasta salva.", "ok"); return desenharInstalacao(); }
  try { inst = await (await fetch("/api/instalacao?pasta=" + encodeURIComponent(instPasta))).json(); } catch {}
  moAviso(r.erro, "erro");
  desenharInstalacao();
}
async function instInstalar() {
  instPasta = ($("inst-pasta") || {}).value?.trim() || instPasta;
  moAviso("Instalando…");
  const r = await post("/api/instalacao", { acao: "instalar", pasta: instPasta });
  if (!r.ok) return moAviso(r.erro, "erro");
  inst = r.situacao;
  moAviso("Instalado! Abra o jogo pela Steam.", "ok");
  desenharInstalacao();
}
async function instZerar() {
  if (!confirm("Começar do zero no app? Contratos, abates e patente voltam ao início (uma cópia fica guardada na pasta do programa).")) return;
  const r = await post("/api/instalacao", { acao: "zerar" });
  if (!r.ok) return moAviso(r.erro || "Não deu certo.", "erro");
  moFecharModal();
  document.querySelector(".jogo-novo")?.remove();
  moAviso(`Pronto: app zerado. Cópia guardada em ${r.copia}.`, "ok");
  atualizar();
}

// aviso quando o jogo parece ter começado do zero (reputação despencou)
function avisoJogoNovo(sim) {
  const el = document.querySelector(".jogo-novo");
  if (!sim || sessionStorage.getItem("hs3_jogo_novo_nao")) { el?.remove(); return; }
  if (el) return;
  const d = document.createElement("div");
  d.className = "jogo-novo";
  d.innerHTML = `<span>Parece que você começou um <b>jogo novo</b>. Quer zerar os contratos e a patente do app também?</span>
    <button class="kit-btn" onclick="instZerar()">Zerar o app</button>
    <button class="kit-btn sec" onclick="sessionStorage.setItem('hs3_jogo_novo_nao','1');this.parentElement.remove()">Não</button>`;
  document.body.appendChild(d);
}

verificarInstalacao();
