import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
from io import BytesIO

st.title("📑 PDF Planning Report Extractor")

uploaded_files = st.file_uploader("Upload one or more PDFs", type="pdf", accept_multiple_files=True)

def extract_field(label, text, stop_on_scale=False):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"{label}[:\-]?", line, re.IGNORECASE):
            collected = []
            inline = re.sub(rf"{label}[:\-]?", "", line, flags=re.IGNORECASE).strip()
            if inline:
                return inline
            for j in range(i + 1, len(lines)):
                nxt = lines[j].strip()
                if not nxt:
                    break
                if stop_on_scale and re.match(r"0\s+\d+\s*m", nxt):
                    break
                if re.match(r".*[:\-]", nxt):
                    break
                collected.append(nxt)
            return " ".join(collected).strip()
    return ""

def extract_overlays(text):
    lines = text.splitlines()
    overlays_present = ""
    vicinity = []
    for i, line in enumerate(lines):
        if re.match(r"Planning Overlay", line, re.IGNORECASE):
            collected = []
            for j in range(i + 1, len(lines)):
                nxt = lines[j].strip()
                if not nxt:
                    break
                if re.match(r"0\s+\d+\s*m", nxt):
                    break
                collected.append(nxt)
            overlays_present = " ".join(collected).strip()
            break

    if overlays_present.startswith("None affecting this land"):
        overlays_flag = "N"
        for i, line in enumerate(lines):
            if re.match(r"OTHER OVERLAYS", line, re.IGNORECASE):
                for j in range(i + 1, len(lines)):
                    nxt = lines[j].strip()
                    if not nxt or re.match(r"0\s+\d+\s*m", nxt):
                        break
                    if nxt.upper().startswith("OTHER OVERLAYS"):
                        continue
                    vicinity.append(nxt)
                break
        return overlays_flag, ", ".join(vicinity)
    else:
        overlays_flag = "Y" if overlays_present else "N"
        return overlays_flag, ""

FIELDS = [
    "Site Name", "Address", "Site Area (ha)", "PFI/Identifier",
    "LGA", "Planning scheme", "Primary zoning",
    "Overlays present (Y/N)", "Vicinity overlays"
]

if uploaded_files:
    records = []
    for uploaded_file in uploaded_files:
        with pdfplumber.open(uploaded_file) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])

        entry = {"File Name": uploaded_file.name}
        entry["Site Name"] = extract_field("PROPERTY DETAILS|PLANNING PROPERTY REPORT", text)
        entry["Address"] = extract_field("Address", text)
        entry["Site Area (ha)"] = extract_field("Site Area", text)
        entry["PFI/Identifier"] = extract_field("Standard Parcel Identifier|SPI", text)
        entry["LGA"] = extract_field("Local Government Area", text)
        entry["Planning scheme"] = extract_field("Planning Scheme", text)
        entry["Primary zoning"] = extract_field("Planning Zones", text, stop_on_scale=True)
        overlays_flag, vicinity_list = extract_overlays(text)
        entry["Overlays present (Y/N)"] = overlays_flag
        entry["Vicinity overlays"] = vicinity_list
        records.append(entry)

    df = pd.DataFrame(records, columns=["File Name"] + FIELDS)
    st.dataframe(df)

    # Download Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    st.download_button(
        "💾 Download Excel",
        data=output.getvalue(),
        file_name="parsed_sites.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

