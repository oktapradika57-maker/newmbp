import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
import requests
from fpdf import FPDF

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def get_file_id(url):
    """Mengekstrak ID file dari link Drive apapun"""
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB"
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(SHEET_NAME)}"
    
    try:
        df = pd.read_csv(csv_url)
    except Exception as e:
        st.error(f"Gagal membaca Spreadsheet. Pastikan sudah Public: {e}")
        return

    # Filter Tanggal
    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])
    
    start_date = st.date_input("Tanggal Mulai", datetime.date.today())
    end_date = st.date_input("Tanggal Akhir", datetime.date.today())
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    
    # Tabel Simpel
    cols = [df.columns[4], df.columns[6], df.columns[20]] if df.shape[1] > 20 else df.columns
    st.dataframe(filtered_df[cols])

    if st.button("Tarik Gambar & Proses PDF"):
        img_paths = []
        with st.spinner("Sedang memproses unduhan..."):
            for _, row in filtered_df.iterrows():
                for col in df.columns:
                    val = str(row[col])
                    if "drive.google.com" in val:
                        fid = get_file_id(val)
                        if fid:
                            url = f"https://drive.google.com/uc?export=download&id={fid}"
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                            try:
                                r = requests.get(url, stream=True, timeout=10)
                                if r.status_code == 200:
                                    with open(tmp, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                    if os.path.getsize(tmp) > 2000: img_paths.append(tmp)
                                    else: os.remove(tmp)
                            except: pass

        if img_paths:
            pdf = FPDF()
            for img in img_paths:
                pdf.add_page()
                pdf.image(img, 10, 10, 190)
                os.remove(img)
            
            pdf_path = "Laporan_PJB.pdf"
            pdf.output(pdf_path)
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, "Laporan_PJB.pdf", "application/pdf")
            os.remove(pdf_path)
        else:
            st.error("Gagal mengunduh gambar. Pastikan link di Sheet adalah link langsung ke file foto.")

if __name__ == "__main__":
    main()
