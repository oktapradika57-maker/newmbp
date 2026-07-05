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
    """Mengekstrak ID file unik dari URL Google Drive menggunakan Regex"""
    match = re.search(r'[-\w]{25,}', url)
    if match:
        return match.group(0)
    return None

def download_image_public(file_id):
    """
    Sistem unduhan 3 lapis untuk menembus pemblokiran Google Drive.
    """
    session = requests.Session()
    # Menyamar sebagai browser modern
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }
    
    # Daftar 3 jalur unduhan rahasia Google Drive
    endpoints = [
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download", # Endpoint terbaru Google
        f"https://drive.google.com/uc?export=download&id={file_id}",                   # Endpoint klasik
        f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"                    # Endpoint Thumbnail API
    ]
    
    for url in endpoints:
        try:
            response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
            # Pastikan yang didownload benar-benar gambar (bukan halaman error HTML)
            if response.status_code == 200 and 'text/html' not in response.headers.get('Content-Type', ''):
                return BytesIO(response.content)
        except Exception:
            continue
            
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
            st.error("🚨 Gagal membaca Spreadsheet. Pastikan link Sheet benar-benar publik.")
            return

    if df.empty:
        st.warning("Data pada Sheet tersebut kosong.")
        return

    # Ambil kolom tanggal (Asumsi di kolom pertama/Indeks 0)
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
    
    st.write(f"Ditemukan **{len(filtered_df)} baris data** pada rentang waktu ini.")
    
    # ---------------------------------------------------------
    # MENAMPILKAN TABEL HANYA UNTUK KOLOM E, G, DAN U
    # Indeks Excel: A=0, B=1, C=2, D=3, E=4, F=5, G=6 ... U=20
    # ---------------------------------------------------------
    try:
        cols_to_show = []
        if df.shape[1] > 4: cols_to_show.append(df.columns[4])   # Kolom E
        if df.shape[1] > 6: cols_to_show.append(df.columns[6])   # Kolom G
        if df.shape[1] > 20: cols_to_show.append(df.columns[20]) # Kolom U
        
        if cols_to_show:
            st.dataframe(filtered_df[cols_to_show])
        else:
            st.dataframe(filtered_df) # Tampilkan semua jika total kolom kurang dari U
    except Exception:
        st.dataframe(filtered_df) # Fallback aman jika terjadi error pemotongan tabel
        
    st.markdown("---")

    if st.button("Tarik Gambar & Proses PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data untuk tanggal ini.")
            return
            
        images_bytes = []
        progress_bar = st.progress(0, text="Memulai pemindaian tautan Drive...")
        total_rows = len(filtered_df)
        
        total_links_found = 0
        total_downloads_success = 0
        
        with st.spinner("Memindai sel dan mengunduh gambar..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                
                # Memindai seluruh sel di baris yang sedang diproses
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

        st.info(f"📊 Laporan Sistem: Ditemukan {total_links_found} tautan, dan berhasil mengunduh {total_downloads_success} gambar.")

        if images_bytes:
            with st.spinner("Merakit gambar menjadi file PDF..."):
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
                    st.error("Gagal menyatukan gambar ke PDF. Pastikan format gambar normal (JPG/PNG).")
                    st.code(traceback.format_exc())
        else:
            if total_links_found > 0:
                st.error("Sistem menemukan tautannya, namun Google masih memblokir unduhan anonim. Sebagai alternatif terakhir, Anda bisa mencoba menyalin kode ini ke Google Colab.")
            else:
                st.warning("Tidak ada link Google Drive yang terdeteksi sama sekali pada tabel data yang difilter.")

if __name__ == "__main__":
    main()
