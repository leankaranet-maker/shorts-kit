# 2. Cuts: `edit.json`, only mistakes and retakes

## Read the clip first

1. `work/shorts/NN/transcript.txt`: one line per sentence or Whisper segment, as
   `[first-last word index] start-end seconds  words`. Lines with the retake cue
   word are marked `<<< RETAKE CUE`.
2. `work/shorts/NN/words.json` for single-word indices and times.
3. The contact sheets `work/shorts/NN/sheets/` (1 frame a second; sheet k = seconds 30k to 30k+29, row by row): where they look, when they read from the phone, when they leave the frame.

**Looking down at the phone and reading = a follower's question.** It becomes
the question card (guide 03).

## Write `work/shorts/NN/edit.json`

```json
{
 "slug": "8000-euro",
 "point": "The question, then their answer in one line.",
 "hook": "Πολλά λεφτά, καθόλου χρόνος;",
 "question": {"words": [0, 29]},
 "drop": [[75, 75]],
 "drop_why": {"75": "«Wait»: retake cue"},
 "fix": {"21": "βλέπαμε.", "29": "καλά;"},
 "cta": null
}
```

| Field | Meaning |
| --- | --- |
| `slug` | short Latin name for the files (`out/NN-slug.mp4`) |
| `point` | one sentence: the question and the answer. Write it before the hook |
| `hook` | the yellow card for the first 3 s (guide 03); `null` for none |
| `question` | `{"words": [first, last]}` word indices of the follower's question as read out; optional `"label"` |
| `drop` | `[first, last]` word index ranges to cut (inclusive) |
| `drop_why` | one reason per drop (for the checkpoint message and for you next time) |
| `fix` | word index → text on screen (spelling, punctuation «καλά;»). Keep the punctuation that ends a sentence |
| `nocap` | word ranges that get no captions |
| `cta` | `null`, or `{"keyword": "AI", "keyword_word": 120, "comment": [[a, b]], "bio": [[c, d]]}`: makes version A (link in bio, drops the `comment` words) and B (comment the keyword, drops the `bio` words) |
| `realign` | `[[first, last, from_s, to_s]]`: re-time words inside a window (merged restarts, below), then run `$PY tools/shorts.py align N` |
| `zoom` | override the base zoom (e.g. `1.08` for a close-up where the automatic one is too tight) |

## What gets cut *(rules from the first runs)*

- **Only mistakes and retakes.** No reordering, no tightening of the content, no cutting of "boring" parts.
- **The retake cue** («wait», «Οκ wait», or theirs in `channel.json`): cut the cue, and if the sentence before it was abandoned and said again, cut the first attempt too. Example: «Και ταυτόχρονα βοηθάει πάρα πολύ να μην του κάνεις κάθε φορά Wait» → cut all of it, keep the second attempt.
- **A cut-off first reading of the question** («…μόνο κο…») is a retake: keep the second reading.
- **Asides to people around them** («Όχι, όχι», a quiet «Γεια σας»): cut. They're quieter (~10 dB under the voice); check the level if unsure.
- **Pauses:** the pipeline cuts every pause over 0.28 s automatically and keeps at most 0.11 s of air each side. Nothing to do by hand.
- Framing changes every 2.4-4 s automatically (zoom 100/108% at sentence starts).

## Transcription traps (all seen on real clips)

- **Outdoors**, Whisper sometimes returns «Λίγο.» or «Υπότιτλοι …» for 20 s of clear speech. `asr` retries thin chunks in halves; if a stretch is still missing in `transcript.txt`, compare it with the contact sheets (mouth moving, no words) and tell them.
- **In long silences** (reading the phone) Whisper invents words («Σου ευχαριστώ.», «Φυσικά!»). If words appear where the sheets show them silent and reading, drop those indices.
- **Numbers:** «200.000» comes as «200» «.000»: joined on screen automatically; «ευρώ» after a number → «€».
- **Stretched words hide gaps and retakes.** Alignment can stretch the word before a pause over the whole pause («κάνει» 3.6 s). `build` trims any word longer than its letters allow and prints a «stretched» line. **Read every one:** a stretch can hide a restart that Whisper merged into one sentence («Και αν χρειάζεται» said twice, transcribed once). Check with `$PY tools/shorts.py window N FROM TO` (seconds): it transcribes that window in two halves and prints both; if the words repeat, put the kept attempt in `realign`, run `align N`, then `build N`.
- English words said in a Greek sentence may come out in Greek letters («κόρσεις» = "courses"): show them in English with `fix`, and add repeat offenders to `channel.json` `fixes`.
