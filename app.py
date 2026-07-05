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
        st.error(f"Gagal membaca Spreadsheet: {e}")
        return

    df['Date_Parsed'] = pd.to_datetime(df[df.columns[0]], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])
    
    start_date = st.date_input("Tanggal Mulai", datetime.date.today())
    end_date = st.date_input("Tanggal Akhir", datetime.date.today())
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    
    st.write(f"Ditemukan {len(filtered_df)} baris data.")

    if st.button("Tarik Gambar & Proses PDF"):
        img_paths = []
        # Tambahkan status untuk melihat apa yang sebenarnya terjadi
        status_text = st.empty()
        
        for _, row in filtered_df.iterrows():
            for col in df.columns:
                val = str(row[col])
                if "drive.google.com" in val:
                    fid = get_file_id(val)
                    if fid:
                        # Menggunakan download url resmi Google Drive
                        url = f"https://drive.google.com/uc?export=download&id={fid}"
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                        try:
                            # Menambah timeout dan headers agar tidak dianggap bot
                            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                            
                            # Cek apakah ini benar-benar gambar
                            content_type = r.headers.get('Content-Type', '')
                            if r.status_code == 200 and 'image' in content_type:
                                with open(tmp, 'wb') as f:
                                    f.write(r.content)
                                img_paths.append(tmp)
                            else:
                                # Jika bukan gambar, hapus file sampah
                                if os.path.exists(tmp): os.remove(tmp)
                        except:
                            if os.path.exists(tmp): os.remove(tmp)
        
        status_text.write(f"Berhasil mengunduh {len(img_paths)} gambar dari total baris.")

        if img_paths:
            pdf = FPDF()
            for img in img_paths:
                pdf.add_page()
                try:
                    pdf.image(img, 10, 10, 190)
                except Exception as e:
                    st.write(f"Gagal memuat gambar ke PDF: {e}")
                os.remove(img)
            
            pdf_path = "Laporan_PJB.pdf"
            pdf.output(pdf_path)
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, "Laporan_PJB.pdf", "application/pdf")
            os.remove(pdf_path)
        else:
            st.error("Gambar tidak ditemukan. Coba cek link di spreadsheet. Apakah saat diklik link tsb langsung membuka gambar?")

if __name__ == "__main__":
    main()
