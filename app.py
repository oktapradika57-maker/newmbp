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

# Fungsi untuk mengambil ID dari link
def get_file_id(url):
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    
    # 1. BACA DATA SPREADSHEET
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
    show_cols = [df.columns[4], df.columns[6], df.columns[20]] if df.shape[1] > 20 else df.columns
    st.dataframe(filtered_df[show_cols])

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
                            # Menggunakan endpoint 'uc' untuk paksa download
                            url = f"https://drive.google.com/uc?export=download&id={fid}"
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                            try:
                                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=10)
                                if r.status_code == 200:
                                    with open(tmp, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                    # Cek ukuran file: jika > 2KB, berarti gambar (bukan halaman error)
                                    if os.path.getsize(tmp) > 2000:
                                        img_paths.append(tmp)
                                    else:
                                        os.remove(tmp)
                            except:
                                if os.path.exists(tmp): os.remove(tmp)
                progress.progress((i+1)/len(filtered_df))

        # 5. BUAT PDF
        if img_paths:
            pdf = FPDF()
            for img in img_paths:
                pdf.add_page()
                try:
                    pdf.image(img, 10, 10, 190)
                except:
                    pass
                os.remove(img)
            
            pdf_path = "Laporan_PJB.pdf"
            pdf.output(pdf_path)
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, "Laporan_PJB.pdf", "application/pdf")
            os.remove(pdf_path)
        else:
            st.error("Gagal mengunduh gambar. Pastikan link di Sheet adalah link file gambar tunggal (bukan folder) dan folder sudah diset ke 'Siapa saja yang memiliki link'.")

if __name__ == "__main__":
    main()
