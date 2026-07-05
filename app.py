
import streamlit as st
import pandas as pd
import re
import tempfile
import os
import urllib.parse
import datetime
import traceback
from fpdf import FPDF
import gdown

st.set_page_config(page_title="PDF Generator PJB", layout="wide")

def extract_file_id(url):
    """Mengekstrak ID file unik dari URL Google Drive menggunakan Regex"""
    match = re.search(r'[-\w]{25,}', url)
    if match: return match.group(0)
    return None

def create_pdf(image_paths):
    """Menyatukan semua file fisik lokal ke PDF"""
    pdf = FPDF()
    for img_path in image_paths:
        pdf.add_page()
        # Margin kiri 10, atas 10, lebar gambar 190 (menyesuaikan ukuran A4)
        pdf.image(img_path, x=10, y=10, w=190)
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        pdf.output(tmp_pdf.name)
        with open(tmp_pdf.name, "rb") as f:
            pdf_data = f.read()
            
    # Membersihkan semua file gambar temporer agar server tidak penuh
    for img_path in image_paths:
        try: os.remove(img_path)
        except: pass
        
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
            st.error("🚨 Gagal membaca Spreadsheet. Pastikan link Sheet publik.")
            return

    if df.empty:
        st.warning("Data kosong.")
        return

    # Ambil kolom tanggal (kolom index 0)
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
    # MENAMPILKAN TABEL HANYA UNTUK KOLOM E(4), G(6), DAN U(20)
    # ---------------------------------------------------------
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
            
        image_paths = []
        progress_bar = st.progress(0, text="Memulai pemindaian tautan Drive...")
        total_rows = len(filtered_df)
        
        total_links_found = 0
        total_downloads_success = 0
        
        with st.spinner("Memindai sel dan mengunduh gambar menggunakan mesin GDOWN..."):
            for idx, (index, row) in enumerate(filtered_df.iterrows()):
                
                # SENSOR: Pindai semua sel untuk mencari link Drive
                for col_name in df.columns:
                    cell_value = str(row[col_name])
                    
                    if "drive.google.com" in cell_value:
                        urls = cell_value.split(',')
                        for u in urls:
                            file_id = extract_file_id(u.strip())
                            if file_id:
                                total_links_found += 1
                                
                                # Menggunakan library gdown untuk membypass blokir
                                tmp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                                try:
                                    res = gdown.download(id=file_id, output=tmp_path, quiet=True)
                                    if res:
                                        image_paths.append(tmp_path)
                                        total_downloads_success += 1
                                    else:
                                        os.remove(tmp_path) # Hapus jika gagal
                                except Exception:
                                    try: os.remove(tmp_path)
                                    except: pass
                                    
                progress_bar.progress(int(((idx + 1) / total_rows) * 100), text=f"Selesai memproses baris ke-{idx + 1}")

        st.info(f"📊 Laporan Sistem: Ditemukan {total_links_found} tautan Google Drive, dan berhasil mengunduh {total_downloads_success} gambar.")

        if image_paths:
            with st.spinner("Merakit gambar menjadi file PDF..."):
                try:
                    pdf_data = create_pdf(image_paths)
                    st.success("🎉 PDF Berhasil Dibuat!")
                    st.download_button(
                        label="📥 Klik di Sini untuk Unduh PDF Laporan",
                        data=pdf_data,
                        file_name=f"Laporan_Gambar_PJB_{start_date}_sd_{end_date}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error("Gagal menyatukan gambar ke PDF. Pastikan format file memang berupa gambar (bukan video/dokumen).")
                    st.code(traceback.format_exc())
        else:
            if total_links_found > 0:
                st.error("Sistem menemukan link-nya, namun Google Drive Anda memiliki keamanan tingkat tinggi yang menolak aplikasi eksternal (mungkin terikat oleh keamanan email perusahaan/Workspace).")
            else:
                st.warning("Tidak ada link Google Drive yang terdeteksi sama sekali pada rentang tanggal tersebut.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        st.error("🚨 TERJADI KESALAHAN FATAL PADA SISTEM!")
        st.code(traceback.format_exc())
