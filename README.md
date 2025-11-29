🩹 Smart Wound‑Care Concierge
AI‑Driven Wound Monitoring with Automated Analysis, Clinical Summaries & PDF Reporting
Built for MumbaiHacks ’25

Smart Wound‑Care Concierge is an AI‑assisted wound‑tracking platform that analyzes wound images, evaluates infection risk, generates clinician‑ready reports, and visualizes healing progress over time.
The entire pipeline runs locally using Python (no training required).

🚀 Quick Start
Prerequisites
Python 3.10+

pip

Virtual environment (recommended)

Installation & Running Locally
# 1. Clone the repository
git clone https://github.com/SilverTech21/smart-wound-watch.git

# 2. Navigate to the backend directory
cd smart-wound-watch

# 3. Create virtual environment
python3 -m venv wound

# 4. Activate environment
source wound/bin/activate   # macOS/Linux
wound\Scripts\activate      # Windows

# 5. Install dependencies
pip install -r requirements.txt

# 6. Run the app
streamlit run app/app.py
Your app will be available at:
👉 http://localhost:8501

⭐ Key Features
1. Wound Image Analysis (Perception Layer)
Python-based image processing extracts:

Wound area (px & %)

Redness score (RGB ratio)

Exudate ratio

Brightness score

Blur score (Variance of Laplacian)

Completely model‑free, fast, and lightweight.

2. Risk Classification (Decision Layer)
Rule‑based logic evaluates:

Redness thresholds

Exudate thresholds

Δ change from previous images

Blur/brightness quality

Trend worsening

Final statuses:
✔ Stable
✔ Monitor
✔ Concerning
✔ Urgent

3. AI-Powered Instructions & Summaries
Optional LLM module (Gemini/OpenRouter) generates:

Clinician summaries

Patient instructions

Automatic fallback to templates when offline.

4. Professional PDF Reports
Each report includes:

Image preview

All wound metrics

Status explanation

AI‑generated summaries

Timeline change (delta)

Timestamp + patient context

5. Healing Timeline & Records
Stored locally via SQLite or JSON:

Metrics history

Trend charts

Previous deltas

Clinician notes

Individual PDF reports

Scrollable and visually clean.

6. Clinician Dashboard
Includes:

All patients grouped by ID

Complete wound history

Alerts for urgent cases

Multi‑PDF export

📁 Project Structure
smart-wound-watch/
│── app/
│   ├── app.py                 # Streamlit frontend/UI
│   ├── perception.py          # Image processing & metrics
│   ├── decision.py            # Rule-based risk classification
│   ├── action.py              # LLM + PDF generation
│   ├── llm.py                 # optional AI helpers
│   ├── db.py                  # Local DB (SQLite / JSON)
│   └── data/                  # Temp images & PDFs
│
├── Wound_dataset/             # Raw wound dataset (optional)
├── requirements.txt
└── README.md
🛠 Tech Stack
Backend
Python 3

Streamlit

OpenCV

Pillow

SQLite

AI + Reports
Gemini / OpenRouter (optional)

FPDF

Frontend
Streamlit components

Custom CSS for medical‑grade UI

🧩 How the System Works
Upload
User uploads wound image + symptoms.

Analyze
Perception module extracts redness, area, blur, brightness, exudate.

Classify
Decision engine determines: Stable / Monitor / Concerning / Urgent.

Generate
AI summaries + patient instructions (optional).

Report
One‑click PDF generation.

Track
Users view wound history + trend charts.

Escalate
Urgent/Concerning → alert inside UI.

📦 Available Commands
streamlit run app/app.py     # Start app
pip install -r requirements.txt
🧪 Demo Workflow
Visit the landing page

Upload a wound image

View metrics: redness, area%, exudate, blur, brightness

Generate patient instructions

Download PDF report

Open Timeline → see historical analysis

Clinician View → alerts for risky wounds

⚠️ Disclaimer
This app is for educational and demonstration purposes only.
It is NOT a medical device and should not replace clinical advice.

👥 Team
Built with ❤️ for MumbaiHacks ‘25
By Team CuraCare
