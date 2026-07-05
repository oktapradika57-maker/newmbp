import streamlit as st
import pandas as pd
import requests
import re
import tempfile
import os
import urllib.parse
import datetime
from fpdf import FPDF
from io import BytesIO

# Konfigurasi Halaman Utama Streamlit
st.set_page_config(page_title="PDF Generator NOP Palangkaraya", layout="wide")

# ==========================================
# FUNGSI HELPER (PROSES DOKUMEN & GAMBAR)
# ==========================================

def extract_file_id(url):
    """Mengekstrak ID file unik dari URL Google Drive"""
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match_id: 
        return match_id.group(1)
    
    match_d = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match_d: 
        return match_d.group(1)
    return None

def download_image_public(file_id):
    """Mengunduh gambar secara publik menggunakan requests"""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        response = requests.get(url, timeout=15)
        # Validasi jika response sukses dan bukan halaman HTML (Google Virus Warning Page)
        if response.status_code == 200 and 'text/html' not in response.headers.get('Content-Type', ''):
            return BytesIO(response.content)
    except Exception as e:
        pass
    return None

def create_pdf(images_data):
    """Menyusun kumpulan data bytes gambar ke dalam satu file PDF"""
    pdf = FPDF()
    for img_bytes in images_data:
        # Membuat file temporer lokal karena FPDF membutuhkan path file fisik
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
            tmp_img.write(img_bytes.read())
            tmp_path = tmp_img.name
            
        pdf.add_page()
        # Mengatur posisi gambar di halaman A4 (Margin kiri 10, atas 10, lebar gambar 190)
        pdf.image(tmp_path, x=10, y=10, w=190)
        
        # Hapus kembali file temporer setelah dimasukkan ke PDF
        try:
            os.remove(tmp_path)
        except:
            pass
    
    # Simpan hasil PDF ke dalam memori untuk siap didownload
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        pdf.output(tmp_pdf.name)
        with open(tmp_pdf.name, "rb") as f:
            pdf_data = f.read()
            
    try:
        os.remove(tmp_pdf.name)
    except:
        pass
        
    return pdf_data

# ==========================================
# ALUR UTAMA APLIKASI WEB (MAIN FUNCTION)
# ==========================================

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    st.info("💡 Penting: Pastikan pengaturan privasi Spreadsheet dan Folder Gambar di Google Drive Anda sudah diubah ke 'Siapa saja yang memiliki link / Anyone with the link' agar aplikasi bisa menarik data tanpa kendala login.")
    
    # ID Spreadsheet dan Nama Sheet target
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB" 
    
    # Proses konversi nama sheet agar aman dibaca via URL browser
    encoded_sheet_name = urllib.parse.quote(SHEET_NAME)
    csv_export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
    
    # Mengambil data dari Google Sheet secara asinkronus
    with st.spinner("Mengambil data dari Google Sheets..."):
        try:
            df = pd.read_csv(csv_export_url)
        except Exception as e:
            st.error(f"Gagal membaca Spreadsheet. Pastikan link sudah di-set publik! Detail Error: {e}")
            return
            
    if df.empty:
        st.warning(f"Data pada tabel sheet '{SHEET_NAME}' terbaca kosong.")
        return

    # Mendeteksi Kolom Tanggal (Asumsi pada kolom pertama / indeks 0)
    date_col = df.columns[0]
    
    # Konversi kolom teks tanggal menjadi format objek tanggal Python
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    # Buang data yang baris tanggalnya rusak/kosong agar tidak menimbulkan error saat difilter
    df = df.dropna(subset=['Date_Parsed'])

    # Komponen Antarmuka Pengguna untuk Memilih Rentang Tanggal
    st.subheader("Filter Rentang Tanggal Pencarian")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Tanggal Mulai", value=datetime.date.today())
    with col2:
        end_date = st.date_input("Tanggal Akhir", value=datetime.date.today())
        
    if start_date > end_date:
        st.error("Format Salah: Tanggal mulai tidak boleh melebihi batas tanggal akhir!")
        return
        
    # Memfilter baris data yang masuk ke dalam rentang tanggal pilihan user
    mask = (df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)
    filtered_df = df.loc[mask]
    
    st.write(f"Ditemukan sebanyak **{len(filtered_df)} baris** data dalam rentang tersebut.")
    st.dataframe(filtered_df.head(5)) # Memperlihatkan pratinjau 5 baris pertama data Anda

    # Eksekusi tombol penarik gambar
    if st.button("Tarik Semua Gambar & Kemas ke PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data yang valid untuk diproses pada tanggal tersebut.")
            return
            
        images_bytes = []
        progress_bar = st.progress(0, text="Mempersiapkan sistem unduhan...")
        total_rows = len(filtered_df)
        
        with st.spinner("Sedang memproses dan mengunduh berkas gambar dari Google Drive..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                # Memotong data tabel hanya untuk kolom N (indeks 13) sampai T (indeks 19)
                try:
                    columns_n_to_t = df.iloc[:, 13:20] 
                except IndexError:
                    st.error("Struktur Tabel Salah: Jumlah total kolom kurang dari batas kolom T (20 kolom). Periksa susunan Spreadsheet Anda.")
                    return
                
                # Memeriksa sel link di kolom N sampai T pada baris aktif
                for col_name in columns_n_to_t.columns:
                    url_str = str(row.get(col_name, ""))
                    if "drive.google.com" in url_str:
                        # Jika dalam satu sel terdapat lebih dari satu link (dipisahkan koma)
                        urls = url_str.split(',')
                        for u in urls:
                            file_id = extract_file_id(u.strip())
                            if file_id:
                                img_io = download_image_public(file_id)
                                if img_io:
                                    images_bytes.append(img_io)
                                    
                # Mengubah persentase status loading bar
                progress_bar.progress(int(((idx + 1) / total_rows) * 100), text=f"Memproses baris data ke-{idx + 1} dari total {total_rows}")

        # Jika ada gambar yang berhasil didownload, buat filenya
        if images_bytes:
            with st.spinner("Mengonversi berkas gambar ke cetakan PDF..."):
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
                    st.error(f"Gagal memformat file PDF: {e}")
        else:
            st.error("Sistem tidak menemukan berkas gambar yang dapat diunduh. Pastikan semua tautan di kolom N hingga T adalah link Google Drive publik yang valid.")

if __name__ == "__main__":
    main()
