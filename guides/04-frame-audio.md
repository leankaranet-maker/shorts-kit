# 4. Frame and audio

## Frame *(rules from the first runs)*

- **Source:** the vertical clip as shot (4K recommended). The 9:16 crop is cut from the full-resolution original and scaled down to 1080×1920, so it stays sharp. A 1080p clip works but the crop is upscaled (`list` warns).
- **No panning, ever.** One fixed frame per Short, placed on the median of the face over the kept footage. Shots only zoom in and out (100% / 108% of the base zoom) around the face, changing every 2.4-4 s at sentence starts.
- **Base zoom from the face size:** the face box (eyebrows to chin) is set to 16.5% of the frame height (someone ~1.5 m from the phone → ~122%). Close-ups start at 100% so the frame can still move; override with `edit.json` `zoom`.
- **Face centre at 38% from the top**, leaving room for the hook card above the head, and the chin never below y 1270, leaving room for captions under it.
- Check in the `build` output: `face samples outside the frame: 0`, and `MISMATCH` never appears.
- Face boxes come from OpenCV's YuNet detector, mapped onto the Apple Vision box these numbers were tuned with (`VISION_H`, `VISION_BOT` in `tools/shorts.py`). If captions end up consistently too low or too high on their face, adjust `CAP_GAP` or those two numbers and say so.

## HDR

iPhone «HDR Video» clips (HLG) are tone-mapped to normal SDR colour
automatically (`list` shows `HDR`). The tone mapping was tuned to match the
iPhone's own SDR export of the same take. If an HDR Short looks washed out or
too dark next to the phone's version, tell them, and suggest turning HDR Video
off on the iPhone for future clips.

## Audio

- Mono from the phone mic, 5 ms fades at every join, **−14 LUFS**, true peak −1.5 dBTP (`qa` checks −14 ±0.5).
- Outdoor takes are peaky: two-pass loudnorm can land at −15; the pipeline then compresses gently (3:1 above −22 dBFS) before gain and a limiter.
- `qa` also runs `silencedetect` (−32 dB, 0.3 s) on the finished audio: it must find nothing. If it finds something, there's a pause the word times hid (guide 02, stretched words).
