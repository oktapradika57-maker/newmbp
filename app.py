import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
import json
import traceback
from fpdf import FPDF
from io import BytesIO
from PIL import Image

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def extract_file_id(url):
    """Mengambil ID dari link Google Drive"""
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    
    st.info("💡 Unggah Kunci JSON Service Account Anda untuk membuka gembok Google Drive.")
    uploaded_json = st.file_uploader("🔑 Unggah File JSON di sini", type="json")
    
    if not uploaded_json:
        st.warning("Menunggu file JSON...")
        return
        
    # OTENTIKASI RESMI GOOGLE API
    try:
        creds_dict = json.load(uploaded_json)
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        robot_email = creds_dict.get('client_email', 'Email robot tidak terbaca')
        st.success(f"✅ Otentikasi Berhasil! Robot Anda: **{robot_email}** siap bekerja.")
    except Exception as e:
        st.error("🚨 File JSON tidak valid.")
        return

    st.markdown("---")
    
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB" 
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(SHEET_NAME)}"
    
    try:
        df = pd.read_csv(csv_url)
    except Exception:
        st.error("🚨 Gagal membaca Spreadsheet.")
        return

    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])

    col1, col2 = st.columns(2)
    start_date = col1.date_input("Tanggal Mulai", value=datetime.date.today())
    end_date = col2.date_input("Tanggal Akhir", value=datetime.date.today())
        
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    
    st.write(f"Ditemukan **{len(filtered_df)} baris data**.")
    
    # Tabel Pratinjau (E, G, U)
    try:
        show_cols = [df.columns[4], df.columns[6], df.columns[20]] if df.shape[1] > 20 else df.columns
        st.dataframe(filtered_df[show_cols])
    except:
        st.dataframe(filtered_df)
        
    st.markdown("---")

    if st.button("🚀 TARIK GAMBAR & PROSES PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data.")
            return
            
        images_paths = []
        progress_bar = st.progress(0)
        total_rows = len(filtered_df)
        
        success_count = 0
        error_logs = []
        
        with st.spinner("Mengunduh foto via Jalur Resmi Google API..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                for col_name in df.columns:
                    cell_val = str(row[col_name])
                    if "drive.google.com" in cell_val:
                        urls = cell_val.split(',')
                        for u in urls:
                            fid = extract_file_id(u.strip())
                            if fid:
                                try:
                                    # Request Resmi menggunakan ID
                                    request = drive_service.files().get_media(fileId=fid)
                                    fh = BytesIO()
                                    downloader = MediaIoBaseDownload(fh, request)
                                    done = False
                                    while done is False:
                                        status, done = downloader.next_chunk()
                                    
                                    fh.seek(0)
                                    # Validasi & Simpan gambar ke temporary file
                                    img = Image.open(fh)
                                    if img.mode != 'RGB': img = img.convert('RGB')
                                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                                    img.save(tmp, format="JPEG")
                                    images_paths.append(tmp)
                                    success_count += 1
                                    
                                except Exception as e:
                                    error_logs.append(f"Gagal di ID {fid}: Belum di-Share ke robot")
                                    
                progress_bar.progress(int(((idx + 1) / total_rows) * 100))

        if error_logs:
            st.warning(f"⚠️ {len(error_logs)} foto tidak bisa diambil karena gembok belum dibuka untuk email robot. (Lakukan CTRL+A pada foto di Drive lalu Share ke {robot_email})")
            
        if images_paths:
            with st.spinner("Merakit gambar menjadi file PDF..."):
                try:
                    pdf = FPDF()
                    for path in images_paths:
                        pdf.add_page()
                        pdf.image(path, x=10, y=10, w=190)
                        os.remove(path) # Bersihkan file setelah dipakai
                    
                    pdf_output = "Laporan_PJB.pdf"
                    pdf.output(pdf_output)
                    
                    with open(pdf_output, "rb") as f:
                        st.download_button("📥 UNDUH PDF SEKARANG", f, "Laporan_Gambar.pdf", "application/pdf")
                    os.remove(pdf_output)
                except Exception as e:
                    st.error("Gagal menyusun PDF.")
                    st.code(traceback.format_exc())
        else:
            st.error("Gagal total mengambil gambar.")
            
if __name__ == "__main__":
    main()
