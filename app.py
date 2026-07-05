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

def extract_file_id(url):
    """Mengekstrak ID file unik dari URL Google Drive"""
    if not isinstance(url, str): return None
    match = re.search(r'([a-zA-Z0-9_-]{25,})', url)
    return match.group(1) if match else None

def main():
    st.title("Ekspor Gambar PJB NOP Palangkaraya ke PDF")
    
    st.info("💡 Karena folder Anda sudah diset Publik ('Siapa saja yang memiliki link'), masukkan API Key Anda untuk melewati pemblokiran bot Google.")
    # Kotak input untuk API Key
    api_key = st.text_input("🔑 Paste API Key Google Cloud Anda di sini:", type="password")
    
    if not api_key:
        st.warning("Menunggu API Key dimasukkan...")
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
            st.error("🚨 Gagal membaca Spreadsheet. Pastikan link Sheet sudah Publik.")
            return

    # 2. FILTER TANGGAL
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
    st.write(f"Ditemukan **{len(filtered_df)} baris data**.")
    
    # TABEL SIMPEL (Kolom E, G, U)
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

    # 3. PROSES UNDUH MENGGUNAKAN API KEY
    if st.button("🚀 MULAI TARIK GAMBAR & PROSES PDF"):
        if filtered_df.empty:
            st.warning("Tidak ada data untuk diproses.")
            return
            
        img_paths = []
        progress_bar = st.progress(0)
        total_rows = len(filtered_df)
        
        total_links_found = 0
        total_downloads_success = 0
        
        with st.spinner("Mengunduh gambar menggunakan Jalur API Key..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                for col_name in df.columns:
                    cell_value = str(row[col_name])
                    
                    if "drive.google.com" in cell_value:
                        urls = cell_value.split(',')
                        for u in urls:
                            fid = extract_file_id(u.strip())
                            if fid:
                                total_links_found += 1
                                
                                # REQUEST SUPER KUAT: Membaca file via API Drive V3 menggunakan API KEY
                                url = f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media&key={api_key.strip()}"
                                
                                try:
                                    r = requests.get(url, timeout=15)
                                    if r.status_code == 200:
                                        # Validasi ketat bahwa ini gambar asli
                                        content_bytes = r.content
                                        with Image.open(BytesIO(content_bytes)) as test_img:
                                            test_img.verify() 
                                            
                                        with Image.open(BytesIO(content_bytes)) as real_img:
                                            if real_img.mode != 'RGB':
                                                real_img = real_img.convert('RGB')
                                            
                                            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                                            real_img.save(tmp_file.name, format="JPEG")
                                            img_paths.append(tmp_file.name)
                                            total_downloads_success += 1
                                except Exception as e:
                                    pass # Abaikan file jika masih ditolak atau rusak
                                        
                progress_bar.progress(int(((idx + 1) / total_rows) * 100))

        st.info(f"📊 Laporan: Mendeteksi {total_links_found} tautan Drive, berhasil mengamankan {total_downloads_success} foto.")

        # 4. RAKIT KE PDF
        if img_paths:
            with st.spinner("Merakit gambar ke dalam halaman PDF..."):
                try:
                    pdf = FPDF()
                    for img_path in img_paths:
                        pdf.add_page()
                        pdf.image(img_path, x=10, y=10, w=190)
                        
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
            st.error("Semua unduhan ditolak. Google Workspace masih mengunci file Anda.")

if __name__ == "__main__":
    main()
