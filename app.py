import streamlit as st
import pandas as pd
import requests
import re
import tempfile
import os
import urllib.parse
import datetime
import traceback
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def extract_file_id(url):
    """Mengekstrak ID file unik dari URL Google Drive menggunakan Regex tingkat lanjut"""
    # Mencari pola karakter unik Google Drive ID (biasanya minimal 25 karakter)
    match = re.search(r'[-\w]{25,}', url)
    if match:
        return match.group(0)
    return None

def download_image_public(file_id):
    """Sistem unduhan ganda (Dual-Engine) agar kebal dari pemblokiran Google"""
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    # 1. Coba Endpoint Direct Download
    url1 = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        r1 = session.get(url1, headers=headers, timeout=10)
        if r1.status_code == 200 and 'text/html' not in r1.headers.get('Content-Type', ''):
            return BytesIO(r1.content)
    except:
        pass
        
    # 2. Coba Endpoint Thumbnail API (sebagai cadangan jika akses langsung ditolak)
    url2 = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
    try:
        r2 = session.get(url2, headers=headers, timeout=10)
        if r2.status_code == 200 and 'text/html' not in r2.headers.get('Content-Type', ''):
            return BytesIO(r2.content)
    except:
        pass
        
    return None

def create_pdf(images_data):
    """Menyatukan semua file ke PDF"""
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

    # Ambil kolom tanggal (kolom pertama)
    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])

    st.subheader("Filter Tanggal")
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
    
    st.write(f"Ditemukan **{len(filtered_df)} baris data** pada rentang tanggal tersebut.")
    
    if st.button("Tarik Gambar & Proses PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data untuk tanggal ini.")
            return
            
        images_bytes = []
        progress_bar = st.progress(0, text="Memulai pemindaian link...")
        total_rows = len(filtered_df)
        
        total_links_found = 0
        total_downloads_success = 0
        
        with st.spinner("Memindai dan mengunduh gambar..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                
                # SENSOR PINTAR: Memindai seluruh sel di baris ini, bukan cuma N-T
                # Aplikasi otomatis mendeteksi mana sel yang kosong dan mana yang berisi link
                for col_name in df.columns:
                    cell_value = str(row[col_name])
                    
                    if "drive.google.com" in cell_value:
                        urls = cell_value.split(',')
                        for u in urls:
                            file_id = extract_file_id(u.strip())
                            if file_id:
                                total_links_found += 1
                                img_io = download_image_public(file_id)
                                if img_io:
                                    images_bytes.append(img_io)
                                    total_downloads_success += 1
                                    
                progress_bar.progress(int(((idx + 1) / total_rows) * 100), text=f"Selesai memproses baris ke-{idx + 1}")

        # Tampilkan laporan agar Anda tahu apa yang terjadi di balik layar
        st.info(f"📊 Laporan Sistem: Ditemukan {total_links_found} tautan Google Drive, dan berhasil mengunduh {total_downloads_success} gambar.")

        if images_bytes:
            with st.spinner("Merakit PDF..."):
                try:
                    pdf_data = create_pdf(images_bytes)
                    st.success("🎉 PDF Berhasil Dibuat!")
                    st.download_button(
                        label="📥 Klik di Sini untuk Unduh PDF Laporan",
                        data=pdf_data,
                        file_name=f"Laporan_Gambar_PJB_{start_date}_sd_{end_date}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error("Gagal menyatukan PDF.")
                    st.code(traceback.format_exc())
        else:
            if total_links_found > 0:
                st.error("Sistem menemukan link-nya, namun akses unduhnya ditolak oleh Google Drive. Pastikan folder benar-benar Publik (Anyone with the link).")
            else:
                st.error("Tidak ada link Google Drive yang terdeteksi sama sekali pada tanggal yang difilter. Coba rentang tanggal lain.")

if __name__ == "__main__":
    main()
