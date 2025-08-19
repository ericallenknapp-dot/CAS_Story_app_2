
from flask import Flask, render_template, request, send_file
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import re, csv, json, math
from generator import make_plan, generate_story_with_keywords

app = Flask(__name__)
import os

def load_lexicon_dict(path):
    lex = {}
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            w = row["word"].strip().lower()
            lex[w] = {
                "initial": row["initial_phonemes"].strip(),
                "medial": row["medial_phonemes"].strip(),
                "final": row["final_phonemes"].strip(),
                "shape": row["syllable_shape"].strip()
            }
    return lex

import os
LEX_PATH = os.environ.get("CAS_LEXICON_PATH", app.root_path + "/cas_lexicon_expanded.csv")

THEME_PROMPTS = {
    "cookies": ["cookie jar", "plate of cookies", "crumb trail", "cookie box", "sharing cookies"],
    "park":    ["swing set", "slide", "ball game", "bench and tree", "picnic"],
    "pets":    ["paw print", "kitten", "dog bowl", "cat nap", "pet friends"],
    "space":   ["rocket ship", "moon and stars", "astronaut wave", "planet ring", "counting stars"],
    "farm":    ["red barn", "cow and calf", "tractor", "hay stack", "farm friends"]
}

# --- ICONS ---
def draw_cookie(c, cx, cy, r):
    c.circle(cx, cy, r)
    for i in range(6):
        ang = i * 60
        x = cx + 0.5*r*math.cos(math.radians(ang))
        y = cy + 0.5*r*math.sin(math.radians(ang))
        c.circle(x, y, r*0.08, fill=1)
def draw_jar(c, x, y, w, h):
    c.roundRect(x, y, w, h, 6); c.rect(x + 0.2*w, y + h, 0.6*w, h*0.15, stroke=1, fill=0)
def draw_ball(c, cx, cy, r):
    c.circle(cx, cy, r); c.line(cx - r, cy, cx + r, cy); c.line(cx, cy - r, cx, cy + r)
def draw_tree(c, x, y, w, h):
    c.rect(x + 0.45*w, y, 0.1*w, 0.3*h, stroke=1, fill=0); c.circle(x + 0.5*w, y + 0.65*h, 0.35*w)
def draw_rocket(c, x, y, w, h):
    c.ellipse(x, y, x + w, y + h); c.line(x + 0.2*w, y, x, y - 0.2*h); c.line(x + 0.8*w, y, x + w, y - 0.2*h); c.circle(x + 0.5*w, y + 0.6*h, 0.12*w)
def draw_moon(c, cx, cy, r):
    c.circle(cx, cy, r); c.setFillGray(1); c.circle(cx + r*0.4, cy + r*0.1, r); c.setFillGray(0)
def draw_star(c, cx, cy, r):
    pts = []
    for i in range(5):
        ang = math.radians(90 + i*72); pts.append((cx + r*math.cos(ang), cy + r*math.sin(ang)))
    for i in range(5):
        j = (i + 2) % 5; c.line(pts[i][0], pts[i][1], pts[j][0], pts[j][1])
def draw_paw(c, cx, cy, r):
    c.circle(cx, cy, r*0.5, fill=0); c.circle(cx - r*0.6, cy + r*0.6, r*0.25, fill=0); c.circle(cx + r*0.6, cy + r*0.6, r*0.25, fill=0); c.circle(cx - r*0.2, cy + r*1.0, r*0.25, fill=0); c.circle(cx + r*0.2, cy + r*1.0, r*0.25, fill=0)
def draw_cup(c, x, y, w, h):
    c.rect(x, y, w, h, stroke=1, fill=0); c.arc(x + w, y + h*0.2, x + 1.4*w, y + h*0.8, 270, 90)
def draw_sock(c, x, y, w, h):
    c.roundRect(x, y, w*0.7, h*0.7, 8); c.rect(x + w*0.5, y - h*0.2, w*0.4, h*0.2, stroke=1, fill=0)

ICON_MAP = {"cookie":"cookie","cookies":"cookie","jar":"jar","cup":"cup","sock":"sock","bag":"jar",
            "ball":"ball","tree":"tree","rocket":"rocket","moon":"moon","star":"star","paw":"paw",
            "dog":"paw","cat":"paw","pet":"paw"}

def draw_icon_by_word(c, area_x, area_y, area_w, area_h, word):
    kind = ICON_MAP.get((word or "").lower())
    if not kind: return
    cx = area_x + area_w/2; cy = area_y + area_h/2; size = min(area_w, area_h) * 0.35
    if kind == "cookie": draw_cookie(c, cx, cy, size)
    elif kind == "jar":  draw_jar(c, cx - size, cy - size*0.8, size*2, size*1.6)
    elif kind == "ball": draw_ball(c, cx, cy, size)
    elif kind == "tree": draw_tree(c, cx - size, cy - size, size*2, size*2)
    elif kind == "rocket": draw_rocket(c, cx - size, cy - size, size*2, size*2.2)
    elif kind == "moon": draw_moon(c, cx, cy, size)
    elif kind == "star": draw_star(c, cx, cy, size)
    elif kind == "paw": draw_paw(c, cx, cy - size*0.2, size*0.6)
    elif kind == "cup": draw_cup(c, cx - size, cy - size*0.6, size*2, size*1.2)
    elif kind == "sock": draw_sock(c, cx - size, cy - size*0.6, size*2, size*1.2)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

def analyze_coverage(story_text, targets, phrases):
    lex = load_lexicon_dict(LEX_PATH)
    pages = {}
    current = None
    for line in story_text.splitlines():
        m = re.match(r"Page\s+(\d+)", line.strip(), re.I)
        if m:
            current = int(m.group(1)); pages[current] = {"lines": [], "footnotes": []}; continue
        if current is None: continue
        if line.strip().startswith("FOOTNOTE:"):
            pages[current]["footnotes"].append(line.strip())
        elif line.strip():
            pages[current]["lines"].append(line.strip())

    per_page = []
    totals = {f"{t['phoneme'].lower()}_{t['position']}":0 for t in targets}
    for p, data in pages.items():
        text = " ".join(data["lines"]).lower()
        words = re.findall(r"[a-z']+", text)
        counts = {}
        unknown = []
        for w in words:
            info = lex.get(w)
            if not info:
                unknown.append(w); continue
            for t in targets:
                ph = t["phoneme"].lower().strip(); pos = t["position"]
                key = f"{ph}_{pos}"
                if info[pos].startswith(ph):
                    counts[key] = counts.get(key,0) + 1
        for k,v in counts.items():
            totals[k] = totals.get(k,0) + v
        per_page.append({"page": p, "counts": counts, "unknown": unknown})

    all_text = " ".join([" ".join(v["lines"]) for v in pages.values()]).lower()
    phrase_counts = {ph: all_text.count(ph.lower()) for ph in phrases}

    return {"pages_map": pages, "per_page": sorted(per_page, key=lambda x: x["page"]),
            "totals": totals, "phrase_counts": phrase_counts}

def draw_illustration_box(c, x, y, w, h, label, word=None):
    c.rect(x, y, w, h)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(x + w/2, y + h - 12, f"Illustration: {label}")
    if word:
        draw_icon_by_word(c, x + 10, y + 10, w - 20, h - 30, word)

def story_to_pdf_bytes(title, story_text, page_keywords, coverage, targets, theme):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width/2, height/2 + 20, title)
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height/2 - 10, f"Theme: {theme.title()}")
    label = THEME_PROMPTS.get(theme, THEME_PROMPTS["cookies"])[0]
    c.rect(2.25*inch, height/2 - 2.2*inch, 3.5*inch, 1.5*inch)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(2.25*inch + 1.75*inch, height/2 - 2.2*inch + 0.75*inch, f"Illustration: {label}")
    c.showPage()

    lines = story_text.splitlines()
    block = []
    page_ix = 0
    def draw_block(block_lines, page_ix, word):
        y = height - 1.2*inch
        prompts = THEME_PROMPTS.get(theme, THEME_PROMPTS["cookies"])
        label = prompts[page_ix % len(prompts)]
        draw_illustration_box(c, 1*inch, y - 1.7*inch, width - 2*inch, 1.2*inch, label, word=word)
        y -= 2.0*inch
        for b in block_lines:
            if b.startswith("FOOTNOTE:"):
                c.setFont("Helvetica-Oblique", 9)
            elif b.lower().startswith("page "):
                c.setFont("Helvetica-Bold", 16)
            else:
                c.setFont("Helvetica", 22)
            c.drawString(1*inch, y, b[:95])
            y -= 0.4*inch
            if y < 1*inch:
                c.showPage(); y = height - 1.2*inch
        c.showPage()

    for ln in lines:
        if ln.strip().lower().startswith("page "):
            if block:
                main_word = page_keywords[page_ix] if page_ix < len(page_keywords) else None
                draw_block(block, page_ix, main_word); block = []; page_ix += 1
            block.append(ln.strip())
        else:
            if ln.strip(): block.append(ln.strip())
    if block:
        main_word = page_keywords[page_ix] if page_ix < len(page_keywords) else None
        draw_block(block, page_ix, main_word)

    # Coverage summary page
    c.setFont("Helvetica-Bold", 20)
    c.drawString(1*inch, height - 1.0*inch, "Coverage Summary")
    y = height - 1.4*inch
    c.setFont("Helvetica", 12)
    c.drawString(1*inch, y, "Targets:"); y -= 0.2*inch
    for t in targets:
        key = f"{t['phoneme'].lower()}_{t['position']}"
        val = coverage["totals"].get(key, 0)
        goal = t.get("reps_per_page",0) * len(coverage["per_page"])
        c.drawString(1.2*inch, y, f"{t['phoneme']} ({t['position']}): {val} / goal {goal}"); y -= 0.2*inch
    y -= 0.1*inch
    c.drawString(1*inch, y, "Phrases:"); y -= 0.2*inch
    for ph, val in coverage["phrase_counts"].items():
        c.drawString(1.2*inch, y, f"{ph}: {val}"); y -= 0.2*inch
    y -= 0.2*inch
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(1*inch, y, "Note: Counts are approximate; use clinician judgment.")
    c.showPage()

    c.save(); buf.seek(0); return buf

@app.route("/preview", methods=["POST"])
def preview():
    # Handle uploaded lexicon (if any)
    up = request.files.get('lexicon')
    if up and up.filename.endswith('.csv'):
        save_path = os.path.join(app.root_path, 'user_lexicon.csv')
        up.save(save_path)
        os.environ['CAS_LEXICON_PATH'] = save_path
    title = request.form.get("title","CAS Story")
    mode = request.form.get("mode","mixed")
    theme = request.form.get("theme","cookies")
    pages = int(request.form.get("pages","10"))
    phrases = [p.strip() for p in request.form.get("phrases","I want a cookie,I go,You go,Out").split(",") if p.strip()]
    shapes = request.form.getlist("shapes") or ["CV","CVC"]

    targets = []
    for i in range(1,6):
        ph = request.form.get(f"t{i}_phoneme","").strip()
        pos = request.form.get(f"t{i}_position","").strip().lower()
        reps = request.form.get(f"t{i}_reps","").strip()
        if ph and pos in {"initial","medial","final"}:
            try:
                reps = int(reps) if reps else 3
            except ValueError:
                reps = 3
            targets.append({"phoneme": ph, "position": pos, "reps_per_page": reps})
    plan = make_plan(mode=mode, pages=pages, phrases=phrases, targets=targets)
    story_text, page_keywords = generate_story_with_keywords(plan, shapes=tuple(shapes))
    cov = analyze_coverage(story_text, targets if targets else [{"phoneme":"w","position":"initial"},{"phoneme":"k","position":"final"}], phrases)

    totals_tbl = []
    for t in (targets if targets else [{"phoneme":"w","position":"initial","reps_per_page":4},{"phoneme":"k","position":"final","reps_per_page":3}]):
        key = f"{t['phoneme'].lower()}_{t['position']}"
        totals_tbl.append({"key": key, "count": cov["totals"].get(key,0), "goal": t.get("reps_per_page",0)*len(cov["per_page"])})

    checklist = build_checklist(cov, targets if targets else [{"phoneme":"w","position":"initial","reps_per_page":4},{"phoneme":"k","position":"final","reps_per_page":3}], phrases, story_text, shapes)

    hidden_fields = {}
    for k in ["title","mode","theme","pages","phrases","t1_phoneme","t1_position","t1_reps","t2_phoneme","t2_position","t2_reps","t3_phoneme","t3_position","t3_reps","t4_phoneme","t4_position","t4_reps","t5_phoneme","t5_position","t5_reps"]:
        v = request.form.get(k,"")
        hidden_fields[k] = v
    for s in shapes:
        hidden_fields.setdefault("shapes", s)

    target_keys = [f"{t['phoneme'].lower()}_{t['position']}" for t in (targets if targets else [{"phoneme":"w","position":"initial"},{"phoneme":"k","position":"final"}])]
    return render_template("preview.html",
        title=title, mode=mode, theme=theme, pages=pages, phrases=phrases, shapes=shapes,
        checklist=checklist, totals=totals_tbl,
        phrase_counts=[{"phrase":ph,"count":cov["phrase_counts"].get(ph,0)} for ph in phrases],
        target_keys=target_keys,
        per_page=cov["per_page"],
        hidden_fields=hidden_fields
    )

def build_checklist(coverage, targets, phrases, story_text, allowed_shapes):
    pages = coverage["per_page"]
    totals = coverage["totals"]
    pages_map = coverage["pages_map"]
    total_pages = len(pages)
    items = []

    # 1. Target totals vs goal
    goal_ok = True
    notes = []
    for t in targets:
        key = f"{t['phoneme'].lower()}_{t['position']}"
        goal = t.get("reps_per_page",0) * total_pages
        got = totals.get(key,0)
        if got < goal:
            goal_ok = False
            notes.append(f"{key}: {got}/{goal}")
    items.append({"item":"Targets meet total goal", "ok": goal_ok, "notes": "; ".join(notes) or "All met"})

    # 2. Position distribution
    pos_ok = True
    pos_notes = []
    for t in targets:
        key = f"{t['phoneme'].lower()}_{t['position']}"
        pages_with = sum(1 for p in pages if p["counts"].get(key,0) > 0)
        if pages_with < max(1, total_pages//2):
            pos_ok = False; pos_notes.append(f"{key} on {pages_with}/{total_pages} pages")
    items.append({"item":"Position coverage across pages", "ok": pos_ok, "notes": "; ".join(pos_notes) or "Balanced"})

    # 3. Prosody prompts
    prosody_ok = ("drum" in story_text.lower()) or ("clap" in story_text.lower())
    items.append({"item":"Prosody prompts included", "ok": prosody_ok, "notes": "Look for: 'TA-ta', 'clap'"})

    # 4. Parent cues
    cue_pages = sum(1 for line in story_text.splitlines() if line.startswith("FOOTNOTE:"))
    cues_ok = (cue_pages >= total_pages)
    items.append({"item":"Parent articulatory cues present", "ok": cues_ok, "notes": f"Footnotes: {cue_pages} / pages: {total_pages}"})

    # 5. Phrase repetition
    phr_ok = any(coverage["phrase_counts"].get(ph,0) >= 2 for ph in phrases)
    items.append({"item":"Core phrases repeated", "ok": phr_ok, "notes": ", ".join([f"{ph}:{coverage['phrase_counts'].get(ph,0)}" for ph in phrases])})

    # 6. Shape adherence on target lines
    lex = load_lexicon_dict(LEX_PATH)
    out_of_shape = 0; checked = 0
    for pnum, pdata in pages_map.items():
        lines = [ln for ln in pdata["lines"] if ln.strip()]
        if not lines: continue
        target_line = lines[-1].lower()
        for w in re.findall(r"[a-z']+", target_line):
            info = lex.get(w)
            if info:
                checked += 1
                if allowed_shapes and info["shape"] not in set(allowed_shapes):
                    out_of_shape += 1
    shape_ok = (out_of_shape == 0)
    items.append({"item":"Target lines obey selected shapes", "ok": shape_ok, "notes": f"out-of-shape tokens: {out_of_shape} / {checked}"})

    for it in items:
        it["status_label"] = "✔ OK" if it["ok"] else "⚠ Check"
        it["status_class"] = "ok" if it["ok"] else "warn"
    return items

@app.route("/generate", methods=["POST"])
def generate():
    # Handle uploaded lexicon (if any)
    up = request.files.get('lexicon')
    if up and up.filename.endswith('.csv'):
        save_path = os.path.join(app.root_path, 'user_lexicon.csv')
        up.save(save_path)
        os.environ['CAS_LEXICON_PATH'] = save_path
    title = request.form.get("title","CAS Story")
    mode = request.form.get("mode","mixed")
    theme = request.form.get("theme","cookies")
    pages = int(request.form.get("pages","10"))
    phrases = [p.strip() for p in request.form.get("phrases","I want a cookie,I go,You go,Out").split(",") if p.strip()]
    shapes = request.form.getlist("shapes") or ["CV","CVC"]

    targets = []
    for i in range(1,6):
        ph = request.form.get(f"t{i}_phoneme","").strip()
        pos = request.form.get(f"t{i}_position","").strip().lower()
        reps = request.form.get(f"t{i}_reps","").strip()
        if ph and pos in {"initial","medial","final"}:
            try:
                reps = int(reps) if reps else 3
            except ValueError:
                reps = 3
            targets.append({"phoneme": ph, "position": pos, "reps_per_page": reps})
    plan = make_plan(mode=mode, pages=pages, phrases=phrases, targets=targets)
    story_text, page_keywords = generate_story_with_keywords(plan, shapes=tuple(shapes))
    cov = analyze_coverage(story_text, targets if targets else [{"phoneme":"w","position":"initial"},{"phoneme":"k","position":"final"}], phrases)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width/2, height/2 + 20, title)
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height/2 - 10, f"Theme: {theme.title()}")
    label = THEME_PROMPTS.get(theme, THEME_PROMPTS["cookies"])[0]
    c.rect(2.25*inch, height/2 - 2.2*inch, 3.5*inch, 1.5*inch)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(2.25*inch + 1.75*inch, height/2 - 2.2*inch + 0.75*inch, f"Illustration: {label}")
    c.showPage()

    lines = story_text.splitlines()
    block = []
    page_ix = 0

    def draw_illustration_box(c, x, y, w, h, label, word=None):
        c.rect(x, y, w, h)
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(x + w/2, y + h - 12, f"Illustration: {label}")
        if word:
            draw_icon_by_word(c, x + 10, y + 10, w - 20, h - 30, word)

    def draw_block(block_lines, page_ix, word):
        y = height - 1.2*inch
        prompts = THEME_PROMPTS.get(theme, THEME_PROMPTS["cookies"])
        label = prompts[page_ix % len(prompts)]
        draw_illustration_box(c, 1*inch, y - 1.7*inch, width - 2*inch, 1.2*inch, label, word=word)
        y -= 2.0*inch
        for b in block_lines:
            if b.startswith("FOOTNOTE:"):
                c.setFont("Helvetica-Oblique", 9)
            elif b.lower().startswith("page "):
                c.setFont("Helvetica-Bold", 16)
            else:
                c.setFont("Helvetica", 22)
            c.drawString(1*inch, y, b[:95])
            y -= 0.4*inch
            if y < 1*inch:
                c.showPage(); y = height - 1.2*inch
        c.showPage()

    for ln in lines:
        if ln.strip().lower().startswith("page "):
            if block:
                main_word = page_keywords[page_ix] if page_ix < len(page_keywords) else None
                draw_block(block, page_ix, main_word); block = []; page_ix += 1
            block.append(ln.strip())
        else:
            if ln.strip(): block.append(ln.strip())
    if block:
        main_word = page_keywords[page_ix] if page_ix < len(page_keywords) else None
        draw_block(block, page_ix, main_word)

    # Coverage summary page
    c.setFont("Helvetica-Bold", 20)
    c.drawString(1*inch, height - 1.0*inch, "Coverage Summary")
    y = height - 1.4*inch
    c.setFont("Helvetica", 12)
    c.drawString(1*inch, y, "Targets:"); y -= 0.2*inch
    for t in (targets if targets else [{"phoneme":"w","position":"initial","reps_per_page":4},{"phoneme":"k","position":"final","reps_per_page":3}]):
        key = f"{t['phoneme'].lower()}_{t['position']}"
        val = cov["totals"].get(key, 0)
        goal = t.get("reps_per_page",0) * len(cov["per_page"])
        c.drawString(1.2*inch, y, f"{t['phoneme']} ({t['position']}): {val} / goal {goal}"); y -= 0.2*inch
    y -= 0.1*inch
    c.drawString(1*inch, y, "Phrases:"); y -= 0.2*inch
    for ph, val in cov["phrase_counts"].items():
        c.drawString(1.2*inch, y, f"{ph}: {val}"); y -= 0.2*inch
    y -= 0.2*inch
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(1*inch, y, "Note: Counts are approximate; use clinician judgment.")
    c.showPage()

    c.save(); buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="cas_story.pdf")
