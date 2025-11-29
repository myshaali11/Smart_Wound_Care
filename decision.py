# app/decision.py
"""
Decision module for Smart Wound-Care Concierge.

- Keeps the same rule-based decision logic.
- If GEMINI_API_KEY environment variable is set, it will call Gemini / Google Generative Language
  API (via a REST request) to produce a clinician-friendly rationale + patient instructions.
- Falls back to templates when Gemini is not configured or the call fails.
"""

import os
import math
from typing import Optional, Dict
import json

# we use requests for a simple REST-call integration to Gemini/Generative Language API
import requests

# --- Decision thresholds (tweak as needed) ---
REDNESS_URGENT = 150.0
REDNESS_CONCERNING = 120.0
DELTA_URGENT = 15.0        # >15% increase -> urgent
DELTA_CONCERNING = 5.0     # >5% increase -> concerning
EXUDATE_HIGH = 0.08        # >8% of pixels very bright -> concerning/urgent
EXUDATE_MED = 0.03         # >3% -> caution

# --- Basic templates (fallback if LLM not present) ---
TEMPLATES = {
    "Stable": "Status: Stable. Continue current wound care and follow up as scheduled.",
    "Monitor": "Status: Monitor. Observe wound daily; photograph change. Contact clinician if worsening.",
    "Concerning": "Status: Concerning. Consider nurse review; increase dressing frequency and monitor.",
    "Urgent": "Status: URGENT. Recommend immediate clinician review; consider in-person evaluation."
}

def compute_delta_pct(curr_metrics: Dict, prev_metrics: Optional[Dict]) -> float:
    if not prev_metrics:
        return 0.0
    prev_area = max(1.0, float(prev_metrics.get("area", 0)))
    return (float(curr_metrics.get("area", 0)) - prev_area) / prev_area * 100.0

def decide_status(curr_metrics: Dict, prev_metrics: Optional[Dict] = None) -> Dict:
    """
    Returns:
      {
        "status": str,
        "delta_pct": float,
        "quality": "ok"/"poor",
        "explanation": str  # short explanation of which rule fired
      }
    """
    delta = compute_delta_pct(curr_metrics, prev_metrics)
    redness = float(curr_metrics.get("redness", 0.0))
    exud = float(curr_metrics.get("exudate_ratio", 0.0))
    blur_var = float(curr_metrics.get("blur_var", 0.0))
    brightness = float(curr_metrics.get("brightness", 0.0))

    # initial status
    status = "Monitor"
    reason = []

    # image quality check
    if blur_var < 60.0 or brightness < 30.0:
        quality = "poor"
        reason.append(f"image_quality: blur_var={blur_var:.1f}, brightness={brightness:.1f}")
    else:
        quality = "ok"

    # exudate influences severity
    if exud >= EXUDATE_HIGH:
        status = "Urgent"
        reason.append(f"high_exudate:{exud:.3f}")
    elif exud >= EXUDATE_MED and status != "Urgent":
        status = "Concerning"
        reason.append(f"moderate_exudate:{exud:.3f}")

    # delta-based rules
    if delta > DELTA_URGENT:
        status = "Urgent"
        reason.append(f"area_increase_pct:{delta:.1f}")
    elif DELTA_CONCERNING < delta <= DELTA_URGENT and status not in ("Urgent",):
        status = "Concerning"
        reason.append(f"area_increase_pct:{delta:.1f}")
    elif -5.0 <= delta <= DELTA_CONCERNING:
        if status == "Monitor":
            status = "Monitor"
        reason.append(f"area_change_pct:{delta:.1f}")
    elif delta < -5.0:
        status = "Stable"
        reason.append(f"area_decrease_pct:{delta:.1f}")

    # redness overrides
    if redness > REDNESS_URGENT:
        status = "Urgent"
        reason.append(f"redness:{redness:.1f}")
    elif redness > REDNESS_CONCERNING and status not in ("Urgent",):
        status = "Concerning"
        reason.append(f"redness:{redness:.1f}")

    explanation = "; ".join(reason) if reason else "heuristic_default"

    return {
        "status": status,
        "delta_pct": delta,
        "quality": quality,
        "explanation": explanation
    }

# ---------------- Gemini / Generative Language integration ----------------
# --- Final GenAI (Gemini) SDK integration for decision.py ---
# Requires: pip install -U google-genai
# Env vars: GEMINI_API_KEY (or Google credentials), GEMINI_MODEL (optional, default "gemini-2.5-flash")

import os
from typing import Dict, Optional

try:
    from google import genai,types
    
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

_FALLBACK_TEMPLATES = {
    "Stable": "Status: Stable. Continue current wound care and follow up as scheduled.",
    "Monitor": "Status: Monitor. Observe wound daily; photograph change. Contact clinician if worsening.",
    "Concerning": "Status: Concerning. Consider nurse review; increase dressing frequency and monitor.",
    "Urgent": "Status: URGENT. Recommend immediate clinician review; consider in-person evaluation."
}

_client = None

def _init_genai_client():
    """Initialize genai Client. The client will pick up GEMINI_API_KEY from env if available."""
    global _client
    if _client is not None:
        return _client
    if not GENAI_AVAILABLE:
        return None
    try:
        _client = genai.Client()
        return _client
    except Exception as e:
        # Last-resort: try explicit api_key if user set GEMINI_API_KEY and genai.Client accepts it
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                _client = genai.Client(api_key=api_key)
                return _client
        except Exception:
            pass
        print("GenAI client init error:", repr(e))
        return None

def generate_llm_rationale(curr_metrics: Dict, prev_metrics: Optional[Dict], decision: Dict, context: Optional[Dict] = None) -> str:
    """
    Generate a clinician one-line summary + 4 patient bullets via Google GenAI SDK.
    Returns model text on success, otherwise returns a deterministic template fallback.
    """
    status = decision.get("status", "Monitor")
    delta = decision.get("delta_pct", 0.0)

    prompt_lines = [
        "You are a careful clinical assistant. Do not invent facts. Use ONLY the metrics and context provided.",
        "",
        f"Automated status: {status}",
        f"Metrics: area={curr_metrics.get('area')}, area_pct={curr_metrics.get('area_pct',0):.3f}, redness={curr_metrics.get('redness'):.1f}, exudate_ratio={curr_metrics.get('exudate_ratio'):.3f}",
        f"Delta_pct (vs previous): {delta:.1f}",
    ]

    if context:
        ctx_parts = []
        for k in ("age", "diabetes", "pain", "notes"):
            v = context.get(k)
            if v not in (None, ""):
                ctx_parts.append(f"{k}={v}")
        if ctx_parts:
            prompt_lines.append("Context: " + ", ".join(ctx_parts))

    prompt_lines.extend([
        "",
        "TASK:",
        "1) Provide a ONE-LINER clinician summary that explicitly cites which metric(s) led to this status.",
        "2) Provide FOUR short, plain-language bullet points for the patient: immediate care steps, warning signs, when to seek care, and one context-specific note.",
        "Be concise, factual, and do not add new clinical claims."
    ])

    prompt_text = "\n".join(prompt_lines)

    # Initialize client
    client = _init_genai_client()
    if client is None:
        return _FALLBACK_TEMPLATES.get(status, _FALLBACK_TEMPLATES["Monitor"])

    # Build a GenerateContentConfig using the SDK types
    try:
        gen_config = types.GenerateContentConfig(
            temperature=0.1,         # low randomness
            max_output_tokens=300,   # conservative token limit
            # optional: you can disable "thinking" budget for faster/cheaper output:
            # thinking_config=types.ThinkingConfig(thinking_budget=0)
        )

        # The SDK accepts contents as a single string or list (string is ok for text prompts)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt_text,
            config=gen_config
        )

        # SDK returns an object with .text containing the generated output
        if hasattr(response, "text") and response.text:
            return response.text.strip()

        # fallback stringification
        return str(response).strip()

    except Exception as e:
        # Print error for debugging during hackathon; return deterministic fallback
        try:
            print("GenAI call error:", repr(e))
        except Exception:
            pass
        return _FALLBACK_TEMPLATES.get(status, _FALLBACK_TEMPLATES["Monitor"])
