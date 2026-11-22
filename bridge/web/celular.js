// ---------------------------------------------------------------- Usar no celular (QR code no app do PC)
async function abrirCelular() {
  let c;
  try { c = await (await fetch("/api/celular")).json(); } catch { return moAviso("O app não respondeu.", "erro"); }
  if (c.erro) return moAviso("Isso só aparece no app do PC.", "erro");
  let qr = "";
  if (c.ligado && c.url_qr && typeof qrcode === "function") {
    const q = qrcode(0, "M");
    q.addData(c.url_qr);
    q.make();
    qr = q.createSvgTag({ cellSize: 6, margin: 3, scalable: true });
  }
  let qrApk = "";
  if (typeof qrcode === "function") {
    const q2 = qrcode(0, "M");
    q2.addData("https://github.com/yannespza/App-ca-a-hs3/releases/latest/download/HS3Companion.apk");
    q2.make();
    qrApk = q2.createSvgTag({ cellSize: 4, margin: 3, scalable: true });
  }
  moModal(`<header class="mo-jan-topo"><div><h3>Usar no celular ${ajuda("celular")}</h3><small>O celular vira uma segunda tela do app, pela rede Wi-Fi de casa</small></div>
      <button class="mo-x" onclick="moFecharModal()">✕</button></header>
    <div class="mo-jan-corpo cel">
      ${!c.ligado ? `<p>O acesso pelo celular está desligado.</p><button class="kit-btn" onclick="celLigar(true)">Ligar o acesso pelo celular</button>`
      : !c.ip ? `<p class="inst-aviso">Não achei este PC na rede. Confira se ele está conectado ao Wi-Fi ou ao cabo do roteador.</p>`
      : `<div class="cel-grade">
          <div class="cel-qr">${qr}</div>
          <ol class="cel-passos">
            <li>Deixe o celular no <b>mesmo Wi-Fi</b> deste PC.</li>
            <li>Abra a <b>câmera</b> do celular e aponte para o QR code. Toque no link que aparecer.</li>
            <li>Na primeira vez, o Windows pode perguntar se o HS3Companion pode usar a rede: clique em <b>Permitir acesso</b>.
              Se não aparecer e o celular não abrir, veja a dica abaixo.</li>
            <li><b>iPhone:</b> no Safari, botão Compartilhar → <b>“Adicionar à Tela de Início”</b>. Vira um ícone que abre em tela cheia.</li>
          </ol>
        </div>
        <div class="cel-grade cel-apk">
          <div class="cel-qr">${qrApk}</div>
          <div><b>Android: instale o app</b>
            <ol class="cel-passos">
              <li>Aponte a câmera para este QR para baixar o <b>HS3Companion.apk</b>.</li>
              <li>Abra o arquivo baixado. Se o Android pedir, permita <b>“instalar apps desconhecidos”</b> para o navegador.</li>
              <li>Abra o app <b>HS3 Companion</b>: ele procura este PC sozinho. Digite o PIN <b class="cel-pin">${esc(c.pin)}</b> uma vez.</li>
            </ol></div>
        </div>
        <p>Sem câmera? Digite no navegador do celular <code>${esc(c.endereco)}</code> e o PIN <b class="cel-pin">${esc(c.pin)}</b>.</p>
        ${c.outros && c.outros.length ? `<p class="mo-dica">Se não abrir, este PC também atende em: ${c.outros.map(x => `<code>${esc(x)}</code>`).join(" ")} (use o que começa igual ao endereço do seu celular no Wi-Fi).</p>` : ""}
        <p class="mo-dica">O PIN impede que outra pessoa na mesma rede mexa no seu jogo. Se quiser trocar, gere um novo: os aparelhos já conectados precisam ler o QR de novo.</p>
        <p class="mo-dica">Não abriu? No Windows, procure “Permitir um aplicativo pelo Firewall do Windows”, clique em Alterar configurações e marque o HS3Companion em “Particular” (e em “Público”, se a sua rede estiver como pública).</p>
        <div class="cel-botoes"><button class="kit-btn sec" onclick="celNovoPin()">Gerar novo PIN</button>
          <button class="kit-btn sec" onclick="celLigar(false)">Desligar o acesso pelo celular</button></div>`}
    </div>`);
}
async function celNovoPin() {
  if (!confirm("Gerar um PIN novo? O celular vai precisar ler o QR code de novo.")) return;
  await post("/api/celular", { acao: "novo_pin" });
  abrirCelular();
}
async function celLigar(ligado) {
  await post("/api/celular", { ligado });
  moFecharModal();
  moAviso(ligado ? "Ligado. Feche e abra o HS3Companion uma vez para valer." : "Desligado: o celular não entra mais.", "ok");
}

// dentro do app Android: botão para procurar outro PC
if (window.HS3 && typeof window.HS3.esquecer === "function") document.body.classList.add("apk");
function trocarPc() { if (confirm("Procurar outro PC na rede?")) window.HS3.esquecer(); }
