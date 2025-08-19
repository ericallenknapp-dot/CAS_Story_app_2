# CAS Story Webapp

Generate **custom storybooks for Childhood Apraxia of Speech (CAS)**.  
Parents and therapists can enter target sounds, phrases, and syllable shapes, then download a themed PDF with **practice stories**, **icons/placeholders**, and **parent cues**.

---

## ✨ Features
- **Custom Targets**: enter up to 5 phoneme + position combos (initial/medial/final).
- **Practice Modes**: 
  - *Blocked*: one target per page.  
  - *Mixed*: all targets on each page.
- **Core Phrases**: repeatable functional phrases (e.g., “I want a cookie”).
- **Validator Feedback**: preview coverage totals, per-page counts, and a CAS checklist before exporting.
- **Themes + Icons**: cookie, park, pets, space, and farm — each page gets a themed placeholder and simple icon.
- **Syllable Shape Controls**: restrict practice words to CV, CVC, etc.
- **Custom Lexicon Upload**: drop in your own CSV word list; app uses it instantly.

---

## 🚀 Quick Start

```bash
# clone repo and enter it
git clone https://github.com/YOURNAME/cas-story-webapp.git
cd cas-story-webapp

# create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# run
python app.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 📱 Preview on iPhone
- Make sure your computer and phone are on the same Wi-Fi.  
- Find your computer’s local IP (e.g., `192.168.1.23`).  
- On your phone’s Safari/Chrome, go to:  
  ```
  http://192.168.1.23:8000
  ```
- Or use a tunnel service like **ngrok** if you want to share outside your home network.

---

## 🌐 Deploy to Render (free)
1. Push this repo to GitHub.  
2. Go to [Render.com](https://render.com) → *New Web Service*.  
3. Connect your repo.  
4. Settings:
   - Build Command:  
     ```bash
     pip install -r requirements.txt
     ```
   - Start Command:  
     ```bash
     gunicorn app:app
     ```
5. Click **Deploy**.  
6. Get your link (e.g., `https://cas-stories.onrender.com`) and open it on your phone.

---

## 📖 Lexicon Options
### Default
A small starter lexicon is included.

### Build a bigger one
```bash
pip install nltk wordfreq pandas
python -c "import nltk; nltk.download('cmudict')"
python tools/build_lexicon.py --max_sylls 2 --outfile cas_lexicon_expanded.csv
```

### Upload custom
On the form, use **Lexicon (CSV upload)**.  
Your file must include columns:

```
word, syllable_shape, initial_phonemes, medial_phonemes, final_phonemes
```

---

## ✅ CAS Validation Checklist
The preview screen runs a quick check:
- Targets meet your reps/page × pages goals
- Positions covered across multiple pages
- Parent cues appear on each page
- Prosody prompts included
- Core phrases repeated

---

## 📂 Project Structure
```
app.py              # Flask app
generator.py        # story + filler logic
templates/          # HTML pages
cas_lexicon_expanded.csv  # starter lexicon
cas_cue_bank.json   # parent cue bank
tools/build_lexicon.py    # build large lexicon from CMUdict
requirements.txt
Procfile            # for Render
README.md
```

---

## ⚖️ Disclaimer
This tool is **not a substitute for speech therapy**.  
It is designed to support practice planned by a qualified **Speech-Language Pathologist (SLP)**.
