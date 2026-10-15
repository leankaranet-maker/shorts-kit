# 3. On screen: hook, question card, captions, CTA

All of it is drawn by `video/src/short/NativeShort.tsx` from
`work/shorts/NN/timeline-A.json`. Positions are in the 1080×1920 frame.

| Element | Look | Where | When |
| --- | --- | --- | --- |
| **Hook card** | yellow `#FDE725`, dark text, Fira Sans 800 62 px, rounded | top 240, centred | first 3 s |
| **Question card** | white comment card, grey avatar, label «Ερώτηση από follower» 24 px, text 34 px, 680 px wide; the word being read darkens | under the chin, never past y 1490 | from frame 0 (or when the reading starts) until the reading ends; captions off meanwhile |
| **Captions** | word by word, 2-4 words a page (≤ 22 characters, one line), Fira Sans 800 55 px, white with an 8 px dark outline, the word being said in yellow | centred, top 26 px under the chin (85th percentile over the Short), never below y 1404 | the whole Short except the question |
| **CTA** | yellow card: «Link στο bio» with a link icon (A), or «Γράψε στα σχόλια KEYWORD …» (B); texts from `channel.json` | top 240 | last ~3.5 s, or from the keyword when it's said (B) |

## The hook card

- From the `point`: **the viewer's pain as a question, ≤ 7 words.** «Πολλά λεφτά, καθόλου χρόνος;», «Viral βίντεο, μηδέν πελάτες;», «Προσέλαβες βοηθό και δουλεύεις περισσότερο;»
- **Never the words being spoken at that moment**, and not the question card's words: the same words twice on screen at once is a waste of the first 3 seconds.
- Fits in two lines. If it doesn't, shorten it.

## Captions

- Made from what was said: words exactly as said, with Whisper's spelling fixed (`fix` per word, `channel.json` `fixes` for the whole channel). Digits for numbers, € and $ after the number.
- A new page at every sentence start and every cut pause. Names and brands in `channel.json` `proper` don't start a new page.
- A final full stop or comma is dropped on screen.
- No em dashes anywhere.

## CTA

**None unless the clip says one** *(rule from the first runs)*. If they say
"comment X", make versions A and B (guide 02, `cta`). Never invent a CTA they didn't say.

## Safe zones (TikTok, Reels, Shorts and Facebook UI)

| Zone | Keep clear |
| --- | --- |
| Top | y < 220 (search, tabs) |
| Bottom | y > 1500 (title, description, account name, music) |
| Right | x > 900, y 700-1500 (like, comment, share) |

`stills` draws these zones in red. Text and the face stay out of them.

## Sound

Two soft pops only: when the question card pops in after frame 0, and when the
CTA appears. No music unless asked.
