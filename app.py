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
    """Mengekstrak ID file dari link Drive"""
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    
    # 1. BACA DATA
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB"
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(SHEET_NAME)}"
    
    try:
        df = pd.read_csv(csv_url)
    except Exception as e:
        st.error(f"Gagal membaca Spreadsheet: {e}")
        return

    # 2. FILTER TANGGAL
    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Tanggal Mulai", datetime.date.today())
    end_date = col2.date_input("Tanggal Akhir", datetime.date.today())
    
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    
    # 3. TABEL SIMPEL
    st.write(f"Ditemukan {len(filtered_df)} baris data.")
    show_cols = [df.columns[4], df.columns[6], df.columns[20]] if df.shape[1] > 20 else df.columns
    st.dataframe(filtered_df[show_cols])

    # 4. DOWNLOAD & PROSES PDF
    if st.button("Tarik Gambar & Proses PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data.")
            return
            
        img_paths = []
        progress = st.progress(0)
        
        for i, (idx, row) in enumerate(filtered_df.iterrows()):
            for col in df.columns:
                val = str(row[col])
                if "drive.google.com" in val:
                    fid = get_file_id(val)
                    if fid:
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                        url = f"https://drive.google.com/uc?export=download&id={fid}"
                        try:
                            r = requests.get(url, stream=True, timeout=10)
                            if r.status_code == 200:
                                with open(tmp, 'wb') as f:
                                    f.write(r.content)
                                if os.path.getsize(tmp) > 2000:
                                    img_paths.append(tmp)
                        except:
                            if os.path.exists(tmp): os.remove(tmp)
            progress.progress((i+1)/len(filtered_df))

        if img_paths:
            pdf = FPDF()
            for img in img_paths:
                pdf.add_page()
                pdf.image(img, 10, 10, 190)
                os.remove(img)
            
            pdf_path = "output.pdf"
            pdf.output(pdf_path)
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, "Laporan.pdf", "application/pdf")
            os.remove(pdf_path)
        else:
            st.error("Gagal mengunduh gambar. Pastikan link adalah link file tunggal (bukan folder) dan folder sudah diset 'Public'.")

if __name__ == "__main__":
    main()
