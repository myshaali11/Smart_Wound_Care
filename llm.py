import os
import requests
from typing import Optional, Dict


def _build_prompt(metrics: Dict, prev_metrics: Optional[Dict], decision: Dict, context: Dict) -> str:
    parts = [
        "You are a concise clinician assistant. Given wound image analysis metrics and patient context, produce:",
        "1) A short (2-4 sentence) clinician summary explaining the current wound status in plain language.",
        "2) 4 suggested next steps the patient or clinician can take now (bullet list).",
        "3) Indicate urgency (Routine / Monitor / Urgent)."
    ]
    parts.append("\nProvide a friendly, empathetic tone and actionable steps. Use short bullets.")

    parts.append("\n---\nMetrics:")
    for k, v in (metrics or {}).items():
        parts.append(f"- {k}: {v}")

    if prev_metrics:
        parts.append("\nPrevious metrics:")
        for k, v in prev_metrics.items():
            parts.append(f"- {k}: {v}")

    parts.append("\nDecision:")
    for k, v in (decision or {}).items():
        parts.append(f"- {k}: {v}")

    parts.append("\nPatient context:")
    for k, v in (context or {}).items():
        parts.append(f"- {k}: {v}")

    parts.append("\n---\nWrite the summary now:")
    return "\n".join(parts)


def generate_llm_rationale(metrics: Dict, prev_metrics: Optional[Dict], decision: Dict, context: Dict, model: str = "gemini-2.5-flash", api_key: Optional[str] = None) -> str:
    """Generate a clinician-style rationale using Google Generative Language API (Gemini).

    This function first tries a direct REST call to the Generative Language API using an API key.
    If the call fails or the API key is missing, it returns a safe fallback summary based on the decision.
    """
    prompt = _build_prompt(metrics, prev_metrics, decision, context)

    api_key = api_key or os.getenv("GEMINI_API_KEY") 

    if api_key:
        # REST endpoint - generativelanguage API v1beta2
        url = f"https://generativelanguage.googleapis.com/v1beta2/models/{model}:generate?key={api_key}"
        body = {
            "prompt": {"text": prompt},
            "temperature": 0.2,
            "maxOutputTokens": 512,
        }
        try:
            resp = requests.post(url, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            # response candidates typically under 'candidates' with 'output'
            if isinstance(data, dict):
                if "candidates" in data and data["candidates"]:
                    return data["candidates"][0].get("output", "")
                # newer formats may return 'output' or 'result'
                if "output" in data:
                    return data.get("output", "")
                # try nested
                for key in ("candidates", "outputs", "results"):
                    if key in data and data[key]:
                        item = data[key][0]
                        for f in ("content", "output", "text", "result"):
                            if f in item:
                                return item[f]
            return ""  # empty but non-error
        except Exception as e:
            # fall through to fallback
            print(f"LLM call failed: {e}")

    # Fallback: generate a simple human-friendly rationale without LLM
    status = (decision or {}).get("status", "Unknown")
    lines = []
    lines.append(f"Status: {status}.")
    # Suggest basic actions based on keywords
    s = status.lower() if isinstance(status, str) else ""
    if "infect" in s or "high" in s or "urgent" in s:
        lines.append("This wound may be infected or require urgent assessment. Contact a clinician promptly.")
        lines.append("Suggested next steps:")
        lines.append("- Seek urgent clinical review or primary care contact.")
        lines.append("- Keep the area clean and avoid applying unprescribed treatments.")
        lines.append("- If there is spreading redness, fever, or increasing pain, go to emergency care.")
    else:
        lines.append("The wound appears stable. Continue local wound care and monitor for changes.")
        lines.append("Suggested next steps:")
        lines.append("- Clean with saline and apply a clean dressing daily.")
        lines.append("- Monitor for increased redness, swelling, or discharge.")
        lines.append("- Follow up with your clinician within 3–7 days or sooner if concerned.")

    return "\n".join(lines)
