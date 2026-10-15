# 1. Workflow: from clips in input/ to finished Shorts

`$PY` below means the kit's Python: `tools/.venv/Scripts/python.exe` on Windows, `tools/.venv/bin/python` on Mac.
Not the system `py` / `python`: they don't have the packages.

## Target: ~20 min of your work per clip, one checkpoint

| Step | Command | Machine time (CPU laptop) | Stop? |
| --- | --- | --- | --- |
| 1. Number the clips | `$PY tools/shorts.py list` | seconds | |
| 2. Audio, transcript, word times | `$PY tools/shorts.py asr` | ~3-6 min a clip (faster with an NVIDIA GPU) | |
| 3. Contact sheets, face boxes | `$PY tools/shorts.py look` | ~20 s a clip | |
| 4. Read each clip, write `work/shorts/NN/edit.json` | by hand (guide 02) | | |
| 5. Cut, audio, reframe, timeline | `$PY tools/shorts.py build` | ~1 min a clip | |
| 6. QA | `$PY tools/shorts.py qa` + `$PY tools/shorts.py stills N` | ~1 min a clip | |
| 7. 720p previews | `$PY tools/shorts.py preview` | ~2 min a Short | **Checkpoint: their notes** |
| 8. Apply notes, finals | `build` again if needed, then `$PY tools/shorts.py final` | ~2 min a Short | deliver |

- Run `asr` for all clips at once in the background, and start reading clip 1 as soon as its `transcript.txt` exists.
- If transcription is too slow on their laptop (over ~10 min a clip), set `"whisper_model": "large-v3-turbo"` in `channel.json` (much faster, slightly more spelling fixes needed). Say so in one line.
- Steps take clip numbers (`build 2 3`); no number = all clips.
- After a change in `video/src`, don't use `NOBUNDLE=1`. After only `build`, `NOBUNDLE=1` saves ~20 s per render command.

## The checkpoint

One message with all previews: per Short, the file path, its length, the hook
text, what was cut (one line, e.g. "cut: «Οκ wait» and the first attempt of
the sentence before it"), and anything you weren't sure of. Ask them to watch
and say what to change. Don't send previews one by one.

Batch their notes: apply all of them, check with stills, render once.

## QA before every preview (never skip)

1. `$PY tools/shorts.py qa`: every Short prints PASS (gaps, silence, loudness, frame count, face in frame, length).
2. Read every «stretched» line printed by `build` (guide 02). Each one is a possible hidden retake.
3. `$PY tools/shorts.py stills N` for every Short and **look at the image**:
   - frame 0: hook card readable, question card (if any) under the chin, not covering the mouth;
   - caption pages: under the chin, correct spelling, nothing in the red zones (platform buttons and text);
   - last frame: looking at the camera, not away or reaching for the phone.
4. Spot-check three caption pages against the audio (the words in the transcript at those times).

## New batch setup

Old clips can stay: `list` keeps existing numbers and adds new clips at the end.
If they want a clean slate, move `input/`, `work/shorts/` and `out/` into
`archive/<date>/` (ask first) and recreate the empty folders.
