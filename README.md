# Rugby Scoreboard

Placar digital para Rugby com suporte a Stream Deck.

## Gerar executável (distribuir sem instalar Python)

> O executável precisa ser compilado **no mesmo sistema operacional** onde vai rodar.
> Para `.exe` no Windows, execute os comandos abaixo no Windows.

```bash
pip install pyinstaller
python build.py
```

O arquivo gerado fica em `dist/Rugby Scoreboard` (Linux/Mac) ou `dist/Rugby Scoreboard.exe` (Windows).
Basta enviar esse único arquivo para o seu amigo — nenhuma instalação adicional é necessária.

**Observação Windows:** a biblioteca de hotkeys globais (`keyboard`) requer que o app seja executado
como **Administrador** para capturar teclas com a janela minimizada.

---

## Desenvolvimento — executar pelo Python

### Requisitos

```bash
pip install -r requirements.txt
```

### Executar

```bash
python scoreboard.py
```

## Pontuação Rugby

| Botão | Pontos |
|-------|--------|
| TRY   | +5     |
| CNV (Conversão) | +2 |
| PEN (Penal) | +3 |
| DRP (Drop Goal) | +3 |
| −1    | Desfaz último ponto |

## Integração com Stream Deck

### Layout do Stream Deck — 15 teclas (5×3)

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│  F1      │  F2      │  Space   │  F6      │  F7      │
│ Casa TRY │ Casa PEN │ START/   │ Visit PEN│ Visit TRY│
│  +5      │  +3      │  STOP    │  +3      │  +5      │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│  F3      │  F4      │  Ctrl+R  │  F8      │  F9      │
│ Casa CNV │ Casa DRP │  RESET   │ Visit DRP│ Visit CNV│
│  +2      │  +3      │  TEMPO   │  +3      │  +2      │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│  F5      │ Ctrl+Up  │  Ctrl+0  │ Ctrl+Down│  F10     │
│ Casa  −1 │ TEMPO UP │  RESET   │TEMPO DOWN│ Visit −1 │
│          │          │  PLACAR  │          │          │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

### Passos para configurar o Stream Deck

1. Abra o **Stream Deck software** → crie um perfil "Rugby"
2. Para cada tecla, adicione a ação **Hotkey** e configure o atalho correspondente
3. Na aba **Hotkeys / Stream Deck** do app, ative os hotkeys (requer `pip install keyboard`)
4. Pronto! Cada tecla física do Stream Deck atualiza o placar em tempo real

## Saída para OBS

Os seguintes arquivos são atualizados automaticamente na pasta `Output/`:

- `Home_Score.txt` — placar da equipe da casa
- `Away_Score.txt` — placar do visitante
- `Home_Name.txt` — nome da equipe da casa
- `Away_Name.txt` — nome do visitante
- `Half.txt` — tempo atual (1º Tempo, 2º Tempo, etc.)
- `Clock.txt` — relógio no formato MM:SS

No OBS: **Adicionar fonte → Texto → Ler de arquivo → selecione o .txt desejado**
