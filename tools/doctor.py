"""Checks that everything the Shorts pipeline needs is installed and works.

  tools/.venv/Scripts/python.exe tools/doctor.py              (Windows)
  tools/.venv/bin/python tools/doctor.py                      (Mac)
  ... doctor.py --models     also downloads Whisper and the alignment model (~4 GB, once)

Prints one line per check and ALL GOOD at the end, or what to fix.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
TMP = ROOT / "work" / "doctor"
results = []


def check(name, fn):
    try:
        msg = fn()
        results.append((True, name, msg or ""))
        print(f"  ok    {name}{' - ' + msg if msg else ''}", flush=True)
    except Exception as e:
        results.append((False, name, str(e)))
        print(f"  FAIL  {name} - {str(e)[:400]}", flush=True)


def sh(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-600:])
    return r.stdout + r.stderr


def python():
    v = sys.version_info
    if (v.major, v.minor) < (3, 10):
        raise RuntimeError(f"Python {v.major}.{v.minor}; need 3.12")
    return f"{v.major}.{v.minor}.{v.micro}"


def packages():
    import cv2
    import faster_whisper
    import numpy
    import torch
    import transformers
    gpu = "NVIDIA GPU visible to torch" if torch.cuda.is_available() else "CPU only (fine, just slower transcription)"
    return f"faster-whisper {faster_whisper.__version__}, torch {torch.__version__}, opencv {cv2.__version__}, numpy {numpy.__version__}; {gpu}"


def ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise RuntimeError(f"{tool} not on PATH (open a new terminal after installing, or restart the Claude app)")
    out = sh(["ffmpeg", "-hide_banner", "-version"])
    m = re.search(r"ffmpeg version (?:n)?(\d+)", out)
    major = int(m.group(1)) if m else 0
    if major and major < 7:
        raise RuntimeError(f"ffmpeg {major}.x is too old; need 7 or newer")
    filters = sh(["ffmpeg", "-hide_banner", "-filters"])
    missing = [f for f in ("zscale", "tonemap", "loudnorm", "silencedetect", "ebur128") if not re.search(rf"\s{f}\s", filters)]
    if missing and not (sys.platform == "darwin" and missing == ["zscale"]):
        raise RuntimeError(f"this ffmpeg build lacks {', '.join(missing)}; install the full build (winget install Gyan.FFmpeg)")
    if "libx264" not in sh(["ffmpeg", "-hide_banner", "-encoders"]):
        raise RuntimeError("this ffmpeg build has no libx264 encoder")
    return (m.group(0) if m else out.splitlines()[0]) + (", no zscale (Mac: HDR goes through VideoToolbox)" if missing else "")


def hdr():
    """A synthetic 10-bit HLG clip (like iPhone «HDR Video») through the same tone mapping the pipeline uses."""
    import shorts
    TMP.mkdir(parents=True, exist_ok=True)
    src = TMP / "hlg.mkv"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=540x960:d=1:r=30", "-vf", "format=yuv420p10le",
        "-c:v", "ffv1", "-color_primaries", "bt2020", "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc", src])
    pre, vf = shorts.decode({"hdr": True, "w": 540, "h": 960})
    if pre:
        return "Mac: VideoToolbox path (not tested here)"
    out = TMP / "hlg-sdr.png"
    sh(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", vf + "scale=270:480", "-frames:v", 1, out])
    stats = sh(["ffmpeg", "-v", "info", "-i", out, "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"])
    y = float(re.search(r"YAVG=([\d.]+)", stats).group(1))
    if not 30 < y < 200:
        raise RuntimeError(f"tone-mapped test frame has average brightness {y:.0f} (expected 30-200)")
    return f"HLG -> SDR works (test frame brightness {y:.0f})"


def node():
    if not shutil.which("node"):
        raise RuntimeError("node not on PATH")
    v = sh(["node", "--version"]).strip()
    if int(v.lstrip("v").split(".")[0]) < 18:
        raise RuntimeError(f"Node {v}; need 18 or newer (LTS)")
    if not (ROOT / "video" / "node_modules" / "@remotion" / "cli" / "remotion-cli.js").exists():
        raise RuntimeError("video/node_modules missing: run `npm ci` in the video folder")
    return v


def typecheck():
    tsc = ROOT / "video" / "node_modules" / "typescript" / "bin" / "tsc"
    sh(["node", tsc, "--noEmit", "-p", ROOT / "video"])
    return "video/src compiles"


def render():
    import shorts
    b = shorts.bundle(TMP / "bundle")
    out = TMP / "test-still.png"
    jobs = TMP / "jobs.json"
    jobs.write_text(json.dumps([{"composition": "NativeShort", "props": {"data": EMPTY, "safe": True},
                                 "frame": 15, "out": str(out), "scale": 0.4}]), encoding="utf-8")
    sh(["node", ROOT / "tools" / "stills.cjs", b, jobs])
    if not out.exists():
        raise RuntimeError("no still was written")
    return f"Remotion + headless Chrome work ({out.relative_to(ROOT)})"


EMPTY = {"slug": "doctor", "fps": 30, "durationInFrames": 30, "video": "", "audio": "", "capTop": 1300,
         "hook": {"text": "Το kit δουλεύει;", "until": 30}, "question": None, "cta": None,
         "captions": [{"start": 0, "end": 30, "words": [{"text": "Ναι,", "start": 0}, {"text": "δουλεύει!", "start": 12}]}],
         "sfx": [], "jumpCuts": []}


def models():
    import shorts
    import greek_align
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    Wav2Vec2Processor.from_pretrained(greek_align.MODEL)
    Wav2Vec2ForCTC.from_pretrained(greek_align.MODEL)
    shorts.whisper()
    shorts.MODELS.mkdir(parents=True, exist_ok=True)
    if not shorts.YUNET.exists():
        import urllib.request
        urllib.request.urlretrieve(shorts.YUNET_URL, shorts.YUNET)
    return f"Whisper {shorts.channel()['whisper_model']}, Greek alignment, face detector downloaded"


def disk():
    free = shutil.disk_usage(ROOT).free / 1e9
    if free < 15:
        raise RuntimeError(f"only {free:.0f} GB free; keep at least 15 GB (4K clips + models + renders)")
    return f"{free:.0f} GB free"


def path_ascii():
    if not str(ROOT).isascii():
        raise RuntimeError(f"the kit is in {ROOT}: move it to a plain path like C:\\shorts (OpenCV can't open non-Latin paths)")
    if "onedrive" in str(ROOT).lower():
        raise RuntimeError("the kit is inside OneDrive: move it to C:\\shorts (OneDrive sync breaks node_modules and big renders)")
    return str(ROOT)


if __name__ == "__main__":
    print("Shorts kit check\n")
    check("folder", path_ascii)
    check("disk space", disk)
    check("Python", python)
    check("Python packages", packages)
    check("ffmpeg", ffmpeg)
    check("HDR tone mapping", hdr)
    check("Node.js + Remotion", node)
    check("TypeScript", typecheck)
    check("test render", render)
    if "--models" in sys.argv:
        check("models", models)
    bad = [r for r in results if not r[0]]
    print("\nALL GOOD" if not bad else f"\n{len(bad)} to fix: " + "; ".join(r[1] for r in bad))
    sys.exit(1 if bad else 0)
