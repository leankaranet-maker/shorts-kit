# Shorts kit

Turns vertical iPhone clips into finished Shorts / Reels / TikToks: retakes and
pauses cut, a fixed vertical frame with gentle zoom changes, a hook card,
word-by-word captions under the chin, a follower-question card, −14 LUFS audio.
Claude Code does the editing; you watch the previews and say what to change.

Works on Windows and Mac.

## Setup (once, about 30 minutes, mostly waiting)

1. **Claude:** install the Claude desktop app from claude.ai/download and sign in.
   Claude Code needs a Pro or Max plan.
2. **Git for Windows:** install it from git-scm.com, clicking Next through every
   screen. Claude Code on Windows needs it.
3. **This folder:** put it at `C:\shorts`. Not on the Desktop, not in Documents
   or OneDrive.
   - Easiest: create an empty folder `C:\shorts` and let Claude download the kit into it (step 5).
   - Or download the zip from https://github.com/leankaranet-maker/shorts-kit (green Code button → Download ZIP) and unzip it there.
4. In the Claude app, open the **Code** tab, choose the folder `C:\shorts`, and
   set the permission mode to **Accept edits** so it doesn't ask about every file.
5. Paste this and press Enter:

   > Clone https://github.com/leankaranet-maker/shorts-kit into this folder (the folder itself, not a subfolder), then read CLAUDE.md and SETUP.md and follow them to set up editing my Shorts. I've never used this before, so before each install tell me in one line what it is.

   (If you unzipped it yourself, leave out the first part, up to "then".)

Claude installs Python, Node.js and ffmpeg, downloads the models (~6 GB), runs
a check, and asks you five short questions about your channel.

## Every time after that

1. Copy the clips from the iPhone into `C:\shorts\input`. Use a USB cable with
   the Photos app, iCloud, or Google Drive. Not WhatsApp: it shrinks the video.
2. Tell Claude: **"I put new clips in input, make Shorts."**
3. About 20 minutes per clip later you get previews in `C:\shorts\out`. Watch
   them and say what to change, in your own words.
4. Claude renders the finals, plus a text file per Short with the title and
   description to paste when you post.

When you correct something ("captions bigger", "don't cut that"), Claude
remembers it for next time in `guides/06-house-rules.md`.

## Shooting tips

- iPhone Settings → Camera → Record Video: **4K, 30 fps**, and **HDR Video off**.
- Vertical, phone at eye height, about 1.5 m away.
- One clip = one Short. If you mess up a sentence, say **«wait»** and say it again; it gets cut.
- Reading a follower's question from your phone at the start becomes a question card on screen.

---

## For the kit's author

- `tools/shorts.py` is the whole pipeline: faster-whisper, Greek wav2vec2 alignment, OpenCV YuNet faces, ffmpeg, Remotion. Run it with no arguments for the steps.
- `tools/doctor.py` checks an install. `--models` also downloads the models.
- `video/src/short/NativeShort.tsx` is the composition.
- Updates: push to the repo. His Claude runs `git pull --ff-only` at the start of every session. His corrections live in `guides/06-house-rules.md` and `channel.json` (ignored by git), so your updates to guides 01-05 never conflict with them. Read his `06-house-rules.md` now and then: rules that work for him may be worth moving into 01-05.
