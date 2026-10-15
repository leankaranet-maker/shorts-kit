# First-time setup (Windows)

Claude runs these steps; the person only approves. Tell them up front: about 30
minutes, mostly downloads (~6 GB in total), and they can do something else
meanwhile. Check each step before moving on. If a step fails, fix it before going on.

## 0. Where the kit is

- It must be in a plain path such as `C:\shorts`. **Not** inside OneDrive,
  Desktop or Documents when those sync to OneDrive, and no Greek letters in the
  path (OpenCV can't open those). If it's somewhere else, tell them, and move it
  with them (close this session, move the folder, reopen it in Claude).
- At least 15 GB free on that drive.

## 1. Programs (winget, built into Windows 10/11)

Check what is already there first (`python --version`, `node --version`,
`ffmpeg -version`, `git --version`), then install only what's missing:

```
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
```

Git is already installed (Claude Code on Windows needs it).

Programs installed by winget are only on PATH in **new** terminals. If `ffmpeg`,
`node` or `py` aren't found right after installing, call them by full path for
now (`py` is in `C:\Windows`, Node in `C:\Program Files\nodejs`, ffmpeg under
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\...\bin`), or ask them to
restart the Claude app once and continue from here.

## 2. Python environment

```
py -3.12 -m venv tools/.venv
tools/.venv/Scripts/python.exe -m pip install --upgrade pip
tools/.venv/Scripts/python.exe -m pip install -r tools/requirements.txt
```

(torch is ~200 MB; this takes a few minutes.)

If they have an **NVIDIA** graphics card (`nvidia-smi` works), Whisper can use it:
`tools/.venv/Scripts/python.exe -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*`.
The pipeline falls back to the CPU on its own if the GPU doesn't load, so skip
this if anything about it fails.

## 3. Remotion (the part that draws captions and renders the video)

```
cd video
npm ci
```

## 4. Check, and download the models (~4 GB, once)

```
tools/.venv/Scripts/python.exe tools/doctor.py --models
```

It must end with **ALL GOOD**. The first test render also downloads a small
headless Chrome. Show them `work/doctor/test-still.png` (a yellow card and a
caption): that's what the captions will look like.

## 5. Their channel (`channel.json`)

Ask in **one message**, with the defaults in brackets so they can just say "ok":

1. What language do you speak in the videos? [Greek]
2. When you mess up mid-sentence and start again, what do you say first? [«wait»]
3. Do you read followers' questions from your phone at the start of the clips? [yes → shown as a comment card «Ερώτηση από follower»]
4. Call to action at the end: none, «Link στο bio», or «comment KEYWORD and I'll DM you»? [none unless you say it in the video]
5. Names or brands you mention often (so they're spelled right)? [none]

Copy `channel.example.json` to `channel.json` and fill it in. The pipeline's
alignment model is Greek: if they speak another language, tell them that
alignment needs a different model (a later step; it still works but word timing
is looser) and write `"language"` accordingly.

## 6. How to shoot and how to bring the clips over

Tell them once, short (it saves hours later):

- **iPhone:** Settings → Camera → Record Video → **4K at 30 fps**, and turn
  **HDR Video off** (HDR works too, but SDR gives the truest colours).
- Vertical, phone at eye height, ~1.5 m away, face around the upper third.
  One clip = one Short. Fluff a line? Say the cue word («wait») and repeat the sentence.
- **Bringing clips to the laptop, without compression:** USB cable + the Windows
  Photos app (Import), or iCloud for Windows, or Google Drive with
  "original quality". **Not** WhatsApp, Messenger or Telegram (they shrink the video).
- Put the clips in `input/`.

## 7. Done

Tell them setup is done and what to say next time: *"I put new clips in input,
make Shorts"*. If clips are already in `input/`, offer to start right away.
