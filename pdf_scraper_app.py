import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO

st.title("Victoria Planning Report Extractor")

uploaded_files = st.file_uploader("Upload one or more PDFs", type="pdf", accept_multiple_files=True)

FIELDS = [
    "Address",
    "Site area",
    "PFI/Identifier",
    "LGA",
    "Planning scheme",
    "Primary zoning",
    "Overlays present (Y/N)",
    "Aboriginal Culture Heritage",
    "Designated Bushfire Prone Area",
    "Native Vegetation",
    "Number of parcels",
]

valid_codes = {
    "BMO","DDO","DPO","EAO","ESO","FO","HO","LSO",
    "LSIO","PAO","RO","SBO","SCO","SLO","SMO","VPO","AEO","EMO"
}

def extract_field(label, text, stop_on_scale=False):
    """
    Extract field value. Stops at scale lines and removes trailing scale if inline.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"{label}[:\-]?", line, re.IGNORECASE):
            collected = []
            # remove label from line
            inline = re.sub(rf"{label}[:\-]?", "", line, flags=re.IGNORECASE).strip()
            if inline:
                collected.append(inline)
                
            # Special case for "This property has"
            if label.lower() == "this property has" and line.startswith("This property has"):
                match = re.search(r"This property has (\d+) parcels?", line, re.IGNORECASE)
                if match:
                    return match.group(1)  # just the number       
        
            # look at following lines
            for j in range(i + 1, len(lines)):
                nxt = lines[j].strip()
                if not nxt:
                    break
                if stop_on_scale and re.match(r"0\s+\d+(?:\.\d+)?\s*m", nxt):
                    break
                if re.match(r".*[:]", nxt):
                    break
                collected.append(nxt)
            result = " ".join(collected).strip()
            # Remove inline scale at the end if present
            if stop_on_scale:
                result = re.sub(r"\s*0\s+\d+\s*m\s*$", "", result)
            return result
    return ""

def clean_codes(raw_codes):
    """Filter overlay codes so only valid ones remain."""
    if raw_codes == "-":
        return "-"
    cleaned = [c for c in raw_codes if any(c.startswith(v) for v in valid_codes)]
    return cleaned if cleaned else "-"

def extract_overlays(text):
    """
    Extract overlays info from text.
    
    Returns:
        overlay_flag: 'Y' if overlays present, 'N' otherwise
        overlay_text: overlays description or 'None'
        vicinity_text: overlays in vicinity or 'None'
    """
    lines = text.splitlines()
    overlay_text = []
    vicinity = []

    scale_pattern = re.compile(r"0\s+\d+(?:\.\d+)?\s*m", re.IGNORECASE)

    # 1. Extract Planning Overlays
    capturing = False
    for line in lines:
        clean = line.strip()

        if re.match(r"Planning Overlays?", clean, re.IGNORECASE):
            capturing = True
            continue

        if capturing:
            # Stop at vicinity section or new header
            if re.match(r"Other Overlays", clean, re.IGNORECASE):
                break
            if re.match(r"Further Planning Information", clean, re.IGNORECASE):
                break

            # Skip empty and scale lines
            if not clean or scale_pattern.fullmatch(clean):
                continue

            # Remove inline scales if they appear in the same line
            clean = scale_pattern.sub("", clean).strip()
            if clean:
                overlay_text.append(clean)

    overlay_text_str = " ".join(overlay_text).strip()
    overlays_flag = "Y" if overlay_text_str and not overlay_text_str.startswith("None affecting this land") else "N"
    if overlays_flag == "N":
        overlay_text_str = "None"

    # 2. Extract Vicinity overlays
    capturing = False
    for line in lines:
        clean = line.strip()

        if re.match(r"Other Overlays", clean, re.IGNORECASE):
            capturing = True
            continue

        if capturing:
            # Stop at next header or end
            if re.match(r"Further Planning Information", clean, re.IGNORECASE):
                break
            if not clean or scale_pattern.fullmatch(clean):
                continue

            if not clean.upper().startswith("OTHER OVERLAYS"):
                vicinity.append(clean)

    vicinity_str = ", ".join(vicinity) if vicinity else "None"

    return overlays_flag, overlay_text_str, vicinity_str

def extract_site_area(text):
    """Extract site area in hectares from a property report PDF."""
    match = re.search(r"Area:\s*([\d,\.]+)\s*sq\.?\s*m", text, re.IGNORECASE)
    if match:
        return match.group(1).replace(",", "")
    return ""

            
if uploaded_files:
    records = []
    site_area_dict = {}
    
    for uploaded_file in uploaded_files:
        if uploaded_file.name.endswith("Detailed-Property-Report.pdf"):
            with pdfplumber.open(uploaded_file) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])

            match = re.search(r"\(ID(\d+)\)", uploaded_file.name)
            if match:
                pfi = "PFI " + match.group(1)
                site_area_dict[pfi] = extract_site_area(text)
        site_area_dict = {k: round(float(v)/10000,2) for k, v in site_area_dict.items()}              
                
        if uploaded_file.name.endswith("Vicplan-Planning-Property-Report.pdf"):
        
            with pdfplumber.open(uploaded_file) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    
            entry = {"File Name": uploaded_file.name}
            
            entry["Address"] = extract_field("Address", text)        
            
            match = re.search(r"\(ID(\d+)\)", uploaded_file.name)
            if match:
                content = match.group(1)
                pfi = "PFI " + match.group(1) 
            entry["PFI/Identifier"] = pfi
            
            entry["Site area"] = site_area_dict.get(entry["PFI/Identifier"], "")
            
            entry["Number of parcels"] = extract_field("This property has", text) or "1"
            
            lga = extract_field("Local Government Area", text)
            lga_clean = re.sub(r"\(.*?\)|:|\bwww.*", "", lga).strip()
            entry["LGA"] = lga_clean 
            
            planning_scheme = extract_field("Planning Scheme", text)
            planning_scheme_clean = planning_scheme.split("-")[0].strip()
            entry["Planning scheme"] = planning_scheme_clean
            
            entry["Primary zoning"] = extract_field("Planning Zones", text, stop_on_scale=True)
    
            overlays_flag, overlay_text_str, vicinity_str = extract_overlays(text)
            overlay_codes = re.findall(r"\((.*?)\)", overlay_text_str) or "-"
            vicinity_codes = re.findall(r"\((.*?)\)", vicinity_str) or "-"
            
            overlay_codes = clean_codes(overlay_codes)
            vicinity_codes = clean_codes(vicinity_codes)
    
            aboriginal_text = extract_field("Areas of Aboriginal Cultural Heritage Sensitivity", text)
            aboriginal_flag = "Y" if aboriginal_text.lower().startswith("all or part of this property is an 'area of cultural heritage sensitivity'") else "N"
            entry["Aboriginal Culture Heritage"] = aboriginal_flag
            
            bushfire_text = extract_field("Designated Bushfire Prone Areas", text)
            bushfire_flag = "Y" if bushfire_text.lower().startswith("this property is in a") else "N"
            entry["Designated Bushfire Prone Area"] = bushfire_flag
            
            vegetation_text = extract_field("Native Vegetation", text)
            vegetation_flag = "Y" if vegetation_text.lower().startswith("native plants that are indigenous to the region and important for biodiversity might be present on this property") else "N"
            entry["Native Vegetation"] = vegetation_flag
            
            EIWA_text = extract_field("Extractive Industry Work Authorities", text)
            eiwa_lower = EIWA_text.lower().strip()
            EIWA_flag = "Y" if eiwa_lower.startswith("(wa) all or parts of this property are within") else "N"
            match = re.search(r"(within.*?)(?:\(|$.)", eiwa_lower)
            EIWA_extracted = match.group(1).strip() if match else ""
            
            vicinity_codes = (vicinity_codes + [EIWA_extracted] if EIWA_extracted else vicinity_codes) or "-"
            
            entry["Overlays present (Y/N)"] = overlays_flag + " (" + "/".join(overlay_codes) +")" + " (vicinity: " + "/".join(vicinity_codes) + ")" 
            
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

