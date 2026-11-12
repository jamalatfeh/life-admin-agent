import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Life Admin Agent", layout="wide")
st.title("🛂 Life Admin Agent")
st.markdown("**Demo: Track your UAE document expiries.**")

st.sidebar.header("Agent Rules")
st.sidebar.info("1. Dual-reader extraction (Regex + AI).\n2. If readers disagree, you confirm.\n3. The agent drafts. The human sends.")

# --- THE DEMO UI ---
st.write("### 1. Upload a Document")
uploaded_file = st.file_uploader("Upload Visa, Emirates ID, or Passport", type=["txt", "pdf", "png", "jpg"])

# --- MOCK LOGIC (Simulating the engine) ---
if uploaded_file is not None:
    st.write("### 2. Dual-Reader Extraction")
    
    # Simulate the two readers
    reader_a = "2027-01-01" # Regex output
    reader_b = "2027-01-01" # AI output
    
    # Check for the ambiguous demo case
    if uploaded_file.name == "ambiguous.txt":
        reader_a = "2027-04-03" # DD/MM
        reader_b = "2027-03-04" # MM/DD
    
    # Check for the injection demo case
    file_content = uploaded_file.read().decode("utf-8", errors="ignore")
    if "ignore previous instructions" in file_content.lower():
        st.error("🚨 Quarantine Alert: Injection detected. File not read.")
        reader_a = None
    
    if reader_a and reader_b:
        if reader_a == reader_b:
            st.success(f"**Both readers agree:** Expiry Date is {reader_a}.")
            expiry_date = datetime.strptime(reader_a, "%Y-%m-%d").date()
            grace_date = expiry_date + timedelta(days=30)
            
            st.write("### 3. The Deadline")
            st.info(f"**Expiry:** {expiry_date}")
            st.warning(f"**Grace Period Deadline:** {grace_date} (30 days)")
            
            st.write("### 4. Human Approval Queue")
            st.write(f"Draft reminder: *'Your document expires on {expiry_date}. Please renew before {grace_date}.'*")
            
            if st.button("Approve Reminder"):
                st.success("Reminder approved and sent to your email.")
                
        else:
            st.warning("⚠️ **Readers Disagree.** Please confirm the date:")
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Confirm {reader_a} (Reader A)"):
                    st.success(f"Date confirmed as {reader_a}.")
            with col2:
                if st.button(f"Confirm {reader_b} (Reader B)"):
                    st.success(f"Date confirmed as {reader_b}.")