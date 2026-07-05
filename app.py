import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
import requests
import json
from fpdf import FPDF
from io import BytesIO
from PIL import Image

# Library Google API (opsional jika menggunakan JSON)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    HAS_GOOGLE_API = True
except ImportError:
    HAS_GOOGLE_API = False

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def extract_file_id(url):
    """Mengekstrak ID file unik dari URL Google Drive"""
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def download_public_image(file_id):
    """Mencoba mengunduh menggunakan jalur pintas publik (lh3 & thumbnail)"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Jalur Pintas 1: Google UserContent (lh3) - Paling kuat untuk file publik
    try:
        url = f"https://lh3.googleusercontent.com/d/{file_id}"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and 'image' in r.headers.get('Content-Type', ''):
            return r.content
    except:
        pass

    # Jalur Pintas 2: Drive Thumbnail High-Res Engine
    try:
        url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and 'image' in r.headers.get('Content-Type', ''):
            return r.content
    except:
        pass
        
    return None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    st.success("⚡ SISTEM BARU: Dilengkapi Fitur Anti-Crash & Validasi Gambar Ganda.")
    
    # KOTAK UPLOAD JSON (OPSIONAL)
    st.markdown("### 🔑 Akses Kredensial (Pilih Salah Satu)")
    st.info("Anda bisa langsung memproses jika folder Drive sudah diset 'Siapa saja yang memiliki link'. Jika folder bersifat privat, silakan unggah file JSON Anda di bawah ini.")
    uploaded_json = st.file_uploader("Unggah File JSON Service Account Google Anda (Opsional)", type="json")
    
    drive_service = None
    robot_email = None
    
    if uploaded_json and HAS_GOOGLE_API:
        try:
            creds_dict = json.load(uploaded_json)
            SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            drive_service = build('drive', 'v3', credentials=creds)
            robot_email = creds_dict.get('client_email', '')
            st.success(f"✅ Kunci JSON Aktif: Berjalan via API Kinarya Analisis ({robot_email})")
        except Exception as e:
            st.error(f"🚨 File JSON bermasalah, aplikasi akan beralih menggunakan Jalur Publik Anonim.")
    
    st.markdown("---")
    
    # 1. BACA DATA SPREADSHEET
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB" 
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(SHEET_NAME)}"
    
    with st.spinner("Membaca data Spreadsheet..."):
        try:
            df = pd.read_csv(csv_url)
        except Exception as e:
            st.error(f"🚨 Gagal membaca Spreadsheet. Pastikan link Sheet sudah Publik: {e}")
            return

    # 2. PARSING TANGGAL
    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])

    st.subheader("🗓️ Filter Tanggal Laporan")
    col1, col2 = st.columns(2)
    with col1:
        start_date = col1.date_input("Tanggal Mulai", value=datetime.date.today())
    with col2:
        end_date = col2.date_input("Tanggal Akhir", value=datetime.date.today())
        
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    st.write(f"Ditemukan **{len(filtered_df)} baris data** pada rentang tanggal ini.")
    
    # TAMPILKAN TABEL SIMPEL (Kolom E, G, U)
    try:
        show_cols = []
        if df.shape[1] > 4: show_cols.append(df.columns[4])
        if df.shape[1] > 6: show_cols.append(df.columns[6])
        if df.shape[1] > 20: show_cols.append(df.columns[20])
        
        if show_cols:
            st.dataframe(filtered_df[show_cols])
        else:
            st.dataframe(filtered_df)
    except:
        st.dataframe(filtered_df)
        
    st.markdown("---")

    # 3. PROSES UNDUH & PEMBUATAN PDF
    if st.button("🚀 MULAI TARIK GAMBAR & PROSES PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data untuk diproses.")
            return
            
        img_paths = []
        progress_bar = st.progress(0)
        total_rows = len(filtered_df)
        
        total_links_found = 0
        total_downloads_success = 0
        
        with st.spinner("Sedang memproses dan memvalidasi gambar..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                for col_name in df.columns:
                    cell_value = str(row[col_name])
                    
                    if "drive.google.com" in cell_value:
                        urls = cell_value.split(',')
                        for u in urls:
                            fid = extract_file_id(u.strip())
                            if fid:
                                total_links_found += 1
                                content_bytes = None
                                
                                # STRATEGI 1: Menggunakan Jalur Resmi Google API (Jika JSON ada)
                                if drive_service:
                                    try:
                                        request = drive_service.files().get_media(fileId=fid)
                                        fh = BytesIO()
                                        downloader = MediaIoBaseDownload(fh, request)
                                        done = False
                                        while done is False:
                                            status, done = downloader.next_chunk()
                                        content_bytes = fh.getvalue()
                                    except:
                                        pass # Jika API gagal/404, lanjut ke Strategi 2
                                
                                # STRATEGI 2: Menggunakan Jalur Ganda Bypass Publik (lh3 / Thumbnail)
                                if not content_bytes:
                                    content_bytes = download_public_image(fid)
                                    
                                # VALIDASI KETAT DENGAN PILLOW (Mencegah UnidentifiedImageError)
                                if content_bytes:
                                    try:
                                        # Test buka file, jika ini HTML error maka baris ini akan otomatis gagal dan masuk ke 'except'
                                        with Image.open(BytesIO(content_bytes)) as test_img:
                                            test_img.verify() 
                                        
                                        # Jika lolos verifikasi, rapihkan format ke RGB dan simpan sebagai file fisik lokal (.jpg)
                                        with Image.open(BytesIO(content_bytes)) as real_img:
                                            if real_img.mode != 'RGB':
                                                real_img = real_img.convert('RGB')
                                            
                                            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                                            real_img.save(tmp_file.name, format="JPEG")
                                            img_paths.append(tmp_file.name)
                                            total_downloads_success += 1
                                    except Exception as e:
                                        # File rusak / halaman HTML error otomatis dibuang di sini tanpa merusak aplikasi
                                        pass
                                        
                progress_bar.progress(int(((idx + 1) / total_rows) * 100))

        st.info(f"📊 Laporan: Mendeteksi {total_links_found} tautan Drive, dan berhasil mengamankan {total_downloads_success} foto valid.")

        # 4. RAKIT KE PDF
        if img_paths:
            with st.spinner("Merakit gambar ke dalam halaman PDF..."):
                try:
                    pdf = FPDF()
                    for img_path in img_paths:
                        pdf.add_page()
                        pdf.image(img_path, x=10, y=10, w=190)
                        
                        # Hapus file gambar temporary setelah ditempel ke PDF agar server bersih
                        try: os.remove(img_path)
                        except: pass
                        
                    pdf_output_name = "Laporan_Gambar_PJB.pdf"
                    pdf.output(pdf_output_name)
                    
                    with open(pdf_output_name, "rb") as f:
                        st.download_button(
                            label="📥 KLIK DI SINI UNTUK UNDUH FILE PDF",
                            data=f,
                            file_name=f"Laporan_Gambar_PJB_{start_date}_sd_{end_date}.pdf",
                            mime="application/pdf"
                        )
                    
                    try: os.remove(pdf_output_name)
                    except: pass
                    st.success("🎉 Luar Biasa! PDF berhasil dibuat berurutan dengan sempurna!")
                except Exception as pdf_err:
                    st.error(f"Gagal merakit PDF: {pdf_err}")
        else:
            st.error("Gagal mengunduh foto.")
            st.warning("⚠️ MASALAH KEAMANAN: Google memblokir akses ke file-file tersebut. Pastikan Anda sudah membuka gembok file di Google Drive: Masuk ke folder foto > Tekan CTRL+A (Pilih Semua Foto) > Klik Kanan > Bagikan > Ubah menjadi 'Siapa saja yang memiliki link'.")

if __name__ == "__main__":
    main()
