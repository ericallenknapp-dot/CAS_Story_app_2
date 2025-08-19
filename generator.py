
import random, json, pandas as pd
from pathlib import Path

LEX_PATH = Path(__file__).parent / "cas_lexicon_expanded.csv"
CUE_PATH = Path(__file__).parent / "cas_cue_bank.json"

def load_assets(lex_path=LEX_PATH, cue_path=CUE_PATH):
    lex_df = pd.read_csv(lex_path)
    cue_bank = json.loads(Path(cue_path).read_text())
    return lex_df, cue_bank

def get_candidates(df, phoneme, position, shapes=("CV","CVC")):
    pos_col = {"initial":"initial_phonemes","medial":"medial_phonemes","final":"final_phonemes"}[position]
    mask = df[pos_col].astype(str).str.startswith(phoneme) & df["syllable_shape"].isin(shapes)
    return df[mask].copy()

def build_line_from_targets(df, targets_spec, max_words=6, avoid=None, shapes=("CV","CVC")):
    avoid = set(avoid or [])
    words = []
    pool_by_target = {}
    for (ph,pos,count) in targets_spec:
        pool = get_candidates(df, ph, pos, shapes)
        pool = pool[~pool["word"].isin(avoid)]
        pool_by_target[(ph,pos)] = pool["word"].tolist()
    tgt_list = []
    for ph,pos,count in targets_spec:
        tgt_list += [(ph,pos)]*max(0,int(count))
    random.shuffle(tgt_list)
    for ph,pos in tgt_list:
        pool = pool_by_target.get((ph,pos), [])
        pick = None
        for w in pool:
            if w not in words and len(" ".join(words+[w]).split()) <= max_words:
                pick = w; break
        if pick is None and pool:
            pick = pool[0]
        if pick:
            words.append(pick)
        if len(words) >= max_words:
            break
    return " ".join(words[:max_words]).strip()

def footnote_for_targets(targets_spec, cue_bank):
    cues = []
    seen = set()
    for ph,pos,_ in targets_spec:
        if ph in seen: 
            continue
        seen.add(ph)
        if ph in cue_bank:
            cues.append(f"{ph} — {cue_bank[ph][0]}")
    if "prosody" in cue_bank:
        cues.append(cue_bank["prosody"][0])
    return "FOOTNOTE: " + " | ".join(cues[:3])

def make_plan(mode="mixed", pages=10, phrases=None, targets=None):
    phrases = phrases or ["I want a cookie","I go","You go","Out"]
    targets = targets or [{"phoneme":"w","position":"initial","reps_per_page":4},
                          {"phoneme":"k","position":"final","reps_per_page":3}]
    norm_targets = []
    for t in targets:
        try:
            ph = str(t["phoneme"]).strip()
            pos = str(t["position"]).strip().lower()
            reps = int(t.get("reps_per_page", 3))
            if ph and pos in {"initial","medial","final"} and reps >= 0:
                norm_targets.append((ph, pos, reps))
        except Exception:
            continue
    if not norm_targets:
        norm_targets = [("w","initial",4),("k","final",3)]
    plan = []
    for i in range(1, pages+1):
        if mode == "blocked":
            pick = norm_targets[(i-1) % len(norm_targets)]
            req = [pick]
        else:
            req = norm_targets[:]
        phs = []
        if i in (1,4,7,10): phs.append("I want a cookie")
        elif i in (2,5,8): phs.append("I go")
        elif i in (3,6,9): phs.append("You go")
        if i in (4,8): phs.append("Out")
        plan.append({"page": i, "targets": req, "phrases": phs})
    return plan

def generate_story_with_keywords(plan, shapes=("CV","CVC")):
    """
    Returns: (story_text, page_keywords)
    page_keywords: list of a 'main' word for each page (from target line).
    """
    lex_df, cue_bank = load_assets()
    pages = []
    used = set()
    page_keywords = []
    for p in plan:
        lines = []
        if p["phrases"]:
            lines.append(p["phrases"][0])
        line2 = build_line_from_targets(lex_df, p["targets"], max_words=6, avoid=used, shapes=shapes)
        used.update(line2.split())
        if line2:
            lines.append(line2)
            key = line2.split()[0].lower()
        else:
            key = "cookie"
        foot = footnote_for_targets(p["targets"], cue_bank)
        pages.append((lines, foot))
        page_keywords.append(key)
    out_lines = []
    for i,(lines,foot) in enumerate(pages, start=1):
        out_lines.append(f"Page {i}")
        for ln in lines:
            out_lines.append(ln)
        out_lines.append(foot)
        out_lines.append("")
    return "\n".join(out_lines), page_keywords

def generate_story(plan, shapes=("CV","CVC")):
    text, _ = generate_story_with_keywords(plan, shapes)
    return text
