"""Vertical Shorts shot on the phone: one clip in input/ = one Short (guides/).

Run with the kit's Python:
  Windows:  tools/.venv/Scripts/python.exe tools/shorts.py STEP [N ...] [A|B]
  Mac:      tools/.venv/bin/python tools/shorts.py STEP [N ...] [A|B]

  list        scan input/, number the clips -> work/shorts/clips.json (keeps existing numbers)
  asr         ingest + transcribe + align (audio, Whisper, exact word times) -> NN/transcript.txt
  look        sheets + faces (contact sheets to read the clip, face boxes for framing)
  build       cut + audio + reframe + timeline (needs NN/edit.json)
  qa          gap check, silence check, loudness, frame count -> PASS/FAIL per Short
  window N FROM TO   transcribe seconds FROM-TO of clip N in two halves (to find a hidden restart)
  stills N [F ...]   QA stills with the platform UI mask (no frames: an automatic set)
  preview [N ...]    720p previews -> out/preview-NN-slug.mp4
  final [N ...]      1080p finals -> out/NN-slug.mp4

Single steps also work: ingest, transcribe, align, sheets, faces, cut, audio, reframe, timeline.
No N = every clip. Versions: A = TikTok + YouTube («link in bio»), B = Instagram +
Facebook (comment a keyword). B only exists when edit.json has a CTA keyword.
NOBUNDLE=1 reuses the last Remotion bundle (only when nothing in video/src changed).
"""
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

for _s in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to cp1252: Greek would crash print()
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
WORK = ROOT / "work" / "shorts"
VIDEO = ROOT / "video"
PUBLIC = VIDEO / "public" / "clips"
OUT = ROOT / "out"
MODELS = ROOT / "tools" / "models"
REMOTION = VIDEO / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
FPS = 30
SPF = 1600  # audio samples per frame at 48 kHz
VIDEO_EXT = {".mov", ".mp4", ".m4v"}

DEFAULTS = {
    "language": "el",
    "whisper_model": "large-v3",
    "retake_cues": ["wait"],
    "question_label": "Ερώτηση από follower",
    "cta": {"bio": ["Link στο bio"], "comment": ["Γράψε στα σχόλια", "και σου το στέλνω στο DM"]},
    "fixes": {},
    "proper": [],
}

# cut rules (guides/02-cuts.md)
PRE_FIRST = 0.04
PRE = 0.04
POST = 0.06
MAX_GAP = 0.28      # a pause longer than this is cut
SIDE = 0.11         # air kept each side of a cut pause: with frame snapping the pause stays under 0.3 s
SHOT_MIN, SHOT_MAX = 2.4, 4.0  # a piece longer than SHOT_MAX gets zoom changes at sentence starts
TAIL = 0.20
# picture (guides/04-frame-audio.md), in 1080x1920 output pixels
CHIN_AT = 1270              # where the chin may sit at most, so captions fit under it
CAP_GAP = 26
CAP_FLOOR = 1404            # caption top never lower (platform title/caption text from ~1500)
HOOK_FRAMES = 90
FACE_H = 0.165   # face box height as a share of the frame at the base zoom (sitting ~1.5 m from the phone)
FACE_Y = 0.38    # face centre this far down the frame: room for the hook card above the head


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r


def stderr_of(cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr


def channel():
    p = ROOT / "channel.json"
    ch = dict(DEFAULTS)
    if p.exists():
        ch.update(load(p))
    return ch


# ---------------------------------------------------------------- clips
def probe(path):
    """Size as shown (phone rotation applied), HDR or not, fps, duration."""
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate,color_transfer:stream_side_data=rotation:stream_tags=rotate:format=duration",
             "-of", "json", path])
    j = json.loads(r.stdout)
    s = j["streams"][0]
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    rot = rot or int(s.get("tags", {}).get("rotate", 0) or 0)
    w, h = s["width"], s["height"]
    if abs(rot) % 180 == 90:
        w, h = h, w
    a, b = s["r_frame_rate"].split("/")
    trc = s.get("color_transfer")
    return {"w": w, "h": h, "hdr": trc in ("arib-std-b67", "smpte2084"), **({"trc": trc} if trc in ("arib-std-b67", "smpte2084") else {}),
            "fps": round(int(a) / int(b), 3), "dur": round(float(j["format"]["duration"]), 2)}


def list_clips(_args):
    """Number the clips in input/. Same name in different case (IMG_1.MOV / IMG_1.mov) = the same
    take exported twice (one HDR, one SDR): keep the SDR one."""
    p = WORK / "clips.json"
    old = load(p) if p.exists() else []
    known = {c["file"] for c in old}
    groups = {}
    for f in sorted(INPUT.iterdir()):
        if f.suffix.lower() in VIDEO_EXT and not f.name.startswith("."):
            groups.setdefault(f.stem.lower(), []).append(f)
    out = list(old)
    n = max([c["n"] for c in old], default=0)
    for stem, fs in groups.items():
        if any(f.name in known for f in fs):
            continue
        infos = [(f, probe(f)) for f in fs]
        infos.sort(key=lambda x: (x[1]["hdr"], -x[1]["h"]))  # SDR first, then the larger
        f, info = infos[0]
        n += 1
        c = {"n": n, "file": f.name, **info}
        if len(fs) > 1:
            c["note"] = "same take also as " + ", ".join(x.name for x, _ in infos[1:]) + " (ignored)"
        out.append(c)
    dump(p, out)
    for c in out:
        warn = []
        if c["w"] > c["h"]:
            warn.append("HORIZONTAL")
        if c["h"] < 1920:
            warn.append("under 1080p: the crop will be soft")
        print(f"#{c['n']:02d} {c['file']}: {c['dur']:.1f} s, {c['w']}x{c['h']}, {c['fps']} fps"
              f"{', HDR' if c['hdr'] else ''}{' (' + c['note'] + ')' if c.get('note') else ''}{'  ! ' + '; '.join(warn) if warn else ''}")


def clips(args):
    p = WORK / "clips.json"
    if not p.exists():
        list_clips([])
    cs = load(p)
    want = [int(a) for a in args]
    return [c for c in cs if not want or c["n"] in want]


def cdir(c):
    return WORK / f"{c['n']:02d}"


def src(c):
    return INPUT / c["file"]


def edit(c):
    return load(cdir(c) / "edit.json")


def versions(c):
    p = cdir(c) / "edit.json"
    cta = (load(p).get("cta") or {}) if p.exists() else {}
    return ["A", "B"] if cta.get("keyword") else ["A"]


def decode(c):
    """ffmpeg input options + filter prefix that turn the clip into SDR BT.709.
    iPhone «HDR Video» is HLG: tone-mapped with zscale (Windows/Linux builds) or
    VideoToolbox (Mac). SDR clips pass through."""
    if not c.get("hdr"):
        return [], ""
    if sys.platform == "darwin" and not has_filter("zscale"):
        return (["-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld"],
                f"scale_vt=w={c['w']}:h={c['h']}:color_matrix=bt709:color_primaries=bt709:color_transfer=bt709,hwdownload,format=p010le,")
    # hable at npl=100 came closest to the iPhone's own SDR export of the same take (2026-10-15 test)
    # input named explicitly: a clip whose colour tags got lost in transfer would otherwise fail («no path between colorspaces»)
    tin = c.get("trc", "arib-std-b67")
    return [], (f"setparams=color_trc={tin}:color_primaries=bt2020:colorspace=bt2020nc:range=tv,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


_FILTERS = None


def has_filter(name):
    global _FILTERS
    if _FILTERS is None:
        _FILTERS = run(["ffmpeg", "-hide_banner", "-filters"]).stdout
    return re.search(rf"\s{name}\s", _FILTERS) is not None


def duration(c):
    return c["dur"]


# ---------------------------------------------------------------- ingest
def ingest(c):
    d = cdir(c)
    d.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", src(c), "-vn", "-ac", 1, "-ar", 48000, "-c:a", "pcm_s16le", d / "audio48k.wav"])
    run(["ffmpeg", "-y", "-v", "error", "-i", d / "audio48k.wav", "-ar", 16000, d / "audio16k.wav"])
    (d / "silences.txt").write_text(stderr_of(["ffmpeg", "-i", d / "audio16k.wav", "-af", "silencedetect=n=-50dB:d=0.4", "-f", "null", "-"]),
                                    encoding="utf-8")
    print(f"#{c['n']} {c['file']}: {c['dur']:.1f} s")


# ---------------------------------------------------------------- transcribe
HALLU = re.compile(r"υπότιτλοι|authorwave|ευχαριστώ που παρακολουθ|subtitles by", re.I)
_WHISPER = None


def whisper():
    """faster-whisper: on an NVIDIA GPU when its libraries load, otherwise on the CPU (int8)."""
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        name = channel()["whisper_model"]
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                m = WhisperModel(name, device="cuda", compute_type="float16")
                list(m.transcribe(np.zeros(16000, np.float32), language="el")[0])  # fails here if cuDNN/cuBLAS are missing
                _WHISPER = m
                print("Whisper on the GPU")
        except Exception as e:
            print(f"GPU not usable for Whisper ({str(e)[:80]}), using the CPU")
        if _WHISPER is None:
            _WHISPER = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    return _WHISPER


def islands(d, dur):
    sil, st = [], None
    for line in (d / "silences.txt").read_text(encoding="utf-8").splitlines():
        if m := re.search(r"silence_start: ([\d.]+)", line):
            st = float(m.group(1))
        elif m := re.search(r"silence_end: ([\d.]+)", line):
            sil.append((st or 0.0, float(m.group(1))))
            st = None
    if st is not None:
        sil.append((st, dur))
    out, p = [], 0.0
    for s, e in sil:
        if s > p:
            out.append((p, s))
        p = e
    if p < dur:
        out.append((p, dur))
    return out


def transcribe(c):
    d = cdir(c)
    lang = channel()["language"]
    model = whisper()
    w = wave.open(str(d / "audio16k.wav"))
    sr = w.getframerate()
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    dur = len(audio) / sr
    chs = []
    for s, e in islands(d, dur):  # <= 24 s chunks, a 0.9 s pause starts a new one (keeps retakes apart)
        if chs and e - chs[-1][0] <= 24 and s - chs[-1][1] <= 0.9:
            chs[-1] = (chs[-1][0], e)
        else:
            chs.append((s, e))
    # finer pauses (-35 dB, 0.2 s) to split a chunk that comes back empty or thin
    err = stderr_of(["ffmpeg", "-i", d / "audio16k.wav", "-af", "silencedetect=n=-35dB:d=0.2", "-f", "null", "-"])
    fine = [(float(a), float(b)) for a, b in re.findall(r"silence_start: ([\d.]+)[\s\S]*?silence_end: ([\d.]+)", err)]

    def asr(cs, ce, depth=0):
        """Whisper on one chunk. Outdoors it returned «Λίγο.» or a «Υπότιτλοι…» hallucination
        for 24 s of clear speech: when a chunk yields under 1.2 words a second, split it at
        its longest pause and retry."""
        a, b = max(0, cs - 0.25), min(dur, ce + 0.25)
        segs, _ = model.transcribe(audio[int(a * sr):int(b * sr)], language=lang, word_timestamps=True,
                                   condition_on_previous_text=False, beam_size=5, vad_filter=False)
        good = []
        for x in segs:
            if x.text.strip() and not HALLU.search(x.text):
                good.append({"text": x.text, "words": [{"word": wd.word, "start": wd.start, "end": wd.end, "probability": wd.probability}
                                                       for wd in (x.words or [])]})
        n = sum(len(x["words"]) for x in good)
        inside = [(s, e) for s, e in fine if s > cs + 0.5 and e < ce - 0.5]
        if n < 1.2 * (ce - cs) and depth < 4 and ce - cs > 3 and inside:
            s, e = max(inside, key=lambda p: p[1] - p[0])
            return asr(cs, s + 0.05, depth + 1) + asr(e - 0.05, ce, depth + 1)
        return [(a, x) for x in good]

    words, segs = [], []
    for ci, (cs, ce) in enumerate(chs):
        for a, x in asr(cs, ce):
            ids = []
            for wd in x["words"]:
                words.append({"i": len(words), "word": wd["word"].strip(), "start": round(a + wd["start"], 3),
                              "end": round(a + wd["end"], 3), "prob": round(float(wd["probability"] or 0), 3), "chunk": ci})
                ids.append(words[-1]["i"])
            if ids:
                segs.append({"start": words[ids[0]]["start"], "end": words[ids[-1]]["end"], "text": x["text"].strip(), "words": ids})
    dump(d / "transcript.json", {"chunks": chs, "segments": segs, "words": words})
    print(f"#{c['n']} transcript: {len(words)} words, {len(chs)} chunks")


def window(c, a, b):
    """A suspected hidden restart: Whisper on each half of the window on its own, so a
    sentence said twice shows up twice."""
    w = wave.open(str(cdir(c) / "audio16k.wav"))
    sr = w.getframerate()
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    m = (a + b) / 2
    for x, y in ((a, m), (m, b)):
        segs, _ = whisper().transcribe(audio[int(x * sr):int(y * sr)], language=channel()["language"], word_timestamps=True,
                                       condition_on_previous_text=False)
        ws = [f"{wd.word.strip()} ({x + wd.start:.2f})" for sg in segs for wd in (sg.words or [])]
        print(f"#{c['n']} {x:.2f}-{y:.2f} s: " + (" ".join(ws) or "(nothing)"))


# ---------------------------------------------------------------- align
_ALIGN = None


def align(c):
    global _ALIGN
    sys.path.insert(0, str(ROOT / "tools"))
    import torch
    import greek_align as A
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    d = cdir(c)
    tr = load(d / "transcript.json")
    words, chunks = tr["words"], tr["chunks"]
    w = wave.open(str(d / "audio16k.wav"))
    sr = w.getframerate()
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if _ALIGN is None:
        proc = Wav2Vec2Processor.from_pretrained(A.MODEL)
        model = Wav2Vec2ForCTC.from_pretrained(A.MODEL).eval()
        dev = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        _ALIGN = (proc, model.to(dev), dev)
    proc, model, dev = _ALIGN
    vocab = proc.tokenizer.get_vocab()
    blank, sep = vocab["<pad>"], vocab["|"]

    def force(idx, a, b):
        inp = proc(audio[int(a * sr):int(b * sr)], sampling_rate=sr, return_tensors="pt").input_values.to(dev)
        with torch.no_grad():
            em = torch.log_softmax(model(inp).logits[0].float(), dim=-1).cpu().numpy()
        tokens, owner = [], []
        for k, i in enumerate(idx):
            cs = A.chars(words[i]["word"], vocab)
            if k:
                tokens.append(sep)
                owner.append(-1)
            tokens += cs
            owner += [i] * len(cs)
        if not tokens or len(tokens) > em.shape[0]:
            return {}
        fr = {}
        for t, tok in enumerate(A.viterbi(em, tokens, blank)):
            if tok >= 0 and owner[tok] >= 0:
                fr.setdefault(owner[tok], []).append(t)
        return {i: (round(a + f[0] * A.STRIDE, 3), round(a + (f[-1] + 1) * A.STRIDE, 3)) for i, f in fr.items()}

    groups = {}
    for wd in words:
        groups.setdefault(wd["chunk"], []).append(wd["i"])
    res = [None] * len(words)
    for ci, idx in groups.items():
        a = max(0.0, min(chunks[ci][0], words[idx[0]]["start"]) - 0.3)
        b = min(len(audio) / sr, max(chunks[ci][1], words[idx[-1]]["end"]) + 0.3)
        for i, r in force(idx, a, b).items():
            res[i] = r
    # words Whisper merged across a restart: align them again inside the window of the attempt that stays
    # (edit.json "realign": [first word, last word, from s, to s])
    for ra, rb, ws, we in (edit(c).get("realign", []) if (d / "edit.json").exists() else []):
        got = force(list(range(ra, rb + 1)), ws, we)
        for i, r in got.items():
            res[i] = r
        print(f"#{c['n']} realigned {ra}-{rb} in {ws}-{we} s: " + ", ".join(f"{words[i]['word']} {r[0]:.2f}-{r[1]:.2f}" for i, r in sorted(got.items())))
    out = []
    for wd, r in zip(words, res):
        s, e = r if r else (wd["start"], wd["end"])
        out.append({"i": wd["i"], "word": wd["word"], "start": s, "end": e, "aligned": bool(r)})
    dump(d / "words.json", out)
    # readable transcript: one line per sentence (or Whisper segment) with word indices and times; retake cues marked
    cues = {x.lower() for x in channel()["retake_cues"]}
    seg_end = {sg["words"][-1] for sg in tr["segments"]}
    lines, cur = [], []
    for wd in out:
        cur.append(wd)
        if re.search(r"[.;!?]$", wd["word"]) or wd["i"] in seg_end:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    txt = []
    for ln in lines:
        mark = [x["i"] for x in ln if re.sub(r"\W", "", x["word"]).lower() in cues]
        txt.append(f"[{ln[0]['i']:3d}-{ln[-1]['i']:3d}] {ln[0]['start']:6.2f}-{ln[-1]['end']:6.2f}  " + " ".join(x["word"] for x in ln)
                   + (f"   <<< RETAKE CUE at word {', '.join(map(str, mark))}" if mark else ""))
    (d / "transcript.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print(f"#{c['n']} aligned {sum(r is not None for r in res)}/{len(words)} -> {d / 'transcript.txt'}")


# ---------------------------------------------------------------- sheets
def sheets(c):
    d = cdir(c) / "sheets"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    pre, vf = decode(c)
    tw = 216 if c["h"] >= c["w"] else 384
    th = round(tw * c["h"] / c["w"] / 2) * 2
    # sheet k holds seconds 30k .. 30k+29, row by row
    run(["ffmpeg", "-y", "-v", "error", *pre, "-i", src(c), "-vf",
         f"{vf}fps=1,scale={tw}:{th},format=yuvj420p,tile=10x3:padding=4:color=white", "-start_number", 0, d / "sheet_%02d.jpg"])
    print(f"#{c['n']} sheets: {len(list(d.glob('*.jpg')))} in {d}")


# ---------------------------------------------------------------- faces
YUNET = MODELS / "face_detection_yunet_2023mar.onnx"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
# YuNet's box (brow to chin) mapped onto the Apple Vision box the framing numbers were tuned on
# (calibrated 2026-10-15 on 360 frames: Vision height = 0.773 x YuNet height, bottom = YuNet bottom - 0.032 x height)
VISION_H = 0.773
VISION_BOT = -0.032


def faces(c):
    """Face boxes 5 times a second (OpenCV YuNet), streamed straight from ffmpeg."""
    import cv2
    if not YUNET.exists():
        import urllib.request
        MODELS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(YUNET_URL, YUNET)
    d = cdir(c)
    W_ = 540
    H_ = round(W_ * c["h"] / c["w"] / 2) * 2
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (W_, H_), score_threshold=0.6)  # (OpenCV needs an ASCII path: keep the kit in C:\shorts)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src(c)), "-vf", f"fps=5,scale={W_}:{H_}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    out, k, size = [], 0, W_ * H_ * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        img = np.frombuffer(buf, np.uint8).reshape(H_, W_, 3)
        _, fs = det.detect(img)
        if fs is not None and len(fs):
            x, y, w, h = (float(v) for v in max(fs, key=lambda f: f[2] * f[3])[:4])
            x, y, w, h = x / W_, y / H_, w / W_, h / H_
            hv = h * VISION_H
            bot = y + h + VISION_BOT * h
            out.append({"t": round(k / 5, 2), "cx": round(x + w / 2, 4), "cy": round(bot - hv / 2, 4), "w": round(w, 4), "h": round(hv, 4),
                        "bot": round(bot, 4)})
        k += 1
    p.wait()
    dump(d / "faces.json", out)
    if not out:
        sys.exit(f"#{c['n']}: no face found in {k} frames")
    print(f"#{c['n']} faces: {len(out)}/{k} frames with a face, median face height {statistics.median(e['h'] for e in out):.3f}")


# ---------------------------------------------------------------- cut
def spans(rs):
    return {i for a, b in rs for i in range(a, b + 1)}


def dropped(c, ver):
    e = edit(c)
    s = spans(e.get("drop", []))
    cta = e.get("cta") or {}
    s |= spans(cta.get("comment", []) if ver == "A" else cta.get("bio", []))
    return s


def level_db(c):
    w = wave.open(str(cdir(c) / "audio48k.wav"))
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = 480  # 10 ms
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms)


def trim_stretched(c, W, db):
    """Alignment can stretch a word over a silence or a stumble that follows it. A word longer
    than its letters allow ends where its first speech run ends (>= -40 dBFS, dips under 0.2 s
    bridged). READ every «stretched» line: it can hide a restart (guides/02-cuts.md)."""
    out = []
    for w in W:
        limit = 0.35 + 0.11 * len(re.sub(r"\W", "", w["word"]))
        if w["end"] - w["start"] > limit:
            k, last, quiet = int(w["start"] * 100), int(w["start"] * 100), 0
            while k < int(w["end"] * 100) and k < len(db) and quiet < 20:
                if db[k] >= -40:
                    last, quiet = k, 0
                else:
                    quiet += 1
                k += 1
            end = round(min(w["end"], (last + 1) / 100), 3)
            print(f"#{c['n']} word {w['i']} «{w['word']}» {w['start']:.2f}-{w['end']:.2f} s stretched, ends at {end:.2f}")
            w = dict(w, end=end)
        out.append(w)
    return out


def cut(c, ver):
    W = load(cdir(c) / "words.json")
    drop = dropped(c, ver)
    db = level_db(c)
    W = trim_stretched(c, W, db)
    seq = [w for w in W if w["i"] not in drop]

    def soft_end(w, limit):  # fricatives and decays after the aligned end count as the word
        k, stop = int(w["end"] * 100), int(min(limit, w["end"] + 0.15) * 100)
        while k < stop and k < len(db) and db[k] >= -45:
            k += 1
        return k / 100

    def soft_start(w, limit):
        k, stop = int(w["start"] * 100), int(max(limit, w["start"] - 0.06) * 100)
        while k > stop and db[k - 1] >= -45:
            k -= 1
        return k / 100

    pieces, cur_in = [], max(0, soft_start(seq[0], 0) - PRE_FIRST)
    for p, n in zip(seq, seq[1:]):
        adjacent = n["i"] == p["i"] + 1
        if adjacent and n["start"] - p["end"] <= MAX_GAP:
            continue
        lim = n["start"] if adjacent else 1e9
        out = min(max(p["end"] + POST, soft_end(p, lim)), p["end"] + SIDE, lim)
        lim2 = p["end"] if adjacent else 0
        inn = max(min(n["start"] - PRE, soft_start(n, lim2)), n["start"] - SIDE, lim2)
        pieces.append([cur_in, out])
        cur_in = inn
    last = seq[-1]
    nxt = W[last["i"] + 1]["start"] - 0.02 if last["i"] + 1 < len(W) else duration(c) - 0.05
    pieces.append([cur_in, min(max(last["end"], soft_end(last, nxt)) + TAIL, nxt)])

    fr = []
    for a, b in pieces:
        fa, fb = math.floor(a * FPS + 1e-6), math.ceil(b * FPS - 1e-6)
        if fr and fa <= fr[-1][1]:
            fr[-1][1] = max(fr[-1][1], fb)
        else:
            fr.append([fa, fb])
    ps, off = [], 0
    for fa, fb in fr:
        ps.append({"in_frame": fa, "out_frame": fb, "in": fa / FPS, "out": fb / FPS, "start": off, "frames": fb - fa})
        off += fb - fa

    def to_short(t):
        for p in ps:
            if p["in"] - 1e-6 <= t <= p["out"] + 1e-6:
                return round((p["start"] + (t - p["in"]) * FPS) / FPS, 3)
        return None

    # shots: each piece, split at sentence starts so the framing changes every 2.4-4 s
    shots = []
    for p in ps:
        inside = [w for w in seq if p["in"] + SHOT_MIN <= w["start"] <= p["out"] - 1.5]
        cands = []
        for w in inside:
            prev = W[w["i"] - 1] if w["i"] else None
            sentence = w["word"][:1].isupper() or (prev and re.search(r"[.,;!?]$", prev["word"]))
            cands.append((math.floor((w["start"] - 0.03) * FPS), bool(sentence)))
        a = p["in_frame"]
        while p["out_frame"] - a > SHOT_MAX * FPS:
            ok = [(f, sen) for f, sen in cands if a + SHOT_MIN * FPS <= f <= a + SHOT_MAX * FPS and p["out_frame"] - f >= 1.5 * FPS]
            if not ok:
                break
            f = next((f for f, sen in ok if sen), ok[len(ok) // 2][0])
            shots.append([a, f])
            a = f
        shots.append([a, p["out_frame"]])
    sh, off2 = [], 0
    for a, b in shots:
        sh.append({"in_frame": a, "out_frame": b, "in": a / FPS, "out": b / FPS, "start": off2, "frames": b - a})
        off2 += b - a

    words = [{"i": w["i"], "word": w["word"], "start": to_short(w["start"]), "end": to_short(w["end"]),
              "src_start": w["start"], "src_end": w["end"]} for w in seq]
    gaps = [b["start"] - a["end"] for a, b in zip(words, words[1:])]
    worst = round(max(gaps), 3) if gaps else 0
    d = {"n": c["n"], "version": ver, "fps": FPS, "durationInFrames": off, "pieces": ps, "shots": sh, "words": words,
         "check": {"max_gap": worst, "gap_ok": worst < 0.3, "jump_cuts": len(ps) - 1}}
    dump(cdir(c) / f"short-{ver}.json", d)
    print(f"#{c['n']}{ver}: {c['dur']:.1f} s -> {off / FPS:.1f} s, {len(ps)} pieces, {len(sh)} shots, longest gap {worst:.2f} s "
          f"{'PASS' if d['check']['gap_ok'] else 'FAIL'}")


# ---------------------------------------------------------------- audio
def measure(path):
    err = stderr_of(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"])
    tail = err[err.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail).group(1))
    return i, tp


def audio(c, ver):
    d = load(cdir(c) / f"short-{ver}.json")
    parts = []
    for k, p in enumerate(d["pieces"]):
        dur = p["frames"] / FPS
        parts.append(f"[0:a]atrim=start_sample={p['in_frame'] * SPF}:end_sample={p['out_frame'] * SPF},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.005,afade=t=out:st={dur - 0.005:.6f}:d=0.005[c{k}];")
    n = len(d["pieces"])
    graph = "".join(parts) + "".join(f"[c{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[cat]"
    rawwav = cdir(c) / f"audio-{ver}-raw.wav"
    out = cdir(c) / f"audio-{ver}.wav"
    script = cdir(c) / f"audio-{ver}-graph.txt"  # long graphs overflow the Windows command line (32k chars)
    script.write_text(graph, encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-i", cdir(c) / "audio48k.wav", "-/filter_complex", script, "-map", "[cat]", "-c:a", "pcm_s16le", rawwav])
    err = stderr_of(["ffmpeg", "-hide_banner", "-i", rawwav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S).group(0))
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-y", "-v", "error", "-i", rawwav, "-af", ln, "-ar", 48000, "-c:a", "pcm_s16le", out])
    i, tp = measure(out)
    if abs(i + 14) > 0.25:  # loudnorm fell back to dynamic (peaky outdoor takes): gentle compression, then gain + limiter
        comp = "acompressor=threshold=0.08:ratio=3:attack=5:release=150:makeup=1"
        g = 0.0
        for _ in range(3):
            run(["ffmpeg", "-y", "-v", "error", "-i", rawwav, "-af", f"{comp},volume={g:.2f}dB,alimiter=limit=0.84:level=false:attack=2:release=60",
                 "-ar", 48000, "-c:a", "pcm_s16le", out])
            i, tp = measure(out)
            if abs(i + 14) <= 0.25:
                break
            g += -14 - i
    want = d["durationInFrames"] * SPF
    tmp = cdir(c) / f"audio-{ver}-x.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", out, "-af", f"apad=whole_len={want},atrim=end_sample={want}", "-c:a", "pcm_s16le", tmp])
    os.replace(tmp, out)
    rawwav.unlink()
    script.unlink()
    print(f"#{c['n']}{ver} audio: {i:.2f} LUFS, true peak {tp:.2f} dBTP")


# ---------------------------------------------------------------- reframe
def reframe(c, ver):
    """One fixed frame per Short, centred on where the face sits over the kept footage;
    shots only zoom in and out (100/108%) around the face, the camera never pans."""
    SW, SH = c["w"], c["h"]
    max_zoom = max(1.0, min(1.6, SH / 1920 * 1.25))  # 4K: 1.6; 1080p: 1.25 (already upscaling)
    d = load(cdir(c) / f"short-{ver}.json")
    fc = load(cdir(c) / "faces.json")
    base = max(1.0, min(max_zoom, FACE_H / statistics.median(e["h"] for e in fc)))
    base = edit(c).get("zoom", base)
    kept = [e for e in fc if any(p["in"] <= e["t"] <= p["out"] for p in d["pieces"])] or fc
    ax = statistics.median(e["cx"] for e in kept) * SW
    ay = statistics.median(e["cy"] for e in kept) * SH
    bots = sorted(e["bot"] * SH for e in kept)
    ch0 = min(SH, SW * 16 / 9) / base
    cw0 = ch0 * 9 / 16
    x0 = max(0, min(SW - cw0, ax - cw0 / 2))
    y0 = max(ay - FACE_Y * ch0, bots[int(len(bots) * 0.9)] - CHIN_AT * ch0 / 1920)  # the chin never below CHIN_AT
    y0 = max(0, min(SH - ch0, y0))
    pdir = cdir(c) / f"pieces-{ver}"
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir()
    pre, tone = decode(c)
    crops = []

    def one(k_p):
        k, p = k_p
        f = 1.08 if k % 2 else 1.0  # zoom in on every other shot, around the face
        ch = round(ch0 / f / 2) * 2
        cw = round(ch * 9 / 16 / 2) * 2
        x = int(max(0, min(SW - cw, ax - (ax - x0) / f)))
        y = int(max(0, min(SH - ch, ay - (ay - y0) / f)))
        dets = [e for e in fc if p["in"] - 0.2 <= e["t"] <= p["out"] + 0.2]
        b = sorted(e["bot"] * SH for e in dets) or [SH * 0.4]
        chin = b[min(len(b) - 1, int(len(b) * 0.9))]
        out = [e for e in dets if (e["cx"] - e["w"] / 2) * SW < x or (e["cx"] + e["w"] / 2) * SW > x + cw]
        crops.append({"piece": k, "zoom": round(base * f, 3), "crop": [cw, ch], "x": x, "y": y,
                      "chinOut": round((chin - y) * 1920 / ch), "faceOut": len(out)})
        vf = f"{tone}fps=30,crop=w={cw}:h={ch}:x={x}:y={y},scale=1080:1920:flags=lanczos,format=yuv420p,setsar=1"
        run(["ffmpeg", "-y", "-v", "error", *pre, "-ss", f"{p['in']:.4f}", "-i", src(c), "-vf", vf, "-frames:v", p["frames"],
             "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-g", "30", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-colorspace", "bt709", "-an", pdir / f"p{k:03d}.mp4"])

    with ThreadPoolExecutor(2 if c.get("hdr") else 4) as ex:
        list(ex.map(one, enumerate(d["shots"])))
    lst = pdir / "list.txt"
    lst.write_text("".join(f"file 'p{k:03d}.mp4'\n" for k in range(len(d["shots"]))), encoding="utf-8")
    face = cdir(c) / f"face-{ver}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", face])
    n = frame_count(face)
    shutil.rmtree(pdir)
    d["crops"] = sorted(crops, key=lambda e: e["piece"])
    dump(cdir(c) / f"short-{ver}.json", d)
    print(f"#{c['n']}{ver} face: {n} frames (want {d['durationInFrames']}) {'OK' if n == d['durationInFrames'] else 'MISMATCH'}, "
          f"zoom {base:.2f}/{base * 1.08:.2f}, chin at {max(e['chinOut'] for e in crops)} px, "
          f"face samples outside the frame: {sum(e['faceOut'] for e in crops)}")


def frame_count(path):
    return int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                    "-of", "csv=p=0", path]).stdout.strip().strip(","))


# ---------------------------------------------------------------- captions
def proper_lc():
    """Capitalised words that do not start a sentence (names, brands): channel.json "proper"."""
    return {p.lower() for p in channel()["proper"]}


def caption_words(words, fix):
    """Caption text per word: spelling fixes (channel.json "fixes"), joins split tokens
    («e» «-book»), writes «1200 ευρώ» as «1200€», capitalises the first word after every cut."""
    out = []
    for w in words:
        t = w["word"]
        if t in fix:  # a fix for the whole token, punctuation included («χαζοί?» -> «χαζοί;»)
            t = fix[t]
        core = re.sub(r"[.,;!?]+$", "", t)
        tail = t[len(core):]
        t = fix.get(core, core) + tail
        if out and t.startswith("-"):
            out[-1] = (out[-1][0], out[-1][1] + t)
            continue
        if out and core in ("ευρώ", "$") and re.fullmatch(r"\d+", out[-1][1]):
            out[-1] = (out[-1][0], out[-1][1] + ("€" if core == "ευρώ" else "$") + tail)
            continue
        out.append((w, t))
    starts = {w["i"] for k, w in enumerate(words) if k == 0 or w["i"] != words[k - 1]["i"] + 1}
    return [(w, t[:1].upper() + t[1:] if w["i"] in starts else t) for w, t in out]


def caption_pages(words, fix):
    """2-4 words a page, at most 22 characters; a new page at every sentence start and every pause."""
    pages, cur = [], []
    proper = proper_lc()
    for w, t in caption_words(words, fix):
        cand = cur + [(w, t)]
        chars = sum(len(x[1]) for x in cand) + len(cand) - 1
        sentence = t[:1].isupper() and t.lower().strip(".,;") not in proper
        gap_before = cur and ((w["start"] - cur[-1][0]["end"]) > 0.25 or sentence)
        if cur and (chars > 22 or len(cand) > 4 or gap_before):
            pages.append(cur)
            cur = [(w, t)]
        else:
            cur = cand
        if re.search(r"[.;!?]$", t) or (t.endswith(",") and len(cur) >= 2 and not re.fullmatch(r"\d+[€$]?,", t)):
            pages.append(cur)
            cur = []
    if cur:
        pages.append(cur)
    out = []
    for k, pg in enumerate(pages):
        start = round(pg[0][0]["start"] * FPS)
        end = round(pages[k + 1][0][0]["start"] * FPS) if k + 1 < len(pages) else None
        out.append({"start": start, "end": end, "words": [{"text": re.sub(r"[.,]$", "", t), "start": round(w["start"] * FPS)} for w, t in pg]})
    return out


def norm_words(words, by_index):
    """Fixes by word index (edit.json "fix"); Whisper splits «8.000» into «8» «.000»: joined,
    and «8.000 ευρώ» becomes «8.000€»."""
    out = []
    for w in words:
        t = by_index.get(str(w["i"]), w["word"])
        prev = out[-1] if out else None
        if prev and re.fullmatch(r"[.,]\d{3}[.,;!?]?", t) and re.fullmatch(r"\d+([.,]\d{3})*", prev["word"]):
            out[-1] = dict(prev, word=prev["word"] + t, end=w["end"], i=w["i"])  # the merged word carries the last index
            continue
        m = re.fullmatch(r"ευρώ([.,;!?]?)", t)
        if prev and m and re.fullmatch(r"\d+([.,]\d{3})*", prev["word"]):
            out[-1] = dict(prev, word=prev["word"] + "€" + m.group(1), end=w["end"], i=w["i"])
            continue
        out.append(dict(w, word=t))
    return out


# ---------------------------------------------------------------- timeline
def slug_of(c, ver):
    e = edit(c)
    return f"{c['n']:02d}-{e['slug']}" + (f"-{ver}" if len(versions(c)) > 1 else "")


def timeline(c, ver):
    ch = channel()
    e = edit(c)
    d = load(cdir(c) / f"short-{ver}.json")
    dur = d["durationInFrames"]
    words = d["words"]
    at = {w["i"]: w for w in words}
    fr = lambda t: round(t * FPS)  # noqa: E731

    fixes = ch["fixes"]
    words = norm_words(words, {str(k): v for k, v in e.get("fix", {}).items()})
    q = None
    if e.get("question"):
        a, b = e["question"]["words"]
        qw = [w for w in words if a <= w["i"] <= b]
        q = {"label": e["question"].get("label", ch["question_label"]),
             "start": 0 if a == words[0]["i"] else fr(at[a]["start"]) - 2, "end": fr(at[b]["end"]) + 12,
             "words": [{"text": t, "start": fr(w["start"])} for w, t in caption_words(qw, fixes)]}
    nocap = spans(e.get("nocap", [])) | spans(e.get("nocap" + ver, []))
    if q:
        nocap |= spans([e["question"]["words"]])
    capw = [w for w in words if w["i"] not in nocap]
    caps = caption_pages(capw, fixes)
    for k, p in enumerate(caps):  # a page ends at the next page, or 0.4 s after its last word before a hidden stretch
        lastw = next(w for w in capw if fr(w["start"]) == p["words"][-1]["start"])
        if k + 1 == len(caps) or caps[k + 1]["start"] - fr(lastw["end"]) > 15:
            p["end"] = min(p["end"] if p["end"] is not None else dur, fr(lastw["end"]) + 12)
        if p["end"] is None:
            p["end"] = dur

    cta_e = e.get("cta")
    if not cta_e:
        cta = None
    elif ver == "A" or not cta_e.get("keyword"):
        cta = {"kind": "bio", "start": max(fr(words[-1]["start"]) - 60, dur - 105), "end": dur, "lines": ch["cta"]["bio"]}
    else:
        kw = cta_e.get("keyword_word")
        cta = {"kind": "comment", "keyword": cta_e["keyword"], "start": (fr(at[kw]["start"]) - 2) if kw in at else dur - 105, "end": dur,
               "lines": ch["cta"]["comment"]}
    hook = {"text": e["hook"], "until": HOOK_FRAMES} if e.get("hook") else None
    sfx = [{"at": cta["start"], "sound": "pop_2", "volume": 0.26}] if cta else []
    if q and q["start"] > 0:
        sfx.append({"at": q["start"], "sound": "pop_1", "volume": 0.26})
    # the face box ends ~40 px under the visible chin; 85th percentile over the shots,
    # so a single look-down doesn't push the captions far from the chin for the whole Short
    chins = sorted(cr["chinOut"] for cr in d["crops"])
    capTop = min(CAP_FLOOR, chins[int(len(chins) * 0.85)] - 40 + CAP_GAP)
    if q:  # the question card sits under the chin too, but never reaches the platform UI at the bottom
        chars = sum(len(w["text"]) + 1 for w in q["words"])
        h = 86 + 42 * math.ceil(chars / 36)  # 680 px card, 34 px text (video/src/short/NativeShort.tsx)
        q["top"] = min(capTop - 10, 1490 - h)
    slug = slug_of(c, ver)
    out = {"slug": slug, "fps": FPS, "durationInFrames": dur, "video": f"clips/{slug}/face.mp4", "audio": f"clips/{slug}/audio.wav",
           "capTop": capTop, "hook": hook, "question": q, "cta": cta, "captions": caps, "sfx": sorted(sfx, key=lambda s: s["at"]),
           "jumpCuts": [p["start"] for p in d["shots"][1:]]}
    dump(cdir(c) / f"timeline-{ver}.json", out)
    pub = PUBLIC / slug
    pub.mkdir(parents=True, exist_ok=True)
    for name, srcf in (("face.mp4", f"face-{ver}.mp4"), ("audio.wav", f"audio-{ver}.wav")):
        if (pub / name).exists():
            (pub / name).unlink()
        try:
            os.link(cdir(c) / srcf, pub / name)  # the Remotion bundler copies public/, but won't follow symlinks
        except OSError:
            shutil.copy2(cdir(c) / srcf, pub / name)
    print(f"#{c['n']}{ver} timeline: {dur / FPS:.1f} s, {len(caps)} caption pages, caption top {capTop}, "
          f"CTA {cta['kind'] + ' from ' + str(round(cta['start'] / FPS, 1)) + ' s' if cta else 'none'}")


# ---------------------------------------------------------------- QA
def qa(c, ver):
    if not (cdir(c) / f"timeline-{ver}.json").exists():
        print(f"#{c['n']}{ver}: not built yet (no edit.json or build not run), skipped")
        return True
    d = load(cdir(c) / f"short-{ver}.json")
    t = load(cdir(c) / f"timeline-{ver}.json")
    wav = cdir(c) / f"audio-{ver}.wav"
    sil = re.findall(r"silence_start: ([\d.]+)", stderr_of(["ffmpeg", "-i", wav, "-af", "silencedetect=n=-32dB:d=0.3", "-f", "null", "-"]))
    i, tp = measure(wav)
    n = frame_count(cdir(c) / f"face-{ver}.mp4")
    outside = sum(e["faceOut"] for e in d["crops"])
    checks = {
        "word gaps under 0.3 s": d["check"]["gap_ok"],
        f"no silence over 0.3 s in the audio{' (at ' + ', '.join(sil[:5]) + ' s)' if sil else ''}": not sil,
        f"loudness -14 LUFS ({i:.1f}), peak <= -1.0 dBTP ({tp:.1f})": abs(i + 14) <= 0.5 and tp <= -1.0,
        f"video frames = audio frames ({n}/{t['durationInFrames']})": n == t["durationInFrames"],
        f"face inside the frame on every sample ({outside} outside)": outside == 0,
        f"length {t['durationInFrames'] / FPS:.1f} s (<= 60 s)": t["durationInFrames"] <= 60 * FPS,
    }
    ok = all(checks.values())
    print(f"#{c['n']}{ver} {t['slug']}: {'PASS' if ok else 'FAIL'}")
    for k, v in checks.items():
        print(f"   {'ok  ' if v else 'FAIL'} {k}")
    return ok


# ---------------------------------------------------------------- stills, renders
def node_cli(*args):
    run(["node", REMOTION, *args], cwd=VIDEO)


def bundle(dest=WORK / "bundle"):
    """The Remotion bundle copies video/public/ when it is made. NOBUNDLE=1 reuses it and
    only adds the clip files built since (no code changes picked up)."""
    if os.environ.get("NOBUNDLE") and dest.exists():
        for f in PUBLIC.rglob("*"):
            to = dest / "public" / "clips" / f.relative_to(PUBLIC)
            if f.is_file() and (not to.exists() or to.stat().st_mtime < f.stat().st_mtime or to.stat().st_size != f.stat().st_size):
                to.parent.mkdir(parents=True, exist_ok=True)
                to.unlink(missing_ok=True)
                shutil.copy2(f, to)
        return dest
    shutil.rmtree(dest, ignore_errors=True)
    node_cli("bundle", "--out-dir", dest, "--log=error")
    return dest


def auto_frames(t):
    """Frame 0 (hook), the question card, three caption pages spread over the Short, the CTA, the last frame."""
    dur = t["durationInFrames"]
    fs = {0, dur - 1}
    if t["question"]:
        fs.add(min(dur - 1, t["question"]["start"] + 20))
    caps = t["captions"]
    for k in (len(caps) // 4, len(caps) // 2, 3 * len(caps) // 4):
        if caps:
            p = caps[k]
            fs.add(min(dur - 1, p["start"] + 4))
    if t["cta"]:
        fs.add(min(dur - 1, t["cta"]["start"] + 20))
    return sorted(fs)[:8]


def stills(c, ver, frames, b):
    data = load(cdir(c) / f"timeline-{ver}.json")
    frames = frames or auto_frames(data)
    sd = cdir(c) / f"stills-{ver}"
    shutil.rmtree(sd, ignore_errors=True)
    sd.mkdir()
    jobs = [{"composition": "NativeShort", "props": {"data": data, "safe": True}, "frame": f, "out": str(sd / f"f{f:05d}.png"), "scale": 0.4}
            for f in frames]
    dump(sd / "jobs.json", jobs)
    run(["node", ROOT / "tools" / "stills.cjs", b, sd / "jobs.json"])
    ins = sum([["-i", j["out"]] for j in jobs], [])
    out = sd.with_suffix(".png")
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex",
         ("".join(f"[{k}]" for k in range(len(jobs))) + f"hstack=inputs={len(jobs)}") if len(jobs) > 1 else "null", out])
    print(f"{out}  (frames {', '.join(map(str, frames))}; red = covered by the platform UI)")


def render(c, ver, final, b):
    data = load(cdir(c) / f"timeline-{ver}.json")
    props = cdir(c) / f"props-{ver}.json"
    dump(props, {"data": data, "safe": False})
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"{data['slug']}.mp4" if final else f"preview-{data['slug']}.mp4"
    opts = ["--crf=18"] if final else ["--scale=0.6666666666666666", "--crf=20"]
    node_cli("render", b, "NativeShort", OUT / name, f"--props={props}", *opts, "--log=error")
    print(OUT / name)


STEPS = {"ingest": ingest, "transcribe": transcribe, "align": align, "sheets": sheets, "faces": faces}
VSTEPS = {"cut": cut, "audio": audio, "reframe": reframe, "timeline": timeline, "qa": qa}
GROUPS = {"asr": ["ingest", "transcribe", "align"], "look": ["sheets", "faces"], "build": ["cut", "audio", "reframe", "timeline"]}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        sys.exit()
    step, args = sys.argv[1], sys.argv[2:]
    only = [a for a in args if a in ("A", "B")]
    args = [a for a in args if a not in ("A", "B")]
    if step == "list":
        list_clips(args)
        sys.exit()
    if step == "window":
        window(clips(args[:1])[0], float(args[1]), float(args[2]))
        sys.exit()
    if step in ("stills", "preview", "final"):
        b = bundle()
        for c in clips(args[:1] if step == "stills" else args):
            for v in only or versions(c):
                if step == "stills":
                    stills(c, v, [int(x) for x in args[1:]], b)
                else:
                    render(c, v, step == "final", b)
        sys.exit()
    if step not in STEPS and step not in VSTEPS and step not in GROUPS:
        sys.exit(f"unknown step «{step}». Steps: list, {', '.join(GROUPS)}, {', '.join(STEPS)}, {', '.join(VSTEPS)}, stills, preview, final")
    results = []
    for c in clips(args):
        for s in GROUPS.get(step, [step]):
            if s in STEPS:
                STEPS[s](c)
            else:
                for v in only or versions(c):
                    results.append(VSTEPS[s](c, v))
    if step == "qa" and not all(results):
        sys.exit(1)
