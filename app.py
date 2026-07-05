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

st.set_page_config(page_title="PDF Generator NOP Palangkaraya", layout="wide")

def extract_file_id(url):
    """Mengekstrak ID file unik dari URL Google Drive"""
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match_id: return match_id.group(1)
    
    match_d = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match_d: return match_d.group(1)
    return None

def download_image_public(file_id):
    """
    Mengunduh gambar menggunakan endpoint Thumbnail API Google Drive.
    sz=w1000 digunakan agar resolusi gambar tetap besar (lebar 1000px).
    Metode ini kebal terhadap halaman peringatan Anti-Bot Google.
    """
    url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
    
    # Menyamar sebagai browser PC agar tidak diblokir oleh Google
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        # Jika sukses (200) dan bukan file HTML
        if response.status_code == 200 and 'text/html' not in response.headers.get('Content-Type', ''):
            return BytesIO(response.content)
    except Exception:
        pass
    return None

def create_pdf(images_data):
    """Menyusun gambar ke dalam PDF"""
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
    
    with st.spinner("Mengambil data dari Google Sheets..."):
        try:
            df = pd.read_csv(csv_export_url)
        except Exception as e:
            st.error("🚨 GAGAL MEMBACA SPREADSHEET!")
            st.code(traceback.format_exc())
            return
            
    if df.empty or len(df.columns) < 2:
        st.error("🚨 DATA KOSONG ATAU FORMAT SALAH!")
        return

    try:
        date_col = df.columns[0]
        df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
        df = df.dropna(subset=['Date_Parsed'])
    except Exception as e:
        st.error("🚨 GAGAL MEMBACA KOLOM TANGGAL!")
        return

    st.subheader("Filter Rentang Tanggal Pencarian")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Tanggal Mulai", value=datetime.date.today())
    with col2:
        end_date = st.date_input("Tanggal Akhir", value=datetime.date.today())
        
    if start_date > end_date:
        st.error("Format Salah: Tanggal mulai tidak boleh melebihi batas tanggal akhir!")
        return
        
    mask = (df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)
    filtered_df = df.loc[mask]
    
    st.write(f"Ditemukan sebanyak **{len(filtered_df)} baris** data.")
    st.dataframe(filtered_df.head(5))

    if st.button("Tarik Semua Gambar & Kemas ke PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data yang valid untuk diproses pada tanggal tersebut.")
            return
            
        images_bytes = []
        progress_bar = st.progress(0, text="Mempersiapkan sistem unduhan...")
        total_rows = len(filtered_df)
        
        with st.spinner("Sedang memproses dan mengelabui sistem keamanan Drive..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                try:
                    # Ambil kolom N-T (indeks 13 s.d 19). Jika kolom kurang dari 20, ambil semampunya sampai akhir
                    columns_n_to_t = df.iloc[:, 13:20] if df.shape[1] >= 20 else df.iloc[:, 13:]
                except Exception:
                    st.error("🚨 GAGAL MEMOTONG KOLOM (N-T)!")
                    return
                
                for col_name in columns_n_to_t.columns:
                    url_str = str(row.get(col_name, ""))
                    if "drive.google.com" in url_str:
                        urls = url_str.split(',')
                        for u in urls:
                            file_id = extract_file_id(u.strip())
                            if file_id:
                                img_io = download_image_public(file_id)
                                if img_io:
                                    images_bytes.append(img_io)
                                    
                progress_bar.progress(int(((idx + 1) / total_rows) * 100), text=f"Selesai memproses baris {idx + 1} dari {total_rows}")

        if images_bytes:
            with st.spinner("Menyusun gambar ke dalam PDF..."):
                try:
                    pdf_data = create_pdf(images_bytes)
                    st.success("Sukses! File bundel dokumen PDF Anda siap diunduh.")
                    
                    st.download_button(
                        label="📥 Klik di Sini untuk Unduh PDF Laporan",
                        data=pdf_data,
                        file_name=f"Laporan_Gambar_PJB_{start_date}_sd_{end_date}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error("🚨 GAGAL MEMBUAT FILE PDF!")
                    st.code(traceback.format_exc())
        else:
            st.error("Sistem gagal menarik gambar. Meskipun folder sudah publik, pastikan sel di Spreadsheet (Kolom N-T) memang berisi link Google Drive yang sah.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        st.error("🚨 TERJADI KESALAHAN FATAL PADA SISTEM!")
        st.code(traceback.format_exc())
