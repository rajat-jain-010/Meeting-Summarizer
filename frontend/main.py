import streamlit as st
import requests
import time
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- Config ---
st.set_page_config(layout="wide")
BACKEND_URL = "http://localhost:8000"

# --- Title ---
st.markdown("<h1 style='text-align: center; color: #4CAF50;'>Meeting Mind</h1>", unsafe_allow_html=True)

# --- Input Choice ---
st.subheader("Upload Input Type")
input_type = st.radio(
    "Choose your input source:",
    ["Audio/Video File", "Direct Transcript"],
    horizontal=True
)

# --- Session State Setup ---
if "transcript" not in st.session_state:
    st.session_state["transcript"] = ""
if "is_processing" not in st.session_state:
    st.session_state["is_processing"] = False
if "report_data" not in st.session_state:
    st.session_state["report_data"] = None

# --- File Upload or Transcript ---
if input_type == "Audio/Video File":
    uploaded_file = st.file_uploader("Upload your audio or video file", type=["mp3", "wav", "mp4", "mkv"])

    if uploaded_file:
        if uploaded_file.size > 100 * 1024 * 1024:
            st.error("File size exceeds 100MB. Please upload a smaller file.")
        else:
            if st.button("Transcribe", disabled=st.session_state["is_processing"]):
                st.session_state["is_processing"] = True
                with st.spinner("Transcribing... Please wait."):
                    try:
                        files = {"file": uploaded_file}
                        res = requests.post(f"{BACKEND_URL}/upload_audio_video/", files=files)
                        res.raise_for_status()
                        st.session_state["transcript"] = res.json()["transcript"]
                    except requests.exceptions.RequestException as e:
                        st.error(f"Transcription failed: {e}")
                st.session_state["is_processing"] = False

    if st.session_state["transcript"]:
        st.markdown("### Transcript")
        st.text_area("Transcribed Text", value=st.session_state["transcript"], height=300, disabled=True)

else:
    st.session_state["transcript"] = st.text_area("Paste your transcript here", height=300)

# --- Generate Report ---
report_data = None
generate_report_button = st.button("Generate Report", disabled=st.session_state["is_processing"])

if generate_report_button and st.session_state["transcript"].strip():
    word_count = len(st.session_state["transcript"].strip().split())
    if word_count < 50:
        st.warning("Transcript has less than 50 words. Cannot generate report.")
    else:
        st.session_state["is_processing"] = True
        with st.spinner("Generating report..."):
            try:
                res = requests.post(f"{BACKEND_URL}/generate_report/", json={"transcript": st.session_state["transcript"]})
                res.raise_for_status()
                st.session_state["report_data"] = res.json()
            except requests.exceptions.RequestException as e:
                st.error(f"Error during report generation: {e}")
        st.session_state["is_processing"] = False

# --- Render Layout ---
if st.session_state["report_data"]:
    responses = {
        "Overview": {
            "Discussion Type": st.session_state["report_data"].get("discussion_type", "N/A"),
            "Summary": st.session_state["report_data"].get("summary", "N/A")
        },
        "Key Actions": {
            "Key Points": st.session_state["report_data"].get("keypoint", "No keypoints found."),
        },
        "Risks & Updates": {
            "Problems": st.session_state["report_data"].get("problem_solution_tech", "No problems found."),
            "Solutions": st.session_state["report_data"].get("solutions", "No solutions found."),
            "Tech": st.session_state["report_data"].get("tech", "No tech points found.")
        },
        "Final Notes": {
            "Action Items": st.session_state["report_data"].get("action_item", "No action items found."),
        }
    }

    left, right = st.columns([3, 4])

    with left:
        st.markdown("### Discussion Type & Summary")
        st.markdown(
            "<div style='height: 776px; overflow-y: auto; border: 1px solid #ccc; padding: 18px; border-radius: 10px; background-color: #f7f7f7;color: black; font-weight: bold;'>"
            + "".join([f"<p><strong>{k}:</strong> {v}</p>" for k, v in responses["Overview"].items()])
            + "</div>",
            unsafe_allow_html=True
        )

    with right:
        st.markdown("### Key Points")
        st.markdown(
            "<div style='height: 360px; overflow-y: auto; border: 1px solid #ccc; padding: 14px; border-radius: 10px; background-color: #eef6ff; color: black; font-weight: bold;'>"
            + "".join([f"<p><strong>{k}:</strong> {v}</p>" for k, v in responses["Key Actions"].items()])
            + "</div>",
            unsafe_allow_html=True
        )

        st.markdown("### Problem & Solution")
        st.markdown(
            "<div style='height: 360px; overflow-y: auto; border: 1px solid #ccc; padding: 14px; border-radius: 10px; background-color: #fffbe6; color: black; font-weight: bold;'>"
            + "".join([f"<p><strong>{k}:</strong> {v}</p>" for k, v in responses["Risks & Updates"].items()])
            + "</div>",
            unsafe_allow_html=True
        )

    st.markdown("### Action Items")
    st.markdown(
        "<div style='height: 300px; overflow-y: auto; border: 1px solid #ccc; padding: 14px; border-radius: 10px; background-color: #e6ffee; color: black; font-weight: bold;'>"
        + "".join([f"<p><strong>{k}:</strong> {v}</p>" for k, v in responses["Final Notes"].items()])
        + "</div>",
        unsafe_allow_html=True
    )

    # --- PDF Generation and Download ---
    def generate_pdf(data_dict):
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 40
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, "Smart Minutes Report")
        c.setFont("Helvetica", 12)
        y -= 30

        for section, content in data_dict.items():
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y, section)
            y -= 20
            c.setFont("Helvetica", 12)
            for key, value in content.items():
                if not value:
                    value = "N/A"  # Handle None or empty string
                lines = value.split("\n")
                c.drawString(60, y, f"{key}:")
                y -= 15
                for line in lines:
                    for wrapped_line in [line[i:i+90] for i in range(0, len(line), 90)]:
                        c.drawString(80, y, wrapped_line)
                        y -= 15
                        if y < 50:
                            c.showPage()
                            y = height - 40
                y -= 10
            y -= 10

        c.save()
        buffer.seek(0)
        return buffer


    pdf_buffer = generate_pdf(responses)
    st.download_button(
        label="📄 Download Report as PDF",
        data=pdf_buffer,
        file_name="smart_minutes_report.pdf",
        mime="application/pdf"
    )
else:
    st.info("Upload a file or paste a transcript to get started.")