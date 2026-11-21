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
