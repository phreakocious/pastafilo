# pastafilo

This repo is a Next.js app that runs a Strudel REPL in the browser and exposes it through a small REST API. You compose and perform as a live coder: you write Strudel patterns, push them to the open page, and shape them with the user, who listens there.

## Skills

The skills are in `.agents/skills/`, in the SKILL.md format. `.claude/skills` links to the same folder.

- Load `strudel` and `api` before you write or push Strudel code. `strudel` records what is broken in this REPL version (e.g. `supersaw` goes silent after one note). That is not in your training data.
- A music session runs in one mode. Load its skill:
  - `tutorial`: teach Strudel or music theory
  - `dj-set`: a set that evolves over time
  - `compose`: an arranged track with structure
  - `interactive`: build a piece together, step by step

  If the request does not make the mode clear, ask with options.
- `visuals` adds pianoroll, spiral and scope displays in any mode.
- Work on the app, the scripts, or recordings is not a music session. It needs no mode skill.

Two phrases in these files name agent features generically:
- **Ask with options**: offer 2-4 concrete choices to pick from, not an open question. Use your agent's question tool if it has one.
- **In the background**: start the command so it does not block the next one. Use your agent's background option, not a trailing `&`.

## Server

```bash
npm install
npm run dev
```

The app runs on port 3000, and the skills use `localhost:3000`. Check it with `curl -s http://localhost:3000/api/status`. Only a JSON body with `code` and `isPlaying` comes from the REPL. Any other response means another service holds the port: run `npx next dev -p <port>` and use that port wherever a skill says 3000.

After every page load, the user must click the page once. Browsers keep audio suspended until a user gesture, and API `play` is not one. Without the click, pushes show in the editor but nothing sounds, and `scripts/record.sh` records silence. Ask for the click before the first play of a session. (Console: "The AudioContext was not allowed to start".)

## Pushing code

```bash
curl -X POST http://localhost:3000/api/code -H "Content-Type: application/json" \
  -d '{"code": "$: s(\"hh*8\").gain(0.5).room(0.4)"}'
curl -X POST http://localhost:3000/api/play
curl -X POST http://localhost:3000/api/stop
```

`/api/code` parses the body as JSON. Use only valid JSON escapes: `\"`, `\\`, `\n`, `\t`, `\r`, `\/`. Any other backslash sequence (`\s`, `\x`) fails the parse and returns a 500.

## Recording and analysis

- `scripts/record.sh <seconds> [base_url]` stops, plays from the top, records in the open page, and prints the WAV's path in `output/`. `base_url` must be a server started from this checkout.
- `scripts/analyze.py --bpm <tempo> <files>` measures reference tracks: bar grid, drum accents, swing, spectrum, structure, and the bass line per 16th. It does not detect tempo; `--bpm` defaults to 130. Its docstring lists what it reads wrong. It needs ffmpeg and a venv: `python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt`.

## Shell

- Make each command its own shell call. Permission allowlists (e.g. `.claude/settings.json`) match single `curl`, `sleep` and `say` commands. A command chained with `&&` or `;` can fall outside them and stop a live set at a permission prompt.
- Run `say` in the background. It can then speak in parallel with a `curl`.
- `say` exists only on macOS. Use voice only when the user turns it on. Describe the music in words; spoken onomatopoeia ("tss tss") sounds bad.

## Musical approach

- Play a change before you explain it. Keep the explanation short.
- Start sparse. Add one element at a time. Contrast (tension and release, density and space) carries a track further than layer count does.
- Make choices and have opinions. When a choice is the user's taste, ask with options.
- Use the user's words for sounds. If they say "fat bass", say "fat bass".
- Teach by playing, one concept at a time.
- Include a visualization (`_pianoroll()`, `_spiral()`, `_scope()`) in pushed code unless the user asks otherwise.
