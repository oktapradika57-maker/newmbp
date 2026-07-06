import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
import requests
import base64
from fpdf import FPDF
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def extract_file_id(url):
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    st.success("⚡ SISTEM TERBARU: Jembatan API Workspace + Filter Role Interaktif")
    
    # URL Web App dari Apps Script
    WEB_APP_URL = st.text_input("🔗 Paste URL Aplikasi Web (Apps Script) Anda di sini:", type="password")
    
    if not WEB_APP_URL:
        st.warning("Menunggu URL Aplikasi Web dimasukkan...")
        return

    st.markdown("---")
    
    # 1. BACA DATA SPREADSHEET
    SHEET_ID = "1HvgVicTWwO4RMQI6ZR3Mu3IgGicwjcLZl9mDN1auvJU"
    SHEET_NAME = "Form PJB" 
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(SHEET_NAME)}"
    
    with st.spinner("Membaca data Spreadsheet..."):
        try:
            df = pd.read_csv(csv_url)
        except Exception as e:
            st.error("🚨 Gagal membaca Spreadsheet.")
            return

    # 2. PERSIAPAN KOLOM TANGGAL & ROLE
    date_col = df.columns[0]
    role_col = df.columns[5] # Kolom F adalah index ke-5 (A=0, B=1, C=2, D=3, E=4, F=5)
    
    df['Date_Parsed'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Date_Parsed'])
    
    # Mengambil daftar Role unik dari Kolom F (menghapus yang kosong)
    daftar_role = ["Semua Role"] + df[role_col].dropna().astype(str).unique().tolist()

    # 3. AREA FILTER (TANGGAL & ROLE)
    st.subheader("⚙️ Filter Data Laporan")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        start_date = st.date_input("Tanggal Mulai", value=datetime.date.today())
    with col2:
        end_date = st.date_input("Tanggal Akhir", value=datetime.date.today())
    with col3:
        selected_role = st.selectbox("Pilih Role (Kolom F)", options=daftar_role)
        
    # Terapkan Filter Tanggal
    filtered_df = df[(df['Date_Parsed'] >= start_date) & (df['Date_Parsed'] <= end_date)]
    
    # Terapkan Filter Role (Jika tidak memilih "Semua Role")
    if selected_role != "Semua Role":
        filtered_df = filtered_df[filtered_df[role_col].astype(str) == selected_role]
        
    st.write(f"Ditemukan *{len(filtered_df)} baris data* sesuai filter di atas.")
    
    # 4. TABEL PRATINJAU
    try:
        show_cols = []
        if df.shape[1] > 4: show_cols.append(df.columns[4]) # Kolom E
        if df.shape[1] > 5: show_cols.append(df.columns[5]) # Kolom F (Role) untuk verifikasi
        if df.shape[1] > 6: show_cols.append(df.columns[6]) # Kolom G
        if df.shape[1] > 20: show_cols.append(df.columns[20]) # Kolom U
        
        if show_cols:
            st.dataframe(filtered_df[show_cols])
        else:
            st.dataframe(filtered_df)
    except:
        st.dataframe(filtered_df)
        
    st.markdown("---")

    # 5. PROSES UNDUH & PDF
    if st.button("🚀 MULAI TARIK GAMBAR & PROSES PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data untuk diproses dengan filter tersebut.")
            return
            
        img_paths = []
        progress_bar = st.progress(0)
        total_rows = len(filtered_df)
        
        total_links_found = 0
        total_downloads_success = 0
        
        with st.spinner("Mengunduh gambar menembus Workspace via API Internal..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                for col_name in df.columns:
                    cell_value = str(row[col_name])
                    
                    if "drive.google.com" in cell_value:
                        urls = cell_value.split(',')
                        for u in urls:
                            fid = extract_file_id(u.strip())
                            if fid:
                                total_links_found += 1
                                
                                # REQUEST KE JEMBATAN APPS SCRIPT
                                req_url = f"{WEB_APP_URL.strip()}?id={fid}"
                                
                                try:
                                    r = requests.get(req_url, timeout=20)
                                    if r.status_code == 200 and not r.text.startswith("ERROR"):
                                        image_data = base64.b64decode(r.text)
                                        
                                        with Image.open(BytesIO(image_data)) as real_img:
                                            if real_img.mode != 'RGB':
                                                real_img = real_img.convert('RGB')
                                            
                                            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                                            real_img.save(tmp_file.name, format="JPEG")
                                            img_paths.append(tmp_file.name)
                                            total_downloads_success += 1
                                except Exception as e:
                                    pass
                                        
                progress_bar.progress(int(((idx + 1) / total_rows) * 100))

        st.info(f"📊 Laporan: Mendeteksi {total_links_found} tautan, berhasil menarik {total_downloads_success} foto.")

        if img_paths:
            with st.spinner("Merakit gambar ke dalam halaman PDF..."):
                try:
                    pdf = FPDF()
                    for img_path in img_paths:
                        pdf.add_page()
                        pdf.image(img_path, x=10, y=10, w=190)
                        
                        try: os.remove(img_path)
                        except: pass
                        
                    # Penamaan PDF menyesuaikan Role yang dipilih
                    role_name_clean = "SemuaRole" if selected_role == "Semua Role" else str(selected_role).replace(" ", "_")
                    pdf_output_name = f"Laporan_PJB_{role_name_clean}.pdf"
                    
                    pdf.output(pdf_output_name)
                    
                    with open(pdf_output_name, "rb") as f:
                        st.download_button(
                            label="📥 KLIK DI SINI UNTUK UNDUH FILE PDF",
                            data=f,
                            file_name=f"Laporan_Gambar_PJB_{role_name_clean}{start_date}_sd{end_date}.pdf",
                            mime="application/pdf"
                        )
                    
                    try: os.remove(pdf_output_name)
                    except: pass
                    st.success("🎉 Luar Biasa! PDF berhasil dibuat sesuai filter dengan sempurna!")
                except Exception as pdf_err:
                    st.error(f"Gagal merakit PDF: {pdf_err}")
        else:
            st.error("Gagal menarik foto. Periksa kembali URL Aplikasi Web Anda.")

if __name__ == "__main__":
    main()
