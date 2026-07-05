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
    """Mengekstrak ID file unik dari URL Google Drive"""
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    
    # 1. READ SHEET
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
    
    # 3. TABEL SIMPEL (E, G, U)
    st.write(f"Ditemukan {len(filtered_df)} baris data.")
    try:
        # A=0, B=1, C=2, D=3, E=4, F=5, G=6 ... U=20
        show_cols = [df.columns[4], df.columns[6], df.columns[20]] 
        st.dataframe(filtered_df[show_cols])
    except:
        st.dataframe(filtered_df)

    # 4. DOWNLOAD & PROSES PDF
    if st.button("Tarik Gambar & Proses PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data.")
            return
            
        img_paths = []
        progress = st.progress(0)
        
        with st.spinner("Mengunduh gambar..."):
            for i, (idx, row) in enumerate(filtered_df.iterrows()):
                for col in df.columns:
                    val = str(row[col])
                    if "drive.google.com" in val:
                        fid = get_file_id(val)
                        if fid:
                            url = f"https://drive.google.com/uc?export=download&id={fid}"
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                            try:
                                headers = {"User-Agent": "Mozilla/5.0"}
                                r = requests.get(url, headers=headers, stream=True, timeout=10)
                                # Pastikan respon adalah gambar
                                if r.status_code == 200 and 'image' in r.headers.get('Content-Type', ''):
                                    with open(tmp, 'wb') as f:
                                        f.write(r.content)
                                    img_paths.append(tmp)
                                else:
                                    if os.path.exists(tmp): os.remove(tmp)
                            except:
                                if os.path.exists(tmp): os.remove(tmp)
                progress.progress((i+1)/len(filtered_df))

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
            st.error("Gagal mengunduh gambar. Pastikan link di Sheet adalah link langsung ke file gambar.")

if __name__ == "__main__":
    main()
