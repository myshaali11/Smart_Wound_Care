# 🩹 Smart Wound‑Care Concierge  
**AI‑driven wound monitoring with automated analysis, risk classification, and clinician‑grade reporting**  
Built for **MumbaiHacks ’25**.

---

## ⭐ Overview
Smart Wound‑Care Concierge is an end‑to‑end wound‑monitoring system that uses simple computer‑vision heuristics + LLM‑generated summaries to assist patients and clinicians.  
It analyzes uploaded wound images, tracks healing over time, detects risk levels, and generates PDF reports — all through a clean, responsive interface.

---

## 🚀 Key Features

### 📷 1. Image Analysis (Perception Layer)
Implemented in **`perception.py`**:
- Wound area (px & %)
- Redness score (R/G/B heuristic)
- Exudate ratio
- Brightness level
- Blur/quality score  
- Optional wound mask for visualization

### 🧠 2. Risk Classification (Decision Layer)
Through **`decision.py`**, the rule‑engine determines:  
- **Stable**  
- **Monitor**  
- **Concerning**  
- **Urgent**

Uses thresholds on redness, exudate, delta change, and image quality.

### 🤖 3. AI‑Generated Instructions & Summaries (LLM Layer)
Using **Gemini (free-tier compatible)** via **`llm.py`**, the system generates:
- Clinician‑style summaries
- Patient‑friendly care instructions
- Escalation guidance
- Context‑aware reasoning (age, diabetes, pain, notes)

If LLM fails → automatic fallback template.

### 📄 4. Professional PDF Reports (Action Layer)
Built in **`action.py`** using ReportLab / FPDF:
- Wound image  
- Metrics table  
- Status explanation  
- LLM summary + instructions  
- Timestamp & patient details  
- "Not medical advice" footer

### 🕒 5. Healing Timeline & Records
Stored using SQLite / JSON via **`data/`**:
- All past wound entries  
- Metrics over time  
- Trend deltas  
- Clinician notes  

Displayed in UI as a scrollable timeline + trend charts.

---

## 📁 Project Structure

```
app/
├── app.py             # Main Streamlit UI
├── action.py          # PDF generation + AI instruction pipeline
├── perception.py      # Image analysis (CV heuristics)
├── decision.py        # Risk classification logic
├── llm.py             # Gemini API + fallback templates
├── data/              # Stored DB / JSON files
└── __init__.py
Wound_dataset/         # Image dataset (optional)
requirements.txt
```

---

## 💻 Running Locally

### 1. Activate your virtual environment
```bash
source wound/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the app
```bash
streamlit run app/app.py
```

App opens at:  
👉 **http://localhost:8501**

---

## 🧪 Workflow (End‑to‑End)

1️⃣ **Upload wound image**  
2️⃣ **Perception** computes redness, area %, exudate, blur, brightness  
3️⃣ **Decision engine** assigns: Stable / Monitor / Concerning / Urgent  
4️⃣ **LLM** generates summary + instructions  
5️⃣ **Action layer** produces PDF  
6️⃣ **Database** updates timeline  
7️⃣ **Clinician view** displays alerts + history  

---

## 📦 Tech Stack
- **Python 3.11**  
- **Streamlit UI**  
- **OpenCV (cv2)** image processing  
- **Gemini LLM API**  
- **ReportLab / FPDF** PDF generation  
- **SQLite / JSON** storage  
- **Matplotlib / Plotly** for charts  

---

## ⚠️ Disclaimer
This tool is strictly for **educational + demonstration purposes**.  
Not intended for real medical diagnosis or treatment.

---

## 👥 Team
Built with ❤️ by  
**Team CuraCare** (MumbaiHacks ’25)

