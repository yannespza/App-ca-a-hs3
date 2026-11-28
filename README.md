# Painel do Caçador HS3 – app companheiro do Hunting Simulator 3

Uso pessoal e offline (PC, Steam). Três partes:

| Pasta | O que é |
|---|---|
| `mod/HS3Discovery/` | Mod UE4SS (Lua) que roda dentro do jogo: lê o estado, registra marcações e abates, paga recompensas e executa comandos do app. |
| `bridge/` | `HS3Companion.exe` (Python, só biblioteca padrão + certifi): lê os arquivos do mod, gera e confere os contratos e serve o app em `http://localhost:8765`. |
| `bridge/web/` | O app (HTML/CSS/JS, Leaflet para o mapa). |
| `tools/dev-mod/` | Scripts de desenvolvimento (não vão no pacote): `sondas/` só leem o jogo para descobrir dados, `testes/` conferem uma função, `utilitarios/` rodam tarefas avulsas. Copie para `HS3Discovery\dev\` e rode com `script <arquivo>.lua` em `cmd.txt`. |

O executável é gerado pelo GitHub Actions a cada push na `main` e publicado em **Releases** (`HS3Companion.zip`).
O botão "Procurar atualização" do app baixa a versão nova, troca o `.exe` e copia o mod para a pasta do jogo.

## Arquivos do mod (pasta `HS3Discovery`)
| Arquivo | Quem escreve | Conteúdo |
|---|---|---|
| `Scripts\main.lua` | — | carregado ao abrir o jogo (estado a cada 1 s, eventos, comandos) |
| `Scripts\mochila.lua`, `contratos.lua`, `hud.lua`, `exportar.lua`, `nitido.lua`, `licencas.lua`, `municao.lua`, `mortos.lua`, `trofeus.lua` | — | recarregados a cada uso (dá para corrigir com o jogo aberto) |
| `state.json` | mod, 1 s | créditos, reputação, mapa, posição, pino |
| `events.jsonl` | mod | `marcado`, `peso_marcado`, `abate`, `recompensa`, `compra`, `mochila`, `empalhado`, `foto_trofeu`, `tecla` |
| `alvejados.json`, `mortos.json` | mod | animais com tiro seu (feridos/mortos) e mortos que o jogo marca no mapa |
| `animais.json`, `equipamento.json`, `mochila.json`, `armas.json`, `contratos_jogo.json` | mod | animais vivos, inventário/roupa, mochila, munição e acessórios das armas da mochila, contratos do jogo |
| `mapa_*.png/json`, `pois_*.json`, `nevoa_*.bin`, `calibres.json`, `catalogo_v2.json`, `jogo_dados.json`, `img\` | mod | mapa, pontos, névoa, tabela de calibres, loja, diário de campo e imagens |
| `cmd.txt` | app | comandos (`add_credits`, `add_rep`, `pin`, `teleport`, `comprar`, `mochila …`, `exportar_dados`, `nitido`) |
| `hud.txt` | app | contratos do app para a caixa de objetivos do jogo |

Descobertas técnicas e o que já fechou o jogo: documento do projeto `descobertas-tecnicas-hs3.md`.
