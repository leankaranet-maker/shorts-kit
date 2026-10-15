# Shorts kit: vertical phone clips → finished Shorts (Remotion)

You are helping someone who has **never used Claude Code or a terminal**. Talk
to them in the language they write in, in plain words, no jargon. Before any
install or anything that takes over a minute, say in one line what it is and why.
Never ask them to type commands: you run them.

## First session (or if `tools/.venv` or `video/node_modules` is missing)

Follow [SETUP.md](SETUP.md) from the top. Don't start editing until
`tools/doctor.py` prints **ALL GOOD** and `channel.json` exists.

## Every session

1. Read every file in `guides/`, in order: `README.md`, then 01 to 06. They are
   the editing rules and the pipeline. Follow them without re-asking what they answer.
   `06-house-rules.md` holds this channel's own corrections and overrides 01-05.
2. Read `channel.json` (their channel: language, retake cue word, CTA texts, spelling fixes).
3. If the folder is a git repo, run `git pull --ff-only` quietly first: the kit gets
   improvements from the person who made it. If it refuses because of local changes,
   `git stash`, `git pull --ff-only`, `git stash pop`, and tell them in one line
   what came in. Never discard their changes.

## Commands (Windows)

- Python: `tools/.venv/Scripts/python.exe` (Mac: `tools/.venv/bin/python`)
- Pipeline: `tools/.venv/Scripts/python.exe tools/shorts.py STEP [N ...]` (run it without arguments for the step list)
- Environment check: `tools/.venv/Scripts/python.exe tools/doctor.py`
- Always write paths with **forward slashes**: commands run in Git Bash, where `\` is an escape character.
- Never use the system `python` / `py` for the pipeline: only the kit's venv has the packages.
- Long steps (`asr`, `build`, `preview`, `final`): run them in the background and
  do the next thing meanwhile (read transcripts, write edit.json for the next clip).

## Folders

| Folder | What | Who touches it |
| --- | --- | --- |
| `input/` | the original clips from the iPhone | they copy clips in; **never delete or modify** |
| `work/shorts/NN/` | everything per clip (audio, transcript, `edit.json`, stills) | you |
| `out/` | previews and finished Shorts | you write, they watch and upload |
| `guides/` | the editing rules | you add their corrections to `06-house-rules.md` |
| `channel.json` | their channel settings | you, from their answers |

## When they correct you

They win. Apply the change, then **add the rule to `guides/06-house-rules.md`
(or `channel.json` for spellings, names, CTA texts) in the same session**, with
the date, so the next batch starts from it. Don't edit guides 01-05 (they come
from upstream and would conflict on the next update). Don't commit or push
anything unless they ask.

## Showing them results

- Previews and finals are in `out/`. Give the full path, and open it for them:
  `explorer.exe "$(cygpath -w out/preview-01-slug.mp4)"` (Mac: `open out/preview-01-slug.mp4`).
- If they say a preview is wrong, ask what second it is and what they'd want instead,
  only if it isn't obvious from what they said.
