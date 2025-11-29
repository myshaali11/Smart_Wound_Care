# action.py
# Helper utilities: save uploaded images, initialize & insert into SQLite DB,
# and generate a one-page PDF report using ReportLab.
#
# Dependencies:
#   pip install pillow reportlab
#
# Usage:
#   from action import save_image_file, insert_record_sqlite, make_pdf_bytes
#   path = save_image_file(pil_image)
#   rec_id = insert_record_sqlite(db_path, record_dict)
#   pdf_bytes = make_pdf_bytes(record_dict)

import os
import io
import json
import sqlite3
from datetime import datetime
from typing import Dict, Optional
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# Configuration
UPLOAD_DIR = "data/uploads"
DB_PATH_DEFAULT = "data/wound_records.db"
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    image_path TEXT,
    metrics_json TEXT,
    decision_json TEXT,
    rationale TEXT,
    context_json TEXT
);
"""

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH_DEFAULT), exist_ok=True)

_db_initialized = False


def _init_db(db_path: str = DB_PATH_DEFAULT):
    global _db_initialized
    if _db_initialized:
        return
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(DB_SCHEMA)
    conn.commit()
    conn.close()
    _db_initialized = True


def save_image_file(pil_img: Image.Image, prefix: str = "upload") -> str:
    """
    Save a PIL.Image to UPLOAD_DIR and return the saved file path (JPEG).
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    filename = f"{prefix}_{ts}.jpg"
    path = os.path.join(UPLOAD_DIR, filename)
    # Convert to RGB if needed and save as JPEG
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    pil_img.save(path, format="JPEG", quality=85)
    return path


def insert_record_sqlite(db_path: str, record: Dict) -> int:
    """
    Insert a record into SQLite DB and return the new row id.
    record should contain keys:
      - image_path (str)
      - timestamp (ISO str) optional
      - metrics (dict)
      - decision (dict)
      - rationale (str)
      - context (dict)
    """
    _init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO records (timestamp, image_path, metrics_json, decision_json, rationale, context_json) VALUES (?,?,?,?,?,?)",
        (
            record.get("timestamp", datetime.utcnow().isoformat()),
            record.get("image_path"),
            json.dumps(record.get("metrics", {})),
            json.dumps(record.get("decision", {})),
            record.get("rationale", ""),
            json.dumps(record.get("context", {})),
        ),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def update_record_sqlite(db_path: str, record_id: int, fields: Dict) -> None:
    """Update fields for a record. `fields` is a dict of column->value e.g. {'rationale': 'text'}"""
    _init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Build SET clause
    cols = []
    vals = []
    for k, v in fields.items():
        cols.append(f"{k} = ?")
        vals.append(v)
    vals.append(record_id)
    sql = f"UPDATE records SET {', '.join(cols)} WHERE id = ?"
    cur.execute(sql, vals)
    conn.commit()
    conn.close()


def fetch_records(db_path: str, limit: int = 200):
    """Fetch recent records from the DB. Returns a list of dicts with parsed JSON fields."""
    _init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, timestamp, image_path, metrics_json, decision_json, rationale, context_json FROM records ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        rid, ts, image_path, metrics_json, decision_json, rationale, context_json = r
        try:
            metrics = json.loads(metrics_json) if metrics_json else {}
        except Exception:
            metrics = {}
        try:
            decision = json.loads(decision_json) if decision_json else {}
        except Exception:
            decision = {}
        try:
            context = json.loads(context_json) if context_json else {}
        except Exception:
            context = {}
        results.append({
            "id": rid,
            "timestamp": ts,
            "image_path": image_path,
            "metrics": metrics,
            "decision": decision,
            "rationale": rationale,
            "context": context,
        })
    return results


def make_pdf_bytes(record: Dict, page_size=A4) -> bytes:
    """
    Create a one-page PDF (bytes) containing:
      - Header/title
      - Image (scaled)
      - Metrics table
      - Decision & explanation
      - LLM rationale / patient instructions
      - Footer/disclaimer

    record keys used:
      image_path (required if you want image), timestamp, metrics (dict),
      decision (dict), rationale (str), context (dict)
    """
    # Page setup
    width, height = page_size
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=page_size)

    # Margins
    left_margin = 18 * mm
    right_margin = 18 * mm
    top_y = height - 20 * mm
    usable_width = width - left_margin - right_margin

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2.0, top_y, "Smart Wound-Care Concierge Report")

    # Timestamp
    c.setFont("Helvetica", 9)
    ts = record.get("timestamp", datetime.utcnow().isoformat())
    c.drawRightString(width - right_margin, top_y - 12, f"Generated: {ts}")

    # Draw image on left (if exists) and metrics on right
    y_after_title = top_y - 30
    img_h_space = 85 * mm  # height reserved for image
    img_w_space = usable_width * 0.55
    metrics_x = left_margin + img_w_space + 8 * mm

    image_path = record.get("image_path")
    if image_path and os.path.exists(image_path):
        try:
            pil = Image.open(image_path)
            ir = ImageReader(pil)
            # Fit image into box preserving aspect ratio
            max_w = img_w_space
            max_h = img_h_space
            iw, ih = pil.size
            scale = min(max_w / iw, max_h / ih)
            draw_w = iw * scale
            draw_h = ih * scale
            img_x = left_margin
            img_y = y_after_title - draw_h
            c.drawImage(ir, img_x, img_y, width=draw_w, height=draw_h, preserveAspectRatio=True, anchor="nw")
        except Exception:
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(left_margin, y_after_title - 12, "Image could not be embedded.")
            draw_h = 0
            img_y = y_after_title
    else:
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(left_margin, y_after_title - 12, "No image provided.")
        draw_h = 0
        img_y = y_after_title

    # Metrics box (right side)
    metrics = record.get("metrics", {})
    decision = record.get("decision", {})
    rationale = record.get("rationale", "")
    context = record.get("context", {})

    # Render metrics
    cur_y = y_after_title
    c.setFont("Helvetica-Bold", 12)
    c.drawString(metrics_x, cur_y, "Metrics & Decision")
    cur_y -= 14
    c.setFont("Helvetica", 10)
    # Metrics list
    metric_keys = [
        ("area", "Area (px)"),
        ("area_pct", "Area (%)"),
        ("redness", "Redness"),
        ("exudate_ratio", "Exudate ratio"),
        ("brightness", "Brightness"),
        ("blur_var", "Blur (var)"),
    ]
    for key, label in metric_keys:
        val = metrics.get(key, "—")
        # format floats nicely
        if isinstance(val, float):
            val_txt = f"{val:.3f}" if key in ("area_pct", "exudate_ratio",) else f"{val:.1f}"
        else:
            val_txt = str(val)
        c.drawString(metrics_x, cur_y, f"{label}: {val_txt}")
        cur_y -= 12

    # Decision summary
    cur_y -= 4
    c.setFont("Helvetica-Bold", 11)
    status_text = decision.get("status", "—")
    c.drawString(metrics_x, cur_y, f"Status: {status_text}")
    cur_y -= 14
    c.setFont("Helvetica", 9)
    explanation = decision.get("explanation", "")
    # Wrap explanation
    text_obj = c.beginText(metrics_x, cur_y)
    text_obj.setFont("Helvetica", 9)
    for line in _wrap_text(f"Explanation: {explanation}", 60):
        text_obj.textLine(line)
    c.drawText(text_obj)
    # advance cur_y according to wrapped lines
    cur_y = text_obj.getY() - 6

    # Rationale / Instructions (below image)
    # Place under image area (left column) or below metrics if space small
    instr_x = left_margin
    instr_y = img_y - 10 if draw_h > 0 else cur_y - 20
    instr_y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_margin, instr_y, "Clinician Summary & Patient Instructions")
    instr_y -= 14
    c.setFont("Helvetica", 10)
    # Render rationale wrapped into multiple lines
    text_obj2 = c.beginText(left_margin, instr_y)
    text_obj2.setFont("Helvetica", 10)
    for line in _wrap_text(rationale or "No generated instructions.", 90):
        text_obj2.textLine(line)
    c.drawText(text_obj2)

    # Footer / context
    footer_y = 20 * mm
    c.setFont("Helvetica-Oblique", 8)
    ctx_str = f"Context: {', '.join([f'{k}={v}' for k, v in (context or {}).items() if v not in (None, '')])}" or ""
    c.drawString(left_margin, footer_y + 6, ctx_str)
    c.drawRightString(width - right_margin, footer_y + 6, "Disclaimer: Automated assistive output — not medical advice.")

    # Finalize
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _wrap_text(text: str, max_chars: int):
    """
    Simple wrapper that yields lines no longer than max_chars, splitting on spaces.
    Keeps words intact.
    """
    words = text.split()
    if not words:
        yield ""
        return
    line = ""
    for w in words:
        if len(line) + len(w) + 1 <= max_chars:
            line = (line + " " + w).strip()
        else:
            yield line
            line = w
    if line:
        yield line
