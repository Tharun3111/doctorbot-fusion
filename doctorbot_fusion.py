
# doctorbot_fusion.py
import os
import openai
import requests
import streamlit as st
import pymongo
from dotenv import load_dotenv
from fpdf import FPDF
from datetime import datetime

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Setup MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client.doctorbot
diagnosis_collection = db.diagnosis_history

# ------------------------------
# Query Perplexity (Data Fetcher)
# ------------------------------
def query_perplexity(prompt):
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "content-type": "application/json"
    }
    payload = {
        "model": "sonar-medium-online",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload)
    return response.json()["choices"][0]["message"]["content"]

# ------------------------------
# Query ChatGPT-4o (Reasoner)
# ------------------------------
def query_chatgpt_fusion(symptoms, context):
    fusion_prompt = f"""
You are a medical diagnosis assistant.

Use the following clinical reference as background:
{context}

Now analyze the patient symptoms:
{symptoms}

Return your response in this exact structure:
Disease(s): ...
Severity: ...
Tests: ...
Medications: ...
Blood Report Flags: ...
Home Remedies: ...
Lifestyle Advice: ...
Referral: ...
Red Flags: ...
"""
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": fusion_prompt}],
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()

# ------------------------------
# PDF Generator
# ------------------------------
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "DoctorBot Diagnosis Summary", ln=True, align="C")

    def add_section(self, title, content):
        self.set_font("Arial", 'B', 11)
        self.cell(0, 10, title, ln=True)
        self.set_font("Arial", '', 10)
        self.multi_cell(0, 10, content)

def export_pdf(data):
    pdf = PDF()
    pdf.add_page()
    for section, content in data.items():
        pdf.add_section(section, content)
    path = "doctorbot_summary.pdf"
    pdf.output(path)
    return path

# ------------------------------
# Streamlit UI
# ------------------------------
st.set_page_config(page_title="🧠 DoctorBot Fusion Engine")
st.title("🧑‍⚕️ DoctorBot: ChatGPT-4o + Perplexity Pro Diagnosis")

symptoms = st.text_area("🔎 Describe the patient's symptoms in detail (min 30 words):", height=200)

if st.button("💡 Generate Diagnosis"):
    if len(symptoms.split()) < 30:
        st.warning("Please enter at least 30 words for meaningful analysis.")
        st.stop()

    with st.spinner("🤖 Fetching medical data and analyzing..."):
        reference = query_perplexity(symptoms)
        diagnosis = query_chatgpt_fusion(symptoms, reference)

    st.subheader("📚 Clinical Reference (Perplexity)")
    st.text_area("Perplexity Output", reference, height=200)

    st.subheader("🧠 Structured Diagnosis (ChatGPT-4o)")
    st.text_area("DoctorBot Diagnosis", diagnosis, height=300)

    # Save to MongoDB
    doc = {
        "timestamp": datetime.now(),
        "symptoms": symptoms,
        "perplexity_output": reference,
        "chatgpt_output": diagnosis,
        "fusion_summary": diagnosis
    }
    diagnosis_collection.insert_one(doc)

    st.subheader("📄 Download Diagnosis Report")
    pdf_path = export_pdf({
        "Symptoms": symptoms,
        "Perplexity Reference": reference,
        "ChatGPT-4o Diagnosis": diagnosis
    })
    with open(pdf_path, "rb") as f:
        st.download_button("📥 Download PDF", f, file_name="doctorbot_diagnosis.pdf")

    st.subheader("🔁 Retry or Explain")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Retry"):
            st.rerun()
    with col2:
        if st.button("ℹ️ Explain Diagnosis"):
            explain = query_chatgpt_fusion(symptoms, reference + "\nExplain the reasoning behind each diagnosis.")
            st.text_area("🧬 Explanation", explain, height=250)

st.subheader("📘 Recent Patient Diagnoses")
history = diagnosis_collection.find().sort("timestamp", -1).limit(5)
for record in history:
    st.markdown(f"""
**🕒 {record['timestamp'].strftime('%Y-%m-%d %H:%M')}**
- **Symptoms:** {record['symptoms'][:100]}...
- **Diagnosis:** {record['chatgpt_output'][:120]}...
""")
