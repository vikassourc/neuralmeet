import streamlit as st
import time
import os
import re
import json
import uuid
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from fpdf import FPDF

from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_action_items, extract_key_decisions, extract_questions
from core.rag_engine import build_rag_chain, ask_question

load_dotenv()

# ── Persistence ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TRANSCRIPTS_DIR = os.path.join(DATA_DIR, "transcripts")
INDEX_PATH = os.path.join(DATA_DIR, "history.json")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

def _load_index():
    if not os.path.exists(INDEX_PATH):
        return []
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_index(index):
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

def save_meeting(result, source, language):
    meeting_id = uuid.uuid4().hex[:12]
    transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{meeting_id}.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(result["transcript"])
    entry = {
        "id": meeting_id, "title": result["title"], "source": source,
        "language": language, "summary": result["summary"],
        "action_items": result["action_items"], "key_decisions": result["key_decisions"],
        "open_questions": result["open_questions"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "transcript_path": transcript_path,
    }
    index = _load_index()
    index.insert(0, entry)
    _save_index(index)
    return meeting_id

def list_meetings():
    return _load_index()

def get_meeting(meeting_id):
    for entry in _load_index():
        if entry["id"] == meeting_id:
            entry = dict(entry)
            entry["transcript"] = open(entry["transcript_path"], "r", encoding="utf-8").read() if os.path.exists(entry["transcript_path"]) else ""
            return entry
    return None

def delete_meeting(meeting_id):
    remaining = []
    for entry in _load_index():
        if entry["id"] == meeting_id:
            if os.path.exists(entry["transcript_path"]):
                os.remove(entry["transcript_path"])
        else:
            remaining.append(entry)
    _save_index(remaining)

# ── PDF ───────────────────────────────────────────────────────────────────────
class MeetingPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20, 20, 25)
        self.cell(0, 10, "AI Video Assistant — Meeting Report", ln=True)
        self.set_draw_color(124, 58, 237)
        self.set_line_width(0.6)
        self.line(10, 20, 200, 20)
        self.ln(6)
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
    def section(self, title, body):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(124, 58, 237)
        self.cell(0, 9, title, ln=True)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(35, 35, 40)
        safe = (body or "N/A").encode("latin-1", "replace").decode("latin-1")
        self.multi_cell(0, 6, safe)
        self.ln(4)

def build_pdf(title, source, language, created_at, summary, action_items, key_decisions, open_questions, transcript, include_transcript=True):
    pdf = MeetingPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, title.encode("latin-1", "replace").decode("latin-1"))
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Source: {source}  |  Language: {language}  |  Generated: {created_at}", ln=True)
    pdf.ln(6)
    pdf.section("Summary", summary)
    pdf.section("Action Items", action_items)
    pdf.section("Key Decisions", key_decisions)
    pdf.section("Open Questions", open_questions)
    if include_transcript:
        pdf.add_page()
        pdf.section("Full Transcript", transcript)
    return bytes(pdf.output())

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="NeuralMeet · AI Video Intelligence", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ── MEGA CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&family=Outfit:wght@300;400;500;600;700;800;900&display=swap');

/* ═══════════════════════════════ TOKENS ═══════════════════════════════════ */
:root {
  --bg:          #05050d;
  --bg2:         #08080f;
  --surface:     rgba(255,255,255,0.03);
  --surface-h:   rgba(255,255,255,0.06);
  --border:      rgba(255,255,255,0.07);
  --border-h:    rgba(139,92,246,0.5);
  --violet:      #8b5cf6;
  --violet-l:    #a78bfa;
  --violet-d:    #6d28d9;
  --cyan:        #22d3ee;
  --cyan-d:      #0891b2;
  --pink:        #f472b6;
  --green:       #34d399;
  --amber:       #fbbf24;
  --red:         #f87171;
  --text:        #f1f0ff;
  --text-2:      #a09cbf;
  --text-3:      #5a5580;
  --glow-v:      rgba(139,92,246,0.35);
  --glow-c:      rgba(34,211,238,0.25);
}

/* ═══════════════════════════════ RESET ════════════════════════════════════ */
*, *::before, *::after { box-sizing: border-box; }

html, body { background: var(--bg) !important; }

[class*="css"], .stApp {
  font-family: 'Space Grotesk', sans-serif !important;
  background: var(--bg) !important;
  color: var(--text) !important;
}

/* ═══════════════════════════ ANIMATED BG ═════════════════════════════════ */
.stApp {
  background:
    radial-gradient(ellipse 80% 50% at 20% -10%, rgba(139,92,246,0.15) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 110%, rgba(34,211,238,0.10) 0%, transparent 55%),
    radial-gradient(ellipse 50% 60% at 50% 50%, rgba(244,114,182,0.04) 0%, transparent 70%),
    var(--bg) !important;
  min-height: 100vh;
}

/* Animated noise grain overlay */
.stApp::after {
  content: '';
  position: fixed; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
  pointer-events: none; z-index: 9999; opacity: 0.4;
}

/* Grid lines */
.stApp::before {
  content: '';
  position: fixed; inset: 0;
  background-image:
    linear-gradient(rgba(139,92,246,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(139,92,246,0.04) 1px, transparent 1px);
  background-size: 60px 60px;
  pointer-events: none; z-index: 0;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 80%);
}

/* ═════════════════════════════ SIDEBAR ════════════════════════════════════ */
[data-testid="stSidebar"] {
  background: rgba(8,8,16,0.95) !important;
  border-right: 1px solid var(--border) !important;
  backdrop-filter: blur(20px);
}
[data-testid="stSidebar"] > div { padding-top: 1.5rem; }
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* ════════════════════════════ BRAND LOGO ══════════════════════════════════ */
.brand {
  display: flex; align-items: center; gap: 10px; margin-bottom: 0.25rem;
}
.brand-icon {
  width: 38px; height: 38px; border-radius: 10px;
  background: linear-gradient(135deg, var(--violet), var(--cyan));
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
  box-shadow: 0 0 20px var(--glow-v);
  flex-shrink: 0;
}
.brand-name {
  font-family: 'Outfit', sans-serif !important;
  font-size: 1.3rem; font-weight: 800;
  background: linear-gradient(135deg, #fff 30%, var(--violet-l) 70%, var(--cyan) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  line-height: 1;
}
.brand-tagline {
  font-family: 'Space Mono', monospace !important;
  font-size: 0.6rem; color: var(--text-3) !important;
  letter-spacing: 0.18em; text-transform: uppercase; margin-top: 2px;
}

/* ════════════════════════════ HERO AREA ═══════════════════════════════════ */
.hero-wrap {
  position: relative; padding: 1rem 0 2rem; text-align: center;
}
.hero-eyebrow {
  font-family: 'Space Mono', monospace;
  font-size: 0.65rem; letter-spacing: 0.25em; text-transform: uppercase;
  color: var(--violet-l); margin-bottom: 0.75rem;
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
}
.hero-eyebrow::before, .hero-eyebrow::after {
  content: ''; width: 30px; height: 1px;
  background: linear-gradient(90deg, transparent, var(--violet));
}
.hero-eyebrow::after { background: linear-gradient(90deg, var(--violet), transparent); }

.hero-h1 {
  font-family: 'Outfit', sans-serif;
  font-size: clamp(2.5rem, 6vw, 4.5rem);
  font-weight: 900; line-height: 1.05; margin: 0 0 1rem;
  background: linear-gradient(135deg, #ffffff 0%, var(--violet-l) 40%, var(--cyan) 75%, var(--pink) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  filter: drop-shadow(0 0 40px rgba(139,92,246,0.3));
}

.hero-sub {
  font-size: 1rem; color: var(--text-2); max-width: 480px; margin: 0 auto 2rem;
  line-height: 1.7;
}

.hero-pills {
  display: flex; gap: 0.6rem; justify-content: center; flex-wrap: wrap;
}

/* ══════════════════════════════ PILLS / TAGS ══════════════════════════════ */
.pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 0.3rem 0.8rem; border-radius: 100px;
  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.05em;
  backdrop-filter: blur(10px);
}
.pill-v { background: rgba(139,92,246,0.15); color: var(--violet-l); border: 1px solid rgba(139,92,246,0.3); }
.pill-c { background: rgba(34,211,238,0.12); color: var(--cyan);     border: 1px solid rgba(34,211,238,0.25); }
.pill-p { background: rgba(244,114,182,0.12); color: var(--pink);    border: 1px solid rgba(244,114,182,0.25); }
.pill-g { background: rgba(52,211,153,0.12); color: var(--green);    border: 1px solid rgba(52,211,153,0.25); }
.pill-a { background: rgba(251,191,36,0.12); color: var(--amber);    border: 1px solid rgba(251,191,36,0.25); }

/* ═══════════════════════════════ GLASS CARDS ══════════════════════════════ */
.gcard {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 1.5rem;
  position: relative; overflow: hidden;
  backdrop-filter: blur(20px);
  transition: border-color 0.3s, background 0.3s, transform 0.2s, box-shadow 0.3s;
}
.gcard:hover {
  border-color: var(--border-h);
  background: var(--surface-h);
  transform: translateY(-2px);
  box-shadow: 0 20px 60px rgba(0,0,0,0.4), 0 0 30px var(--glow-v);
}
.gcard-glow::after {
  content: ''; position: absolute;
  top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--violet), var(--cyan), transparent);
  opacity: 0; transition: opacity 0.3s;
}
.gcard-glow:hover::after { opacity: 1; }

.gcard-label {
  font-family: 'Space Mono', monospace;
  font-size: 0.6rem; font-weight: 700; letter-spacing: 0.2em;
  text-transform: uppercase; color: var(--text-3);
  margin-bottom: 0.75rem; display: flex; align-items: center; gap: 6px;
}
.gcard-label-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: linear-gradient(135deg, var(--violet), var(--cyan));
  flex-shrink: 0;
}
.gcard-body { font-size: 0.9rem; line-height: 1.75; color: var(--text-2); }

/* ═══════════════════════════════ STAT CARDS ═══════════════════════════════ */
.stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 1rem; margin: 1.5rem 0; }
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px; padding: 1.2rem;
  text-align: center; position: relative; overflow: hidden;
  backdrop-filter: blur(10px);
  transition: all 0.3s;
}
.stat-card::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse at top, rgba(139,92,246,0.08), transparent 70%);
  opacity: 0; transition: opacity 0.3s;
}
.stat-card:hover::before { opacity: 1; }
.stat-card:hover { border-color: rgba(139,92,246,0.3); transform: translateY(-3px); box-shadow: 0 12px 40px rgba(0,0,0,0.3); }
.stat-num {
  font-family: 'Outfit', sans-serif;
  font-size: 2rem; font-weight: 800; line-height: 1;
  background: linear-gradient(135deg, var(--violet-l), var(--cyan));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.stat-label {
  font-family: 'Space Mono', monospace;
  font-size: 0.58rem; letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--text-3); margin-top: 0.4rem;
}
.stat-icon { font-size: 1.4rem; margin-bottom: 0.4rem; }

/* ════════════════════════════ PIPELINE STATUS ═════════════════════════════ */
.pipe-row {
  display: flex; align-items: center; gap: 10px;
  padding: 0.6rem 0.8rem; border-radius: 10px;
  background: var(--surface); border: 1px solid var(--border);
  margin: 0.3rem 0; font-size: 0.78rem; transition: border-color 0.2s;
}
.pipe-row:hover { border-color: rgba(139,92,246,0.3); }
.pipe-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; transition: all 0.3s; }
.pd-pending { background: var(--text-3); }
.pd-active  { background: var(--violet-l); box-shadow: 0 0 10px var(--violet-l), 0 0 20px var(--glow-v); animation: blink 1.2s ease-in-out infinite; }
.pd-done    { background: var(--green); box-shadow: 0 0 8px rgba(52,211,153,0.5); }
@keyframes blink { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(0.8)} }

.pipe-name { color: var(--text-2); flex: 1; }
.pipe-badge-done { font-size: 0.6rem; color: var(--green); font-family:'Space Mono',monospace; letter-spacing:0.1em; }
.pipe-badge-active { font-size: 0.6rem; color: var(--violet-l); font-family:'Space Mono',monospace; letter-spacing:0.1em; animation: blink 1s ease-in-out infinite; }

/* ══════════════════════════════ HISTORY ITEMS ═════════════════════════════ */
.hist-item {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.65rem 0.85rem; margin-bottom: 0.4rem;
  transition: all 0.2s; cursor: pointer; position: relative; overflow: hidden;
}
.hist-item:hover { border-color: rgba(139,92,246,0.4); background: var(--surface-h); }
.hist-item::before { content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background: linear-gradient(180deg, var(--violet), var(--cyan)); border-radius: 2px 0 0 2px; opacity:0; transition: opacity 0.2s; }
.hist-item:hover::before { opacity: 1; }
.hist-title { font-size: 0.78rem; font-weight: 600; color: var(--text); line-height: 1.3; margin-bottom: 3px; }
.hist-meta  { font-family:'Space Mono',monospace; font-size: 0.6rem; color: var(--text-3); }

/* ══════════════════════════════ INPUT FIELDS ══════════════════════════════ */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stFileUploader section {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text) !important;
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 0.9rem !important;
  transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stTextInput > div > div > input:focus {
  border-color: var(--violet) !important;
  box-shadow: 0 0 0 3px rgba(139,92,246,0.15), 0 0 20px var(--glow-v) !important;
  outline: none !important;
}
.stTextInput > div > div > input::placeholder { color: var(--text-3) !important; }

/* ══════════════════════════════ BUTTONS ═══════════════════════════════════ */
.stButton > button {
  background: linear-gradient(135deg, var(--violet-d) 0%, var(--violet) 50%, #7c3aed 100%) !important;
  color: white !important; border: none !important;
  border-radius: 10px !important;
  font-family: 'Outfit', sans-serif !important;
  font-weight: 700 !important; font-size: 0.875rem !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important;
  padding: 0.65rem 1.5rem !important;
  transition: all 0.25s !important;
  position: relative !important; overflow: hidden !important;
  box-shadow: 0 4px 15px var(--glow-v) !important;
}
.stButton > button::after {
  content: '' !important; position: absolute !important; inset: 0 !important;
  background: linear-gradient(135deg, rgba(255,255,255,0.15), transparent) !important;
  opacity: 0 !important; transition: opacity 0.2s !important;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 30px var(--glow-v), 0 0 60px rgba(139,92,246,0.2) !important;
}
.stButton > button:hover::after { opacity: 1 !important; }
.stButton > button:active { transform: translateY(0) !important; }

.stButton > button[kind="secondary"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  box-shadow: none !important;
  color: var(--text-2) !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color: rgba(139,92,246,0.4) !important;
  color: var(--text) !important;
  box-shadow: none !important;
}

.stDownloadButton > button {
  background: rgba(34,211,238,0.08) !important;
  color: var(--cyan) !important;
  border: 1px solid rgba(34,211,238,0.3) !important;
  border-radius: 10px !important;
  font-family: 'Outfit', sans-serif !important;
  font-weight: 600 !important; font-size: 0.8rem !important;
  letter-spacing: 0.06em !important;
  transition: all 0.2s !important;
}
.stDownloadButton > button:hover {
  background: rgba(34,211,238,0.15) !important;
  border-color: var(--cyan) !important;
  box-shadow: 0 0 20px var(--glow-c) !important;
  transform: translateY(-1px) !important;
}

/* ══════════════════════════════ TABS ══════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--border) !important;
  gap: 0.5rem !important; padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  border: none !important; border-radius: 0 !important;
  color: var(--text-3) !important;
  font-family: 'Space Grotesk', sans-serif !important;
  font-weight: 600 !important; font-size: 0.85rem !important;
  padding: 0.6rem 1.2rem !important;
  border-bottom: 2px solid transparent !important;
  transition: all 0.2s !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text) !important; border-bottom-color: rgba(139,92,246,0.4) !important; }
.stTabs [aria-selected="true"] {
  color: var(--violet-l) !important;
  border-bottom-color: var(--violet) !important;
  background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 1.5rem 0 !important; }

/* ══════════════════════════════ CHAT ══════════════════════════════════════ */
.chat-wrap {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 16px; padding: 1.25rem;
  max-height: 460px; overflow-y: auto; margin-bottom: 1rem;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
}
.cmsg { margin-bottom: 1.1rem; display: flex; flex-direction: column; }
.clabel {
  font-family: 'Space Mono', monospace;
  font-size: 0.58rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase;
  margin-bottom: 4px;
}
.clabel-u { color: var(--violet-l); }
.clabel-b { color: var(--cyan); }
.cbubble {
  display: inline-block; padding: 0.65rem 1rem;
  border-radius: 12px; font-size: 0.88rem; line-height: 1.65;
  max-width: 85%;
}
.cbubble-u {
  background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.25);
  align-self: flex-end; border-radius: 12px 12px 2px 12px;
}
.cbubble-b {
  background: rgba(34,211,238,0.08); border: 1px solid rgba(34,211,238,0.2);
  align-self: flex-start; border-radius: 12px 12px 12px 2px;
}

/* ══════════════════════════════ TRANSCRIPT ════════════════════════════════ */
.t-box {
  background: rgba(255,255,255,0.02); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.25rem; font-family: 'Space Mono', monospace;
  font-size: 0.8rem; line-height: 1.9; max-height: 520px;
  overflow-y: auto; color: var(--text-2); white-space: pre-wrap; word-break: break-word;
}
mark { background: rgba(139,92,246,0.35); color: var(--violet-l); padding: 1px 4px; border-radius: 3px; }

/* ═══════════════════════════ TITLE BANNER ═════════════════════════════════ */
.title-banner {
  background: linear-gradient(135deg, rgba(139,92,246,0.12), rgba(34,211,238,0.06));
  border: 1px solid rgba(139,92,246,0.2);
  border-radius: 16px; padding: 1.5rem 2rem;
  position: relative; overflow: hidden; margin-bottom: 1.5rem;
}
.title-banner::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--violet), var(--cyan), transparent);
}
.title-banner-eyebrow {
  font-family: 'Space Mono', monospace; font-size: 0.58rem;
  letter-spacing: 0.2em; text-transform: uppercase; color: var(--violet-l);
  margin-bottom: 0.4rem;
}
.title-banner-text {
  font-family: 'Outfit', sans-serif; font-size: clamp(1.3rem, 3vw, 2rem);
  font-weight: 700; color: var(--text); line-height: 1.2;
}
.title-banner-meta {
  font-family: 'Space Mono', monospace; font-size: 0.65rem;
  color: var(--text-3); margin-top: 0.5rem; letter-spacing: 0.05em;
}
.title-banner-glow {
  position: absolute; right: -40px; top: -40px;
  width: 180px; height: 180px; border-radius: 50%;
  background: radial-gradient(circle, rgba(139,92,246,0.15), transparent 70%);
  pointer-events: none;
}

/* ══════════════════════════════ EMPTY STATE ═══════════════════════════════ */
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 5rem 2rem; text-align: center;
  position: relative;
}
.empty-orb {
  width: 120px; height: 120px; border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(139,92,246,0.4), rgba(34,211,238,0.1) 60%, transparent);
  border: 1px solid rgba(139,92,246,0.2);
  display: flex; align-items: center; justify-content: center;
  font-size: 3rem; margin-bottom: 2rem;
  box-shadow: 0 0 60px rgba(139,92,246,0.2), 0 0 120px rgba(139,92,246,0.08);
  animation: float 4s ease-in-out infinite;
}
@keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }

.empty-title {
  font-family: 'Outfit', sans-serif; font-size: 1.8rem; font-weight: 700;
  background: linear-gradient(135deg, var(--text), var(--violet-l));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  margin-bottom: 0.75rem;
}
.empty-sub { font-size: 0.9rem; color: var(--text-2); max-width: 400px; line-height: 1.7; margin-bottom: 2rem; }

/* ═════════════════════════ FEATURE GRID (empty state) ════════════════════ */
.feat-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 1rem; max-width: 600px; margin: 0 auto; }
.feat-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.2rem; text-align: left;
  transition: all 0.3s;
}
.feat-card:hover { border-color: rgba(139,92,246,0.4); transform: translateY(-3px); }
.feat-icon { font-size: 1.4rem; margin-bottom: 0.5rem; }
.feat-title { font-weight: 700; font-size: 0.85rem; color: var(--text); margin-bottom: 0.25rem; }
.feat-desc { font-size: 0.75rem; color: var(--text-3); line-height: 1.5; }

/* ══════════════════════════════ MISC ══════════════════════════════════════ */
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 1.5rem 0 !important; }
.stProgress > div > div > div { background: linear-gradient(90deg, var(--violet), var(--cyan)) !important; border-radius: 4px !important; }
.stSpinner > div { border-top-color: var(--violet) !important; }
[data-testid="stMarkdownContainer"] p { color: var(--text-2) !important; }
label { color: var(--text-3) !important; font-size: 0.78rem !important; letter-spacing: 0.03em !important; }
.stRadio label p { color: var(--text-2) !important; font-size: 0.85rem !important; }
.stCheckbox label p { color: var(--text-2) !important; }
.stExpander { border: 1px solid var(--border) !important; border-radius: 12px !important; background: var(--surface) !important; }
.stExpander:hover { border-color: rgba(139,92,246,0.3) !important; }

/* scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--violet); }

/* smooth transitions on everything */
* { transition-property: border-color, background-color, box-shadow, transform, opacity; transition-duration: 0.15s; transition-timing-function: ease; }
</style>
""", unsafe_allow_html=True)

# ── Session State ─────────────────────────────────────────────────────────────
for k, v in {
    "result": None, "meeting_id": None, "chat_history": [],
    "processing": False, "pipeline_done": False, "pipeline_steps": {},
    "audio_bytes": None, "checklist_state": {},
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def cached_rag_chain(transcript: str):
    return build_rag_chain(transcript)

def word_count(t): return len(t.split()) if t else 0
def est_min(t, wpm=130): wc = word_count(t); return max(1, round(wc/wpm)) if wc else 0

def highlight(text, q):
    if not q: return text
    return re.compile(re.escape(q), re.IGNORECASE).sub(lambda m: f"<mark>{m.group(0)}</mark>", text)

def pipe_cls(steps, k):
    s = steps.get(k, "pending")
    return "pd-active" if s=="active" else ("pd-done" if s=="done" else "pd-pending")

def pipe_badge(steps, k):
    s = steps.get(k, "pending")
    if s == "active": return '<span class="pipe-badge-active">● RUNNING</span>'
    if s == "done":   return '<span class="pipe-badge-done">✓ DONE</span>'
    return '<span style="color:var(--text-3);font-family:Space Mono,monospace;font-size:0.6rem">QUEUED</span>'

def render_pipe(label, k, icon):
    cls = pipe_cls(st.session_state.pipeline_steps, k)
    badge = pipe_badge(st.session_state.pipeline_steps, k)
    st.markdown(f'''<div class="pipe-row">
      <div class="pipe-dot {cls}"></div>
      <span class="pipe-name">{icon} {label}</span>
      {badge}
    </div>''', unsafe_allow_html=True)

def render_checklist(section_key, raw_text):
    lines = [ln.strip("-• \t") for ln in (raw_text or "").split("\n") if ln.strip()]
    if not lines:
        st.caption("Nothing found in this section.")
        return
    for i, line in enumerate(lines):
        sk = f"{section_key}_{i}"
        checked = st.session_state.checklist_state.get(sk, False)
        val = st.checkbox(line, value=checked, key=f"chk_{sk}")
        st.session_state.checklist_state[sk] = val

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('''
    <div class="brand">
      <div class="brand-icon">⚡</div>
      <div>
        <div class="brand-name">NeuralMeet</div>
        <div class="brand-tagline">AI Video Intelligence</div>
      </div>
    </div>''', unsafe_allow_html=True)
    st.markdown("---")

    st.markdown('<span class="pill pill-v">⚙ Configure</span>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    input_mode = st.radio("Input Method", ["🔗 URL / Path", "📁 Upload File"], horizontal=True, label_visibility="collapsed")

    source = None
    st.session_state.audio_bytes = None
    if input_mode == "🔗 URL / Path":
        source = st.text_input("URL or Path", placeholder="https://youtube.com/watch?v=... or /path/to/file.mp4", label_visibility="collapsed")
    else:
        uploaded = st.file_uploader("", type=["mp3","wav","m4a","mp4","mov","mkv"], label_visibility="collapsed")
        if uploaded:
            tmp = os.path.join(tempfile.gettempdir(), uploaded.name)
            fb = uploaded.getbuffer()
            with open(tmp, "wb") as f: f.write(fb)
            source = tmp
            st.session_state.audio_bytes = bytes(fb)

    language = st.selectbox("Language", ["english", "hinglish"], index=0)
    run_btn = st.button("⚡  Analyse Now", use_container_width=True)

    if st.session_state.pipeline_done:
        st.markdown("---")
        st.markdown('<span class="pill pill-g">✓ Pipeline</span>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        for step, icon, label in [
            ("audio","🔊","Audio"), ("transcript","📝","Transcription"),
            ("title","🏷️","Title"), ("summary","📋","Summary"),
            ("extract","🔍","Extraction"), ("rag","🧠","RAG Engine"),
        ]:
            render_pipe(label, step, icon)

    st.markdown("---")
    st.markdown('<span class="pill pill-c">📂 History</span>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    meetings = list_meetings()
    if not meetings:
        st.markdown('<p style="color:var(--text-3);font-size:0.78rem">Analysed sessions appear here.</p>', unsafe_allow_html=True)
    else:
        for m in meetings[:12]:
            st.markdown(f'''<div class="hist-item">
              <div class="hist-title">{m["title"][:44]}</div>
              <div class="hist-meta">{m["created_at"][:16]} · {m["language"]}</div>
            </div>''', unsafe_allow_html=True)
            hc1, hc2 = st.columns([3,1])
            with hc1:
                if st.button("Open", key=f"open_{m['id']}", use_container_width=True):
                    loaded = get_meeting(m["id"])
                    loaded["rag_chain"] = None
                    st.session_state.result = loaded
                    st.session_state.meeting_id = m["id"]
                    st.session_state.chat_history = []
                    st.session_state.checklist_state = {}
                    st.session_state.pipeline_done = True
                    st.session_state.pipeline_steps = {k:"done" for k in ["audio","transcript","title","summary","extract","rag"]}
                    st.rerun()
            with hc2:
                if st.button("🗑️", key=f"del_{m['id']}"):
                    delete_meeting(m["id"]); st.rerun()

# ── HERO ──────────────────────────────────────────────────────────────────────
st.markdown('''
<div class="hero-wrap">
  <div class="hero-eyebrow">Powered by Whisper + Mistral + ChromaDB</div>
  <div class="hero-h1">AI Video<br>Intelligence</div>
  <div class="hero-sub">Drop any YouTube video or audio file. Get a full transcript, executive summary, action items, and an AI chat — in minutes.</div>
  <div class="hero-pills">
    <span class="pill pill-v">🎙 Transcription</span>
    <span class="pill pill-c">📋 Summarisation</span>
    <span class="pill pill-p">✅ Action Extraction</span>
    <span class="pill pill-g">🧠 RAG Chat</span>
    <span class="pill pill-a">📤 PDF Export</span>
  </div>
</div>
''', unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# ── PIPELINE ──────────────────────────────────────────────────────────────────
if run_btn:
    if not source or not str(source).strip():
        st.error("⚠️ Please provide a YouTube URL, file path, or upload a file.")
    else:
        st.session_state.update({"pipeline_done":False,"result":None,"chat_history":[],"checklist_state":{},"pipeline_steps":{}})
        pp = st.empty()
        def upd(k, s): st.session_state.pipeline_steps[k] = s
        try:
            pp.info("⚙️ Pipeline running — check sidebar for live status…")
            upd("audio","active");      chunks = process_input(source);           upd("audio","done")
            upd("transcript","active"); transcript = transcribe_all(chunks,language); upd("transcript","done")
            upd("title","active");      title = generate_title(transcript);       upd("title","done")
            upd("summary","active");    summary = summarize(transcript);          upd("summary","done")
            upd("extract","active");    action_items = extract_action_items(transcript); decisions = extract_key_decisions(transcript); questions = extract_questions(transcript); upd("extract","done")
            upd("rag","active");        rag_chain = build_rag_chain(transcript);  upd("rag","done")
            result = {"title":title,"transcript":transcript,"summary":summary,"action_items":action_items,"key_decisions":decisions,"open_questions":questions,"rag_chain":rag_chain,"generated_at":datetime.now().strftime("%Y-%m-%d %H:%M")}
            st.session_state.result = result
            st.session_state.pipeline_done = True
            st.session_state.meeting_id = save_meeting(result, str(source), language)
            pp.success("✅ Analysis complete!"); time.sleep(0.4); pp.empty(); st.rerun()
        except Exception as e:
            for k in ["audio","transcript","title","summary","extract","rag"]:
                if st.session_state.pipeline_steps.get(k) == "active": st.session_state.pipeline_steps[k] = "pending"
            pp.error(f"❌ {e}")

# ── RESULTS ───────────────────────────────────────────────────────────────────
if st.session_state.result:
    r = st.session_state.result
    tx = r["transcript"]

    # Title banner
    st.markdown(f'''
    <div class="title-banner">
      <div class="title-banner-glow"></div>
      <div class="title-banner-eyebrow">📌 Session Title</div>
      <div class="title-banner-text">{r["title"]}</div>
      <div class="title-banner-meta">Generated {r.get("generated_at","—")} &nbsp;·&nbsp; {language}</div>
    </div>''', unsafe_allow_html=True)

    if st.session_state.audio_bytes:
        st.audio(st.session_state.audio_bytes)

    # Stat cards
    ai_count = len([l for l in r["action_items"].split("\n") if l.strip()])
    kd_count = len([l for l in r["key_decisions"].split("\n") if l.strip()])
    st.markdown(f'''
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-icon">💬</div><div class="stat-num">{word_count(tx):,}</div><div class="stat-label">Words</div></div>
      <div class="stat-card"><div class="stat-icon">⏱️</div><div class="stat-num">{est_min(tx)}</div><div class="stat-label">Est. Minutes</div></div>
      <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-num">{ai_count}</div><div class="stat-label">Action Items</div></div>
      <div class="stat-card"><div class="stat-icon">🔑</div><div class="stat-num">{kd_count}</div><div class="stat-label">Key Decisions</div></div>
    </div>''', unsafe_allow_html=True)

    tabs = st.tabs(["🧩 Overview", "📝 Transcript", "💬 Chat", "📤 Export"])
    tab_ov, tab_tx, tab_ch, tab_ex = tabs

    with tab_ov:
        col1, col2 = st.columns([3,2], gap="large")
        with col1:
            st.markdown(f'''<div class="gcard gcard-glow">
              <div class="gcard-label"><div class="gcard-label-dot"></div>Executive Summary</div>
              <div class="gcard-body">{r["summary"]}</div>
            </div>''', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="gcard gcard-glow"><div class="gcard-label"><div class="gcard-label-dot"></div>Action Items ✅</div>', unsafe_allow_html=True)
            render_checklist("actions", r["action_items"])
            st.markdown('</div>', unsafe_allow_html=True)

        c2, c3 = st.columns(2, gap="large")
        with c2:
            st.markdown(f'''<div class="gcard gcard-glow">
              <div class="gcard-label"><div class="gcard-label-dot"></div>🔑 Key Decisions</div>
              <div class="gcard-body">{r["key_decisions"]}</div>
            </div>''', unsafe_allow_html=True)
        with c3:
            st.markdown(f'''<div class="gcard gcard-glow">
              <div class="gcard-label"><div class="gcard-label-dot"></div>❓ Open Questions</div>
              <div class="gcard-body">{r["open_questions"]}</div>
            </div>''', unsafe_allow_html=True)

    with tab_tx:
        q = st.text_input("", placeholder="🔍  Search the transcript…", label_visibility="collapsed")
        st.markdown(f'<div class="t-box">{highlight(tx, q)}</div>', unsafe_allow_html=True)

    with tab_ch:
        if st.session_state.chat_history:
            html = '<div class="chat-wrap">'
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    html += f'<div class="cmsg"><span class="clabel clabel-u">You</span><div class="cbubble cbubble-u">{msg["content"]}</div></div>'
                else:
                    html += f'<div class="cmsg"><span class="clabel clabel-b">⚡ NeuralMeet</span><div class="cbubble cbubble-b">{msg["content"]}</div></div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.markdown('''<div class="gcard" style="text-align:center;padding:2.5rem">
              <div style="font-size:2.5rem;margin-bottom:0.75rem">🧠</div>
              <div style="font-family:Outfit,sans-serif;font-size:1.1rem;font-weight:700;color:var(--text);margin-bottom:0.4rem">Ask anything about this session</div>
              <div style="color:var(--text-3);font-size:0.82rem">The AI has read the full transcript and is ready to answer questions.</div>
            </div>''', unsafe_allow_html=True)

        cc1, cc2 = st.columns([5,1], gap="small")
        with cc1:
            ui = st.text_input("", placeholder="e.g. What decisions were made? Who owns the action items?", label_visibility="collapsed", key="chat_box")
        with cc2:
            send = st.button("Send ➜", use_container_width=True)

        if send and ui.strip():
            with st.spinner("Thinking…"):
                try:
                    chain = r.get("rag_chain") or cached_rag_chain(tx)
                    ans = ask_question(chain, ui.strip())
                    if isinstance(ans, tuple): ans = ans[0]
                except Exception as e:
                    ans = f"⚠️ {e}"
            st.session_state.chat_history += [{"role":"user","content":ui.strip()},{"role":"assistant","content":ans}]
            st.rerun()

        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat", type="secondary"):
                st.session_state.chat_history = []; st.rerun()

    with tab_ex:
        inc = st.checkbox("Include full transcript in PDF", value=True)
        st.markdown("<br>", unsafe_allow_html=True)
        e1, e2, e3 = st.columns(3)
        with e1:
            st.download_button("⬇️ Transcript (TXT)", tx, file_name="transcript.txt", use_container_width=True)
        with e2:
            rpt = f"Title: {r['title']}\n\nSummary:\n{r['summary']}\n\nAction Items:\n{r['action_items']}\n\nKey Decisions:\n{r['key_decisions']}\n\nOpen Questions:\n{r['open_questions']}\n"
            st.download_button("⬇️ Report (TXT)", rpt, file_name="meeting_report.txt", use_container_width=True)
        with e3:
            try:
                pdf = build_pdf(r["title"], str(source or "—"), language, r.get("generated_at",""), r["summary"], r["action_items"], r["key_decisions"], r["open_questions"], tx, inc)
                st.download_button("⬇️ Report (PDF)", pdf, file_name="meeting_report.pdf", mime="application/pdf", use_container_width=True)
            except Exception as e:
                st.error(f"PDF error: {e}")

# ── EMPTY STATE ───────────────────────────────────────────────────────────────
else:
    st.markdown('''
    <div class="empty-state">
      <div class="empty-orb">⚡</div>
      <div class="empty-title">Ready to Analyse</div>
      <div class="empty-sub">Paste a YouTube URL or upload an audio/video file in the sidebar, pick a language, and hit <strong>Analyse Now</strong>.</div>
    </div>
    <div class="feat-grid">
      <div class="feat-card">
        <div class="feat-icon">🎙️</div>
        <div class="feat-title">Whisper Transcription</div>
        <div class="feat-desc">State-of-the-art OpenAI Whisper transcribes any language with high accuracy.</div>
      </div>
      <div class="feat-card">
        <div class="feat-icon">📋</div>
        <div class="feat-title">Smart Summaries</div>
        <div class="feat-desc">Mistral LLM distils hours of content into a structured executive brief.</div>
      </div>
      <div class="feat-card">
        <div class="feat-icon">🧠</div>
        <div class="feat-title">RAG Chat</div>
        <div class="feat-desc">Ask any question about your meeting — ChromaDB retrieves the exact context.</div>
      </div>
      <div class="feat-card">
        <div class="feat-icon">✅</div>
        <div class="feat-title">Action Extraction</div>
        <div class="feat-desc">Automatically pulls action items, key decisions, and open questions.</div>
      </div>
      <div class="feat-card">
        <div class="feat-icon">📤</div>
        <div class="feat-title">PDF / TXT Export</div>
        <div class="feat-desc">Download a beautiful branded PDF report or raw text files instantly.</div>
      </div>
      <div class="feat-card">
        <div class="feat-icon">🗂️</div>
        <div class="feat-title">Session History</div>
        <div class="feat-desc">Every session is saved and searchable. Reopen any past meeting anytime.</div>
      </div>
    </div>
    ''', unsafe_allow_html=True)