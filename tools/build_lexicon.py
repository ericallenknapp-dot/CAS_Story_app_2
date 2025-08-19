
"""
Build a CAS-friendly lexicon CSV from the CMU Pronouncing Dictionary.

What you get:
- word, syllable_shape, initial_phonemes, medial_phonemes, final_phonemes
- phonemes are mapped from ARPABET to simple lowercase tokens (e.g., SH->"sh", K->"k", W->"w")
- shape is derived from phones (V for vowels, C for consonants), e.g., CVC, CVCV, etc.
- filters for kid-friendly words: <= 2 syllables by default, alphabetic only, frequency cutoff

Usage:
    python tools/build_lexicon.py --minfreq 2e-6 --max_sylls 2 --outfile cas_lexicon_expanded.csv

Requires:
    pip install nltk wordfreq pandas
    python -c "import nltk; nltk.download('cmudict')"
"""

import argparse, re, pandas as pd
from wordfreq import zipf_frequency
import nltk
from nltk.corpus import cmudict

ARPABET_VOWELS = {"AA","AE","AH","AO","AW","AY","EH","ER","EY","IH","IY","OW","OY","UH","UW"}
# Map ARPABET (no stress digits) -> simple tokens used by the app
MAP = {
    # consonants
    "P":"p","B":"b","T":"t","D":"d","K":"k","G":"g",
    "CH":"ch","JH":"j","F":"f","V":"v","TH":"th","DH":"dh",
    "S":"s","Z":"z","SH":"sh","ZH":"zh","HH":"h","M":"m",
    "N":"n","NG":"ng","L":"l","R":"r","Y":"y","W":"w",
    # vowels (reduce to letters that parents recognize; you can refine later)
    "AA":"aa","AE":"ae","AH":"uh","AO":"aw","AW":"ow","AY":"ai",
    "EH":"eh","ER":"er","EY":"ey","IH":"ih","IY":"ee","OW":"oh",
    "OY":"oy","UH":"uh","UW":"oo"
}

def strip_stress(p):
    return re.sub(r"\d$", "", p)

def phones_to_shape(phones):
    s = []
    for p in phones:
        base = strip_stress(p)
        s.append("V" if base in ARPABET_VOWELS else "C")
    # collapse repeats: e.g., CCVCC -> CCVCC (kept as-is)
    return "".join(s)

def phones_to_simple(phones):
    out = []
    for p in phones:
        base = strip_stress(p)
        out.append(MAP.get(base, base.lower()))
    return out

def to_positions(simple):
    """Return (initial, medial, final) strings; medial can be empty."""
    if not simple:
        return "","",""
    initial = simple[0]
    final = simple[-1] if len(simple)>1 else ""
    medial = " ".join(simple[1:-1]) if len(simple)>2 else ""
    return initial, medial, final

def is_child_friendly(word):
    # basic filter: letters only, no apostrophes/hyphens, not ALL CAPS (acronyms)
    return word.isalpha() and word.islower()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minfreq", type=float, default=2e-6, help="minimum wordfreq (Zipf≈3)")
    ap.add_argument("--max_sylls", type=int, default=2, help="maximum syllables to include")
    ap.add_argument("--outfile", type=str, default="cas_lexicon_expanded.csv")
    args = ap.parse_args()

    entries = cmudict.dict()  # word -> list of phone sequences
    rows = []
    for word, prons in entries.items():
        if not is_child_friendly(word):
            continue
        # pick the first pronunciation
        phones = prons[0]
        # count syllables as number of vowel phones
        sylls = sum(1 for p in phones if strip_stress(p) in ARPABET_VOWELS)
        if sylls > args.max_sylls:
            continue
        # frequency filter
        # zipf_frequency returns ~0..7; we convert to linear by 10**(zipf-6) if needed,
        # but simpler: keep if zipf >= 3.0  (~1 per million) or use minfreq numeric cutoff.
        zipf = zipf_frequency(word, 'en')
        if zipf < 3.0:
            continue
        shape = phones_to_shape(phones)
        simple = phones_to_simple(phones)
        ini, med, fin = to_positions(simple)
        rows.append({
            "word": word,
            "syllable_shape": shape,
            "initial_phonemes": ini,
            "medial_phonemes": med,
            "final_phonemes": fin
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["word"])
    # sort by length then by word for consistency
    df["len"] = df["word"].str.len()
    df = df.sort_values(["len","word"]).drop(columns=["len"])
    df.to_csv(args.outfile, index=False)
    print(f"Saved {len(df)} words to {args.outfile}")

if __name__ == "__main__":
    main()
