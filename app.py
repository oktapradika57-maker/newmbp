import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
import requests
from fpdf import FPDF
from PIL import Image

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def get_file_id(url):
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def is_valid_image(filepath):
    """Cek apakah file benar-benar gambar yang bisa dibuka oleh PIL"""
    try:
        with Image.open(filepath) as img:
            img.verify() # Validasi apakah file gambar rusak/teks
        return True
    except:
        return False

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB"
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(SHEET_NAME)}"
    
    try:
        df = pd.read_csv(csv_url)
        date_col = df.columns[0]
        df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
        df = df.dropna(subset=['Date_Parsed'])
        
        start_date = st.date_input("Tanggal Mulai", datetime.date.today())
        end_date = st.date_input("Tanggal Akhir", datetime.date.today())
        filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
        
        st.write(f"Ditemukan {len(filtered_df)} baris data.")
        
        if st.button("Tarik Gambar & Proses PDF"):
            img_paths = []
            with st.spinner("Mengunduh gambar..."):
                for _, row in filtered_df.iterrows():
                    for col in df.columns:
                        val = str(row[col])
                        if "drive.google.com" in val:
                            fid = get_file_id(val)
                            if fid:
                                url = f"https://drive.google.com/uc?export=download&id={fid}"
                                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                                try:
                                    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                                    if r.status_code == 200:
                                        with open(tmp, 'wb') as f:
                                            f.write(r.content)
                                        # HANYA masukkan jika benar-benar gambar
                                        if is_valid_image(tmp):
                                            img_paths.append(tmp)
                                        else:
                                            os.remove(tmp)
                                except:
                                    if os.path.exists(tmp): os.remove(tmp)
            
            if img_paths:
                pdf = FPDF()
                for img in img_paths:
                    pdf.add_page()
                    pdf.image(img, 10, 10, 190)
                    os.remove(img)
                
                pdf_path = "Laporan.pdf"
                pdf.output(pdf_path)
                with open(pdf_path, "rb") as f:
                    st.download_button("Download PDF", f, "Laporan.pdf", "application/pdf")
                os.remove(pdf_path)
            else:
                st.error("Tidak ada gambar valid yang berhasil diunduh. Google menolak akses unduhan otomatis.")
                st.info("Saran: Unduh foto dari Drive secara manual ke PC, lalu buat aplikasi dengan fitur 'File Uploader' untuk menghindari blokir Google.")
                
    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
