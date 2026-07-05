import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
import requests
from fpdf import FPDF
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def get_file_id(url):
    """Mengekstrak ID unik dari link Google Drive apapun"""
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def download_image_bypass(file_id):
    """
    Sistem Dual-Bypass Browser.
    Menarik file langsung dari sistem cache gambar Google tanpa diblokir 404.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # JALUR 1: Google UserContent Engine (Paling ampuh tembus blokir 404)
    url_lh3 = f"https://lh3.googleusercontent.com/d/{file_id}"
    try:
        r = requests.get(url_lh3, headers=headers, timeout=12)
        if r.status_code == 200 and 'image' in r.headers.get('Content-Type', ''):
            return BytesIO(r.content)
    except:
        pass
        
    # JALUR 2: Jalur Standar uc dengan Penangan Cookie Peringatan Virus
    url_uc = "https://docs.google.com/uc?export=download"
    try:
        session = requests.Session()
        r = session.get(url_uc, params={'id': file_id}, headers=headers, timeout=12)
        token = None
        for key, value in session.cookies.items():
            if key.startswith('download_warning'):
                token = value
                break
        if token:
            r = session.get(url_uc, params={'id': file_id, 'confirm': token}, headers=headers, timeout=12)
        
        if r.status_code == 200 and 'image' in r.headers.get('Content-Type', ''):
            return BytesIO(r.content)
    except:
        pass
        
    return None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    st.success("⚡ SISTEM TERBARU: Jalur Kunci JSON yang diblokir telah dihapus! Menggunakan Bypass Link Langsung.")
    
    # 1. AMBIL DATA SPREADSHEET
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB"
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(SHEET_NAME)}"
    
    with st.spinner("Menghubungkan ke Spreadsheet..."):
        try:
            df = pd.read_csv(csv_url)
        except Exception as e:
            st.error(f"Gagal membaca Spreadsheet. Pastikan link Sheet sudah Public: {e}")
            return

    # 2. FILTER BERDASARKAN TANGGAL
    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Tanggal Mulai", datetime.date.today())
    end_date = col2.date_input("Tanggal Akhir", datetime.date.today())
    
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    
    st.write(f"Ditemukan **{len(filtered_df)} baris data** pada rentang tanggal terpilih.")
    
    # 3. TAMPILKAN TABEL SIMPEL (Kolom E, G, U)
    try:
        # Index: E=4, G=6, U=20
        show_cols = [df.columns[4], df.columns[6], df.columns[20]] if df.shape[1] > 20 else df.columns
        st.dataframe(filtered_df[show_cols])
    except:
        st.dataframe(filtered_df)

    st.markdown("---")

    # 4. PROSES UNDUH & PEMBUATAN PDF
    if st.button("🚀 MULAI TARIK GAMBAR & BUAT PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data untuk diproses pada tanggal ini.")
            return
            
        valid_images = []
        progress_bar = st.progress(0)
        total_rows = len(filtered_df)
        
        links_found = 0
        downloads_success = 0
        
        with st.spinner("Sedang menembus enkripsi Drive & mengunduh foto asli..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                for col_name in df.columns:
                    cell_val = str(row[col_name])
                    
                    if "drive.google.com" in cell_val:
                        # Antisipasi jika dalam satu sel terdapat beberapa link dipisah koma
                        urls = cell_val.split(',')
                        for u in urls:
                            fid = get_file_id(u.strip())
                            if fid:
                                links_found += 1
                                img_data = download_image_bypass(fid)
                                if img_data:
                                    try:
                                        # Validasi ketat dengan Pillow: Pastikan ini data gambar asli, bukan HTML error
                                        with Image.open(img_data) as test_img:
                                            test_img.verify()
                                        img_data.seek(0)
                                        valid_images.append(img_data)
                                        downloads_success += 1
                                    except:
                                        pass
                                        
                progress_bar.progress(int(((idx + 1) / total_rows) * 100))
        
        st.info(f"📊 Laporan Hasil: Mendeteksi {links_found} link, berhasil mengamankan {downloads_success} foto asli.")

        # 5. RAKIT KE PDF
        if valid_images:
            with st.spinner("Menyatukan seluruh foto ke dalam file PDF..."):
                try:
                    pdf = FPDF()
                    for img_bytes in valid_images:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(img_bytes.read())
                            tmp_path = tmp.name
                        
                        pdf.add_page()
                        pdf.image(tmp_path, x=10, y=10, w=190)
                        
                        try: os.remove(tmp_path)
                        except: pass
                    
                    pdf_output_path = "Laporan_Gambar_PJB.pdf"
                    pdf.output(pdf_output_path)
                    
                    with open(pdf_output_path, "rb") as f:
                        st.download_button(
                            label="📥 KLIK DI SINI UNTUK DOWNLOAD FILE PDF",
                            data=f,
                            file_name=f"Bundel_Foto_PJB_{start_date}_sd_{end_date}.pdf",
                            mime="application/pdf"
                        )
                    
                    try: os.remove(pdf_output_path)
                    except: pass
                    st.success("🎉 Selesai! File PDF berhasil dirakit sempurna.")
                except Exception as pdf_err:
                    st.error(f"Gagal membuat susunan PDF: {pdf_err}")
        else:
            st.error("Gagal mengunduh foto. Google Drive memblokir akses otomatis.")

if __name__ == "__main__":
    main()
