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
        st.error(f"Gagal baca Sheet: {e}")
        return

    df['Date_Parsed'] = pd.to_datetime(df[df.columns[0]], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Tanggal Mulai", datetime.date.today())
    end_date = col2.date_input("Tanggal Akhir", datetime.date.today())
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    
    st.write(f"Ditemukan {len(filtered_df)} baris data.")

    if st.button("Tarik Gambar & Proses PDF"):
        img_paths = []
        
        # Header yang sangat kuat agar dianggap sebagai browser manusia
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.google.com/"
        }
        
        with st.spinner("Mengunduh..."):
            for _, row in filtered_df.iterrows():
                for col in df.columns:
                    val = str(row[col])
                    if "drive.google.com" in val:
                        fid = get_file_id(val)
                        if fid:
                            # Menggunakan download url resmi
                            url = f"https://drive.google.com/uc?export=download&id={fid}"
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                            try:
                                r = requests.get(url, headers=headers, timeout=15)
                                if r.status_code == 200:
                                    with open(tmp, 'wb') as f:
                                        f.write(r.content)
                                    # Jika file benar-benar gambar
                                    if os.path.getsize(tmp) > 500:
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
            
            pdf_path = "Laporan_PJB.pdf"
            pdf.output(pdf_path)
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, "Laporan_PJB.pdf", "application/pdf")
            os.remove(pdf_path)
        else:
            st.error("Tetap gagal. Jika link tsb dibuka di browser muncul gambar, tapi di sini gagal, artinya Google memblokir IP server Streamlit.")

if __name__ == "__main__":
    main()
