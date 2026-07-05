import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
import traceback
import json
from fpdf import FPDF
from io import BytesIO

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def extract_file_id(url):
    match = re.search(r'[-\w]{25,}', url)
    if match: return match.group(0)
    return None

def create_pdf(images_data):
    pdf = FPDF()
    for img_bytes in images_data:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
            tmp_img.write(img_bytes.read())
            tmp_path = tmp_img.name
            
        pdf.add_page()
        pdf.image(tmp_path, x=10, y=10, w=190)
        
        try: os.remove(tmp_path)
        except: pass
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        pdf.output(tmp_pdf.name)
        with open(tmp_pdf.name, "rb") as f:
            pdf_data = f.read()
            
    try: os.remove(tmp_pdf.name)
    except: pass
    return pdf_data

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    
    st.info("💡 Silakan unggah file JSON Anda di bawah ini.")
    uploaded_json = st.file_uploader("🔑 Unggah File JSON Service Account Google Anda", type="json")
    
    if not uploaded_json:
        st.warning("Menunggu file JSON...")
        return
        
    try:
        creds_dict = json.load(uploaded_json)
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        st.success("✅ File Kunci JSON diterima!")
    except Exception as e:
        st.error("🚨 File JSON tidak valid.")
        return

    st.markdown("---")
    
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB" 
    encoded_sheet_name = urllib.parse.quote(SHEET_NAME)
    csv_export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
    
    with st.spinner("Membaca data Spreadsheet..."):
        try:
            df = pd.read_csv(csv_export_url)
        except Exception:
            st.error("🚨 Gagal membaca Spreadsheet.")
            return

    if df.empty:
        st.warning("Data kosong.")
        return

    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])

    st.subheader("Filter Tanggal Laporan")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Tanggal Mulai", value=datetime.date.today())
    with col2:
        end_date = st.date_input("Tanggal Akhir", value=datetime.date.today())
        
    if start_date > end_date:
        st.error("Tanggal mulai tidak boleh lewat dari tanggal akhir.")
        return
        
    mask = (df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)
    filtered_df = df.loc[mask]
    
    try:
        cols_to_show = []
        if df.shape[1] > 4: cols_to_show.append(df.columns[4])
        if df.shape[1] > 6: cols_to_show.append(df.columns[6])
        if df.shape[1] > 20: cols_to_show.append(df.columns[20])
        
        if cols_to_show:
            st.dataframe(filtered_df[cols_to_show])
        else:
            st.dataframe(filtered_df)
    except Exception:
        st.dataframe(filtered_df)
        
    st.markdown("---")

    if st.button("Tarik Gambar & Proses PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data untuk tanggal ini.")
            return
            
        images_bytes = []
        progress_bar = st.progress(0, text="Memulai pemindaian...")
        total_rows = len(filtered_df)
        
        total_links_found = 0
        total_downloads_success = 0
        
        # KOTAK KHUSUS UNTUK MENANGKAP ERROR GOOGLE
        error_logs = []
        
        with st.spinner("Mengunduh..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                for col_name in df.columns:
                    cell_value = str(row[col_name])
                    
                    if "drive.google.com" in cell_value:
                        urls = cell_value.split(',')
                        for u in urls:
                            file_id = extract_file_id(u.strip())
                            if file_id:
                                total_links_found += 1
                                try:
                                    request = drive_service.files().get_media(fileId=file_id)
                                    fh = BytesIO()
                                    downloader = MediaIoBaseDownload(fh, request)
                                    done = False
                                    while done is False:
                                        status, done = downloader.next_chunk()
                                    fh.seek(0)
                                    images_bytes.append(fh)
                                    total_downloads_success += 1
                                except Exception as e:
                                    # MENANGKAP PESAN ERROR DARI GOOGLE API
                                    error_logs.append(f"ID {file_id}: {str(e)}")
                                    
                progress_bar.progress(int(((idx + 1) / total_rows) * 100), text=f"Selesai baris {idx + 1}/{total_rows}")

        # MENAMPILKAN HASIL INVESTIGASI ERROR KEPADA ANDA
        if error_logs:
            st.error("⚠️ Sistem mencatat penolakan dari server Google Drive! Berikut adalah alasan aslinya:")
            with st.expander("Klik untuk melihat detail log error dari Google"):
                for err in error_logs:
                    st.code(err)

        st.info(f"📊 Laporan: Ditemukan {total_links_found} tautan, berhasil mengunduh {total_downloads_success} gambar.")

        if images_bytes:
            with st.spinner("Merakit PDF..."):
                try:
                    pdf_data = create_pdf(images_bytes)
                    st.success("🎉 PDF Berhasil Dibuat!")
                    st.download_button(
                        label="📥 Klik di Sini untuk Unduh PDF",
                        data=pdf_data,
                        file_name=f"Laporan_Gambar_PJB_{start_date}_sd_{end_date}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error("Gagal menyatukan gambar ke PDF.")
                    st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
