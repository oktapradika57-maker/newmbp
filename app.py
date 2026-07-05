import streamlit as st
import pandas as pd
import requests
import re
import tempfile
import os
import urllib.parse
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="PDF Generator NOP Palangkaraya", layout="wide")

# 1. FUNGSI UNTUK MENDAPATKAN ID GAMBAR DAN MENGUNDUHNYA
def extract_file_id(url):
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match_id: return match_id.group(1)
    
    match_d = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match_d: return match_d.group(1)
    return None

def download_image_public(file_id):
    # Menggunakan endpoint direct download Google Drive
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        response = requests.get(url, timeout=10)
        # Memastikan yang didownload benar-benar file gambar, bukan halaman peringatan Google
        if response.status_code == 200 and 'text/html' not in response.headers.get('Content-Type', ''):
            return BytesIO(response.content)
    except Exception as e:
        st.error(f"Error saat mengunduh gambar ID {file_id}: {e}")
    return None

# 2. FUNGSI MEMBUAT PDF
def create_pdf(images_data):
    pdf = FPDF()
    for img_bytes in images_data:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
            tmp_img.write(img_bytes.read())
            tmp_path = tmp_img.name
            
        pdf.add_page()
        pdf.image(tmp_path, x=10, y=10, w=190)
        os.remove(tmp_path)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        pdf.output(tmp_pdf.name)
        with open(tmp_pdf.name, "rb") as f:
            pdf_data = f.read()
    os.remove(tmp_pdf.name)
    return pdf_data

# 3. APLIKASI UTAMA
def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    st.info("💡 Pastikan akses Spreadsheet dan Folder Gambar di Google Drive sudah diset ke 'Siapa saja yang memiliki link'.")
    
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB" # Spesifik mengambil sheet Form PJB
    
    # Membaca data langsung tanpa otentikasi (karena sudah dibuat publik)
    encoded_sheet_name = urllib.parse.quote(SHEET_NAME)
    csv_export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
    
    with st.spinner("Mengambil data dari Google Sheets..."):
        try:
            df = pd.read_csv(csv_export_url)
        except Exception as e:
            st.error(f"Gagal membaca Spreadsheet. Pastikan link sudah di-set publik! Error: {e}")
            return
            
    if df.empty:
        st.warning(f"Data pada sheet '{SHEET_NAME}' kosong.")
        return

    # Asumsi: Kolom tanggal berada di kolom paling kiri (index 0).
    date_col = df.columns[0]
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date

    st.subheader("Filter Tanggal")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Tanggal Mulai")
    with col2:
        end_date = st.date_input("Tanggal Akhir")
        
    if start_date > end_date:
        st.error("Tanggal mulai tidak boleh lebih dari tanggal akhir!")
        return
        
    mask = (df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)
    filtered_df = df.loc[mask]
    
    st.write(f"Ditemukan **{len(filtered_df)} baris** pada rentang tanggal tersebut.")
    st.dataframe(filtered_df.head(3))

    if st.button("Tarik Gambar & Buat PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data untuk diproses.")
            return
            
        images_bytes = []
        progress_bar = st.progress(0, text="Mempersiapkan unduhan...")
        total_rows = len(filtered_df)
        
        with st.spinner("Sedang memproses gambar dari Google Drive..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                # Mengambil data dari kolom N (index 13) sampai T (index 19)
                # Pastikan jumlah kolom mencukupi agar tidak terjadi error
                try:
                    columns_n_to_t = df.iloc[:, 13:20] 
                except IndexError:
                    st.error("Jumlah kolom di Spreadsheet kurang dari T (kolom ke-20). Cek kembali struktur tabel.")
                    return
                
                # Cek setiap sel di kolom N-T pada baris yang sedang diproses
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
                                else:
                                    st.warning(f"Gagal/Akses ditolak mendownload gambar ID: {file_id}")
                                    
                progress_bar.progress(int(((idx + 1) / total_rows) * 100), text=f"Memproses baris ke-{idx + 1} dari {total_rows}")

        if images_bytes:
            with st.spinner("Mengonversi ke PDF..."):
                try:
                    pdf_data = create_pdf(images_bytes)
                    st.success("Selesai! PDF siap diunduh.")
                    
                    st.download_button(
                        label="📥 Download File PDF",
                        data=pdf_data,
                        file_name=f"Gambar_PJB_{start_date}_sd_{end_date}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Gagal membuat PDF: {e}")
        else:
            st.error("Tidak ada gambar yang berhasil diunduh. Pastikan folder Google Drive gambar Anda sudah di-set ke 'Siapa saja yang memiliki link / Anyone with the link'.")

if __name__ == "__main__":
    main()
