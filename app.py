import streamlit as st
import pandas as pd
import numpy as np

# Konfigurasi Halaman
st.set_page_config(
    page_title="Genset Backup Monitor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ID Spreadsheet Anda
SPREADSHEET_ID = "1CrupWIBU3NP49ORN3AxC6ave7SD01ds_odu7NVBOIoI"
csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid=0"

st.title("⚡ Genset Backup Monitor")
st.caption("Komparasi Durasi Nyata (Waktu Start/Stop) vs Running Hours (RH) Genset")

# Tombol Refresh Data
if st.button("🔄 Refresh Data", type="primary"):
    st.rerun()

# Memuat Data dari Google Sheets
@st.cache_data(ttl=60) 
def load_data(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Gagal mengambil data dari Google Sheets. Pastikan link sudah 'Anyone with link can view'. Error: {e}")
        return None

df_raw = load_data(csv_url)

if df_raw is not None and not df_raw.empty:
    cols = df_raw.columns
    
    # 1. Identifikasi Kolom Utama
    start_backup_col = next((c for c in cols if 'start' in c.lower() and ('backup' in c.lower() or 'waktu' in c.lower())), None)
    stop_backup_col = next((c for c in cols if 'stop' in c.lower() and ('backup' in c.lower() or 'waktu' in c.lower())), None)
    
    # Perbaikan logic gate pencarian kolom RH
    rh_start_col = next((c for c in cols if ('rh' in c.lower() and 'start' in c.lower())), None)
    rh_stop_col = next((c for c in cols if ('rh' in c.lower() and 'stop' in c.lower())), None)

    # 2. Identifikasi Kolom Baru untuk Pencarian
    site_id_col = next((c for c in cols if 'site' in c.lower() and 'id' in c.lower()), None)
    pic_col = next((c for c in cols if 'pic' in c.lower() or 'take over' in c.lower()), None)
    tiket_col = next((c for c in cols if 'tiket' in c.lower() or 'ticket' in c.lower() or 'no' in c.lower()), None)

    if not all([start_backup_col, stop_backup_col, rh_start_col, rh_stop_col]):
        st.warning("⚠️ Beberapa kolom krusial tidak ditemukan. Pastikan nama kolom di Google Sheets mengandung kata kunci 'Start Backup', 'Stop Backup', 'RH Start', dan 'RH Stop'.")
        st.write("Kolom yang terdeteksi di sheet Anda:", list(cols))
    else:
        # --- PRE-PROCESSING DATA ---
        df = df_raw.copy()
        df[start_backup_col] = pd.to_datetime(df[start_backup_col], errors='coerce', format='mixed')
        df[stop_backup_col] = pd.to_datetime(df[stop_backup_col], errors='coerce', format='mixed')
        df[rh_start_col] = pd.to_numeric(df[rh_start_col], errors='coerce').fillna(0)
        df[rh_stop_col] = pd.to_numeric(df[rh_stop_col], errors='coerce').fillna(0)
        df = df.dropna(subset=[start_backup_col])

        # Kalkulasi Durasi & Selisih
        df['Durasi Waktu Nyata (Jam)'] = (df[stop_backup_col] - df[start_backup_col]).dt.total_seconds() / 3600
        df['Durasi Waktu Nyata (Jam)'] = df['Durasi Waktu Nyata (Jam)'].apply(lambda x: x if x >= 0 else 0).round(2)
        df['Durasi RH (Jam)'] = np.where(df[rh_stop_col] >= df[rh_start_col], df[rh_stop_col] - df[rh_start_col], 0).round(2)
        df['Selisih (Jam)'] = (df['Durasi Waktu Nyata (Jam)'] - df['Durasi RH (Jam)']).abs().round(2)

        # FIX: Menggunakan tipe data bawaan Python objek 'str' yang murni, bukan alias streamlit
        for c in [site_id_col, pic_col, tiket_col]:
            if c: 
                df[c] = df[c].astype(object).astype(str).fillna('')

        # --- SIDEBAR PANEL PENCARIAN & FILTER ---
        st.sidebar.header("🔍 Panel Pencarian")
        
        search_site = st.sidebar.text_input("Cari Site ID")
        search_pic = st.sidebar.text_input("Cari PIC Take Over")
        search_tiket = st.sidebar.text_input("Cari Nomor Tiket")
        
        if st.sidebar.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()

        # Proses Filtering Berdasarkan Input User
        df_filtered = df.copy()
        if search_site and site_id_col:
            df_filtered = df_filtered[df_filtered[site_id_col].str.contains(search_site, case=False, na=False)]
        if search_pic and pic_col:
            df_filtered = df_filtered[df_filtered[pic_col].str.contains(search_pic, case=False, na=False)]
        if search_tiket and tiket_col:
            df_filtered = df_filtered[df_filtered[tiket_col].str.contains(search_tiket, case=False, na=False)]

        # --- TAMPILAN KPI METRICS ---
        total_backup = len(df_filtered)
        total_waktu_nyata = df_filtered['Durasi Waktu Nyata (Jam)'].sum()
        total_rh = df_filtered['Durasi RH (Jam)'].sum()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Total Kejadian Backup", value=f"{total_backup} Kali")
        with col2:
            st.metric(label="Total Akumulasi Waktu Nyata", value=f"{total_waktu_nyata:.2f} Jam")
        with col3:
            st.metric(label="Total Akumulasi RH Genset", value=f"{total_rh:.2f} Jam")

        st.markdown("---")

        # --- TAMPILAN GRAFIK ANALISA ---
        st.subheader("📊 Grafik Analisa Durasi Backup")
        if not df_filtered.empty:
            chart_data = pd.DataFrame({
                'Durasi Nyata (Jam)': df_filtered['Durasi Waktu Nyata (Jam)'].values,
                'Durasi RH (Jam)': df_filtered['Durasi RH (Jam)'].values
            }, index=df_filtered[site_id_col].values if site_id_col else range(1, len(df_filtered) + 1))
            
            st.bar_chart(chart_data, y=['Durasi Nyata (Jam)', 'Durasi RH (Jam)'], color=["#3b82f6", "#f59e0b"])
        else:
            st.info("Tidak ada data untuk menampilkan grafik.")

        st.markdown("---")

        # --- TAMPILAN TABEL LOG DATA ---
        st.subheader("📋 Log Perhitungan & Komparasi Data")
        
        if not df_filtered.empty:
            df_display = pd.DataFrame({
                "No": range(1, len(df_filtered) + 1),
                "Site ID": df_filtered[site_id_col] if site_id_col else "-",
                "No Tiket": df_filtered[tiket_col] if tiket_col else "-",
                "PIC Take Over": df_filtered[pic_col] if pic_col else "-",
                "Waktu Start": df_filtered[start_backup_col].dt.strftime('%Y-%m-%d %H:%M').fillna('-'),
                "Waktu Stop": df_filtered[stop_backup_col].dt.strftime('%Y-%m-%d %H:%M').fillna('-'),
                "Durasi Nyata": df_filtered['Durasi Waktu Nyata (Jam)'].map("{:.2f} Jam".format),
                "RH Start": df_filtered[rh_start_col],
                "RH Stop": df_filtered[rh_stop_col],
                "Durasi RH": df_filtered['Durasi RH (Jam)'].map("{:.2f} Jam".format),
                "Selisih Komparasi": df_filtered['Selisih (Jam)'].map("{:.2f} Jam".format)
            })

            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.warning("Data tidak ditemukan. Silakan periksa kembali kata kunci pencarian Anda pada sidebar.")
else:
    st.info("Belum ada data atau spreadsheet kosong.")
