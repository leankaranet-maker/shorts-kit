"""Greek forced alignment helpers (used by tools/shorts.py align).

Whisper's word times are loose (a sentence's first word often starts up to a
second early). Every word is re-timed against the audio with a Greek wav2vec2
CTC model (the WhisperX approach): the words are spelled out as characters and
aligned to the model's per-20 ms character probabilities with a CTC Viterbi pass.

For alignment only, digits become Greek number words and English words are
transliterated (add new English words to LATIN when they come up); the
transcript text itself is unchanged.
"""
import re
import unicodedata

import numpy as np

MODEL = "jonatasgrosman/wav2vec2-large-xlsr-53-greek"
STRIDE = 0.02  # seconds per model frame

UNITS = ["μηδέν", "ένα", "δύο", "τρία", "τέσσερα", "πέντε", "έξι", "επτά", "οκτώ", "εννιά", "δέκα", "έντεκα", "δώδεκα",
         "δεκατρία", "δεκατέσσερα", "δεκαπέντε", "δεκαέξι", "δεκαεπτά", "δεκαοκτώ", "δεκαεννιά"]
TENS = {2: "είκοσι", 3: "τριάντα", 4: "σαράντα", 5: "πενήντα", 6: "εξήντα", 7: "εβδομήντα", 8: "ογδόντα", 9: "ενενήντα"}
HUNDREDS = {1: "εκατό", 2: "διακόσια", 3: "τριακόσια", 4: "τετρακόσια", 5: "πεντακόσια", 6: "εξακόσια", 7: "επτακόσια",
            8: "οκτακόσια", 9: "εννιακόσια"}
LATIN = {"meta": "μετα", "facebook": "φεισμπουκ", "budget": "μπατζετ", "ebook": "ιμπουκ", "e": "ι", "book": "μπουκ",
         "marketing": "μαρκετινγκ", "interests": "ιντερεστς", "engaged": "ενγκεϊτζντ", "shoppers": "σοπερς",
         "creatives": "κριεϊτιβς", "creative": "κριεϊτιβ", "offer": "οφερ", "conversion": "κονβερζιον", "event": "ιβεντ",
         "done": "νταν", "with": "γουιθ", "you": "γιου", "month": "μανθ", "ltv": "ελτιβι", "ads": "αντς", "ai": "εϊαϊ",
         "peak": "πικ", "maximum": "μαξιμουμ", "challenge": "τσαλεντζ", "no": "νοου", "again": "αγκεν", "lets": "λετς",
         "let's": "λετς", "do": "ντου", "that": "νταθ", "last": "λαστ", "part": "παρτ", "go": "γκοου"}
LETTERS = dict(zip("abcdefghijklmnopqrstuvwxyz",
                   ["α", "μπ", "κ", "ντ", "ε", "φ", "γκ", "χ", "ι", "τζ", "κ", "λ", "μ", "ν", "ο", "π", "κ", "ρ", "σ", "τ",
                    "ου", "β", "ου", "ξ", "ι", "ζ"]))
SYMBOLS = {"€": "ευρώ", "$": "δολάρια", "%": "τοις εκατό"}


def num_words(n: int) -> str:
    if n < 20:
        return UNITS[n]
    if n < 100:
        t, u = divmod(n, 10)
        return TENS[t] + ("" if u == 0 else " " + UNITS[u])
    if n < 1000:
        h, r = divmod(n, 100)
        head = "εκατόν" if h == 1 and r else HUNDREDS[h]
        return head + ("" if r == 0 else " " + num_words(r))
    th, r = divmod(n, 1000)
    head = "χίλια" if th == 1 else num_words(th) + " χιλιάδες"
    return head + ("" if r == 0 else " " + num_words(r))


def spoken(word: str) -> str:
    """The word as pronounceable Greek letters (for alignment only)."""
    out = []
    for tok in re.findall(r"\d+|[A-Za-z']+|[^\sA-Za-z\d]+", word):
        if tok.isdigit():
            out.append(num_words(int(tok)))
        elif re.fullmatch(r"[A-Za-z']+", tok):
            low = tok.lower()
            out.append(LATIN.get(low) or "".join(LETTERS.get(c, "") for c in low))
        else:
            out.append("".join(SYMBOLS.get(c, c) if c in SYMBOLS else c for c in tok))
    return " ".join(out)


def chars(word: str, vocab: dict) -> list:
    s = unicodedata.normalize("NFC", spoken(word)).upper().replace("ΐ", "Ϊ").replace("ΰ", "Ϋ")
    s = unicodedata.normalize("NFC", s)
    return [vocab[c] for c in s if c in vocab and c not in "|'-"]


def viterbi(em: np.ndarray, tokens: list, blank: int) -> np.ndarray:
    """CTC forced alignment. Returns, per frame, the token index or -1 (blank)."""
    T, U = em.shape[0], len(tokens)
    S = 2 * U + 1
    ext = np.full(S, blank)
    ext[1::2] = tokens
    allow_skip = np.zeros(S, bool)
    for s in range(3, S, 2):
        allow_skip[s] = ext[s] != ext[s - 2]
    alpha = np.full((T, S), -np.inf)
    back = np.zeros((T, S), np.int8)  # 0 stay, 1 from s-1, 2 from s-2
    alpha[0, 0] = em[0, blank]
    if S > 1:
        alpha[0, 1] = em[0, ext[1]]
    for t in range(1, T):
        prev = alpha[t - 1]
        stay = prev
        one = np.concatenate(([-np.inf], prev[:-1]))
        two = np.concatenate(([-np.inf, -np.inf], prev[:-2]))
        two = np.where(allow_skip, two, -np.inf)
        cand = np.stack([stay, one, two])
        best = cand.argmax(0)
        alpha[t] = cand[best, np.arange(S)] + em[t, ext]
        back[t] = best
    s = S - 1 if alpha[T - 1, S - 1] >= alpha[T - 1, S - 2] else S - 2
    path = np.empty(T, int)
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(back[t, s])
    return np.where(path % 2 == 1, (path - 1) // 2, -1)
