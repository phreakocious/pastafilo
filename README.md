# pastafilo

A [Strudel](https://strudel.cc) REPL that a coding agent can play. It is a minimal, full-screen live-coding page with a small REST API. An agent (Claude Code, Codex, or anything that can run `curl`) writes Strudel patterns and pushes them to the page you are listening to.

*Pasta filo* is phyllo dough: strudel dough, stretched paper-thin and layered.

pastafilo began as a fork of [strudel-claude](https://github.com/renatoworks/strudel-claude) by Renato Costa.

## What is Strudel?

Strudel is a JavaScript port of Tidal Cycles for algorithmic music composition. Write code, make music, in real time.

```javascript
// Drums
$: s("bd*4, [~ cp]*2, hh*8").bank("RolandTR909")

// Bass
$: note("<c2 eb2 f2 g2>").s("sawtooth").lpf(400)
```

## Quick start

**1. Start the server**
```bash
npm install
npm run dev
```

**2. Open http://localhost:3000 and click the page once.** Browsers keep audio suspended until a click or key press. Until then, pushed code shows in the editor but nothing sounds.

**3. Open your agent in the project folder** and ask:
```
"Teach me Strudel"          → tutorial
"Play me a techno set"      → dj-set
"Compose a synthwave track" → compose
"Let's make music together" → interactive
```

## Agents

- **Instructions** are in [AGENTS.md](AGENTS.md). `CLAUDE.md` imports it and maps its two generic phrases to Claude Code's tools.
- **Skills** are in `.agents/skills/`, in the SKILL.md format. `.claude/skills` is a symlink to the same folder. On Windows, git checks out a symlink as a plain file unless symlinks are on: turn on Developer Mode and run `git config --global core.symlinks true` before you clone, or Claude Code will not find the skills.
- Tested with Claude Code. Other agents that read `AGENTS.md` and `.agents/skills/` should work, but are untested.

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+Enter` | Play / evaluate code |
| `Cmd+.` | Stop |

## Recording audio

By hand:

1. **Start playback**: hit play or `Cmd+Enter`
2. **Click the red record button**: it pulses and shows the duration
3. **Click again to stop**: a preview toast appears
4. **Listen, then Download or Discard**

Recording is independent of playback: stop recording at any time without stopping the music.

From a script: `scripts/record.sh <seconds> [base_url]` stops, plays from the top, records in the open page, and prints the path of the WAV it saves in `output/`. `base_url` must point at a server started from this checkout, because the script waits for the file in its own `output/`.

## API

The page follows the server over Server-Sent Events, so it updates as soon as code is pushed or playback changes.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/code` | `GET` | Get current code and playing state |
| `/api/code` | `POST` | Push new code `{ "code": "..." }` |
| `/api/play` | `POST` | Start playback |
| `/api/stop` | `POST` | Stop playback |
| `/api/status` | `GET` | Get current state |
| `/api/record` | `POST` | Record `{ "seconds": n }` (up to 900) in the open page; 409 when no page is connected |
| `/api/recording` | `POST` | The page uploads a finished WAV here; it is saved to `output/` |
| `/api/events` | `GET` | SSE stream for real-time updates |

```bash
curl -X POST http://localhost:3000/api/code \
  -H "Content-Type: application/json" \
  -d '{"code": "$: s(\"bd*4, cp*2\").bank(\"RolandTR909\")"}'

curl -X POST http://localhost:3000/api/play
```

`/api/code` parses the body as JSON: a backslash sequence JSON does not define (`\s`, `\x`) returns a 500.

## Analyzing reference tracks

`scripts/analyze.py` measures tracks you want to learn from: bar grid, drum accent maps, swing, spectral balance, structure, and the bass line per 16th. The numbers give an agent something concrete to build a pattern from. It does not detect tempo: pass `--bpm` (default 130). Its docstring lists what it reads wrong.

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/analyze.py --selftest
.venv/bin/python scripts/analyze.py --bpm 128 references/*.aiff   # references/ is ignored by git
```

It needs ffmpeg on the `PATH`. On Intel Macs, use Python 3.10-3.13: librosa depends on llvmlite, and its last x86_64 macOS wheels cover only those versions.

## Project structure

```
.agents/skills/             # Agent skills (SKILL.md); .claude/skills links here
scripts/
├── record.sh               # Record the open page to output/
├── analyze.py              # Measure reference tracks
└── requirements.txt
src/
├── app/
│   ├── api/                # REST API for agents
│   │   ├── code/           # GET/POST code
│   │   ├── events/         # SSE stream
│   │   ├── play/           # POST play
│   │   ├── stop/           # POST stop
│   │   ├── status/         # GET status
│   │   ├── record/         # POST record (sent to the page)
│   │   ├── recording/      # POST the page's WAV
│   │   └── state.ts        # Shared state + event emitter
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Home page
│   └── globals.css         # Styles + CodeMirror theme
├── components/
│   └── strudel-editor.tsx  # Main editor
├── hooks/
│   ├── use-strudel.ts      # Strudel lifecycle + SSE sync
│   └── use-audio-recorder.ts # Audio recording to WAV
└── lib/
    ├── constants.ts        # Shared constants
    └── wav-encoder.ts      # Pure JS WAV encoder
tracks/                     # Example compositions
```

## Voice feedback (macOS only)

The skills can narrate with the macOS `say` command, when you turn voice on.

By default, macOS uses basic voices like Daniel or Samantha. The Siri voices sound much more natural:

1. Open **System Settings** → **Accessibility** → **Spoken Content**
2. Click the **ⓘ** (info icon) next to **System Voice**
3. In the voice dropdown, search for **"Siri"**
4. Download a Siri voice you like
5. **Set it as your System Voice**, so every `say` command uses it

Test it in Terminal:

```bash
say "Let's make some music"
```

## Skills

`strudel` (the syntax reference) and `api` (REPL control) load before any music is played. In Claude Code, every skill is also a slash command (`/tutorial`).

### tutorial: learn Strudel and music theory

```
"Teach me Strudel from the beginning"
"Explain how filters work"
"Show me how to make chord progressions"
"What's the difference between major and minor scales?"
```

### dj-set: live DJ sets

```
"Play me a 5-minute live techno set"
"Create a deep house journey"
"Do a chill ambient set with voice narration"
"Play an indefinite acid house set until I stop you"
```

### compose: full track compositions

```
"Compose a 3-minute synthwave track"
"Create a full UK garage song"
"Make a lo-fi hip hop beat"
```

### interactive: guided music creation

```
"Let's make music together"
"Help me create a beat"
"Guide me through making a song"
```

### visuals

Adds pianoroll, spiral and oscilloscope displays to any pattern.

## Learn more

- [Strudel docs](https://strudel.cc/learn)
- [Strudel on Codeberg](https://codeberg.org/uzu/strudel)
- [Tidal Cycles](https://tidalcycles.org)

## License

MIT. See [LICENSE](LICENSE).
