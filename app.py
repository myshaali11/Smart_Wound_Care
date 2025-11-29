import streamlit as st
import os
import io
import json
from datetime import datetime
from PIL import Image

st.set_page_config(
    page_title="Smart Wound-Care Concierge",
    page_icon="🩹",
    layout="wide",
)

# ---- backend wiring ----
from perception import analyze_image
from decision import decide_status
from action import save_image_file, insert_record_sqlite, make_pdf_bytes, fetch_records, update_record_sqlite
from llm import generate_llm_rationale

# DB path
DB_PATH = "data/wound_records.db"

# session defaults
if "page" not in st.session_state:
    st.session_state.page = "Home"
if "uploaded" not in st.session_state:
    st.session_state.uploaded = None
if "timeline" not in st.session_state:
    st.session_state.timeline = []
if "latest_record" not in st.session_state:
    st.session_state.latest_record = None

# safe rerun helper — some Streamlit versions may not expose experimental_rerun
def try_rerun():
    fn = getattr(st, "experimental_rerun", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass

# ---------- BASIC THEME TWEAKS (INLINE CSS) ----------
st.markdown(
    """
    <style>
    /* Global */
    .main {
        background: radial-gradient(circle at top left, #eef4ff 0, #f8fbff 40%, #ffffff 100%);
        padding-top: 2rem;
    }
    h1, h2, h3, h4 {
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif;
    }
    .hero-title {
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        letter-spacing: -0.03em;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: #4b5563;
        max-width: 640px;
        text-align: center;
        margin: 0.75rem auto 0 auto;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        background: rgba(59,130,246,0.08);
        color: #2563eb;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .primary-btn {
        border-radius: 999px;
        padding: 0.85rem 1.75rem;
        border: none;
        background: linear-gradient(135deg, #2563eb, #4f46e5);
        color: white;
        font-weight: 600;
        font-size: 0.95rem;
        cursor: pointer;
        box-shadow: 0 18px 40px rgba(37, 99, 235, 0.35);
    }
    .primary-btn:hover {
        opacity: 0.95;
    }
    .ghost-btn {
        border-radius: 999px;
        padding: 0.85rem 1.75rem;
        border: 1px solid rgba(148,163,184,0.6);
        background: rgba(255,255,255,0.9);
        color: #0f172a;
        font-weight: 500;
        font-size: 0.95rem;
        cursor: pointer;
    }
    .ghost-btn:hover {
        background: white;
    }
    .hero-buttons {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin-top: 1.5rem;
    }
    .section-title {
        font-size: 1.8rem;
        font-weight: 700;
        text-align: center;
        margin-top: 3.5rem;
        margin-bottom: 0.5rem;
    }
    .section-subtitle {
        text-align: center;
        font-size: 0.95rem;
        color: #6b7280;
        margin-bottom: 1.5rem;
    }
    .card {
        background: white;
        border-radius: 1.25rem;
        padding: 1.25rem 1.35rem;
        box-shadow:
            0 16px 45px rgba(15, 23, 42, 0.08),
            0 0 0 1px rgba(148, 163, 184, 0.2);
        height: 100%;
    }
    .card-title {
        font-size: 1rem;
        font-weight: 600;
        margin-top: 0.6rem;
        margin-bottom: 0.3rem;
    }
    .card-body {
        font-size: 0.9rem;
        color: #6b7280;
    }
    .icon-circle {
        width: 2.4rem;
        height: 2.4rem;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(37,99,235,0.08);
        color: #2563eb;
        font-size: 1.1rem;
    }
    /* Timeline styles */
    .timeline-header { max-width:1100px; margin: 1.25rem auto; display:flex; justify-content:space-between; align-items:center }
    .timeline-title { font-size:1.9rem; font-weight:800; }
    .timeline-subtitle { color:#6b7280; margin-top:6px }
    .new-upload { border-radius:999px; padding:10px 16px; background: linear-gradient(90deg,#2563eb,#60a5fa); color:white; box-shadow: 0 10px 28px rgba(37,99,235,0.12); }
    .timeline-card { background: white; border-radius: 12px; padding: 12px 16px; box-shadow: 0 10px 30px rgba(15,23,42,0.06); display:flex; align-items:center; gap:14px; margin-bottom:14px }
    .thumbnail { width:72px; height:72px; border-radius:8px; object-fit:cover; }
    .status-badge { display:inline-block; padding:6px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
    .status-urgent { background:#fee2e2; color:#b91c1c }
    .status-monitor { background:#fff7ed; color:#b45309 }
    .status-stable { background:#ecfdf5; color:#15803d }
    .card-actions { margin-left:auto; display:flex; gap:8px; align-items:center }
    /* full-bleed hero panel for Home page */
    .hero-panel {
        position: relative;
        left: 50%;
        right: 50%;
        margin-left: -50vw;
        margin-right: -50vw;
        width: 100vw;
        background: linear-gradient(180deg,#eef6ff,#e8f3ff);
        padding:48px 24px 36px 24px;
        border-radius:12px 12px 0 0;
        text-align:center;
    }
    .hero-inner { max-width: 980px; margin: 0 auto; }
    .hero-panel h1 { margin:0 }
    .home-full-bg {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        min-height: 100vh;
        background: linear-gradient(180deg,#eef6ff,#f7fbff);
        z-index: -1;
        pointer-events: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- NAV BAR ----------
# Top navigation rendered as a sticky header with right-aligned nav pills
st.markdown(
    """
    <style>
    .topbar { position: sticky; top:0; z-index:9999; background: #ffffff; border-bottom:1px solid rgba(15,23,42,0.04); }
    .topbar-inner { max-width:1200px; margin:0 auto; display:flex; align-items:center; justify-content:space-between; padding:12px 18px; }
    .brand { display:flex; align-items:center; gap:12px; font-weight:700; color:#0f172a }
    .brand .logo { width:36px; height:36px; border-radius:8px; background: linear-gradient(90deg,#60a5fa,#7c3aed); display:flex; align-items:center; justify-content:center; color:white }
    .nav-row { display:flex; gap:12px; align-items:center }
    .nav-btn { padding:8px 14px; border-radius:12px; border:1px solid transparent; background:transparent; color:#64748b; cursor:pointer }
    .nav-btn.active { background: linear-gradient(90deg,#2563eb,#4f46e5); color:white; box-shadow: 0 10px 30px rgba(79,70,229,0.12); }
    .nav-ghost { padding:6px 10px; border-radius:10px; color:#0f172a; background:#fff; border:1px solid rgba(15,23,42,0.04) }
    </style>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns([1, 3])
with col1:
    st.markdown("<div class='topbar'><div class='topbar-inner'><div class='brand'><div class='logo'>💙</div><div style='font-size:16px'>WoundCare</div></div><div id='nav-placeholder'></div></div></div>", unsafe_allow_html=True)
with col2:
    # render nav buttons on the right using Streamlit buttons so they are interactive
    nav1, nav2, nav3, nav4 = st.columns([1,1,1,1])
    def nav_button(label, key, emoji=None):
        is_active = (st.session_state.get('page') == label)
        btn_label = f"{emoji} {label}" if emoji else label
        if is_active:
            # render as a highlighted button
            if st.button(btn_label, key=key):
                st.session_state.page = label
                try_rerun()
        else:
            if st.button(btn_label, key=key):
                st.session_state.page = label
                try_rerun()
    with nav1:
        nav_button('Home', 'nav_home', '♡')
    with nav2:
        nav_button('Upload', 'nav_upload', '📤')
    with nav3:
        nav_button('Timeline', 'nav_timeline', '🕒')
    with nav4:
        nav_button('Clinician', 'nav_clinician', '🩺')

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ---------- HERO & FEATURE (only on Home) ----------
if st.session_state.get('page') == 'Home':
    # full-page light-blue background (behind all home content)
    st.markdown("<div class='home-full-bg'></div>", unsafe_allow_html=True)
    with st.container():
        # hero-panel centers and gives a light-blue background
        st.markdown("<div class='hero-panel'>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class='hero-inner'>
              <div style="display:flex; justify-content:center; margin-top:1rem;">
                <div class="pill">
                    <span>💡</span>
                    <span>Intelligent Wound Monitoring</span>
                </div>
              </div>
              <h1 class="hero-title">
                Smart Wound‑Care<br/>
                <span style="background:linear-gradient(135deg,#2563eb,#38bdf8); -webkit-background-clip:text; color:transparent;">
                    Concierge
                </span>
              </h1>
              <p class="hero-subtitle" style="margin-top:8px">
                Track wound healing with AI‑powered analysis, get personalized care instructions, and know exactly when to seek medical attention.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Hero CTA buttons (functional) - centered beneath title
        outer1, outer2, outer3 = st.columns([1,2,1])
        with outer2:
            b1, b2 = st.columns([1,1], gap='small')
            with b1:
                if st.button("Upload Wound Image", key="hero_to_upload"):
                    st.session_state.page = "Upload"
                    try_rerun()
            with b2:
                if st.button("View Timeline", key="hero_to_timeline"):
                    st.session_state.page = "Timeline"
                    try_rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)

# ---------- FEATURE SECTION (Home only) ----------
if st.session_state.get('page') == 'Home':
    st.markdown(
        """
        <div class="section-title">Comprehensive Wound Management</div>
        <div class="section-subtitle">
            Monitor wound metrics, track healing trends, and generate clinician‑ready reports in one place.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="card">
                <div class="icon-circle">📊</div>
                <div class="card-title">AI Wound Analysis</div>
                <div class="card-body">
                    Automatically extract wound area, redness, exudate ratio, and image quality checks in seconds.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="card">
                <div class="icon-circle">🚦</div>
                <div class="card-title">Risk Classification</div>
                <div class="card-body">
                    Instantly classify status as Stable, Monitor, Concerning, or Urgent to guide next clinical steps.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="card">
                <div class="icon-circle">🧾</div>
                <div class="card-title">Clinician‑Ready Reports</div>
                <div class="card-body">
                    Generate structured PDF summaries with metrics, trend snapshots, and clear escalation notes.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Home page content handled via global hero + feature sections above

# ---------- Page: Upload ----------
if st.session_state.get('page') == 'Upload':
    st.markdown("<div style='max-width:1100px;margin:0 auto' class='page'>", unsafe_allow_html=True)
    left, right = st.columns([1.6, 1], gap='large')
    with left:
        uploaded = st.file_uploader("Upload wound photo (png, jpg)", type=["png", "jpg", "jpeg"], key="uploader")
        name = st.text_input("Patient name", key="patient_name")
        age = st.number_input("Age", min_value=0, max_value=120, value=60)
        notes = st.text_area("Notes / allergies / location", key="notes")
        consent = st.checkbox("Patient consents to analysis", value=True, key="consent")
        if uploaded is not None:
            st.session_state.uploaded = uploaded
        if st.button("Analyze Wound", key="analyze"):
            if not st.session_state.uploaded:
                st.warning("Please upload an image first.")
            elif not consent:
                st.warning("Consent required to analyze.")
            else:
                try:
                    raw = st.session_state.uploaded.getvalue()
                    pil = Image.open(io.BytesIO(raw)).convert("RGB")
                    metrics = analyze_image(pil)
                    # serialize metrics
                    clean_metrics = {}
                    for k, v in (metrics or {}).items():
                        if hasattr(v, 'tolist'):
                            clean_metrics[k] = v.tolist()
                        else:
                            try:
                                json.dumps(v)
                                clean_metrics[k] = v
                            except Exception:
                                clean_metrics[k] = str(v)
                    prev = st.session_state.timeline[0].get('metrics') if st.session_state.timeline else None
                    decision = decide_status(clean_metrics, prev)
                    try:
                        rationale = generate_llm_rationale(clean_metrics, prev, decision, {"name": name, "notes": notes})
                    except Exception:
                        rationale = None
                    saved = save_image_file(pil)
                    record = {"image_path": saved, "timestamp": datetime.utcnow().isoformat(), "metrics": clean_metrics, "decision": decision, "rationale": rationale, "context": {"name": name, "age": age, "notes": notes}}
                    rec_id = insert_record_sqlite(DB_PATH, record)
                    record['id'] = rec_id
                    st.session_state.latest_record = record
                    st.session_state.timeline.insert(0, {"time": datetime.now().strftime('%Y-%m-%d %H:%M'), "text": f"{decision.get('status','Unknown')}", "metrics": clean_metrics, "id": rec_id})
                    st.success("Analysis completed.")
                except Exception as e:
                    st.error(f"Failed: {e}")
    with right:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<b>Latest Analysis</b>", unsafe_allow_html=True)
        lr = st.session_state.get('latest_record')
        if lr:
            if lr.get('image_path') and os.path.exists(lr.get('image_path')):
                st.image(lr.get('image_path'), use_column_width=True)
            st.markdown(f"<div style='margin-top:8px'><b>Status:</b> {lr.get('decision',{}).get('status','-')}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            with st.expander('Clinician summary / tips', expanded=True):
                st.write(lr.get('rationale') or 'No summary available')
            try:
                pdf = make_pdf_bytes(lr)
                safe_ts = lr.get('timestamp', datetime.utcnow().isoformat()).replace(':','-')
                st.download_button('📄 Download PDF', data=pdf, file_name=f'wound_report_{safe_ts}_{lr.get("id")}.pdf', mime='application/pdf')
            except Exception as e:
                st.write('PDF generation error:', e)
        else:
            st.info('No analysis yet')
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Page: Timeline ----------
if st.session_state.get('page') == 'Timeline':
    # header with title + new upload button
    st.markdown("<div class='timeline-header'>", unsafe_allow_html=True)
    with st.container():
        st.markdown("<div style='max-width:1100px;margin:0'>", unsafe_allow_html=True)
        c1, c2 = st.columns([6,1])
        with c1:
            st.markdown("<div class='timeline-title'>Wound Timeline</div>", unsafe_allow_html=True)
            st.markdown("<div class='timeline-subtitle'>Track your healing progress over time</div>", unsafe_allow_html=True)
        with c2:
            if st.button('+ New Upload', key='timeline_new_upload'):
                st.session_state.page = 'Upload'
                try_rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    tabs = st.tabs(["Timeline", "Trends"])
    # Timeline tab
    with tabs[0]:
        st.markdown("<div style='max-width:1100px;margin:0 auto;padding-top:8px'>", unsafe_allow_html=True)
        records = fetch_records(DB_PATH, limit=200)
        if not records:
            st.info('No records yet')
        else:
            for r in records:
                # build display timestamp
                ts = r.get('timestamp')
                try:
                    dt = datetime.fromisoformat(ts)
                    disp = dt.strftime('%a, %b %d, %I:%M %p')
                except Exception:
                    disp = ts

                with st.container():
                    cols = st.columns([0.12, 5, 0.6])
                    thumb_col, info_col, act_col = cols
                    with thumb_col:
                        if r.get('image_path') and os.path.exists(r.get('image_path')):
                            st.image(r.get('image_path'), use_container_width=True, output_format='PNG')
                        else:
                            st.markdown('<div style="width:72px;height:72px;border-radius:8px;background:#f3f4f6"></div>', unsafe_allow_html=True)
                    with info_col:
                        status = r.get('decision',{}).get('status','-')
                        badge_class = 'status-stable'
                        if status and status.lower().startswith('urgent'):
                            badge_class = 'status-urgent'
                        elif status and status.lower().startswith('concerning') or status.lower().startswith('monitor'):
                            badge_class = 'status-monitor'

                        st.markdown(f"<div class='timeline-card'><div><span class='status-badge {badge_class}'>{status}</span><div style='height:6px'></div><div style='color:#475569'>" + disp + "</div></div>", unsafe_allow_html=True)
                        with st.expander('Details'):
                            st.write('Metrics:', r.get('metrics'))
                            st.write('Context:', r.get('context'))
                    with act_col:
                        try:
                            pdf_bytes = make_pdf_bytes(r)
                            safe_ts = (r.get('timestamp') or datetime.utcnow().isoformat()).replace(':','-')
                            st.download_button('📄', data=pdf_bytes, file_name=f'wound_report_{safe_ts}_{r.get("id")}.pdf', key=f'dl_{r.get("id")}', mime='application/pdf')
                        except Exception:
                            st.button('📄', key=f'dl_{r.get("id")}_err')
        st.markdown('</div>', unsafe_allow_html=True)

    # Trends tab (placeholder)
    with tabs[1]:
        st.markdown("<div style='max-width:1100px;margin:0 auto;padding-top:8px'>", unsafe_allow_html=True)
        st.info('Trends view coming soon — shows area and redness over time.')
        st.markdown('</div>', unsafe_allow_html=True)

# ---------- Page: Clinician ----------
if st.session_state.get('page') == 'Clinician':
    st.markdown("<div style='max-width:1100px;margin:0 auto' class='page'>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Clinician Dashboard</div>', unsafe_allow_html=True)
    recs = fetch_records(DB_PATH, limit=1000)
    if not recs:
        st.info('No records')
    else:
        # compute patients grouped by context.name
        patients = {}
        for r in recs:
            name = (r.get('context') or {}).get('name') or 'Unknown'
            patients.setdefault(name, []).append(r)

        # count urgent across all
        urgent_count = sum(1 for r in recs if (r.get('decision') or {}).get('status','').lower().startswith('urgent'))
        if urgent_count:
            st.markdown(f"<div style='background:#fee2e2;border:1px solid #fca5a5;padding:14px;border-radius:10px;margin-bottom:14px'><b>{urgent_count} wound requiring attention</b><div style='color:#7f1d1d'>Review urgent and concerning cases below</div></div>", unsafe_allow_html=True)

        left_col, right_col = st.columns([1,3], gap='large')

        # Left: patient list
        with left_col:
            st.markdown("<div class='card'><b>Patients</b></div>", unsafe_allow_html=True)
            names = list(patients.keys())
            sel_name = st.selectbox('Select patient', names, index=0, key='clin_patient')
            # display a simple list
            for n in names:
                count = len(patients[n])
                # derive patient status (worst)
                statuses = [ (pr.get('decision') or {}).get('status','').lower() for pr in patients[n] ]
                pstatus = 'Stable'
                if any(s.startswith('urgent') for s in statuses):
                    pstatus = 'Urgent'
                elif any(s.startswith('concerning') or s.startswith('monitor') for s in statuses):
                    pstatus = 'Concerning'
                # pick colors
                if pstatus == 'Urgent':
                    badge_bg = '#fee2e2'
                    badge_color = '#b91c1c'
                elif pstatus == 'Concerning':
                    badge_bg = '#fff7ed'
                    badge_color = '#b45309'
                else:
                    badge_bg = '#ecfdf5'
                    badge_color = '#15803d'

                html = (
                    "<div style='padding:10px;border-radius:8px;margin-top:8px;background:#f8fafc;display:flex;justify-content:space-between;align-items:center'>"
                    f"<div><b>{n}</b><div style='font-size:12px;color:#6b7280'>{count} entries</div></div>"
                    f"<div style='padding:6px 10px;border-radius:999px;background:{badge_bg};color:{badge_color}'>{pstatus}</div>"
                    "</div>"
                )
                st.markdown(html, unsafe_allow_html=True)

        # Right: patient dashboard
        with right_col:
            selected_patient = sel_name
            entries = patients.get(selected_patient, [])
            first_visit = entries[-1].get('timestamp') if entries else ''
            st.markdown("<div style='display:flex;justify-content:space-between;align-items:center'><div><h3 style='margin:0'>" + selected_patient + "</h3><div style='color:#6b7280'>First visit: " + (first_visit or '') + "</div></div>", unsafe_allow_html=True)
            # Download all reports (zip)
            try:
                import zipfile
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w') as zf:
                    for e in entries:
                        try:
                            pdfb = make_pdf_bytes(e)
                            name = f"report_{e.get('id')}.pdf"
                            zf.writestr(name, pdfb)
                        except Exception:
                            pass
                buf.seek(0)
                st.download_button('Download All Reports', data=buf.read(), file_name=f'{selected_patient}_reports.zip', mime='application/zip')
            except Exception:
                st.button('Download All Reports')

            # Tabs: Overview / Timeline / Trends
            t1, t2, t3 = st.tabs(['Overview','Timeline','Trends'])
            with t1:
                # summary cards
                total = len(entries)
                stable = sum(1 for e in entries if (e.get('decision') or {}).get('status','').lower().startswith('stable'))
                concerning = sum(1 for e in entries if (e.get('decision') or {}).get('status','').lower().startswith('concerning') or (e.get('decision') or {}).get('status','').lower().startswith('monitor'))
                urgent = sum(1 for e in entries if (e.get('decision') or {}).get('status','').lower().startswith('urgent'))
                ccol1, ccol2, ccol3, ccol4 = st.columns(4)
                ccol1.markdown(f"<div class='card' style='text-align:center'><div style='font-weight:700'>{total}</div><div style='color:#6b7280'>Total Entries</div></div>", unsafe_allow_html=True)
                ccol2.markdown(f"<div class='card' style='text-align:center;color:#15803d'><div style='font-weight:700'>{stable}</div><div style='color:#6b7280'>Stable</div></div>", unsafe_allow_html=True)
                ccol3.markdown(f"<div class='card' style='text-align:center;color:#b45309'><div style='font-weight:700'>{concerning}</div><div style='color:#6b7280'>Concerning</div></div>", unsafe_allow_html=True)
                ccol4.markdown(f"<div class='card' style='text-align:center;color:#b91c1c'><div style='font-weight:700'>{urgent}</div><div style='color:#6b7280'>Urgent</div></div>", unsafe_allow_html=True)

                # Recent Alerts
                alerts = [e for e in entries if (e.get('decision') or {}).get('status','').lower().startswith('urgent') or (e.get('decision') or {}).get('status','').lower().startswith('concerning')]
                if alerts:
                    st.markdown("<div style='margin-top:16px' class='card'><b>Recent Alerts</b><div style='height:10px'></div>", unsafe_allow_html=True)
                    for a in alerts:
                        ts = a.get('timestamp')
                        try:
                            dt = datetime.fromisoformat(ts)
                            disp = dt.strftime('%m/%d/%Y, %I:%M:%S %p')
                        except Exception:
                            disp = ts
                        st.markdown(f"<div style='padding:10px;border-radius:8px;background:#f8fafc;margin-bottom:8px;display:flex;align-items:center;gap:12px'><div style='padding:6px 10px;border-radius:8px;background:#fee2e2;color:#b91c1c;font-weight:700'>Urgent</div><div style='color:#0f172a'>" + (a.get('rationale') or 'Wound assessment alert') + f"</div><div style='margin-left:auto;color:#6b7280'>{disp}</div></div>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info('No recent alerts')

            with t2:
                st.info('Patient timeline — entries listed below')
                for e in sorted(entries, key=lambda x: x.get('timestamp',''), reverse=True):
                    st.markdown(f"**{e.get('timestamp')}** — { (e.get('decision') or {}).get('status','-') } (ID: {e.get('id')})")

            with t3:
                st.info('Trends coming soon')


    st.markdown('</div>', unsafe_allow_html=True)
