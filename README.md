# HS3 Companion – Cabana do Caçador

App companheiro para **Hunting Simulator 3** (PC, uso pessoal e offline).

- **mod/** – mod UE4SS (Lua) que lê o estado do jogo, registra marcações e abates e paga recompensas pelas funções oficiais do jogo.
- **bridge/** – `HS3Companion.exe` (Python, só biblioteca padrão): lê os arquivos do mod, gera e valida missões e serve o app em `http://localhost:8765`.
- **bridge/web/** – app web instalável (PWA).

O executável é gerado automaticamente pelo GitHub Actions a cada push na `main` e publicado em **Releases** como `HS3Companion.zip`.

## Canal mod ↔ ponte
| Arquivo | Quem escreve | Conteúdo |
|---|---|---|
| `state.json` | mod, a cada 1 s | moedas, reputação, mapa, posição, direção |
| `events.jsonl` | mod | `marcado`, `abate`, `abate_final`, `recompensa` |
| `cmd.txt` | ponte | `add_credits N ref`, `add_rep N ref` |

## Fase 1 – descobertas (21/11/2026)
- Mapa do Texas: `/HS3DefaultMaps/Terrain/Texas_a/Map/ZoomLevel1/T_Texas_a_MiniMap` (4096², exportável via render target + `ExportRenderTarget`). Mundo = 1.224.000 cm de lado, centrado em 0: `u = X/1224000 + 0.5`, `v = Y/1224000 + 0.5` (X → direita, Y → baixo).
- Névoa: `NavigationSaveData.FogOfWarLists[nível].FogArray` = 2048×2048 bits (1 bpp, ordem little-endian) nos primeiros 524.288 bytes; 1 = explorado.
- Pontos de interesse: `NavigationContentComponent.NavigationActorDataMap` (tipo → lista com Hash/Transform); estado em `NavigationSaveData.DiscoverStatusLists` (`Map.UI.POI.Discovered`).
- Animais vivos: `AnimalCharacter.EcoSimCreatureId` = id do binóculo; posição por `K2_GetActorLocation`.
- Pino rápido no jogo: `NavigationPlayerStateComponent:Server_AddQuickWaypoint(NavigationIconData:DA_QuickWaypoint_MapIconData, Transform)`.
