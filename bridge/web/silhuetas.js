// Silhuetas simples por grupo de animal (viewBox 0 0 100 70), estilo placa de caça.
const SILHUETAS = {
  cervo: "M70 6 l3 9 5-8 -2 10 6-6 -3 11 -6 6 4 4 8 3 0 4 -10 0 -4 3 -2 12 3 22 -4 0 -4 -20 -6 -8 -24 0 -6 8 -3 20 -4 0 1 -22 -6 -8 -3 -14 6 -8 30 -2 8 -8 -1 -8 -6 -6 -1 -10 5 7 0 -12 4 9 z",
  alce: "M66 4 l-4 8 6 -2 -2 8 7 -4 -1 8 8 -6 -3 10 -6 6 3 3 9 2 0 5 -10 1 -4 4 -2 12 3 20 -4 0 -4 -18 -8 -8 -22 0 -6 8 -3 18 -4 0 1 -20 -6 -8 -3 -14 7 -7 30 -3 7 -8 -2 -8 -8 -4 -1 -12 6 6 1 -10 z",
  porco: "M12 30 c4 -12 20 -16 36 -15 c10 0 22 2 30 8 l8 -3 -1 6 6 4 8 2 -1 6 -10 2 -4 4 -2 8 2 14 -5 0 -3 -12 -8 -4 -24 0 -6 5 -2 11 -5 0 0 -13 -6 -5 -4 -6 -6 3 -2 -4 4 -4 z",
  pato: "M14 38 c6 -10 22 -12 34 -10 c4 -10 14 -16 24 -12 c6 3 8 9 6 13 l12 2 -12 4 c-2 2 -5 3 -8 3 c2 10 -6 20 -22 22 c-14 2 -30 -4 -36 -12 l-8 -4 z",
  peru: "M20 50 c-8 -10 -6 -28 8 -36 c10 -6 22 -4 28 6 c4 -10 12 -14 18 -10 l6 -8 0 10 c2 6 -2 10 -6 12 l2 14 c0 12 -10 20 -24 20 l-2 10 -4 0 0 -10 -6 0 -2 10 -4 0 2 -12 c-6 -2 -12 -4 -16 -6 z",
  coiote: "M8 30 c8 -2 14 2 18 4 c10 -6 30 -6 42 -4 l10 -12 2 6 4 -6 2 10 8 6 -2 4 -10 0 -4 6 -2 10 2 14 -4 0 -3 -14 -4 -4 -22 0 -6 6 -2 12 -4 0 0 -14 -6 -6 c-10 0 -20 -4 -22 -12 z",
  coelho: "M30 54 c-10 -2 -16 -14 -8 -24 c8 -8 22 -8 30 -2 l6 -22 c2 -4 6 -4 6 0 l-2 20 6 -18 c2 -4 6 -2 5 2 l-6 22 c6 4 8 12 2 16 l-2 8 4 4 -24 0 0 -6 z",
  outro: "M50 8 c18 0 32 12 32 28 s-14 28 -32 28 -32 -12 -32 -28 14 -28 32 -28 z m0 10 c-10 0 -18 8 -18 18 s8 18 18 18 18 -8 18 -18 -8 -18 -18 -18 z",
};
const SIL_GRUPO = { cervo: "cervo", alce: "alce", antilocapra: "cervo", carneiro: "cervo", bisao: "porco", porco: "porco",
  pato: "pato", ganso: "pato", peru: "peru", faisao: "peru", codorna: "pato", pomba: "pato",
  coiote: "coiote", lobo: "coiote", raposa: "coiote", puma: "coiote", felino: "coiote", urso: "porco", coelho: "coelho", antilope: "cervo", roedor: "coelho" };

function silhueta(grupo) {
  const d = SILHUETAS[SIL_GRUPO[grupo] || grupo] || SILHUETAS.outro;
  return `<svg viewBox="0 0 100 70" xmlns="http://www.w3.org/2000/svg"><path d="${d}"/></svg>`;
}
document.querySelectorAll("[data-sil]").forEach(el => el.innerHTML = silhueta(el.dataset.sil));
