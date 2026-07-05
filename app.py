import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
from fpdf import FPDF
import gdown

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def get_file_id(url):
    """Mengekstrak ID file dengan lebih fleksibel"""
    if not isinstance(url, str): return None
    # Pola ID Google Drive biasanya 25-40 karakter alfanumerik
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
    except:
        st.error("Gagal membaca Spreadsheet. Pastikan sudah Public!")
        return

    # 2. FILTER TANGGAL
    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])
    
    start_date = st.date_input("Tanggal Mulai", datetime.date.today())
    end_date = st.date_input("Tanggal Akhir", datetime.date.today())
    
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    
    # 3. TABEL SIMPEL
    st.write(f"Data ditemukan: {len(filtered_df)} baris")
    show_cols = [df.columns[4], df.columns[6], df.columns[20]] if df.shape[1] > 20 else df.columns
    st.dataframe(filtered_df[show_cols])

    # 4. DOWNLOAD & PDF
    if st.button("Proses PDF"):
        img_paths = []
        progress = st.progress(0)
        
        for i, row in enumerate(filtered_df.iterrows()):
            _, data = row
            for col in df.columns:
                val = str(data[col])
                if "drive.google.com" in val:
                    fid = get_file_id(val)
                    if fid:
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                        # Teknik gdown bypass
                        if gdown.download(id=fid, output=tmp, quiet=True, fuzzy=True):
                            if os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
                                img_paths.append(tmp)
            progress.progress((i+1)/len(filtered_df))

        if img_paths:
            pdf = FPDF()
            for img in img_paths:
                pdf.add_page()
                pdf.image(img, 10, 10, 190)
                os.remove(img)
            
            pdf_out = "laporan.pdf"
            pdf.output(pdf_out)
            with open(pdf_out, "rb") as f:
                st.download_button("Download PDF", f, "Laporan_PJB.pdf", "application/pdf")
            os.remove(pdf_out)
        else:
            st.error("Tidak ada gambar ditemukan. Pastikan link di Sheet benar-benar mengarah ke file gambar tunggal.")

if __name__ == "__main__":
    main()
