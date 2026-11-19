Selected Files Directory Structure:

└── ./
    ├── clean-data
    │   ├── databersih.csv
    │   ├── fiony_cleaning.csv
    │   ├── gracie_bersih.csv
    │   └── test.csv
    ├── data
    │   ├── slang.csv
    │   └── stopwordbahasa.csv
    ├── preprocessing
    │   ├── __init__.py
    │   └── pipeline.py
    ├── app.py
    ├── cleaner.py
    ├── crawler.py
    └── test.py



--- app.py ---

# Import
import streamlit as streamlit
import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import ast
import time

from datetime import datetime
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.util import ngrams
from transformers import pipeline

from sqlalchemy import create_engine, inspect, text

from crawler import crawl_x
from cleaner import bersihkan, filter_bahasa
from preprocessing.pipeline import jalankan_pipeline

# Head of Pages
st.set_page_config(
    page_title="Deteksi Trending Topik",
    page_icon="📑",
    layout="wide"
)

def halaman_crawling():
    st.title("🔎 Crawling")
    st.markdown("This page is for retrieving data from X")

    with st.form("form_crawl", border=False):
        input_keywords = st.text_area(
            "Input Keyword", 
            placeholder="ex: prabowo, kopdes, ihsg",
            help="You can enter more than one keyword. Separate each keyword with a comma (,)"
        )

        # Ganti labelnya biar jelas fungsinya cuma buat CSV
        filename = st.text_input(
            "Filename (For Local CSV Backup)",
            placeholder="ex fiony_alveria",
            help="The data will be saved in the 'raw_data_tweet' table. This is only for naming the .csv file."
        )

        col1,col2 = st.columns(2)
        with col1:
            since = st.date_input("Since")
        with col2:
            until = st.date_input("Until")

        limit = st.number_input(
            "Limit Tweet",
            min_value=1,
            max_value=1000,
            value=100
        )

        submitted = st.form_submit_button("🔎 Crawl", type="primary")
        
    try:
        db_connection_str = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'
        engine = create_engine(db_connection_str)
        query = "SELECT MAX(time_slot) as max_slot FROM raw_data_tweet"
        df_max = pd.read_sql(query, con=engine)
        max_slot = df_max['max_slot'].iloc[0]
        
        current_counter = 0 if pd.isna(max_slot) else int(max_slot)
    except Exception:
        current_counter = 0

    st.write("") # Kasih sedikit jarak/spasi dari form

    # 2. Bikin layout 2 kolom (Kolom 1 lebih lebar biar tombol ke-dorong ke kanan)
    col_counter, col_hapus = st.columns([5, 1])

    with col_counter:
        st.write(f"**Counter:** {current_counter}")

    with col_hapus:
        if st.button("🗑️ Delete Data", type="secondary", use_container_width=True):
            try:
                with engine.begin() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS raw_data_tweet"))
                
                # 1. Munculin pesan sukses
                st.success("✅ All 'raw_data_tweet' data has been successfully deleted!")
                
                # 2. Tahan eksekusi (pause) selama 2 detik biar pesannya terbaca
                time.sleep(2) 
                
                # 3. Baru refresh halamannya biar counter mereset jadi 0
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to delete data: {e}")
    
    # Validation of Button Crawl
    if submitted:
    # 1. Validasi
        if not input_keywords.strip():
            st.error("⚠️ Keyword cannot be empty!")
            return
        
        if not filename.strip():
            st.error("⚠️ Filename cannot be empty! Please enter the filename (without .csv).")
            return
        
        # 2. Konversi tanggal
        since_str = since.strftime("%Y-%m-%d")
        until_str = until.strftime("%Y-%m-%d")
        
        # 3. Jalankan crawl dengan spinner
        with st.spinner("Crawling in progress, please wait..."):
            sukses, pesan = crawl_x(
                input_keywords=input_keywords,
                since=since_str,
                until=until_str,
                filename=filename,
                limit=limit
            )
        
        # --- PERBAIKAN LOGIKA DISINI ---
        if sukses:
            path = f"tweets-data/{filename}.csv"
            
            # Cek dulu apakah filenya beneran ada di sistem buat jaga-jaga
            if os.path.exists(path):
                df = pd.read_csv(path)
                st.caption(f"File: {filename} ({len(df)} baris)")
                st.success(f"💾 Saved Locally: {path}")

                # --- TAMBAHAN KONEKSI DATABASE ---
                try:
                    db_connection_str = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'
                    engine = create_engine(db_connection_str)

                    # --- LOGIKA AUTO-INCREMENT TIME SLOT ---
                    try:
                        # Cek angka time_slot paling besar di tabel saat ini
                        query = "SELECT MAX(time_slot) as max_slot FROM raw_data_tweet"
                        df_max = pd.read_sql(query, con=engine)
                        max_slot = df_max['max_slot'].iloc[0]
                        
                        # Kalau nilai balikan kosong (NaN) berarti tabel ada tapi belum ada isinya
                        if pd.isna(max_slot):
                            time_slot_otomatis = 1
                        else:
                            time_slot_otomatis = int(max_slot) + 1
                    except Exception:
                        # Bakal lari ke sini kalau tabel 'raw_data_tweet' BELUM PERNAH DIBIKIN sama sekali
                        time_slot_otomatis = 1

                    # 1. Taruh time_slot di urutan pertama (index 0)
                    df.insert(0, 'time_slot', time_slot_otomatis)

                    # 2. Ambil waktu lokal sekarang dengan format Tahun-Bulan-Tanggal Jam:Menit:Detik
                    waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 3. Taruh waktu_crawl di urutan kedua (index 1), persis di sebelah time_slot
                    df.insert(1, 'waktu_crawl', waktu_sekarang)

                    # 4. Simpan ke database dengan nama tabel statis
                    df.to_sql(name='raw_data_tweet', con=engine, if_exists='append', index=False)

                    st.success(f"✅ The data has been inserted into the 'raw_data_tweet' table (Time Slot {time_slot_otomatis}) and has been saved locally!")
                except Exception as e:
                    st.error(f"❌ Failed to connect to the database: {e}")
                # ---------------------------------

                with st.expander("preview of file"):
                    st.dataframe(df.head(10))

                # Download File        
                csv_string = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV Crawling",
                    data=csv_string,
                    file_name=f"{filename}.csv",
                    mime="text/csv"
                )
            else:
                st.error("❌ Crawl was successful, but the CSV file was not found.")
        else:
            # Kalau dari awal crawl_x udah gagal
            st.error(f"❌ Crawling process failed: {pesan}")


# def halaman_cleaning_preprocessing():
#     st.title("🧹 Cleaning & Preprocessing")
#     st.markdown("This page is for cleaning and preprocessing (normalization & stemming) data from X.")
    
#     st.write("")

#     # --- 1. FITUR PILIH SUMBER DATA ---
#     sumber_data = st.radio(
#         "📁 Select the data source you want to process:", 
#         ["🗄️ use 'raw_data_tweet' table", "📄 Upload CSV File"],
#         horizontal=True  # <--- Tambahin parameter ini di sini
#     )
    
#     df_raw = None

#     # Opsi A: Dari Database (Persis kaya sebelumnya)
#     if sumber_data == "🗄️ use 'raw_data_tweet' table":
#         db_connection_str = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'
#         try:
#             engine = create_engine(db_connection_str)
#             inspector = inspect(engine)
            
#             if "raw_data_tweet" in inspector.get_table_names():
#                 df_raw = pd.read_sql_table("raw_data_tweet", con=engine)
#                 st.success(f"📦 Successfully loaded the 'raw_data_tweet' table ({len(df_raw)} rows).")
#             else:
#                 st.warning("⚠️ The 'raw_data_tweet' table has not been found. Please perform Crawling first.")
#                 return
#         except Exception as e:
#             st.error(f"❌ Failed to connect to the database: {e}")
#             return
            
#     # Opsi B: Upload CSV Lokal
#     elif sumber_data == "📄 Upload CSV File":
#         uploaded_file = st.file_uploader("Upload Your CSV File", type=['csv'])
#         if uploaded_file is not None:
#             try:
#                 df_raw = pd.read_csv(uploaded_file)
#                 st.success(f"📦 CSV file successfully loaded '{uploaded_file.name}' ({len(df_raw)} rows).")
#             except Exception as e:
#                 st.error(f"❌ Failed to read the CSV file: {e}")
#                 return
#         else:
#             st.info("Please upload a CSV file to continue.")
#             return

#     # Tampilkan preview data mentah jika berhasil di-load
#     if df_raw is not None and not df_raw.empty:
#         with st.expander("File Preview"):
#             st.dataframe(df_raw.head())
#     else:
#         return # Hentikan kalau data kosong

#     st.write("---")
#     st.caption("⚙️ Parameter Settings")
    
#     # Target Bahasa udah DIBUANG. Sisa metrik jumlah kata dan nama file.
#     min_kata = st.number_input("Minimum Word Count", min_value=1, max_value=20, value=3)

#     filename_backup = st.text_input(
#         "Filename (For Local CSV Backup)",
#         placeholder="ex fiony_clean",
#         help="The data will be saved in the 'preprocessing_data_tweet' table. This is only for naming the .csv file."
#     )

#     # --- 2. TOMBOL EKSEKUSI ---
#     if st.button("🧹 Clean & Preprocess", type="primary"):
        
#         with st.spinner("Cleaning, Tokenizing, Stemming in progress, please wait..."):
#             start_time = time.time()
            
#             # --- PROSES NLP MURNI ---
            
#             # Cek keamanan kolom CSV (siapa tau CSV yang di-upload namanya beda)
#             kolom_teks_target = "full_text" if "full_text" in df_raw.columns else df_raw.columns[0]
#             kolom_kunci_target = "id_str" if "id_str" in df_raw.columns else (df_raw.columns[0] if len(df_raw.columns) > 0 else "")
            
#             # Jangan maksa narik time_slot/waktu_crawl kalau user nge-upload CSV murni yang gak ada kolom itunya
#             kolom_penting_tersedia = [col for col in ["time_slot", "waktu_crawl", kolom_teks_target] if col in df_raw.columns]

#             # 1. Bersihkan Teks
#             df_clean = bersihkan(
#                 df=df_raw, 
#                 kolom_penting=kolom_penting_tersedia, 
#                 kolom_kunci=kolom_kunci_target, 
#                 kolom_teks=kolom_teks_target, 
#                 min_kata=min_kata
#             )
            
#             # 3. Preprocessing (Token, Stopword, Stemming)
#             df_hasil = jalankan_pipeline(df=df_raw, kolom_target='full_text', min_kata=min_kata)
            
#             # Gabungkan token hasil stemming
#             if 'stemmed' in df_hasil.columns:
#                 df_hasil['final_text'] = df_hasil['stemmed'].apply(lambda x: " ".join(x) if isinstance(x, list) else x)

#             end_time = time.time()

#         # --- TAHAP 1: METRIK ---
#         st.subheader("📈 Filtering & Cleaning Results")
#         col_met1, col_met2, col_met3 = st.columns(3)
#         with col_met1:
#             st.metric("Before", len(df_raw))
#         with col_met2:
#             st.metric("After", len(df_hasil))
#         with col_met3:
#             st.metric("Discarded (Word & Language Filter)", len(df_raw) - len(df_hasil))
        
#         st.success(f"✅ Cleaning, Tokenizing, Stemming completed in {round(end_time - start_time, 2)} seconds!")

#         # --- TAHAP 2: OTOMATIS MASUK DATABASE ---
#         df_sql = df_hasil.copy()
        
#         # MySQL gak bisa ngebaca list, wajib jadi string
#         for col in df_sql.columns:
#             df_sql[col] = df_sql[col].apply(lambda x: str(x) if isinstance(x, list) else x)

#         try:
#             # Karena engine di atas cuma nyala pas milih opsi A, kita define ulang buat nyimpen
#             db_connection_str = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'
#             engine_save = create_engine(db_connection_str)
#             df_sql.to_sql(name='preprocessing_data_tweet', con=engine_save, if_exists='replace', index=False)
#             st.success("✅ The data has been inserted into the 'preprocessing_data_tweet' tabel!")
#         except Exception as e:
#             st.error(f"❌ Failed to connect to the database: {e}")

#         # --- TAHAP 3: BACKUP CSV LOKAL ---
#         if filename_backup.strip():
#             nama_aman_csv = filename_backup.replace(" ", "_").lower()
#             os.makedirs("processed-data", exist_ok=True)
#             path_output = f"processed-data/{nama_aman_csv}.csv"
#             df_hasil.to_csv(path_output, index=False)
#             st.success(f"💾 Saved Locally: {path_output}")

#         # --- TAHAP 4: PREVIEW UI ---
#         st.subheader("📋 Final Result Preview")
#         kolom_tampil = ["time_slot", "waktu_crawl", kolom_teks_target, "final_text"]
#         kolom_ada = [k for k in kolom_tampil if k in df_hasil.columns]
#         st.dataframe(df_hasil[kolom_ada].head(10))

#         # Tentukan nama file (pakai inputan user kalau diisi, kalau kosong pakai nama tabel default)
#         if filename_backup.strip():
#             nama_file_download = f"{filename_backup.replace(' ', '_').lower()}.csv"
#         else:
#             nama_file_download = "preprocessing_data_tweet.csv"
            
#         csv_string = df_hasil.to_csv(index=False)
#         st.download_button(
#             label="📥 Download CSV Preprocessing",
#             data=csv_string,
#             file_name=nama_file_download,
#             mime="text/csv"
#         )
    

#     # ==========================================================
#     # BLOK COUNTER & TOMBOL HAPUS KHUSUS PREPROCESSING
#     # ==========================================================
#     count_raw = 0
#     count_prep = 0
    
#     try:
#         db_connection_str = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'
#         engine = create_engine(db_connection_str)
        
#         # 1. Hitung time_slot dari raw_data_tweet (Data Mentah)
#         try:
#             query_raw = "SELECT COUNT(DISTINCT time_slot) as jml_raw FROM raw_data_tweet"
#             df_raw_count = pd.read_sql(query_raw, con=engine)
#             count_raw = int(df_raw_count['jml_raw'].iloc[0])
#         except Exception:
#             count_raw = 0
            
#         # 2. Hitung time_slot dari preprocessing_data_tweet (Data Olahan)
#         try:
#             query_prep = "SELECT COUNT(DISTINCT time_slot) as jml_prep FROM preprocessing_data_tweet"
#             df_prep_count = pd.read_sql(query_prep, con=engine)
#             count_prep = int(df_prep_count['jml_prep'].iloc[0])
#         except Exception:
#             count_prep = 0
#     except Exception:
#         pass

#     st.write("") # Kasih sedikit spasi

#     # Layout 2 kolom (Kiri buat Counter, Kanan buat Tombol)
#     col_counter, col_hapus = st.columns([5, 1])

#     with col_counter:
#         st.write(f"**Total Counter: `{count_raw}` available in 'raw_data_tweet'")

#     with col_hapus:
#         # Tambahin parameter 'key' biar Streamlit nggak bingung sama tombol hapus di halaman sebelah
#         if st.button("🗑️ Delete Data", type="secondary", use_container_width=True, key="btn_hapus_prep"):
#             try:
#                 with engine.begin() as conn:
#                     # Gunakan DELETE FROM untuk mengosongkan isi tabel tanpa menghapus tabelnya
#                     conn.execute(text("DELETE FROM preprocessing_data_tweet"))
                
#                 st.success("✅ All 'preprocessing_data_tweet' data has been successfully deleted!")
#                 time.sleep(2) 
#                 st.rerun()
#             except Exception as e:
#                 st.error(f"❌ Failed to delete data: {e}")
#     # ==========================================================

def halaman_cleaning_preprocessing():
    st.title("🧹 Cleaning & Preprocessing")
    st.markdown("This page is for cleaning and preprocessing (normalization & stemming) data from X.")
    st.write("")

    # --- 1. INISIALISASI DATABASE GLOBAL (Scope aman dari atas) ---
    db_connection_str = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'
    engine = None
    inspector = None
    try:
        engine = create_engine(db_connection_str)
        inspector = inspect(engine)
    except Exception as e:
        st.error(f"❌ Failed to connect to database: {e}")

    # --- 2. FITUR PILIH SUMBER DATA ---
    sumber_data = st.radio(
        "📁 Select the data source you want to process:", 
        ["🗄️ use 'raw_data_tweet' table", "📄 Upload CSV File"],
        horizontal=True
    )
    
    df_raw = None

    if "raw_data_tweet" in sumber_data:
        if inspector and "raw_data_tweet" in inspector.get_table_names():
            try:
                df_raw = pd.read_sql_table("raw_data_tweet", con=engine)
                st.success(f"📦 Successfully loaded the 'raw_data_tweet' table ({len(df_raw)} rows).")
            except Exception as e:
                st.error(f"❌ Failed to load table: {e}")
        else:
            st.warning("⚠️ The 'raw_data_tweet' table has not been found. Please perform Crawling first.")
            
    elif "Upload" in sumber_data:
        uploaded_file = st.file_uploader("Upload Your CSV File", type=['csv'])
        if uploaded_file is not None:
            try:
                df_raw = pd.read_csv(uploaded_file)
                st.success(f"📦 CSV file successfully loaded '{uploaded_file.name}' ({len(df_raw)} rows).")
            except Exception as e:
                st.error(f"❌ Failed to read the CSV file: {e}")
        else:
            st.info("Please upload a CSV file to continue.")

    # --- 3. PREVIEW & EKSEKUSI (Pakai IF, TANPA 'return' liar) ---
    if df_raw is not None and not df_raw.empty:
        with st.expander("File Preview"):
            st.dataframe(df_raw.head())

        st.write("---")
        st.caption("⚙️ Parameter Settings")
        
        min_kata = st.number_input("Minimum Word Count", min_value=1, max_value=20, value=3)

        filename_backup = st.text_input(
            "Filename (For Local CSV Backup)",
            placeholder="ex fiony_clean",
            help="The data will be saved in the 'preprocessing_data_tweet' table. This is only for naming the .csv file."
        )

        # --- TOMBOL EKSEKUSI PREPROCESSING ---
        if st.button("🧹 Clean & Preprocess", type="primary"):
            with st.spinner("Cleaning, Tokenizing, Stemming in progress, please wait..."):
                start_time = time.time()
                
                kolom_teks_target = "full_text" if "full_text" in df_raw.columns else df_raw.columns[0]
                
                # Eksekusi pipeline NLP
                df_hasil = jalankan_pipeline(df=df_raw, kolom_target=kolom_teks_target, min_kata=min_kata)
                
                if 'stemmed' in df_hasil.columns:
                    df_hasil['final_text'] = df_hasil['stemmed'].apply(lambda x: " ".join(x) if isinstance(x, list) else x)

                end_time = time.time()

            # --- TAMPILKAN METRIK ---
            st.subheader("📈 Filtering & Cleaning Results")
            col_met1, col_met2, col_met3 = st.columns(3)
            with col_met1:
                st.metric("Before", len(df_raw))
            with col_met2:
                st.metric("After", len(df_hasil))
            with col_met3:
                st.metric("Discarded (Word & Language Filter)", len(df_raw) - len(df_hasil))
            
            st.success(f"✅ Cleaning, Tokenizing, Stemming completed in {round(end_time - start_time, 2)} seconds!")

            # --- SIMPAN OTOMATIS KE MARIADB/MYSQL ---
            df_sql = df_hasil.copy()
            for col in df_sql.columns:
                df_sql[col] = df_sql[col].apply(lambda x: str(x) if isinstance(x, list) else x)

            if engine:
                try:
                    df_sql.to_sql(name='preprocessing_data_tweet', con=engine, if_exists='replace', index=False)
                    st.success("✅ The data has been inserted into the 'preprocessing_data_tweet' table!")
                except Exception as e:
                    st.error(f"❌ Failed to connect to the database: {e}")

            # --- BACKUP CSV LOKAL ---
            if filename_backup.strip():
                nama_aman_csv = filename_backup.replace(" ", "_").lower()
                os.makedirs("processed-data", exist_ok=True)
                path_output = f"processed-data/{nama_aman_csv}.csv"
                df_hasil.to_csv(path_output, index=False)
                st.success(f"💾 Saved Locally: {path_output}")

            # --- PREVIEW HASIL AKHIR ---
            st.subheader("📋 Final Result Preview")
            kolom_tampil = ["time_slot", "waktu_crawl", kolom_teks_target, "final_text"]
            kolom_ada = [k for k in kolom_tampil if k in df_hasil.columns]
            st.dataframe(df_hasil[kolom_ada].head(10))

            # --- TOMBOL DOWNLOAD CSV PREPROCESSING ---
            if filename_backup.strip():
                nama_file_download = f"{filename_backup.replace(' ', '_').lower()}.csv"
            else:
                nama_file_download = "preprocessing_data_tweet.csv"
                
            csv_string = df_hasil.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV Preprocessing",
                data=csv_string,
                file_name=nama_file_download,
                mime="text/csv"
            )

    # ==========================================================
    # BLOK COUNTER & TOMBOL HAPUS DATA (DI PALING BAWAH TERLAKSANA EKSPLISIT)
    # ==========================================================
    st.write("---")
    count_prep = 0
    
    if engine and inspector:
        try:
            if "preprocessing_data_tweet" in inspector.get_table_names():
                query_prep = "SELECT COUNT(*) as jml_prep FROM preprocessing_data_tweet"
                df_prep_count = pd.read_sql(query_prep, con=engine)
                count_prep = int(df_prep_count['jml_prep'].iloc[0])
        except Exception:
            pass

    col_counter, col_hapus = st.columns([5, 1])

    with col_counter:
        st.write(f"**Status Database:** `{count_prep}` baris data tersimpan di tabel 'preprocessing_data_tweet'")

    with col_hapus:
        if st.button("🗑️ Delete Data", type="secondary", use_container_width=True, key="btn_hapus_prep_bottom"):
            if engine:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM preprocessing_data_tweet"))
                    st.success("✅ All 'preprocessing_data_tweet' data has been successfully deleted!")
                    time.sleep(2) 
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to delete data: {e}")
            else:
                st.error("❌ Database connection is not available.")


# ==============================================================================
# 1. LOAD MODEL HUGGING FACE (CACHED BISA LEBIH CEPAT)
# ==============================================================================
@st.cache_resource
def load_ner_model():
    # Menggunakan model NER khusus Bahasa Indonesia yang stabil
    return pipeline("ner", model="cahya/bert-base-indonesian-NER", aggregation_strategy="simple")

try:
    ner_pipeline = load_ner_model()
except Exception as e:
    ner_pipeline = None
    st.error(f"Failed to load Hugging Face model: {e}")


# ==============================================================================
# 2. FUNGSI PEMBANTU BN-GRAMS & NER
# ==============================================================================
def buat_ngrams(teks, n):
    if not isinstance(teks, str) or not teks.strip():
        return []
    tokens = teks.split()
    if len(tokens) < n:
        return []
    return [" ".join(gram) for gram in ngrams(tokens, n)]

def deteksi_ner_dan_boost(teks):
    if not isinstance(teks, str) or not teks.strip() or ner_pipeline is None:
        return [], 1.0 # Default boost 1.0 kalau tidak ada entitas
    
    try:
        hasil = ner_pipeline(teks)
    except Exception:
        return [], 1.0
        
    entitas = []
    boost_val = 1.0
    
    for ent in hasil:
        label = ent.get('entity_group', '')
        word = ent.get('word', '')
        
        # Saring entitas orang, lokasi, atau organisasi
        if label in ['PER', 'LOC', 'ORG']:
            # BERSIHKAN ARTIFAK MESIN BERT BIAR RAPI DI UI
            word_bersih = word.replace('##', '').strip()
            
            # Abaikan kalau cuma sisa karakter kosong atau simbol doang
            if len(word_bersih) > 1 and word_bersih != "@": 
                entitas.append(f"{word_bersih} ({label})")
            
            boost_val = 1.5 
            
    # Hapus duplikat (biar kalau "Jakarta" kedeteksi dua kali, ditampilinnya sekali aja)
    entitas_unik = list(set(entitas))
            
    return entitas_unik, boost_val

# ==============================================================================
# 3. HALAMAN UTAMA BN-GRAMS
# ==============================================================================
def halaman_bngram():
    st.title("📊 Ekstraksi BN-Grams & NER (Hugging Face)")
    st.markdown("This page is for extracting Bigrams & Trigrams, as well as detecting NER using Hugging Face to determine the Boost Value (1.5).")

    st.write("")

    if ner_pipeline is None:
        st.error("⚠️ NER model failed to load. Check the terminal for Hugging Face errors.")
        return

    # --- 1. INISIALISASI KONEKSI DATABASE DI AWAL (Biar scope 'engine' & 'inspector' aman) ---
    db_connection_str = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'
    engine = None
    inspector = None
    try:
        engine = create_engine(db_connection_str)
        inspector = inspect(engine)
    except Exception as e:
        st.error(f"❌ Failed to connect to the database: {e}")

    # --- 2. FITUR PILIH SUMBER DATA ---
    sumber_data = st.radio(
        "📁 Select the data source you want to process:", 
        ["🗄️ Use 'preprocessing_data_tweet' table", "📄 Upload CSV File"],
        horizontal=True
    )
    
    df_prep = None

    # Opsi A: Tarik dari Database
    if "table" in sumber_data:
        if inspector and "preprocessing_data_tweet" in inspector.get_table_names():
            try:
                df_prep = pd.read_sql_table("preprocessing_data_tweet", con=engine)
                st.success(f"📦 Successfully loaded clean data from 'preprocessing_data_tweet' ({len(df_prep)} rows).")
            except Exception as e:
                st.error(f"❌ Failed to load table: {e}")
        else:
            st.warning("⚠️ The 'preprocessing_data_tweet' table has not been found. Please perform Preprocessing first.")
            
    # Opsi B: Upload CSV Sendiri
    elif "Upload" in sumber_data:
        uploaded_file = st.file_uploader("Upload your preprocessed CSV file", type=['csv'])
        if uploaded_file is not None:
            try:
                df_prep = pd.read_csv(uploaded_file)
                st.success(f"📦 Successfully loaded CSV file '{uploaded_file.name}' ({len(df_prep)} rows).")
            except Exception as e:
                st.error(f"❌ Failed to read CSV file: {e}")
        else:
            st.info("Please upload a CSV file to continue.")

    # --- 3. PREVIEW & EKSEKUSI (Cuma jalan kalau df_prep terisi) ---
    if df_prep is not None and not df_prep.empty:
        with st.expander("View Loaded Data Preview"):
            st.dataframe(df_prep.head(10))

        st.write("---")

        # Tombol Eksekusi BN-Grams
        if st.button("🧮 BN-Grams & NER Extraction", type="primary"):
            kolom_teks = 'final_text' if 'final_text' in df_prep.columns else (
                         'full_text' if 'full_text' in df_prep.columns else None)
            
            if not kolom_teks:
                st.error("❌ No processable text column found (final_text / full_text).")
            elif 'full_text' not in df_prep.columns or 'final_text' not in df_prep.columns:
                st.error("The data must have a 'full_text' column (for NER) and a 'final_text' column (for n-grams). Pastikan CSV/tabel lu sesuai.")
            else:
                with st.spinner("Extracting Bigrams, Trigrams, and detecting Entities via Hugging Face in progress, please wait..."):
                    df_bngram = df_prep.copy()

                    df_bngram['bigrams'] = df_bngram['final_text'].apply(lambda x: buat_ngrams(str(x), 2))
                    df_bngram['trigrams'] = df_bngram['final_text'].apply(lambda x: buat_ngrams(str(x), 3))

                    hasil_ner = df_bngram['full_text'].apply(lambda x: deteksi_ner_dan_boost(str(x)))
                    df_bngram['ner_tags'] = hasil_ner.apply(lambda x: x[0])
                    df_bngram['boost_value'] = hasil_ner.apply(lambda x: x[1])

                st.success("✅ BN-Grams and NER extraction successful!")

                # Simpan otomatis ke MySQL
                df_sql = df_bngram.copy()
                for col in df_sql.columns:
                    df_sql[col] = df_sql[col].apply(lambda x: str(x) if isinstance(x, list) else x)

                try:
                    df_sql.to_sql(name='bngrams_data_tweet', con=engine, if_exists='replace', index=False)
                    st.success("✅ The data has been inserted into the 'bngrams_data_tweet' table!")
                except Exception as e:
                    st.error(f"❌ Failed to save data to database: {e}")

                # Preview Hasil
                st.subheader("📋 Final Result Preview")
                kolom_tampil = [kolom_teks, 'bigrams', 'trigrams', 'ner_tags', 'boost_value']
                kolom_ada = [k for k in kolom_tampil if k in df_bngram.columns]
                st.dataframe(df_bngram[kolom_ada].head(15))
                
                # Download CSV
                csv_string = df_sql.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV BN-Grams",
                    data=csv_string,
                    file_name="hasil_bngrams_ner.csv",
                    mime="text/csv"
                )

    # ==========================================================
    # BLOK COUNTER & TOMBOL HAPUS DATA (ALWAYS RENDER DI PALING BAWAH)
    # ==========================================================
    st.write("---")
    count_bngram = 0
    if inspector and "bngrams_data_tweet" in inspector.get_table_names():
        try:
            query_count = "SELECT COUNT(*) as jml FROM bngrams_data_tweet"
            df_count = pd.read_sql(query_count, con=engine)
            count_bngram = int(df_count['jml'].iloc[0])
        except Exception:
            count_bngram = 0

    col_counter, col_hapus = st.columns([5, 1])

    with col_counter:
        st.write(f"**Status Database:** `{count_bngram}` data rows saved in the 'bngrams_data_tweet' table")

    with col_hapus:
        if st.button("🗑️ Delete Data", type="secondary", use_container_width=True, key="btn_hapus_bngram"):
            if engine:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM bngrams_data_tweet"))
                    st.success("✅ All 'bngrams_data_tweet' data has been successfully deleted!")
                    time.sleep(2) 
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to delete data: {e}")
            else:
                st.error("❌ Database connection is not available.")


def konversi_string_ke_list(teks):
    try:
        if isinstance(teks, str):
            return ast.literal_eval(teks)
        elif isinstance(teks, list):
            return teks
        return []
    except (ValueError, SyntaxError):
        return []

# 2. HALAMAN UTAMA PERANGKINGAN
def halaman_perangkingan():
    st.title("🏆 Perangkingan Topic (BN-Grams)")
    st.markdown("This page calculates Document Frequency (DF) and the final DF-IDFt score based on the formula to find the Top Trending Topic.")
    
    db_connection_str = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'
    engine = None
    try:
        engine = create_engine(db_connection_str)
    except Exception as e:
        st.error(f"❌ Failed to connect to the database: {e}")
        return

    # ==========================================================
    # BLOK COUNTER & TOMBOL HAPUS DATA PERANGKINGAN
    # ==========================================================
    count_rank = 0
    try:
        query_count = "SELECT COUNT(*) as jml FROM perangkingan_data_tweet"
        df_count = pd.read_sql(query_count, con=engine)
        count_rank = int(df_count['jml'].iloc[0])
    except Exception:
        count_rank = 0
    # ==========================================================

    # --- 1. FITUR PILIH SUMBER DATA ---
    st.write("---")
    sumber_data = st.radio(
        "📁 Select the data source you want to process:", 
        ["🗄️ Use 'bngrams_data_tweet' table", "📄 Upload CSV File"],
        horizontal=True
    )
    
    df_bngram = None

    if "table" in sumber_data:
        try:
            inspector = inspect(engine)
            if "bngrams_data_tweet" in inspector.get_table_names():
                df_bngram = pd.read_sql_table("bngrams_data_tweet", con=engine)
                st.success(f"📦 Successfully loaded {len(df_bngram)} data rows from the MySQL table: 'bngrams_data_tweet'.")
            else:
                st.warning("⚠️ Tabel 'bngrams_data_tweet' belum ada di database.")
                return
        except Exception as e:
            st.error(f"❌ Failed to load bngrams table: {e}")
            return

    elif "Upload" in sumber_data:
        uploaded_file = st.file_uploader("Upload the CSV file resulting from your BN-Grams", type=['csv'])
        if uploaded_file is not None:
            try:
                df_bngram = pd.read_csv(uploaded_file)
                st.success(f"📦 Successfully loaded {len(df_bngram)} data rows from the CSV file: '{uploaded_file.name}'.")
            except Exception as e:
                st.error(f"❌ Failed to read the CSV file: {e}")
                return
        else:
            st.info("Please upload a CSV file to continue.")
            return

    # --- 2. PREVIEW DATA AWAL ---
    if df_bngram is not None and not df_bngram.empty:
        with st.expander("View Loaded Data Preview"):
            st.dataframe(df_bngram.head(10))
    else:
        return 

    if not all(col in df_bngram.columns for col in ['bigrams', 'trigrams', 'boost_value']):
        st.error("❌ Invalid data! Please ensure the 'bigrams', 'trigrams', and 'boost_value' columns are present.")
        return

    if 'time_slot' not in df_bngram.columns:
        df_bngram['time_slot'] = 1 
        
    st.write("---")
    
    # --- 3. UI PEMILIHAN TIME SLOT ---
    st.subheader("⚙️ Parameter Settings")
    list_slot = sorted(df_bngram['time_slot'].unique())
    
    target_slot = st.selectbox(
        "Select Target Time Slot (Time Slot ke-i):", 
        list_slot, 
        index=len(list_slot)-1,
        help="The current time slot for which you want to find the trending topics."
    )
    
    # --- 4. TOMBOL EKSEKUSI MATEMATIS ---
    if st.button("🧮 DF-IDFt Score & Ranking", type="primary"):
        with st.spinner("Splitting N-Grams and executing the DF-IDFt formula..."):
            
            df_calc = df_bngram.copy()
            df_calc['bigrams'] = df_calc['bigrams'].apply(konversi_string_ke_list)
            df_calc['trigrams'] = df_calc['trigrams'].apply(konversi_string_ke_list)
            
            df_calc['all_ngrams'] = df_calc['bigrams'] + df_calc['trigrams']
            df_calc['doc_id'] = df_calc.index 
            
            df_exploded = df_calc[['doc_id', 'time_slot', 'all_ngrams', 'boost_value']].explode('all_ngrams')
            df_exploded = df_exploded.dropna(subset=['all_ngrams'])
            df_exploded = df_exploded[df_exploded['all_ngrams'].str.strip() != ""] 
            
            t = len(list_slot) 
            
            df_target = df_exploded[df_exploded['time_slot'] == target_slot]
            df_i_counts = df_target.groupby('all_ngrams')['doc_id'].nunique().reset_index(name='df_i')
            boost_df = df_target.groupby('all_ngrams')['boost_value'].max().reset_index(name='boost')
            
            df_prev = df_exploded[df_exploded['time_slot'] < target_slot]
            if not df_prev.empty:
                df_prev_counts = df_prev.groupby('all_ngrams')['doc_id'].nunique().reset_index(name='sum_df_prev')
            else:
                df_prev_counts = pd.DataFrame(columns=['all_ngrams', 'sum_df_prev'])
                
            hasil_df = pd.merge(df_i_counts, boost_df, on='all_ngrams', how='left')
            hasil_df = pd.merge(hasil_df, df_prev_counts, on='all_ngrams', how='left')
            hasil_df['sum_df_prev'] = hasil_df['sum_df_prev'].fillna(0) 
            
            def hitung_dfidft(row):
                df_i = row['df_i']
                sum_df_prev = row['sum_df_prev']
                boost_val = row['boost']
                
                pembilang = df_i + 1
                penyebut = np.log10((sum_df_prev / t) + 1) + 1 
                return (pembilang / penyebut) * float(boost_val)
                
            hasil_df['skor_dfidft'] = hasil_df.apply(hitung_dfidft, axis=1)
            
            hasil_df = hasil_df.sort_values(by='skor_dfidft', ascending=False).reset_index(drop=True)
            hasil_df.index = hasil_df.index + 1
            hasil_df.index.name = 'Rank'

            # --- 5. SIMPAN OTOMATIS KE DATABASE ---
            try:
                # Ubah index 'Rank' jadi kolom biasa supaya ngga hilang pas masuk MySQL
                hasil_df_sql = hasil_df.reset_index()
                # Tambahin keterangan time_slot-nya di tabel SQL
                hasil_df_sql['time_slot'] = target_slot 
                
                hasil_df_sql.to_sql(name='perangkingan_data_tweet', con=engine, if_exists='replace', index=False)
                st.success("✅ The data has been inserted into the 'perangkingan_data_tweet' table!")
            except Exception as e:
                st.error(f"❌ Failed to save data to database: {e}")
        
        # --- 6. PREVIEW UI HASIL & DOWNLOAD ---
        st.subheader(f"📈 Top Trending Topics (Time Slot {target_slot})")
        st.dataframe(hasil_df.style.format({'skor_dfidft': '{:.2f}'})) 
        
        csv_string = hasil_df.to_csv()
        st.download_button(
            label="📥 Download CSV Rangking",
            data=csv_string,
            file_name=f"trending_rangking_slot_{target_slot}.csv",
            mime="text/csv"
        )
    
    st.write("") 

    col_counter, col_hapus = st.columns([5, 1])
    with col_counter:
        st.write(f"**Status Database:** `{count_rank}` baris hasil rangking tersimpan di tabel 'perangkingan_data_tweet'")

    with col_hapus:
        if st.button("🗑️ Delete Data", type="secondary", use_container_width=True, key="btn_hapus_rangking"):
            try:
                from sqlalchemy import text
                import time
                with engine.begin() as conn:
                    # Hapus isi tanpa menghapus tabel
                    conn.execute(text("DELETE FROM perangkingan_data_tweet"))
                
                st.success("✅ All 'perangkingan_data_tweet' data has been successfully deleted!")
                time.sleep(2) 
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to delete data: {e}")


# Sidebar + Navigation
st.sidebar.title("Navigation")

menu = st.sidebar.radio(
    "Select page:",
    ["Crawling", "Preprocessing", "BN-Grams", "Ranking"]
)

if menu == "Crawling":
    halaman_crawling()
elif menu == "Preprocessing":
    halaman_cleaning_preprocessing()
elif menu == "BN-Grams":
    halaman_bngram()
elif menu == "Ranking":
    halaman_perangkingan()

--- clean-data/databersih.csv ---

conversation_id_str,created_at,favorite_count,full_text,id_str,image_url,in_reply_to_screen_name,lang,location,quote_count,reply_count,retweet_count,tweet_url,user_id_str,username
2110988904904245492,2026-10-16T07:50:00.000Z,0,@LambeSahamjja datengin Prabowo harusnya. stop MBG dan Kopdes,2111001698525466907,,LambeSahamjja,in,,0,0,0,https://x.com/Enkithelord/status/2111001698525466907,1781216713146781696,Enkithelord
2110724349854704080,2026-10-16T07:49:57.000Z,0,@LambeSahamjja Maksutnya br di jaman Prabowo dia bs punya jabatan &amp; hidup enak,2111001687897071620,,LambeSahamjja,in,,0,0,0,https://x.com/erimeureun/status/2111001687897071620,625871632,erimeureun
2111001682889097531,2026-10-16T07:49:56.000Z,0,"🚨🚨SIANG INI TERJADI LAGI🚨🚨
KEBAKARAN HUTAN LAGI dekat Perumahan Mutiara Indah 2 sudah mendekati pemukiman, bagi relawan dan pemadam tolong padamkan SEGERA sebelum KEBAKARAN HUTAN ini meluas dengan cepat

Terjadi di oganilir sorotan Indralaya, Ogan Ilir, Sumatra Selatan.

KEEP https://t.co/5mbmU0T1gF",2111001682889097531,https://pbs.twimg.com/amplify_video_thumb/2111001652580986880/img/HRxDlGb-MPv3L2VJ.jpg,,in,,0,0,0,https://x.com/jenostalker/status/2111001682889097531,1885318915498401796,jenostalker
2111001680301244750,2026-10-16T07:49:55.000Z,0,sok sokan gamau nerima bantuin kaya becus aja lu @prabowo,2111001680301244750,,,in,,0,0,0,https://x.com/findstufhere/status/2111001680301244750,1468067621698359297,findstufhere
2111001665696600571,2026-10-16T07:49:52.000Z,0,Karena literally sudah besar beneran kebakaran nya,2111001665696600571,,,in,,0,0,0,https://x.com/prizuardi/status/2111001665696600571,1337643428729954304,prizuardi
2110996666199220258,2026-10-16T07:49:49.000Z,0,"@saludosparatii Sebenarnya Jokowi ngajak Prabowo masuk kabinet itu gapapa, tapi yg terkesan memaksa itu Jokowi malah mendukung Prabowo jadi presiden. 

Walaupun saat itu sebenernya Jokowi juga akan mendukung Ganjar.",2111001655726719214,,saludosparatii,in,,0,0,0,https://x.com/chris_azura/status/2111001655726719214,3062188777,chris_azura
2110958919744991665,2026-10-16T07:49:37.000Z,0,@kvn_doc Tuhan bersama seluruh WNI yang menderita di rezim Prabowo,2111001605105700933,,kvn_doc,in,,0,0,0,https://x.com/KulinerAftWork/status/2111001605105700933,2106643220532965376,KulinerAftWork
2110990082341761085,2026-10-16T07:49:31.000Z,0,"@abu_waras Geng Solo sdh banyak tersingkir Hakim &amp; Jaksa kok sepertinya masih ketakutan sama Jokowi padahal digaji oleh rakyat, percuma gaji dinaikkan 280% oleh Prabowo agar berani tegakkan keadilan.

""Polisi Bersama Masyarakat"", kapan jaksa &amp; hakim bersama Masyarakat ?",2111001576974520693,,abu_waras,in,,0,0,0,https://x.com/sayno_KKN/status/2111001576974520693,1735636779192233984,sayno_KKN
2111001537011147256,2026-10-16T07:49:21.000Z,0,"Ga ada yang perlu disampaikan.

Langsung aja, prabowo need to get Charlie Kirk treatment.",2111001537011147256,,,in,,0,0,0,https://x.com/NeoPolice25/status/2111001537011147256,1302515107650445312,NeoPolice25
2110696070682669332,2026-10-16T07:49:20.000Z,0,@maxxnxine Tapi ada plotwist ke 2 setelah kemarin gagal fs kak yaitu asap Kalimantan mulai hari ini sdh mulai masuk jakarta jadi GK tau nanti bagaimana berjalan nya FANSIGN Hearts2hearts di JKT. Tetap pake masker aja jaga kesehatan,2111001533672521860,,maxxnxine,in,,0,0,0,https://x.com/Riansyah040215/status/2111001533672521860,1923285244427501568,Riansyah040215
2110958471315406907,2026-10-16T07:49:10.000Z,0,@jeajezz mirip di kalimantan jir sampe 38,2111001488936128561,,jeajezz,in,,0,0,0,https://x.com/shikerei/status/2111001488936128561,1237868566503923712,shikerei
2110961240633639282,2026-10-16T07:49:07.000Z,0,@kumparan Setuju. Cari perusahaan yang bertanggungjawab atas kebakaran hutan. Boycott produk²nya dan bekukan asset² mereka yang di Singapura.,2111001478685143146,,kumparan,in,,0,0,0,https://x.com/toocool711/status/2111001478685143146,207065595,toocool711
2111001437304213848,2026-10-16T07:48:57.000Z,1,"Padahal Udara itu gratis tapi negara ini gagal memfasilitasi warga warga nya 
🥀🥀🥀

@DPR_RI @prabowo 

#IndonesiaButuhOksigen😷 https://t.co/NvS8FNmOiY",2111001437304213848,https://pbs.twimg.com/media/HUvIncHbcAAfkd5.jpg,,in,,0,0,0,https://x.com/dvnadrlprmdya/status/2111001437304213848,1667124436657672194,dvnadrlprmdya
2110987375522549914,2026-10-16T07:48:57.000Z,0,@Alitt4mb3ng @prabowo Lah kok 😀😀😀😀 padahal preman,2111001434355360022,,Alitt4mb3ng,in,,0,0,0,https://x.com/Hiugundul/status/2111001434355360022,1703670621622710272,Hiugundul
2110997554444030245,2026-10-16T07:48:56.000Z,0,"@BarisanOpOsisi @prabowo SEMOGA AMANAH MEMIMPIN NEGERI INI
SEMOGA DIA TIDAK AKAN MELANGGAR JANJINYA SEBAGAI MANTAN PRAJURIT, DAN TIDAK MELANGGAR  SUMPAH SEBAGAI PRESIDEN!

#BRAVO1986",2111001430127792591,,BarisanOpOsisi,in,,0,0,0,https://x.com/a999on/status/2111001430127792591,2041804213986951168,a999on
2111001266390552661,2026-10-16T07:48:17.000Z,0,sedih gak lu indo masuk shoshibuya dengan cara kek gini kwkwkw. @prabowo gblk,2111001266390552661,,,in,,0,0,0,https://x.com/zerunemui/status/2111001266390552661,2090048654702956544,zerunemui
2111001265786528207,2026-10-16T07:48:16.000Z,0,"Yah pinter banget. Kocak. Bom diledakin di tempat tertutup kayak gua gitu ya kekuatan ledakannya berlipat ganda lah. Pantesan lab Life Spiral kebakaran

Pas liat Ogier bilang 11 tahun lalu aku udah nebak ada hubungannya sama kebakaran 11 tahun lalu, tapi ga expect alasannya ini https://t.co/YvFrEynwXG",2111001265786528207,https://pbs.twimg.com/media/HUvIIz3aoAAyaBB.jpg,,in,,0,1,0,https://x.com/el_ktnk_lon/status/2111001265786528207,1333079502264492033,el_ktnk_lon
2111001254046642453,2026-10-16T07:48:14.000Z,0,guys SURPRISE in prabowo yok besok dia ultah nih🤩 mau diramein di istana negara apa di rumah hambalang pak,2111001254046642453,,,in,,0,0,0,https://x.com/UTDYoda_/status/2111001254046642453,1794520397330907136,UTDYoda_
2111001249718075758,2026-10-16T07:48:13.000Z,0,"Ini si wowok di tanya apa jawab apa, Kalimantan tuh gaada hubungannya sama Ring of fire ya anjirt, Instead bilang maaf dan akan menangani dengan baik, dia malah ngomong yg ga nyambung 💔 https://t.co/miqJR1rH8T",2111001249718075758,https://pbs.twimg.com/amplify_video_thumb/2111001208144175104/img/KhxiQSlyo4tBk5Ff.jpg,,in,,0,0,0,https://x.com/flllowiee/status/2111001249718075758,1584671789459701760,flllowiee
2111001234803220516,2026-10-16T07:48:09.000Z,0,"Padahal baru gak ada seminggu aku lewat sini tumbuhan gangang dan enceng gondoknya belum sebanyak ini loh.

Hari ini aku lewat udah full menutupi kali (lebih tepatnya aku sebut ini paceran). 
Ada satu tumbuhan kaya lumut, itu yang kecil-kecil gak tau nama pastinyaaa tapi https://t.co/Olp9NqyaG5",2111001234803220516,https://pbs.twimg.com/amplify_video_thumb/2111001146626281472/img/UhetRfSe2jfeiIb2.jpg,,in,,0,0,0,https://x.com/_prabowo88/status/2111001234803220516,52935312,_prabowo88
2111001233574252798,2026-10-16T07:48:09.000Z,0,"Ada hubungan dengan: Kantor ATR/BPN Kabupaten Karawang, Jawa Barat, mengalami kebakaran hebat pada Rabu malam, 14 Oktober 2026.
Sekitar pukul 22.00–23.10 WIB, Gudang arsip sekitar 70%. Dokumen: Semua sertifikat SHM (Sertifikat Hak Milik) dilaporkan ludes/habis terbakar.",2111001233574252798,,,in,,0,0,0,https://x.com/WidhiLawan/status/2111001233574252798,1918479126803169281,WidhiLawan
2111001232265617443,2026-10-16T07:48:08.000Z,0,Prabowo kapan mati?,2111001232265617443,,,in,,0,0,0,https://x.com/hime_anjai/status/2111001232265617443,2078500844459483136,hime_anjai
2110980056252301775,2026-10-16T07:48:08.000Z,0,@lelucone Aku harap semoga aja prabowo juga Anjlok Nyai,2111001229329592796,,lelucone,in,,0,0,0,https://x.com/restafajri/status/2111001229329592796,720245756,restafajri
2110917019843654112,2026-10-16T07:48:05.000Z,0,"@Saham_fess Good aja sih. Yg ngeluh2 gitu biasanya karena rugi judi di saham.  Udah tau antek2 asing lagi gencar2nya nyerang indo karena patriotiknya Pak Prabowo. Eh rakyatnya malah nyerang pemerintah. Aneh banget. Mending dukung pemerintah. Prabowo 2 periode pokoknya, ga mau tau!",2111001219556954231,,Saham_fess,in,,0,1,0,https://x.com/oxsakaSKY/status/2111001219556954231,1873699410103914496,oxsakaSKY
2111001196945416209,2026-10-16T07:48:00.000Z,0,Minat bgt Kalimantan ini di ambil Singapore 🙏,2111001196945416209,,,in,,0,0,0,https://x.com/ecrivain_rin/status/2111001196945416209,1805106620902572032,ecrivain_rin
2110303347458609293,2026-10-16T07:47:53.000Z,0,"@pw_gun kenapa alat pelaku ditinggal di pinggir jalan? kan bisa dilempar ke api.. kan TOLOL..
ATAU
 memang sengaja ditaruh di tempat yg aman dari api supaya bisa ditemukan utuh oleh petugas lapangan untuk membentuk opini kalau kebakaran bukan disebabkan oleh perusahaan sawit saja?😏",2111001168185069592,,pw_gun,in,,0,0,0,https://x.com/JLAPS15/status/2111001168185069592,135828208,JLAPS15
2111001143958716876,2026-10-16T07:47:47.000Z,0,"Aku rela di daerah sini jarang ujan asal api di Kalimantan cepet padam 😔 

Jangan sampe kekeringan juga sih di sini 😭☝️ balance aja deh. Tapi utamanya biar warga Kalimantan pada bisa menghirup udara segar",2111001143958716876,,,in,,0,0,0,https://x.com/huaot/status/2111001143958716876,1172443332,huaot
2110949246543511995,2026-10-16T07:47:44.000Z,0,@jayidzes @prabowo sehidup semati semaki maki prabowo kontol,2111001130839036380,,jayidzes,in,,0,0,0,https://x.com/surgaca/status/2111001130839036380,1857814846156451842,surgaca
2111001129052242020,2026-10-16T07:47:44.000Z,0,"Dua tahun pemerintahan Prabowo Subianto - Gibran Rakabuming Raka membawa Indonesia pada swasembada pangan, target empat tahun yang tercapai hanya dalam satu tahun. 

#GarudaMerah
#2TahunGerakNyata
#BadanKomunikasiPemerintah https://t.co/KiflBxGCut",2111001129052242020,https://pbs.twimg.com/amplify_video_thumb/2111000504511979521/img/kdwhiB0OnMcgF9M5.jpg,,in,,0,1,0,https://x.com/GARUDAMERAH__/status/2111001129052242020,869958008251367424,GARUDAMERAH__
2110768683018801341,2026-10-16T07:47:43.000Z,0,@Thebiglade kebakaran hutan,2111001123901632918,,Thebiglade,in,,0,0,0,https://x.com/tendanganpetir/status/2111001123901632918,51109056,tendanganpetir
2111001104490340601,2026-10-16T07:47:38.000Z,1,"Demi allah pingin nangis, kenapa sih prabowo jadi presiden. Kenapa sih orang2 jahat jadi pejabat. Kenapa sih orang kaya yg punya akses pendidikan tinggi ujung2nya memelintir orang bodoh dan miskin di bawahnya. Kenapa dunia berasa makin gak layak buat di huni😭",2111001104490340601,,,in,,0,0,0,https://x.com/bbymoonstruck/status/2111001104490340601,2062727039308972032,bbymoonstruck
2111001068171878886,2026-10-16T07:47:29.000Z,0,prabowo goblok bgt ye ternyata,2111001068171878886,,,in,,0,0,0,https://x.com/hilmisworo/status/2111001068171878886,894599668096684032,hilmisworo
2111001067336892615,2026-10-16T07:47:29.000Z,0,Prabowo Gibran dan kreni-kreninya next,2111001067336892615,,,in,,0,0,0,https://x.com/gdl_is/status/2111001067336892615,1244213097482424323,gdl_is
2110594634254561594,2026-10-16T07:47:14.000Z,0,"@kabjagyi Alaah.. Masyarakat kalimantan malah lbh parah,minta simpati rakyatkah?",2111001003713810923,,kabjagyi,in,,0,0,0,https://x.com/IwanGun5611250/status/2111001003713810923,1742044141713055744,IwanGun5611250
2111000930137395665,2026-10-16T07:46:56.000Z,0,Hadiah terbaik untuk ulang tahun prabowo adalah guillotine🤩,2111000930137395665,,,in,,0,0,0,https://x.com/tylersnewbae/status/2111000930137395665,62237246,tylersnewbae
2111000926865838486,2026-10-16T07:46:56.000Z,0,Sakit tekak ni cam takde tanda nak baik je. Esok tak tahulah jadi ke tak pegi konsert nya. Dah lah sekarang asyik hujan petang je. Nak kena bawa baju hujan pulak esok. Ni semua salah @prabowo,2111000926865838486,,,in,,0,0,0,https://x.com/nurqzfrh/status/2111000926865838486,1739301203539042304,nurqzfrh
2111000917533405473,2026-10-16T07:46:53.000Z,0,prabowo bangsat muatan gw kena imbas solar anjing goblok presiden gak guna gw sebel bgt anjg,2111000917533405473,,,in,,0,0,0,https://x.com/quietquitquite/status/2111000917533405473,1576244960177053696,quietquitquite
2110974182607745168,2026-10-16T07:46:53.000Z,0,@minjilalala grgr prabowo,2111000915696304364,,minjilalala,in,,0,0,0,https://x.com/orchidiey/status/2111000915696304364,1801045591503536128,orchidiey
2111000912978378781,2026-10-16T07:46:52.000Z,0,Karhutla Kalimantan ada kaitannya dengan Malaysia dan Singapur https://t.co/jr0rzQJJM3,2111000912978378781,https://pbs.twimg.com/amplify_video_thumb/2111000456956964864/img/Vsohjj0VJX3SGa4o.jpg,,in,,0,0,0,https://x.com/anak_indigo99/status/2111000912978378781,1927633754379735040,anak_indigo99
2110795759239221414,2026-10-16T07:46:51.000Z,1,"@indepenSumatera selamat anda kena hujat,  sepong terus bjii prabowo, iri kok ama swasta 😹 https://t.co/NcuSO12bV4",2111000908268249402,https://pbs.twimg.com/media/HUvIIrdboAAuEO5.jpg,indepenSumatera,in,,0,0,0,https://x.com/kakei_jun/status/2111000908268249402,1784026799711887361,kakei_jun
2110652375434478019,2026-10-16T07:46:46.000Z,0,@BANGSAygSUJUD Halah gua orang Kalbar.. tepatnya di kabupaten Ketapang ..selama kebakaran mana ada heli heli gini..relawan semua yg turun,2111000884754940356,,BANGSAygSUJUD,in,,0,0,0,https://x.com/Senju73123708/status/2111000884754940356,1517130312815628288,Senju73123708
2110716587074531395,2026-10-16T07:46:33.000Z,0,@mortaliel kemayu banget loh ya buna,2111000830841381114,,mortaliel,in,,0,0,0,https://x.com/Xdevilhun/status/2111000830841381114,1298490649419759617,Xdevilhun
2111000824113762544,2026-10-16T07:46:31.000Z,0,"Bakar aja istana negara sama gedung dpr + seluruh isinya. Laknat emang, manusia di sana pantes mati. Ga cukup warga negara sendiri, warga negara luar pun harus kena imbasnya. Minta kompensasi juga nanti pake duit pajak. Prabowo bangsat.",2111000824113762544,,,in,,0,0,0,https://x.com/monyetwtf/status/2111000824113762544,1332891499323744256,monyetwtf
2111000817818046790,2026-10-16T07:46:30.000Z,0,"Repost @kementerian.atrbpn

PENGUMUMAN LAYANAN PERTANAHAN KABUPATEN KARAWANG

Sehubungan dengan musibah kebakaran yang terjadi di Kantor Pertanahan Kabupaten Karawang pada Rabu, 14 Oktober 2026, kami memohon maaf kepada seluruh masyarakat atas gangguan dan ketidaknyamanan https://t.co/yHx88us2zo",2111000817818046790,https://pbs.twimg.com/media/HUvIBbzbIAEHDGB.jpg,,in,,0,0,0,https://x.com/atrbpnsumut/status/2111000817818046790,970842441812029441,atrbpnsumut
2110378014773297573,2026-10-16T07:46:27.000Z,0,@nyepamaja @prabowo celeng kuadrattt,2111000804819894699,,nyepamaja,in,,0,0,0,https://x.com/arfawkwk/status/2111000804819894699,1070666149707231232,arfawkwk
2111000771097763984,2026-10-16T07:46:18.000Z,0,"sangat NORMAL tuh

#bnpb #kalimantan #beritaterkini https://t.co/sRG9BxltbY",2111000771097763984,https://pbs.twimg.com/amplify_video_thumb/2111000738260484096/img/KLbLCzyIT3-fJVPJ.jpg,,in,,0,0,0,https://x.com/langitsenayan/status/2111000771097763984,1939894464094613504,langitsenayan
2111000735530061937,2026-10-16T07:46:11.000Z,0,"Lomba Seleksi Khusus

Hari, Tanggal: Kamis, 17 Desember 2026
Waktu: 14:00 - 17:00 WIB Tempat: Daring (Zoom)
Periode Pendaftaran: 
Jumat, 16 Oktober 2026 - Senin, 30 November 2026

Link pendaftaran dan pedoman : https://t.co/hvcFCXOqmF (tautan di bio)

※ Seleksi Khusus bagi https://t.co/ZaeGOZpfpu",2111000739137065404,https://pbs.twimg.com/media/HUvH3webEAE_W_v.jpg,JF_Jakarta,in,,0,0,0,https://x.com/JF_Jakarta/status/2111000739137065404,296111529,JF_Jakarta
2111000721370046677,2026-10-16T07:46:07.000Z,0,"Mangsa terperangkap dalam kepungan api dan asap tebal semasa operasi memadam kebakaran.

https://t.co/6kurI8TfHg

Yang sahih di RTM'
#RTM #BeritaRTM #MalaysiaMadani #TaatSetia #BersamaMALAYSIAKU #RancakkanMADANI #MADANIBekerja https://t.co/GUsukGMpZe",2111000721370046677,https://pbs.twimg.com/media/HUvH1UtbgAAPd5K.jpg,,in,,0,0,0,https://x.com/beritartm/status/2111000721370046677,704725700,beritartm
2110978131360412103,2026-10-16T07:45:54.000Z,0,"@menanti94297 @idextratime Good aja sih. Yg ngeluh2 gitu biasanya karena rugi judi di saham.  Udah tau antek2 asing lagi gencar2nya nyerang indo karena patriotiknya Pak Prabowo. Eh rakyatnya malah nyerang pemerintah. Aneh banget. Mending dukung pemerintah. Prabowo 2 periode pokoknya, ga mau tau!",2111000669113225382,,menanti94297,in,,0,0,0,https://x.com/oxsakaSKY/status/2111000669113225382,1873699410103914496,oxsakaSKY
2110996545013440894,2026-10-16T07:45:47.000Z,0,@cariaeosa Semoga di waraskan otaknya Prabowo,2111000640583536683,,cariaeosa,in,,0,0,0,https://x.com/restafajri/status/2111000640583536683,720245756,restafajri
2110639859568349211,2026-10-16T07:45:45.000Z,0,"@BANGSAygSUJUD Malu paman, sama namanya, BANGSA YANG SUJUD
Malu sama SUJUD paman
Malu sama ilmu paman
Malu sama agama paman
Malu sama RAKYAT INDONESIA WABIL KHUSUS RAKYAT KALIMANTAN DAN SUMATERA YG TERKENA MUSIBAH KEBAKARAN HUTAN
ingat KETIKAN PAMAN AKAN DIMINTAIN PERTANGGUNGJAWABAN DI AKHIRAT!",2111000629883887757,,BANGSAygSUJUD,in,,0,0,0,https://x.com/samar_wulu/status/2111000629883887757,1422108749959864323,samar_wulu
2110982067567947944,2026-10-16T07:45:44.000Z,0,"@papavilenn bener om, bukan cuma kalimantan sm sumatra saja",2111000626624967034,,papavilenn,in,,0,0,0,https://x.com/buburrayam12/status/2111000626624967034,235555503,buburrayam12
2111000611764523448,2026-10-16T07:45:40.000Z,0,"buzzer2 prabowo, klian smua taiiiii",2111000611764523448,,,in,,0,0,0,https://x.com/vinsensiasps/status/2111000611764523448,2938257301,vinsensiasps
2111000604676128945,2026-10-16T07:45:39.000Z,0,"Salut buat polisi yg gercep bantu warga saat kebakaran di Duri Kosambi

#Polri #PolriBersamaMasyarakat #FYP #polisiindonesia https://t.co/0LcJeZrCIz",2111000604676128945,https://pbs.twimg.com/amplify_video_thumb/2111000566159794177/img/4RX66Dsh4g0BQDbK.jpg,,in,,0,0,0,https://x.com/SuryanaWis83893/status/2111000604676128945,1701075217999962112,SuryanaWis83893
2111000590595903984,2026-10-16T07:45:35.000Z,20,giliran gini pada kompak sama tetangga😆😆😆😆 https://t.co/Yd22I1ACtg,2111000590595903984,https://pbs.twimg.com/media/HUvH2B_bQAAzSaT.jpg,,in,,0,7,2,https://x.com/unmagnetism/status/2111000590595903984,843269533930405888,unmagnetism
2111000578512019786,2026-10-16T07:45:33.000Z,0,"14:49 Halo min mau melaporkan alhamdulillah di Kalimantan Tengah kota Waringin lama sudah hujan, semoga jogja dan sekitarnya juga ada hujan, dan biar tidak kepanasan lagi aminn

#Merapiuncover #Merapinews #Merapi
masresa_28 https://t.co/EqvQri6tHV",2111000578512019786,https://pbs.twimg.com/amplify_video_thumb/2111000557481799680/img/ruIuNzaI9Nw-DQJb.jpg,,in,,0,0,0,https://x.com/merapi_uncover/status/2111000578512019786,1279804428724211712,merapi_uncover
2110930759519518840,2026-10-16T07:45:31.000Z,0,"@Ndrewstjan Prabowo tidak meminta maaf karena 2014 atau 2019. Ia memanfaatkan politik agama dan menyulut narasi divisive hingga menciptakan kerusuhan. Ia tidak pernah minta maaf. Saya sudah menolak dia 3 kali, tapi Jokowi memungut dia bagaikan sampah untuk jadi Menhan.",2111000569867296840,,Ndrewstjan,in,,0,0,0,https://x.com/LebakBulusLRT/status/2111000569867296840,1641703807251025921,LebakBulusLRT
2111000562254975308,2026-10-16T07:45:29.000Z,0,"Juru Bicara PDI-Perjuangan, Seno Bagaskoro, menyampaikan pandangannya terkait krisis kebakaran hutan dan lahan yang melanda wilayah Kalimantan, Riau, serta beberapa daerah di Indonesia dalam beberapa pekan terakhir. 

Dampak asap tebal dilaporkan telah mengganggu kesehatan warga, https://t.co/6vbu3Fe5KE",2111000562254975308,https://pbs.twimg.com/amplify_video_thumb/2111000320021262336/img/KPIsFUS9fDrfXjpk.jpg,,in,,0,0,0,https://x.com/kompascom/status/2111000562254975308,23343960,kompascom
2110563006493172070,2026-10-16T07:45:21.000Z,0,@pendekar_kalcer Semoga petugas di lapangan selalu diberi kelancaran dan kebakaran bisa segera teratasi 🤝,2111000528742420522,,pendekar_kalcer,in,,0,0,0,https://x.com/aciladewi955/status/2111000528742420522,2014648557543071744,aciladewi955
2111000507993280886,2026-10-16T07:45:16.000Z,0,"Jangan susah susah kalau dinasehatin, tolong hentikan kebijakan yg cuma nyusahin dan gak bermanfaat buat rakyat, terakhir coba turun ke lapangan yg terdampak bencana secara langsung &amp; pikirkan solusinya dengan baik, bukan hanya mendapat laporan &amp; tanya program gaje itu! @prabowo",2111000507993280886,,,in,,0,0,0,https://x.com/Fakhri270797/status/2111000507993280886,1561231966313525248,Fakhri270797
2111000491320844634,2026-10-16T07:45:12.000Z,0,"bener-bener gak bisa mikir, apa sih kebaikan/bagusnya prabowo sedikit aja? mau ngeanjing-anjingin si eta lebih kasian anjingnya disetarain sama orang itu🥲",2111000491320844634,,,in,,0,0,0,https://x.com/hardtoseeasily_/status/2111000491320844634,1217458764682448896,hardtoseeasily_
2111000486623220038,2026-10-16T07:45:11.000Z,0,"Semoga pengusutan kebakaran ini berjalan transparan dan hasilnya segera diketahui

#KampungAmbon #PolsekTambora #JakartaBarat #polribersamamasyarakat https://t.co/PhVKggQMXO",2111000486623220038,https://pbs.twimg.com/media/HUvHwDtbQAA9gdi.jpg,,in,,0,0,0,https://x.com/andrekusnadii/status/2111000486623220038,1699669980579872768,andrekusnadii
2111000440590729504,2026-10-16T07:45:00.000Z,0,"Prabowo akan Kumpulkan Menteri-Wamen di Istana Bogor Malam Ini

https://t.co/OClEuvnVjq",2111000440590729504,,,in,,0,0,0,https://x.com/TirtoID/status/2111000440590729504,4187275698,TirtoID
2111000423696109614,2026-10-16T07:44:56.000Z,0,Prabowo mundur lo anjing!!!!!!! https://t.co/rPnzIJOOuo,2111000423696109614,https://pbs.twimg.com/media/HUvHfo9aoAA0OFc.jpg,,in,,0,0,0,https://x.com/hendra_balikin/status/2111000423696109614,2166281996,hendra_balikin
2111000395866886553,2026-10-16T07:44:49.000Z,1,Dan gw adalah salah satu korban gempa lombok 2018 yg alhamdulillah selamat itu. Sedikit fun fact berapa kali kali prabowo nyalon vs jokowi dulu waktu pilpres di lombok selalu gede dukungannya si Prabowo ini dan jeng jeng jeng eh kejadian bencana pas jokowi jd presiden (jagoan yg https://t.co/a66cP585mb,2111000395866886553,https://pbs.twimg.com/amplify_video_thumb/2111000338933432320/img/j4eOG77GkyeiqWTQ.jpg,,in,,0,0,0,https://x.com/naturemood_/status/2111000395866886553,1623987941201842176,naturemood_
2110946359037870138,2026-10-16T07:44:47.000Z,0,@youngmasterjcw @MiskinTV_ Tapi yg diliat disitu bukan cuma Kalimantan aja deh karena peta Sulawesi juga kayak sdh menyatu dengan Kalimantan dan ditulis Singapore,2111000389189562626,,youngmasterjcw,in,,0,0,0,https://x.com/Riansyah040215/status/2111000389189562626,1923285244427501568,Riansyah040215
2111000386312278383,2026-10-16T07:44:47.000Z,0,"Perdana Menteri Singapura, Lawrence Wong, berkata pihaknya sedang mengenal pasti syarikat yang mungkin terbabit dalam kebakaran berkenaan.

https://t.co/nLRnFXJXXI

Yang sahih di RTM'
#RTM #BeritaRTM #MalaysiaMadani #TaatSetia #BersamaMALAYSIAKU #RancakkanMADANI #MADANIBekerja https://t.co/MRkJdphmiz",2111000386312278383,https://pbs.twimg.com/media/HUvHidEaMAAWV0g.jpg,,in,,0,0,0,https://x.com/beritartm/status/2111000386312278383,704725700,beritartm
2110954676627595493,2026-10-16T07:44:44.000Z,0,"@txtdrimedia stop ngomong kebakaran hutan, itu pembakaran hutan.",2111000375751024736,,txtdrimedia,in,,0,0,0,https://x.com/Bucha63473312/status/2111000375751024736,1158903222578212864,Bucha63473312
2111000362433868165,2026-10-16T07:44:41.000Z,0,"and also waktu itu aku lagi hts an sm cowo ilpol, thanks to him aku jadi punya banyak pengetahuan kenapa ga pilih prabowo hihi",2111000362433868165,,,in,,0,0,0,https://x.com/raracyraa/status/2111000362433868165,1807154344355348480,raracyraa
2111000345963028499,2026-10-16T07:44:37.000Z,0,"MSCI bukan sekadar indeks: dapatkah Indonesia membuktikan bahwa transparansi pasar telah menjadi praktik, bukan hanya peta jalan? @ojkindonesia  @IDX_BEI @prabowo",2111000345963028499,,,in,,0,0,0,https://x.com/sugiyarto_semsi/status/2111000345963028499,1959829346,sugiyarto_semsi
2111000331408810157,2026-10-16T07:44:34.000Z,0,"Jakim tanpa asap kebakaran aja berat, apakabar nanti JRF😖",2111000331408810157,,,in,,0,0,0,https://x.com/nom33rcy/status/2111000331408810157,1009334587221147648,nom33rcy
2111000323628425522,2026-10-16T07:44:32.000Z,1,"YA ALLAH BERTAMBAH 1 ORANG YANG MENINGGAL DALAM KEBAKARAN GUNUNG BROMO😭🙏
turut berdukacita untuk keluarga korban, semoga amal ibadah korban diterima dan ditempatkan di tempat terbaik disisinya🤲 https://t.co/0vju26dd6M",2111000323628425522,https://pbs.twimg.com/media/HUvHhBQaIAEEVGG.jpg,,in,,0,0,0,https://x.com/suncomeinrain/status/2111000323628425522,1389107518702374915,suncomeinrain
2111000309157769644,2026-10-16T07:44:28.000Z,0,"Kabut asap akibat kebakaran hutan dan lahan (karhutla) menyelimuti kawasan Ibu Kota Nusantara (IKN), Kalimantan Timur, hingga membuat sejumlah bangunan pemerintahan tampak samar. Istana Garuda, rumah susun aparatur sipil negara (ASN), dan Masjid Negara nyaris tidak terlihat jelas https://t.co/K5vg7X6W3a",2111000309157769644,https://pbs.twimg.com/amplify_video_thumb/2110998358274023424/img/DmklVX91gkCMao33.jpg,,in,,0,0,0,https://x.com/SINDOnews/status/2111000309157769644,231355136,SINDOnews
2111000282889126148,2026-10-16T07:44:22.000Z,0,"Dukung Kemajuan dan Perlindungan KI, Kemenkum Kaltim Koordinasikan Rencana Pembentukan Perda Kekayaan Intelektual dengan Unikarta

Berita selengkapnya dapat diakses melalui
https://t.co/ino5SlfkYm

#KementerianHukum 
#LayananHukumMakinMudah 
#kanwilkemenkumkalimantantimur https://t.co/B14j2AeZI4",2111000282889126148,https://pbs.twimg.com/media/HUvHd8MbcAA7itS.jpg,,in,,0,0,0,https://x.com/kemenkumkaltim/status/2111000282889126148,2516891534,kemenkumkaltim
2110975391351603710,2026-10-16T07:44:17.000Z,0,"@forfracha @prabowo asli nad, mana lagi angin jugaa",2111000261808263484,,forfracha,in,,0,0,0,https://x.com/edokusai/status/2111000261808263484,1522713928299655170,edokusai
2111000220712743413,2026-10-16T07:44:07.000Z,0,"Km yg mana, busuk ap brsih @prabowo",2111000220712743413,,,in,,0,0,0,https://x.com/beetswax/status/2111000220712743413,1798587991004524544,beetswax
2110933597213606043,2026-10-16T07:44:01.000Z,0,"@Ndrewstjan Saya aja udah mulai hilang kepercayaan ke Prabowo apalagi banyak masalah yang ditimbulkan dari Prabowo padahal baru 2 tahun, siap2 2029 Prabowo kalah",2111000193470456086,,Ndrewstjan,in,,0,0,0,https://x.com/RahagungC33511/status/2111000193470456086,1837501803568717824,RahagungC33511
2111000142698733998,2026-10-16T07:43:49.000Z,0,Kebakaran Limbah Penggergajian Kayu di Argasoka Babinsa dan Damkar Bergerak ke Lokasi https://t.co/qwWhJIOD2l,2111000142698733998,https://pbs.twimg.com/amplify_video_thumb/2110999932081700865/img/97MwxzcbXWQG21Jl.jpg,,in,,0,0,0,https://x.com/Kodim0704bna/status/2111000142698733998,890727850923376640,Kodim0704bna
2110714103853707394,2026-10-16T07:43:44.000Z,0,"@Tan_Mar3M Bener kata orang²...stres di jaman jokowi, gila dijaman prabowo",2111000121513234853,,Tan_Mar3M,in,,0,0,0,https://x.com/ahmadfaisal_13/status/2111000121513234853,276989068,ahmadfaisal_13
2110934617448661254,2026-10-16T07:43:41.000Z,0,"@kamarlintang kenapa ya dedy corbuzier selalu ada di luar influencer yang harus dicancel dan dituntut untuk bersuara ya?? padahal dia juga dapet jabatan dari prabowo, selalu ngebela prabowo segitunya sampe ngegoblok2in kita soal mbg.. dia pendukung garis keras prabowo sejal awal",2111000111354610002,,kamarlintang,in,,0,0,0,https://x.com/WeeYjh23/status/2111000111354610002,1622994199015718912,WeeYjh23
2111000072657998199,2026-10-16T07:43:32.000Z,0,"Perkuat Perlindungan Inovasi Akademik, Kemenkum Kaltim Gelar Pelatihan Pendaftaran KI dan Pembinaan Sentra KI di Kutai Timur

Berita selengkapnya dapat diakses melalui
https://t.co/GnwbIoyYlT

#KementerianHukum 
#LayananHukumMakinMudah 
#kanwilkemenkumkalimantantimur https://t.co/t4z3s5bylZ",2111000072657998199,https://pbs.twimg.com/media/HUvHUaFbgAAA2cv.jpg,,in,,0,0,0,https://x.com/kemenkumkaltim/status/2111000072657998199,2516891534,kemenkumkaltim
2110995767527960839,2026-10-16T07:43:28.000Z,0,@gitanofieka kak dia dateng langsung aja gak datengin yg kena kebakaran tp dikasih liat lahan kosong 🙂 emang ignorance indonesia makmur dipikiran dia doang. pdhal kliatan klo dia mau k kalimantan itu pesawat udh gbs flight 🥲,2111000055511691391,,gitanofieka,in,,0,0,0,https://x.com/sekarflo/status/2111000055511691391,169053480,sekarflo
2111000047080927738,2026-10-16T07:43:26.000Z,0,Indonesia udah mau ancur masi aja dibelain tu orang bodoh @prabowo,2111000047080927738,,,in,,0,0,0,https://x.com/Raybadoet/status/2111000047080927738,1548470138269081602,Raybadoet
2110993291093365154,2026-10-16T07:43:24.000Z,0,@LambeSahamjja Yang benar PRABOWO kah!,2111000037962768776,,LambeSahamjja,in,,0,0,0,https://x.com/orang_miiskin/status/2111000037962768776,539776095,orang_miiskin
2110966939795513790,2026-10-16T07:43:19.000Z,0,"@manwithoutlovey @faqueerm1squeen @undesiringmecha Kan gubernurnya orang Kalimantan, bang. Jadi gk bakal digorok walopun tolol. Yang dia mau gorok cuma orang luar Kalimantan doang.",2111000016471093538,,manwithoutlovey,in,,0,0,0,https://x.com/LLawleett/status/2111000016471093538,1779226661919272962,LLawleett
2110923693253894516,2026-10-16T07:43:17.000Z,0,@inipiian_ Prabowo paling sulit,2111000009491779771,,inipiian_,in,,0,0,0,https://x.com/alldyspa/status/2111000009491779771,1256432920501182466,alldyspa
2111000006807486731,2026-10-16T07:43:16.000Z,0,Kerjaan abang gw emg mantep. Tapi fia ga bisa maki Prabowo. Big win ✊🏼,2111000006807486731,,,in,,0,0,0,https://x.com/torquemaxx/status/2111000006807486731,1496760260643545089,torquemaxx
2110999973131362525,2026-10-16T07:43:08.000Z,0,"Halo, Sobat Mahakam! 👋
Kenalan yuk dengan Sobat Mahakam yang sedang menjalani program magang di BWS Kalimantan IV Samarinda! 

#SigapMembangunNegeriUntukRakyat
#MengelolaAirUntukNegeri https://t.co/VRSboxmKdw",2110999973131362525,https://pbs.twimg.com/amplify_video_thumb/2110997934674481152/img/kt0Bx1tsWyBr2mFj.jpg,,in,,0,0,0,https://x.com/pu_sda_bwsk4/status/2110999973131362525,724840214145961992,pu_sda_bwsk4
2110897337476497718,2026-10-16T07:43:06.000Z,0,"@LambeSahamjja Halah dungu, argumen mu udah gak relevan pasti akan berpihak ke prabowo.. munafik",2110999963123789851,,LambeSahamjja,in,,0,0,0,https://x.com/AdnanNurwachid/status/2110999963123789851,1169907722499719175,AdnanNurwachid
2110981300706501077,2026-10-16T07:43:03.000Z,0,@its__Arthur19 @prabowo MBG nomer satu,2110999952415748500,,its__Arthur19,in,,0,0,0,https://x.com/babyto332/status/2110999952415748500,1743137844133285888,babyto332
2110999938536726545,2026-10-16T07:43:00.000Z,0,"Prabowo Panggil Menteri dan Kepala Badan ke Istana Bogor Jumat Malam
https://t.co/83HWPZrL3n",2110999938536726545,,,in,,0,0,0,https://x.com/Nusavox08/status/2110999938536726545,1947698074547326977,Nusavox08
2110999927937732665,2026-10-16T07:42:57.000Z,0,"Pemberdayaan Masyarakat Muhaimin Iskandar menggalang aksi solidaritas bersama para pelaku industri untuk menyalurkan bantuan darurat berupa masker dan air bersih bagi warga terdampak kebakaran hutan dan lahan (Karhutla), Jumat (16/10). 🎥Rea https://t.co/yX228XGD2q",2110999927937732665,https://pbs.twimg.com/amplify_video_thumb/2110999869162913792/img/S3t6Ilgq5ZdgsYdv.jpg,,in,,0,0,0,https://x.com/RadioElshinta/status/2110999927937732665,121640063,RadioElshinta
2110946359037870138,2026-10-16T07:42:56.000Z,0,"@MiskinTV_ Siap otw kalimantan, infokan kpr yg ready 😆",2110999921646325900,,MiskinTV_,in,,0,0,0,https://x.com/rhkQ/status/2110999921646325900,764506068,rhkQ
2110891147900121175,2026-10-16T07:42:54.000Z,0,"@aniblogsan52394 @Dospemz Tidak cukup hanya cari siapa yang Salah. Mereka yang punya wewenang Dan tugas mencari yang Salah, silahkan. Tapi hanya itu aja tidak akan mengembalikan kondisi hutan Kalimantan. Prof bagus fokus pada harus ada yang juga bekerja melakukan restorasi kondisi Kalimantan.",2110999914675143165,,regalos_torus,in,,0,0,0,https://x.com/regalos_torus/status/2110999914675143165,1558490216671084544,regalos_torus
2110903177860317207,2026-10-16T07:42:50.000Z,0,"@InFebriyan128 Padahal Kalimantan tuh surganya ekosistem, menhut nya aja yg plenger ga bisa kerja,",2110999895675216360,,InFebriyan128,in,,0,0,0,https://x.com/NakatoWill53510/status/2110999895675216360,1773326748492648448,NakatoWill53510
2110962686364442871,2026-10-16T07:42:49.000Z,0,@onyour_cissism bangun kalo presidennya bukan prabowo lg,2110999892911165743,,onyour_cissism,in,,0,1,0,https://x.com/delouvre00/status/2110999892911165743,1261385013087531008,delouvre00
2110979794154430967,2026-10-16T07:42:48.000Z,7,@LambeSahamjja Tolong itu gubernur kalimantan coba disuruh sekolah ulang. Masa pernyataan selayaknya gubernur kyk gini ga bisa?,2110999886623855103,,LambeSahamjja,in,,0,0,0,https://x.com/futonmyouji/status/2110999886623855103,1621177559408058368,futonmyouji
2110999833427509621,2026-10-16T07:42:35.000Z,0,"Lindungi Inovasi Daerah dan Perluas Sinergi KI, Kemenkum Kaltim Berpartisipasi di Pekan Raya Kutim Expo 2026

Berita selengkapnya dapat diakses melalui
https://t.co/2GjaqMioni

#KementerianHukum 
#LayananHukumMakinMudah 
#kanwilkemenkumkalimantantimur https://t.co/kZCg6KPqIZ",2110999833427509621,https://pbs.twimg.com/media/HUvHGQGaIAACQOt.jpg,,in,,0,0,0,https://x.com/kemenkumkaltim/status/2110999833427509621,2516891534,kemenkumkaltim
2110999791996170591,2026-10-16T07:42:25.000Z,0,bangsat semua lu yang pilih prabowo,2110999791996170591,,,in,,0,0,0,https://x.com/nozoitaa/status/2110999791996170591,1474330223487324160,nozoitaa
2110999791711002645,2026-10-16T07:42:25.000Z,0,"""Seorang bayi berusia 1 tahun 2 bulan di Samarinda, Kalimantan Timur, meninggal setelah mengalami sesak napas dan sempat menjalani perawatan intensif di ruang Intensive Care Unit (ICU) rumah sakit.⁠ "" 😥😭",2110999791711002645,,,in,,0,0,0,https://x.com/hanan052020/status/2110999791711002645,1417251642085318663,hanan052020
2110804242181312590,2026-10-16T07:42:22.000Z,0,"@espwilisa @jerukiyowok Gue ga mau tau lu bicara sebagai anak prabowo juga gue ga mau tau. Cuma membandingkan dengan fave lu gimana, berarti perasaan fave lu ga valid karena ngapain dia nangis nangis di acara, mau bikin drama doang? Kan kalau sesuai logika lo kaya gitu.",2110999777672679710,,espwilisa,in,,0,0,0,https://x.com/byurbaby/status/2110999777672679710,1282325268292497409,byurbaby
2110999741152788792,2026-10-16T07:42:13.000Z,0,bagian sedihnya adalah warga kalimantan punya harapan besar pada pemimpin baru. https://t.co/h6hhVBhmS3,2110999741152788792,https://pbs.twimg.com/media/HUvHEqpbEAA6rPt.jpg,,in,,0,0,0,https://x.com/faisalrosanto/status/2110999741152788792,73484895,faisalrosanto
2110996790044766275,2026-10-16T07:42:11.000Z,0,"Ini artikelnya di Tempo

https://t.co/dYdSnTvkh2",2110999731967242569,,abulmuzaffar10,in,,0,0,0,https://x.com/abulmuzaffar10/status/2110999731967242569,909850779749466112,abulmuzaffar10
2110999574068474159,2026-10-16T07:42:05.000Z,0,@littlebubear bangun kalo presidennya bukan prabowo lagi,2110999709620006932,,littlebubear,in,,0,1,0,https://x.com/delouvre00/status/2110999709620006932,1261385013087531008,delouvre00
2110999703295082622,2026-10-16T07:42:04.000Z,0,"Hari ini kita berduka untuk tanah Kalimantan,
untuk langit yang tak lagi biru,
untuk hutan yang terbakar habis,
untuk udara yang tak lagi bersih,
untuk langit yang tak lagi biru.
 
Dan hari ini kita berduka untuk matinya nurani pemerintah Indonesia.

https://t.co/51EzJVY1NX https://t.co/pprqSrwISy",2110999703295082622,https://pbs.twimg.com/media/HUvHCR3aoAAOpgz.jpg,,in,,0,0,0,https://x.com/peritapimenulis/status/2110999703295082622,1863521222988075008,peritapimenulis
2110994059770905015,2026-10-16T07:42:01.000Z,0,@_amandapuspitaa soffel anget 1 buat Opa Prabowo,2110999690279870949,,_amandapuspitaa,in,,0,0,0,https://x.com/chillducc/status/2110999690279870949,1680814449555566592,chillducc
2110999681790792030,2026-10-16T07:41:59.000Z,0,"Wujudkan Hilirisasi dan Penguatan Ekosistem KI di Kutai Timur, Kemenkum Kaltim Dampingi Survei Maturitas KI 2026

Berita selengkapnya dapat diakses melalui
https://t.co/y3SnRcMoHp

#KementerianHukum 
#LayananHukumMakinMudah 
#kanwilkemenkumkalimantantimur https://t.co/idh7IDDYIH",2110999681790792030,https://pbs.twimg.com/media/HUvG_rCaoAEYlE6.jpg,,in,,0,0,0,https://x.com/kemenkumkaltim/status/2110999681790792030,2516891534,kemenkumkaltim
2110968838275964963,2026-10-16T07:41:56.000Z,0,@LambeSahamjja Tenaga mereka lebih banyak buat ngebungkam berita kebakaran dibandingkan buat madamin api,2110999671489626618,,LambeSahamjja,in,,0,0,0,https://x.com/Syipiiap/status/2110999671489626618,1175752795607093248,Syipiiap
2110999653739270212,2026-10-16T07:41:52.000Z,0,@RajaJuliAntoni kamu mentrik kesayangan @prabowo,2110999653739270212,,RajaJuliAntoni,in,,0,0,0,https://x.com/kuntoadji/status/2110999653739270212,50895997,kuntoadji
2110751410409378059,2026-10-16T07:41:51.000Z,0,@cowostress Jangan pilih Prabowo saat pemilu,2110999649775763883,,cowostress,in,,0,0,0,https://x.com/ju_dafirenze/status/2110999649775763883,1381275787140075522,ju_dafirenze
2110999617248834018,2026-10-16T07:41:43.000Z,0,emang prabowo anjing,2110999617248834018,,,in,,0,0,0,https://x.com/ninefahrenheit/status/2110999617248834018,1547889376373248003,ninefahrenheit
2110232008119177538,2026-10-16T07:41:39.000Z,0,"@al_fajr68 @temanduit @gibran_tweet @dennyindrayana @prabowo @grok iya betul sekali....
@Ki_Nusantara99 
TULISANKU TERLALU MENGHIBUR TERMUL",2110999600584896559,,al_fajr68,in,,0,0,0,https://x.com/ardjasa_solo/status/2110999600584896559,1950344826194710528,ardjasa_solo
2110999585065742467,2026-10-16T07:41:36.000Z,1,"gini, kebusukan prabowo membuat jokowi terlihat mendingan 
padahal membandingkan dua hal buruk ga ada gunanya juga",2110999585065742467,,,in,,0,0,0,https://x.com/pendthosa/status/2110999585065742467,2090407859377070080,pendthosa
2110999577319166333,2026-10-16T07:41:34.000Z,0,Gue dah muak banget anjing sama prabowo. Ni orang awet dalam doa gue soal kehancuran,2110999577319166333,,,in,,0,0,0,https://x.com/fmokoz/status/2110999577319166333,1370363980674338816,fmokoz
2110999575242899902,2026-10-16T07:41:33.000Z,0,Gara² prabowo babi semua pada tutup Karna asap https://t.co/0nGTrmnoIc,2110999575242899902,https://pbs.twimg.com/media/HUvG613bIAACvo6.jpg,,in,,0,0,0,https://x.com/Fyners18/status/2110999575242899902,230068840,Fyners18
2110999561066172759,2026-10-16T07:41:30.000Z,0,"maut dalam kebakaran dua rumah berkembar di Kampung Koh, Sitiawan 
https://t.co/3MtuTOY1uv",2110999561066172759,,,in,,0,0,0,https://x.com/MgPerak/status/2110999561066172759,1683735839850004481,MgPerak
2110999521941680226,2026-10-16T07:41:21.000Z,0,"Hutan Kebakaran, IHSG juga 🔥",2110999521941680226,,,in,,0,0,0,https://x.com/tulangputra/status/2110999521941680226,59953809,tulangputra
2110966939795513790,2026-10-16T07:41:12.000Z,3,@faqueerm1squeen @undesiringmecha Kalo orang Kalimantan walopun asbun gpp ya? Kalo orang luar Kalimantan walopun bener mau digorok. Gak heran kalo dipimpin sama pemimpin tolol wkwkwk,2110999485321220113,,faqueerm1squeen,in,,0,0,0,https://x.com/LLawleett/status/2110999485321220113,1779226661919272962,LLawleett
2110997981101203867,2026-10-16T07:41:09.000Z,1,"@GARUDAMERAH__ @ucoxregar @prabowo @sarah_pndjtn @4Y4NKZ @Sammi86Pilang @Subur0204 @SotoAyam1970 Gak masalah mau mendirikan  1000 gereja, 1000 mesjid, 1000 Vihara, 1000 Pura

Faktanya  kebanyakan umat muslim di negeri ini menjadi sekuler 😂",2110999472373465369,,GARUDAMERAH__,in,,0,0,0,https://x.com/a999on/status/2110999472373465369,2041804213986951168,a999on
2110948210135155035,2026-10-16T07:41:03.000Z,0,"@LambeSahamjja Kemungkinan asing lihat program² Prabowo ini arahnya pada dominan nya peran negara mengontrol pasar, yang itu oleh asing dilihat membahayakan",2110999449925521619,,LambeSahamjja,in,,0,0,0,https://x.com/1umarsidik/status/2110999449925521619,325507498,1umarsidik
2110994927127834959,2026-10-16T07:41:02.000Z,0,@1nt0easy Bang lagi dimana emang? Apa di Kalimantan?,2110999442023404017,,1nt0easy,in,,0,1,0,https://x.com/akiracakra/status/2110999442023404017,2028655157924560896,akiracakra
2110999441843118287,2026-10-16T07:41:02.000Z,0,"Ya Allah ni orang @prabowo kebanyakan mudharat daripada manfaatnya selama menjabat, tolong lengserin segera ya Allah",2110999441843118287,,,in,,0,0,0,https://x.com/beetswax/status/2110999441843118287,1798587991004524544,beetswax
2110756361143484733,2026-10-16T07:40:50.000Z,0,@namelesid masi ada yg pilih prabowo astaga,2110999394099294408,,namelesid,in,,0,0,0,https://x.com/jackdp27/status/2110999394099294408,1378994177329954818,jackdp27
2110987990915010919,2026-10-16T07:40:50.000Z,0,@txtdrjkt Ini bukan kebakaran hutan min?,2110999392421597517,,txtdrjkt,in,,0,0,0,https://x.com/blqs__s/status/2110999392421597517,1831051307446329344,blqs__s
2110981300706501077,2026-10-16T07:40:48.000Z,0,@its__Arthur19 @prabowo Duit nya nggak ada 😃,2110999386914500861,,its__Arthur19,in,,0,0,0,https://x.com/CelineAR24/status/2110999386914500861,2060271898744037376,CelineAR24
2110927199083638890,2026-10-16T07:40:43.000Z,0,@NyaiNeneng Wah kau nih..... statement adu kambing. Yang jelas mereka sudah mendesak pemerintah u/ memadamkan api di hutan Kalimantan.,2110999361895412021,,NyaiNeneng,in,,0,0,0,https://x.com/bagushermawan66/status/2110999361895412021,2925058837,bagushermawan66
2110999318157275494,2026-10-16T07:40:32.000Z,1,"Rachel setauku dia pernah update klo nyesel soal keputusannya di pihak 02, beberapa kli dia up jg soal kebakaran hutan ini

Disclaimer bkn fans RV, cuma qrt aja soalnya prnah tau",2110999318157275494,,,in,,0,0,0,https://x.com/hawtsuharu/status/2110999318157275494,857043557760212992,hawtsuharu
2110699290888909248,2026-10-16T07:40:27.000Z,0,@Kimberley_PS08 Tp jujur tanpa harus di jelekan prabowo sudah menjelek kan dirinya sendiri 🙏,2110999295252169205,,Kimberley_PS08,in,,0,0,0,https://x.com/Gunadi____/status/2110999295252169205,1102195438940119040,Gunadi____
2110929784469626920,2026-10-16T07:40:15.000Z,0,@LambeSahamjja kok ga teratasi? katanya tinggal 329hektar lahan yang kebakaran 🤭,2110999247072231689,,LambeSahamjja,in,,0,0,0,https://x.com/furioushanks/status/2110999247072231689,330340103,furioushanks
2110891147900121175,2026-10-16T07:40:15.000Z,0,"@aniblogsan52394 @Dospemz Pembicaraanya adalah, apakah penyataan prof bagus itu adalah penyataan yang tidak melihat kenyataan atau tidak? Beliau lihat pemerintah sudah salah dan lalai, tapi nasi udah jadi bubur, Kalimantan sudah terbakar, sekarang apa yang pemerintah harus lakukan. Itu fokus Dari videonya",2110999244593303577,,regalos_torus,in,,0,1,0,https://x.com/regalos_torus/status/2110999244593303577,1558490216671084544,regalos_torus
2110947859759825066,2026-10-16T07:40:12.000Z,0,"@didiaah_ wow, km pasti pendukung prabowo",2110999233214193833,,didiaah_,in,,0,0,0,https://x.com/irulanm66/status/2110999233214193833,1693894238185086976,irulanm66
2110688902034096393,2026-10-16T07:40:10.000Z,0,@ch_chotimah2 Dr awal sdh curiga si hashim ini ikut bermain dlm kebakaran hutan.. kyk negara punya kel mereka aja.. karena apa.. karena rakyat diam mknya mereka semena2,2110999224519430476,,ch_chotimah2,in,,0,0,0,https://x.com/Fid3llio12/status/2110999224519430476,1508209752119320576,Fid3llio12
2110999189413130541,2026-10-16T07:40:01.000Z,0,"Baca di sini: https://t.co/YKQYqaK18K

Langit Jakarta dan Surabaya tampak berkabut, memicu dugaan asap karhutla Kalimantan telah menyebar hingga Pulau Jawa. Benarkah klaim yang ramai di media sosial tersebut?

~KQ #AsapKarhutla #PulauJawa [20261016090000365] https://t.co/BUWlPlaJF4",2110999189413130541,https://pbs.twimg.com/media/HUvGkhEbgAAH6pg.jpg,,in,,0,0,0,https://x.com/kompascom/status/2110999189413130541,23343960,kompascom
2110953929324576965,2026-10-16T07:39:58.000Z,0,@Astro_Boy020 Kalo udh gini prabowo mikir ga yaww?,2110999176486301826,,Astro_Boy020,in,,0,0,0,https://x.com/wixinteo/status/2110999176486301826,1523792186323894272,wixinteo
2110999170828091567,2026-10-16T07:39:57.000Z,0,"kebul udud ng ruangan indoor wae wes kemlepek, raiso mbayangke dulur-dulure sek ng Kalimantan, Riau &amp; daerah terdampak karhutla liyane🥲",2110999170828091567,,,in,,0,0,0,https://x.com/fakhri_nugrahaa/status/2110999170828091567,1314727567476191232,fakhri_nugrahaa
2110999129770033488,2026-10-16T07:39:47.000Z,3,"Tukang Doxx MASYARAKAT kapan ya ini Manusia dapat Azab.

Orang super jahat modelan Dasco, Prabowo, Hashim rata-rata dikasih umur panjang sama Tuhan.

Rakyat doain mereka cepetan mati, masih hidup aja mereka 😮‍💨",2110999129770033488,,,in,,0,1,0,https://x.com/taniaviandra/status/2110999129770033488,304946313,taniaviandra
2110999071649615992,2026-10-16T07:39:33.000Z,0,Di Semarang aja sepanas ini gimana di Kalimantan???,2110999071649615992,,,in,,0,0,0,https://x.com/aningpa/status/2110999071649615992,64949913,aningpa
2110999070760411225,2026-10-16T07:39:33.000Z,0,KOALISA JOKODOC-PRABOWO 2029 ADALAH KHAYALAN https://t.co/POHg3EngqL,2110999070760411225,https://pbs.twimg.com/amplify_video_thumb/2110997960687517696/img/a3qvRpPLscESFh8D.jpg,,in,,0,0,0,https://x.com/supriyadi2704/status/2110999070760411225,1299649988,supriyadi2704
2110996790044766275,2026-10-16T07:39:33.000Z,1,"@abulmuzaffar10 beneran curiga kalau selama asap ga sampe jawa, ga bakalan pernah kelar ini asap yang di kalimantan sama sumatera",2110999069640610083,,abulmuzaffar10,in,,0,0,0,https://x.com/andniput/status/2110999069640610083,1654277842648322048,andniput
2110999043040317937,2026-10-16T07:39:26.000Z,0,"Topup wdp ml udh 34k anjing dari 28k
@prabowo lu kerja yg bener anjing, kesel bgt gw ngentot, tup up wdp jd mahal ni anjing",2110999043040317937,,,in,,0,0,0,https://x.com/_K4FeCN6/status/2110999043040317937,1616094180241215489,_K4FeCN6
2110997019431194744,2026-10-16T07:39:23.000Z,0,"15/15

Pada akhirnya, pertanyaan pentingnya bukan hanya berapa banyak kebakaran berhasil dipadamkan.

Tetapi juga: mengapa lahan tetap rentan terbakar, apakah pencegahan menyasar sumber risikonya, siapa yang menanggung biaya, dan siapa yang bertanggung jawab ketika pencegahan",2110999029639438428,,HidsalJ,in,,0,0,0,https://x.com/HidsalJ/status/2110999029639438428,1382725234445348864,HidsalJ
2110644907895558396,2026-10-16T07:39:23.000Z,0,@DedynurPalakka @_Sadewa__ @Uki23 @Gerindra Logika lw dimana ... yg bermasalah gibran knp prabowo dibawa bawa 😝,2110999029299700092,,DedynurPalakka,in,,0,0,0,https://x.com/jurigh107/status/2110999029299700092,2044585134897213441,jurigh107
2110999013877223674,2026-10-16T07:39:20.000Z,0,"Jangankan manusia, binatang aja tersiksa hidup di kalimantan saat ini",2110999013877223674,,,in,,0,0,0,https://x.com/yudhaacngkring/status/2110999013877223674,1219982392762322944,yudhaacngkring
2110999011184550235,2026-10-16T07:39:19.000Z,0,"side effect being kalimantan people, disinilah paru paru gua di uji for almost 4 fucking month",2110999011184550235,,,in,,0,0,0,https://x.com/JohnnySuh9295/status/2110999011184550235,1280499619449929731,JohnnySuh9295
2110941510653104275,2026-10-16T07:39:14.000Z,0,@hrdbacot #2tahunGerakNyata prabowo wkwkw,2110998988656943538,,hrdbacot,in,,0,0,0,https://x.com/mrEko_84/status/2110998988656943538,1794451186978099200,mrEko_84
2110998965026271523,2026-10-16T07:39:08.000Z,0,"semangat banget gue retweet hate tweet ke Prabowo, udah sebenci itu emang.",2110998965026271523,,,in,,0,0,0,https://x.com/xolumbina/status/2110998965026271523,1600753598282940416,xolumbina
2110998963587625139,2026-10-16T07:39:08.000Z,0,"@prabowo taek lah, bgaimana kebakaran hutan ini? Anjing ga becus semuaaa..",2110998963587625139,,prabowo,in,,0,0,0,https://x.com/luciusbardata/status/2110998963587625139,1071615588,luciusbardata
2110998924009820466,2026-10-16T07:38:58.000Z,1,"Baca di sini: https://t.co/2FXuNjMUYz 

BMKG mendeteksi asap karhutla dari Kalimantan memasuki atmosfer Jakarta, Banten, dan Jawa Barat, tetapi belum mencapai permukaan tanah. Bagaimana masyarakat dapat memantau kualitas udara dan mengantisipasi dampak asap karhutla?

~KR #BMKG https://t.co/UzA30R9TpH",2110998924009820466,https://pbs.twimg.com/amplify_video_thumb/2110998824126926849/img/YIkQivhGYANL99oR.jpg,,in,,1,0,0,https://x.com/kompascom/status/2110998924009820466,23343960,kompascom
2110978831565967644,2026-10-16T07:38:56.000Z,0,"@senogp Suruh aja grok munculin dampak kebakaran paling parah era SBY, era Jokowi, era Prabowo parahan mana.",2110998913268502805,,senogp,in,,0,0,0,https://x.com/GamefaqsIDN/status/2110998913268502805,1962315346893021184,GamefaqsIDN
2110874067754684468,2026-10-16T07:38:34.000Z,0,"@TheCurut007 Presiden @prabowo  jangan jadi Bedebah,",2110998822940012757,,TheCurut007,in,,0,0,0,https://x.com/dos135790/status/2110998822940012757,1660880654358441985,dos135790
2110998775011708996,2026-10-16T07:38:23.000Z,0,"Update Peringatan Dini Cuaca Wilayah - Kalimantan Tengah Tgl. 16 Oktober 2026 pkl. 14:40 WIB
Prakirawan - BMKG - Kalimantan Tengah
https://t.co/0AS6mswbf5 https://t.co/cmYfswBvXX",2110998775011708996,https://pbs.twimg.com/media/HUvGMj7bEAAxQ8p.jpg,,in,,0,0,0,https://x.com/infoBMKG/status/2110998775011708996,108543358,infoBMKG
2110920475388133526,2026-10-16T07:38:17.000Z,0,@IDX_BEI Sudah berapa kali ini Pak Bowo? Baru juga 2 tahun @prabowo,2110998752710496523,,IDX_BEI,in,,0,0,0,https://x.com/break_habit/status/2110998752710496523,408557445,break_habit
2110982067567947944,2026-10-16T07:38:09.000Z,0,@buburrayam12 Pada kebakaran yak?,2110998720104018084,,buburrayam12,in,,0,1,0,https://x.com/papavilenn/status/2110998720104018084,2029744498675437568,papavilenn
2110998719390990577,2026-10-16T07:38:09.000Z,1,Kau dengan prabowo sama. Anak babi.,2110998719390990577,,,in,,0,0,0,https://x.com/hopemoonfairy/status/2110998719390990577,851666594740568064,hopemoonfairy
2110998718233334184,2026-10-16T07:38:09.000Z,0,"Gila sih, Elon Musk udah bisa bikin Mobil Terbang aja. Indonesia boro-boro bikin mobil terbang, disini padamin kebakaran hutan aja ga becus, udah gitu masih ributin ijazah wkwkwkwkw...

Sc: Yahoo Finance https://t.co/HHN7I2DlBe",2110998718233334184,https://pbs.twimg.com/amplify_video_thumb/2110998685488455680/img/yHSid0OhQnCITNGY.jpg,,in,,0,0,0,https://x.com/DalamDunia888/status/2110998718233334184,2041352553317761024,DalamDunia888
2110998678504951972,2026-10-16T07:38:00.000Z,0,prabowo ki tai dikei nyowo dadi ra bakal nyandak uteke,2110998678504951972,,,in,,0,0,0,https://x.com/ddaengnyangi/status/2110998678504951972,1800558398578237440,ddaengnyangi
2110998643679584588,2026-10-16T07:37:51.000Z,0,"kebakaran di mana-mana woii, mana penanganannya",2110998643679584588,,,in,,0,0,0,https://x.com/aaqwarium/status/2110998643679584588,1542805195981484032,aaqwarium
2110998562507210982,2026-10-16T07:37:48.000Z,0,"Penyebaran dry ice dilakukan bersamaan dengan Operasi Modifikasi Cuaca (OMC), tetapi keduanya memiliki tujuan berbeda. Teknologi dry ice diarahkan untuk mengurangi penumpukan kabut asap, sedangkan OMC bertujuan merangsang hujan buatan guna membantu pemadaman kebakaran. Pemerintah",2110998629368639491,,GNFI,in,,0,0,0,https://x.com/GNFI/status/2110998629368639491,39677695,GNFI
2110997019431194744,2026-10-16T07:37:48.000Z,0,"11/15

Sebab, banyaknya program belum tentu berarti masalahnya selesai.

Aturan bisa diterbitkan. Anggaran bisa dialokasikan. Kegiatan bisa dilaporkan.

Tetapi apakah risiko kebakaran benar-benar berkurang? Apakah intervensi menyasar lokasi berisiko tinggi dan dilakukan sebelum",2110998628563378183,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110998628563378183,1382725234445348864,HidsalJ
2110707357781225859,2026-10-16T07:37:45.000Z,0,"@heniunique Ya Allah.. turunkan bala tentaraMu berupa hujan, padamkan titik-titik api di bumi Kalimantan, Sumatra, Papua, dll.
Turunkan azabMu pada mereka yang harusnya bertanggungjawab terhadap bencana ini..😭😭😭😭",2110998617163247842,,heniunique,in,,0,0,0,https://x.com/DianRivia5/status/2110998617163247842,1603692798372220929,DianRivia5
2110300141299315120,2026-10-16T07:37:45.000Z,0,"@mediaindonesia MANUSA KARDUS ,PENGADUDOMBA MANUSIA, LAYAK DI GANJAR BAKSR HIDUB² MANUSIA SATU INI,, INGINKAN INDONESIA HANCOR MINA SEPERTI TH 97..
BAKAEKAM MANUSIA SATU INI
@prabowo",2110998615544262875,,mediaindonesia,in,,0,0,0,https://x.com/dos135790/status/2110998615544262875,1660880654358441985,dos135790
2110897337476497718,2026-10-16T07:37:44.000Z,0,"@LambeSahamjja Terus kenapa dia ngoceh d Rosi, dan media lain setelah menjabat d ketiak Prabowo 🤔🙄🤭🥱😮‍💨😮‍💨",2110998614751543435,,LambeSahamjja,in,,0,0,0,https://x.com/murniatauasli/status/2110998614751543435,1734445602807955456,murniatauasli
2110998562507210982,2026-10-16T07:37:43.000Z,0,"Pemerintah menguji metode baru untuk mengurangi kabut asap akibat kebakaran hutan dan lahan (karhutla) dengan menyebarkan es kering atau dry ice menggunakan pesawat di Sumatera Selatan. Menteri Koordinator Bidang Politik dan Keamanan, Dudung Abdurachman, menyampaikan bahwa uji",2110998607898009891,,GNFI,in,,0,1,0,https://x.com/GNFI/status/2110998607898009891,39677695,GNFI
2110998583356899728,2026-10-16T07:37:37.000Z,0,"mau dimanapun tempat tinggal ku skrng , aku ttp merasakan sakit hati banget ngeliat saudara sahabat teman ku di kalimantan kekeringan dan kebakaran hebat 😭",2110998583356899728,,,in,,0,0,0,https://x.com/sigemoyyyyyyy15/status/2110998583356899728,1440302537161134093,sigemoyyyyyyy15
2110998565594280205,2026-10-16T07:37:33.000Z,0,Please bgt pak duit pajak gue digunain buat kalimantan dulu lah. @prabowo #prayforkalimantan,2110998565594280205,,,in,,0,0,0,https://x.com/pemaniseni/status/2110998565594280205,302761781,pemaniseni
2110998564797120558,2026-10-16T07:37:32.000Z,0,"Kebakaran hutan dan lahan di Palangka Raya, Kalimantan Tengah, sempat meluas mendekati permukiman warga akibat tiupan angin kencang.

Setelah berbulan-bulan bergelut dengan pekatnya kabut asap, guyuran hujan singkat selama kurang lebih 10 menit akhirnya turun di kawasan Jalan https://t.co/owekK3xDD6",2110998564797120558,https://pbs.twimg.com/amplify_video_thumb/2110998324061016064/img/3aR_2zcHSMVYBorj.jpg,,in,,0,0,0,https://x.com/kompascom/status/2110998564797120558,23343960,kompascom
2110998564054987150,2026-10-16T07:37:32.000Z,0,"Bahkan gw gatau sumpah dan kutukan apalagi yg harus gw teriakkan, gw udh ditahap berpikir neraka pun masih terlalu baik buat prabowo dan antek2nya.",2110998564054987150,,,in,,0,0,0,https://x.com/caaciicuu_u/status/2110998564054987150,1831826487303139330,caaciicuu_u
2110998559621562483,2026-10-16T07:37:31.000Z,0,"Market seharian dibiarkan tanpa response resmi pemerintah @prabowo , dan baru malam hari tepat jelang akhir pekan dmn market akn tutup 2 hari, hal ini baru akn dibahas 😁

Sampai disini jelas kan skenarionya?! 😁

Retail jgn masuk dulu, maksa masuk bs bunuh diri Pak 🤭",2110998559621562483,,,in,,0,0,0,https://x.com/fortisfortuna_9/status/2110998559621562483,2281694042,fortisfortuna_9
2110757133495173262,2026-10-16T07:37:29.000Z,0,@jjkstaan2 tapi kak alhamdulillah denger denger di kalimantan udah turun hujan di beberapa daerah,2110998551174254637,,jjkstaan2,in,,0,0,0,https://x.com/mocacinooy/status/2110998551174254637,1739614028459294720,mocacinooy
2110998541053387208,2026-10-16T07:37:27.000Z,0,gua gapernah seuring uringan ini selama main saham bangsattt prabowo kontol,2110998541053387208,,,in,,0,1,0,https://x.com/tipsyymonkeyy/status/2110998541053387208,1520275437179777030,tipsyymonkeyy
2110998520786465000,2026-10-16T07:37:22.000Z,0,"Rezim laknat. Kalo ga bunuh rakyat, bunuh binatang. Demi Allah gw akan bersumpah di akhirat kelak kalo rezim prabowo ini banyak dzolim nya ke mahluk hidup mau manusia mau binatang",2110998520786465000,,,in,,0,0,0,https://x.com/saintiker_/status/2110998520786465000,887498408,saintiker_
2110982237416288354,2026-10-16T07:37:21.000Z,0,"@daybyzak gw mikir ini bgt dr kmrn, mslahnya story aku buat promoin tmpt club ak kerja. kek abis post kalimantan trus share info party kan ga lucu ya😭",2110998518060228940,,daybyzak,in,,0,0,0,https://x.com/debitbca/status/2110998518060228940,1195898907881959424,debitbca
2110998516902588886,2026-10-16T07:37:21.000Z,0,"Ini galian sepanjang Daan Mogot sampe JORR tuh kapan kelarnya ya? 

Kiri selesai, geser kanan. Gitu aja terus sampe Prabowo pergi meninggalkan kita semua~ https://t.co/pgtaKMCh8h",2110998516902588886,https://pbs.twimg.com/media/HUvF9ZNbEAAVJDj.jpg,,in,,0,0,0,https://x.com/tuhkanasu/status/2110998516902588886,96932909,tuhkanasu
2110998511479386578,2026-10-16T07:37:20.000Z,0,"GAPKI Minta Penanganan Karhutla Berbasis Bukti, Hanya 3,7 Persen Kebakaran Tercatat di Area Sawit Berdiri

JAKARTA – Gabungan Pengusaha Kelapa Sawit Indonesia (GAPKI) meminta penanganan kebakaran hutan dan lahan (karhutla) dilakukan berdasarkan data, pemeriksaan lapangan, dan https://t.co/hTVV8p7s0v",2110998511479386578,https://pbs.twimg.com/media/HUvF9A-acAAJXbt.jpg,,in,,0,0,0,https://x.com/RadioElshinta/status/2110998511479386578,121640063,RadioElshinta
2110998481028764050,2026-10-16T07:37:12.000Z,0,"Ada hujan sebentar hari ini di Kuala Lumpur. Masih terlihat masih berkabut asap imbas dr karhutla. 

Tetap waspada. Semoga karhutla di Kalimantan dan daerah2 lainnya bisa segera padam!  

Bila ada pelaku yang sengaja membakar hutan/lahan, semoga kelakuan kalian dibalas olehNya https://t.co/igcjub1TOi",2110998481028764050,https://pbs.twimg.com/amplify_video_thumb/2110998365769281536/img/yZXEIYr2Sj_gfIPq.jpg,,in,,0,0,0,https://x.com/yusufgunawan/status/2110998481028764050,78619866,yusufgunawan
2110891147900121175,2026-10-16T07:37:09.000Z,0,@regalos_torus @Dospemz anda itu gak paham ya yang saya maksud?  kalau mau gak terjadi kebakaran kasih duid segar untuk orang sekitar agar buka lahan gak dibakar.. pakai sistem harian kalau perlu . uangnya ada gak?,2110998467283935439,,regalos_torus,in,,0,1,0,https://x.com/aniblogsan52394/status/2110998467283935439,1664876228401303554,aniblogsan52394
2110998452947595628,2026-10-16T07:37:06.000Z,0,"4 maut ketika memadam kebakaran di Indonesia yang hasilkan jerebu toksik

#BHdunia Singapura duduki tempat teratas penarafan IQAir bagi bandar utama paling tercemar di dunia, diikuti Kuala Lumpur di tempat kedua dan Jakarta di tempat keenam

https://t.co/OUcnfENONm",2110998452947595628,,,in,,0,0,0,https://x.com/bharianmy/status/2110998452947595628,63070483,bharianmy
2110998442504044993,2026-10-16T07:37:03.000Z,0,dan kata admin @Gerindra masyarakat kalimantan ga ada yang protes,2110998442504044993,,,in,,0,0,0,https://x.com/yourcl1ngyleo/status/2110998442504044993,3265955491,yourcl1ngyleo
2110997019431194744,2026-10-16T07:37:03.000Z,0,"9/15

Lalu, apakah banyaknya program pencegahan berarti masalahnya sudah ditangani dengan tepat?

Jefferson dkk. meneliti 60 intervensi pengelolaan kebakaran di lahan gambut Riau selama 1999 sampai 2016.

Studi mereka menemukan kesenjangan antara rekomendasi ilmiah dan cara",2110998440935362980,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110998440935362980,1382725234445348864,HidsalJ
2110998437324095775,2026-10-16T07:37:02.000Z,0,prabowo dan jajarannya lengser dan diganti orang pintar dan baik. 🥹,2110998437324095775,,,in,,0,0,0,https://x.com/whipielast/status/2110998437324095775,2479024759,whipielast
2110998409717125227,2026-10-16T07:36:55.000Z,0,Sentimen gue terhadap prabowo...... https://t.co/XXKHKLv6hw,2110998409717125227,https://pbs.twimg.com/media/HUvF3OBagAAa52X.jpg,,in,,0,0,0,https://x.com/sopjamur_/status/2110998409717125227,1592445736054304768,sopjamur_
2110998382059942225,2026-10-16T07:36:49.000Z,0,"ANJINGGGGGGGG PRABOWO LU DZOLIM BANGET BANGSATTTTT, LU DAN ANTEK ANTEK LU BETUL BETUL TONE DEAF MAMPUSS",2110998382059942225,,,in,,0,0,0,https://x.com/worriestsv/status/2110998382059942225,1996972398382587904,worriestsv
2110998331296223357,2026-10-16T07:36:37.000Z,0,investasi di era prabowo kocag,2110998331296223357,,,in,,0,0,0,https://x.com/ossjauh/status/2110998331296223357,1500960541421965313,ossjauh
2110998320911130745,2026-10-16T07:36:34.000Z,0,Hp pake segala rusak bangsaaaaaat mau beli pun kudu mikir mikir dulu ah prabowo kontol,2110998320911130745,,,in,,0,0,0,https://x.com/Casualprotest/status/2110998320911130745,1832061990363336704,Casualprotest
2110998285062418516,2026-10-16T07:36:26.000Z,1,"Kebakaran hutan dan lahan (karhutla) menghanguskan rumah Anang Noraini, warga Desa Pematang Baru, Kecamatan Martapura Timur, Kabupaten Banjar, Kalimantan Selatan. Hingga Jumat (16/10/2026), Anang bersama anak dan keponakannya terpaksa tinggal di tenda darurat beratap terpal https://t.co/PdYsZC8QzB",2110998285062418516,https://pbs.twimg.com/amplify_video_thumb/2110992923374575616/img/le6-h5J_vTMxyOF8.jpg,,in,,0,0,0,https://x.com/SINDOnews/status/2110998285062418516,231355136,SINDOnews
2110591246590939555,2026-10-16T07:36:25.000Z,0,"@sehyrui Ntar diaminin, prabowo meninggal wkwk",2110998280738058570,,sehyrui,in,,0,0,0,https://x.com/sqorpius/status/2110998280738058570,757032655380553730,sqorpius
2110997019431194744,2026-10-16T07:36:21.000Z,0,"8/15

Asap tidak mengenal batas administratif. Partikel halus dapat terbawa jauh dari sumber kebakaran.

Dampaknya tidak hanya dirasakan masyarakat yang tinggal dekat area terbakar. Kualitas udara dan kesehatan masyarakat di wilayah lain juga bisa terdampak.

Karhutla adalah",2110998263130407295,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110998263130407295,1382725234445348864,HidsalJ
2110998222906986948,2026-10-16T07:36:11.000Z,0,Info guys kebakaran lagi tapi udah mulai pemadaman ini https://t.co/PcQkOjearK,2110998222906986948,https://pbs.twimg.com/media/HUvFrvsaIAAdUy2.jpg,,in,,0,0,0,https://x.com/KacuiD/status/2110998222906986948,1579267251077025792,KacuiD
2110998208352850188,2026-10-16T07:36:07.000Z,0,"Keterkaitan Malaysia dan Singapura dengan Karhutla di Indonesia terlihat dari dampak kabut asap lintas batas yang dapat mengganggu kesehatan masyarakat, aktivitas ekonomi, dan transportasi. Karena itu, diperlukan kerja sama regional untuk mencegah kebakaran hutan dan lahan. https://t.co/VQ5EDquAFD",2110998208352850188,https://pbs.twimg.com/amplify_video_thumb/2110998097421905920/img/Lw81V3yIQCuFlISk.jpg,,in,,0,0,0,https://x.com/deborahevelyn41/status/2110998208352850188,1830714059777548288,deborahevelyn41
2110998206926688542,2026-10-16T07:36:07.000Z,0,"https://t.co/bfmZe0PJDi

Kepulan asap pekat akibat kebakaran hutan dan lahan (karhutla) yang mengepung kawasan Palaran, Kota Samarinda, Kalimantan Timur merenggut nyawa tak berdosa. https://t.co/IXZ8xwlCuC",2110998206926688542,https://pbs.twimg.com/media/HUvFqzFboAAuC58.jpg,,in,,0,0,0,https://x.com/tribunkaltim/status/2110998206926688542,103551225,tribunkaltim
2110929784469626920,2026-10-16T07:36:07.000Z,0,@LambeSahamjja Rasanya baca berita pak prabowo anxiety bertambah,2110998205911765473,,LambeSahamjja,in,,0,0,0,https://x.com/halloserenity/status/2110998205911765473,1115836030656090114,halloserenity
2110985418011504929,2026-10-16T07:36:07.000Z,0,@RiantDaffa Kecuali kalimantan ya.,2110998205370626274,,RiantDaffa,in,,0,0,0,https://x.com/sntkrnsr/status/2110998205370626274,796796310426787840,sntkrnsr
2110998165340233757,2026-10-16T07:35:57.000Z,0,Bangsat emg gw baru lulus sekolah lg susah nyari kerja yang jabat prabowo jembut jembuttt,2110998165340233757,,,in,,0,0,0,https://x.com/uppuze/status/2110998165340233757,1542111846357794817,uppuze
2110946359037870138,2026-10-16T07:35:56.000Z,2,"@MiskinTV_ Kalimantan jadi negara bagian di bawah invansi/otonomi singapura, ntah diberikan kemerdekaan atau enggak gatau.  

Memicu daerah daerah lainya yang sudsh lama mau memisahkan diri untuk keluar karena indonesia udah gak mampu mengelola (bangkrut)

Indonesia bubar 2030",2110998159715676223,,youngmasterjcw,in,,0,0,0,https://x.com/youngmasterjcw/status/2110998159715676223,1382545107669323777,youngmasterjcw
2110997019431194744,2026-10-16T07:35:50.000Z,0,"7/15

Dampak karhutla tidak berhenti pada lahan yang terbakar.

Grosvenor dkk. dalam Communications Earth &amp; Environment (2024) memperkirakan paparan PM2.5 akibat kebakaran 2019 berkaitan dengan lebih dari 87.000 kematian berlebih di Indonesia.

Ini estimasi berbasis pemodelan,",2110998136634359942,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110998136634359942,1382725234445348864,HidsalJ
2110998125683016027,2026-10-16T07:35:48.000Z,0,Melihat gambar2 &amp; video2 mengenai pasukan penyelamat berusaha dlm mbantu orang utan yg cedera akibat kebakaran hutan di Indonesia sgt menyentuh perasaan. Diwajah mrk tampak sayu &amp; seolah melihat “rumah” mrk dijarah sikap manusia yg kejam.,2110998125683016027,,,in,,0,1,0,https://x.com/akmal_ishak/status/2110998125683016027,289298315,akmal_ishak
2110998123514597451,2026-10-16T07:35:47.000Z,0,"bahkan hewan yang hidup saat pemerintahan prabowo banyak yang jadi korban

kurang ajar, dasar biadab, dasar  pembunuh",2110998123514597451,,,in,,0,0,0,https://x.com/journeywithApr/status/2110998123514597451,2402369514,journeywithApr
2110998088261484910,2026-10-16T07:35:39.000Z,1,"Orangutan betina bernama Ira berhasil diselamatkan dari area lahan terbakar di Kotawaringin Timur, Kalimantan Tengah, pada Rabu (14/10).

Dalam proses evakuasi, Ira sempat tersangkut di pohon setelah dibius, sehingga petugas harus memanjat untuk menurunkannya. Hasil pemeriksaan https://t.co/BhRPsMxP0E",2110998088261484910,https://pbs.twimg.com/amplify_video_thumb/2110997892446273536/img/ikbso3tXY_q9N0-j.jpg,,in,,0,0,0,https://x.com/RadioElshinta/status/2110998088261484910,121640063,RadioElshinta
2110923089920033090,2026-10-16T07:35:37.000Z,0,"@ch_chotimah2 @KPK_RI @prabowo @bang_dasco Mana berani sama Hercules, Nusron",2110998078559768903,,ch_chotimah2,in,,0,0,0,https://x.com/ABudhantar72548/status/2110998078559768903,1863431443726360576,ABudhantar72548
2110908572938952757,2026-10-16T07:35:32.000Z,0,@BelengBeleng687 masa prabowo nggak bisa ngomong baik2. ijab kabulnya kan baik2....,2110998060516139256,,BelengBeleng687,in,,0,0,0,https://x.com/sungpran/status/2110998060516139256,2753286941,sungpran
2110948476179873837,2026-10-16T07:35:30.000Z,0,@olivesugarly @naraeraa @prabowo ini kak dzalim banget :(,2110998050336538926,,olivesugarly,in,,0,0,0,https://x.com/oxyzzuy/status/2110998050336538926,1407625907783696386,oxyzzuy
2110591246590939555,2026-10-16T07:35:27.000Z,0,"@sehyrui Sejak prabowo menjabat, hidup sudah tidak pernah baik baik saja.",2110998040219893932,,sehyrui,in,,0,0,0,https://x.com/duskking96/status/2110998040219893932,1864639134926798848,duskking96
2110998012596290018,2026-10-16T07:35:21.000Z,0,"gila ya prabowo pantesan u nyapres 3 kali kalah mulu anjir, sekalinya dikasih negara nya mau bubar",2110998012596290018,,,in,,0,0,0,https://x.com/baerother/status/2110998012596290018,1509246330,baerother
2110997992018936008,2026-10-16T07:35:16.000Z,0,"Udah melek politik dari era presiden megawati, dari 4 presiden treakhir di negara ini, baru era prabowo dimana seluruh sektor kacau, korupsi, nepotisme dimana mana, mafia ada di setiap bidang, pertama kali ngerasain indonesia kaya gak punya masa depan",2110997992018936008,,,in,,0,0,0,https://x.com/manonhisway/status/2110997992018936008,1173856694008307713,manonhisway
2110724913330012528,2026-10-16T07:35:12.000Z,0,"@ryxul @hi @hollow_sun_club @prabowo YANG BENER KOCAK NAMA LU ITU? 😂 Secinta itu ya lu sama tnr sampai nama lu begitu? Alasan gue ke HSC soalnya mereka lewat tl gue, jadi gue isi aja dah formnya sekalian menguji keberuntungan dalam memikat OA.",2110997976722399687,,ryxul,in,,0,0,0,https://x.com/hyuwnsuk/status/2110997976722399687,1384537299724103682,hyuwnsuk
2110997973585080376,2026-10-16T07:35:12.000Z,0,Lho koq ?!,2110997973585080376,,,in,,0,0,0,https://x.com/JSuryoP1/status/2110997973585080376,1128167650444529666,JSuryoP1
2110990639253082145,2026-10-16T07:35:10.000Z,1,"@scenesgoeshard ""selamat datang di prabowo dua periode"" 🗣",2110997967465509295,,scenesgoeshard,in,,0,0,0,https://x.com/skzophrenia_/status/2110997967465509295,1189548215386787842,skzophrenia_
2110997963602567454,2026-10-16T07:35:09.000Z,0,"Haters nomor 1 Aijing jelas dari Indonesia, you know you know
Kek begitu energynya kenapa gak diarahkan ngebenci prabowo aja sihhh cape dehh",2110997963602567454,,,in,,0,0,0,https://x.com/Vivi_kingdom/status/2110997963602567454,981361196799426560,Vivi_kingdom
2110948210135155035,2026-10-16T07:35:07.000Z,0,@duyduibudui @LambeSahamjja prabowo bener bener stuk otaknya di orde baru,2110997954404425893,,duyduibudui,in,,0,0,0,https://x.com/GogonKelapa/status/2110997954404425893,1324978037935415298,GogonKelapa
2110858355283808418,2026-10-16T07:34:56.000Z,0,@ohmycaramel Bahkan itu size APAR cuma geli geli buat satu rumah 😭 udh gila banget kebakaran hutan ditanganin sama APAR??? Dalam satu ruangan 62 meter aja itu minimal 1 APAR yang 6kg,2110997908581654716,,ohmycaramel,in,,0,0,0,https://x.com/keysenju/status/2110997908581654716,1355872053186809856,keysenju
2110863376046059754,2026-10-16T07:34:55.000Z,0,@unmagnetism nikmati pilihan klean prabowo KNTOL,2110997905276645696,,unmagnetism,in,,0,0,0,https://x.com/Penyintas22/status/2110997905276645696,111226133,Penyintas22
2110997887438200916,2026-10-16T07:34:51.000Z,0,"imagine jokowi udah keliatan se evil apa, masih keliatan better dari prabowo",2110997887438200916,,,in,,0,0,0,https://x.com/88dityara/status/2110997887438200916,811460709510836224,88dityara
2110997876990173501,2026-10-16T07:34:48.000Z,0,Kata aing mah pemerentah udah ditunggangi antek antek asing untuk mengancurkan kalimantan,2110997876990173501,,,in,,0,0,0,https://x.com/Daffamtsn1/status/2110997876990173501,4476037754,Daffamtsn1
2110997854739481054,2026-10-16T07:34:43.000Z,0,"Pesan Keluarga Mulyono
#pesan #keluarga #mulyono @Gerindra @prabowo
https://t.co/4OioZO1PLd",2110997854739481054,,,in,,0,0,0,https://x.com/gulaciamis/status/2110997854739481054,2307033840,gulaciamis
2110997793783660578,2026-10-16T07:34:29.000Z,0,"Selamat ulang tahun, Pak Presiden RI Prabowo Subianto.

Selamat bertambah usia. Semoga kursi kepresidenan ini cukup menjadi bukti bahwa selama ini Anda hanya penasaran dengan kekuasaan. Anda sudah tiga kali mencoba merebut kursi tersebut dan gagal. Tuhan mungkin sudah mencegah https://t.co/yMxFDwvQfT",2110997793783660578,https://pbs.twimg.com/media/HUvFSCeagAEhsdQ.jpg,,in,,0,0,0,https://x.com/Smash1014314/status/2110997793783660578,1838979981948616704,Smash1014314
2110997724548239816,2026-10-16T07:34:12.000Z,0,Dulu sebelum kerja mikirnya gaji atas umr bisa hidup. Pas udah atas umr ternyata susah jg. Ini aku yg boros atau emang ekonomi sekarang yg kayak prabowo?,2110997724548239816,,,in,,0,0,0,https://x.com/rainbowartinya/status/2110997724548239816,1210149111770439680,rainbowartinya
2110997720869773638,2026-10-16T07:34:11.000Z,0,"Kabut asap akibat kebakaran hutan dan lahan bukan hanya  disebakan dari  Indonesia, tetapi juga menjadi masalah lintas negara di Asia Tenggara malasya dan singapura.",2110997720869773638,,,in,,0,0,0,https://x.com/Rifkipu62641451/status/2110997720869773638,1906039917832228864,Rifkipu62641451
2110554306973970602,2026-10-16T07:34:08.000Z,0,"@chyprefloral Udah dipersiapkan jauh2 hari supaya mereka menang, apapun caranya. Dibikin tolol, dibikin miskin, dibikin gak ada pilihan lain. 2014 &amp; 2019 cuma pilihannya cuma jokowi vs prabowo",2110997707255165128,,chyprefloral,in,,0,0,0,https://x.com/RickoSetyabudi/status/2110997707255165128,132023874,RickoSetyabudi
2110997679526609298,2026-10-16T07:34:01.000Z,0,saatnya ke kalimantan pak ❤️,2110997679526609298,,,in,,0,0,0,https://x.com/eajfries/status/2110997679526609298,1441314530282205185,eajfries
2110997019431194744,2026-10-16T07:33:54.000Z,0,"3/15

Kiely dkk. dalam Nature Communications (2021) memperkirakan kerugian ekonomi dari enam peristiwa kebakaran besar di Indonesia pada 2004 sampai 2015 mencapai US$93,9 miliar. Kebakaran 2015 sendiri diperkirakan menimbulkan kerugian sekitar US$28 miliar.

Perlu dicatat, ini",2110997648547463585,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110997648547463585,1382725234445348864,HidsalJ
2110997617488642329,2026-10-16T07:33:47.000Z,0,"BREAKING NEWS: Asap karhutla Kalimantan masuk Jakarta, Banten, Jabar

Selengkapnya &gt;&gt;&gt; https://t.co/X4SwBN8vG5

https://t.co/X4SwBN8vG5",2110997617488642329,,,in,,0,0,0,https://x.com/otonomicoid/status/2110997617488642329,753824742491074561,otonomicoid
2110997598467477932,2026-10-16T07:33:42.000Z,0,"Api karhutla di Kalimantan masih belum sepenuhnya padam, tapi Jepang sudah mengakhiri misi bantuan pemadaman.

Pas baca siaran pers dari Jepang, ternyata mereka pulang karena pihak Indonesia menyatakan kebakarannya “bisa ditangani oleh pemerintah Indonesia”. https://t.co/kTWkQZnpyy",2110997598467477932,https://pbs.twimg.com/media/HUvFGRza8AA9ory.jpg,,in,,0,0,0,https://x.com/keluhkesahkonoh/status/2110997598467477932,494927528,keluhkesahkonoh
2110997583397286239,2026-10-16T07:33:38.000Z,0,Karya Nyata Prabowo @prabowo,2110997583397286239,,,in,,0,0,0,https://x.com/YoyokSub0302/status/2110997583397286239,1681216695472656384,YoyokSub0302
2110699290888909248,2026-10-16T07:33:28.000Z,0,"@Kimberley_PS08 hei pantek, kau sama prabowo kau itu mau kita bawa ke hutan yang masih kebakaran itu kah?",2110997539856281633,,Kimberley_PS08,in,,0,0,0,https://x.com/ashenvenus/status/2110997539856281633,1062137177239281664,ashenvenus
2110931537785229498,2026-10-16T07:33:26.000Z,0,@keluhkesahkonoh Pasti pendukung prabowo subiantolol,2110997529869599046,,keluhkesahkonoh,in,,0,0,0,https://x.com/YahyaIbhan/status/2110997529869599046,1264980416110268421,YahyaIbhan
2110986017859617144,2026-10-16T07:33:25.000Z,0,@Hiugundul @Uki23 Gank termul skrg nyerang prabowo ada yg gak beres 😂,2110997526769963274,,Hiugundul,in,,0,0,0,https://x.com/jurigh107/status/2110997526769963274,2044585134897213441,jurigh107
2110997520621146341,2026-10-16T07:33:24.000Z,0,"""bayangkan tiba-tiba datang orang yang kalian benci"" REFLEKS PRABOWO DATENG AJG BENCI",2110997520621146341,,,in,,0,0,0,https://x.com/121draft/status/2110997520621146341,1484577553948246017,121draft
2110997520205967442,2026-10-16T07:33:23.000Z,0,"Keterkaitan Malaysia dan Singapura dengan Karhutla di Indonesia terlihat dari dampak kabut asap lintas batas yang dapat mengganggu kesehatan masyarakat, aktivitas ekonomi, dan transportasi. Karena itu, diperlukan kerja sama regional untuk mencegah kebakaran hutan dan lahan. https://t.co/05cEeO1pW1",2110997520205967442,https://pbs.twimg.com/amplify_video_thumb/2110997245105709056/img/mr7cTVZS6iB--tOy.jpg,,in,,0,0,0,https://x.com/malesmikir33/status/2110997520205967442,2080134318634958848,malesmikir33
2110997511137828963,2026-10-16T07:33:21.000Z,0,"Keterkaitan Malaysia dan Singapura dengan Karhutla di Indonesia terlihat dari dampak kabut asap lintas batas yang dapat mengganggu kesehatan masyarakat, aktivitas ekonomi, dan transportasi. Karena itu, diperlukan kerja sama regional untuk mencegah kebakaran hutan dan lahan. https://t.co/tK7xwmxEIz",2110997511137828963,https://pbs.twimg.com/amplify_video_thumb/2110997212587282432/img/nZ0nC3Fb19ABFPSm.jpg,,in,,0,0,0,https://x.com/itsmedivaxo/status/2110997511137828963,2080134391796252672,itsmedivaxo
429646884152434689,2026-10-16T07:33:20.000Z,0,"@prabowo @Gerindra @Aktivis_Larshen LOE UDAH GILA, SAKIT JIWA, NPD, DEMENSIA, NAJIS, TUA BANGKA, BIJI SATU, DAN IMPOTEN",2110997505483980842,,prabowo,in,,0,0,0,https://x.com/zhoriez/status/2110997505483980842,1641481592421109760,zhoriez
2110997505257410779,2026-10-16T07:33:20.000Z,0,Gue capek banget Ya Alloh…. Gak ada yang bisa menghukum rezim Prabowo Gibran kecuali Engkau dan atas izin-Mu Ya Alloh 😭😭😭😭😭 capeeeekk,2110997505257410779,,,in,,0,0,0,https://x.com/sourirever/status/2110997505257410779,1499411440692006912,sourirever
2110997484189397432,2026-10-16T07:33:15.000Z,0,"jujur ikut seneng banget bangett liat kabar kalo beberapa daerah di kalimantan udah hujan, semoga hujan merata di setiap daerah karhutla aamiinnn",2110997484189397432,,,in,,0,0,0,https://x.com/lutpeyyy/status/2110997484189397432,1079533962765029376,lutpeyyy
2110997474374758531,2026-10-16T07:33:12.000Z,0,stop the wedding yang kmrn milih prabowo cuman karna fomo gemoy dan kasian anjing lah lu semua,2110997474374758531,,,in,,0,0,0,https://x.com/crietis/status/2110997474374758531,1330849192818790402,crietis
2110719284653797524,2026-10-16T07:33:12.000Z,0,@LambeSahamjja tiup tu api-api hutan kalimantan,2110997472965431591,,LambeSahamjja,in,,0,0,0,https://x.com/Rissunflower/status/2110997472965431591,1259682498423873536,Rissunflower
2110966364466983052,2026-10-16T07:33:08.000Z,0,@idextratime untung banget gw gak terjun saham di era prabowo ini,2110997454414020968,,idextratime,in,,0,0,0,https://x.com/yellowzename/status/2110997454414020968,1688002399687106560,yellowzename
2110718608124842222,2026-10-16T07:30:41.000Z,0,@Fraksi_Gerindra @prabowo indonesia cerah ndassmuu https://t.co/jODRiNij6k,2110996838069542988,https://pbs.twimg.com/media/HUvEbs2aIAAv2bA.jpg,Fraksi_Gerindra,in,,0,0,0,https://x.com/coretan_gorong2/status/2110996838069542988,1482411191544971264,coretan_gorong2
2110996828108001515,2026-10-16T07:30:38.000Z,0,saya sangat rela tidak merasakan gerimis di jogja demi melihat langit biru di kalimantan perlahan kembali✊✊✊,2110996828108001515,,,in,,0,0,0,https://x.com/hancockfanboy/status/2110996828108001515,1577612428048637952,hancockfanboy
2110996790044766275,2026-10-16T07:30:29.000Z,5,"Barusan baca artikel di Tempo.

Kebakaran hutan di Kalimantan dan Sumatra harus diatasi segera. Maksimal bulan ini.

Jika bulan depan belum selesai, waduh, Jawa bisa kena.

Tahu ga kenapa? Karena arah angin muson nanti akan mengarah ke Jawa, khususnya Jakarta, mulai bulan depan. https://t.co/8fILXsk7Gq",2110996790044766275,https://pbs.twimg.com/media/HUvECuWaIAAXuNP.png,,in,,0,4,1,https://x.com/abulmuzaffar10/status/2110996790044766275,909850779749466112,abulmuzaffar10
2110995129310069187,2026-10-16T07:30:25.000Z,0,"@dimzsky_ Terima kasih sudah menambahkan perspektifnya. Saya sepakat. Betul, kalau mau ditelusuri lebih jauh, kebakaran hutan sudah lama terjadi sejak ORBA tapi waktu itu belum ada pencatatan modern oleh KLHK/BNPB.

Konteks twit saya sebelumnya adalah perbandingan Jokowi &amp; Prabowo. Jelas",2110996773099708604,,dimzsky_,in,,0,0,0,https://x.com/anakgembala116/status/2110996773099708604,1688920600461574144,anakgembala116
2110933612535357533,2026-10-16T07:30:25.000Z,0,@pyongariy @edzsamudra Kalau kata claude sih jaman jokowi 2015 paling parah baik dalam hal jumlah korban dan nilai kerugian. Tapi jaman prabowo bukan berarti baik ya,2110996772956803086,,pyongariy,in,,0,0,0,https://x.com/johnkennedav2z/status/2110996772956803086,2063809768242962432,johnkennedav2z
2110919591648190665,2026-10-16T07:30:22.000Z,0,@tadanoryandesu @Ndrewstjan @prabowo bukanya surya paloh dan cak imin ya? yang menggaungkan 3 periode,2110996759594033462,,tadanoryandesu,in,,0,0,0,https://x.com/kaleramadhan_/status/2110996759594033462,1407986023716376582,kaleramadhan_
2110996758910112172,2026-10-16T07:30:22.000Z,0,"Presiden Prabowo beri lampu hijau bantuan asing untuk pemadaman karhutla. 

Langkah ini diambil usai asap pekat memicu krisis udara regional hingga meliburkan sekolah di Malaysia. 
https://t.co/5QnG2uT48N",2110996758910112172,,,in,,0,0,0,https://x.com/TRTindonesia/status/2110996758910112172,1793626602623897601,TRTindonesia
2110996695354077254,2026-10-16T07:30:17.000Z,0,Satwa yang di lindungi Jalan sendiri aja udah tau berat lebi dari pada manusia setiap Kebakaran selalu di Pindahin emangnya gue enggak Capek Mindahin banyak satwa langka Hampir pindah itu mereka aja Yang gimmick mulu apa lagi temen Gue sih paling suku dayak emnag enggak dapetduit,2110996736584102311,,BABIHAEKELd4m0,in,,0,1,0,https://x.com/BABIHAEKELd4m0/status/2110996736584102311,2092410765458411520,BABIHAEKELd4m0
2110996718611468459,2026-10-16T07:30:12.000Z,4,"Di tengah kepungan kabut asap yang menyelimuti Kalimantan Tengah, sebuah pesan sederhana dari seorang anak menyentuh hati 🥹 https://t.co/nch9MxwQMK",2110996718611468459,https://pbs.twimg.com/amplify_video_thumb/2110995310109745152/img/vB3xlf7G2wAJhC0J.jpg,,in,,0,0,2,https://x.com/bagindo_kopi/status/2110996718611468459,1091031753924403200,bagindo_kopi
2110996695354077254,2026-10-16T07:30:07.000Z,0,enggak usah di Tag lagi Saam viralin Masalah bahlil aja Ge gue capek setopa tahun ada aja hutan yang kebakaran Dari pubrikan Malaysia 8 % Indonesia 93 % Yang bakar pulau kalimatan Sulawesi dan lain lain mereka minta Empati cuman gimmick aja lah  apek pula aku suruh Orang Utan,2110996695354077254,,,in,,0,1,0,https://x.com/BABIHAEKELd4m0/status/2110996695354077254,2092410765458411520,BABIHAEKELd4m0
2110898685215470040,2026-10-16T07:30:01.000Z,0,"@msaid_didu @ojkindonesia @prabowo Pak, teman bapak omon, kelilingin sama org2 yg ga berkemampuam…. Dikasih data ga diliat….",2110996671295627374,,msaid_didu,in,,0,0,0,https://x.com/bydhln/status/2110996671295627374,1117011459702005760,bydhln
2110996666702815336,2026-10-16T07:30:00.000Z,0,"SBY :
10 tahun = 1 kali trading halt

Jokowi :
10 tahun = 1 kali

Prabowo :
2 tahun = 5 kali
10 tahun = potensi 25 kali trading halt ☠️",2110996666702815336,,,in,,0,0,0,https://x.com/ekky1995/status/2110996666702815336,1259033406333059073,ekky1995
2110996666321092887,2026-10-16T07:30:00.000Z,1,"gue kritik prabowo bukan berarti gue pendukung anies. gue cuma rakyat biasa yang pengen harga kebutuhan murah, gaji naik, dan bisa masuk minimarket tanpa harus mempertimbangkan kondisi geopolitik dompet sendiri 😭",2110996666321092887,,,in,,0,0,0,https://x.com/sihalistebal/status/2110996666321092887,1236493893580943360,sihalistebal
2110996666258239981,2026-10-16T07:30:00.000Z,0,Sing sarehat dulur dulur kalimantan.,2110996666258239981,,,in,,0,0,0,https://x.com/muhammadariel_r/status/2110996666258239981,742564700,muhammadariel_r
2110637905886769546,2026-10-16T07:29:55.000Z,0,@fagaraga777 hidup udah dibikin susah aja masi jadi penyepong prabowo. kntl lah,2110996646981169371,,fagaraga777,in,,0,0,0,https://x.com/yourbabytalk/status/2110996646981169371,2021475575358160906,yourbabytalk
2110996622234820804,2026-10-16T07:29:54.000Z,0,"Meski situasi saat ini sudah berangsur membaik, pihak berwenang tetap mengimbau warga untuk waspada dan menghindari aktivitas yang dapat memicu kebakaran lahan baru.

#TVRI #TVRINasional #MediaPemersatuBangsa #Palangkaraya #Hujan",2110996639792157110,,TVRINasional,in,,0,0,0,https://x.com/TVRINasional/status/2110996639792157110,822554676,TVRINasional
2110900774016540965,2026-10-16T07:29:53.000Z,1,"@jhonsitorus_19 Jokowi pernah di hajar Kebakaran hutan, kini Prabowo di hajar lagi kebakaran hutan,,
Musuh politik begitu Jahat dan masif kerjanya...
Hukum Mati pembuat onar di negara ini biar ada efek ajera,
ini bahaya Laten jika di biarkan bisa hancor mina negara ini
@prabowo",2110996636797415831,,jhonsitorus_19,in,,0,0,0,https://x.com/dos135790/status/2110996636797415831,1660880654358441985,dos135790
2110976372571275598,2026-10-16T07:29:51.000Z,0,@indomerebus @prabowo Lah diotar atur sak karepe dewe..,2110996629159657852,,indomerebus,in,,0,1,0,https://x.com/RonoReneRemen/status/2110996629159657852,257056323,RonoReneRemen
2110996622234820804,2026-10-16T07:29:50.000Z,0,"Kondisi ini disambut baik oleh warga setempat melalui berbagai unggahan di media sosial, setelah sebelumnya wilayah ini terpapar kabut asap akibat Kebakaran Hutan dan Lahan (Karhutla) selama hampir tiga bulan terakhir.",2110996626013929724,,TVRINasional,in,,0,1,0,https://x.com/TVRINasional/status/2110996626013929724,822554676,TVRINasional
2110996622234820804,2026-10-16T07:29:49.000Z,0,"Kualitas udara di Kota Palangka Raya, Kalimantan Tengah, akhirnya menunjukkan perubahan signifikan menjadi lebih bersih pada Jumat pagi (16/10/2026). https://t.co/BRoP6sxOPZ",2110996622234820804,https://pbs.twimg.com/amplify_video_thumb/2110996552793927681/img/pngg3SVRdp-80if0.jpg,,in,,0,1,0,https://x.com/TVRINasional/status/2110996622234820804,822554676,TVRINasional
2110615761324777723,2026-10-16T07:29:43.000Z,0,"@BangPino__ Kita tidak menghina Presiden Prabowo, harus skala prioritas, Jokowi dan Gibran dulu yg harus diselesaikan polemik ijazahnya. Karena ini masalah identitas.",2110996596435640409,,BangPino__,in,,0,0,0,https://x.com/Tomhen2/status/2110996596435640409,1307551656784007168,Tomhen2
2110996584066687483,2026-10-16T07:29:40.000Z,0,"prabowo out 
windah in",2110996584066687483,,,in,,0,0,0,https://x.com/bagasmancing/status/2110996584066687483,1921747340689625088,bagasmancing
2110996545013440894,2026-10-16T07:29:31.000Z,2,DROP 1 UCAPAN UNTUK PRABOWO DI HARI ULANG TAHUNNYA BESOK,2110996545013440894,,,in,,0,2,0,https://x.com/cariaeosa/status/2110996545013440894,1515859957001830401,cariaeosa
2110996488029663461,2026-10-16T07:29:17.000Z,0,prabowo tuh buta dan tuli kah?,2110996488029663461,,,in,,0,0,0,https://x.com/worriestsv/status/2110996488029663461,1996972398382587904,worriestsv
2110996435017801822,2026-10-16T07:29:12.000Z,0,"dan sesuai dengan ketentuan yang berlaku.
Melalui kegiatan ini, Balai Bahasa Provinsi Kalimantan Selatan berkomitmen untuk meningkatkan kualitas pengelolaan arsip yang efektif, efisien, dan akuntabel guna mendukung tertib administrasi serta pelestarian dokumen secara digital.",2110996464780693556,,balaibhskalsel,in,,0,0,0,https://x.com/balaibhskalsel/status/2110996464780693556,700676990722924544,balaibhskalsel
2110996456001966588,2026-10-16T07:29:10.000Z,0,"Gak hutan,gak rupiah,gak ihsg. Semuanya kebakaran. Great job prabowo🔥🔥🔥",2110996456001966588,,,in,,0,0,0,https://x.com/albert454654271/status/2110996456001966588,1595753666577063936,albert454654271
2110996435017801822,2026-10-16T07:29:05.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan rapat penyelesaian digitalisasi arsip tahun 2025 pada Selasa, 13 Oktober 2026. Kegiatan ini bertujuan untuk memastikan penyelesaian proses digitalisasi arsip berjalan dengan baik, tertib, https://t.co/fl8D6Mo2tT",2110996435017801822,https://pbs.twimg.com/media/HUvEDnFbAAAGjKv.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110996435017801822,700676990722924544,balaibhskalsel
2110988904904245492,2026-10-16T07:28:50.000Z,0,"@LambeSahamjja Sudah banyak yg maksi-maki prabowo, kalian gimana? Sudah atau belum? Belum atau sudah? https://t.co/H7sgMHJi2m",2110996372082319585,https://pbs.twimg.com/media/HUvEApCaMAAE1OL.jpg,LambeSahamjja,in,,0,0,0,https://x.com/Prabomon/status/2110996372082319585,1802586755285356544,Prabomon
2110968838275964963,2026-10-16T07:28:49.000Z,0,"@LambeSahamjja jangan mundur, terus siarkan kawan2. Saudara2 kita di kalimantan dan sumatra sedang benar2 butuh suara kita",2110996367455948902,,LambeSahamjja,in,,0,0,0,https://x.com/ParamartaY/status/2110996367455948902,1456193213358768129,ParamartaY
2110966364466983052,2026-10-16T07:28:37.000Z,0,@idextratime 0 udah keluar IHSG semenjak presidennya prabowo,2110996318533689835,,idextratime,in,,0,0,0,https://x.com/swjaya/status/2110996318533689835,513076245,swjaya
2110933612535357533,2026-10-16T07:28:35.000Z,0,"@Gilfffttthhh @edzsamudra Kata2 andalan dia : ""saya dapat laporan""... Masalahnya dr era jokowi semua data yg pihak pemerintah rilis udh kebanyakan di manipulasi, jd data apa bjir yg dimaksud? 🤣😂 Mungkin antekw bawahannya ngefliter jd pg13 Kali yah buat Prabowo? Kan mentalnya labil bngt",2110996312053387395,,Gilfffttthhh,in,,0,0,0,https://x.com/ragildw_t/status/2110996312053387395,1994102693582000128,ragildw_t
2110996310698631352,2026-10-16T07:28:35.000Z,4,"Tetep sy anggap temen, kok. TAPI, tiap hari akan sy bombardir dg fakta2 ketololan prabowo sampai—kalau dia nggak berubah pikiran juga—dia yg nggak mau jadi temen saya.",2110996310698631352,,,in,,0,0,0,https://x.com/_MasWis/status/2110996310698631352,3301333705,_MasWis
2110996293921439844,2026-10-16T07:28:31.000Z,0,Nah gini cara respon yg bener @RajaJuliAntoni @prabowo,2110996293921439844,,,in,,0,0,0,https://x.com/Canopiz/status/2110996293921439844,1433279749774733315,Canopiz
2110996271561630164,2026-10-16T07:28:26.000Z,1,"Update Peringatan Dini Cuaca Wilayah - Kalimantan Barat Tgl. 16 Oktober 2026 pkl. 14:50 WIB
Prakirawan - BMKG - Kalimantan Barat 
https://t.co/CS490ZbCxX https://t.co/0Fn8Dx05RM",2110996271561630164,https://pbs.twimg.com/media/HUvD6wNbgAA7J6I.jpg,,in,,0,0,0,https://x.com/infoBMKG/status/2110996271561630164,108543358,infoBMKG
2110933597213606043,2026-10-16T07:28:23.000Z,0,"@Ndrewstjan Semua kebijakan yang bagus zaman jokowi dirombak total oleh Prabowo, hasilnya ya seperti skrg, arahnya tdak jelas.",2110996258253045919,,Ndrewstjan,in,,0,0,0,https://x.com/jayacand/status/2110996258253045919,1364379045543047169,jayacand
2110915370983027030,2026-10-16T07:28:07.000Z,0,"@gnrlfans @persib Dan beberapa pemegang saham terbesar di Persib jg punya kepentingan CPO di Kalimantan, anu nya Erick Thohir jg salah satu nya. 🫢",2110996194092806343,,tukangtwittter,in,,0,1,0,https://x.com/tukangtwittter/status/2110996194092806343,1244673152166182912,tukangtwittter
2110996184366264751,2026-10-16T07:28:05.000Z,0,"Kabut asap tebal membuat langit Palangkaraya, Kalimantan Tengah, tampak kuning dan oranye. Seperti diberitakan https://t.co/5exe197Vxj pada Jumat (16/10), akibat kabut asap yang tebal ini, maka jarak pandang turun hingga hanya beberapa puluh meter. 

Editor: Adit

#IDNTimesKaltim https://t.co/iqRD0G5k2Z",2110996184366264751,https://pbs.twimg.com/amplify_video_thumb/2110996115512610817/img/mqW6fPbEWO4ja1MV.jpg,,in,,0,0,0,https://x.com/IDNTimesKaltim/status/2110996184366264751,1318854352069554177,IDNTimesKaltim
2110922720829714516,2026-10-16T07:27:57.000Z,1,"@indeksIND Di dalam negeri saja GAK ADA lagi yg PERCAYA kepada NIAT &amp; KEMAMPUAN Rezim Prabowo utk membenahi Indonesia. 
Apalagi Lembaga Rating Internasional seperti MSCI?",2110996152573407331,,indeksIND,in,,0,0,0,https://x.com/meliksuman74092/status/2110996152573407331,2008154113826271232,meliksuman74092
2110996147926130995,2026-10-16T07:27:56.000Z,0,"Beredar narasi di medsos yg menyebutkan bahwa asap kebakaran hutan&amp;lahan (karhutla) dr Kalimantan telah sampai ke ibu kota. Meski demikian, tampilan langit saja belum cukup untuk memastikan asal dari kabut tersebut.  
​#Viral #PolusiUdara #PolusiJakarta #LangitJakarta #Karhutla https://t.co/59QfrD8CLl",2110996147926130995,https://pbs.twimg.com/amplify_video_thumb/2110996100987719680/img/jDWFkZh-bo7uL_y-.jpg,,in,,0,0,0,https://x.com/RahmaTriwi84221/status/2110996147926130995,2047241365688639488,RahmaTriwi84221
2110996142460952873,2026-10-16T07:27:55.000Z,0,"Invasi sih invasi. Tapi jangan grup pecinta prabowo subianto juga asw!!

Skip full intel X buzzer grupnya https://t.co/pYuNBL8N4T",2110996142460952873,https://pbs.twimg.com/media/HUvDy0La4AAuWLL.jpg,,in,,0,1,0,https://x.com/emyr_za1/status/2110996142460952873,1504627720915132416,emyr_za1
2110732178837602642,2026-10-16T07:27:45.000Z,0,"@susipudjiastuti @prabowo Maaf bu, Kebakaran hutan segitu luasnya saja beliau tidak tahu apalagi informasi ini 🙏",2110996100102656219,,susipudjiastuti,in,,0,0,0,https://x.com/yasinal_/status/2110996100102656219,496070325,yasinal_
2110943544315937250,2026-10-16T07:27:43.000Z,0,"@Sebelahkampus ya meskipun gak ada jalur solo seperti definisi karirnya pa prabowo, tapi pecah bintangnya kan waktu jadi wakapolda metro. lalu jadi kapolda Banten atas persetujuan siapa? ya pa prabowo dan presiden Jokowi lah",2110996091739230261,,Sebelahkampus,in,,0,0,0,https://x.com/afannni/status/2110996091739230261,54114263,afannni
2110708729490636804,2026-10-16T07:27:41.000Z,0,@apriedaze Bawa ke Kalimantan biar dia ngerasain kena ISPA bkn malah ank2 bayi/ kecil disana aja yg ngerasain gara2 penanganan di era dia lelet bgt,2110996082427879577,,apriedaze,in,,0,0,0,https://x.com/nanagurlx/status/2110996082427879577,1425714579456225280,nanagurlx
2110946940565537194,2026-10-16T07:27:39.000Z,0,@heykoomi Kakk kmu org kalimantan?,2110996074383167570,,heykoomi,in,,0,1,0,https://x.com/iggemajja/status/2110996074383167570,1504759473667440645,iggemajja
2110995955810254970,2026-10-16T07:27:37.000Z,0,"BPMP Provinsi Kalimantan Selatan, Selasa 13 Oktober 2026.
Kegiatan ini dihadiri oleh kepala dan kepala subbagian umum dari kedua instansi, serta tim ZI-WBK dan PPID BBPKS dan BPMP Provinsi Kalimantan Selatan.",2110996068657930676,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110996068657930676,700676990722924544,balaibhskalsel
2110996034776412302,2026-10-16T07:27:29.000Z,1,Energy nya mending dipake buat menyuarakan kebakaran dan krisis di indonesia aja bang.,2110996034776412302,,,in,,0,0,0,https://x.com/thlss0philes/status/2110996034776412302,1652335890306584576,thlss0philes
2110990639253082145,2026-10-16T07:27:29.000Z,0,@scenesgoeshard prabowo jadi presiden. itu aja serem,2110996033849458834,,scenesgoeshard,in,,0,0,0,https://x.com/KaitoTrivunk/status/2110996033849458834,1736926616859901952,KaitoTrivunk
2110996028317188361,2026-10-16T07:27:28.000Z,3,"saran buat pak prabowo 
untuk kali ini ulang tahun nya di rayakan secara tertutup aja pak + jangan di dokumentasikan 
kondisi lagi begini aslii dahh
kalo sampe di live in gokill sihh anjirrr

ini foto ultah ke 74 
ntar malam beliau usai 75 https://t.co/v5iHQsXfOd",2110996028317188361,https://pbs.twimg.com/media/HUvDZwtaIAA1KGI.jpg,,in,,0,1,0,https://x.com/LambeSahamjja/status/2110996028317188361,1772323119111487490,LambeSahamjja
2110920475388133526,2026-10-16T07:27:23.000Z,0,"@Xliner_beright @pbrgmn @IDX_BEI kan sebelum ngutang bakal di analisis dulu sama tim credit analyst, ya ini yg ngutang si haji yg punya kalimantan assetnya banyak pasti di approve

sebenernya model gini umum, kaya glazer ambil alih united pake model gini, tp masalah UTAMA BYAN di PAKSA jual kl ga gbs jualan",2110996008738189812,,Xliner_beright,in,,0,0,0,https://x.com/zfhorsed/status/2110996008738189812,1780949657323274240,zfhorsed
2110917689661333790,2026-10-16T07:27:23.000Z,0,@damuhsin_ @prabowo Lonte ratau suntik,2110996007584743473,,damuhsin_,in,,0,0,0,https://x.com/attithuts/status/2110996007584743473,868583954,attithuts
2110995994699784653,2026-10-16T07:27:20.000Z,0,Bilang ke prabowo ngentot,2110995994699784653,,,in,,0,0,0,https://x.com/_xxxxcxxxx_/status/2110995994699784653,1908047706511347712,_xxxxcxxxx_
2110915370983027030,2026-10-16T07:27:16.000Z,1,@gnrlfans @persib Persib mah kan masih 1 gerbong sama erick thohir ama kdm masih masuk pemerintahan prabowo jdi wajarlah ga posting,2110995978979578279,,gnrlfans,in,,0,1,0,https://x.com/YEJinny__/status/2110995978979578279,1317043996460380168,YEJinny__
2110995977545109679,2026-10-16T07:27:16.000Z,2,BRAVOO PRABOWO MEMBAWA INDONESIA SETARA DENGAN ZIMBABWE 👏👏,2110995977545109679,,,in,,0,1,0,https://x.com/jenostalker/status/2110995977545109679,1885318915498401796,jenostalker
2110995955810254970,2026-10-16T07:27:10.000Z,0,"Halo, SahabatBahsa!

Balai Bahasa Provinsi Kalimantan Selatan (BBPKS) melaksanakan studi tiru pengelolaan Pejabat Pengelola Informasi dan Dokumentasi (PPID) serta sarana dan prasarana pendukung pembangunan Zona Integritas menuju Wilayah Bebas dari Korupsi (ZI-WBK) di https://t.co/1iZNGA3GyN",2110995955810254970,https://pbs.twimg.com/media/HUvDnWkaEAA1q5-.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110995955810254970,700676990722924544,balaibhskalsel
2110995936914948113,2026-10-16T07:27:06.000Z,0,"Proses evakuasi seekor orangutan betina bernama Ira berlangsung dramatis, saat petugas berhasil menyelamatkannya dari kawasan bekas karhutla di Jalan Cilik Riwut, Kabupaten Kotawaringin Timur, Kalimantan Tengah, pada Rabu (14/10). 

Editor : Imam Rifqi Wicaksono

#IDNTimesKaltim https://t.co/Bs2vUYmRYg",2110995936914948113,https://pbs.twimg.com/amplify_video_thumb/2110995869613076480/img/RmXTLUqitJIyXpwO.jpg,,in,,0,0,0,https://x.com/IDNTimesKaltim/status/2110995936914948113,1318854352069554177,IDNTimesKaltim
2110995934717128814,2026-10-16T07:27:05.000Z,0,"Jare koe ameh ultah @prabowo .
Yo di tiup genine nganti padam kae 🫵",2110995934717128814,,,in,,0,0,0,https://x.com/Tweetofpian/status/2110995934717128814,1195193060688183296,Tweetofpian
2110913992386600989,2026-10-16T07:26:51.000Z,0,"@vizanya12 bismillah semoga saudara-saudara kita yang terdampak kebakaran hutan diberikan keselamatan, tempat berlindung yang aman, dan bantuan yang cukup. semoga para petugas juga selalu dilindungi dan kebakaran segera teratasi. aamiin 🤲🏻",2110995875761664447,,vizanya12,in,,0,0,0,https://x.com/taevelours95/status/2110995875761664447,1775638388672237568,taevelours95
2110995846129205507,2026-10-16T07:26:44.000Z,0,"Sebenarnya baru tadi mlm kesel lagi

Org manual jnt ke ak ongkirnya selalu 15-25 kl udh diskon

Lah giliran jawa ke kalimantan, 30k sama diskonnya, fak kata gw",2110995846129205507,,,in,,0,0,0,https://x.com/Hanasakikirari/status/2110995846129205507,755973333825441793,Hanasakikirari
2110995843105108266,2026-10-16T07:26:44.000Z,0,"sumpah ini jadi dosa besar buat antek antek nya si wowo, bikin kebakaran, banjir, orang orang kena ISPA, dan bikin orang kewalahan gara gara antri BBM 

#IndonesiaButuhOksigen https://t.co/trNgHST6w9",2110995843105108266,https://pbs.twimg.com/amplify_video_thumb/2110720995829178368/img/pRDKm5qOXvOcAagZ.jpg,,in,,0,1,0,https://x.com/sweetzhra/status/2110995843105108266,1573701529185312768,sweetzhra
2110995836033438099,2026-10-16T07:26:42.000Z,0,"UDAH GA ADA ACTION BUAT NANGANI BENCANA KEBAKARAN HUTAN DAN LAHAN, UP DI MEDIA PUN SUARA RAKYAT DIBUNGKAM

SIAPA LAGI KALO BUKAN KELAKUAN PRABOWO ANJING",2110995836033438099,,,in,,0,0,0,https://x.com/syalaamore/status/2110995836033438099,1791493821714604032,syalaamore
2110995828580171892,2026-10-16T07:26:40.000Z,0,"KABUT ASAP MAKIN PEKAT, PENERBANGAN BANDARA MALIKUSSALEH LUMPUH 3 HARI!

Kabut asap akibat kebakaran hutan dan lahan (karhutla) berdampak pada aktivitas penerbangan di Bandara Malikussaleh, Aceh Utara. https://t.co/7rj3skaPRL",2110995828580171892,https://pbs.twimg.com/media/HUvDg36aEAADyYD.jpg,,in,,0,0,0,https://x.com/tribungayo_ofc/status/2110995828580171892,1606555181453565952,tribungayo_ofc
2110995820309078513,2026-10-16T07:26:38.000Z,0,"time ni jgn dulu yang lek lu yang, jerebu yang😭😭 aku kesian dgn kawan aku kat indo maki prabowo bangang tu",2110995820309078513,,,in,,0,0,0,https://x.com/rawrraberry/status/2110995820309078513,1577297861016170496,rawrraberry
2110995795470405981,2026-10-16T07:26:32.000Z,0,Giliran ngebungkam kyk gini aja cepet. ngurusin kebakaran dan korban bencana mesti ngu berbulan-bulan wkwk,2110995795470405981,,,in,,0,0,0,https://x.com/itsvi_laaaa/status/2110995795470405981,1263828020378218498,itsvi_laaaa
2110995724985077802,2026-10-16T07:26:15.000Z,0,coba dia aja yg dilempar kesana ketengah hutan kebakaran,2110995724985077802,,,in,,0,0,0,https://x.com/itravenn/status/2110995724985077802,1905600419562438657,itravenn
2110995687156666461,2026-10-16T07:26:06.000Z,0,prabowo and the hambalang botiboys mana mau liat ginian😭😭😭,2110995687156666461,,,in,,0,0,0,https://x.com/rahmadeux/status/2110995687156666461,39171760,rahmadeux
2110233776500420895,2026-10-16T07:26:03.000Z,0,@indepenSumatera Kalimantan udh biasa bgini,2110995672635757021,,indepenSumatera,in,,0,0,0,https://x.com/Gomupapel/status/2110995672635757021,1477685365339090949,Gomupapel
2110890970200072517,2026-10-16T07:25:58.000Z,0,"@icukprayogi Kalo untuk kalangan elit ga peduli, cuma di grassroot itu perlu dipecah fokusnya. Apalagi suara2 bawah udah mulai ga percaya Prabowo wkwk

Makanya kenapa banyak elit2 yg diajak masuk kabinet, karena untuk mengamankan 2029 full power buat ngelawan Oslo",2110995650490077671,,icukprayogi,in,,0,0,0,https://x.com/piscokgede/status/2110995650490077671,1128315888480899073,piscokgede
2110571116632883465,2026-10-16T07:25:57.000Z,0,@TheCurut007 Hehehe.. ngeles. Setelah 3 bulan akhirnya matane Prabowo melek.,2110995647323128143,,TheCurut007,in,,0,0,0,https://x.com/indah_suwondo/status/2110995647323128143,1638814473476612096,indah_suwondo
2110995641573019738,2026-10-16T07:25:56.000Z,0,That one istri gubernur di Kalimantan,2110995641573019738,,,in,,0,0,0,https://x.com/callmepollo_/status/2110995641573019738,1550875386770120705,callmepollo_
2110981300706501077,2026-10-16T07:25:51.000Z,0,@its__Arthur19 @prabowo Ada kepentingan adiknya disana,2110995623722053641,,its__Arthur19,in,,0,0,0,https://x.com/bagindo_kopi/status/2110995623722053641,1091031753924403200,bagindo_kopi
2110266976090419365,2026-10-16T07:25:51.000Z,0,@rkmndsfilm @prabowo Pemerintah sudah mengerahkan water bombing dan personel. Jangan menutup mata pada upaya yang sudah dilakukan,2110995622719635762,,rkmndsfilm,in,,0,0,0,https://x.com/padriansyah952/status/2110995622719635762,1927094848470855680,padriansyah952
2110995614872035499,2026-10-16T07:25:49.000Z,0,Kebakaran hutan X kebakaran porto 🔥,2110995614872035499,,,in,,0,0,0,https://x.com/Rofiqkurnia/status/2110995614872035499,195214439,Rofiqkurnia
2110995531719954656,2026-10-16T07:25:29.000Z,0,indogsat skrg 7GB/28 hari udah 37-38k coba 🤣🤣 prabowo memek tai kotok bangsat,2110995531719954656,,,in,,0,1,0,https://x.com/25300501s/status/2110995531719954656,1796842705257185280,25300501s
2110919591648190665,2026-10-16T07:25:17.000Z,0,@Ndrewstjan @prabowo (((kondisi terbaik))),2110995478926229531,,Ndrewstjan,in,,0,0,0,https://x.com/azibij/status/2110995478926229531,229334657,azibij
2110995469979812303,2026-10-16T07:25:15.000Z,4,kalo ga kebakaran lahan ya kebakaran pemukiman😭 sumpah takut bgt soalnya disini tuh pemukimannya rapet bgt yg rumah antar rumah tuh nempel😭😭 https://t.co/GW4Q13FkWv,2110995469979812303,https://pbs.twimg.com/media/HUvDMHZbgAAhcQy.jpg,,in,,0,0,0,https://x.com/p8dripepi/status/2110995469979812303,1856901056992874498,p8dripepi
2109906681568379086,2026-10-16T07:25:14.000Z,0,@bacaskskuning coba ditengok juga berapa hektar lahan konsesi milik prabowo yang 'terbakar' di Kalimantan sana.,2110995466536292449,,rolladewarteg,in,,0,0,0,https://x.com/rolladewarteg/status/2110995466536292449,1075930207700144128,rolladewarteg
2110995463906513327,2026-10-16T07:25:13.000Z,0,Dapet sebotol aquiviva ini sih...,2110995463906513327,,,in,,0,1,0,https://x.com/kelixmann/status/2110995463906513327,1425377301953277953,kelixmann
2110995462119641442,2026-10-16T07:25:13.000Z,0,Sumpah yg selalu nyampein berita hoax alias dimanip baik² ttg kondisi indonesia ke prabowo semoga bantal lu selalu panas lebih panas dari kondisi kahutla saat ini,2110995462119641442,,,in,,0,0,0,https://x.com/lafwons/status/2110995462119641442,1108520968081661952,lafwons
2110971568264466450,2026-10-16T07:25:11.000Z,1,"@cfmomski @karinyoo Ya Allah andai aku bisa kirim, aku kirim gratis aja kak ke kalimantan😭",2110995456948146599,,cfmomski,in,,0,0,0,https://x.com/bobbateas/status/2110995456948146599,181133374,bobbateas
2110962379085500847,2026-10-16T07:25:09.000Z,0,@memorosie @kumamoriee @prabowo eh setuju,2110995448551096559,,memorosie,in,,0,0,0,https://x.com/itafushiicanon/status/2110995448551096559,1939186189917159424,itafushiicanon
2110983227062243631,2026-10-16T07:25:05.000Z,0,@clavinjune Prabowo tidak berhenti di asap,2110995429294846059,,clavinjune,in,,0,0,0,https://x.com/hamardikan/status/2110995429294846059,1794672659986530304,hamardikan
2110770933162234039,2026-10-16T07:25:03.000Z,0,@tham878 Si doi lebih heran dgn ijazah jokowi ketimbang kondisi negara ini pasca terpilihnya prabowo,2110995419757240402,,tham878,in,,0,0,0,https://x.com/AlbaSanto_/status/2110995419757240402,1409740738829504515,AlbaSanto_
2110995419526468001,2026-10-16T07:25:03.000Z,0,"Kabut asap akibat kebakaran hutan dan lahan bukan hanya  disebakan dari  Indonesia, tetapi juga menjadi masalah lintas negara di Asia Tenggara malasya dan singapura. https://t.co/nvv8Rt77ad",2110995419526468001,https://pbs.twimg.com/amplify_video_thumb/2110995327482515456/img/2HA0Txw33Fyq_c3B.jpg,,in,,1,0,0,https://x.com/Rifkipu62641451/status/2110995419526468001,1906039917832228864,Rifkipu62641451
2110976232053785014,2026-10-16T07:24:57.000Z,0,"@LambeSahamjja Ga kepala, ga anak buahnya prabowo goblok kabeh. Apa² ko yo nyalaha osang aseng. Dibayar go pajake rakyat ko yo ra ngutek, dol wae uteke pak.",2110995395010850869,,LambeSahamjja,in,,0,0,0,https://x.com/bisayukbisa_/status/2110995395010850869,1588197462816481281,bisayukbisa_
2110654264821387430,2026-10-16T07:24:55.000Z,0,@tempodotco Parah wo @prabowo kaga nyampe 11 masa wo cuma 5,2110995389814039029,,tempodotco,in,,0,0,0,https://x.com/zbeomi/status/2110995389814039029,1016511387734949889,zbeomi
2110995378208399581,2026-10-16T07:24:53.000Z,0,"Kesihatan rakyat perlu menjadi keutamaan. Tindakan pencegahan kebakaran hutan dan tanah gambut wajar diperkukuh bagi mengurangkan risiko pencemaran udara yang boleh menjejaskan kesihatan masyarakat.
https://t.co/9gcz9OdGui",2110995378208399581,,,in,,0,0,0,https://x.com/JadIzzuddin/status/2110995378208399581,1548842035372691456,JadIzzuddin
2110995375574368549,2026-10-16T07:24:52.000Z,0,"Suram bgst porto minus 40%
Kerja yg bener lah @prabowo org luar aja bs liat bobroknya tata kelola negara di SEMUA ASPEK",2110995375574368549,,,in,,0,0,0,https://x.com/MR_XYZOO/status/2110995375574368549,432707526,MR_XYZOO
2110995369257742610,2026-10-16T07:24:51.000Z,0,"Keluarga Besar Balai Bahasa Provinsi Kalimantan Selatan dan Kemendikdasmen mengucapkan selamat dan sukses atas pelantikan Bapak Hidayat Widiyanto, S.S., M.Pd. sebagai Kepala Pusat Pembinaan Bahasa dan Sastra, Badan Pengembangan dan Pembinaan Bahasa. https://t.co/lmZasFHqVR",2110995369257742610,https://pbs.twimg.com/media/HUvDF8JboAA2xso.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110995369257742610,700676990722924544,balaibhskalsel
2110995345970962719,2026-10-16T07:24:45.000Z,1,"Diduga Terpapar Asap Karhutla Bocah 6 Tahun di Kalbar Meninggal Dunia

SEORANG bocah berusia 6 tahun berinisial A, warga Kecamatan Sukadana, Kalimantan Barat, meninggal dunia setelah mengalami ISPA yang diduga akibat Karhutla.

Anak perempuan itu meninggal setelah menjalani https://t.co/yeUIKgGAVe",2110995345970962719,https://pbs.twimg.com/amplify_video_thumb/2110995043163209728/img/3_vfeeV0ryeduWnn.jpg,,in,,0,0,1,https://x.com/mediaindonesia/status/2110995345970962719,68930552,mediaindonesia
2110988637517312076,2026-10-16T07:24:41.000Z,0,@lunaticzt Kabur asap sudah di selatan kalimantan,2110995327935517043,,lunaticzt,in,,0,0,0,https://x.com/Peterlafan/status/2110995327935517043,2613611785,Peterlafan
2110915370983027030,2026-10-16T07:24:22.000Z,0,@gnrlfans @persib CEO Persib punya kepentingan bisnis di Kalimantan si glen ... FYI,2110995248226897972,,gnrlfans,in,,0,1,0,https://x.com/tukangtwittter/status/2110995248226897972,1244673152166182912,tukangtwittter
2110976797093605578,2026-10-16T07:24:12.000Z,0,"@OrizaSativa_1 Gak hutan gak ihsg, KEBAKARAN SEMUAAAA",2110995208976654685,,OrizaSativa_1,in,,0,1,0,https://x.com/LingOrmFaen/status/2110995208976654685,1812701039302512640,LingOrmFaen
2110995196687360374,2026-10-16T07:24:09.000Z,3,"kualitas udara di palembang, jambi, dan sampit (kalimantan tengah) sekarang menempati tiga peringkat teratas dalam daftar kota dengan tingkat pencemaran udara tertinggi di dunia. 

sekali lagi, di dunia. https://t.co/Blcg9LJC9h",2110995196687360374,https://pbs.twimg.com/media/HUvC6lSaIAAuQ4S.jpg,,in,,0,1,1,https://x.com/gfheeez/status/2110995196687360374,1416030028173742085,gfheeez
2110995173794795730,2026-10-16T07:24:04.000Z,0,"Keluarga Besar Balai Bahasa Provinsi Kalimantan Selatan dan Kemendikdasmen mengucapkan selamat dan sukses atas pelantikan Bapak Dony Setiawan, S.S., M.Pd. sebagai Kepala Pusat Pemberdayaan Bahasa dan Sastra, Badan Pengembangan dan Pembinaan Bahasa. https://t.co/TVDHOeBSlA",2110995173794795730,https://pbs.twimg.com/media/HUvC6mZaYAALUxd.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110995173794795730,700676990722924544,balaibhskalsel
2110882452478792081,2026-10-16T07:24:02.000Z,2,"@julpamiaw TAPI YAAA, gue banyak baca pernyataan ""milih prabowo krn gibrannya"" maksud gue ya.... gibran.... krn gibran tuh... 😭",2110995163476906384,,julpamiaw,in,,0,0,0,https://x.com/zbeomi/status/2110995163476906384,1016511387734949889,zbeomi
2110893974357770322,2026-10-16T07:23:59.000Z,1,@AdiSapu19153274 @MafiaWasit CEO Persib punya bisnis di Kalimantan 🫢🫢🫢 si glen,2110995152093499804,,AdiSapu19153274,in,,0,0,0,https://x.com/tukangtwittter/status/2110995152093499804,1244673152166182912,tukangtwittter
138948254804099072,2026-10-16T07:23:54.000Z,0,@prabowo @Gerindra Hidup makin hari makin susah  lihat kelapangan ke pasar-pasar udah banyak yg tutup gara2 sepi,2110995130731962557,,prabowo,in,,0,0,0,https://x.com/ChaniagoJa62786/status/2110995130731962557,1666323305513771011,ChaniagoJa62786
2110995129310069187,2026-10-16T07:23:53.000Z,1,Kebakaran hutan itu warisan lintas kepemimpinan yang dimulai dari masa Orde Baru dan terus berlanjut hingga sekarang. Kita gak pernah memiliki pemimpin yang punya perspektif lingkungan. Hutan selalu dialihfungsikan atas nama pembangunan tanpa pernah dipulihkan ekosistemnya.,2110995129310069187,,,in,,0,1,0,https://x.com/dimzsky_/status/2110995129310069187,1326879014150164483,dimzsky_
2110995104685281453,2026-10-16T07:23:48.000Z,0,"Innalilah wa innailaihi rojiun, mau sampai kapan ini @prabowo?",2110995104685281453,,,in,,0,0,0,https://x.com/aud_zka/status/2110995104685281453,2371502659,aud_zka
2110995059013464238,2026-10-16T07:23:37.000Z,0,"Demi Negara....
Juga utk Kesehatan Mental Warga Negara
Setiap hari disuguhi Keboiongan², Masalah² yg Orgnya itu² aja
.
Reshuffle Kabinet, Rocky Gerung: Prabowo Harus Putus Perjanjian Politik dengan Jokowi | ROSI https://t.co/xFPtqrBkSv",2110995059013464238,,,in,,0,0,0,https://x.com/Na_T1N4/status/2110995059013464238,174453386,Na_T1N4
2110578549057098144,2026-10-16T07:23:24.000Z,0,"@PatubMbel while(prabowo!=waras){Console.WriteLine(""Pemrentah ASU"");}",2110995007012585935,,PatubMbel,in,,0,0,0,https://x.com/bangunnagoro/status/2110995007012585935,206679796,bangunnagoro
2110933612535357533,2026-10-16T07:23:23.000Z,0,"@edzsamudra halah tai kucing dr jaman dulu apalagi jaman sby 2015 paling parah, mau ganti presiden 100 kali tetep aj itu kebakaran hutan tiap tahun, kami di kalimantan udah basi ngisep asep kebakaran hutan udah agenda tahunan pemerintah daerah",2110995002386198827,,edzsamudra,in,,0,0,0,https://x.com/iMadeSlowly/status/2110995002386198827,1229417931651444737,iMadeSlowly
2110994974552854981,2026-10-16T07:23:16.000Z,0,Pak Prabowo besok ulang tahun guys. Kalian mau kasih kado apa ?,2110994974552854981,,,in,,0,0,0,https://x.com/rahmadsaifulhs/status/2110994974552854981,4600958176,rahmadsaifulhs
2110994776560447537,2026-10-16T07:23:15.000Z,0,"Lawangan–Indonesia.
Melalui kegiatan pendampingan ini, diharapkan penyusunan kamus di Balai Bahasa Provinsi Kalimantan Selatan semakin terarah dan berkualitas serta mendukung upaya pendokumentasian dan pelindungan bahasa daerah di Provinsi Kalimantan Selatan.",2110994966621429793,,balaibhskalsel,in,,0,0,0,https://x.com/balaibhskalsel/status/2110994966621429793,700676990722924544,balaibhskalsel
2109906681568379086,2026-10-16T07:23:14.000Z,0,@bacaskskuning yash bagus kalau dulu ikut menyuarakan penentangan ke PT TPL. sekarang? mengundang presiden yang ga ambil tindakan jelas ketika hutan kalimantan terbakar? coba diliat juga itu hubungan ephorus sama adik prabowo yang bilang mau tanam sawit di lahan terbakar. . https://t.co/OP2OneQZZr,2110994965186908310,https://pbs.twimg.com/media/HUvCuv2bEAAmm9i.jpg,bacaskskuning,in,,0,2,0,https://x.com/rolladewarteg/status/2110994965186908310,1075930207700144128,rolladewarteg
2110927199083638890,2026-10-16T07:23:14.000Z,0,@NyaiNeneng @MerahPetrus @PanglimaJilah kenapa tidak bersuara ketika ada kebakaran hutan?,2110994962825490731,,NyaiNeneng,in,,0,0,0,https://x.com/indah_suwondo/status/2110994962825490731,1638814473476612096,indah_suwondo
2110994947801518153,2026-10-16T07:23:10.000Z,1,"Buzzer bilang, “Pak Prabowo itu ahli strategi.”

Strategi apaan, Zer? Coba lihat ini dulu??? 😭 https://t.co/CnCVI0MrOy",2110994947801518153,https://pbs.twimg.com/media/HUvCr2NbMAAPnvW.jpg,,in,,0,0,1,https://x.com/atokdalangs4/status/2110994947801518153,2059977246853705728,atokdalangs4
2110994776560447537,2026-10-16T07:23:10.000Z,0,"Evaluasi Kamus Mini Bergambar Bidang Pertanian dan Perairan Karya Mahasiswa Magang dari Universitas PGRI Kalimantan (UPK).
Pada hari kedua, kegiatan difokuskan pada evaluasi hasil inventarisasi kosakata bahasa Lawangan sebagai bagian dari proses penyusunan Kamus Dwibahasa",2110994946820116987,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110994946820116987,700676990722924544,balaibhskalsel
2110943822649659622,2026-10-16T07:22:57.000Z,0,@fjrwo mantap wo keren bgt prabowo,2110994892080185860,,fjrwo,in,,0,0,0,https://x.com/manhaveataste/status/2110994892080185860,2052789254703689728,manhaveataste
2110732178837602642,2026-10-16T07:22:57.000Z,0,@susipudjiastuti @prabowo Susah bu...serba Omon2..,2110994890800734213,,susipudjiastuti,in,,0,0,0,https://x.com/ABudhantar72548/status/2110994890800734213,1863431443726360576,ABudhantar72548
2110994885579059487,2026-10-16T07:22:55.000Z,0,Gerak Cepat Tim Damkar Lanud SKI Hadapi Informasi Kebakaran https://t.co/oWAJhJGar7,2110994885579059487,https://pbs.twimg.com/media/HUvCmK4a4AABbfS.jpg,,in,,0,0,0,https://x.com/sugirisukani/status/2110994885579059487,1270547290936102913,sugirisukani
2110994882160709783,2026-10-16T07:22:54.000Z,0,siapapun pls culik bunted ke kalimantan biar jd bencana nasional,2110994882160709783,,,in,,0,0,0,https://x.com/miookbarusadar/status/2110994882160709783,1473192384078827520,miookbarusadar
2110994871939211494,2026-10-16T07:22:52.000Z,1,"Tidak akan terjadi perubahan besar jika di pulau jawa tidak merasakan seperti yang terjadi di papua, kalimantan, sumatera &amp; bali.

Jawa adalah Koentji.",2110994871939211494,,,in,,0,0,0,https://x.com/Bgssgb_/status/2110994871939211494,1445747060871872513,Bgssgb_
2110994776560447537,2026-10-16T07:22:50.000Z,0,"Universitas PGRI Kalimantan (UPK), dengan pendampingan dari Tim Kamus dan Istilah Pusat Pengembangan dan Pelindungan Bahasa dan Sastra (Pusbanglin).
Kegiatan ini bertujuan untuk meningkatkan kualitas penyusunan kamus bahasa daerah melalui penguatan pemahaman teknis, evaluasi",2110994861881274379,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110994861881274379,700676990722924544,balaibhskalsel
2110933612535357533,2026-10-16T07:22:43.000Z,0,"@edzsamudra Karena Prabowo, bahkan kita skrg merasa Jokowi dan semua presiden sebelumnya itu baik"" saja
Kecuali mungkin mertuanya",2110994835352256685,,edzsamudra,in,,0,0,0,https://x.com/Hiro28146303/status/2110994835352256685,1445348285934305284,Hiro28146303
2110920304256241801,2026-10-16T07:22:31.000Z,1,"@LambeSahamjja itu kmrn ada utas 'knp ga spik up, krn takut atau gimana' NIH BUKA MATA LO SIALAN!! bg windah yg namanya gede aja kena pressure dr buzzer yg siap nyerang keluarganya, lah kita yg  gada nama?? LENYAP BOSS, negara gendeng",2110994784580243750,,LambeSahamjja,in,,0,0,0,https://x.com/aethernalangel/status/2110994784580243750,2018530933377466368,aethernalangel
2110994783338729936,2026-10-16T07:22:31.000Z,0,eh si wowo gimana sih ini yaAllah. JAHAT BGTT SEMUA NYAA. fak of deh yg kmrn nyoblos prabowo dgn alasan yg gamasuk akal,2110994783338729936,,,in,,0,0,0,https://x.com/astagaangerinya/status/2110994783338729936,1433840174459277313,astagaangerinya
2110994776560447537,2026-10-16T07:22:29.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan kegiatan Pendampingan Penyusunan Kamus pada 13 dan 14 Oktober 2026. Kegiatan ini diikuti oleh Tim Kerja Pengembangan Bahasa dan Sastra Balai Bahasa Provinsi Kalimantan Selatan dan mahasiswa magang dari https://t.co/BKATu1Lb7B",2110994776560447537,https://pbs.twimg.com/media/HUvCieIbMAAxod0.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110994776560447537,700676990722924544,balaibhskalsel
2110900774016540965,2026-10-16T07:22:24.000Z,0,"@jhonsitorus_19 Tanya @KemensetnegRI @setkabgoid dulu Bang @jhonsitorus_19 
apakah gerombolan @psi_id di @kemenhut_ri masih digaji?masih berguna?

Lebih baik gaji gerombolan itu diberi ke relawan atau ke @Puspen_TNI @DivHumas_Polri yang turut serta berjuang

Setuju @prabowo @puanmaharani_ri ? https://t.co/m0uZPNd1uT",2110994753013878882,https://pbs.twimg.com/media/HUvCh53aMAAEmhc.jpg,jhonsitorus_19,in,,0,0,0,https://x.com/horastondi03/status/2110994753013878882,1750817457798082560,horastondi03
2110690311139983870,2026-10-16T07:20:09.000Z,0,"@Kimberley_PS08 Apa itu jokowi, ijazah gak jelas... lihat dong prabowo lengkap dan terbukti hebat. Indonesia per hari ini dlm kondisi terbaik berkat tangan emas prabowo. No debat pokoknya... 🥱",2110994190003818776,,Kimberley_PS08,in,,0,0,0,https://x.com/AlbaSanto_/status/2110994190003818776,1409740738829504515,AlbaSanto_
2110673163814375564,2026-10-16T07:20:01.000Z,0,"@indepenSumatera Puan mirip Mega
AHY mirip SBY
Tomy mirip Soeharto
Yenny mirip Istrinya Gusdur
Ilham mirip Habibie
Didit mirip Prabowo
Gibran mirip siapa pasti beda DNA dengan Jokowi.",2110994153761112151,,indepenSumatera,in,,0,0,0,https://x.com/azfar_tamsil/status/2110994153761112151,1791799188961046528,azfar_tamsil
2110994143317242011,2026-10-16T07:19:58.000Z,0,kok bisa prabowo jadi manusia,2110994143317242011,,,in,,0,0,0,https://x.com/griseunbi/status/2110994143317242011,441816730,griseunbi
2110994131732586816,2026-10-16T07:19:56.000Z,0,WEEEYY KELAKUAN LU LEBIH DARI SETAN! @prabowo https://t.co/blZyVtl4WD,2110994131732586816,https://pbs.twimg.com/media/HUvB-BCaoAEbSoG.jpg,,in,,0,0,2,https://x.com/KanayakanSC/status/2110994131732586816,1857009042515742720,KanayakanSC
2110953377194746018,2026-10-16T07:19:45.000Z,1,"@GusDikaOfficial Iya gpp, kasihan gajah Otan dan hewan2 lainnya. Mau ikut malay or Singapore gpp deh, yg penting seluruh penghuni kalimantan sehat bahagia. 
Lagu bisa diubah, sejarah bisa d ubah. Tapi sakit kalian yg rasa,,,",2110994087935639963,,GusDikaOfficial,in,,0,0,0,https://x.com/ItsMeEka131/status/2110994087935639963,1420626267791974403,ItsMeEka131
2110994060957859858,2026-10-16T07:19:39.000Z,0,"Balai Wilayah Sungai (BWS) Kalimantan II melalui Tim UPI Dadahup melaksanakan penanganan kekeringan lahan.
Penanganan dilakukan melalui pemompaan air dari saluran sekunder menggunakan 1 unit mobil pompa berkapasitas 250 liter/detik untuk mengairi lahan seluas kurang lebih 1 ha. https://t.co/RgZF3FWOZF",2110994060957859858,https://pbs.twimg.com/media/HUvBxUqbkAA_xoe.jpg,,in,,0,0,0,https://x.com/pu_sda_kal2/status/2110994060957859858,1631615281859821568,pu_sda_kal2
2110994060429172984,2026-10-16T07:19:39.000Z,0,Padahal kemaren sama malam hujan deras sampai berpetir tapi hari ini asapnya masih tebal banget 😞 apalagi yang di Kalimantan ya,2110994060429172984,,,in,,0,1,0,https://x.com/maysochist/status/2110994060429172984,1046451443685687297,maysochist
2110964536862024084,2026-10-16T07:19:38.000Z,1,"@splittheatoom Tapi gosip di kalangan plantation mereka kaya cacing kepanasan di jaman Prabowo, karena beredar kabar bahwa Sinarmas melepas saham mereka di awal 2026 ke group yang terafiliasi dengan mereka. 

Ini kan membuat pembuktian makin sulit karena menambah jumlah nominee",2110994059724788215,,splittheatoom,in,,0,1,0,https://x.com/Big83717Dude/status/2110994059724788215,2029516685393510400,Big83717Dude
2110994050551890136,2026-10-16T07:19:36.000Z,0,"Orang orang tolol itu bukannya bikin program atau kebijakan yang baik di saat carut marutnya keadaan indonesia, ehh tiap kementrian sibuk buat video seolah di bawah kepemimpunan prabowo indonesia membaik,",2110994050551890136,,,in,,0,0,0,https://x.com/Gunadi____/status/2110994050551890136,1102195438940119040,Gunadi____
2110994044172321237,2026-10-16T07:19:35.000Z,0,Prabowo Mati aja,2110994044172321237,,,in,,0,0,0,https://x.com/CRASHBR41N/status/2110994044172321237,1277473771981430785,CRASHBR41N
2110994011318350240,2026-10-16T07:19:27.000Z,0,"kebakaran dimana"", literally dimana""..
sampe ihsg jg kebakaran, menyalaaa 🔥",2110994011318350240,,,in,,0,0,0,https://x.com/onlypho/status/2110994011318350240,62698233,onlypho
2110227310804918544,2026-10-16T07:19:21.000Z,0,"@karepmudeweeee @Kejeffreyan memang kak, di tiktok banyak koo yang naturally dongoo makanya aku herann, klo buzzer kan dibayar yaa, nah mereka sukarela bangga gitu membela prabowo😭",2110993985057784122,,karepmudeweeee,in,,0,0,0,https://x.com/thisfaa/status/2110993985057784122,1420307524520013827,thisfaa
2110993953571164298,2026-10-16T07:19:13.000Z,0,Yakin kamu mau diam saja jendral @prabowo ? Manusia rendahan ini yang nyata2 bawahanmu. Secara terang benderang telah menghinamu. Jiwa korsa ku menjerit pak presiden. Kasih aku AMANAT itu. Niscaya matahari besok adalah sesuatu yang sangat mahal bagi manusia ga tau diri ini.,2110993953571164298,,,in,,0,0,0,https://x.com/SangReal99/status/2110993953571164298,2037215824042483716,SangReal99
2110967930511053124,2026-10-16T07:19:12.000Z,0,@kucinghilang_ @prabowo mASIH KAAAK… lusa balik ke sanaa🫩🥀,2110993950391844977,,kucinghilang_,in,,0,0,0,https://x.com/nikiateh/status/2110993950391844977,1769051604429447168,nikiateh
2110993924999516633,2026-10-16T07:19:06.000Z,0,"IHSG drop
Karhutla Kalimantan dan Sumatra udah berbulan bulan
Batam blackout
Bali antrian BBM panjang
Kritik pemerintah langsung diserang buzzer
Wapres Gibran

Kuat kuat dah WNI !!",2110993924999516633,,,in,,0,0,0,https://x.com/achmadyusuft/status/2110993924999516633,730603485134127104,achmadyusuft
2110923358158340441,2026-10-16T07:19:02.000Z,0,@cellaurent negara prabowo dan teddy,2110993907949711566,,cellaurent,in,,0,0,0,https://x.com/yourbabytalk/status/2110993907949711566,2021475575358160906,yourbabytalk
2110993877431971890,2026-10-16T07:18:55.000Z,0,"vacation ke belitung bukannya hepi2 malah radicalized jir. ngeliat tambang dimana2, kekeringan, orang ngantri BBM sampe mobil ditinggal di pom bensin, lewatin lahan kebakar juga. asap dari kalimantan juga sampe ke sini walaupun gak gitu parah. memang pemerintah bajingan semua",2110993877431971890,,,in,,0,1,0,https://x.com/yuanst/status/2110993877431971890,47901092,yuanst
2110981300706501077,2026-10-16T07:18:53.000Z,0,@its__Arthur19 @prabowo Fokus MBG wehh,2110993870179717224,,its__Arthur19,in,,0,0,0,https://x.com/Mia_Kyushu/status/2110993870179717224,1345197460474318848,Mia_Kyushu
2110714601914466461,2026-10-16T07:18:50.000Z,0,@nocontextwindah windah ampe marah2 jir sumpah gapernah gw liat dia longtext kyk gitu di storynya emg rezim anjing prabowo anjing kontol dajjal,2110993855093018633,,nocontextwindah,in,,0,0,0,https://x.com/joszjis/status/2110993855093018633,1879358862790451200,joszjis
2109906681568379086,2026-10-16T07:18:46.000Z,0,@bacaskskuning press release terkait bencana lingkungan di Kalimantan sudah ada? bencananya sudah 3 bulan tapi sampai saat ini HKBP Pusat blm ada statement apa apa. Apa karena kejadiannya di Kalimantan bukan di Sumatera?,2110993841407009021,,bacaskskuning,in,,0,0,0,https://x.com/rolladewarteg/status/2110993841407009021,1075930207700144128,rolladewarteg
2110993835631489163,2026-10-16T07:18:45.000Z,0,gue adalah 1/283.270 orang itu 🥲 fuck you @prabowo,2110993835631489163,,,in,,0,0,0,https://x.com/rifaille/status/2110993835631489163,1871507789744676864,rifaille
2110993813162672175,2026-10-16T07:18:40.000Z,55,"❗️Update Bantuan Karhutla❗️

Saat ini kami sedang mempersiapkan Rumah Aman Asap ke-3 di Kalimantan

semoga semuanya dilancarkan dan bisa membantu warga yang terdampak kabut asap. 

doain yaa guys! 🤲",2110993813162672175,,,in,,0,0,24,https://x.com/humaniesproject/status/2110993813162672175,2086017777618628608,humaniesproject
2110993802022236358,2026-10-16T07:18:37.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan Rapat Evaluasi Pelaksanaan Program dan Anggaran Triwulan III Tahun 2026 pada 15 Oktober 2026 yang diikuti oleh seluruh pegawai. https://t.co/5vXbQNMTVn",2110993802022236358,https://pbs.twimg.com/media/HUvBp_IbsAI9_Bw.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110993802022236358,700676990722924544,balaibhskalsel
2110933612535357533,2026-10-16T07:18:36.000Z,0,"@edzsamudra jaditau kenapa pemerintah ABAI sama kebakaran lahan. yakni
1. Pemerintah cekak dana APBN maupun Cadanganya
2. Pemerintah malu buat minta bantuan ASEAN 
3. Pemerintah beraharap sudah mulai masuk musim penghujan.",2110993798214168864,,edzsamudra,in,,0,0,0,https://x.com/DhasamukaLokal/status/2110993798214168864,1150204117521850369,DhasamukaLokal
2110958714173984873,2026-10-16T07:18:30.000Z,0,"@unmagnetism awas kalo omon doang lu un, ntr kyk prabowo🙂‍↔️",2110993773933306354,,unmagnetism,in,,0,0,0,https://x.com/fnyraaaaaaa/status/2110993773933306354,1415179527240572934,fnyraaaaaaa
2110938133785370800,2026-10-16T07:18:28.000Z,0,"@AzzamIzzulhaq Apasih lebay amat jadi netizen dan sok paling ahli padami api, kalau memang  ahli atau mau cepat tuntas kebakaran hutan nih, langsung turun ke lapangan dan ikut padami tuh kebakaran, jangan asal bacot doank di mendsos, buktikan langsung... anak SD pun bisa cuma bacot doank.",2110993762755436814,,AzzamIzzulhaq,in,,0,0,0,https://x.com/lolegema/status/2110993762755436814,1908004508879433729,lolegema
2110993758678569309,2026-10-16T07:18:27.000Z,0,"Adili ibu dewi astutik !! Gembong Narkoba Republik Indonesia yang ditangkap waktu itu, jangan sampai rezim Jendral Haji Prabowo dan Haji Gibran di cap pelanggar HAM berat menangkap seseorang tapi tidak di adili sampai sekarang. kalau Kapolri tidak mampu mundur saja !!",2110993758678569309,,,in,,0,0,0,https://x.com/Partikellirs/status/2110993758678569309,1594732397492195330,Partikellirs
2110993758477316179,2026-10-16T07:18:27.000Z,0,ni orang ga cocok kalau dikatain rot in hell.. semoga rumahnya kebakaran dan dia ga bisa keluar,2110993758477316179,,,in,,0,0,0,https://x.com/rumpangan/status/2110993758477316179,950177501816352768,rumpangan
2110993756862488785,2026-10-16T07:18:26.000Z,1,"Kebakaran hutan udah jadi berita di mana-mana, rakyat pun udah teriak ke mana-mana. Pemerintah masih aja tutup mata melihat rakyat sengsara. Tutup telinga mendengar suara rakyat. Tutup mulut saat diminta bertanggung jawab. Lengkap udah ketidakpeduliannya. 

Tutup usia, kapan?",2110993756862488785,,,in,,0,0,0,https://x.com/olinlei/status/2110993756862488785,1785655415776407553,olinlei
2110979454310953367,2026-10-16T07:18:23.000Z,0,@pilarkeamanan Apresiasi buat personel yg sigap di tengah situasi kebakaran,2110993743465857158,,pilarkeamanan,in,,0,0,0,https://x.com/SuryanaWis83893/status/2110993743465857158,1701075217999962112,SuryanaWis83893
2110993743356756465,2026-10-16T07:18:23.000Z,0,keren banget prabowo,2110993743356756465,,,in,,0,0,0,https://x.com/TanInsideAhim/status/2110993743356756465,1264831959915622401,TanInsideAhim
2110869016550187027,2026-10-16T07:18:21.000Z,0,"@goPuudd jaditau kenapa pemerintah ABAI sama kebakaran lahan. yakni
1. Pemerintah cekak dana APBN maupun Cadanganya
2. Pemerintah malu buat minta bantuan ASEAN 
3. Pemerintah beraharap sudah mulai masuk musim penghujan.",2110993733730947229,,goPuudd,in,,0,0,0,https://x.com/DhasamukaLokal/status/2110993733730947229,1150204117521850369,DhasamukaLokal
2110979379572728090,2026-10-16T07:18:20.000Z,0,@pilarkeamanan Nah gini dong kepolisian tegas usut akar masalah kebakaran hutan kita,2110993731071693017,,pilarkeamanan,in,,0,0,0,https://x.com/QaylaAnindia/status/2110993731071693017,1319179947026518016,QaylaAnindia
2110979244893564946,2026-10-16T07:18:18.000Z,0,"@pilarkeamanan Biar fakta yang bicara, penyebab kebakaran harus dipastikan lewat penyelidikan",2110993724310520208,,pilarkeamanan,in,,0,0,0,https://x.com/feriantoarii/status/2110993724310520208,1699266519329566720,feriantoarii
2110993723450626364,2026-10-16T07:18:18.000Z,0,"Status bencana nasional bukan satu-satunya penentu kecepatan bantuan. Meski belum berstatus nasional, penanganan karhutla Kalimantan tetap melibatkan personel gabungan, pemadaman darat, hingga operasi udara. 
#KawalPenangananKarhutla #PemerintahBergerak https://t.co/EaLh44wzyQ",2110993723450626364,https://pbs.twimg.com/amplify_video_thumb/2110993692312182784/img/cQ5OVagjzoK02gFZ.jpg,,in,,0,0,0,https://x.com/sy_nch/status/2110993723450626364,1338128640597401600,sy_nch
2110993405606306154,2026-10-16T07:18:17.000Z,3,"peluang bantuan dari Malaysia dan negara tetangga.
10. Polisi sudah menetapkan ratusan tersangka terkait pembakaran lahan.
Kesimpulan singkat: 
Polusi CO dari kebakaran Indonesia masih aktif dan menyebar regional. Situasi masih kritis, meski upaya pemadaman ditingkatkan.",2110993717951893870,,Rahadi0816,in,,0,0,3,https://x.com/Rahadi0816/status/2110993717951893870,1611567480992043008,Rahadi0816
2110993714965619169,2026-10-16T07:18:16.000Z,0,not a single recent post about kalimantan @NarasiNewsroom @NajwaShihab ayo setajam covid dulu kritik nya https://t.co/ek2XXJEX5m,2110993714965619169,https://pbs.twimg.com/media/HUvBlwdbcAAmXJw.jpg,,in,,0,0,0,https://x.com/agusartaaa1/status/2110993714965619169,1432300358856962049,agusartaaa1
2110939022382309503,2026-10-16T07:18:13.000Z,0,"@JonghoJoestarr Inilah bodohnya kamu, saya hanya membandingkan Anies dan Prabowo, hanya karena kamu tidak puas, langsung menyimpulkan saya pendukung Prabowo. 

Pesan saya, jangan merendahkan rakyat karena kamu sendiri ternyata bukan orang berwawasan luas, tapi kok bisa menuduh close minded",2110993702340751680,,JonghoJoestarr,in,,0,0,0,https://x.com/frmsrgr/status/2110993702340751680,1638681500,frmsrgr
2110993678605197602,2026-10-16T07:18:13.000Z,0,"Intinya apa, disini sekali lagi pemerintahan prabowo-gibran gagal dalam penanggulangan bencana, buktinya adalah tidak dipenuhinya ketentuan2 pada undang2 tersebut
memang negara kita negara rawan bencana, tapi masyarakat berhak merasa aman apabila ada mitigasi dari pemerintah",2110993701124313268,,auliaakbaroi,in,,0,1,0,https://x.com/auliaakbaroi/status/2110993701124313268,1753052079277723648,auliaakbaroi
2110934681915122083,2026-10-16T07:18:04.000Z,1,@indepenSumatera Semua kon di kaitkan sama jokowi padahal prabowo sendiri yang tolol dan gak bisa jadi presiden,2110993665535656445,,indepenSumatera,in,,0,0,0,https://x.com/alumni_monas/status/2110993665535656445,1456372701459726337,alumni_monas
2110919591648190665,2026-10-16T07:18:02.000Z,0,@bukan4non @Ndrewstjan @prabowo Buzzer koplak tuh Don dasco udah bilang 5 kali Wowo ke solo minta Gibran jadi wakilnya,2110993653653237887,,bukan4non,in,,0,0,0,https://x.com/darmawan_paisal/status/2110993653653237887,1604359810199171075,darmawan_paisal
2110993653091139949,2026-10-16T07:18:01.000Z,0,"dia ini kayak kenalan ku juga, yang selalu bilang “kenapa sih apa apa nyalahin prabowo” dan heran nya adalah diaaa ituu lulusan s1 hukummmm???? kokk otak nya gak dipake mikirr yaa😭💔",2110993653091139949,,,in,,0,0,0,https://x.com/thisfaa/status/2110993653091139949,1420307524520013827,thisfaa
2110993652495638920,2026-10-16T07:18:01.000Z,13,"kabinet bengkak, wantimpres seabrek, tapi ngasih statement kalo kebakaran di kalimantan krn ring of fire. AWOWKWK PEKOKKKK. ring of fire itu kawasan dgn aktivitas tektonik dan vulkanik. kalimantan bukan wilayah jalur vulkanik aktif. jgn terlalu dihubung2kan. mentang2 ada firenya.",2110993652495638920,,,in,,0,0,2,https://x.com/thenggara/status/2110993652495638920,2016709097119477760,thenggara
2110993405606306154,2026-10-16T07:17:52.000Z,3,"gambut yang sulit dipadamkan.
4. Luas lahan terbakar: perkiraan independen hampir 900.000 hektar.
5. Emisi kebakaran Indonesia menjadi yang tertinggi di dunia dalam sebulan terakhir.
6. Kasus gangguan pernapasan di 7 provinsi Indonesia melebihi 283.000.
Polusi udara di Kalimantan",2110993615334093034,,Rahadi0816,in,,0,0,3,https://x.com/Rahadi0816/status/2110993615334093034,1611567480992043008,Rahadi0816
2110993610221183252,2026-10-16T07:17:51.000Z,0,"ya Allah ga tega bgt liat bapaknya keinget bapak gw sendiri, ga pake masker pg si bapak ya Allah, yg kuat yaa pak dan semua masyarakat Kalimantan😢😭",2110993610221183252,,,in,,0,0,0,https://x.com/stfugthlol/status/2110993610221183252,2016454414933123072,stfugthlol
2110993603871076819,2026-10-16T07:17:50.000Z,0,"onee-san, kalo Indonesia isinya bukan orang bodoh sudah pasti presidennya bukan Prabowo",2110993603871076819,,,in,,0,0,0,https://x.com/vertiogo/status/2110993603871076819,1248589001591623682,vertiogo
2110616071845912662,2026-10-16T07:17:49.000Z,0,@hanIogys Semoga asapnya cepat mereda. Semoga Pemerintah Pusat dan Daerah cepat tobat dan langsung sigap menangani kebakaran dan asapnya. #IndonesiaButuhOksigen,2110993600624415179,,hanIogys,in,,0,0,0,https://x.com/azizan_mars/status/2110993600624415179,1725674047,azizan_mars
2110993595595661536,2026-10-16T07:17:48.000Z,0,"Kepala Kantor Pertanahan Kota Samarinda, Ceto Subagiyo, beserta jajaran menghadiri pelantikan Majelis Pembina dan Pengawas Pejabat Pembuat Akta Tanah (PPAT) Wilayah dan Daerah Provinsi Kalimantan Timur Tahun 2026 yang diselenggarakan oleh Kanwil BPN Provinsi Kaltim https://t.co/50TaqaEmXv",2110993595595661536,https://pbs.twimg.com/media/HUvBe95boAAToG2.jpg,,in,,0,0,0,https://x.com/kantahkotasmd/status/2110993595595661536,974164577372876800,kantahkotasmd
2110993581964153320,2026-10-16T07:17:44.000Z,0,"Keluarga Besar Tentara Nasional Indonesia Angkatan Darat Mengucapkan Selamat &amp; Sukses kepada Jenderal TNI Tandyo Budi R, atas Amanah Jabatan Baru Sebagai Kepala Staf TNI Angkatan Darat https://t.co/C6UwJr1ISh",2110993581964153320,https://pbs.twimg.com/media/HUvBd_rbkAARIM1.jpg,,in,,0,0,0,https://x.com/Jokowi_RI/status/2110993581964153320,1369851902,Jokowi_RI
2110993405606306154,2026-10-16T07:17:32.000Z,3,"konsentrasi CO ekstrem (warna merah gelap) di atas Sumatra, Kalimantan, dan sekitarnya.
3. Musim kebakaran terburuk dalam lebih dari 10 tahun, diperparah El Niño sangat kuat (kekeringan ekstrem).
Faktor utama: pembakaran lahan (slash-and-burn) untuk sawit &amp; pertanian + kebakaran",2110993529405391290,,Rahadi0816,in,,0,0,3,https://x.com/Rahadi0816/status/2110993529405391290,1611567480992043008,Rahadi0816
2110993521285190097,2026-10-16T07:17:30.000Z,0,"Laporan Khusus Dua Tahun Prabowo–Gibran: Booming Bisnis Data Center di Indonesia, Apa yang Harus Dilakukan Pemerintah? https://t.co/liFx5ZJ3IZ @indoict",2110993521285190097,,,in,,0,0,0,https://x.com/indoict/status/2110993521285190097,957482702,indoict
2110993512493957442,2026-10-16T07:17:28.000Z,0,Demi dah… prabowo cwpet lengser ya alloh gak kuaaat,2110993512493957442,,,in,,0,0,0,https://x.com/sourirever/status/2110993512493957442,1499411440692006912,sourirever
2110993457787642012,2026-10-16T07:17:15.000Z,2,"Personel Satbrimob Polda Maluku Utara bersama Polsek Jailolo Selatan bergerak cepat memadamkan kebakaran hutan dan lahan (karhutla) di Desa Domato, Kecamatan Jailolo Selatan, Kabupaten Halmahera Barat. Personel gabungan melakukan upaya pemadaman untuk mencegah api meluas dan https://t.co/CznHpCauXB",2110993457787642012,https://pbs.twimg.com/media/HUvBWchasAATLox.jpg,,in,,0,0,0,https://x.com/DivHumas_Polri/status/2110993457787642012,138290629,DivHumas_Polri
2110990946074574852,2026-10-16T07:17:14.000Z,0,@yourdebluesion Kebakaran Hutan dan Lahan,2110993454239207497,,yourdebluesion,in,,0,0,0,https://x.com/gocanz89/status/2110993454239207497,2105970967713570816,gocanz89
2110993446219715021,2026-10-16T07:17:12.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan kegiatan koordinasi dengan mitra kerja terkait pembayaran pajak melalui aplikasi Qlola di Kantor Wilayah Direktorat Jenderal Pajak (DJP) Kalimantan Selatan dan Tengah, Jalan Lambung Mangkurat Nomor 21, https://t.co/Wy8Liv5Sbp",2110993446219715021,https://pbs.twimg.com/media/HUvBVtmbgAA0-5G.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110993446219715021,700676990722924544,balaibhskalsel
2110993415718781416,2026-10-16T07:17:08.000Z,0,"Dukungan dari Bapak menjadi penyemangat bagi seluruh jajaran Karantina Kalimantan Barat untuk terus menjaga kedaulatan negara, melindungi kelestarian sumber daya alam hayati, serta memperkuat ketahanan ekonomi 🇮🇩.",2110993427567636901,,karantinakalbar,in,,0,1,0,https://x.com/karantinakalbar/status/2110993427567636901,828524256996646912,karantinakalbar
2110993415718781416,2026-10-16T07:17:07.000Z,0,"Dukungan dari Bapak menjadi penyemangat bagi seluruh jajaran Karantina Kalimantan Barat untuk terus menjaga kedaulatan negara, melindungi kelestarian sumber daya alam hayati, serta memperkuat ketahanan ekonomi 🇮🇩.",2110993423151022457,,karantinakalbar,in,,0,1,0,https://x.com/karantinakalbar/status/2110993423151022457,828524256996646912,karantinakalbar
2110993415718781416,2026-10-16T07:17:06.000Z,0,"beserta seluruh jajaran atas ucapan, dukungan, dan sinergi yang diberikan dalam rangka Hari Karantina Indonesia yang ke-149 serta ulang tahun Badan Karantina Indonesia yang ke-3. 🎉",2110993419481100717,,karantinakalbar,in,,0,1,0,https://x.com/karantinakalbar/status/2110993419481100717,828524256996646912,karantinakalbar
2110993415718781416,2026-10-16T07:17:05.000Z,0,"Terima kasih dan apresiasi kami sampaikan kepada Kepala Kantor Imigrasi Kelas I TPI Singkawang, Dadang Munandar,

Semoga sinergi serta kolaborasi antara Karantina dan Imigrasi semakin kuat demi menjaga kedaulatan negara ✨ https://t.co/GouKaXm4K8",2110993415718781416,https://pbs.twimg.com/amplify_video_thumb/2110993363784867840/img/x7K0FtN_icUUSfxi.jpg,,in,,0,1,0,https://x.com/karantinakalbar/status/2110993415718781416,828524256996646912,karantinakalbar
2110953377194746018,2026-10-16T07:17:04.000Z,0,"@GusDikaOfficial engga lah,  paling bener emang ganti semua pemerintahnya palagi presiden (wajib ganti)",2110993410903670816,,GusDikaOfficial,in,,0,0,0,https://x.com/aethernalangel/status/2110993410903670816,2018530933377466368,aethernalangel
2110993410882449903,2026-10-16T07:17:04.000Z,0,"cuma mau bilang,

terima kasih banyak, Vicky Prasetyo —sudah mau bersuara untuk kebakaran hutan di Indonesia.

say it louder, my bro.✊🏼

🙏🏼🤍 https://t.co/KRINgVomRE",2110993410882449903,https://pbs.twimg.com/amplify_video_thumb/2110993291948990464/img/M2AH7MTHRDCN17bw.jpg,,in,,0,0,0,https://x.com/xClaudyastev/status/2110993410882449903,2104546537401708544,xClaudyastev
2110993405606306154,2026-10-16T07:17:02.000Z,3,"Ringkasan Situasi Kebakaran Hutan Indonesia &amp; Polusi CO (per 16 Oktober 2026)
1. Data satelit NASA menunjukkan polusi karbon monoksida (CO) yang sangat tinggi dari kebakaran hutan/lahan intens di Indonesia.
2. Polusi menyebar luas ke Malaysia dan Singapore.
Peta menunjukkan.. https://t.co/aGwjaQ5daL",2110993405606306154,https://pbs.twimg.com/amplify_video_thumb/2110993369233334273/img/id73yBvx4x-pIHBr.jpg,,in,,0,4,3,https://x.com/Rahadi0816/status/2110993405606306154,1611567480992043008,Rahadi0816
2110993403005849628,2026-10-16T07:17:02.000Z,0,IHSG dibekukan guys! Apakah ekonomi  baik2 saja pak @prabowo ?,2110993403005849628,,,in,,0,0,0,https://x.com/falihazmi/status/2110993403005849628,75992221,falihazmi
138948254804099072,2026-10-16T07:16:53.000Z,0,@prabowo @Gerindra ALAHHHH TAIK,2110993366372782276,,prabowo,in,,0,0,0,https://x.com/markkganteng/status/2110993366372782276,1243142081008156672,markkganteng
2110738555723255947,2026-10-16T07:16:49.000Z,0,@sosmedkeras Dikasih fasilitas buat judol dan ngeslot dari presiden @prabowo 👏👏,2110993349104848936,,sosmedkeras,in,,0,0,0,https://x.com/jin_pae/status/2110993349104848936,1228755411718639616,jin_pae
2110993346948907283,2026-10-16T07:16:48.000Z,0,"Presiden Prabowo Subianto melantik tujuh pejabat negara sekaligus di Istana Negara, Kamis (15/10/2026), dalam perombakan jajaran pemerintahan.

Salah satu posisi yang berganti adalah Kepala BNPB. Letjen TNI Kristomei Sianturi kini menduduki jabatan tersebut menggantikan Letjen https://t.co/8Wh4q2hdeJ",2110993346948907283,https://pbs.twimg.com/amplify_video_thumb/2110993286932680704/img/MttqhWUCUNW3vzLs.jpg,,in,,0,0,0,https://x.com/owritedotid/status/2110993346948907283,1964554328649453576,owritedotid
2110982005639012729,2026-10-16T07:16:47.000Z,0,@itszweedy PRABOWO ANJING,2110993341009785096,,itszweedy,in,,0,0,0,https://x.com/syalaamore/status/2110993341009785096,1791493821714604032,syalaamore
2110993332398920055,2026-10-16T07:16:45.000Z,0,"Sebelum komentar atau share berita Presiden Prabowo, cek lagi kevalidannya supaya nggak nyebarin kabar bohong #SaringInformasi https://t.co/fvcbbLm6Rb",2110993332398920055,https://pbs.twimg.com/media/HUvBPc6akAAQg04.jpg,,in,,0,0,0,https://x.com/alghia_dena/status/2110993332398920055,1678670618416541696,alghia_dena
2110993330809311589,2026-10-16T07:16:45.000Z,0,"Laporan Khusus Dua Tahun Prabowo–Gibran: Booming Bisnis Data Center di Indonesia, Apa yang Harus Dilakukan Pemerintah? https://t.co/liFx5ZJ3IZ via @indoict",2110993330809311589,,,in,,0,0,0,https://x.com/indoict/status/2110993330809311589,957482702,indoict
2110993327893909844,2026-10-16T07:16:44.000Z,0,Profil Mayjen TNI Sriyanto: Alumni SMA Taruna Nusantara Resmi Dilantik Presiden Prabowo Subianto jadi Wakil Kepala BPGMN RI https://t.co/e1ayWoiP2m,2110993327893909844,,,in,,0,0,0,https://x.com/TajukNasional/status/2110993327893909844,729309555486642176,TajukNasional
2110993323276325081,2026-10-16T07:16:43.000Z,0,"ga heran kan indo punya presiden kek prabowo? ya beginilah warganya, tone deaf.",2110993323276325081,,,in,,0,0,0,https://x.com/131larabee/status/2110993323276325081,1274680674230784003,131larabee
2110993317064536103,2026-10-16T07:16:41.000Z,0,Thanks God doa sejuta umat turunlan hujan di Kalimantan🙏💜,2110993317064536103,,,in,,0,0,0,https://x.com/MuvMuvna/status/2110993317064536103,1783468380139429888,MuvMuvna
2110927560934924324,2026-10-16T07:16:39.000Z,1,"@tribunnews Segera telepon prabowo....
Semuanya akan baik-baik saja",2110993309380600240,,tribunnews,in,,0,0,0,https://x.com/Idiand/status/2110993309380600240,220888132,Idiand
2110993299372958030,2026-10-16T07:16:37.000Z,0,"Pokoknya, kalau yang survei Adidaya Institute, kepuasan publik pada pemerintahan selalu tinggi....
Heheheeee

https://t.co/8EzGrfaS2I",2110993299372958030,,,in,,0,0,0,https://x.com/sipengen_tenar/status/2110993299372958030,1847982814895194112,sipengen_tenar
2110606115881046501,2026-10-16T07:16:33.000Z,0,"@hidanieldisini @txtdarigenz97 Prabowo ngunci Jokowi, tapi masyarakat masih punya 2 pilihan lain dan kok gobloknya yg terburuk yg justru yg menang 🫣",2110993282847359230,,hidanieldisini,in,,0,0,0,https://x.com/dikobelaja/status/2110993282847359230,1665582685157466113,dikobelaja
2110929784469626920,2026-10-16T07:16:32.000Z,0,"@LambeSahamjja Trus ganti menteri, ganti wamen...atau bikin lembaga baru utk menanggulangi kebakaran hutan. Paling itu agendanya.. Wowo gak mau melihat langsung ke sana, alasannya dulu kan sudah. Takut sesak napas dia.",2110993276019085632,,LambeSahamjja,in,,0,0,0,https://x.com/indah_suwondo/status/2110993276019085632,1638814473476612096,indah_suwondo
2110993270247739789,2026-10-16T07:16:30.000Z,0,"berapa ratus orang yang udah kena penyakit pernafasan gara-gara kebakaran hutan? ini pemerintah ga all-in padahal udahh berbulan2,,, masa depan bangsa pada mati semua sebelum umur 30 tahun 🤦",2110993270247739789,,,in,,0,0,0,https://x.com/rendrafrizal/status/2110993270247739789,1625480431415201794,rendrafrizal
2110950874109604188,2026-10-16T07:16:26.000Z,0,@SigitWasito8 Kegagalan prabowo adalah dosa terbesar jokowi yg jadikan dia presiden demi ambisi jadikan gibran wapres.,2110993254724645306,,SigitWasito8,in,,0,0,0,https://x.com/bukan4non/status/2110993254724645306,2148752027,bukan4non
2110993229739159836,2026-10-16T07:16:20.000Z,0,"Presiden Prabowo Subianto resmi melantik Jenderal Tandyo Budi Revita sebagai KSAD dan Jenderal Maruli Simanjuntak sebagai Wakil Panglima TNI, Kamis (15/10/2026).

“Mengangkat Jenderal Maruli Simanjuntak sebagai Wakil Panglima TNI merangkap Kepala Badan Nasional Pengelola https://t.co/iSE3qIahRe",2110993229739159836,https://pbs.twimg.com/amplify_video_thumb/2110993176702115840/img/1hQANtHjMeZibwLr.jpg,,in,,0,0,0,https://x.com/owritedotid/status/2110993229739159836,1964554328649453576,owritedotid
2110993224869487023,2026-10-16T07:16:19.000Z,1,"tadi liat konten warga Kalimantan kalau langitnya warna merah, bukan dari filter sosmed tapi karena kebakaran hutan. gusti pangeran teu kabayang euy nyesek pisan nafasna meren nya, ningalina oge ku loba haseup, kebul timana mana",2110993224869487023,,,in,,0,1,0,https://x.com/BaseBDG/status/2110993224869487023,1248335621988311041,BaseBDG
2110984568031555792,2026-10-16T07:16:19.000Z,1,"@harusbekerja pertama salah 58% 
kedua salah prabowo, krn setelah jadi bikin proyek yg ugal2an gatau arahnya kemana dan sangat tdk efisien. 
ketiga salah wakilnya juga kenapa dia maksa banget jadi wapres",2110993222256533867,,harusbekerja,in,,0,0,0,https://x.com/tachimchuu/status/2110993222256533867,996212005949267968,tachimchuu
2110993179860443309,2026-10-16T07:16:09.000Z,0,DIET GUA GAGAL GEGARA PRABOWO,2110993179860443309,,,in,,0,0,0,https://x.com/weltpyang/status/2110993179860443309,1415894962424586242,weltpyang
2110528247364747629,2026-10-16T07:15:59.000Z,0,"@MAzka58885102 @ferrykoto @SyedSaddiq Kecewa sama prabowo, ga foto2 di tengah hutan yang udh kebakar biar keliatan kerja",2110993140479832098,,Nugrohoisme,in,,0,0,0,https://x.com/Nugrohoisme/status/2110993140479832098,353749113,Nugrohoisme
2110756052287590868,2026-10-16T07:15:52.000Z,0,@ezash prabowo kak plis oper aja ke luar,2110993109806973339,,ezash,in,,0,0,0,https://x.com/pawangsadboy101/status/2110993109806973339,1568288736429092866,pawangsadboy101
2110992986373034226,2026-10-16T07:15:46.000Z,0,"tahapan penyelesaian administrasi dan pelaksanaan anggaran menjelang akhir tahun.
Melalui koordinasi ini, Balai Bahasa Provinsi Kalimantan Selatan berkomitmen untuk meningkatkan ketertiban administrasi keuangan, memastikan kelengkapan dokumen,",2110993085899649259,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110993085899649259,700676990722924544,balaibhskalsel
2110711759325499401,2026-10-16T07:15:44.000Z,0,@IrawanRommi @grok sekali lagi saya minta. Rank dampak karhutla dari yang terparah era SBY vs era Jokowi vs era prabowo,2110993077754310820,,IrawanRommi,in,,0,1,0,https://x.com/GamefaqsIDN/status/2110993077754310820,1962315346893021184,GamefaqsIDN
138948254804099072,2026-10-16T07:15:43.000Z,0,@prabowo @Gerindra Opo bedanya omon2 dengan ngecebret🤔,2110993072851214684,,prabowo,in,,0,0,0,https://x.com/WIPA60891075/status/2110993072851214684,1603757079717564417,WIPA60891075
2110993069655085118,2026-10-16T07:15:42.000Z,0,"Gak hutan
Gak Rupiah
Gak IHSG

semua kebakaran.",2110993069655085118,,,in,,0,0,0,https://x.com/nflsaragih/status/2110993069655085118,200422096,nflsaragih
2110988900705694189,2026-10-16T07:15:27.000Z,0,"@firstletterisY Tiap hari bukannya membaik malah makin buruk ini di Kalimantan, mana buzzer makin bego pula, ada yg speak up langsung diserang, dibungkam pula sama KEMKOMDIGI, sengaja mau dibunuh kayaknya kami yg di Kalimantan 😑😑😑",2110993004932821426,,firstletterisY,in,,0,0,0,https://x.com/galtzarr/status/2110993004932821426,61446677,galtzarr
2110377589093064881,2026-10-16T07:15:25.000Z,0,@elzraha @prabowo Kebagusan dipanggil Sir,2110992998137995667,,elzraha,in,,0,0,0,https://x.com/dandweissilla/status/2110992998137995667,314361584,dandweissilla
2110992986373034226,2026-10-16T07:15:22.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan koordinasi dengan Kantor Pelayanan Perbendaharaan Negara (KPPN) Banjarmasin terkait proses gaji, SKPP(Surat Keterangan Pemberhentian Pembayaran) Mutasi ASN serta LLAT(Langkah-Langkah Akhir Tahun 2026) https://t.co/HgphATNSdq",2110992986373034226,https://pbs.twimg.com/media/HUvA6ymbAAAH13B.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110992986373034226,700676990722924544,balaibhskalsel
2110618714379051348,2026-10-16T07:15:16.000Z,0,"@G_redJ20 @kenhans03 @NusronWahid1 @prabowo @DPR_RI @KPK_RI @mohmahfudmd Nawaitu
Kalo kita bicara seorang tokoh agamis, maka mari kita agungkan nawaitu dan tenggungjawab di akherat dan karma di kehidupan ini.
Jika saya di posisi dia, saya akan menyesal dan bunuh diri.",2110992960540348600,,G_redJ20,in,,0,0,0,https://x.com/J_a2y0/status/2110992960540348600,239712409,J_a2y0
2110992917573898414,2026-10-16T07:15:06.000Z,0,"halloween pake baju prabowo, hidup setan setan yg melawan (setan jg)",2110992917573898414,,,in,,0,0,0,https://x.com/steefucaca/status/2110992917573898414,1087334897016922112,steefucaca
2110992892261171447,2026-10-16T07:15:00.000Z,0,"Kebakaran melanda kawasan Jalan Mayjen Sutoyo S, Kelurahan Telaga Biru, Kecamatan Banjarmasin Barat, Kota Banjarmasin, Kalimantan Selatan, Jumat (16/10/2026) dini hari. Berdasarkan laporan sementara yang mengutip data Dinas Pemadam Kebakaran dan Penyelamatan (DPKP) Kota",2110992892261171447,,,in,,0,0,0,https://x.com/leonardathens/status/2110992892261171447,2036047361940832256,leonardathens
2110957132732633553,2026-10-16T07:14:54.000Z,0,@estehijau_ illfeel kalo dia bela prabowo,2110992867208622273,,estehijau_,in,,0,0,0,https://x.com/kelodeonn/status/2110992867208622273,2299768676,kelodeonn
2110992857486254135,2026-10-16T07:14:52.000Z,0,"lagi sama bapa, lagi sama bapa, sombong bgt sok ngartis. 2027 gue bawa bapa prabowo sekalian gue sombongin depan biji mata lu",2110992857486254135,,,in,,0,0,0,https://x.com/juliaanggyy/status/2110992857486254135,1992265998280630273,juliaanggyy
2110992817057329393,2026-10-16T07:14:42.000Z,1,"Polres Wonosobo bersama TNI, Perhutani, dan masyarakat bergerak cepat memadamkan kebakaran hutan pinus di Dusun Pucungroto, Desa Kalikarung, Kecamatan Kalibawang, Kabupaten Wonosobo, Rabu malam (14/10). Kebakaran yang melanda kawasan hutan lindung milik Perhutani RPH Sapuran Kedu https://t.co/hf5P9dIgSx",2110992817057329393,https://pbs.twimg.com/media/HUvAweDa0AEpOlU.jpg,,in,,0,1,0,https://x.com/DivHumas_Polri/status/2110992817057329393,138290629,DivHumas_Polri
2110992814528172097,2026-10-16T07:14:41.000Z,0,Cuma di rezim prabowo operator spbu sampe digantiin tentara. Negara apa ini anjeeengggg.!,2110992814528172097,,,in,,0,0,0,https://x.com/Panjulrasakeju/status/2110992814528172097,728976835866820609,Panjulrasakeju
2110992801295114574,2026-10-16T07:14:38.000Z,0,ring of fire di otak prabowo adalah bikin a literal fire di Kalimantan (hadeh),2110992801295114574,,,in,,0,0,0,https://x.com/llyenawyn/status/2110992801295114574,1109862436234903553,llyenawyn
2110992797730017560,2026-10-16T07:14:37.000Z,0,"Baca selengkapnya: https://t.co/gnXwG0h9Mf

Seluruh menteri dan wakil menteri Kabinet Merah Putih dijadwalkan mengikuti rapat kabinet bersama Presiden Prabowo Subainto di Istana Bogor pada Jumat (16/10/2026) malam.

~MS #Prabowo #AstaCita [2026101613503161] https://t.co/SBQp2P3exR",2110992797730017560,https://pbs.twimg.com/media/HUvAwU1asAAxqsi.jpg,,in,,0,0,2,https://x.com/kompascom/status/2110992797730017560,23343960,kompascom
2110954676627595493,2026-10-16T07:14:25.000Z,6,"@txtdrimedia Mampus lu gubernur² kalimantan, ganti rugi lu ke negara sebelah, semoga dengan ini lu lebiv aware sama masyarakat lu sendiri terkait kondisi, jangan nunggu di gugat negara lain baru sadar, jangan seenaknya aja berfoya foya diatas penderitaan orang lain, dasar OKB",2110992744852369869,,txtdrimedia,in,,0,0,0,https://x.com/SweetyPieAraa/status/2110992744852369869,2065828064932888576,SweetyPieAraa
2110992733133316356,2026-10-16T07:14:22.000Z,0,"katanya gausa dibesar besarin masalah karhutla, sbnrnya elu melek gaksi wokkkk @prabowo @Gerindra",2110992733133316356,,,in,,0,0,0,https://x.com/1633crumble/status/2110992733133316356,1983907177397157888,1633crumble
2110989062622343336,2026-10-16T07:14:20.000Z,2,@saludosparatii Prabowo ini presiden paling gagal didunia,2110992724849807813,,saludosparatii,in,,0,1,0,https://x.com/Netizenbola123/status/2110992724849807813,2104822285718913024,Netizenbola123
2110992711847498184,2026-10-16T07:14:17.000Z,0,YaAllah turunkanlah hujan dan Prabowo Gibran,2110992711847498184,,,in,,0,0,0,https://x.com/waswasilkhonnas/status/2110992711847498184,1316369124453347331,waswasilkhonnas
2110981842677740031,2026-10-16T07:14:15.000Z,0,@GusDikaOfficial Jadinya prabowo presiden adalh dosa terbesar jokowi.,2110992702007546010,,GusDikaOfficial,in,,0,0,0,https://x.com/bukan4non/status/2110992702007546010,2148752027,bukan4non
2110992698756977001,2026-10-16T07:14:14.000Z,0,"Status bencana nasional bukan satu-satunya penentu kecepatan bantuan. Meski belum berstatus nasional, penanganan karhutla Kalimantan tetap melibatkan personel gabungan, pemadaman darat, hingga operasi udara. 
#KawalPenangananKarhutla #PemerintahBergerak https://t.co/r4SV8DQNKD",2110992698756977001,https://pbs.twimg.com/amplify_video_thumb/2110992669006778368/img/63eqC6GR9JWD2yTX.jpg,,in,,0,0,0,https://x.com/Khan05074664/status/2110992698756977001,1288146217386426373,Khan05074664
2110711759325499401,2026-10-16T07:14:14.000Z,0,@piscokgede @IrawanRommi Prabowo juga mengurus koruptor kalau soal tampil seolah mengurus mah sama aja keduanya. Sama sama suka menipu orang goblok,2110992697498763540,,piscokgede,in,,0,0,0,https://x.com/GamefaqsIDN/status/2110992697498763540,1962315346893021184,GamefaqsIDN
2110609734768427251,2026-10-16T07:14:10.000Z,0,@Galehfy @BANGSAygSUJUD @prabowo Ngimpi 🤣🤣🤣👏,2110992681858105538,,Galehfy,in,,0,0,0,https://x.com/bungusleader/status/2110992681858105538,2017882226822991872,bungusleader
2110809126347722920,2026-10-16T07:14:09.000Z,0,@segaizsme hah aku bukan mau insensitive kok cuma bagi perspektif sebagai orang yg ngadepin negara2 lain di rl. kami di kl jg sakit2an jujur dan malunya jg bukan karena orang2 kalimantan/sumatra kok lebih ke malu sm pemerintah. maaf kalo kedengeran insensitive tp maksudku gak gt,2110992678100021667,,segaizsme,in,,0,0,0,https://x.com/archenized/status/2110992678100021667,932122218670186496,archenized
2110976859928433023,2026-10-16T07:14:09.000Z,0,"@msaid_didu Tumben opung berpikir cerdas, sudah jelas pasar modal itu mainan oligarki utk meruntuhkan Presiden Prabowo",2110992676359401946,,msaid_didu,in,,0,0,0,https://x.com/Da_Ajiee/status/2110992676359401946,1604136659662307330,Da_Ajiee
2110992490719502391,2026-10-16T07:14:07.000Z,0,"digunakan dalam kehidupan sehari-hari.
Kehadiran Balai Bahasa Provinsi Kalimantan Selatan merupakan bentuk dukungan terhadap sinergi antara pemerintah daerah, satuan pendidikan, dan berbagai pihak dalam upaya pelindungan bahasa daerah. Diharapkan,",2110992669279142366,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110992669279142366,700676990722924544,balaibhskalsel
2110912959849570366,2026-10-16T07:14:05.000Z,0,@belvinvvipreal Bisa2nya bikin king ga makan hari ini. Tega @prabowo,2110992661327065159,,belvinvvipreal,in,,0,0,0,https://x.com/ModalAvgD/status/2110992661327065159,2031665488837885953,ModalAvgD
2110992621426651623,2026-10-16T07:13:55.000Z,0,"in this economy masih ada yang antri iphone 18, padahal di sisi lain masih ada yang antri bensin di bali, antri air di jawa barat, antri utk akses bantuan oksigen di kalimantan, dan antri masuk ke pesawat rute singapura - indonesia (pak gubernur kalimantan contohnya)",2110992621426651623,,,in,,0,0,0,https://x.com/crypto_menfess/status/2110992621426651623,1280522160377942018,crypto_menfess
2110826694982668742,2026-10-16T07:13:55.000Z,0,@NyaiNeneng Hercules versi Kalimantan,2110992619379859718,,NyaiNeneng,in,,0,0,0,https://x.com/paman_ojek/status/2110992619379859718,2400248299,paman_ojek
2110732178837602642,2026-10-16T07:13:53.000Z,0,@susipudjiastuti @prabowo Langsung Japri saja ke Beliau Ibu. 😁,2110992611892994393,,susipudjiastuti,in,,0,0,0,https://x.com/nygoews/status/2110992611892994393,164079141,nygoews
2110992602694869477,2026-10-16T07:13:51.000Z,0,IY LG MONYEEETTT baru mau menjalani hidup beneran apes dapet era prabowo shitt shittttt,2110992602694869477,,,in,,0,0,0,https://x.com/pixieyyo/status/2110992602694869477,1009466964203302912,pixieyyo
1112546208554221568,2026-10-16T07:13:48.000Z,0,"@Uki23 @prabowo anda ini mendukung jokowi 100 persen ya, sampai pak prabowo anda hajar habis di sosmed.",2110992589801595008,,Uki23,in,,0,0,0,https://x.com/sr6723/status/2110992589801595008,97611062,sr6723
2110992244027326874,2026-10-16T07:12:25.000Z,1,terus kapan gorok gubernur se Kalimantan raya yang tone deaf dan malah cabut ke Singapur itu?,2110992244027326874,,,in,,0,0,0,https://x.com/hujanyangturun_/status/2110992244027326874,710280429442441216,hujanyangturun_
2110992217439715610,2026-10-16T07:12:19.000Z,0,Penjilat akan tetap penjilat. Walau pun harus menjadi anjing. Cc. @prabowo,2110992217439715610,,,in,,0,0,0,https://x.com/DM_Sihombing16/status/2110992217439715610,832458432271704065,DM_Sihombing16
2110992209638314356,2026-10-16T07:12:17.000Z,0,"Boleh, kasih ke Paman Xi Jinping aja Kalimantan

Nanti panglima² tatoan itu dimasukin kamp pendidikan sama dia🤣",2110992209638314356,,,in,,0,0,0,https://x.com/KarinaShen54587/status/2110992209638314356,1948776122575192069,KarinaShen54587
2110980523091022082,2026-10-16T07:12:17.000Z,0,@dav_m_ib ehhh ikan yg cuma nemu kalok pas di Kalimantan,2110992207461351623,,dav_m_ib,in,,0,0,0,https://x.com/eko_neko3/status/2110992207461351623,1260723134358908928,eko_neko3
2110939022382309503,2026-10-16T07:12:16.000Z,0,"@JonghoJoestarr Prabowo tidak pernah mengatakan pakar tolol secara terbuka di kampanye Pilpres. Antek² asing itu adalah propaganda. 

Kalau agitasi kamu tetap merendahkan rakyat, itu akan menjadi propaganda bisa mengarah pada totaliterisme = hanya pendapat elite yg benar, rakyat tidak tahu apa²",2110992203804024837,,frmsrgr,in,,0,0,0,https://x.com/frmsrgr/status/2110992203804024837,1638681500,frmsrgr
2110992125383135234,2026-10-16T07:11:57.000Z,0,"Tragedi Karhutla Bromo, 3 Petugas dan Relawan Tewas Saat Padamkan Api
#kebakaran #gunungbromoterbakar #gunungbromo #korbankebakaranbromo #karhutlabromo2026 #poldajatim @HumasPoldaJatim 

https://t.co/s1NAZAGQDQ",2110992125383135234,,,in,,0,0,0,https://x.com/BongkahI/status/2110992125383135234,1226400848080539650,BongkahI
2110992124732915919,2026-10-16T07:11:57.000Z,0,"Wakapolres Melawi Kompol Aang Permana mengajak masyarakat untuk bersama-sama mencegah kebakaran hutan dan lahan (karhutla) serta memanfaatkan layanan Call Center 110 Polri saat membutuhkan bantuan kepolisian.

#polisibersamamasyarakat #polresmelawisiap #jumatkeliling #jagamelawi https://t.co/jWytLTlP8Z",2110992124732915919,https://pbs.twimg.com/media/HUvAIKwagAAKTis.jpg,,in,,0,0,0,https://x.com/polres_melawi86/status/2110992124732915919,1747090307798441984,polres_melawi86
2110992123872866545,2026-10-16T07:11:57.000Z,0,Orang yg enggak punya etika begini kau jadikan mentri...wo wo..😅🤣😜👎❤️🇮🇩😍✌️👌 cc. @prabowo @kompascom @tempodotco @Metro_TV @tvOneNews @msaid_didu @mohmahfudmd @MataNajwa https://t.co/sqBvkHaibJ,2110992123872866545,https://pbs.twimg.com/media/HUvAJVrbIAALUUB.jpg,,in,,0,0,0,https://x.com/wa_one1/status/2110992123872866545,81386247,wa_one1
2110609734768427251,2026-10-16T07:11:51.000Z,1,@farhanrizkippp @BANGSAygSUJUD @prabowo Yahahaha berita pesanan dipercaya miris cok 🤣🤣,2110992100636737946,,farhanrizkippp,in,,0,0,0,https://x.com/bungusleader/status/2110992100636737946,2017882226822991872,bungusleader
2110992051722748403,2026-10-16T07:11:51.000Z,0,"Kegiatan ini membahas teknis  pelaksanaan FTBI Tingkat Provinsi Kalimantan Selatan Tahun 2026 yang akan diselenggarakan pada Kamis, 29 September 2026 di Balai Bahasa Provinsi Kalimantan Selatan, dengan melibatkan peserta jenjang SD dan SMP.",2110992098065592493,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110992098065592493,700676990722924544,balaibhskalsel
2110992081753915765,2026-10-16T07:11:47.000Z,0,matlis lagi tapi kali ini karena kebakaran di blok sebelah huhu kasihan sekali :(,2110992081753915765,,,in,,0,1,0,https://x.com/stegoland/status/2110992081753915765,1989704537687691269,stegoland
2110992051722748403,2026-10-16T07:11:40.000Z,0,"Halo, #SabahatBahasa!

Dalam rangka persiapan pelaksanaan Festival Tunas Bahasa Ibu (FTBI) Tingkat Provinsi Kalimantan Selatan Tahun 2026, telah dilaksanakan kegiatan taklimat secara daring. https://t.co/5zxkFAJDRf",2110992051722748403,https://pbs.twimg.com/media/HUvAELbbEAAzEax.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110992051722748403,700676990722924544,balaibhskalsel
2110696076517019781,2026-10-16T07:11:32.000Z,0,"@Ambakarok007 Tolong dibiasakan ngetik KEBAKARAN HUTAN bang, jangan karhutla karhutla. Apa itu karhutla? Singkatan yg ga semua orang paham. Biar algoritmanya tuh paham oh ada kebakaran hutan.",2110992018386411563,,Ambakarok007,in,,0,0,0,https://x.com/boreochoco/status/2110992018386411563,1813414170966302720,boreochoco
2110992009695744079,2026-10-16T07:11:30.000Z,15,"Kabarnya X lagi bagi duit $3000 buat yang mau post video vertikal doang 

syaratnya post 15 video ngata2in prabowo selama sebulan

ini beneran gak sih?",2110992009695744079,,,in,,0,15,0,https://x.com/isishaki/status/2110992009695744079,1105824703891988482,isishaki
2110738555723255947,2026-10-16T07:11:28.000Z,0,@Ozyyd @sosmedkeras @prabowo iya juga yaaa😅😅,2110992002162761842,,Ozyyd,in,,0,0,0,https://x.com/ciperamanuk/status/2110992002162761842,1603697958230593537,ciperamanuk
2110991989999358121,2026-10-16T07:11:25.000Z,2,"Kalo Kata buzzer 100 perak, “keluar aja sana kalo ga suka sama Prabowo”.

Gw: ACC bosku https://t.co/oo8gvBWQXP",2110991989999358121,https://pbs.twimg.com/media/HUvABmqawAApV2R.jpg,,in,,0,1,0,https://x.com/Jacksepertiga/status/2110991989999358121,1477114168536829952,Jacksepertiga
2110528247364747629,2026-10-16T07:11:25.000Z,0,"@MAzka58885102 @ferrykoto @SyedSaddiq Ga usah banding2in. Dr Jokowi smp prabowo udh berusaha. Nnt malu sendiri. Klo mau bs dibandingin jg sama data jaman pak harto.

Skrg 1 kejadian diviralin 1000 orang jd 1000 kejadian. https://t.co/a6ko3ENun4",2110991988686200979,https://pbs.twimg.com/media/HUvABbrakAAnNyk.jpg,MAzka58885102,in,,0,1,0,https://x.com/Nugrohoisme/status/2110991988686200979,353749113,Nugrohoisme
2110991973121417430,2026-10-16T07:11:21.000Z,0,semoga prabowo masuk neraka dan disiksa sedahsyat2nya siksaan neraka,2110991973121417430,,,in,,0,0,0,https://x.com/blckroot/status/2110991973121417430,1344919778436083714,blckroot
2110567694856769717,2026-10-16T07:11:15.000Z,0,"@yaniarsim @aniesbaswedan @prabowo Jika Melawan bencana Alami atau Buatan Manusia seperti Karhutla ini ibarat suatu Medan Peperangan, Maka Prabodo Subiantolol sebagai Jeneral Peperangan GAGAL TOTAL !!!

Omon-Omon aja tidak memastikan Karhutla. Pak Jeneral sendiri gak tahu dimana Kawasan terbakar besar.",2110991948006015304,,yaniarsim,in,,0,0,0,https://x.com/Salahuddin4yub1/status/2110991948006015304,1726029634083733504,Salahuddin4yub1
2110991945757765697,2026-10-16T07:11:14.000Z,0,"KATA ISTRIMU, KEBAKARAN HUTAN TERTANGANI 80% WOK??",2110991945757765697,,,in,,0,0,0,https://x.com/sighforlyfe/status/2110991945757765697,791250813767213056,sighforlyfe


--- clean-data/fiony_cleaning.csv ---

conversation_id_str,created_at,favorite_count,full_text,id_str,image_url,in_reply_to_screen_name,lang,location,quote_count,reply_count,retweet_count,tweet_url,user_id_str,username
2112750496201277454,2026-10-21T03:39:05.000Z,2,"Hasil voting final dan klasemen sementara Matchday 6 liga member inti (LDP) team love 🩷: 

1. Senin, 19 Oktober 2026
Match 1: Aurellia 0-2 Grace Octaviani Tanujaya

Match 2: Anindya Ramadhani Purnomo 1-4 Araki Nayla Suji Aurellia

Match 3: Cynthia Yaputera 5-8 Indah Cahya https://t.co/Br8CLpkxFm",2112750496201277454,https://pbs.twimg.com/media/HVH_YCZa8AAWNJd.jpg,,in,,0,0,0,https://x.com/Nivlac2nd/status/2112750496201277454,1443302420864331777,Nivlac2nd
2112589276378763472,2026-10-20T17:47:28.000Z,2670,@CErine_JKT48 Kaget dikit tapi gapapa lanjutkan 😬👍🏻,2112601609838735643,,CErine_JKT48,in,,3,38,124,https://x.com/A_FionyJKT48/status/2112601609838735643,1130448444282232832,A_FionyJKT48
2112598941300871569,2026-10-20T17:36:52.000Z,5634,"Adik2, tenangin diri kalian ✋🏻🤚🏻",2112598941300871569,,,in,,6,135,264,https://x.com/A_FionyJKT48/status/2112598941300871569,1130448444282232832,A_FionyJKT48
2112575412727595520,2026-10-20T17:31:34.000Z,2309,@Michie_JKT48 Michie “M”nya marah 😠,2112597608854335822,,Michie_JKT48,in,,2,66,119,https://x.com/A_FionyJKT48/status/2112597608854335822,1130448444282232832,A_FionyJKT48
2112571667654590908,2026-10-20T15:48:29.000Z,4,"Bagus cintaku Fiony Alveria Tantri, terus amati anak itu 🤣🤣🤣",2112571667654590908,,,in,,0,0,0,https://x.com/Nivlac2nd/status/2112571667654590908,1443302420864331777,Nivlac2nd
2112562524508115050,2026-10-20T15:12:10.000Z,0,"Hasil sementara matchday 6 liga member inti (LDP) team love 🩷: 

Match 4: Hillary Abigail Mantiri 1-3 Michelle Alexandra Suandi

Match 5: Aurhel Alana Tirta 1-0 Fritzy Rosmerian

Match 6: Fiony Alveria Tantri 2-4 Jazzlyn Agatha Trisha Indra Putri

Apakah hasil diatas sudah",2112562524508115050,,,in,,0,0,0,https://x.com/Nivlac2nd/status/2112562524508115050,1443302420864331777,Nivlac2nd
2112522742259912708,2026-10-20T12:34:05.000Z,2,"🔴 Fiony Alveria lagi live sekarang

Live Streaming
Mulai: 19:26 WIB
Platform: SHOWROOM
https://t.co/TvWsJMX3tt

#JKT48 #FionyAlveria #JKT48Connect https://t.co/oWKpmE8NPE",2112522742259912708,https://pbs.twimg.com/media/HVEwPNeXQAALHe3.jpg,,in,,0,0,0,https://x.com/JKT48Connect/status/2112522742259912708,1741149775398064128,JKT48Connect
2112320861764263960,2026-10-19T23:11:53.000Z,2,"""Gemerlap kota malam ini terasa sunyi, kalah telak oleh kilau indah di matamu. Sebuah detak yang konstan, menegaskan bahwa ada rasa yang telanjur menetap dan takkan pernah menemui pengganti.""

^ Fiony Alveria https://t.co/zYv5ggAJTE",2112320861764263960,https://pbs.twimg.com/media/HVB4nsCbUAA9mb_.jpg,,in,,0,0,0,https://x.com/Ketumbar_48/status/2112320861764263960,1665575002312413185,Ketumbar_48
2112205627795882037,2026-10-19T15:33:59.000Z,0,Cantik dan keren banget seh fotomu ini cintaku Fiony Alveria Tantri 🥰🩷 @A_FionyJKT48 https://t.co/hgbSKfJAne,2112205627795882037,https://pbs.twimg.com/media/HVAPzE_aEAAChWM.jpg,,in,,0,0,0,https://x.com/Nivlac2nd/status/2112205627795882037,1443302420864331777,Nivlac2nd
2111881532503974358,2026-10-18T18:06:08.000Z,0,"Oya maaf agak telat pengumumannya, tapi mulai hari ini nanti pagi akan saya adakan Matchday 6 liga member inti (LDP) kembali, dimulai dari liga team love 🩷 dengan 2 sistem voting (voting gratis dan premium) 

Untuk voting premium bisa langsung klik link di bawah ini untuk vote https://t.co/0njD1KmRZb",2111881532503974358,https://pbs.twimg.com/media/HU7pDv4aUAA90Bu.jpg,,in,,1,0,0,https://x.com/Nivlac2nd/status/2111881532503974358,1443302420864331777,Nivlac2nd
2111875711346885036,2026-10-18T17:46:58.000Z,0,@brekzsnotbear Gw sih gamau. Dan gw yakin Fiony Alveria Tantri ga tega mukul gw,2111876706432889156,,brekzsnotbear,in,,0,1,0,https://x.com/kreestee15/status/2111876706432889156,1500736417210966016,kreestee15
2111865438380458430,2026-10-18T17:02:11.000Z,3,"Jadwal show minggu ini (19 Oct – 24 Oct 2026)

Kamis, 22/10/2026
19:00 – 21:00 WIB
ITADAKI♥LOVE
Team: LOVE
Lineup: Anindya-ramadhani, Aurellia, Aurhel-alana, Celline-thefani, Fiony-alveria, +7 lainnya

https://t.co/TvWsJMX3tt

#JKT48 #JKT48Connect #JKT48Theater",2111865438380458430,,,in,,0,0,0,https://x.com/JKT48Connect/status/2111865438380458430,1741149775398064128,JKT48Connect
2111832498816917662,2026-10-18T14:51:18.000Z,4318,Mau show 3,2111832498816917662,,,in,,36,390,221,https://x.com/A_FionyJKT48/status/2111832498816917662,1130448444282232832,A_FionyJKT48
2111792232194044188,2026-10-18T12:11:18.000Z,0,"Selamat ulang tahun Gracie
semangat menikmati usia baru sambil tetap menyadari kalau lifetime semakin berkurang di dunia fana ini
--------
salam buat oshiku satu2nya fiony alveria aditya bilangin jangan capek2 wlpn aku tau jadi cantik terus itu capek wkwk #ItadakiLoveJKT48",2111792232194044188,,,in,,0,0,0,https://x.com/dimasgtg02/status/2111792232194044188,1900234362937057280,dimasgtg02
2111642378666991761,2026-10-18T02:15:50.000Z,3803,Hari ini 2 show lagi setelah sekian lama hihi semangaaatt 💪🏻,2111642378666991761,,,in,,12,252,173,https://x.com/A_FionyJKT48/status/2111642378666991761,1130448444282232832,A_FionyJKT48
2111375087970721895,2026-10-17T09:10:09.000Z,0,@RanggaWidigda Malah mempertegas kalau semakin serius menuju Fiony Alveria Tantri Widigda wkwkww,2111384258891878478,,RanggaWidigda,in,,0,0,0,https://x.com/Spiderwots616/status/2111384258891878478,247135071,Spiderwots616
2111359336434024563,2026-10-17T07:57:55.000Z,0,@RanggaWidigda @A_FionyJKT48 Beuh udh siap menambah nama jadi Fiony Alveria Tantri Widigda nih 🤭,2111366079042007120,,RanggaWidigda,in,,0,1,0,https://x.com/Spiderwots616/status/2111366079042007120,247135071,Spiderwots616
2110990941721113024,2026-10-16T07:07:15.000Z,517,"Selalu ada alasan untuk mengagumi dirimu. 

Happy #TGIF~

Fiony Alveria @ Amazing24 GTV

(RCTI+ Studio, Kebon Jeruk)
09102026 https://t.co/0EQ8TrHY2c",2110990941721113024,https://pbs.twimg.com/media/HUu-_I1aUAAog_c.jpg,,in,,1,3,82,https://x.com/bingkaikabesha/status/2110990941721113024,1572261551884890113,bingkaikabesha
2110975261164650612,2026-10-16T06:04:56.000Z,0,CANTIK BANGET SEH CINTAKU FIONY ALVERIA TANTRI #TGIF 🥰🩷,2110975261164650612,,,in,,0,0,0,https://x.com/Nivlac2nd/status/2110975261164650612,1443302420864331777,Nivlac2nd
2110962687790510324,2026-10-16T05:14:59.000Z,0,Ga masuk akal banget cantiknya fiony alveria tantri! 🫠🫠,2110962687790510324,,,in,,0,0,0,https://x.com/efaeraendee/status/2110962687790510324,1794242929726472192,efaeraendee


--- clean-data/gracie_bersih.csv ---

conversation_id_str,created_at,favorite_count,full_text,id_str,image_url,in_reply_to_screen_name,lang,location,quote_count,reply_count,retweet_count,tweet_url,user_id_str,username
2110998308449886385,2026-10-16T08:23:44.000Z,0,@kreestee15 invest ke JKT48 aja kak krees,2111010188308156677,,kreestee15,in,,0,0,0,https://x.com/Joeyrycho1/status/2111010188308156677,1083729356042563589,Joeyrycho1
2111006098543268047,2026-10-16T08:23:34.000Z,0,@Levi_JKT48 klo mau blajar dalang &amp; silsilah pewayangan dm mimin ya! alias tantiknaaaa 🫠,2111010148588359740,,Levi_JKT48,in,,0,0,0,https://x.com/JKT48_Madiun/status/2111010148588359740,564227912,JKT48_Madiun
2110733926826398015,2026-10-16T08:17:53.000Z,0,"@HachuStreamLab @xxbuttercupy cb sama jkt48 min gede itu fanbase mrk, siapa tau kan😵‍💫",2111008715587620910,,HachuStreamLab,in,,0,0,0,https://x.com/seunghwanimnida/status/2111008715587620910,1589058412515426304,seunghwanimnida
2111008218629706000,2026-10-16T08:15:54.000Z,0,Melati ex JKT48 https://t.co/Lw5XOtcLh3,2111008218629706000,https://pbs.twimg.com/amplify_video_thumb/2111008088157470720/img/lA3S2QyeAr0mUL8U.jpg,,in,,0,0,0,https://x.com/RianTegara/status/2111008218629706000,545889637,RianTegara
2111006465158750704,2026-10-16T08:08:56.000Z,1,"ngedeath maljum kemarin bareng mylofly😎
.
.
.
🔗 jkt48.lily_ Instagram Story, 151026 https://t.co/gp9c5SJZwF",2111006465158750704,https://pbs.twimg.com/media/HUvNMDAboAAm5VE.jpg,,in,,0,0,0,https://x.com/FanaRylai/status/2111006465158750704,2914313874,FanaRylai
2110976634363035728,2026-10-16T08:08:14.000Z,0,@jaedoistic check dr ticketmaster nya jg deh sometimes bs resell lgsg dr web nya kl ngga ya stubhub tp mrk mark up nya gila sih 😭 krn ticket swap tuh bnrn bs lgsg ilang in seconds kyk hrs 24/7 on it i tried getting sabrina and gracie ams tickets last year dan SUSAH BGT,2111006287362457941,,jaedoistic,in,,0,1,0,https://x.com/jaedoliu/status/2111006287362457941,1986813448832098304,jaedoliu
2111003105374728541,2026-10-16T07:55:35.000Z,0,"Jawaban wordta beberapa hari lalu ternyata cukup ngebantu buat dapetin huruf2 vokalnya wkwk

Wordta #52
4/6 · 4m 50s
⬛🟨⬛🟨🟨
🟨⬛⬛⬛⬛
🟨🟨🟨⬛⬛
🟩🟩🟩🟩🟩

https://t.co/zpj6tHBPsx",2111003105374728541,,,in,,0,0,0,https://x.com/garrycussoy/status/2111003105374728541,159770164,garrycussoy
2111002729628017044,2026-10-16T07:54:05.000Z,0,"Tujuan Ralyne di JKT48

Ingin membuat orang lain senang saat melihat dan bertemu dia, simple

Sambil benerin poni 😆
#RalyneJKT48
#JKT48Gen14
#JKT48Trainee
#RaLive https://t.co/YuftfPq76k",2111002729628017044,https://pbs.twimg.com/amplify_video_thumb/2111002683067019265/img/7qSi-7ZYpjf5_Aon.jpg,,in,,0,0,0,https://x.com/YareY4r3Daze/status/2111002729628017044,1411142861098143748,YareY4r3Daze
2110920475388133526,2026-10-16T07:54:01.000Z,0,@gayustambuan @IDX_BEI kak mjb bs jelasin ga efeknya gmn,2111002711814758559,,gayustambuan,in,,0,0,0,https://x.com/blankeryz/status/2111002711814758559,1226824313833017344,blankeryz
2111002431924625905,2026-10-16T07:52:54.000Z,0,"Unpopular opinion (or maybe popular) : suara member jkt48 bagus bagus, asal jangan nyanyi lagu jkt🙂‍↔️",2111002431924625905,,,in,,0,0,0,https://x.com/Felicitasptc/status/2111002431924625905,1769325403368570880,Felicitasptc
2110950184666775971,2026-10-16T07:51:53.000Z,0,@The_RedsIndo @francttz presiden tergoblok tergagal ternirempati terdajjal sepanjang sejarah indonesia,2111002173870149956,,The_RedsIndo,in,,0,0,0,https://x.com/blankeryz/status/2111002173870149956,1226824313833017344,blankeryz
2111000751543865426,2026-10-16T07:46:14.000Z,6,Pada suatu masa pernah nge-briefing kapten-kapten JKT48 he he he https://t.co/lyTEboxs6c,2111000751543865426,https://pbs.twimg.com/media/HUvHz3gbAAAOXru.jpg,,in,,0,0,0,https://x.com/giIangmahesa/status/2111000751543865426,29385415,giIangmahesa
2110963991598240233,2026-10-16T07:45:46.000Z,0,@Ohyulx Jkt48 - seesaw game penuh air mata.. https://t.co/SKJegMDdE3,2111000634677952583,https://pbs.twimg.com/amplify_video_thumb/2111000600020426752/img/wxmzDriu2rvK7F9W.jpg,Ohyulx,in,,0,0,0,https://x.com/ofsangwon/status/2111000634677952583,1314833216688193536,ofsangwon
2110957588586316013,2026-10-16T07:42:33.000Z,0,@beeIzeebub kirain muthe jkt48,2110999827379298397,,beeIzeebub,in,,0,0,0,https://x.com/yoogiiss/status/2110999827379298397,3114295140,yoogiiss
2110999512080879874,2026-10-16T07:41:18.000Z,0,Baru tau ada akun jkt48 ini...ini dibuat untuk member2 jkt48 yg u-16 kah? https://t.co/W5MsQExUCH,2110999512080879874,https://pbs.twimg.com/media/HUvG3PFaQAA6y82.jpg,,in,,0,1,0,https://x.com/PutraDalem10/status/2110999512080879874,1356237907703459840,PutraDalem10
2110996812693938565,2026-10-16T07:39:00.000Z,0,"@txfrtdyyy itu bawah nya masih member juga njir, lu berasa jkt48.ulima",2110998933757714463,,txfrtdyyy,in,,0,0,0,https://x.com/ainascnrrmt/status/2110998933757714463,1235183135647600641,ainascnrrmt
2087428398159438189,2026-10-16T07:38:40.000Z,1,"@yujsn @ruangyara Ayok bondinggg. Wah kamu nungguin doi kayak nunggu makanan kesukaan ya.. langsung merekah senyumnya.
Iyaaa kadang suka gitu.. lagu galau fav aku tuh JKT48 - Seesaw game penuh air mata. Kalo kamu gimana??",2110998846713352631,,yujsn,in,,0,0,0,https://x.com/ofsangwon/status/2110998846713352631,1314833216688193536,ofsangwon
2110968989086261583,2026-10-16T07:38:27.000Z,0,"@yogiiii02 17 &amp; 18 Oktober. Blom ada rundown nya sih. Tapi kemungkinan besar jkt48 dapet yg tanggal 17, soalnya Elin tanggal 18 ada itadaki https://t.co/WaaXqXgRqY",2110998793454018973,https://pbs.twimg.com/media/HUvGNKMbgAA5Qxc.jpg,yogiiii02,in,,0,1,0,https://x.com/cruzozzan/status/2110998793454018973,1275914937177567234,cruzozzan
2110998413173203220,2026-10-16T07:36:56.000Z,0,"Ada fans jeketi yang juga suka h2h ga? Dan dateng ke ice bsd tgl 24 okt nanti?
Bisa ambil stiker ini, 1pcs /orang.

Mari berbagi kebahagiaan ~~~ 🤣

#jkt48 #hearts2hearts https://t.co/I77A3iLwfq",2110998413173203220,https://pbs.twimg.com/amplify_video_thumb/2110998272106246144/img/bamMWedLMbfNAZ0r.jpg,,in,,0,0,0,https://x.com/rosen_ocen/status/2110998413173203220,97610700,rosen_ocen
2110997326873678090,2026-10-16T07:32:37.000Z,1,"yg mau order replay, show stream, live dan pm jkt48 semuanya bisa lewat atau access via link dibawah ini yaa

https://t.co/tS1LNVJBqc https://t.co/CI6kyALvsk",2110997326873678090,https://pbs.twimg.com/media/HUvE3gVa4AAKKJp.jpg,,in,,0,0,0,https://x.com/ivand56395/status/2110997326873678090,1761554024028139520,ivand56395


--- clean-data/test.csv ---

conversation_id_str,created_at,favorite_count,full_text,id_str,image_url,in_reply_to_screen_name,lang,location,quote_count,reply_count,retweet_count,tweet_url,user_id_str,username
2110988904904245492,2026-10-16T07:50:00.000Z,0,@LambeSahamjja datengin Prabowo harusnya. stop MBG dan Kopdes,2111001698525466907,,LambeSahamjja,in,,0,0,0,https://x.com/Enkithelord/status/2111001698525466907,1781216713146781696,Enkithelord
2110724349854704080,2026-10-16T07:49:57.000Z,0,@LambeSahamjja Maksutnya br di jaman Prabowo dia bs punya jabatan &amp; hidup enak,2111001687897071620,,LambeSahamjja,in,,0,0,0,https://x.com/erimeureun/status/2111001687897071620,625871632,erimeureun
2111001682889097531,2026-10-16T07:49:56.000Z,0,"🚨🚨SIANG INI TERJADI LAGI🚨🚨
KEBAKARAN HUTAN LAGI dekat Perumahan Mutiara Indah 2 sudah mendekati pemukiman, bagi relawan dan pemadam tolong padamkan SEGERA sebelum KEBAKARAN HUTAN ini meluas dengan cepat

Terjadi di oganilir sorotan Indralaya, Ogan Ilir, Sumatra Selatan.

KEEP https://t.co/5mbmU0T1gF",2111001682889097531,https://pbs.twimg.com/amplify_video_thumb/2111001652580986880/img/HRxDlGb-MPv3L2VJ.jpg,,in,,0,0,0,https://x.com/jenostalker/status/2111001682889097531,1885318915498401796,jenostalker
2111001680301244750,2026-10-16T07:49:55.000Z,0,sok sokan gamau nerima bantuin kaya becus aja lu @prabowo,2111001680301244750,,,in,,0,0,0,https://x.com/findstufhere/status/2111001680301244750,1468067621698359297,findstufhere
2111001665696600571,2026-10-16T07:49:52.000Z,0,Karena literally sudah besar beneran kebakaran nya,2111001665696600571,,,in,,0,0,0,https://x.com/prizuardi/status/2111001665696600571,1337643428729954304,prizuardi
2110996666199220258,2026-10-16T07:49:49.000Z,0,"@saludosparatii Sebenarnya Jokowi ngajak Prabowo masuk kabinet itu gapapa, tapi yg terkesan memaksa itu Jokowi malah mendukung Prabowo jadi presiden. 

Walaupun saat itu sebenernya Jokowi juga akan mendukung Ganjar.",2111001655726719214,,saludosparatii,in,,0,0,0,https://x.com/chris_azura/status/2111001655726719214,3062188777,chris_azura
2110958919744991665,2026-10-16T07:49:37.000Z,0,@kvn_doc Tuhan bersama seluruh WNI yang menderita di rezim Prabowo,2111001605105700933,,kvn_doc,in,,0,0,0,https://x.com/KulinerAftWork/status/2111001605105700933,2106643220532965376,KulinerAftWork
2110990082341761085,2026-10-16T07:49:31.000Z,0,"@abu_waras Geng Solo sdh banyak tersingkir Hakim &amp; Jaksa kok sepertinya masih ketakutan sama Jokowi padahal digaji oleh rakyat, percuma gaji dinaikkan 280% oleh Prabowo agar berani tegakkan keadilan.

""Polisi Bersama Masyarakat"", kapan jaksa &amp; hakim bersama Masyarakat ?",2111001576974520693,,abu_waras,in,,0,0,0,https://x.com/sayno_KKN/status/2111001576974520693,1735636779192233984,sayno_KKN
2111001537011147256,2026-10-16T07:49:21.000Z,0,"Ga ada yang perlu disampaikan.

Langsung aja, prabowo need to get Charlie Kirk treatment.",2111001537011147256,,,in,,0,0,0,https://x.com/NeoPolice25/status/2111001537011147256,1302515107650445312,NeoPolice25
2110696070682669332,2026-10-16T07:49:20.000Z,0,@maxxnxine Tapi ada plotwist ke 2 setelah kemarin gagal fs kak yaitu asap Kalimantan mulai hari ini sdh mulai masuk jakarta jadi GK tau nanti bagaimana berjalan nya FANSIGN Hearts2hearts di JKT. Tetap pake masker aja jaga kesehatan,2111001533672521860,,maxxnxine,in,,0,0,0,https://x.com/Riansyah040215/status/2111001533672521860,1923285244427501568,Riansyah040215
2110958471315406907,2026-10-16T07:49:10.000Z,0,@jeajezz mirip di kalimantan jir sampe 38,2111001488936128561,,jeajezz,in,,0,0,0,https://x.com/shikerei/status/2111001488936128561,1237868566503923712,shikerei
2110961240633639282,2026-10-16T07:49:07.000Z,0,@kumparan Setuju. Cari perusahaan yang bertanggungjawab atas kebakaran hutan. Boycott produk²nya dan bekukan asset² mereka yang di Singapura.,2111001478685143146,,kumparan,in,,0,0,0,https://x.com/toocool711/status/2111001478685143146,207065595,toocool711
2111001437304213848,2026-10-16T07:48:57.000Z,1,"Padahal Udara itu gratis tapi negara ini gagal memfasilitasi warga warga nya 
🥀🥀🥀

@DPR_RI @prabowo 

#IndonesiaButuhOksigen😷 https://t.co/NvS8FNmOiY",2111001437304213848,https://pbs.twimg.com/media/HUvIncHbcAAfkd5.jpg,,in,,0,0,0,https://x.com/dvnadrlprmdya/status/2111001437304213848,1667124436657672194,dvnadrlprmdya
2110987375522549914,2026-10-16T07:48:57.000Z,0,@Alitt4mb3ng @prabowo Lah kok 😀😀😀😀 padahal preman,2111001434355360022,,Alitt4mb3ng,in,,0,0,0,https://x.com/Hiugundul/status/2111001434355360022,1703670621622710272,Hiugundul
2110997554444030245,2026-10-16T07:48:56.000Z,0,"@BarisanOpOsisi @prabowo SEMOGA AMANAH MEMIMPIN NEGERI INI
SEMOGA DIA TIDAK AKAN MELANGGAR JANJINYA SEBAGAI MANTAN PRAJURIT, DAN TIDAK MELANGGAR  SUMPAH SEBAGAI PRESIDEN!

#BRAVO1986",2111001430127792591,,BarisanOpOsisi,in,,0,0,0,https://x.com/a999on/status/2111001430127792591,2041804213986951168,a999on
2111001266390552661,2026-10-16T07:48:17.000Z,0,sedih gak lu indo masuk shoshibuya dengan cara kek gini kwkwkw. @prabowo gblk,2111001266390552661,,,in,,0,0,0,https://x.com/zerunemui/status/2111001266390552661,2090048654702956544,zerunemui
2111001265786528207,2026-10-16T07:48:16.000Z,0,"Yah pinter banget. Kocak. Bom diledakin di tempat tertutup kayak gua gitu ya kekuatan ledakannya berlipat ganda lah. Pantesan lab Life Spiral kebakaran

Pas liat Ogier bilang 11 tahun lalu aku udah nebak ada hubungannya sama kebakaran 11 tahun lalu, tapi ga expect alasannya ini https://t.co/YvFrEynwXG",2111001265786528207,https://pbs.twimg.com/media/HUvIIz3aoAAyaBB.jpg,,in,,0,1,0,https://x.com/el_ktnk_lon/status/2111001265786528207,1333079502264492033,el_ktnk_lon
2111001254046642453,2026-10-16T07:48:14.000Z,0,guys SURPRISE in prabowo yok besok dia ultah nih🤩 mau diramein di istana negara apa di rumah hambalang pak,2111001254046642453,,,in,,0,0,0,https://x.com/UTDYoda_/status/2111001254046642453,1794520397330907136,UTDYoda_
2111001249718075758,2026-10-16T07:48:13.000Z,0,"Ini si wowok di tanya apa jawab apa, Kalimantan tuh gaada hubungannya sama Ring of fire ya anjirt, Instead bilang maaf dan akan menangani dengan baik, dia malah ngomong yg ga nyambung 💔 https://t.co/miqJR1rH8T",2111001249718075758,https://pbs.twimg.com/amplify_video_thumb/2111001208144175104/img/KhxiQSlyo4tBk5Ff.jpg,,in,,0,0,0,https://x.com/flllowiee/status/2111001249718075758,1584671789459701760,flllowiee
2111001234803220516,2026-10-16T07:48:09.000Z,0,"Padahal baru gak ada seminggu aku lewat sini tumbuhan gangang dan enceng gondoknya belum sebanyak ini loh.

Hari ini aku lewat udah full menutupi kali (lebih tepatnya aku sebut ini paceran). 
Ada satu tumbuhan kaya lumut, itu yang kecil-kecil gak tau nama pastinyaaa tapi https://t.co/Olp9NqyaG5",2111001234803220516,https://pbs.twimg.com/amplify_video_thumb/2111001146626281472/img/UhetRfSe2jfeiIb2.jpg,,in,,0,0,0,https://x.com/_prabowo88/status/2111001234803220516,52935312,_prabowo88
2111001233574252798,2026-10-16T07:48:09.000Z,0,"Ada hubungan dengan: Kantor ATR/BPN Kabupaten Karawang, Jawa Barat, mengalami kebakaran hebat pada Rabu malam, 14 Oktober 2026.
Sekitar pukul 22.00–23.10 WIB, Gudang arsip sekitar 70%. Dokumen: Semua sertifikat SHM (Sertifikat Hak Milik) dilaporkan ludes/habis terbakar.",2111001233574252798,,,in,,0,0,0,https://x.com/WidhiLawan/status/2111001233574252798,1918479126803169281,WidhiLawan
2111001232265617443,2026-10-16T07:48:08.000Z,0,Prabowo kapan mati?,2111001232265617443,,,in,,0,0,0,https://x.com/hime_anjai/status/2111001232265617443,2078500844459483136,hime_anjai
2110980056252301775,2026-10-16T07:48:08.000Z,0,@lelucone Aku harap semoga aja prabowo juga Anjlok Nyai,2111001229329592796,,lelucone,in,,0,0,0,https://x.com/restafajri/status/2111001229329592796,720245756,restafajri
2110917019843654112,2026-10-16T07:48:05.000Z,0,"@Saham_fess Good aja sih. Yg ngeluh2 gitu biasanya karena rugi judi di saham.  Udah tau antek2 asing lagi gencar2nya nyerang indo karena patriotiknya Pak Prabowo. Eh rakyatnya malah nyerang pemerintah. Aneh banget. Mending dukung pemerintah. Prabowo 2 periode pokoknya, ga mau tau!",2111001219556954231,,Saham_fess,in,,0,1,0,https://x.com/oxsakaSKY/status/2111001219556954231,1873699410103914496,oxsakaSKY
2111001196945416209,2026-10-16T07:48:00.000Z,0,Minat bgt Kalimantan ini di ambil Singapore 🙏,2111001196945416209,,,in,,0,0,0,https://x.com/ecrivain_rin/status/2111001196945416209,1805106620902572032,ecrivain_rin
2110303347458609293,2026-10-16T07:47:53.000Z,0,"@pw_gun kenapa alat pelaku ditinggal di pinggir jalan? kan bisa dilempar ke api.. kan TOLOL..
ATAU
 memang sengaja ditaruh di tempat yg aman dari api supaya bisa ditemukan utuh oleh petugas lapangan untuk membentuk opini kalau kebakaran bukan disebabkan oleh perusahaan sawit saja?😏",2111001168185069592,,pw_gun,in,,0,0,0,https://x.com/JLAPS15/status/2111001168185069592,135828208,JLAPS15
2111001143958716876,2026-10-16T07:47:47.000Z,0,"Aku rela di daerah sini jarang ujan asal api di Kalimantan cepet padam 😔 

Jangan sampe kekeringan juga sih di sini 😭☝️ balance aja deh. Tapi utamanya biar warga Kalimantan pada bisa menghirup udara segar",2111001143958716876,,,in,,0,0,0,https://x.com/huaot/status/2111001143958716876,1172443332,huaot
2110949246543511995,2026-10-16T07:47:44.000Z,0,@jayidzes @prabowo sehidup semati semaki maki prabowo kontol,2111001130839036380,,jayidzes,in,,0,0,0,https://x.com/surgaca/status/2111001130839036380,1857814846156451842,surgaca
2111001129052242020,2026-10-16T07:47:44.000Z,0,"Dua tahun pemerintahan Prabowo Subianto - Gibran Rakabuming Raka membawa Indonesia pada swasembada pangan, target empat tahun yang tercapai hanya dalam satu tahun. 

#GarudaMerah
#2TahunGerakNyata
#BadanKomunikasiPemerintah https://t.co/KiflBxGCut",2111001129052242020,https://pbs.twimg.com/amplify_video_thumb/2111000504511979521/img/kdwhiB0OnMcgF9M5.jpg,,in,,0,1,0,https://x.com/GARUDAMERAH__/status/2111001129052242020,869958008251367424,GARUDAMERAH__
2110768683018801341,2026-10-16T07:47:43.000Z,0,@Thebiglade kebakaran hutan,2111001123901632918,,Thebiglade,in,,0,0,0,https://x.com/tendanganpetir/status/2111001123901632918,51109056,tendanganpetir
2111001104490340601,2026-10-16T07:47:38.000Z,1,"Demi allah pingin nangis, kenapa sih prabowo jadi presiden. Kenapa sih orang2 jahat jadi pejabat. Kenapa sih orang kaya yg punya akses pendidikan tinggi ujung2nya memelintir orang bodoh dan miskin di bawahnya. Kenapa dunia berasa makin gak layak buat di huni😭",2111001104490340601,,,in,,0,0,0,https://x.com/bbymoonstruck/status/2111001104490340601,2062727039308972032,bbymoonstruck
2111001068171878886,2026-10-16T07:47:29.000Z,0,prabowo goblok bgt ye ternyata,2111001068171878886,,,in,,0,0,0,https://x.com/hilmisworo/status/2111001068171878886,894599668096684032,hilmisworo
2111001067336892615,2026-10-16T07:47:29.000Z,0,Prabowo Gibran dan kreni-kreninya next,2111001067336892615,,,in,,0,0,0,https://x.com/gdl_is/status/2111001067336892615,1244213097482424323,gdl_is
2110594634254561594,2026-10-16T07:47:14.000Z,0,"@kabjagyi Alaah.. Masyarakat kalimantan malah lbh parah,minta simpati rakyatkah?",2111001003713810923,,kabjagyi,in,,0,0,0,https://x.com/IwanGun5611250/status/2111001003713810923,1742044141713055744,IwanGun5611250
2111000930137395665,2026-10-16T07:46:56.000Z,0,Hadiah terbaik untuk ulang tahun prabowo adalah guillotine🤩,2111000930137395665,,,in,,0,0,0,https://x.com/tylersnewbae/status/2111000930137395665,62237246,tylersnewbae
2111000926865838486,2026-10-16T07:46:56.000Z,0,Sakit tekak ni cam takde tanda nak baik je. Esok tak tahulah jadi ke tak pegi konsert nya. Dah lah sekarang asyik hujan petang je. Nak kena bawa baju hujan pulak esok. Ni semua salah @prabowo,2111000926865838486,,,in,,0,0,0,https://x.com/nurqzfrh/status/2111000926865838486,1739301203539042304,nurqzfrh
2111000917533405473,2026-10-16T07:46:53.000Z,0,prabowo bangsat muatan gw kena imbas solar anjing goblok presiden gak guna gw sebel bgt anjg,2111000917533405473,,,in,,0,0,0,https://x.com/quietquitquite/status/2111000917533405473,1576244960177053696,quietquitquite
2110974182607745168,2026-10-16T07:46:53.000Z,0,@minjilalala grgr prabowo,2111000915696304364,,minjilalala,in,,0,0,0,https://x.com/orchidiey/status/2111000915696304364,1801045591503536128,orchidiey
2111000912978378781,2026-10-16T07:46:52.000Z,0,Karhutla Kalimantan ada kaitannya dengan Malaysia dan Singapur https://t.co/jr0rzQJJM3,2111000912978378781,https://pbs.twimg.com/amplify_video_thumb/2111000456956964864/img/Vsohjj0VJX3SGa4o.jpg,,in,,0,0,0,https://x.com/anak_indigo99/status/2111000912978378781,1927633754379735040,anak_indigo99
2110795759239221414,2026-10-16T07:46:51.000Z,1,"@indepenSumatera selamat anda kena hujat,  sepong terus bjii prabowo, iri kok ama swasta 😹 https://t.co/NcuSO12bV4",2111000908268249402,https://pbs.twimg.com/media/HUvIIrdboAAuEO5.jpg,indepenSumatera,in,,0,0,0,https://x.com/kakei_jun/status/2111000908268249402,1784026799711887361,kakei_jun
2110652375434478019,2026-10-16T07:46:46.000Z,0,@BANGSAygSUJUD Halah gua orang Kalbar.. tepatnya di kabupaten Ketapang ..selama kebakaran mana ada heli heli gini..relawan semua yg turun,2111000884754940356,,BANGSAygSUJUD,in,,0,0,0,https://x.com/Senju73123708/status/2111000884754940356,1517130312815628288,Senju73123708
2110716587074531395,2026-10-16T07:46:33.000Z,0,@mortaliel kemayu banget loh ya buna,2111000830841381114,,mortaliel,in,,0,0,0,https://x.com/Xdevilhun/status/2111000830841381114,1298490649419759617,Xdevilhun
2111000824113762544,2026-10-16T07:46:31.000Z,0,"Bakar aja istana negara sama gedung dpr + seluruh isinya. Laknat emang, manusia di sana pantes mati. Ga cukup warga negara sendiri, warga negara luar pun harus kena imbasnya. Minta kompensasi juga nanti pake duit pajak. Prabowo bangsat.",2111000824113762544,,,in,,0,0,0,https://x.com/monyetwtf/status/2111000824113762544,1332891499323744256,monyetwtf
2111000817818046790,2026-10-16T07:46:30.000Z,0,"Repost @kementerian.atrbpn

PENGUMUMAN LAYANAN PERTANAHAN KABUPATEN KARAWANG

Sehubungan dengan musibah kebakaran yang terjadi di Kantor Pertanahan Kabupaten Karawang pada Rabu, 14 Oktober 2026, kami memohon maaf kepada seluruh masyarakat atas gangguan dan ketidaknyamanan https://t.co/yHx88us2zo",2111000817818046790,https://pbs.twimg.com/media/HUvIBbzbIAEHDGB.jpg,,in,,0,0,0,https://x.com/atrbpnsumut/status/2111000817818046790,970842441812029441,atrbpnsumut
2110378014773297573,2026-10-16T07:46:27.000Z,0,@nyepamaja @prabowo celeng kuadrattt,2111000804819894699,,nyepamaja,in,,0,0,0,https://x.com/arfawkwk/status/2111000804819894699,1070666149707231232,arfawkwk
2111000771097763984,2026-10-16T07:46:18.000Z,0,"sangat NORMAL tuh

#bnpb #kalimantan #beritaterkini https://t.co/sRG9BxltbY",2111000771097763984,https://pbs.twimg.com/amplify_video_thumb/2111000738260484096/img/KLbLCzyIT3-fJVPJ.jpg,,in,,0,0,0,https://x.com/langitsenayan/status/2111000771097763984,1939894464094613504,langitsenayan
2111000735530061937,2026-10-16T07:46:11.000Z,0,"Lomba Seleksi Khusus

Hari, Tanggal: Kamis, 17 Desember 2026
Waktu: 14:00 - 17:00 WIB Tempat: Daring (Zoom)
Periode Pendaftaran: 
Jumat, 16 Oktober 2026 - Senin, 30 November 2026

Link pendaftaran dan pedoman : https://t.co/hvcFCXOqmF (tautan di bio)

※ Seleksi Khusus bagi https://t.co/ZaeGOZpfpu",2111000739137065404,https://pbs.twimg.com/media/HUvH3webEAE_W_v.jpg,JF_Jakarta,in,,0,0,0,https://x.com/JF_Jakarta/status/2111000739137065404,296111529,JF_Jakarta
2111000721370046677,2026-10-16T07:46:07.000Z,0,"Mangsa terperangkap dalam kepungan api dan asap tebal semasa operasi memadam kebakaran.

https://t.co/6kurI8TfHg

Yang sahih di RTM'
#RTM #BeritaRTM #MalaysiaMadani #TaatSetia #BersamaMALAYSIAKU #RancakkanMADANI #MADANIBekerja https://t.co/GUsukGMpZe",2111000721370046677,https://pbs.twimg.com/media/HUvH1UtbgAAPd5K.jpg,,in,,0,0,0,https://x.com/beritartm/status/2111000721370046677,704725700,beritartm
2110978131360412103,2026-10-16T07:45:54.000Z,0,"@menanti94297 @idextratime Good aja sih. Yg ngeluh2 gitu biasanya karena rugi judi di saham.  Udah tau antek2 asing lagi gencar2nya nyerang indo karena patriotiknya Pak Prabowo. Eh rakyatnya malah nyerang pemerintah. Aneh banget. Mending dukung pemerintah. Prabowo 2 periode pokoknya, ga mau tau!",2111000669113225382,,menanti94297,in,,0,0,0,https://x.com/oxsakaSKY/status/2111000669113225382,1873699410103914496,oxsakaSKY
2110996545013440894,2026-10-16T07:45:47.000Z,0,@cariaeosa Semoga di waraskan otaknya Prabowo,2111000640583536683,,cariaeosa,in,,0,0,0,https://x.com/restafajri/status/2111000640583536683,720245756,restafajri
2110639859568349211,2026-10-16T07:45:45.000Z,0,"@BANGSAygSUJUD Malu paman, sama namanya, BANGSA YANG SUJUD
Malu sama SUJUD paman
Malu sama ilmu paman
Malu sama agama paman
Malu sama RAKYAT INDONESIA WABIL KHUSUS RAKYAT KALIMANTAN DAN SUMATERA YG TERKENA MUSIBAH KEBAKARAN HUTAN
ingat KETIKAN PAMAN AKAN DIMINTAIN PERTANGGUNGJAWABAN DI AKHIRAT!",2111000629883887757,,BANGSAygSUJUD,in,,0,0,0,https://x.com/samar_wulu/status/2111000629883887757,1422108749959864323,samar_wulu
2110982067567947944,2026-10-16T07:45:44.000Z,0,"@papavilenn bener om, bukan cuma kalimantan sm sumatra saja",2111000626624967034,,papavilenn,in,,0,0,0,https://x.com/buburrayam12/status/2111000626624967034,235555503,buburrayam12
2111000611764523448,2026-10-16T07:45:40.000Z,0,"buzzer2 prabowo, klian smua taiiiii",2111000611764523448,,,in,,0,0,0,https://x.com/vinsensiasps/status/2111000611764523448,2938257301,vinsensiasps
2111000604676128945,2026-10-16T07:45:39.000Z,0,"Salut buat polisi yg gercep bantu warga saat kebakaran di Duri Kosambi

#Polri #PolriBersamaMasyarakat #FYP #polisiindonesia https://t.co/0LcJeZrCIz",2111000604676128945,https://pbs.twimg.com/amplify_video_thumb/2111000566159794177/img/4RX66Dsh4g0BQDbK.jpg,,in,,0,0,0,https://x.com/SuryanaWis83893/status/2111000604676128945,1701075217999962112,SuryanaWis83893
2111000590595903984,2026-10-16T07:45:35.000Z,20,giliran gini pada kompak sama tetangga😆😆😆😆 https://t.co/Yd22I1ACtg,2111000590595903984,https://pbs.twimg.com/media/HUvH2B_bQAAzSaT.jpg,,in,,0,7,2,https://x.com/unmagnetism/status/2111000590595903984,843269533930405888,unmagnetism
2111000578512019786,2026-10-16T07:45:33.000Z,0,"14:49 Halo min mau melaporkan alhamdulillah di Kalimantan Tengah kota Waringin lama sudah hujan, semoga jogja dan sekitarnya juga ada hujan, dan biar tidak kepanasan lagi aminn

#Merapiuncover #Merapinews #Merapi
masresa_28 https://t.co/EqvQri6tHV",2111000578512019786,https://pbs.twimg.com/amplify_video_thumb/2111000557481799680/img/ruIuNzaI9Nw-DQJb.jpg,,in,,0,0,0,https://x.com/merapi_uncover/status/2111000578512019786,1279804428724211712,merapi_uncover
2110930759519518840,2026-10-16T07:45:31.000Z,0,"@Ndrewstjan Prabowo tidak meminta maaf karena 2014 atau 2019. Ia memanfaatkan politik agama dan menyulut narasi divisive hingga menciptakan kerusuhan. Ia tidak pernah minta maaf. Saya sudah menolak dia 3 kali, tapi Jokowi memungut dia bagaikan sampah untuk jadi Menhan.",2111000569867296840,,Ndrewstjan,in,,0,0,0,https://x.com/LebakBulusLRT/status/2111000569867296840,1641703807251025921,LebakBulusLRT
2111000562254975308,2026-10-16T07:45:29.000Z,0,"Juru Bicara PDI-Perjuangan, Seno Bagaskoro, menyampaikan pandangannya terkait krisis kebakaran hutan dan lahan yang melanda wilayah Kalimantan, Riau, serta beberapa daerah di Indonesia dalam beberapa pekan terakhir. 

Dampak asap tebal dilaporkan telah mengganggu kesehatan warga, https://t.co/6vbu3Fe5KE",2111000562254975308,https://pbs.twimg.com/amplify_video_thumb/2111000320021262336/img/KPIsFUS9fDrfXjpk.jpg,,in,,0,0,0,https://x.com/kompascom/status/2111000562254975308,23343960,kompascom
2110563006493172070,2026-10-16T07:45:21.000Z,0,@pendekar_kalcer Semoga petugas di lapangan selalu diberi kelancaran dan kebakaran bisa segera teratasi 🤝,2111000528742420522,,pendekar_kalcer,in,,0,0,0,https://x.com/aciladewi955/status/2111000528742420522,2014648557543071744,aciladewi955
2111000507993280886,2026-10-16T07:45:16.000Z,0,"Jangan susah susah kalau dinasehatin, tolong hentikan kebijakan yg cuma nyusahin dan gak bermanfaat buat rakyat, terakhir coba turun ke lapangan yg terdampak bencana secara langsung &amp; pikirkan solusinya dengan baik, bukan hanya mendapat laporan &amp; tanya program gaje itu! @prabowo",2111000507993280886,,,in,,0,0,0,https://x.com/Fakhri270797/status/2111000507993280886,1561231966313525248,Fakhri270797
2111000491320844634,2026-10-16T07:45:12.000Z,0,"bener-bener gak bisa mikir, apa sih kebaikan/bagusnya prabowo sedikit aja? mau ngeanjing-anjingin si eta lebih kasian anjingnya disetarain sama orang itu🥲",2111000491320844634,,,in,,0,0,0,https://x.com/hardtoseeasily_/status/2111000491320844634,1217458764682448896,hardtoseeasily_
2111000486623220038,2026-10-16T07:45:11.000Z,0,"Semoga pengusutan kebakaran ini berjalan transparan dan hasilnya segera diketahui

#KampungAmbon #PolsekTambora #JakartaBarat #polribersamamasyarakat https://t.co/PhVKggQMXO",2111000486623220038,https://pbs.twimg.com/media/HUvHwDtbQAA9gdi.jpg,,in,,0,0,0,https://x.com/andrekusnadii/status/2111000486623220038,1699669980579872768,andrekusnadii
2111000440590729504,2026-10-16T07:45:00.000Z,0,"Prabowo akan Kumpulkan Menteri-Wamen di Istana Bogor Malam Ini

https://t.co/OClEuvnVjq",2111000440590729504,,,in,,0,0,0,https://x.com/TirtoID/status/2111000440590729504,4187275698,TirtoID
2111000423696109614,2026-10-16T07:44:56.000Z,0,Prabowo mundur lo anjing!!!!!!! https://t.co/rPnzIJOOuo,2111000423696109614,https://pbs.twimg.com/media/HUvHfo9aoAA0OFc.jpg,,in,,0,0,0,https://x.com/hendra_balikin/status/2111000423696109614,2166281996,hendra_balikin
2111000395866886553,2026-10-16T07:44:49.000Z,1,Dan gw adalah salah satu korban gempa lombok 2018 yg alhamdulillah selamat itu. Sedikit fun fact berapa kali kali prabowo nyalon vs jokowi dulu waktu pilpres di lombok selalu gede dukungannya si Prabowo ini dan jeng jeng jeng eh kejadian bencana pas jokowi jd presiden (jagoan yg https://t.co/a66cP585mb,2111000395866886553,https://pbs.twimg.com/amplify_video_thumb/2111000338933432320/img/j4eOG77GkyeiqWTQ.jpg,,in,,0,0,0,https://x.com/naturemood_/status/2111000395866886553,1623987941201842176,naturemood_
2110946359037870138,2026-10-16T07:44:47.000Z,0,@youngmasterjcw @MiskinTV_ Tapi yg diliat disitu bukan cuma Kalimantan aja deh karena peta Sulawesi juga kayak sdh menyatu dengan Kalimantan dan ditulis Singapore,2111000389189562626,,youngmasterjcw,in,,0,0,0,https://x.com/Riansyah040215/status/2111000389189562626,1923285244427501568,Riansyah040215
2111000386312278383,2026-10-16T07:44:47.000Z,0,"Perdana Menteri Singapura, Lawrence Wong, berkata pihaknya sedang mengenal pasti syarikat yang mungkin terbabit dalam kebakaran berkenaan.

https://t.co/nLRnFXJXXI

Yang sahih di RTM'
#RTM #BeritaRTM #MalaysiaMadani #TaatSetia #BersamaMALAYSIAKU #RancakkanMADANI #MADANIBekerja https://t.co/MRkJdphmiz",2111000386312278383,https://pbs.twimg.com/media/HUvHidEaMAAWV0g.jpg,,in,,0,0,0,https://x.com/beritartm/status/2111000386312278383,704725700,beritartm
2110954676627595493,2026-10-16T07:44:44.000Z,0,"@txtdrimedia stop ngomong kebakaran hutan, itu pembakaran hutan.",2111000375751024736,,txtdrimedia,in,,0,0,0,https://x.com/Bucha63473312/status/2111000375751024736,1158903222578212864,Bucha63473312
2111000362433868165,2026-10-16T07:44:41.000Z,0,"and also waktu itu aku lagi hts an sm cowo ilpol, thanks to him aku jadi punya banyak pengetahuan kenapa ga pilih prabowo hihi",2111000362433868165,,,in,,0,0,0,https://x.com/raracyraa/status/2111000362433868165,1807154344355348480,raracyraa
2111000345963028499,2026-10-16T07:44:37.000Z,0,"MSCI bukan sekadar indeks: dapatkah Indonesia membuktikan bahwa transparansi pasar telah menjadi praktik, bukan hanya peta jalan? @ojkindonesia  @IDX_BEI @prabowo",2111000345963028499,,,in,,0,0,0,https://x.com/sugiyarto_semsi/status/2111000345963028499,1959829346,sugiyarto_semsi
2111000331408810157,2026-10-16T07:44:34.000Z,0,"Jakim tanpa asap kebakaran aja berat, apakabar nanti JRF😖",2111000331408810157,,,in,,0,0,0,https://x.com/nom33rcy/status/2111000331408810157,1009334587221147648,nom33rcy
2111000323628425522,2026-10-16T07:44:32.000Z,1,"YA ALLAH BERTAMBAH 1 ORANG YANG MENINGGAL DALAM KEBAKARAN GUNUNG BROMO😭🙏
turut berdukacita untuk keluarga korban, semoga amal ibadah korban diterima dan ditempatkan di tempat terbaik disisinya🤲 https://t.co/0vju26dd6M",2111000323628425522,https://pbs.twimg.com/media/HUvHhBQaIAEEVGG.jpg,,in,,0,0,0,https://x.com/suncomeinrain/status/2111000323628425522,1389107518702374915,suncomeinrain
2111000309157769644,2026-10-16T07:44:28.000Z,0,"Kabut asap akibat kebakaran hutan dan lahan (karhutla) menyelimuti kawasan Ibu Kota Nusantara (IKN), Kalimantan Timur, hingga membuat sejumlah bangunan pemerintahan tampak samar. Istana Garuda, rumah susun aparatur sipil negara (ASN), dan Masjid Negara nyaris tidak terlihat jelas https://t.co/K5vg7X6W3a",2111000309157769644,https://pbs.twimg.com/amplify_video_thumb/2110998358274023424/img/DmklVX91gkCMao33.jpg,,in,,0,0,0,https://x.com/SINDOnews/status/2111000309157769644,231355136,SINDOnews
2111000282889126148,2026-10-16T07:44:22.000Z,0,"Dukung Kemajuan dan Perlindungan KI, Kemenkum Kaltim Koordinasikan Rencana Pembentukan Perda Kekayaan Intelektual dengan Unikarta

Berita selengkapnya dapat diakses melalui
https://t.co/ino5SlfkYm

#KementerianHukum 
#LayananHukumMakinMudah 
#kanwilkemenkumkalimantantimur https://t.co/B14j2AeZI4",2111000282889126148,https://pbs.twimg.com/media/HUvHd8MbcAA7itS.jpg,,in,,0,0,0,https://x.com/kemenkumkaltim/status/2111000282889126148,2516891534,kemenkumkaltim
2110975391351603710,2026-10-16T07:44:17.000Z,0,"@forfracha @prabowo asli nad, mana lagi angin jugaa",2111000261808263484,,forfracha,in,,0,0,0,https://x.com/edokusai/status/2111000261808263484,1522713928299655170,edokusai
2111000220712743413,2026-10-16T07:44:07.000Z,0,"Km yg mana, busuk ap brsih @prabowo",2111000220712743413,,,in,,0,0,0,https://x.com/beetswax/status/2111000220712743413,1798587991004524544,beetswax
2110933597213606043,2026-10-16T07:44:01.000Z,0,"@Ndrewstjan Saya aja udah mulai hilang kepercayaan ke Prabowo apalagi banyak masalah yang ditimbulkan dari Prabowo padahal baru 2 tahun, siap2 2029 Prabowo kalah",2111000193470456086,,Ndrewstjan,in,,0,0,0,https://x.com/RahagungC33511/status/2111000193470456086,1837501803568717824,RahagungC33511
2111000142698733998,2026-10-16T07:43:49.000Z,0,Kebakaran Limbah Penggergajian Kayu di Argasoka Babinsa dan Damkar Bergerak ke Lokasi https://t.co/qwWhJIOD2l,2111000142698733998,https://pbs.twimg.com/amplify_video_thumb/2110999932081700865/img/97MwxzcbXWQG21Jl.jpg,,in,,0,0,0,https://x.com/Kodim0704bna/status/2111000142698733998,890727850923376640,Kodim0704bna
2110714103853707394,2026-10-16T07:43:44.000Z,0,"@Tan_Mar3M Bener kata orang²...stres di jaman jokowi, gila dijaman prabowo",2111000121513234853,,Tan_Mar3M,in,,0,0,0,https://x.com/ahmadfaisal_13/status/2111000121513234853,276989068,ahmadfaisal_13
2110934617448661254,2026-10-16T07:43:41.000Z,0,"@kamarlintang kenapa ya dedy corbuzier selalu ada di luar influencer yang harus dicancel dan dituntut untuk bersuara ya?? padahal dia juga dapet jabatan dari prabowo, selalu ngebela prabowo segitunya sampe ngegoblok2in kita soal mbg.. dia pendukung garis keras prabowo sejal awal",2111000111354610002,,kamarlintang,in,,0,0,0,https://x.com/WeeYjh23/status/2111000111354610002,1622994199015718912,WeeYjh23
2111000072657998199,2026-10-16T07:43:32.000Z,0,"Perkuat Perlindungan Inovasi Akademik, Kemenkum Kaltim Gelar Pelatihan Pendaftaran KI dan Pembinaan Sentra KI di Kutai Timur

Berita selengkapnya dapat diakses melalui
https://t.co/GnwbIoyYlT

#KementerianHukum 
#LayananHukumMakinMudah 
#kanwilkemenkumkalimantantimur https://t.co/t4z3s5bylZ",2111000072657998199,https://pbs.twimg.com/media/HUvHUaFbgAAA2cv.jpg,,in,,0,0,0,https://x.com/kemenkumkaltim/status/2111000072657998199,2516891534,kemenkumkaltim
2110995767527960839,2026-10-16T07:43:28.000Z,0,@gitanofieka kak dia dateng langsung aja gak datengin yg kena kebakaran tp dikasih liat lahan kosong 🙂 emang ignorance indonesia makmur dipikiran dia doang. pdhal kliatan klo dia mau k kalimantan itu pesawat udh gbs flight 🥲,2111000055511691391,,gitanofieka,in,,0,0,0,https://x.com/sekarflo/status/2111000055511691391,169053480,sekarflo
2111000047080927738,2026-10-16T07:43:26.000Z,0,Indonesia udah mau ancur masi aja dibelain tu orang bodoh @prabowo,2111000047080927738,,,in,,0,0,0,https://x.com/Raybadoet/status/2111000047080927738,1548470138269081602,Raybadoet
2110993291093365154,2026-10-16T07:43:24.000Z,0,@LambeSahamjja Yang benar PRABOWO kah!,2111000037962768776,,LambeSahamjja,in,,0,0,0,https://x.com/orang_miiskin/status/2111000037962768776,539776095,orang_miiskin
2110966939795513790,2026-10-16T07:43:19.000Z,0,"@manwithoutlovey @faqueerm1squeen @undesiringmecha Kan gubernurnya orang Kalimantan, bang. Jadi gk bakal digorok walopun tolol. Yang dia mau gorok cuma orang luar Kalimantan doang.",2111000016471093538,,manwithoutlovey,in,,0,0,0,https://x.com/LLawleett/status/2111000016471093538,1779226661919272962,LLawleett
2110923693253894516,2026-10-16T07:43:17.000Z,0,@inipiian_ Prabowo paling sulit,2111000009491779771,,inipiian_,in,,0,0,0,https://x.com/alldyspa/status/2111000009491779771,1256432920501182466,alldyspa
2111000006807486731,2026-10-16T07:43:16.000Z,0,Kerjaan abang gw emg mantep. Tapi fia ga bisa maki Prabowo. Big win ✊🏼,2111000006807486731,,,in,,0,0,0,https://x.com/torquemaxx/status/2111000006807486731,1496760260643545089,torquemaxx
2110999973131362525,2026-10-16T07:43:08.000Z,0,"Halo, Sobat Mahakam! 👋
Kenalan yuk dengan Sobat Mahakam yang sedang menjalani program magang di BWS Kalimantan IV Samarinda! 

#SigapMembangunNegeriUntukRakyat
#MengelolaAirUntukNegeri https://t.co/VRSboxmKdw",2110999973131362525,https://pbs.twimg.com/amplify_video_thumb/2110997934674481152/img/kt0Bx1tsWyBr2mFj.jpg,,in,,0,0,0,https://x.com/pu_sda_bwsk4/status/2110999973131362525,724840214145961992,pu_sda_bwsk4
2110897337476497718,2026-10-16T07:43:06.000Z,0,"@LambeSahamjja Halah dungu, argumen mu udah gak relevan pasti akan berpihak ke prabowo.. munafik",2110999963123789851,,LambeSahamjja,in,,0,0,0,https://x.com/AdnanNurwachid/status/2110999963123789851,1169907722499719175,AdnanNurwachid
2110981300706501077,2026-10-16T07:43:03.000Z,0,@its__Arthur19 @prabowo MBG nomer satu,2110999952415748500,,its__Arthur19,in,,0,0,0,https://x.com/babyto332/status/2110999952415748500,1743137844133285888,babyto332
2110999938536726545,2026-10-16T07:43:00.000Z,0,"Prabowo Panggil Menteri dan Kepala Badan ke Istana Bogor Jumat Malam
https://t.co/83HWPZrL3n",2110999938536726545,,,in,,0,0,0,https://x.com/Nusavox08/status/2110999938536726545,1947698074547326977,Nusavox08
2110999927937732665,2026-10-16T07:42:57.000Z,0,"Pemberdayaan Masyarakat Muhaimin Iskandar menggalang aksi solidaritas bersama para pelaku industri untuk menyalurkan bantuan darurat berupa masker dan air bersih bagi warga terdampak kebakaran hutan dan lahan (Karhutla), Jumat (16/10). 🎥Rea https://t.co/yX228XGD2q",2110999927937732665,https://pbs.twimg.com/amplify_video_thumb/2110999869162913792/img/S3t6Ilgq5ZdgsYdv.jpg,,in,,0,0,0,https://x.com/RadioElshinta/status/2110999927937732665,121640063,RadioElshinta
2110946359037870138,2026-10-16T07:42:56.000Z,0,"@MiskinTV_ Siap otw kalimantan, infokan kpr yg ready 😆",2110999921646325900,,MiskinTV_,in,,0,0,0,https://x.com/rhkQ/status/2110999921646325900,764506068,rhkQ
2110891147900121175,2026-10-16T07:42:54.000Z,0,"@aniblogsan52394 @Dospemz Tidak cukup hanya cari siapa yang Salah. Mereka yang punya wewenang Dan tugas mencari yang Salah, silahkan. Tapi hanya itu aja tidak akan mengembalikan kondisi hutan Kalimantan. Prof bagus fokus pada harus ada yang juga bekerja melakukan restorasi kondisi Kalimantan.",2110999914675143165,,regalos_torus,in,,0,0,0,https://x.com/regalos_torus/status/2110999914675143165,1558490216671084544,regalos_torus
2110903177860317207,2026-10-16T07:42:50.000Z,0,"@InFebriyan128 Padahal Kalimantan tuh surganya ekosistem, menhut nya aja yg plenger ga bisa kerja,",2110999895675216360,,InFebriyan128,in,,0,0,0,https://x.com/NakatoWill53510/status/2110999895675216360,1773326748492648448,NakatoWill53510
2110962686364442871,2026-10-16T07:42:49.000Z,0,@onyour_cissism bangun kalo presidennya bukan prabowo lg,2110999892911165743,,onyour_cissism,in,,0,1,0,https://x.com/delouvre00/status/2110999892911165743,1261385013087531008,delouvre00
2110979794154430967,2026-10-16T07:42:48.000Z,7,@LambeSahamjja Tolong itu gubernur kalimantan coba disuruh sekolah ulang. Masa pernyataan selayaknya gubernur kyk gini ga bisa?,2110999886623855103,,LambeSahamjja,in,,0,0,0,https://x.com/futonmyouji/status/2110999886623855103,1621177559408058368,futonmyouji
2110999833427509621,2026-10-16T07:42:35.000Z,0,"Lindungi Inovasi Daerah dan Perluas Sinergi KI, Kemenkum Kaltim Berpartisipasi di Pekan Raya Kutim Expo 2026

Berita selengkapnya dapat diakses melalui
https://t.co/2GjaqMioni

#KementerianHukum 
#LayananHukumMakinMudah 
#kanwilkemenkumkalimantantimur https://t.co/kZCg6KPqIZ",2110999833427509621,https://pbs.twimg.com/media/HUvHGQGaIAACQOt.jpg,,in,,0,0,0,https://x.com/kemenkumkaltim/status/2110999833427509621,2516891534,kemenkumkaltim
2110999791996170591,2026-10-16T07:42:25.000Z,0,bangsat semua lu yang pilih prabowo,2110999791996170591,,,in,,0,0,0,https://x.com/nozoitaa/status/2110999791996170591,1474330223487324160,nozoitaa
2110999791711002645,2026-10-16T07:42:25.000Z,0,"""Seorang bayi berusia 1 tahun 2 bulan di Samarinda, Kalimantan Timur, meninggal setelah mengalami sesak napas dan sempat menjalani perawatan intensif di ruang Intensive Care Unit (ICU) rumah sakit.⁠ "" 😥😭",2110999791711002645,,,in,,0,0,0,https://x.com/hanan052020/status/2110999791711002645,1417251642085318663,hanan052020
2110804242181312590,2026-10-16T07:42:22.000Z,0,"@espwilisa @jerukiyowok Gue ga mau tau lu bicara sebagai anak prabowo juga gue ga mau tau. Cuma membandingkan dengan fave lu gimana, berarti perasaan fave lu ga valid karena ngapain dia nangis nangis di acara, mau bikin drama doang? Kan kalau sesuai logika lo kaya gitu.",2110999777672679710,,espwilisa,in,,0,0,0,https://x.com/byurbaby/status/2110999777672679710,1282325268292497409,byurbaby
2110999741152788792,2026-10-16T07:42:13.000Z,0,bagian sedihnya adalah warga kalimantan punya harapan besar pada pemimpin baru. https://t.co/h6hhVBhmS3,2110999741152788792,https://pbs.twimg.com/media/HUvHEqpbEAA6rPt.jpg,,in,,0,0,0,https://x.com/faisalrosanto/status/2110999741152788792,73484895,faisalrosanto
2110996790044766275,2026-10-16T07:42:11.000Z,0,"Ini artikelnya di Tempo

https://t.co/dYdSnTvkh2",2110999731967242569,,abulmuzaffar10,in,,0,0,0,https://x.com/abulmuzaffar10/status/2110999731967242569,909850779749466112,abulmuzaffar10
2110999574068474159,2026-10-16T07:42:05.000Z,0,@littlebubear bangun kalo presidennya bukan prabowo lagi,2110999709620006932,,littlebubear,in,,0,1,0,https://x.com/delouvre00/status/2110999709620006932,1261385013087531008,delouvre00
2110999703295082622,2026-10-16T07:42:04.000Z,0,"Hari ini kita berduka untuk tanah Kalimantan,
untuk langit yang tak lagi biru,
untuk hutan yang terbakar habis,
untuk udara yang tak lagi bersih,
untuk langit yang tak lagi biru.
 
Dan hari ini kita berduka untuk matinya nurani pemerintah Indonesia.

https://t.co/51EzJVY1NX https://t.co/pprqSrwISy",2110999703295082622,https://pbs.twimg.com/media/HUvHCR3aoAAOpgz.jpg,,in,,0,0,0,https://x.com/peritapimenulis/status/2110999703295082622,1863521222988075008,peritapimenulis
2110994059770905015,2026-10-16T07:42:01.000Z,0,@_amandapuspitaa soffel anget 1 buat Opa Prabowo,2110999690279870949,,_amandapuspitaa,in,,0,0,0,https://x.com/chillducc/status/2110999690279870949,1680814449555566592,chillducc
2110999681790792030,2026-10-16T07:41:59.000Z,0,"Wujudkan Hilirisasi dan Penguatan Ekosistem KI di Kutai Timur, Kemenkum Kaltim Dampingi Survei Maturitas KI 2026

Berita selengkapnya dapat diakses melalui
https://t.co/y3SnRcMoHp

#KementerianHukum 
#LayananHukumMakinMudah 
#kanwilkemenkumkalimantantimur https://t.co/idh7IDDYIH",2110999681790792030,https://pbs.twimg.com/media/HUvG_rCaoAEYlE6.jpg,,in,,0,0,0,https://x.com/kemenkumkaltim/status/2110999681790792030,2516891534,kemenkumkaltim
2110968838275964963,2026-10-16T07:41:56.000Z,0,@LambeSahamjja Tenaga mereka lebih banyak buat ngebungkam berita kebakaran dibandingkan buat madamin api,2110999671489626618,,LambeSahamjja,in,,0,0,0,https://x.com/Syipiiap/status/2110999671489626618,1175752795607093248,Syipiiap
2110999653739270212,2026-10-16T07:41:52.000Z,0,@RajaJuliAntoni kamu mentrik kesayangan @prabowo,2110999653739270212,,RajaJuliAntoni,in,,0,0,0,https://x.com/kuntoadji/status/2110999653739270212,50895997,kuntoadji
2110751410409378059,2026-10-16T07:41:51.000Z,0,@cowostress Jangan pilih Prabowo saat pemilu,2110999649775763883,,cowostress,in,,0,0,0,https://x.com/ju_dafirenze/status/2110999649775763883,1381275787140075522,ju_dafirenze
2110999617248834018,2026-10-16T07:41:43.000Z,0,emang prabowo anjing,2110999617248834018,,,in,,0,0,0,https://x.com/ninefahrenheit/status/2110999617248834018,1547889376373248003,ninefahrenheit
2110232008119177538,2026-10-16T07:41:39.000Z,0,"@al_fajr68 @temanduit @gibran_tweet @dennyindrayana @prabowo @grok iya betul sekali....
@Ki_Nusantara99 
TULISANKU TERLALU MENGHIBUR TERMUL",2110999600584896559,,al_fajr68,in,,0,0,0,https://x.com/ardjasa_solo/status/2110999600584896559,1950344826194710528,ardjasa_solo
2110999585065742467,2026-10-16T07:41:36.000Z,1,"gini, kebusukan prabowo membuat jokowi terlihat mendingan 
padahal membandingkan dua hal buruk ga ada gunanya juga",2110999585065742467,,,in,,0,0,0,https://x.com/pendthosa/status/2110999585065742467,2090407859377070080,pendthosa
2110999577319166333,2026-10-16T07:41:34.000Z,0,Gue dah muak banget anjing sama prabowo. Ni orang awet dalam doa gue soal kehancuran,2110999577319166333,,,in,,0,0,0,https://x.com/fmokoz/status/2110999577319166333,1370363980674338816,fmokoz
2110999575242899902,2026-10-16T07:41:33.000Z,0,Gara² prabowo babi semua pada tutup Karna asap https://t.co/0nGTrmnoIc,2110999575242899902,https://pbs.twimg.com/media/HUvG613bIAACvo6.jpg,,in,,0,0,0,https://x.com/Fyners18/status/2110999575242899902,230068840,Fyners18
2110999561066172759,2026-10-16T07:41:30.000Z,0,"maut dalam kebakaran dua rumah berkembar di Kampung Koh, Sitiawan 
https://t.co/3MtuTOY1uv",2110999561066172759,,,in,,0,0,0,https://x.com/MgPerak/status/2110999561066172759,1683735839850004481,MgPerak
2110999521941680226,2026-10-16T07:41:21.000Z,0,"Hutan Kebakaran, IHSG juga 🔥",2110999521941680226,,,in,,0,0,0,https://x.com/tulangputra/status/2110999521941680226,59953809,tulangputra
2110966939795513790,2026-10-16T07:41:12.000Z,3,@faqueerm1squeen @undesiringmecha Kalo orang Kalimantan walopun asbun gpp ya? Kalo orang luar Kalimantan walopun bener mau digorok. Gak heran kalo dipimpin sama pemimpin tolol wkwkwk,2110999485321220113,,faqueerm1squeen,in,,0,0,0,https://x.com/LLawleett/status/2110999485321220113,1779226661919272962,LLawleett
2110997981101203867,2026-10-16T07:41:09.000Z,1,"@GARUDAMERAH__ @ucoxregar @prabowo @sarah_pndjtn @4Y4NKZ @Sammi86Pilang @Subur0204 @SotoAyam1970 Gak masalah mau mendirikan  1000 gereja, 1000 mesjid, 1000 Vihara, 1000 Pura

Faktanya  kebanyakan umat muslim di negeri ini menjadi sekuler 😂",2110999472373465369,,GARUDAMERAH__,in,,0,0,0,https://x.com/a999on/status/2110999472373465369,2041804213986951168,a999on
2110948210135155035,2026-10-16T07:41:03.000Z,0,"@LambeSahamjja Kemungkinan asing lihat program² Prabowo ini arahnya pada dominan nya peran negara mengontrol pasar, yang itu oleh asing dilihat membahayakan",2110999449925521619,,LambeSahamjja,in,,0,0,0,https://x.com/1umarsidik/status/2110999449925521619,325507498,1umarsidik
2110994927127834959,2026-10-16T07:41:02.000Z,0,@1nt0easy Bang lagi dimana emang? Apa di Kalimantan?,2110999442023404017,,1nt0easy,in,,0,1,0,https://x.com/akiracakra/status/2110999442023404017,2028655157924560896,akiracakra
2110999441843118287,2026-10-16T07:41:02.000Z,0,"Ya Allah ni orang @prabowo kebanyakan mudharat daripada manfaatnya selama menjabat, tolong lengserin segera ya Allah",2110999441843118287,,,in,,0,0,0,https://x.com/beetswax/status/2110999441843118287,1798587991004524544,beetswax
2110756361143484733,2026-10-16T07:40:50.000Z,0,@namelesid masi ada yg pilih prabowo astaga,2110999394099294408,,namelesid,in,,0,0,0,https://x.com/jackdp27/status/2110999394099294408,1378994177329954818,jackdp27
2110987990915010919,2026-10-16T07:40:50.000Z,0,@txtdrjkt Ini bukan kebakaran hutan min?,2110999392421597517,,txtdrjkt,in,,0,0,0,https://x.com/blqs__s/status/2110999392421597517,1831051307446329344,blqs__s
2110981300706501077,2026-10-16T07:40:48.000Z,0,@its__Arthur19 @prabowo Duit nya nggak ada 😃,2110999386914500861,,its__Arthur19,in,,0,0,0,https://x.com/CelineAR24/status/2110999386914500861,2060271898744037376,CelineAR24
2110927199083638890,2026-10-16T07:40:43.000Z,0,@NyaiNeneng Wah kau nih..... statement adu kambing. Yang jelas mereka sudah mendesak pemerintah u/ memadamkan api di hutan Kalimantan.,2110999361895412021,,NyaiNeneng,in,,0,0,0,https://x.com/bagushermawan66/status/2110999361895412021,2925058837,bagushermawan66
2110999318157275494,2026-10-16T07:40:32.000Z,1,"Rachel setauku dia pernah update klo nyesel soal keputusannya di pihak 02, beberapa kli dia up jg soal kebakaran hutan ini

Disclaimer bkn fans RV, cuma qrt aja soalnya prnah tau",2110999318157275494,,,in,,0,0,0,https://x.com/hawtsuharu/status/2110999318157275494,857043557760212992,hawtsuharu
2110699290888909248,2026-10-16T07:40:27.000Z,0,@Kimberley_PS08 Tp jujur tanpa harus di jelekan prabowo sudah menjelek kan dirinya sendiri 🙏,2110999295252169205,,Kimberley_PS08,in,,0,0,0,https://x.com/Gunadi____/status/2110999295252169205,1102195438940119040,Gunadi____
2110929784469626920,2026-10-16T07:40:15.000Z,0,@LambeSahamjja kok ga teratasi? katanya tinggal 329hektar lahan yang kebakaran 🤭,2110999247072231689,,LambeSahamjja,in,,0,0,0,https://x.com/furioushanks/status/2110999247072231689,330340103,furioushanks
2110891147900121175,2026-10-16T07:40:15.000Z,0,"@aniblogsan52394 @Dospemz Pembicaraanya adalah, apakah penyataan prof bagus itu adalah penyataan yang tidak melihat kenyataan atau tidak? Beliau lihat pemerintah sudah salah dan lalai, tapi nasi udah jadi bubur, Kalimantan sudah terbakar, sekarang apa yang pemerintah harus lakukan. Itu fokus Dari videonya",2110999244593303577,,regalos_torus,in,,0,1,0,https://x.com/regalos_torus/status/2110999244593303577,1558490216671084544,regalos_torus
2110947859759825066,2026-10-16T07:40:12.000Z,0,"@didiaah_ wow, km pasti pendukung prabowo",2110999233214193833,,didiaah_,in,,0,0,0,https://x.com/irulanm66/status/2110999233214193833,1693894238185086976,irulanm66
2110688902034096393,2026-10-16T07:40:10.000Z,0,@ch_chotimah2 Dr awal sdh curiga si hashim ini ikut bermain dlm kebakaran hutan.. kyk negara punya kel mereka aja.. karena apa.. karena rakyat diam mknya mereka semena2,2110999224519430476,,ch_chotimah2,in,,0,0,0,https://x.com/Fid3llio12/status/2110999224519430476,1508209752119320576,Fid3llio12
2110999189413130541,2026-10-16T07:40:01.000Z,0,"Baca di sini: https://t.co/YKQYqaK18K

Langit Jakarta dan Surabaya tampak berkabut, memicu dugaan asap karhutla Kalimantan telah menyebar hingga Pulau Jawa. Benarkah klaim yang ramai di media sosial tersebut?

~KQ #AsapKarhutla #PulauJawa [20261016090000365] https://t.co/BUWlPlaJF4",2110999189413130541,https://pbs.twimg.com/media/HUvGkhEbgAAH6pg.jpg,,in,,0,0,0,https://x.com/kompascom/status/2110999189413130541,23343960,kompascom
2110953929324576965,2026-10-16T07:39:58.000Z,0,@Astro_Boy020 Kalo udh gini prabowo mikir ga yaww?,2110999176486301826,,Astro_Boy020,in,,0,0,0,https://x.com/wixinteo/status/2110999176486301826,1523792186323894272,wixinteo
2110999170828091567,2026-10-16T07:39:57.000Z,0,"kebul udud ng ruangan indoor wae wes kemlepek, raiso mbayangke dulur-dulure sek ng Kalimantan, Riau &amp; daerah terdampak karhutla liyane🥲",2110999170828091567,,,in,,0,0,0,https://x.com/fakhri_nugrahaa/status/2110999170828091567,1314727567476191232,fakhri_nugrahaa
2110999129770033488,2026-10-16T07:39:47.000Z,3,"Tukang Doxx MASYARAKAT kapan ya ini Manusia dapat Azab.

Orang super jahat modelan Dasco, Prabowo, Hashim rata-rata dikasih umur panjang sama Tuhan.

Rakyat doain mereka cepetan mati, masih hidup aja mereka 😮‍💨",2110999129770033488,,,in,,0,1,0,https://x.com/taniaviandra/status/2110999129770033488,304946313,taniaviandra
2110999071649615992,2026-10-16T07:39:33.000Z,0,Di Semarang aja sepanas ini gimana di Kalimantan???,2110999071649615992,,,in,,0,0,0,https://x.com/aningpa/status/2110999071649615992,64949913,aningpa
2110999070760411225,2026-10-16T07:39:33.000Z,0,KOALISA JOKODOC-PRABOWO 2029 ADALAH KHAYALAN https://t.co/POHg3EngqL,2110999070760411225,https://pbs.twimg.com/amplify_video_thumb/2110997960687517696/img/a3qvRpPLscESFh8D.jpg,,in,,0,0,0,https://x.com/supriyadi2704/status/2110999070760411225,1299649988,supriyadi2704
2110996790044766275,2026-10-16T07:39:33.000Z,1,"@abulmuzaffar10 beneran curiga kalau selama asap ga sampe jawa, ga bakalan pernah kelar ini asap yang di kalimantan sama sumatera",2110999069640610083,,abulmuzaffar10,in,,0,0,0,https://x.com/andniput/status/2110999069640610083,1654277842648322048,andniput
2110999043040317937,2026-10-16T07:39:26.000Z,0,"Topup wdp ml udh 34k anjing dari 28k
@prabowo lu kerja yg bener anjing, kesel bgt gw ngentot, tup up wdp jd mahal ni anjing",2110999043040317937,,,in,,0,0,0,https://x.com/_K4FeCN6/status/2110999043040317937,1616094180241215489,_K4FeCN6
2110997019431194744,2026-10-16T07:39:23.000Z,0,"15/15

Pada akhirnya, pertanyaan pentingnya bukan hanya berapa banyak kebakaran berhasil dipadamkan.

Tetapi juga: mengapa lahan tetap rentan terbakar, apakah pencegahan menyasar sumber risikonya, siapa yang menanggung biaya, dan siapa yang bertanggung jawab ketika pencegahan",2110999029639438428,,HidsalJ,in,,0,0,0,https://x.com/HidsalJ/status/2110999029639438428,1382725234445348864,HidsalJ
2110644907895558396,2026-10-16T07:39:23.000Z,0,@DedynurPalakka @_Sadewa__ @Uki23 @Gerindra Logika lw dimana ... yg bermasalah gibran knp prabowo dibawa bawa 😝,2110999029299700092,,DedynurPalakka,in,,0,0,0,https://x.com/jurigh107/status/2110999029299700092,2044585134897213441,jurigh107
2110999013877223674,2026-10-16T07:39:20.000Z,0,"Jangankan manusia, binatang aja tersiksa hidup di kalimantan saat ini",2110999013877223674,,,in,,0,0,0,https://x.com/yudhaacngkring/status/2110999013877223674,1219982392762322944,yudhaacngkring
2110999011184550235,2026-10-16T07:39:19.000Z,0,"side effect being kalimantan people, disinilah paru paru gua di uji for almost 4 fucking month",2110999011184550235,,,in,,0,0,0,https://x.com/JohnnySuh9295/status/2110999011184550235,1280499619449929731,JohnnySuh9295
2110941510653104275,2026-10-16T07:39:14.000Z,0,@hrdbacot #2tahunGerakNyata prabowo wkwkw,2110998988656943538,,hrdbacot,in,,0,0,0,https://x.com/mrEko_84/status/2110998988656943538,1794451186978099200,mrEko_84
2110998965026271523,2026-10-16T07:39:08.000Z,0,"semangat banget gue retweet hate tweet ke Prabowo, udah sebenci itu emang.",2110998965026271523,,,in,,0,0,0,https://x.com/xolumbina/status/2110998965026271523,1600753598282940416,xolumbina
2110998963587625139,2026-10-16T07:39:08.000Z,0,"@prabowo taek lah, bgaimana kebakaran hutan ini? Anjing ga becus semuaaa..",2110998963587625139,,prabowo,in,,0,0,0,https://x.com/luciusbardata/status/2110998963587625139,1071615588,luciusbardata
2110998924009820466,2026-10-16T07:38:58.000Z,1,"Baca di sini: https://t.co/2FXuNjMUYz 

BMKG mendeteksi asap karhutla dari Kalimantan memasuki atmosfer Jakarta, Banten, dan Jawa Barat, tetapi belum mencapai permukaan tanah. Bagaimana masyarakat dapat memantau kualitas udara dan mengantisipasi dampak asap karhutla?

~KR #BMKG https://t.co/UzA30R9TpH",2110998924009820466,https://pbs.twimg.com/amplify_video_thumb/2110998824126926849/img/YIkQivhGYANL99oR.jpg,,in,,1,0,0,https://x.com/kompascom/status/2110998924009820466,23343960,kompascom
2110978831565967644,2026-10-16T07:38:56.000Z,0,"@senogp Suruh aja grok munculin dampak kebakaran paling parah era SBY, era Jokowi, era Prabowo parahan mana.",2110998913268502805,,senogp,in,,0,0,0,https://x.com/GamefaqsIDN/status/2110998913268502805,1962315346893021184,GamefaqsIDN
2110874067754684468,2026-10-16T07:38:34.000Z,0,"@TheCurut007 Presiden @prabowo  jangan jadi Bedebah,",2110998822940012757,,TheCurut007,in,,0,0,0,https://x.com/dos135790/status/2110998822940012757,1660880654358441985,dos135790
2110998775011708996,2026-10-16T07:38:23.000Z,0,"Update Peringatan Dini Cuaca Wilayah - Kalimantan Tengah Tgl. 16 Oktober 2026 pkl. 14:40 WIB
Prakirawan - BMKG - Kalimantan Tengah
https://t.co/0AS6mswbf5 https://t.co/cmYfswBvXX",2110998775011708996,https://pbs.twimg.com/media/HUvGMj7bEAAxQ8p.jpg,,in,,0,0,0,https://x.com/infoBMKG/status/2110998775011708996,108543358,infoBMKG
2110920475388133526,2026-10-16T07:38:17.000Z,0,@IDX_BEI Sudah berapa kali ini Pak Bowo? Baru juga 2 tahun @prabowo,2110998752710496523,,IDX_BEI,in,,0,0,0,https://x.com/break_habit/status/2110998752710496523,408557445,break_habit
2110982067567947944,2026-10-16T07:38:09.000Z,0,@buburrayam12 Pada kebakaran yak?,2110998720104018084,,buburrayam12,in,,0,1,0,https://x.com/papavilenn/status/2110998720104018084,2029744498675437568,papavilenn
2110998719390990577,2026-10-16T07:38:09.000Z,1,Kau dengan prabowo sama. Anak babi.,2110998719390990577,,,in,,0,0,0,https://x.com/hopemoonfairy/status/2110998719390990577,851666594740568064,hopemoonfairy
2110998718233334184,2026-10-16T07:38:09.000Z,0,"Gila sih, Elon Musk udah bisa bikin Mobil Terbang aja. Indonesia boro-boro bikin mobil terbang, disini padamin kebakaran hutan aja ga becus, udah gitu masih ributin ijazah wkwkwkwkw...

Sc: Yahoo Finance https://t.co/HHN7I2DlBe",2110998718233334184,https://pbs.twimg.com/amplify_video_thumb/2110998685488455680/img/yHSid0OhQnCITNGY.jpg,,in,,0,0,0,https://x.com/DalamDunia888/status/2110998718233334184,2041352553317761024,DalamDunia888
2110998678504951972,2026-10-16T07:38:00.000Z,0,prabowo ki tai dikei nyowo dadi ra bakal nyandak uteke,2110998678504951972,,,in,,0,0,0,https://x.com/ddaengnyangi/status/2110998678504951972,1800558398578237440,ddaengnyangi
2110998643679584588,2026-10-16T07:37:51.000Z,0,"kebakaran di mana-mana woii, mana penanganannya",2110998643679584588,,,in,,0,0,0,https://x.com/aaqwarium/status/2110998643679584588,1542805195981484032,aaqwarium
2110998562507210982,2026-10-16T07:37:48.000Z,0,"Penyebaran dry ice dilakukan bersamaan dengan Operasi Modifikasi Cuaca (OMC), tetapi keduanya memiliki tujuan berbeda. Teknologi dry ice diarahkan untuk mengurangi penumpukan kabut asap, sedangkan OMC bertujuan merangsang hujan buatan guna membantu pemadaman kebakaran. Pemerintah",2110998629368639491,,GNFI,in,,0,0,0,https://x.com/GNFI/status/2110998629368639491,39677695,GNFI
2110997019431194744,2026-10-16T07:37:48.000Z,0,"11/15

Sebab, banyaknya program belum tentu berarti masalahnya selesai.

Aturan bisa diterbitkan. Anggaran bisa dialokasikan. Kegiatan bisa dilaporkan.

Tetapi apakah risiko kebakaran benar-benar berkurang? Apakah intervensi menyasar lokasi berisiko tinggi dan dilakukan sebelum",2110998628563378183,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110998628563378183,1382725234445348864,HidsalJ
2110707357781225859,2026-10-16T07:37:45.000Z,0,"@heniunique Ya Allah.. turunkan bala tentaraMu berupa hujan, padamkan titik-titik api di bumi Kalimantan, Sumatra, Papua, dll.
Turunkan azabMu pada mereka yang harusnya bertanggungjawab terhadap bencana ini..😭😭😭😭",2110998617163247842,,heniunique,in,,0,0,0,https://x.com/DianRivia5/status/2110998617163247842,1603692798372220929,DianRivia5
2110300141299315120,2026-10-16T07:37:45.000Z,0,"@mediaindonesia MANUSA KARDUS ,PENGADUDOMBA MANUSIA, LAYAK DI GANJAR BAKSR HIDUB² MANUSIA SATU INI,, INGINKAN INDONESIA HANCOR MINA SEPERTI TH 97..
BAKAEKAM MANUSIA SATU INI
@prabowo",2110998615544262875,,mediaindonesia,in,,0,0,0,https://x.com/dos135790/status/2110998615544262875,1660880654358441985,dos135790
2110897337476497718,2026-10-16T07:37:44.000Z,0,"@LambeSahamjja Terus kenapa dia ngoceh d Rosi, dan media lain setelah menjabat d ketiak Prabowo 🤔🙄🤭🥱😮‍💨😮‍💨",2110998614751543435,,LambeSahamjja,in,,0,0,0,https://x.com/murniatauasli/status/2110998614751543435,1734445602807955456,murniatauasli
2110998562507210982,2026-10-16T07:37:43.000Z,0,"Pemerintah menguji metode baru untuk mengurangi kabut asap akibat kebakaran hutan dan lahan (karhutla) dengan menyebarkan es kering atau dry ice menggunakan pesawat di Sumatera Selatan. Menteri Koordinator Bidang Politik dan Keamanan, Dudung Abdurachman, menyampaikan bahwa uji",2110998607898009891,,GNFI,in,,0,1,0,https://x.com/GNFI/status/2110998607898009891,39677695,GNFI
2110998583356899728,2026-10-16T07:37:37.000Z,0,"mau dimanapun tempat tinggal ku skrng , aku ttp merasakan sakit hati banget ngeliat saudara sahabat teman ku di kalimantan kekeringan dan kebakaran hebat 😭",2110998583356899728,,,in,,0,0,0,https://x.com/sigemoyyyyyyy15/status/2110998583356899728,1440302537161134093,sigemoyyyyyyy15
2110998565594280205,2026-10-16T07:37:33.000Z,0,Please bgt pak duit pajak gue digunain buat kalimantan dulu lah. @prabowo #prayforkalimantan,2110998565594280205,,,in,,0,0,0,https://x.com/pemaniseni/status/2110998565594280205,302761781,pemaniseni
2110998564797120558,2026-10-16T07:37:32.000Z,0,"Kebakaran hutan dan lahan di Palangka Raya, Kalimantan Tengah, sempat meluas mendekati permukiman warga akibat tiupan angin kencang.

Setelah berbulan-bulan bergelut dengan pekatnya kabut asap, guyuran hujan singkat selama kurang lebih 10 menit akhirnya turun di kawasan Jalan https://t.co/owekK3xDD6",2110998564797120558,https://pbs.twimg.com/amplify_video_thumb/2110998324061016064/img/3aR_2zcHSMVYBorj.jpg,,in,,0,0,0,https://x.com/kompascom/status/2110998564797120558,23343960,kompascom
2110998564054987150,2026-10-16T07:37:32.000Z,0,"Bahkan gw gatau sumpah dan kutukan apalagi yg harus gw teriakkan, gw udh ditahap berpikir neraka pun masih terlalu baik buat prabowo dan antek2nya.",2110998564054987150,,,in,,0,0,0,https://x.com/caaciicuu_u/status/2110998564054987150,1831826487303139330,caaciicuu_u
2110998559621562483,2026-10-16T07:37:31.000Z,0,"Market seharian dibiarkan tanpa response resmi pemerintah @prabowo , dan baru malam hari tepat jelang akhir pekan dmn market akn tutup 2 hari, hal ini baru akn dibahas 😁

Sampai disini jelas kan skenarionya?! 😁

Retail jgn masuk dulu, maksa masuk bs bunuh diri Pak 🤭",2110998559621562483,,,in,,0,0,0,https://x.com/fortisfortuna_9/status/2110998559621562483,2281694042,fortisfortuna_9
2110757133495173262,2026-10-16T07:37:29.000Z,0,@jjkstaan2 tapi kak alhamdulillah denger denger di kalimantan udah turun hujan di beberapa daerah,2110998551174254637,,jjkstaan2,in,,0,0,0,https://x.com/mocacinooy/status/2110998551174254637,1739614028459294720,mocacinooy
2110998541053387208,2026-10-16T07:37:27.000Z,0,gua gapernah seuring uringan ini selama main saham bangsattt prabowo kontol,2110998541053387208,,,in,,0,1,0,https://x.com/tipsyymonkeyy/status/2110998541053387208,1520275437179777030,tipsyymonkeyy
2110998520786465000,2026-10-16T07:37:22.000Z,0,"Rezim laknat. Kalo ga bunuh rakyat, bunuh binatang. Demi Allah gw akan bersumpah di akhirat kelak kalo rezim prabowo ini banyak dzolim nya ke mahluk hidup mau manusia mau binatang",2110998520786465000,,,in,,0,0,0,https://x.com/saintiker_/status/2110998520786465000,887498408,saintiker_
2110982237416288354,2026-10-16T07:37:21.000Z,0,"@daybyzak gw mikir ini bgt dr kmrn, mslahnya story aku buat promoin tmpt club ak kerja. kek abis post kalimantan trus share info party kan ga lucu ya😭",2110998518060228940,,daybyzak,in,,0,0,0,https://x.com/debitbca/status/2110998518060228940,1195898907881959424,debitbca
2110998516902588886,2026-10-16T07:37:21.000Z,0,"Ini galian sepanjang Daan Mogot sampe JORR tuh kapan kelarnya ya? 

Kiri selesai, geser kanan. Gitu aja terus sampe Prabowo pergi meninggalkan kita semua~ https://t.co/pgtaKMCh8h",2110998516902588886,https://pbs.twimg.com/media/HUvF9ZNbEAAVJDj.jpg,,in,,0,0,0,https://x.com/tuhkanasu/status/2110998516902588886,96932909,tuhkanasu
2110998511479386578,2026-10-16T07:37:20.000Z,0,"GAPKI Minta Penanganan Karhutla Berbasis Bukti, Hanya 3,7 Persen Kebakaran Tercatat di Area Sawit Berdiri

JAKARTA – Gabungan Pengusaha Kelapa Sawit Indonesia (GAPKI) meminta penanganan kebakaran hutan dan lahan (karhutla) dilakukan berdasarkan data, pemeriksaan lapangan, dan https://t.co/hTVV8p7s0v",2110998511479386578,https://pbs.twimg.com/media/HUvF9A-acAAJXbt.jpg,,in,,0,0,0,https://x.com/RadioElshinta/status/2110998511479386578,121640063,RadioElshinta
2110998481028764050,2026-10-16T07:37:12.000Z,0,"Ada hujan sebentar hari ini di Kuala Lumpur. Masih terlihat masih berkabut asap imbas dr karhutla. 

Tetap waspada. Semoga karhutla di Kalimantan dan daerah2 lainnya bisa segera padam!  

Bila ada pelaku yang sengaja membakar hutan/lahan, semoga kelakuan kalian dibalas olehNya https://t.co/igcjub1TOi",2110998481028764050,https://pbs.twimg.com/amplify_video_thumb/2110998365769281536/img/yZXEIYr2Sj_gfIPq.jpg,,in,,0,0,0,https://x.com/yusufgunawan/status/2110998481028764050,78619866,yusufgunawan
2110891147900121175,2026-10-16T07:37:09.000Z,0,@regalos_torus @Dospemz anda itu gak paham ya yang saya maksud?  kalau mau gak terjadi kebakaran kasih duid segar untuk orang sekitar agar buka lahan gak dibakar.. pakai sistem harian kalau perlu . uangnya ada gak?,2110998467283935439,,regalos_torus,in,,0,1,0,https://x.com/aniblogsan52394/status/2110998467283935439,1664876228401303554,aniblogsan52394
2110998452947595628,2026-10-16T07:37:06.000Z,0,"4 maut ketika memadam kebakaran di Indonesia yang hasilkan jerebu toksik

#BHdunia Singapura duduki tempat teratas penarafan IQAir bagi bandar utama paling tercemar di dunia, diikuti Kuala Lumpur di tempat kedua dan Jakarta di tempat keenam

https://t.co/OUcnfENONm",2110998452947595628,,,in,,0,0,0,https://x.com/bharianmy/status/2110998452947595628,63070483,bharianmy
2110998442504044993,2026-10-16T07:37:03.000Z,0,dan kata admin @Gerindra masyarakat kalimantan ga ada yang protes,2110998442504044993,,,in,,0,0,0,https://x.com/yourcl1ngyleo/status/2110998442504044993,3265955491,yourcl1ngyleo
2110997019431194744,2026-10-16T07:37:03.000Z,0,"9/15

Lalu, apakah banyaknya program pencegahan berarti masalahnya sudah ditangani dengan tepat?

Jefferson dkk. meneliti 60 intervensi pengelolaan kebakaran di lahan gambut Riau selama 1999 sampai 2016.

Studi mereka menemukan kesenjangan antara rekomendasi ilmiah dan cara",2110998440935362980,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110998440935362980,1382725234445348864,HidsalJ
2110998437324095775,2026-10-16T07:37:02.000Z,0,prabowo dan jajarannya lengser dan diganti orang pintar dan baik. 🥹,2110998437324095775,,,in,,0,0,0,https://x.com/whipielast/status/2110998437324095775,2479024759,whipielast
2110998409717125227,2026-10-16T07:36:55.000Z,0,Sentimen gue terhadap prabowo...... https://t.co/XXKHKLv6hw,2110998409717125227,https://pbs.twimg.com/media/HUvF3OBagAAa52X.jpg,,in,,0,0,0,https://x.com/sopjamur_/status/2110998409717125227,1592445736054304768,sopjamur_
2110998382059942225,2026-10-16T07:36:49.000Z,0,"ANJINGGGGGGGG PRABOWO LU DZOLIM BANGET BANGSATTTTT, LU DAN ANTEK ANTEK LU BETUL BETUL TONE DEAF MAMPUSS",2110998382059942225,,,in,,0,0,0,https://x.com/worriestsv/status/2110998382059942225,1996972398382587904,worriestsv
2110998331296223357,2026-10-16T07:36:37.000Z,0,investasi di era prabowo kocag,2110998331296223357,,,in,,0,0,0,https://x.com/ossjauh/status/2110998331296223357,1500960541421965313,ossjauh
2110998320911130745,2026-10-16T07:36:34.000Z,0,Hp pake segala rusak bangsaaaaaat mau beli pun kudu mikir mikir dulu ah prabowo kontol,2110998320911130745,,,in,,0,0,0,https://x.com/Casualprotest/status/2110998320911130745,1832061990363336704,Casualprotest
2110998285062418516,2026-10-16T07:36:26.000Z,1,"Kebakaran hutan dan lahan (karhutla) menghanguskan rumah Anang Noraini, warga Desa Pematang Baru, Kecamatan Martapura Timur, Kabupaten Banjar, Kalimantan Selatan. Hingga Jumat (16/10/2026), Anang bersama anak dan keponakannya terpaksa tinggal di tenda darurat beratap terpal https://t.co/PdYsZC8QzB",2110998285062418516,https://pbs.twimg.com/amplify_video_thumb/2110992923374575616/img/le6-h5J_vTMxyOF8.jpg,,in,,0,0,0,https://x.com/SINDOnews/status/2110998285062418516,231355136,SINDOnews
2110591246590939555,2026-10-16T07:36:25.000Z,0,"@sehyrui Ntar diaminin, prabowo meninggal wkwk",2110998280738058570,,sehyrui,in,,0,0,0,https://x.com/sqorpius/status/2110998280738058570,757032655380553730,sqorpius
2110997019431194744,2026-10-16T07:36:21.000Z,0,"8/15

Asap tidak mengenal batas administratif. Partikel halus dapat terbawa jauh dari sumber kebakaran.

Dampaknya tidak hanya dirasakan masyarakat yang tinggal dekat area terbakar. Kualitas udara dan kesehatan masyarakat di wilayah lain juga bisa terdampak.

Karhutla adalah",2110998263130407295,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110998263130407295,1382725234445348864,HidsalJ
2110998222906986948,2026-10-16T07:36:11.000Z,0,Info guys kebakaran lagi tapi udah mulai pemadaman ini https://t.co/PcQkOjearK,2110998222906986948,https://pbs.twimg.com/media/HUvFrvsaIAAdUy2.jpg,,in,,0,0,0,https://x.com/KacuiD/status/2110998222906986948,1579267251077025792,KacuiD
2110998208352850188,2026-10-16T07:36:07.000Z,0,"Keterkaitan Malaysia dan Singapura dengan Karhutla di Indonesia terlihat dari dampak kabut asap lintas batas yang dapat mengganggu kesehatan masyarakat, aktivitas ekonomi, dan transportasi. Karena itu, diperlukan kerja sama regional untuk mencegah kebakaran hutan dan lahan. https://t.co/VQ5EDquAFD",2110998208352850188,https://pbs.twimg.com/amplify_video_thumb/2110998097421905920/img/Lw81V3yIQCuFlISk.jpg,,in,,0,0,0,https://x.com/deborahevelyn41/status/2110998208352850188,1830714059777548288,deborahevelyn41
2110998206926688542,2026-10-16T07:36:07.000Z,0,"https://t.co/bfmZe0PJDi

Kepulan asap pekat akibat kebakaran hutan dan lahan (karhutla) yang mengepung kawasan Palaran, Kota Samarinda, Kalimantan Timur merenggut nyawa tak berdosa. https://t.co/IXZ8xwlCuC",2110998206926688542,https://pbs.twimg.com/media/HUvFqzFboAAuC58.jpg,,in,,0,0,0,https://x.com/tribunkaltim/status/2110998206926688542,103551225,tribunkaltim
2110929784469626920,2026-10-16T07:36:07.000Z,0,@LambeSahamjja Rasanya baca berita pak prabowo anxiety bertambah,2110998205911765473,,LambeSahamjja,in,,0,0,0,https://x.com/halloserenity/status/2110998205911765473,1115836030656090114,halloserenity
2110985418011504929,2026-10-16T07:36:07.000Z,0,@RiantDaffa Kecuali kalimantan ya.,2110998205370626274,,RiantDaffa,in,,0,0,0,https://x.com/sntkrnsr/status/2110998205370626274,796796310426787840,sntkrnsr
2110998165340233757,2026-10-16T07:35:57.000Z,0,Bangsat emg gw baru lulus sekolah lg susah nyari kerja yang jabat prabowo jembut jembuttt,2110998165340233757,,,in,,0,0,0,https://x.com/uppuze/status/2110998165340233757,1542111846357794817,uppuze
2110946359037870138,2026-10-16T07:35:56.000Z,2,"@MiskinTV_ Kalimantan jadi negara bagian di bawah invansi/otonomi singapura, ntah diberikan kemerdekaan atau enggak gatau.  

Memicu daerah daerah lainya yang sudsh lama mau memisahkan diri untuk keluar karena indonesia udah gak mampu mengelola (bangkrut)

Indonesia bubar 2030",2110998159715676223,,youngmasterjcw,in,,0,0,0,https://x.com/youngmasterjcw/status/2110998159715676223,1382545107669323777,youngmasterjcw
2110997019431194744,2026-10-16T07:35:50.000Z,0,"7/15

Dampak karhutla tidak berhenti pada lahan yang terbakar.

Grosvenor dkk. dalam Communications Earth &amp; Environment (2024) memperkirakan paparan PM2.5 akibat kebakaran 2019 berkaitan dengan lebih dari 87.000 kematian berlebih di Indonesia.

Ini estimasi berbasis pemodelan,",2110998136634359942,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110998136634359942,1382725234445348864,HidsalJ
2110998125683016027,2026-10-16T07:35:48.000Z,0,Melihat gambar2 &amp; video2 mengenai pasukan penyelamat berusaha dlm mbantu orang utan yg cedera akibat kebakaran hutan di Indonesia sgt menyentuh perasaan. Diwajah mrk tampak sayu &amp; seolah melihat “rumah” mrk dijarah sikap manusia yg kejam.,2110998125683016027,,,in,,0,1,0,https://x.com/akmal_ishak/status/2110998125683016027,289298315,akmal_ishak
2110998123514597451,2026-10-16T07:35:47.000Z,0,"bahkan hewan yang hidup saat pemerintahan prabowo banyak yang jadi korban

kurang ajar, dasar biadab, dasar  pembunuh",2110998123514597451,,,in,,0,0,0,https://x.com/journeywithApr/status/2110998123514597451,2402369514,journeywithApr
2110998088261484910,2026-10-16T07:35:39.000Z,1,"Orangutan betina bernama Ira berhasil diselamatkan dari area lahan terbakar di Kotawaringin Timur, Kalimantan Tengah, pada Rabu (14/10).

Dalam proses evakuasi, Ira sempat tersangkut di pohon setelah dibius, sehingga petugas harus memanjat untuk menurunkannya. Hasil pemeriksaan https://t.co/BhRPsMxP0E",2110998088261484910,https://pbs.twimg.com/amplify_video_thumb/2110997892446273536/img/ikbso3tXY_q9N0-j.jpg,,in,,0,0,0,https://x.com/RadioElshinta/status/2110998088261484910,121640063,RadioElshinta
2110923089920033090,2026-10-16T07:35:37.000Z,0,"@ch_chotimah2 @KPK_RI @prabowo @bang_dasco Mana berani sama Hercules, Nusron",2110998078559768903,,ch_chotimah2,in,,0,0,0,https://x.com/ABudhantar72548/status/2110998078559768903,1863431443726360576,ABudhantar72548
2110908572938952757,2026-10-16T07:35:32.000Z,0,@BelengBeleng687 masa prabowo nggak bisa ngomong baik2. ijab kabulnya kan baik2....,2110998060516139256,,BelengBeleng687,in,,0,0,0,https://x.com/sungpran/status/2110998060516139256,2753286941,sungpran
2110948476179873837,2026-10-16T07:35:30.000Z,0,@olivesugarly @naraeraa @prabowo ini kak dzalim banget :(,2110998050336538926,,olivesugarly,in,,0,0,0,https://x.com/oxyzzuy/status/2110998050336538926,1407625907783696386,oxyzzuy
2110591246590939555,2026-10-16T07:35:27.000Z,0,"@sehyrui Sejak prabowo menjabat, hidup sudah tidak pernah baik baik saja.",2110998040219893932,,sehyrui,in,,0,0,0,https://x.com/duskking96/status/2110998040219893932,1864639134926798848,duskking96
2110998012596290018,2026-10-16T07:35:21.000Z,0,"gila ya prabowo pantesan u nyapres 3 kali kalah mulu anjir, sekalinya dikasih negara nya mau bubar",2110998012596290018,,,in,,0,0,0,https://x.com/baerother/status/2110998012596290018,1509246330,baerother
2110997992018936008,2026-10-16T07:35:16.000Z,0,"Udah melek politik dari era presiden megawati, dari 4 presiden treakhir di negara ini, baru era prabowo dimana seluruh sektor kacau, korupsi, nepotisme dimana mana, mafia ada di setiap bidang, pertama kali ngerasain indonesia kaya gak punya masa depan",2110997992018936008,,,in,,0,0,0,https://x.com/manonhisway/status/2110997992018936008,1173856694008307713,manonhisway
2110724913330012528,2026-10-16T07:35:12.000Z,0,"@ryxul @hi @hollow_sun_club @prabowo YANG BENER KOCAK NAMA LU ITU? 😂 Secinta itu ya lu sama tnr sampai nama lu begitu? Alasan gue ke HSC soalnya mereka lewat tl gue, jadi gue isi aja dah formnya sekalian menguji keberuntungan dalam memikat OA.",2110997976722399687,,ryxul,in,,0,0,0,https://x.com/hyuwnsuk/status/2110997976722399687,1384537299724103682,hyuwnsuk
2110997973585080376,2026-10-16T07:35:12.000Z,0,Lho koq ?!,2110997973585080376,,,in,,0,0,0,https://x.com/JSuryoP1/status/2110997973585080376,1128167650444529666,JSuryoP1
2110990639253082145,2026-10-16T07:35:10.000Z,1,"@scenesgoeshard ""selamat datang di prabowo dua periode"" 🗣",2110997967465509295,,scenesgoeshard,in,,0,0,0,https://x.com/skzophrenia_/status/2110997967465509295,1189548215386787842,skzophrenia_
2110997963602567454,2026-10-16T07:35:09.000Z,0,"Haters nomor 1 Aijing jelas dari Indonesia, you know you know
Kek begitu energynya kenapa gak diarahkan ngebenci prabowo aja sihhh cape dehh",2110997963602567454,,,in,,0,0,0,https://x.com/Vivi_kingdom/status/2110997963602567454,981361196799426560,Vivi_kingdom
2110948210135155035,2026-10-16T07:35:07.000Z,0,@duyduibudui @LambeSahamjja prabowo bener bener stuk otaknya di orde baru,2110997954404425893,,duyduibudui,in,,0,0,0,https://x.com/GogonKelapa/status/2110997954404425893,1324978037935415298,GogonKelapa
2110858355283808418,2026-10-16T07:34:56.000Z,0,@ohmycaramel Bahkan itu size APAR cuma geli geli buat satu rumah 😭 udh gila banget kebakaran hutan ditanganin sama APAR??? Dalam satu ruangan 62 meter aja itu minimal 1 APAR yang 6kg,2110997908581654716,,ohmycaramel,in,,0,0,0,https://x.com/keysenju/status/2110997908581654716,1355872053186809856,keysenju
2110863376046059754,2026-10-16T07:34:55.000Z,0,@unmagnetism nikmati pilihan klean prabowo KNTOL,2110997905276645696,,unmagnetism,in,,0,0,0,https://x.com/Penyintas22/status/2110997905276645696,111226133,Penyintas22
2110997887438200916,2026-10-16T07:34:51.000Z,0,"imagine jokowi udah keliatan se evil apa, masih keliatan better dari prabowo",2110997887438200916,,,in,,0,0,0,https://x.com/88dityara/status/2110997887438200916,811460709510836224,88dityara
2110997876990173501,2026-10-16T07:34:48.000Z,0,Kata aing mah pemerentah udah ditunggangi antek antek asing untuk mengancurkan kalimantan,2110997876990173501,,,in,,0,0,0,https://x.com/Daffamtsn1/status/2110997876990173501,4476037754,Daffamtsn1
2110997854739481054,2026-10-16T07:34:43.000Z,0,"Pesan Keluarga Mulyono
#pesan #keluarga #mulyono @Gerindra @prabowo
https://t.co/4OioZO1PLd",2110997854739481054,,,in,,0,0,0,https://x.com/gulaciamis/status/2110997854739481054,2307033840,gulaciamis
2110997793783660578,2026-10-16T07:34:29.000Z,0,"Selamat ulang tahun, Pak Presiden RI Prabowo Subianto.

Selamat bertambah usia. Semoga kursi kepresidenan ini cukup menjadi bukti bahwa selama ini Anda hanya penasaran dengan kekuasaan. Anda sudah tiga kali mencoba merebut kursi tersebut dan gagal. Tuhan mungkin sudah mencegah https://t.co/yMxFDwvQfT",2110997793783660578,https://pbs.twimg.com/media/HUvFSCeagAEhsdQ.jpg,,in,,0,0,0,https://x.com/Smash1014314/status/2110997793783660578,1838979981948616704,Smash1014314
2110997724548239816,2026-10-16T07:34:12.000Z,0,Dulu sebelum kerja mikirnya gaji atas umr bisa hidup. Pas udah atas umr ternyata susah jg. Ini aku yg boros atau emang ekonomi sekarang yg kayak prabowo?,2110997724548239816,,,in,,0,0,0,https://x.com/rainbowartinya/status/2110997724548239816,1210149111770439680,rainbowartinya
2110997720869773638,2026-10-16T07:34:11.000Z,0,"Kabut asap akibat kebakaran hutan dan lahan bukan hanya  disebakan dari  Indonesia, tetapi juga menjadi masalah lintas negara di Asia Tenggara malasya dan singapura.",2110997720869773638,,,in,,0,0,0,https://x.com/Rifkipu62641451/status/2110997720869773638,1906039917832228864,Rifkipu62641451
2110554306973970602,2026-10-16T07:34:08.000Z,0,"@chyprefloral Udah dipersiapkan jauh2 hari supaya mereka menang, apapun caranya. Dibikin tolol, dibikin miskin, dibikin gak ada pilihan lain. 2014 &amp; 2019 cuma pilihannya cuma jokowi vs prabowo",2110997707255165128,,chyprefloral,in,,0,0,0,https://x.com/RickoSetyabudi/status/2110997707255165128,132023874,RickoSetyabudi
2110997679526609298,2026-10-16T07:34:01.000Z,0,saatnya ke kalimantan pak ❤️,2110997679526609298,,,in,,0,0,0,https://x.com/eajfries/status/2110997679526609298,1441314530282205185,eajfries
2110997019431194744,2026-10-16T07:33:54.000Z,0,"3/15

Kiely dkk. dalam Nature Communications (2021) memperkirakan kerugian ekonomi dari enam peristiwa kebakaran besar di Indonesia pada 2004 sampai 2015 mencapai US$93,9 miliar. Kebakaran 2015 sendiri diperkirakan menimbulkan kerugian sekitar US$28 miliar.

Perlu dicatat, ini",2110997648547463585,,HidsalJ,in,,0,1,0,https://x.com/HidsalJ/status/2110997648547463585,1382725234445348864,HidsalJ
2110997617488642329,2026-10-16T07:33:47.000Z,0,"BREAKING NEWS: Asap karhutla Kalimantan masuk Jakarta, Banten, Jabar

Selengkapnya &gt;&gt;&gt; https://t.co/X4SwBN8vG5

https://t.co/X4SwBN8vG5",2110997617488642329,,,in,,0,0,0,https://x.com/otonomicoid/status/2110997617488642329,753824742491074561,otonomicoid
2110997598467477932,2026-10-16T07:33:42.000Z,0,"Api karhutla di Kalimantan masih belum sepenuhnya padam, tapi Jepang sudah mengakhiri misi bantuan pemadaman.

Pas baca siaran pers dari Jepang, ternyata mereka pulang karena pihak Indonesia menyatakan kebakarannya “bisa ditangani oleh pemerintah Indonesia”. https://t.co/kTWkQZnpyy",2110997598467477932,https://pbs.twimg.com/media/HUvFGRza8AA9ory.jpg,,in,,0,0,0,https://x.com/keluhkesahkonoh/status/2110997598467477932,494927528,keluhkesahkonoh
2110997583397286239,2026-10-16T07:33:38.000Z,0,Karya Nyata Prabowo @prabowo,2110997583397286239,,,in,,0,0,0,https://x.com/YoyokSub0302/status/2110997583397286239,1681216695472656384,YoyokSub0302
2110699290888909248,2026-10-16T07:33:28.000Z,0,"@Kimberley_PS08 hei pantek, kau sama prabowo kau itu mau kita bawa ke hutan yang masih kebakaran itu kah?",2110997539856281633,,Kimberley_PS08,in,,0,0,0,https://x.com/ashenvenus/status/2110997539856281633,1062137177239281664,ashenvenus
2110931537785229498,2026-10-16T07:33:26.000Z,0,@keluhkesahkonoh Pasti pendukung prabowo subiantolol,2110997529869599046,,keluhkesahkonoh,in,,0,0,0,https://x.com/YahyaIbhan/status/2110997529869599046,1264980416110268421,YahyaIbhan
2110986017859617144,2026-10-16T07:33:25.000Z,0,@Hiugundul @Uki23 Gank termul skrg nyerang prabowo ada yg gak beres 😂,2110997526769963274,,Hiugundul,in,,0,0,0,https://x.com/jurigh107/status/2110997526769963274,2044585134897213441,jurigh107
2110997520621146341,2026-10-16T07:33:24.000Z,0,"""bayangkan tiba-tiba datang orang yang kalian benci"" REFLEKS PRABOWO DATENG AJG BENCI",2110997520621146341,,,in,,0,0,0,https://x.com/121draft/status/2110997520621146341,1484577553948246017,121draft
2110997520205967442,2026-10-16T07:33:23.000Z,0,"Keterkaitan Malaysia dan Singapura dengan Karhutla di Indonesia terlihat dari dampak kabut asap lintas batas yang dapat mengganggu kesehatan masyarakat, aktivitas ekonomi, dan transportasi. Karena itu, diperlukan kerja sama regional untuk mencegah kebakaran hutan dan lahan. https://t.co/05cEeO1pW1",2110997520205967442,https://pbs.twimg.com/amplify_video_thumb/2110997245105709056/img/mr7cTVZS6iB--tOy.jpg,,in,,0,0,0,https://x.com/malesmikir33/status/2110997520205967442,2080134318634958848,malesmikir33
2110997511137828963,2026-10-16T07:33:21.000Z,0,"Keterkaitan Malaysia dan Singapura dengan Karhutla di Indonesia terlihat dari dampak kabut asap lintas batas yang dapat mengganggu kesehatan masyarakat, aktivitas ekonomi, dan transportasi. Karena itu, diperlukan kerja sama regional untuk mencegah kebakaran hutan dan lahan. https://t.co/tK7xwmxEIz",2110997511137828963,https://pbs.twimg.com/amplify_video_thumb/2110997212587282432/img/nZ0nC3Fb19ABFPSm.jpg,,in,,0,0,0,https://x.com/itsmedivaxo/status/2110997511137828963,2080134391796252672,itsmedivaxo
429646884152434689,2026-10-16T07:33:20.000Z,0,"@prabowo @Gerindra @Aktivis_Larshen LOE UDAH GILA, SAKIT JIWA, NPD, DEMENSIA, NAJIS, TUA BANGKA, BIJI SATU, DAN IMPOTEN",2110997505483980842,,prabowo,in,,0,0,0,https://x.com/zhoriez/status/2110997505483980842,1641481592421109760,zhoriez
2110997505257410779,2026-10-16T07:33:20.000Z,0,Gue capek banget Ya Alloh…. Gak ada yang bisa menghukum rezim Prabowo Gibran kecuali Engkau dan atas izin-Mu Ya Alloh 😭😭😭😭😭 capeeeekk,2110997505257410779,,,in,,0,0,0,https://x.com/sourirever/status/2110997505257410779,1499411440692006912,sourirever
2110997484189397432,2026-10-16T07:33:15.000Z,0,"jujur ikut seneng banget bangett liat kabar kalo beberapa daerah di kalimantan udah hujan, semoga hujan merata di setiap daerah karhutla aamiinnn",2110997484189397432,,,in,,0,0,0,https://x.com/lutpeyyy/status/2110997484189397432,1079533962765029376,lutpeyyy
2110997474374758531,2026-10-16T07:33:12.000Z,0,stop the wedding yang kmrn milih prabowo cuman karna fomo gemoy dan kasian anjing lah lu semua,2110997474374758531,,,in,,0,0,0,https://x.com/crietis/status/2110997474374758531,1330849192818790402,crietis
2110719284653797524,2026-10-16T07:33:12.000Z,0,@LambeSahamjja tiup tu api-api hutan kalimantan,2110997472965431591,,LambeSahamjja,in,,0,0,0,https://x.com/Rissunflower/status/2110997472965431591,1259682498423873536,Rissunflower
2110966364466983052,2026-10-16T07:33:08.000Z,0,@idextratime untung banget gw gak terjun saham di era prabowo ini,2110997454414020968,,idextratime,in,,0,0,0,https://x.com/yellowzename/status/2110997454414020968,1688002399687106560,yellowzename
2110718608124842222,2026-10-16T07:30:41.000Z,0,@Fraksi_Gerindra @prabowo indonesia cerah ndassmuu https://t.co/jODRiNij6k,2110996838069542988,https://pbs.twimg.com/media/HUvEbs2aIAAv2bA.jpg,Fraksi_Gerindra,in,,0,0,0,https://x.com/coretan_gorong2/status/2110996838069542988,1482411191544971264,coretan_gorong2
2110996828108001515,2026-10-16T07:30:38.000Z,0,saya sangat rela tidak merasakan gerimis di jogja demi melihat langit biru di kalimantan perlahan kembali✊✊✊,2110996828108001515,,,in,,0,0,0,https://x.com/hancockfanboy/status/2110996828108001515,1577612428048637952,hancockfanboy
2110996790044766275,2026-10-16T07:30:29.000Z,5,"Barusan baca artikel di Tempo.

Kebakaran hutan di Kalimantan dan Sumatra harus diatasi segera. Maksimal bulan ini.

Jika bulan depan belum selesai, waduh, Jawa bisa kena.

Tahu ga kenapa? Karena arah angin muson nanti akan mengarah ke Jawa, khususnya Jakarta, mulai bulan depan. https://t.co/8fILXsk7Gq",2110996790044766275,https://pbs.twimg.com/media/HUvECuWaIAAXuNP.png,,in,,0,4,1,https://x.com/abulmuzaffar10/status/2110996790044766275,909850779749466112,abulmuzaffar10
2110995129310069187,2026-10-16T07:30:25.000Z,0,"@dimzsky_ Terima kasih sudah menambahkan perspektifnya. Saya sepakat. Betul, kalau mau ditelusuri lebih jauh, kebakaran hutan sudah lama terjadi sejak ORBA tapi waktu itu belum ada pencatatan modern oleh KLHK/BNPB.

Konteks twit saya sebelumnya adalah perbandingan Jokowi &amp; Prabowo. Jelas",2110996773099708604,,dimzsky_,in,,0,0,0,https://x.com/anakgembala116/status/2110996773099708604,1688920600461574144,anakgembala116
2110933612535357533,2026-10-16T07:30:25.000Z,0,@pyongariy @edzsamudra Kalau kata claude sih jaman jokowi 2015 paling parah baik dalam hal jumlah korban dan nilai kerugian. Tapi jaman prabowo bukan berarti baik ya,2110996772956803086,,pyongariy,in,,0,0,0,https://x.com/johnkennedav2z/status/2110996772956803086,2063809768242962432,johnkennedav2z
2110919591648190665,2026-10-16T07:30:22.000Z,0,@tadanoryandesu @Ndrewstjan @prabowo bukanya surya paloh dan cak imin ya? yang menggaungkan 3 periode,2110996759594033462,,tadanoryandesu,in,,0,0,0,https://x.com/kaleramadhan_/status/2110996759594033462,1407986023716376582,kaleramadhan_
2110996758910112172,2026-10-16T07:30:22.000Z,0,"Presiden Prabowo beri lampu hijau bantuan asing untuk pemadaman karhutla. 

Langkah ini diambil usai asap pekat memicu krisis udara regional hingga meliburkan sekolah di Malaysia. 
https://t.co/5QnG2uT48N",2110996758910112172,,,in,,0,0,0,https://x.com/TRTindonesia/status/2110996758910112172,1793626602623897601,TRTindonesia
2110996695354077254,2026-10-16T07:30:17.000Z,0,Satwa yang di lindungi Jalan sendiri aja udah tau berat lebi dari pada manusia setiap Kebakaran selalu di Pindahin emangnya gue enggak Capek Mindahin banyak satwa langka Hampir pindah itu mereka aja Yang gimmick mulu apa lagi temen Gue sih paling suku dayak emnag enggak dapetduit,2110996736584102311,,BABIHAEKELd4m0,in,,0,1,0,https://x.com/BABIHAEKELd4m0/status/2110996736584102311,2092410765458411520,BABIHAEKELd4m0
2110996718611468459,2026-10-16T07:30:12.000Z,4,"Di tengah kepungan kabut asap yang menyelimuti Kalimantan Tengah, sebuah pesan sederhana dari seorang anak menyentuh hati 🥹 https://t.co/nch9MxwQMK",2110996718611468459,https://pbs.twimg.com/amplify_video_thumb/2110995310109745152/img/vB3xlf7G2wAJhC0J.jpg,,in,,0,0,2,https://x.com/bagindo_kopi/status/2110996718611468459,1091031753924403200,bagindo_kopi
2110996695354077254,2026-10-16T07:30:07.000Z,0,enggak usah di Tag lagi Saam viralin Masalah bahlil aja Ge gue capek setopa tahun ada aja hutan yang kebakaran Dari pubrikan Malaysia 8 % Indonesia 93 % Yang bakar pulau kalimatan Sulawesi dan lain lain mereka minta Empati cuman gimmick aja lah  apek pula aku suruh Orang Utan,2110996695354077254,,,in,,0,1,0,https://x.com/BABIHAEKELd4m0/status/2110996695354077254,2092410765458411520,BABIHAEKELd4m0
2110898685215470040,2026-10-16T07:30:01.000Z,0,"@msaid_didu @ojkindonesia @prabowo Pak, teman bapak omon, kelilingin sama org2 yg ga berkemampuam…. Dikasih data ga diliat….",2110996671295627374,,msaid_didu,in,,0,0,0,https://x.com/bydhln/status/2110996671295627374,1117011459702005760,bydhln
2110996666702815336,2026-10-16T07:30:00.000Z,0,"SBY :
10 tahun = 1 kali trading halt

Jokowi :
10 tahun = 1 kali

Prabowo :
2 tahun = 5 kali
10 tahun = potensi 25 kali trading halt ☠️",2110996666702815336,,,in,,0,0,0,https://x.com/ekky1995/status/2110996666702815336,1259033406333059073,ekky1995
2110996666321092887,2026-10-16T07:30:00.000Z,1,"gue kritik prabowo bukan berarti gue pendukung anies. gue cuma rakyat biasa yang pengen harga kebutuhan murah, gaji naik, dan bisa masuk minimarket tanpa harus mempertimbangkan kondisi geopolitik dompet sendiri 😭",2110996666321092887,,,in,,0,0,0,https://x.com/sihalistebal/status/2110996666321092887,1236493893580943360,sihalistebal
2110996666258239981,2026-10-16T07:30:00.000Z,0,Sing sarehat dulur dulur kalimantan.,2110996666258239981,,,in,,0,0,0,https://x.com/muhammadariel_r/status/2110996666258239981,742564700,muhammadariel_r
2110637905886769546,2026-10-16T07:29:55.000Z,0,@fagaraga777 hidup udah dibikin susah aja masi jadi penyepong prabowo. kntl lah,2110996646981169371,,fagaraga777,in,,0,0,0,https://x.com/yourbabytalk/status/2110996646981169371,2021475575358160906,yourbabytalk
2110996622234820804,2026-10-16T07:29:54.000Z,0,"Meski situasi saat ini sudah berangsur membaik, pihak berwenang tetap mengimbau warga untuk waspada dan menghindari aktivitas yang dapat memicu kebakaran lahan baru.

#TVRI #TVRINasional #MediaPemersatuBangsa #Palangkaraya #Hujan",2110996639792157110,,TVRINasional,in,,0,0,0,https://x.com/TVRINasional/status/2110996639792157110,822554676,TVRINasional
2110900774016540965,2026-10-16T07:29:53.000Z,1,"@jhonsitorus_19 Jokowi pernah di hajar Kebakaran hutan, kini Prabowo di hajar lagi kebakaran hutan,,
Musuh politik begitu Jahat dan masif kerjanya...
Hukum Mati pembuat onar di negara ini biar ada efek ajera,
ini bahaya Laten jika di biarkan bisa hancor mina negara ini
@prabowo",2110996636797415831,,jhonsitorus_19,in,,0,0,0,https://x.com/dos135790/status/2110996636797415831,1660880654358441985,dos135790
2110976372571275598,2026-10-16T07:29:51.000Z,0,@indomerebus @prabowo Lah diotar atur sak karepe dewe..,2110996629159657852,,indomerebus,in,,0,1,0,https://x.com/RonoReneRemen/status/2110996629159657852,257056323,RonoReneRemen
2110996622234820804,2026-10-16T07:29:50.000Z,0,"Kondisi ini disambut baik oleh warga setempat melalui berbagai unggahan di media sosial, setelah sebelumnya wilayah ini terpapar kabut asap akibat Kebakaran Hutan dan Lahan (Karhutla) selama hampir tiga bulan terakhir.",2110996626013929724,,TVRINasional,in,,0,1,0,https://x.com/TVRINasional/status/2110996626013929724,822554676,TVRINasional
2110996622234820804,2026-10-16T07:29:49.000Z,0,"Kualitas udara di Kota Palangka Raya, Kalimantan Tengah, akhirnya menunjukkan perubahan signifikan menjadi lebih bersih pada Jumat pagi (16/10/2026). https://t.co/BRoP6sxOPZ",2110996622234820804,https://pbs.twimg.com/amplify_video_thumb/2110996552793927681/img/pngg3SVRdp-80if0.jpg,,in,,0,1,0,https://x.com/TVRINasional/status/2110996622234820804,822554676,TVRINasional
2110615761324777723,2026-10-16T07:29:43.000Z,0,"@BangPino__ Kita tidak menghina Presiden Prabowo, harus skala prioritas, Jokowi dan Gibran dulu yg harus diselesaikan polemik ijazahnya. Karena ini masalah identitas.",2110996596435640409,,BangPino__,in,,0,0,0,https://x.com/Tomhen2/status/2110996596435640409,1307551656784007168,Tomhen2
2110996584066687483,2026-10-16T07:29:40.000Z,0,"prabowo out 
windah in",2110996584066687483,,,in,,0,0,0,https://x.com/bagasmancing/status/2110996584066687483,1921747340689625088,bagasmancing
2110996545013440894,2026-10-16T07:29:31.000Z,2,DROP 1 UCAPAN UNTUK PRABOWO DI HARI ULANG TAHUNNYA BESOK,2110996545013440894,,,in,,0,2,0,https://x.com/cariaeosa/status/2110996545013440894,1515859957001830401,cariaeosa
2110996488029663461,2026-10-16T07:29:17.000Z,0,prabowo tuh buta dan tuli kah?,2110996488029663461,,,in,,0,0,0,https://x.com/worriestsv/status/2110996488029663461,1996972398382587904,worriestsv
2110996435017801822,2026-10-16T07:29:12.000Z,0,"dan sesuai dengan ketentuan yang berlaku.
Melalui kegiatan ini, Balai Bahasa Provinsi Kalimantan Selatan berkomitmen untuk meningkatkan kualitas pengelolaan arsip yang efektif, efisien, dan akuntabel guna mendukung tertib administrasi serta pelestarian dokumen secara digital.",2110996464780693556,,balaibhskalsel,in,,0,0,0,https://x.com/balaibhskalsel/status/2110996464780693556,700676990722924544,balaibhskalsel
2110996456001966588,2026-10-16T07:29:10.000Z,0,"Gak hutan,gak rupiah,gak ihsg. Semuanya kebakaran. Great job prabowo🔥🔥🔥",2110996456001966588,,,in,,0,0,0,https://x.com/albert454654271/status/2110996456001966588,1595753666577063936,albert454654271
2110996435017801822,2026-10-16T07:29:05.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan rapat penyelesaian digitalisasi arsip tahun 2025 pada Selasa, 13 Oktober 2026. Kegiatan ini bertujuan untuk memastikan penyelesaian proses digitalisasi arsip berjalan dengan baik, tertib, https://t.co/fl8D6Mo2tT",2110996435017801822,https://pbs.twimg.com/media/HUvEDnFbAAAGjKv.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110996435017801822,700676990722924544,balaibhskalsel
2110988904904245492,2026-10-16T07:28:50.000Z,0,"@LambeSahamjja Sudah banyak yg maksi-maki prabowo, kalian gimana? Sudah atau belum? Belum atau sudah? https://t.co/H7sgMHJi2m",2110996372082319585,https://pbs.twimg.com/media/HUvEApCaMAAE1OL.jpg,LambeSahamjja,in,,0,0,0,https://x.com/Prabomon/status/2110996372082319585,1802586755285356544,Prabomon
2110968838275964963,2026-10-16T07:28:49.000Z,0,"@LambeSahamjja jangan mundur, terus siarkan kawan2. Saudara2 kita di kalimantan dan sumatra sedang benar2 butuh suara kita",2110996367455948902,,LambeSahamjja,in,,0,0,0,https://x.com/ParamartaY/status/2110996367455948902,1456193213358768129,ParamartaY
2110966364466983052,2026-10-16T07:28:37.000Z,0,@idextratime 0 udah keluar IHSG semenjak presidennya prabowo,2110996318533689835,,idextratime,in,,0,0,0,https://x.com/swjaya/status/2110996318533689835,513076245,swjaya
2110933612535357533,2026-10-16T07:28:35.000Z,0,"@Gilfffttthhh @edzsamudra Kata2 andalan dia : ""saya dapat laporan""... Masalahnya dr era jokowi semua data yg pihak pemerintah rilis udh kebanyakan di manipulasi, jd data apa bjir yg dimaksud? 🤣😂 Mungkin antekw bawahannya ngefliter jd pg13 Kali yah buat Prabowo? Kan mentalnya labil bngt",2110996312053387395,,Gilfffttthhh,in,,0,0,0,https://x.com/ragildw_t/status/2110996312053387395,1994102693582000128,ragildw_t
2110996310698631352,2026-10-16T07:28:35.000Z,4,"Tetep sy anggap temen, kok. TAPI, tiap hari akan sy bombardir dg fakta2 ketololan prabowo sampai—kalau dia nggak berubah pikiran juga—dia yg nggak mau jadi temen saya.",2110996310698631352,,,in,,0,0,0,https://x.com/_MasWis/status/2110996310698631352,3301333705,_MasWis
2110996293921439844,2026-10-16T07:28:31.000Z,0,Nah gini cara respon yg bener @RajaJuliAntoni @prabowo,2110996293921439844,,,in,,0,0,0,https://x.com/Canopiz/status/2110996293921439844,1433279749774733315,Canopiz
2110996271561630164,2026-10-16T07:28:26.000Z,1,"Update Peringatan Dini Cuaca Wilayah - Kalimantan Barat Tgl. 16 Oktober 2026 pkl. 14:50 WIB
Prakirawan - BMKG - Kalimantan Barat 
https://t.co/CS490ZbCxX https://t.co/0Fn8Dx05RM",2110996271561630164,https://pbs.twimg.com/media/HUvD6wNbgAA7J6I.jpg,,in,,0,0,0,https://x.com/infoBMKG/status/2110996271561630164,108543358,infoBMKG
2110933597213606043,2026-10-16T07:28:23.000Z,0,"@Ndrewstjan Semua kebijakan yang bagus zaman jokowi dirombak total oleh Prabowo, hasilnya ya seperti skrg, arahnya tdak jelas.",2110996258253045919,,Ndrewstjan,in,,0,0,0,https://x.com/jayacand/status/2110996258253045919,1364379045543047169,jayacand
2110915370983027030,2026-10-16T07:28:07.000Z,0,"@gnrlfans @persib Dan beberapa pemegang saham terbesar di Persib jg punya kepentingan CPO di Kalimantan, anu nya Erick Thohir jg salah satu nya. 🫢",2110996194092806343,,tukangtwittter,in,,0,1,0,https://x.com/tukangtwittter/status/2110996194092806343,1244673152166182912,tukangtwittter
2110996184366264751,2026-10-16T07:28:05.000Z,0,"Kabut asap tebal membuat langit Palangkaraya, Kalimantan Tengah, tampak kuning dan oranye. Seperti diberitakan https://t.co/5exe197Vxj pada Jumat (16/10), akibat kabut asap yang tebal ini, maka jarak pandang turun hingga hanya beberapa puluh meter. 

Editor: Adit

#IDNTimesKaltim https://t.co/iqRD0G5k2Z",2110996184366264751,https://pbs.twimg.com/amplify_video_thumb/2110996115512610817/img/mqW6fPbEWO4ja1MV.jpg,,in,,0,0,0,https://x.com/IDNTimesKaltim/status/2110996184366264751,1318854352069554177,IDNTimesKaltim
2110922720829714516,2026-10-16T07:27:57.000Z,1,"@indeksIND Di dalam negeri saja GAK ADA lagi yg PERCAYA kepada NIAT &amp; KEMAMPUAN Rezim Prabowo utk membenahi Indonesia. 
Apalagi Lembaga Rating Internasional seperti MSCI?",2110996152573407331,,indeksIND,in,,0,0,0,https://x.com/meliksuman74092/status/2110996152573407331,2008154113826271232,meliksuman74092
2110996147926130995,2026-10-16T07:27:56.000Z,0,"Beredar narasi di medsos yg menyebutkan bahwa asap kebakaran hutan&amp;lahan (karhutla) dr Kalimantan telah sampai ke ibu kota. Meski demikian, tampilan langit saja belum cukup untuk memastikan asal dari kabut tersebut.  
​#Viral #PolusiUdara #PolusiJakarta #LangitJakarta #Karhutla https://t.co/59QfrD8CLl",2110996147926130995,https://pbs.twimg.com/amplify_video_thumb/2110996100987719680/img/jDWFkZh-bo7uL_y-.jpg,,in,,0,0,0,https://x.com/RahmaTriwi84221/status/2110996147926130995,2047241365688639488,RahmaTriwi84221
2110996142460952873,2026-10-16T07:27:55.000Z,0,"Invasi sih invasi. Tapi jangan grup pecinta prabowo subianto juga asw!!

Skip full intel X buzzer grupnya https://t.co/pYuNBL8N4T",2110996142460952873,https://pbs.twimg.com/media/HUvDy0La4AAuWLL.jpg,,in,,0,1,0,https://x.com/emyr_za1/status/2110996142460952873,1504627720915132416,emyr_za1
2110732178837602642,2026-10-16T07:27:45.000Z,0,"@susipudjiastuti @prabowo Maaf bu, Kebakaran hutan segitu luasnya saja beliau tidak tahu apalagi informasi ini 🙏",2110996100102656219,,susipudjiastuti,in,,0,0,0,https://x.com/yasinal_/status/2110996100102656219,496070325,yasinal_
2110943544315937250,2026-10-16T07:27:43.000Z,0,"@Sebelahkampus ya meskipun gak ada jalur solo seperti definisi karirnya pa prabowo, tapi pecah bintangnya kan waktu jadi wakapolda metro. lalu jadi kapolda Banten atas persetujuan siapa? ya pa prabowo dan presiden Jokowi lah",2110996091739230261,,Sebelahkampus,in,,0,0,0,https://x.com/afannni/status/2110996091739230261,54114263,afannni
2110708729490636804,2026-10-16T07:27:41.000Z,0,@apriedaze Bawa ke Kalimantan biar dia ngerasain kena ISPA bkn malah ank2 bayi/ kecil disana aja yg ngerasain gara2 penanganan di era dia lelet bgt,2110996082427879577,,apriedaze,in,,0,0,0,https://x.com/nanagurlx/status/2110996082427879577,1425714579456225280,nanagurlx
2110946940565537194,2026-10-16T07:27:39.000Z,0,@heykoomi Kakk kmu org kalimantan?,2110996074383167570,,heykoomi,in,,0,1,0,https://x.com/iggemajja/status/2110996074383167570,1504759473667440645,iggemajja
2110995955810254970,2026-10-16T07:27:37.000Z,0,"BPMP Provinsi Kalimantan Selatan, Selasa 13 Oktober 2026.
Kegiatan ini dihadiri oleh kepala dan kepala subbagian umum dari kedua instansi, serta tim ZI-WBK dan PPID BBPKS dan BPMP Provinsi Kalimantan Selatan.",2110996068657930676,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110996068657930676,700676990722924544,balaibhskalsel
2110996034776412302,2026-10-16T07:27:29.000Z,1,Energy nya mending dipake buat menyuarakan kebakaran dan krisis di indonesia aja bang.,2110996034776412302,,,in,,0,0,0,https://x.com/thlss0philes/status/2110996034776412302,1652335890306584576,thlss0philes
2110990639253082145,2026-10-16T07:27:29.000Z,0,@scenesgoeshard prabowo jadi presiden. itu aja serem,2110996033849458834,,scenesgoeshard,in,,0,0,0,https://x.com/KaitoTrivunk/status/2110996033849458834,1736926616859901952,KaitoTrivunk
2110996028317188361,2026-10-16T07:27:28.000Z,3,"saran buat pak prabowo 
untuk kali ini ulang tahun nya di rayakan secara tertutup aja pak + jangan di dokumentasikan 
kondisi lagi begini aslii dahh
kalo sampe di live in gokill sihh anjirrr

ini foto ultah ke 74 
ntar malam beliau usai 75 https://t.co/v5iHQsXfOd",2110996028317188361,https://pbs.twimg.com/media/HUvDZwtaIAA1KGI.jpg,,in,,0,1,0,https://x.com/LambeSahamjja/status/2110996028317188361,1772323119111487490,LambeSahamjja
2110920475388133526,2026-10-16T07:27:23.000Z,0,"@Xliner_beright @pbrgmn @IDX_BEI kan sebelum ngutang bakal di analisis dulu sama tim credit analyst, ya ini yg ngutang si haji yg punya kalimantan assetnya banyak pasti di approve

sebenernya model gini umum, kaya glazer ambil alih united pake model gini, tp masalah UTAMA BYAN di PAKSA jual kl ga gbs jualan",2110996008738189812,,Xliner_beright,in,,0,0,0,https://x.com/zfhorsed/status/2110996008738189812,1780949657323274240,zfhorsed
2110917689661333790,2026-10-16T07:27:23.000Z,0,@damuhsin_ @prabowo Lonte ratau suntik,2110996007584743473,,damuhsin_,in,,0,0,0,https://x.com/attithuts/status/2110996007584743473,868583954,attithuts
2110995994699784653,2026-10-16T07:27:20.000Z,0,Bilang ke prabowo ngentot,2110995994699784653,,,in,,0,0,0,https://x.com/_xxxxcxxxx_/status/2110995994699784653,1908047706511347712,_xxxxcxxxx_
2110915370983027030,2026-10-16T07:27:16.000Z,1,@gnrlfans @persib Persib mah kan masih 1 gerbong sama erick thohir ama kdm masih masuk pemerintahan prabowo jdi wajarlah ga posting,2110995978979578279,,gnrlfans,in,,0,1,0,https://x.com/YEJinny__/status/2110995978979578279,1317043996460380168,YEJinny__
2110995977545109679,2026-10-16T07:27:16.000Z,2,BRAVOO PRABOWO MEMBAWA INDONESIA SETARA DENGAN ZIMBABWE 👏👏,2110995977545109679,,,in,,0,1,0,https://x.com/jenostalker/status/2110995977545109679,1885318915498401796,jenostalker
2110995955810254970,2026-10-16T07:27:10.000Z,0,"Halo, SahabatBahsa!

Balai Bahasa Provinsi Kalimantan Selatan (BBPKS) melaksanakan studi tiru pengelolaan Pejabat Pengelola Informasi dan Dokumentasi (PPID) serta sarana dan prasarana pendukung pembangunan Zona Integritas menuju Wilayah Bebas dari Korupsi (ZI-WBK) di https://t.co/1iZNGA3GyN",2110995955810254970,https://pbs.twimg.com/media/HUvDnWkaEAA1q5-.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110995955810254970,700676990722924544,balaibhskalsel
2110995936914948113,2026-10-16T07:27:06.000Z,0,"Proses evakuasi seekor orangutan betina bernama Ira berlangsung dramatis, saat petugas berhasil menyelamatkannya dari kawasan bekas karhutla di Jalan Cilik Riwut, Kabupaten Kotawaringin Timur, Kalimantan Tengah, pada Rabu (14/10). 

Editor : Imam Rifqi Wicaksono

#IDNTimesKaltim https://t.co/Bs2vUYmRYg",2110995936914948113,https://pbs.twimg.com/amplify_video_thumb/2110995869613076480/img/RmXTLUqitJIyXpwO.jpg,,in,,0,0,0,https://x.com/IDNTimesKaltim/status/2110995936914948113,1318854352069554177,IDNTimesKaltim
2110995934717128814,2026-10-16T07:27:05.000Z,0,"Jare koe ameh ultah @prabowo .
Yo di tiup genine nganti padam kae 🫵",2110995934717128814,,,in,,0,0,0,https://x.com/Tweetofpian/status/2110995934717128814,1195193060688183296,Tweetofpian
2110913992386600989,2026-10-16T07:26:51.000Z,0,"@vizanya12 bismillah semoga saudara-saudara kita yang terdampak kebakaran hutan diberikan keselamatan, tempat berlindung yang aman, dan bantuan yang cukup. semoga para petugas juga selalu dilindungi dan kebakaran segera teratasi. aamiin 🤲🏻",2110995875761664447,,vizanya12,in,,0,0,0,https://x.com/taevelours95/status/2110995875761664447,1775638388672237568,taevelours95
2110995846129205507,2026-10-16T07:26:44.000Z,0,"Sebenarnya baru tadi mlm kesel lagi

Org manual jnt ke ak ongkirnya selalu 15-25 kl udh diskon

Lah giliran jawa ke kalimantan, 30k sama diskonnya, fak kata gw",2110995846129205507,,,in,,0,0,0,https://x.com/Hanasakikirari/status/2110995846129205507,755973333825441793,Hanasakikirari
2110995843105108266,2026-10-16T07:26:44.000Z,0,"sumpah ini jadi dosa besar buat antek antek nya si wowo, bikin kebakaran, banjir, orang orang kena ISPA, dan bikin orang kewalahan gara gara antri BBM 

#IndonesiaButuhOksigen https://t.co/trNgHST6w9",2110995843105108266,https://pbs.twimg.com/amplify_video_thumb/2110720995829178368/img/pRDKm5qOXvOcAagZ.jpg,,in,,0,1,0,https://x.com/sweetzhra/status/2110995843105108266,1573701529185312768,sweetzhra
2110995836033438099,2026-10-16T07:26:42.000Z,0,"UDAH GA ADA ACTION BUAT NANGANI BENCANA KEBAKARAN HUTAN DAN LAHAN, UP DI MEDIA PUN SUARA RAKYAT DIBUNGKAM

SIAPA LAGI KALO BUKAN KELAKUAN PRABOWO ANJING",2110995836033438099,,,in,,0,0,0,https://x.com/syalaamore/status/2110995836033438099,1791493821714604032,syalaamore
2110995828580171892,2026-10-16T07:26:40.000Z,0,"KABUT ASAP MAKIN PEKAT, PENERBANGAN BANDARA MALIKUSSALEH LUMPUH 3 HARI!

Kabut asap akibat kebakaran hutan dan lahan (karhutla) berdampak pada aktivitas penerbangan di Bandara Malikussaleh, Aceh Utara. https://t.co/7rj3skaPRL",2110995828580171892,https://pbs.twimg.com/media/HUvDg36aEAADyYD.jpg,,in,,0,0,0,https://x.com/tribungayo_ofc/status/2110995828580171892,1606555181453565952,tribungayo_ofc
2110995820309078513,2026-10-16T07:26:38.000Z,0,"time ni jgn dulu yang lek lu yang, jerebu yang😭😭 aku kesian dgn kawan aku kat indo maki prabowo bangang tu",2110995820309078513,,,in,,0,0,0,https://x.com/rawrraberry/status/2110995820309078513,1577297861016170496,rawrraberry
2110995795470405981,2026-10-16T07:26:32.000Z,0,Giliran ngebungkam kyk gini aja cepet. ngurusin kebakaran dan korban bencana mesti ngu berbulan-bulan wkwk,2110995795470405981,,,in,,0,0,0,https://x.com/itsvi_laaaa/status/2110995795470405981,1263828020378218498,itsvi_laaaa
2110995724985077802,2026-10-16T07:26:15.000Z,0,coba dia aja yg dilempar kesana ketengah hutan kebakaran,2110995724985077802,,,in,,0,0,0,https://x.com/itravenn/status/2110995724985077802,1905600419562438657,itravenn
2110995687156666461,2026-10-16T07:26:06.000Z,0,prabowo and the hambalang botiboys mana mau liat ginian😭😭😭,2110995687156666461,,,in,,0,0,0,https://x.com/rahmadeux/status/2110995687156666461,39171760,rahmadeux
2110233776500420895,2026-10-16T07:26:03.000Z,0,@indepenSumatera Kalimantan udh biasa bgini,2110995672635757021,,indepenSumatera,in,,0,0,0,https://x.com/Gomupapel/status/2110995672635757021,1477685365339090949,Gomupapel
2110890970200072517,2026-10-16T07:25:58.000Z,0,"@icukprayogi Kalo untuk kalangan elit ga peduli, cuma di grassroot itu perlu dipecah fokusnya. Apalagi suara2 bawah udah mulai ga percaya Prabowo wkwk

Makanya kenapa banyak elit2 yg diajak masuk kabinet, karena untuk mengamankan 2029 full power buat ngelawan Oslo",2110995650490077671,,icukprayogi,in,,0,0,0,https://x.com/piscokgede/status/2110995650490077671,1128315888480899073,piscokgede
2110571116632883465,2026-10-16T07:25:57.000Z,0,@TheCurut007 Hehehe.. ngeles. Setelah 3 bulan akhirnya matane Prabowo melek.,2110995647323128143,,TheCurut007,in,,0,0,0,https://x.com/indah_suwondo/status/2110995647323128143,1638814473476612096,indah_suwondo
2110995641573019738,2026-10-16T07:25:56.000Z,0,That one istri gubernur di Kalimantan,2110995641573019738,,,in,,0,0,0,https://x.com/callmepollo_/status/2110995641573019738,1550875386770120705,callmepollo_
2110981300706501077,2026-10-16T07:25:51.000Z,0,@its__Arthur19 @prabowo Ada kepentingan adiknya disana,2110995623722053641,,its__Arthur19,in,,0,0,0,https://x.com/bagindo_kopi/status/2110995623722053641,1091031753924403200,bagindo_kopi
2110266976090419365,2026-10-16T07:25:51.000Z,0,@rkmndsfilm @prabowo Pemerintah sudah mengerahkan water bombing dan personel. Jangan menutup mata pada upaya yang sudah dilakukan,2110995622719635762,,rkmndsfilm,in,,0,0,0,https://x.com/padriansyah952/status/2110995622719635762,1927094848470855680,padriansyah952
2110995614872035499,2026-10-16T07:25:49.000Z,0,Kebakaran hutan X kebakaran porto 🔥,2110995614872035499,,,in,,0,0,0,https://x.com/Rofiqkurnia/status/2110995614872035499,195214439,Rofiqkurnia
2110995531719954656,2026-10-16T07:25:29.000Z,0,indogsat skrg 7GB/28 hari udah 37-38k coba 🤣🤣 prabowo memek tai kotok bangsat,2110995531719954656,,,in,,0,1,0,https://x.com/25300501s/status/2110995531719954656,1796842705257185280,25300501s
2110919591648190665,2026-10-16T07:25:17.000Z,0,@Ndrewstjan @prabowo (((kondisi terbaik))),2110995478926229531,,Ndrewstjan,in,,0,0,0,https://x.com/azibij/status/2110995478926229531,229334657,azibij
2110995469979812303,2026-10-16T07:25:15.000Z,4,kalo ga kebakaran lahan ya kebakaran pemukiman😭 sumpah takut bgt soalnya disini tuh pemukimannya rapet bgt yg rumah antar rumah tuh nempel😭😭 https://t.co/GW4Q13FkWv,2110995469979812303,https://pbs.twimg.com/media/HUvDMHZbgAAhcQy.jpg,,in,,0,0,0,https://x.com/p8dripepi/status/2110995469979812303,1856901056992874498,p8dripepi
2109906681568379086,2026-10-16T07:25:14.000Z,0,@bacaskskuning coba ditengok juga berapa hektar lahan konsesi milik prabowo yang 'terbakar' di Kalimantan sana.,2110995466536292449,,rolladewarteg,in,,0,0,0,https://x.com/rolladewarteg/status/2110995466536292449,1075930207700144128,rolladewarteg
2110995463906513327,2026-10-16T07:25:13.000Z,0,Dapet sebotol aquiviva ini sih...,2110995463906513327,,,in,,0,1,0,https://x.com/kelixmann/status/2110995463906513327,1425377301953277953,kelixmann
2110995462119641442,2026-10-16T07:25:13.000Z,0,Sumpah yg selalu nyampein berita hoax alias dimanip baik² ttg kondisi indonesia ke prabowo semoga bantal lu selalu panas lebih panas dari kondisi kahutla saat ini,2110995462119641442,,,in,,0,0,0,https://x.com/lafwons/status/2110995462119641442,1108520968081661952,lafwons
2110971568264466450,2026-10-16T07:25:11.000Z,1,"@cfmomski @karinyoo Ya Allah andai aku bisa kirim, aku kirim gratis aja kak ke kalimantan😭",2110995456948146599,,cfmomski,in,,0,0,0,https://x.com/bobbateas/status/2110995456948146599,181133374,bobbateas
2110962379085500847,2026-10-16T07:25:09.000Z,0,@memorosie @kumamoriee @prabowo eh setuju,2110995448551096559,,memorosie,in,,0,0,0,https://x.com/itafushiicanon/status/2110995448551096559,1939186189917159424,itafushiicanon
2110983227062243631,2026-10-16T07:25:05.000Z,0,@clavinjune Prabowo tidak berhenti di asap,2110995429294846059,,clavinjune,in,,0,0,0,https://x.com/hamardikan/status/2110995429294846059,1794672659986530304,hamardikan
2110770933162234039,2026-10-16T07:25:03.000Z,0,@tham878 Si doi lebih heran dgn ijazah jokowi ketimbang kondisi negara ini pasca terpilihnya prabowo,2110995419757240402,,tham878,in,,0,0,0,https://x.com/AlbaSanto_/status/2110995419757240402,1409740738829504515,AlbaSanto_
2110995419526468001,2026-10-16T07:25:03.000Z,0,"Kabut asap akibat kebakaran hutan dan lahan bukan hanya  disebakan dari  Indonesia, tetapi juga menjadi masalah lintas negara di Asia Tenggara malasya dan singapura. https://t.co/nvv8Rt77ad",2110995419526468001,https://pbs.twimg.com/amplify_video_thumb/2110995327482515456/img/2HA0Txw33Fyq_c3B.jpg,,in,,1,0,0,https://x.com/Rifkipu62641451/status/2110995419526468001,1906039917832228864,Rifkipu62641451
2110976232053785014,2026-10-16T07:24:57.000Z,0,"@LambeSahamjja Ga kepala, ga anak buahnya prabowo goblok kabeh. Apa² ko yo nyalaha osang aseng. Dibayar go pajake rakyat ko yo ra ngutek, dol wae uteke pak.",2110995395010850869,,LambeSahamjja,in,,0,0,0,https://x.com/bisayukbisa_/status/2110995395010850869,1588197462816481281,bisayukbisa_
2110654264821387430,2026-10-16T07:24:55.000Z,0,@tempodotco Parah wo @prabowo kaga nyampe 11 masa wo cuma 5,2110995389814039029,,tempodotco,in,,0,0,0,https://x.com/zbeomi/status/2110995389814039029,1016511387734949889,zbeomi
2110995378208399581,2026-10-16T07:24:53.000Z,0,"Kesihatan rakyat perlu menjadi keutamaan. Tindakan pencegahan kebakaran hutan dan tanah gambut wajar diperkukuh bagi mengurangkan risiko pencemaran udara yang boleh menjejaskan kesihatan masyarakat.
https://t.co/9gcz9OdGui",2110995378208399581,,,in,,0,0,0,https://x.com/JadIzzuddin/status/2110995378208399581,1548842035372691456,JadIzzuddin
2110995375574368549,2026-10-16T07:24:52.000Z,0,"Suram bgst porto minus 40%
Kerja yg bener lah @prabowo org luar aja bs liat bobroknya tata kelola negara di SEMUA ASPEK",2110995375574368549,,,in,,0,0,0,https://x.com/MR_XYZOO/status/2110995375574368549,432707526,MR_XYZOO
2110995369257742610,2026-10-16T07:24:51.000Z,0,"Keluarga Besar Balai Bahasa Provinsi Kalimantan Selatan dan Kemendikdasmen mengucapkan selamat dan sukses atas pelantikan Bapak Hidayat Widiyanto, S.S., M.Pd. sebagai Kepala Pusat Pembinaan Bahasa dan Sastra, Badan Pengembangan dan Pembinaan Bahasa. https://t.co/lmZasFHqVR",2110995369257742610,https://pbs.twimg.com/media/HUvDF8JboAA2xso.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110995369257742610,700676990722924544,balaibhskalsel
2110995345970962719,2026-10-16T07:24:45.000Z,1,"Diduga Terpapar Asap Karhutla Bocah 6 Tahun di Kalbar Meninggal Dunia

SEORANG bocah berusia 6 tahun berinisial A, warga Kecamatan Sukadana, Kalimantan Barat, meninggal dunia setelah mengalami ISPA yang diduga akibat Karhutla.

Anak perempuan itu meninggal setelah menjalani https://t.co/yeUIKgGAVe",2110995345970962719,https://pbs.twimg.com/amplify_video_thumb/2110995043163209728/img/3_vfeeV0ryeduWnn.jpg,,in,,0,0,1,https://x.com/mediaindonesia/status/2110995345970962719,68930552,mediaindonesia
2110988637517312076,2026-10-16T07:24:41.000Z,0,@lunaticzt Kabur asap sudah di selatan kalimantan,2110995327935517043,,lunaticzt,in,,0,0,0,https://x.com/Peterlafan/status/2110995327935517043,2613611785,Peterlafan
2110915370983027030,2026-10-16T07:24:22.000Z,0,@gnrlfans @persib CEO Persib punya kepentingan bisnis di Kalimantan si glen ... FYI,2110995248226897972,,gnrlfans,in,,0,1,0,https://x.com/tukangtwittter/status/2110995248226897972,1244673152166182912,tukangtwittter
2110976797093605578,2026-10-16T07:24:12.000Z,0,"@OrizaSativa_1 Gak hutan gak ihsg, KEBAKARAN SEMUAAAA",2110995208976654685,,OrizaSativa_1,in,,0,1,0,https://x.com/LingOrmFaen/status/2110995208976654685,1812701039302512640,LingOrmFaen
2110995196687360374,2026-10-16T07:24:09.000Z,3,"kualitas udara di palembang, jambi, dan sampit (kalimantan tengah) sekarang menempati tiga peringkat teratas dalam daftar kota dengan tingkat pencemaran udara tertinggi di dunia. 

sekali lagi, di dunia. https://t.co/Blcg9LJC9h",2110995196687360374,https://pbs.twimg.com/media/HUvC6lSaIAAuQ4S.jpg,,in,,0,1,1,https://x.com/gfheeez/status/2110995196687360374,1416030028173742085,gfheeez
2110995173794795730,2026-10-16T07:24:04.000Z,0,"Keluarga Besar Balai Bahasa Provinsi Kalimantan Selatan dan Kemendikdasmen mengucapkan selamat dan sukses atas pelantikan Bapak Dony Setiawan, S.S., M.Pd. sebagai Kepala Pusat Pemberdayaan Bahasa dan Sastra, Badan Pengembangan dan Pembinaan Bahasa. https://t.co/TVDHOeBSlA",2110995173794795730,https://pbs.twimg.com/media/HUvC6mZaYAALUxd.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110995173794795730,700676990722924544,balaibhskalsel
2110882452478792081,2026-10-16T07:24:02.000Z,2,"@julpamiaw TAPI YAAA, gue banyak baca pernyataan ""milih prabowo krn gibrannya"" maksud gue ya.... gibran.... krn gibran tuh... 😭",2110995163476906384,,julpamiaw,in,,0,0,0,https://x.com/zbeomi/status/2110995163476906384,1016511387734949889,zbeomi
2110893974357770322,2026-10-16T07:23:59.000Z,1,@AdiSapu19153274 @MafiaWasit CEO Persib punya bisnis di Kalimantan 🫢🫢🫢 si glen,2110995152093499804,,AdiSapu19153274,in,,0,0,0,https://x.com/tukangtwittter/status/2110995152093499804,1244673152166182912,tukangtwittter
138948254804099072,2026-10-16T07:23:54.000Z,0,@prabowo @Gerindra Hidup makin hari makin susah  lihat kelapangan ke pasar-pasar udah banyak yg tutup gara2 sepi,2110995130731962557,,prabowo,in,,0,0,0,https://x.com/ChaniagoJa62786/status/2110995130731962557,1666323305513771011,ChaniagoJa62786
2110995129310069187,2026-10-16T07:23:53.000Z,1,Kebakaran hutan itu warisan lintas kepemimpinan yang dimulai dari masa Orde Baru dan terus berlanjut hingga sekarang. Kita gak pernah memiliki pemimpin yang punya perspektif lingkungan. Hutan selalu dialihfungsikan atas nama pembangunan tanpa pernah dipulihkan ekosistemnya.,2110995129310069187,,,in,,0,1,0,https://x.com/dimzsky_/status/2110995129310069187,1326879014150164483,dimzsky_
2110995104685281453,2026-10-16T07:23:48.000Z,0,"Innalilah wa innailaihi rojiun, mau sampai kapan ini @prabowo?",2110995104685281453,,,in,,0,0,0,https://x.com/aud_zka/status/2110995104685281453,2371502659,aud_zka
2110995059013464238,2026-10-16T07:23:37.000Z,0,"Demi Negara....
Juga utk Kesehatan Mental Warga Negara
Setiap hari disuguhi Keboiongan², Masalah² yg Orgnya itu² aja
.
Reshuffle Kabinet, Rocky Gerung: Prabowo Harus Putus Perjanjian Politik dengan Jokowi | ROSI https://t.co/xFPtqrBkSv",2110995059013464238,,,in,,0,0,0,https://x.com/Na_T1N4/status/2110995059013464238,174453386,Na_T1N4
2110578549057098144,2026-10-16T07:23:24.000Z,0,"@PatubMbel while(prabowo!=waras){Console.WriteLine(""Pemrentah ASU"");}",2110995007012585935,,PatubMbel,in,,0,0,0,https://x.com/bangunnagoro/status/2110995007012585935,206679796,bangunnagoro
2110933612535357533,2026-10-16T07:23:23.000Z,0,"@edzsamudra halah tai kucing dr jaman dulu apalagi jaman sby 2015 paling parah, mau ganti presiden 100 kali tetep aj itu kebakaran hutan tiap tahun, kami di kalimantan udah basi ngisep asep kebakaran hutan udah agenda tahunan pemerintah daerah",2110995002386198827,,edzsamudra,in,,0,0,0,https://x.com/iMadeSlowly/status/2110995002386198827,1229417931651444737,iMadeSlowly
2110994974552854981,2026-10-16T07:23:16.000Z,0,Pak Prabowo besok ulang tahun guys. Kalian mau kasih kado apa ?,2110994974552854981,,,in,,0,0,0,https://x.com/rahmadsaifulhs/status/2110994974552854981,4600958176,rahmadsaifulhs
2110994776560447537,2026-10-16T07:23:15.000Z,0,"Lawangan–Indonesia.
Melalui kegiatan pendampingan ini, diharapkan penyusunan kamus di Balai Bahasa Provinsi Kalimantan Selatan semakin terarah dan berkualitas serta mendukung upaya pendokumentasian dan pelindungan bahasa daerah di Provinsi Kalimantan Selatan.",2110994966621429793,,balaibhskalsel,in,,0,0,0,https://x.com/balaibhskalsel/status/2110994966621429793,700676990722924544,balaibhskalsel
2109906681568379086,2026-10-16T07:23:14.000Z,0,@bacaskskuning yash bagus kalau dulu ikut menyuarakan penentangan ke PT TPL. sekarang? mengundang presiden yang ga ambil tindakan jelas ketika hutan kalimantan terbakar? coba diliat juga itu hubungan ephorus sama adik prabowo yang bilang mau tanam sawit di lahan terbakar. . https://t.co/OP2OneQZZr,2110994965186908310,https://pbs.twimg.com/media/HUvCuv2bEAAmm9i.jpg,bacaskskuning,in,,0,2,0,https://x.com/rolladewarteg/status/2110994965186908310,1075930207700144128,rolladewarteg
2110927199083638890,2026-10-16T07:23:14.000Z,0,@NyaiNeneng @MerahPetrus @PanglimaJilah kenapa tidak bersuara ketika ada kebakaran hutan?,2110994962825490731,,NyaiNeneng,in,,0,0,0,https://x.com/indah_suwondo/status/2110994962825490731,1638814473476612096,indah_suwondo
2110994947801518153,2026-10-16T07:23:10.000Z,1,"Buzzer bilang, “Pak Prabowo itu ahli strategi.”

Strategi apaan, Zer? Coba lihat ini dulu??? 😭 https://t.co/CnCVI0MrOy",2110994947801518153,https://pbs.twimg.com/media/HUvCr2NbMAAPnvW.jpg,,in,,0,0,1,https://x.com/atokdalangs4/status/2110994947801518153,2059977246853705728,atokdalangs4
2110994776560447537,2026-10-16T07:23:10.000Z,0,"Evaluasi Kamus Mini Bergambar Bidang Pertanian dan Perairan Karya Mahasiswa Magang dari Universitas PGRI Kalimantan (UPK).
Pada hari kedua, kegiatan difokuskan pada evaluasi hasil inventarisasi kosakata bahasa Lawangan sebagai bagian dari proses penyusunan Kamus Dwibahasa",2110994946820116987,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110994946820116987,700676990722924544,balaibhskalsel
2110943822649659622,2026-10-16T07:22:57.000Z,0,@fjrwo mantap wo keren bgt prabowo,2110994892080185860,,fjrwo,in,,0,0,0,https://x.com/manhaveataste/status/2110994892080185860,2052789254703689728,manhaveataste
2110732178837602642,2026-10-16T07:22:57.000Z,0,@susipudjiastuti @prabowo Susah bu...serba Omon2..,2110994890800734213,,susipudjiastuti,in,,0,0,0,https://x.com/ABudhantar72548/status/2110994890800734213,1863431443726360576,ABudhantar72548
2110994885579059487,2026-10-16T07:22:55.000Z,0,Gerak Cepat Tim Damkar Lanud SKI Hadapi Informasi Kebakaran https://t.co/oWAJhJGar7,2110994885579059487,https://pbs.twimg.com/media/HUvCmK4a4AABbfS.jpg,,in,,0,0,0,https://x.com/sugirisukani/status/2110994885579059487,1270547290936102913,sugirisukani
2110994882160709783,2026-10-16T07:22:54.000Z,0,siapapun pls culik bunted ke kalimantan biar jd bencana nasional,2110994882160709783,,,in,,0,0,0,https://x.com/miookbarusadar/status/2110994882160709783,1473192384078827520,miookbarusadar
2110994871939211494,2026-10-16T07:22:52.000Z,1,"Tidak akan terjadi perubahan besar jika di pulau jawa tidak merasakan seperti yang terjadi di papua, kalimantan, sumatera &amp; bali.

Jawa adalah Koentji.",2110994871939211494,,,in,,0,0,0,https://x.com/Bgssgb_/status/2110994871939211494,1445747060871872513,Bgssgb_
2110994776560447537,2026-10-16T07:22:50.000Z,0,"Universitas PGRI Kalimantan (UPK), dengan pendampingan dari Tim Kamus dan Istilah Pusat Pengembangan dan Pelindungan Bahasa dan Sastra (Pusbanglin).
Kegiatan ini bertujuan untuk meningkatkan kualitas penyusunan kamus bahasa daerah melalui penguatan pemahaman teknis, evaluasi",2110994861881274379,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110994861881274379,700676990722924544,balaibhskalsel
2110933612535357533,2026-10-16T07:22:43.000Z,0,"@edzsamudra Karena Prabowo, bahkan kita skrg merasa Jokowi dan semua presiden sebelumnya itu baik"" saja
Kecuali mungkin mertuanya",2110994835352256685,,edzsamudra,in,,0,0,0,https://x.com/Hiro28146303/status/2110994835352256685,1445348285934305284,Hiro28146303
2110920304256241801,2026-10-16T07:22:31.000Z,1,"@LambeSahamjja itu kmrn ada utas 'knp ga spik up, krn takut atau gimana' NIH BUKA MATA LO SIALAN!! bg windah yg namanya gede aja kena pressure dr buzzer yg siap nyerang keluarganya, lah kita yg  gada nama?? LENYAP BOSS, negara gendeng",2110994784580243750,,LambeSahamjja,in,,0,0,0,https://x.com/aethernalangel/status/2110994784580243750,2018530933377466368,aethernalangel
2110994783338729936,2026-10-16T07:22:31.000Z,0,eh si wowo gimana sih ini yaAllah. JAHAT BGTT SEMUA NYAA. fak of deh yg kmrn nyoblos prabowo dgn alasan yg gamasuk akal,2110994783338729936,,,in,,0,0,0,https://x.com/astagaangerinya/status/2110994783338729936,1433840174459277313,astagaangerinya
2110994776560447537,2026-10-16T07:22:29.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan kegiatan Pendampingan Penyusunan Kamus pada 13 dan 14 Oktober 2026. Kegiatan ini diikuti oleh Tim Kerja Pengembangan Bahasa dan Sastra Balai Bahasa Provinsi Kalimantan Selatan dan mahasiswa magang dari https://t.co/BKATu1Lb7B",2110994776560447537,https://pbs.twimg.com/media/HUvCieIbMAAxod0.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110994776560447537,700676990722924544,balaibhskalsel
2110900774016540965,2026-10-16T07:22:24.000Z,0,"@jhonsitorus_19 Tanya @KemensetnegRI @setkabgoid dulu Bang @jhonsitorus_19 
apakah gerombolan @psi_id di @kemenhut_ri masih digaji?masih berguna?

Lebih baik gaji gerombolan itu diberi ke relawan atau ke @Puspen_TNI @DivHumas_Polri yang turut serta berjuang

Setuju @prabowo @puanmaharani_ri ? https://t.co/m0uZPNd1uT",2110994753013878882,https://pbs.twimg.com/media/HUvCh53aMAAEmhc.jpg,jhonsitorus_19,in,,0,0,0,https://x.com/horastondi03/status/2110994753013878882,1750817457798082560,horastondi03
2110690311139983870,2026-10-16T07:20:09.000Z,0,"@Kimberley_PS08 Apa itu jokowi, ijazah gak jelas... lihat dong prabowo lengkap dan terbukti hebat. Indonesia per hari ini dlm kondisi terbaik berkat tangan emas prabowo. No debat pokoknya... 🥱",2110994190003818776,,Kimberley_PS08,in,,0,0,0,https://x.com/AlbaSanto_/status/2110994190003818776,1409740738829504515,AlbaSanto_
2110673163814375564,2026-10-16T07:20:01.000Z,0,"@indepenSumatera Puan mirip Mega
AHY mirip SBY
Tomy mirip Soeharto
Yenny mirip Istrinya Gusdur
Ilham mirip Habibie
Didit mirip Prabowo
Gibran mirip siapa pasti beda DNA dengan Jokowi.",2110994153761112151,,indepenSumatera,in,,0,0,0,https://x.com/azfar_tamsil/status/2110994153761112151,1791799188961046528,azfar_tamsil
2110994143317242011,2026-10-16T07:19:58.000Z,0,kok bisa prabowo jadi manusia,2110994143317242011,,,in,,0,0,0,https://x.com/griseunbi/status/2110994143317242011,441816730,griseunbi
2110994131732586816,2026-10-16T07:19:56.000Z,0,WEEEYY KELAKUAN LU LEBIH DARI SETAN! @prabowo https://t.co/blZyVtl4WD,2110994131732586816,https://pbs.twimg.com/media/HUvB-BCaoAEbSoG.jpg,,in,,0,0,2,https://x.com/KanayakanSC/status/2110994131732586816,1857009042515742720,KanayakanSC
2110953377194746018,2026-10-16T07:19:45.000Z,1,"@GusDikaOfficial Iya gpp, kasihan gajah Otan dan hewan2 lainnya. Mau ikut malay or Singapore gpp deh, yg penting seluruh penghuni kalimantan sehat bahagia. 
Lagu bisa diubah, sejarah bisa d ubah. Tapi sakit kalian yg rasa,,,",2110994087935639963,,GusDikaOfficial,in,,0,0,0,https://x.com/ItsMeEka131/status/2110994087935639963,1420626267791974403,ItsMeEka131
2110994060957859858,2026-10-16T07:19:39.000Z,0,"Balai Wilayah Sungai (BWS) Kalimantan II melalui Tim UPI Dadahup melaksanakan penanganan kekeringan lahan.
Penanganan dilakukan melalui pemompaan air dari saluran sekunder menggunakan 1 unit mobil pompa berkapasitas 250 liter/detik untuk mengairi lahan seluas kurang lebih 1 ha. https://t.co/RgZF3FWOZF",2110994060957859858,https://pbs.twimg.com/media/HUvBxUqbkAA_xoe.jpg,,in,,0,0,0,https://x.com/pu_sda_kal2/status/2110994060957859858,1631615281859821568,pu_sda_kal2
2110994060429172984,2026-10-16T07:19:39.000Z,0,Padahal kemaren sama malam hujan deras sampai berpetir tapi hari ini asapnya masih tebal banget 😞 apalagi yang di Kalimantan ya,2110994060429172984,,,in,,0,1,0,https://x.com/maysochist/status/2110994060429172984,1046451443685687297,maysochist
2110964536862024084,2026-10-16T07:19:38.000Z,1,"@splittheatoom Tapi gosip di kalangan plantation mereka kaya cacing kepanasan di jaman Prabowo, karena beredar kabar bahwa Sinarmas melepas saham mereka di awal 2026 ke group yang terafiliasi dengan mereka. 

Ini kan membuat pembuktian makin sulit karena menambah jumlah nominee",2110994059724788215,,splittheatoom,in,,0,1,0,https://x.com/Big83717Dude/status/2110994059724788215,2029516685393510400,Big83717Dude
2110994050551890136,2026-10-16T07:19:36.000Z,0,"Orang orang tolol itu bukannya bikin program atau kebijakan yang baik di saat carut marutnya keadaan indonesia, ehh tiap kementrian sibuk buat video seolah di bawah kepemimpunan prabowo indonesia membaik,",2110994050551890136,,,in,,0,0,0,https://x.com/Gunadi____/status/2110994050551890136,1102195438940119040,Gunadi____
2110994044172321237,2026-10-16T07:19:35.000Z,0,Prabowo Mati aja,2110994044172321237,,,in,,0,0,0,https://x.com/CRASHBR41N/status/2110994044172321237,1277473771981430785,CRASHBR41N
2110994011318350240,2026-10-16T07:19:27.000Z,0,"kebakaran dimana"", literally dimana""..
sampe ihsg jg kebakaran, menyalaaa 🔥",2110994011318350240,,,in,,0,0,0,https://x.com/onlypho/status/2110994011318350240,62698233,onlypho
2110227310804918544,2026-10-16T07:19:21.000Z,0,"@karepmudeweeee @Kejeffreyan memang kak, di tiktok banyak koo yang naturally dongoo makanya aku herann, klo buzzer kan dibayar yaa, nah mereka sukarela bangga gitu membela prabowo😭",2110993985057784122,,karepmudeweeee,in,,0,0,0,https://x.com/thisfaa/status/2110993985057784122,1420307524520013827,thisfaa
2110993953571164298,2026-10-16T07:19:13.000Z,0,Yakin kamu mau diam saja jendral @prabowo ? Manusia rendahan ini yang nyata2 bawahanmu. Secara terang benderang telah menghinamu. Jiwa korsa ku menjerit pak presiden. Kasih aku AMANAT itu. Niscaya matahari besok adalah sesuatu yang sangat mahal bagi manusia ga tau diri ini.,2110993953571164298,,,in,,0,0,0,https://x.com/SangReal99/status/2110993953571164298,2037215824042483716,SangReal99
2110967930511053124,2026-10-16T07:19:12.000Z,0,@kucinghilang_ @prabowo mASIH KAAAK… lusa balik ke sanaa🫩🥀,2110993950391844977,,kucinghilang_,in,,0,0,0,https://x.com/nikiateh/status/2110993950391844977,1769051604429447168,nikiateh
2110993924999516633,2026-10-16T07:19:06.000Z,0,"IHSG drop
Karhutla Kalimantan dan Sumatra udah berbulan bulan
Batam blackout
Bali antrian BBM panjang
Kritik pemerintah langsung diserang buzzer
Wapres Gibran

Kuat kuat dah WNI !!",2110993924999516633,,,in,,0,0,0,https://x.com/achmadyusuft/status/2110993924999516633,730603485134127104,achmadyusuft
2110923358158340441,2026-10-16T07:19:02.000Z,0,@cellaurent negara prabowo dan teddy,2110993907949711566,,cellaurent,in,,0,0,0,https://x.com/yourbabytalk/status/2110993907949711566,2021475575358160906,yourbabytalk
2110993877431971890,2026-10-16T07:18:55.000Z,0,"vacation ke belitung bukannya hepi2 malah radicalized jir. ngeliat tambang dimana2, kekeringan, orang ngantri BBM sampe mobil ditinggal di pom bensin, lewatin lahan kebakar juga. asap dari kalimantan juga sampe ke sini walaupun gak gitu parah. memang pemerintah bajingan semua",2110993877431971890,,,in,,0,1,0,https://x.com/yuanst/status/2110993877431971890,47901092,yuanst
2110981300706501077,2026-10-16T07:18:53.000Z,0,@its__Arthur19 @prabowo Fokus MBG wehh,2110993870179717224,,its__Arthur19,in,,0,0,0,https://x.com/Mia_Kyushu/status/2110993870179717224,1345197460474318848,Mia_Kyushu
2110714601914466461,2026-10-16T07:18:50.000Z,0,@nocontextwindah windah ampe marah2 jir sumpah gapernah gw liat dia longtext kyk gitu di storynya emg rezim anjing prabowo anjing kontol dajjal,2110993855093018633,,nocontextwindah,in,,0,0,0,https://x.com/joszjis/status/2110993855093018633,1879358862790451200,joszjis
2109906681568379086,2026-10-16T07:18:46.000Z,0,@bacaskskuning press release terkait bencana lingkungan di Kalimantan sudah ada? bencananya sudah 3 bulan tapi sampai saat ini HKBP Pusat blm ada statement apa apa. Apa karena kejadiannya di Kalimantan bukan di Sumatera?,2110993841407009021,,bacaskskuning,in,,0,0,0,https://x.com/rolladewarteg/status/2110993841407009021,1075930207700144128,rolladewarteg
2110993835631489163,2026-10-16T07:18:45.000Z,0,gue adalah 1/283.270 orang itu 🥲 fuck you @prabowo,2110993835631489163,,,in,,0,0,0,https://x.com/rifaille/status/2110993835631489163,1871507789744676864,rifaille
2110993813162672175,2026-10-16T07:18:40.000Z,55,"❗️Update Bantuan Karhutla❗️

Saat ini kami sedang mempersiapkan Rumah Aman Asap ke-3 di Kalimantan

semoga semuanya dilancarkan dan bisa membantu warga yang terdampak kabut asap. 

doain yaa guys! 🤲",2110993813162672175,,,in,,0,0,24,https://x.com/humaniesproject/status/2110993813162672175,2086017777618628608,humaniesproject
2110993802022236358,2026-10-16T07:18:37.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan Rapat Evaluasi Pelaksanaan Program dan Anggaran Triwulan III Tahun 2026 pada 15 Oktober 2026 yang diikuti oleh seluruh pegawai. https://t.co/5vXbQNMTVn",2110993802022236358,https://pbs.twimg.com/media/HUvBp_IbsAI9_Bw.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110993802022236358,700676990722924544,balaibhskalsel
2110933612535357533,2026-10-16T07:18:36.000Z,0,"@edzsamudra jaditau kenapa pemerintah ABAI sama kebakaran lahan. yakni
1. Pemerintah cekak dana APBN maupun Cadanganya
2. Pemerintah malu buat minta bantuan ASEAN 
3. Pemerintah beraharap sudah mulai masuk musim penghujan.",2110993798214168864,,edzsamudra,in,,0,0,0,https://x.com/DhasamukaLokal/status/2110993798214168864,1150204117521850369,DhasamukaLokal
2110958714173984873,2026-10-16T07:18:30.000Z,0,"@unmagnetism awas kalo omon doang lu un, ntr kyk prabowo🙂‍↔️",2110993773933306354,,unmagnetism,in,,0,0,0,https://x.com/fnyraaaaaaa/status/2110993773933306354,1415179527240572934,fnyraaaaaaa
2110938133785370800,2026-10-16T07:18:28.000Z,0,"@AzzamIzzulhaq Apasih lebay amat jadi netizen dan sok paling ahli padami api, kalau memang  ahli atau mau cepat tuntas kebakaran hutan nih, langsung turun ke lapangan dan ikut padami tuh kebakaran, jangan asal bacot doank di mendsos, buktikan langsung... anak SD pun bisa cuma bacot doank.",2110993762755436814,,AzzamIzzulhaq,in,,0,0,0,https://x.com/lolegema/status/2110993762755436814,1908004508879433729,lolegema
2110993758678569309,2026-10-16T07:18:27.000Z,0,"Adili ibu dewi astutik !! Gembong Narkoba Republik Indonesia yang ditangkap waktu itu, jangan sampai rezim Jendral Haji Prabowo dan Haji Gibran di cap pelanggar HAM berat menangkap seseorang tapi tidak di adili sampai sekarang. kalau Kapolri tidak mampu mundur saja !!",2110993758678569309,,,in,,0,0,0,https://x.com/Partikellirs/status/2110993758678569309,1594732397492195330,Partikellirs
2110993758477316179,2026-10-16T07:18:27.000Z,0,ni orang ga cocok kalau dikatain rot in hell.. semoga rumahnya kebakaran dan dia ga bisa keluar,2110993758477316179,,,in,,0,0,0,https://x.com/rumpangan/status/2110993758477316179,950177501816352768,rumpangan
2110993756862488785,2026-10-16T07:18:26.000Z,1,"Kebakaran hutan udah jadi berita di mana-mana, rakyat pun udah teriak ke mana-mana. Pemerintah masih aja tutup mata melihat rakyat sengsara. Tutup telinga mendengar suara rakyat. Tutup mulut saat diminta bertanggung jawab. Lengkap udah ketidakpeduliannya. 

Tutup usia, kapan?",2110993756862488785,,,in,,0,0,0,https://x.com/olinlei/status/2110993756862488785,1785655415776407553,olinlei
2110979454310953367,2026-10-16T07:18:23.000Z,0,@pilarkeamanan Apresiasi buat personel yg sigap di tengah situasi kebakaran,2110993743465857158,,pilarkeamanan,in,,0,0,0,https://x.com/SuryanaWis83893/status/2110993743465857158,1701075217999962112,SuryanaWis83893
2110993743356756465,2026-10-16T07:18:23.000Z,0,keren banget prabowo,2110993743356756465,,,in,,0,0,0,https://x.com/TanInsideAhim/status/2110993743356756465,1264831959915622401,TanInsideAhim
2110869016550187027,2026-10-16T07:18:21.000Z,0,"@goPuudd jaditau kenapa pemerintah ABAI sama kebakaran lahan. yakni
1. Pemerintah cekak dana APBN maupun Cadanganya
2. Pemerintah malu buat minta bantuan ASEAN 
3. Pemerintah beraharap sudah mulai masuk musim penghujan.",2110993733730947229,,goPuudd,in,,0,0,0,https://x.com/DhasamukaLokal/status/2110993733730947229,1150204117521850369,DhasamukaLokal
2110979379572728090,2026-10-16T07:18:20.000Z,0,@pilarkeamanan Nah gini dong kepolisian tegas usut akar masalah kebakaran hutan kita,2110993731071693017,,pilarkeamanan,in,,0,0,0,https://x.com/QaylaAnindia/status/2110993731071693017,1319179947026518016,QaylaAnindia
2110979244893564946,2026-10-16T07:18:18.000Z,0,"@pilarkeamanan Biar fakta yang bicara, penyebab kebakaran harus dipastikan lewat penyelidikan",2110993724310520208,,pilarkeamanan,in,,0,0,0,https://x.com/feriantoarii/status/2110993724310520208,1699266519329566720,feriantoarii
2110993723450626364,2026-10-16T07:18:18.000Z,0,"Status bencana nasional bukan satu-satunya penentu kecepatan bantuan. Meski belum berstatus nasional, penanganan karhutla Kalimantan tetap melibatkan personel gabungan, pemadaman darat, hingga operasi udara. 
#KawalPenangananKarhutla #PemerintahBergerak https://t.co/EaLh44wzyQ",2110993723450626364,https://pbs.twimg.com/amplify_video_thumb/2110993692312182784/img/cQ5OVagjzoK02gFZ.jpg,,in,,0,0,0,https://x.com/sy_nch/status/2110993723450626364,1338128640597401600,sy_nch
2110993405606306154,2026-10-16T07:18:17.000Z,3,"peluang bantuan dari Malaysia dan negara tetangga.
10. Polisi sudah menetapkan ratusan tersangka terkait pembakaran lahan.
Kesimpulan singkat: 
Polusi CO dari kebakaran Indonesia masih aktif dan menyebar regional. Situasi masih kritis, meski upaya pemadaman ditingkatkan.",2110993717951893870,,Rahadi0816,in,,0,0,3,https://x.com/Rahadi0816/status/2110993717951893870,1611567480992043008,Rahadi0816
2110993714965619169,2026-10-16T07:18:16.000Z,0,not a single recent post about kalimantan @NarasiNewsroom @NajwaShihab ayo setajam covid dulu kritik nya https://t.co/ek2XXJEX5m,2110993714965619169,https://pbs.twimg.com/media/HUvBlwdbcAAmXJw.jpg,,in,,0,0,0,https://x.com/agusartaaa1/status/2110993714965619169,1432300358856962049,agusartaaa1
2110939022382309503,2026-10-16T07:18:13.000Z,0,"@JonghoJoestarr Inilah bodohnya kamu, saya hanya membandingkan Anies dan Prabowo, hanya karena kamu tidak puas, langsung menyimpulkan saya pendukung Prabowo. 

Pesan saya, jangan merendahkan rakyat karena kamu sendiri ternyata bukan orang berwawasan luas, tapi kok bisa menuduh close minded",2110993702340751680,,JonghoJoestarr,in,,0,0,0,https://x.com/frmsrgr/status/2110993702340751680,1638681500,frmsrgr
2110993678605197602,2026-10-16T07:18:13.000Z,0,"Intinya apa, disini sekali lagi pemerintahan prabowo-gibran gagal dalam penanggulangan bencana, buktinya adalah tidak dipenuhinya ketentuan2 pada undang2 tersebut
memang negara kita negara rawan bencana, tapi masyarakat berhak merasa aman apabila ada mitigasi dari pemerintah",2110993701124313268,,auliaakbaroi,in,,0,1,0,https://x.com/auliaakbaroi/status/2110993701124313268,1753052079277723648,auliaakbaroi
2110934681915122083,2026-10-16T07:18:04.000Z,1,@indepenSumatera Semua kon di kaitkan sama jokowi padahal prabowo sendiri yang tolol dan gak bisa jadi presiden,2110993665535656445,,indepenSumatera,in,,0,0,0,https://x.com/alumni_monas/status/2110993665535656445,1456372701459726337,alumni_monas
2110919591648190665,2026-10-16T07:18:02.000Z,0,@bukan4non @Ndrewstjan @prabowo Buzzer koplak tuh Don dasco udah bilang 5 kali Wowo ke solo minta Gibran jadi wakilnya,2110993653653237887,,bukan4non,in,,0,0,0,https://x.com/darmawan_paisal/status/2110993653653237887,1604359810199171075,darmawan_paisal
2110993653091139949,2026-10-16T07:18:01.000Z,0,"dia ini kayak kenalan ku juga, yang selalu bilang “kenapa sih apa apa nyalahin prabowo” dan heran nya adalah diaaa ituu lulusan s1 hukummmm???? kokk otak nya gak dipake mikirr yaa😭💔",2110993653091139949,,,in,,0,0,0,https://x.com/thisfaa/status/2110993653091139949,1420307524520013827,thisfaa
2110993652495638920,2026-10-16T07:18:01.000Z,13,"kabinet bengkak, wantimpres seabrek, tapi ngasih statement kalo kebakaran di kalimantan krn ring of fire. AWOWKWK PEKOKKKK. ring of fire itu kawasan dgn aktivitas tektonik dan vulkanik. kalimantan bukan wilayah jalur vulkanik aktif. jgn terlalu dihubung2kan. mentang2 ada firenya.",2110993652495638920,,,in,,0,0,2,https://x.com/thenggara/status/2110993652495638920,2016709097119477760,thenggara
2110993405606306154,2026-10-16T07:17:52.000Z,3,"gambut yang sulit dipadamkan.
4. Luas lahan terbakar: perkiraan independen hampir 900.000 hektar.
5. Emisi kebakaran Indonesia menjadi yang tertinggi di dunia dalam sebulan terakhir.
6. Kasus gangguan pernapasan di 7 provinsi Indonesia melebihi 283.000.
Polusi udara di Kalimantan",2110993615334093034,,Rahadi0816,in,,0,0,3,https://x.com/Rahadi0816/status/2110993615334093034,1611567480992043008,Rahadi0816
2110993610221183252,2026-10-16T07:17:51.000Z,0,"ya Allah ga tega bgt liat bapaknya keinget bapak gw sendiri, ga pake masker pg si bapak ya Allah, yg kuat yaa pak dan semua masyarakat Kalimantan😢😭",2110993610221183252,,,in,,0,0,0,https://x.com/stfugthlol/status/2110993610221183252,2016454414933123072,stfugthlol
2110993603871076819,2026-10-16T07:17:50.000Z,0,"onee-san, kalo Indonesia isinya bukan orang bodoh sudah pasti presidennya bukan Prabowo",2110993603871076819,,,in,,0,0,0,https://x.com/vertiogo/status/2110993603871076819,1248589001591623682,vertiogo
2110616071845912662,2026-10-16T07:17:49.000Z,0,@hanIogys Semoga asapnya cepat mereda. Semoga Pemerintah Pusat dan Daerah cepat tobat dan langsung sigap menangani kebakaran dan asapnya. #IndonesiaButuhOksigen,2110993600624415179,,hanIogys,in,,0,0,0,https://x.com/azizan_mars/status/2110993600624415179,1725674047,azizan_mars
2110993595595661536,2026-10-16T07:17:48.000Z,0,"Kepala Kantor Pertanahan Kota Samarinda, Ceto Subagiyo, beserta jajaran menghadiri pelantikan Majelis Pembina dan Pengawas Pejabat Pembuat Akta Tanah (PPAT) Wilayah dan Daerah Provinsi Kalimantan Timur Tahun 2026 yang diselenggarakan oleh Kanwil BPN Provinsi Kaltim https://t.co/50TaqaEmXv",2110993595595661536,https://pbs.twimg.com/media/HUvBe95boAAToG2.jpg,,in,,0,0,0,https://x.com/kantahkotasmd/status/2110993595595661536,974164577372876800,kantahkotasmd
2110993581964153320,2026-10-16T07:17:44.000Z,0,"Keluarga Besar Tentara Nasional Indonesia Angkatan Darat Mengucapkan Selamat &amp; Sukses kepada Jenderal TNI Tandyo Budi R, atas Amanah Jabatan Baru Sebagai Kepala Staf TNI Angkatan Darat https://t.co/C6UwJr1ISh",2110993581964153320,https://pbs.twimg.com/media/HUvBd_rbkAARIM1.jpg,,in,,0,0,0,https://x.com/Jokowi_RI/status/2110993581964153320,1369851902,Jokowi_RI
2110993405606306154,2026-10-16T07:17:32.000Z,3,"konsentrasi CO ekstrem (warna merah gelap) di atas Sumatra, Kalimantan, dan sekitarnya.
3. Musim kebakaran terburuk dalam lebih dari 10 tahun, diperparah El Niño sangat kuat (kekeringan ekstrem).
Faktor utama: pembakaran lahan (slash-and-burn) untuk sawit &amp; pertanian + kebakaran",2110993529405391290,,Rahadi0816,in,,0,0,3,https://x.com/Rahadi0816/status/2110993529405391290,1611567480992043008,Rahadi0816
2110993521285190097,2026-10-16T07:17:30.000Z,0,"Laporan Khusus Dua Tahun Prabowo–Gibran: Booming Bisnis Data Center di Indonesia, Apa yang Harus Dilakukan Pemerintah? https://t.co/liFx5ZJ3IZ @indoict",2110993521285190097,,,in,,0,0,0,https://x.com/indoict/status/2110993521285190097,957482702,indoict
2110993512493957442,2026-10-16T07:17:28.000Z,0,Demi dah… prabowo cwpet lengser ya alloh gak kuaaat,2110993512493957442,,,in,,0,0,0,https://x.com/sourirever/status/2110993512493957442,1499411440692006912,sourirever
2110993457787642012,2026-10-16T07:17:15.000Z,2,"Personel Satbrimob Polda Maluku Utara bersama Polsek Jailolo Selatan bergerak cepat memadamkan kebakaran hutan dan lahan (karhutla) di Desa Domato, Kecamatan Jailolo Selatan, Kabupaten Halmahera Barat. Personel gabungan melakukan upaya pemadaman untuk mencegah api meluas dan https://t.co/CznHpCauXB",2110993457787642012,https://pbs.twimg.com/media/HUvBWchasAATLox.jpg,,in,,0,0,0,https://x.com/DivHumas_Polri/status/2110993457787642012,138290629,DivHumas_Polri
2110990946074574852,2026-10-16T07:17:14.000Z,0,@yourdebluesion Kebakaran Hutan dan Lahan,2110993454239207497,,yourdebluesion,in,,0,0,0,https://x.com/gocanz89/status/2110993454239207497,2105970967713570816,gocanz89
2110993446219715021,2026-10-16T07:17:12.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan kegiatan koordinasi dengan mitra kerja terkait pembayaran pajak melalui aplikasi Qlola di Kantor Wilayah Direktorat Jenderal Pajak (DJP) Kalimantan Selatan dan Tengah, Jalan Lambung Mangkurat Nomor 21, https://t.co/Wy8Liv5Sbp",2110993446219715021,https://pbs.twimg.com/media/HUvBVtmbgAA0-5G.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110993446219715021,700676990722924544,balaibhskalsel
2110993415718781416,2026-10-16T07:17:08.000Z,0,"Dukungan dari Bapak menjadi penyemangat bagi seluruh jajaran Karantina Kalimantan Barat untuk terus menjaga kedaulatan negara, melindungi kelestarian sumber daya alam hayati, serta memperkuat ketahanan ekonomi 🇮🇩.",2110993427567636901,,karantinakalbar,in,,0,1,0,https://x.com/karantinakalbar/status/2110993427567636901,828524256996646912,karantinakalbar
2110993415718781416,2026-10-16T07:17:07.000Z,0,"Dukungan dari Bapak menjadi penyemangat bagi seluruh jajaran Karantina Kalimantan Barat untuk terus menjaga kedaulatan negara, melindungi kelestarian sumber daya alam hayati, serta memperkuat ketahanan ekonomi 🇮🇩.",2110993423151022457,,karantinakalbar,in,,0,1,0,https://x.com/karantinakalbar/status/2110993423151022457,828524256996646912,karantinakalbar
2110993415718781416,2026-10-16T07:17:06.000Z,0,"beserta seluruh jajaran atas ucapan, dukungan, dan sinergi yang diberikan dalam rangka Hari Karantina Indonesia yang ke-149 serta ulang tahun Badan Karantina Indonesia yang ke-3. 🎉",2110993419481100717,,karantinakalbar,in,,0,1,0,https://x.com/karantinakalbar/status/2110993419481100717,828524256996646912,karantinakalbar
2110993415718781416,2026-10-16T07:17:05.000Z,0,"Terima kasih dan apresiasi kami sampaikan kepada Kepala Kantor Imigrasi Kelas I TPI Singkawang, Dadang Munandar,

Semoga sinergi serta kolaborasi antara Karantina dan Imigrasi semakin kuat demi menjaga kedaulatan negara ✨ https://t.co/GouKaXm4K8",2110993415718781416,https://pbs.twimg.com/amplify_video_thumb/2110993363784867840/img/x7K0FtN_icUUSfxi.jpg,,in,,0,1,0,https://x.com/karantinakalbar/status/2110993415718781416,828524256996646912,karantinakalbar
2110953377194746018,2026-10-16T07:17:04.000Z,0,"@GusDikaOfficial engga lah,  paling bener emang ganti semua pemerintahnya palagi presiden (wajib ganti)",2110993410903670816,,GusDikaOfficial,in,,0,0,0,https://x.com/aethernalangel/status/2110993410903670816,2018530933377466368,aethernalangel
2110993410882449903,2026-10-16T07:17:04.000Z,0,"cuma mau bilang,

terima kasih banyak, Vicky Prasetyo —sudah mau bersuara untuk kebakaran hutan di Indonesia.

say it louder, my bro.✊🏼

🙏🏼🤍 https://t.co/KRINgVomRE",2110993410882449903,https://pbs.twimg.com/amplify_video_thumb/2110993291948990464/img/M2AH7MTHRDCN17bw.jpg,,in,,0,0,0,https://x.com/xClaudyastev/status/2110993410882449903,2104546537401708544,xClaudyastev
2110993405606306154,2026-10-16T07:17:02.000Z,3,"Ringkasan Situasi Kebakaran Hutan Indonesia &amp; Polusi CO (per 16 Oktober 2026)
1. Data satelit NASA menunjukkan polusi karbon monoksida (CO) yang sangat tinggi dari kebakaran hutan/lahan intens di Indonesia.
2. Polusi menyebar luas ke Malaysia dan Singapore.
Peta menunjukkan.. https://t.co/aGwjaQ5daL",2110993405606306154,https://pbs.twimg.com/amplify_video_thumb/2110993369233334273/img/id73yBvx4x-pIHBr.jpg,,in,,0,4,3,https://x.com/Rahadi0816/status/2110993405606306154,1611567480992043008,Rahadi0816
2110993403005849628,2026-10-16T07:17:02.000Z,0,IHSG dibekukan guys! Apakah ekonomi  baik2 saja pak @prabowo ?,2110993403005849628,,,in,,0,0,0,https://x.com/falihazmi/status/2110993403005849628,75992221,falihazmi
138948254804099072,2026-10-16T07:16:53.000Z,0,@prabowo @Gerindra ALAHHHH TAIK,2110993366372782276,,prabowo,in,,0,0,0,https://x.com/markkganteng/status/2110993366372782276,1243142081008156672,markkganteng
2110738555723255947,2026-10-16T07:16:49.000Z,0,@sosmedkeras Dikasih fasilitas buat judol dan ngeslot dari presiden @prabowo 👏👏,2110993349104848936,,sosmedkeras,in,,0,0,0,https://x.com/jin_pae/status/2110993349104848936,1228755411718639616,jin_pae
2110993346948907283,2026-10-16T07:16:48.000Z,0,"Presiden Prabowo Subianto melantik tujuh pejabat negara sekaligus di Istana Negara, Kamis (15/10/2026), dalam perombakan jajaran pemerintahan.

Salah satu posisi yang berganti adalah Kepala BNPB. Letjen TNI Kristomei Sianturi kini menduduki jabatan tersebut menggantikan Letjen https://t.co/8Wh4q2hdeJ",2110993346948907283,https://pbs.twimg.com/amplify_video_thumb/2110993286932680704/img/MttqhWUCUNW3vzLs.jpg,,in,,0,0,0,https://x.com/owritedotid/status/2110993346948907283,1964554328649453576,owritedotid
2110982005639012729,2026-10-16T07:16:47.000Z,0,@itszweedy PRABOWO ANJING,2110993341009785096,,itszweedy,in,,0,0,0,https://x.com/syalaamore/status/2110993341009785096,1791493821714604032,syalaamore
2110993332398920055,2026-10-16T07:16:45.000Z,0,"Sebelum komentar atau share berita Presiden Prabowo, cek lagi kevalidannya supaya nggak nyebarin kabar bohong #SaringInformasi https://t.co/fvcbbLm6Rb",2110993332398920055,https://pbs.twimg.com/media/HUvBPc6akAAQg04.jpg,,in,,0,0,0,https://x.com/alghia_dena/status/2110993332398920055,1678670618416541696,alghia_dena
2110993330809311589,2026-10-16T07:16:45.000Z,0,"Laporan Khusus Dua Tahun Prabowo–Gibran: Booming Bisnis Data Center di Indonesia, Apa yang Harus Dilakukan Pemerintah? https://t.co/liFx5ZJ3IZ via @indoict",2110993330809311589,,,in,,0,0,0,https://x.com/indoict/status/2110993330809311589,957482702,indoict
2110993327893909844,2026-10-16T07:16:44.000Z,0,Profil Mayjen TNI Sriyanto: Alumni SMA Taruna Nusantara Resmi Dilantik Presiden Prabowo Subianto jadi Wakil Kepala BPGMN RI https://t.co/e1ayWoiP2m,2110993327893909844,,,in,,0,0,0,https://x.com/TajukNasional/status/2110993327893909844,729309555486642176,TajukNasional
2110993323276325081,2026-10-16T07:16:43.000Z,0,"ga heran kan indo punya presiden kek prabowo? ya beginilah warganya, tone deaf.",2110993323276325081,,,in,,0,0,0,https://x.com/131larabee/status/2110993323276325081,1274680674230784003,131larabee
2110993317064536103,2026-10-16T07:16:41.000Z,0,Thanks God doa sejuta umat turunlan hujan di Kalimantan🙏💜,2110993317064536103,,,in,,0,0,0,https://x.com/MuvMuvna/status/2110993317064536103,1783468380139429888,MuvMuvna
2110927560934924324,2026-10-16T07:16:39.000Z,1,"@tribunnews Segera telepon prabowo....
Semuanya akan baik-baik saja",2110993309380600240,,tribunnews,in,,0,0,0,https://x.com/Idiand/status/2110993309380600240,220888132,Idiand
2110993299372958030,2026-10-16T07:16:37.000Z,0,"Pokoknya, kalau yang survei Adidaya Institute, kepuasan publik pada pemerintahan selalu tinggi....
Heheheeee

https://t.co/8EzGrfaS2I",2110993299372958030,,,in,,0,0,0,https://x.com/sipengen_tenar/status/2110993299372958030,1847982814895194112,sipengen_tenar
2110606115881046501,2026-10-16T07:16:33.000Z,0,"@hidanieldisini @txtdarigenz97 Prabowo ngunci Jokowi, tapi masyarakat masih punya 2 pilihan lain dan kok gobloknya yg terburuk yg justru yg menang 🫣",2110993282847359230,,hidanieldisini,in,,0,0,0,https://x.com/dikobelaja/status/2110993282847359230,1665582685157466113,dikobelaja
2110929784469626920,2026-10-16T07:16:32.000Z,0,"@LambeSahamjja Trus ganti menteri, ganti wamen...atau bikin lembaga baru utk menanggulangi kebakaran hutan. Paling itu agendanya.. Wowo gak mau melihat langsung ke sana, alasannya dulu kan sudah. Takut sesak napas dia.",2110993276019085632,,LambeSahamjja,in,,0,0,0,https://x.com/indah_suwondo/status/2110993276019085632,1638814473476612096,indah_suwondo
2110993270247739789,2026-10-16T07:16:30.000Z,0,"berapa ratus orang yang udah kena penyakit pernafasan gara-gara kebakaran hutan? ini pemerintah ga all-in padahal udahh berbulan2,,, masa depan bangsa pada mati semua sebelum umur 30 tahun 🤦",2110993270247739789,,,in,,0,0,0,https://x.com/rendrafrizal/status/2110993270247739789,1625480431415201794,rendrafrizal
2110950874109604188,2026-10-16T07:16:26.000Z,0,@SigitWasito8 Kegagalan prabowo adalah dosa terbesar jokowi yg jadikan dia presiden demi ambisi jadikan gibran wapres.,2110993254724645306,,SigitWasito8,in,,0,0,0,https://x.com/bukan4non/status/2110993254724645306,2148752027,bukan4non
2110993229739159836,2026-10-16T07:16:20.000Z,0,"Presiden Prabowo Subianto resmi melantik Jenderal Tandyo Budi Revita sebagai KSAD dan Jenderal Maruli Simanjuntak sebagai Wakil Panglima TNI, Kamis (15/10/2026).

“Mengangkat Jenderal Maruli Simanjuntak sebagai Wakil Panglima TNI merangkap Kepala Badan Nasional Pengelola https://t.co/iSE3qIahRe",2110993229739159836,https://pbs.twimg.com/amplify_video_thumb/2110993176702115840/img/1hQANtHjMeZibwLr.jpg,,in,,0,0,0,https://x.com/owritedotid/status/2110993229739159836,1964554328649453576,owritedotid
2110993224869487023,2026-10-16T07:16:19.000Z,1,"tadi liat konten warga Kalimantan kalau langitnya warna merah, bukan dari filter sosmed tapi karena kebakaran hutan. gusti pangeran teu kabayang euy nyesek pisan nafasna meren nya, ningalina oge ku loba haseup, kebul timana mana",2110993224869487023,,,in,,0,1,0,https://x.com/BaseBDG/status/2110993224869487023,1248335621988311041,BaseBDG
2110984568031555792,2026-10-16T07:16:19.000Z,1,"@harusbekerja pertama salah 58% 
kedua salah prabowo, krn setelah jadi bikin proyek yg ugal2an gatau arahnya kemana dan sangat tdk efisien. 
ketiga salah wakilnya juga kenapa dia maksa banget jadi wapres",2110993222256533867,,harusbekerja,in,,0,0,0,https://x.com/tachimchuu/status/2110993222256533867,996212005949267968,tachimchuu
2110993179860443309,2026-10-16T07:16:09.000Z,0,DIET GUA GAGAL GEGARA PRABOWO,2110993179860443309,,,in,,0,0,0,https://x.com/weltpyang/status/2110993179860443309,1415894962424586242,weltpyang
2110528247364747629,2026-10-16T07:15:59.000Z,0,"@MAzka58885102 @ferrykoto @SyedSaddiq Kecewa sama prabowo, ga foto2 di tengah hutan yang udh kebakar biar keliatan kerja",2110993140479832098,,Nugrohoisme,in,,0,0,0,https://x.com/Nugrohoisme/status/2110993140479832098,353749113,Nugrohoisme
2110756052287590868,2026-10-16T07:15:52.000Z,0,@ezash prabowo kak plis oper aja ke luar,2110993109806973339,,ezash,in,,0,0,0,https://x.com/pawangsadboy101/status/2110993109806973339,1568288736429092866,pawangsadboy101
2110992986373034226,2026-10-16T07:15:46.000Z,0,"tahapan penyelesaian administrasi dan pelaksanaan anggaran menjelang akhir tahun.
Melalui koordinasi ini, Balai Bahasa Provinsi Kalimantan Selatan berkomitmen untuk meningkatkan ketertiban administrasi keuangan, memastikan kelengkapan dokumen,",2110993085899649259,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110993085899649259,700676990722924544,balaibhskalsel
2110711759325499401,2026-10-16T07:15:44.000Z,0,@IrawanRommi @grok sekali lagi saya minta. Rank dampak karhutla dari yang terparah era SBY vs era Jokowi vs era prabowo,2110993077754310820,,IrawanRommi,in,,0,1,0,https://x.com/GamefaqsIDN/status/2110993077754310820,1962315346893021184,GamefaqsIDN
138948254804099072,2026-10-16T07:15:43.000Z,0,@prabowo @Gerindra Opo bedanya omon2 dengan ngecebret🤔,2110993072851214684,,prabowo,in,,0,0,0,https://x.com/WIPA60891075/status/2110993072851214684,1603757079717564417,WIPA60891075
2110993069655085118,2026-10-16T07:15:42.000Z,0,"Gak hutan
Gak Rupiah
Gak IHSG

semua kebakaran.",2110993069655085118,,,in,,0,0,0,https://x.com/nflsaragih/status/2110993069655085118,200422096,nflsaragih
2110988900705694189,2026-10-16T07:15:27.000Z,0,"@firstletterisY Tiap hari bukannya membaik malah makin buruk ini di Kalimantan, mana buzzer makin bego pula, ada yg speak up langsung diserang, dibungkam pula sama KEMKOMDIGI, sengaja mau dibunuh kayaknya kami yg di Kalimantan 😑😑😑",2110993004932821426,,firstletterisY,in,,0,0,0,https://x.com/galtzarr/status/2110993004932821426,61446677,galtzarr
2110377589093064881,2026-10-16T07:15:25.000Z,0,@elzraha @prabowo Kebagusan dipanggil Sir,2110992998137995667,,elzraha,in,,0,0,0,https://x.com/dandweissilla/status/2110992998137995667,314361584,dandweissilla
2110992986373034226,2026-10-16T07:15:22.000Z,0,"Halo, #SahabatBahasa!

Balai Bahasa Provinsi Kalimantan Selatan melaksanakan koordinasi dengan Kantor Pelayanan Perbendaharaan Negara (KPPN) Banjarmasin terkait proses gaji, SKPP(Surat Keterangan Pemberhentian Pembayaran) Mutasi ASN serta LLAT(Langkah-Langkah Akhir Tahun 2026) https://t.co/HgphATNSdq",2110992986373034226,https://pbs.twimg.com/media/HUvA6ymbAAAH13B.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110992986373034226,700676990722924544,balaibhskalsel
2110618714379051348,2026-10-16T07:15:16.000Z,0,"@G_redJ20 @kenhans03 @NusronWahid1 @prabowo @DPR_RI @KPK_RI @mohmahfudmd Nawaitu
Kalo kita bicara seorang tokoh agamis, maka mari kita agungkan nawaitu dan tenggungjawab di akherat dan karma di kehidupan ini.
Jika saya di posisi dia, saya akan menyesal dan bunuh diri.",2110992960540348600,,G_redJ20,in,,0,0,0,https://x.com/J_a2y0/status/2110992960540348600,239712409,J_a2y0
2110992917573898414,2026-10-16T07:15:06.000Z,0,"halloween pake baju prabowo, hidup setan setan yg melawan (setan jg)",2110992917573898414,,,in,,0,0,0,https://x.com/steefucaca/status/2110992917573898414,1087334897016922112,steefucaca
2110992892261171447,2026-10-16T07:15:00.000Z,0,"Kebakaran melanda kawasan Jalan Mayjen Sutoyo S, Kelurahan Telaga Biru, Kecamatan Banjarmasin Barat, Kota Banjarmasin, Kalimantan Selatan, Jumat (16/10/2026) dini hari. Berdasarkan laporan sementara yang mengutip data Dinas Pemadam Kebakaran dan Penyelamatan (DPKP) Kota",2110992892261171447,,,in,,0,0,0,https://x.com/leonardathens/status/2110992892261171447,2036047361940832256,leonardathens
2110957132732633553,2026-10-16T07:14:54.000Z,0,@estehijau_ illfeel kalo dia bela prabowo,2110992867208622273,,estehijau_,in,,0,0,0,https://x.com/kelodeonn/status/2110992867208622273,2299768676,kelodeonn
2110992857486254135,2026-10-16T07:14:52.000Z,0,"lagi sama bapa, lagi sama bapa, sombong bgt sok ngartis. 2027 gue bawa bapa prabowo sekalian gue sombongin depan biji mata lu",2110992857486254135,,,in,,0,0,0,https://x.com/juliaanggyy/status/2110992857486254135,1992265998280630273,juliaanggyy
2110992817057329393,2026-10-16T07:14:42.000Z,1,"Polres Wonosobo bersama TNI, Perhutani, dan masyarakat bergerak cepat memadamkan kebakaran hutan pinus di Dusun Pucungroto, Desa Kalikarung, Kecamatan Kalibawang, Kabupaten Wonosobo, Rabu malam (14/10). Kebakaran yang melanda kawasan hutan lindung milik Perhutani RPH Sapuran Kedu https://t.co/hf5P9dIgSx",2110992817057329393,https://pbs.twimg.com/media/HUvAweDa0AEpOlU.jpg,,in,,0,1,0,https://x.com/DivHumas_Polri/status/2110992817057329393,138290629,DivHumas_Polri
2110992814528172097,2026-10-16T07:14:41.000Z,0,Cuma di rezim prabowo operator spbu sampe digantiin tentara. Negara apa ini anjeeengggg.!,2110992814528172097,,,in,,0,0,0,https://x.com/Panjulrasakeju/status/2110992814528172097,728976835866820609,Panjulrasakeju
2110992801295114574,2026-10-16T07:14:38.000Z,0,ring of fire di otak prabowo adalah bikin a literal fire di Kalimantan (hadeh),2110992801295114574,,,in,,0,0,0,https://x.com/llyenawyn/status/2110992801295114574,1109862436234903553,llyenawyn
2110992797730017560,2026-10-16T07:14:37.000Z,0,"Baca selengkapnya: https://t.co/gnXwG0h9Mf

Seluruh menteri dan wakil menteri Kabinet Merah Putih dijadwalkan mengikuti rapat kabinet bersama Presiden Prabowo Subainto di Istana Bogor pada Jumat (16/10/2026) malam.

~MS #Prabowo #AstaCita [2026101613503161] https://t.co/SBQp2P3exR",2110992797730017560,https://pbs.twimg.com/media/HUvAwU1asAAxqsi.jpg,,in,,0,0,2,https://x.com/kompascom/status/2110992797730017560,23343960,kompascom
2110954676627595493,2026-10-16T07:14:25.000Z,6,"@txtdrimedia Mampus lu gubernur² kalimantan, ganti rugi lu ke negara sebelah, semoga dengan ini lu lebiv aware sama masyarakat lu sendiri terkait kondisi, jangan nunggu di gugat negara lain baru sadar, jangan seenaknya aja berfoya foya diatas penderitaan orang lain, dasar OKB",2110992744852369869,,txtdrimedia,in,,0,0,0,https://x.com/SweetyPieAraa/status/2110992744852369869,2065828064932888576,SweetyPieAraa
2110992733133316356,2026-10-16T07:14:22.000Z,0,"katanya gausa dibesar besarin masalah karhutla, sbnrnya elu melek gaksi wokkkk @prabowo @Gerindra",2110992733133316356,,,in,,0,0,0,https://x.com/1633crumble/status/2110992733133316356,1983907177397157888,1633crumble
2110989062622343336,2026-10-16T07:14:20.000Z,2,@saludosparatii Prabowo ini presiden paling gagal didunia,2110992724849807813,,saludosparatii,in,,0,1,0,https://x.com/Netizenbola123/status/2110992724849807813,2104822285718913024,Netizenbola123
2110992711847498184,2026-10-16T07:14:17.000Z,0,YaAllah turunkanlah hujan dan Prabowo Gibran,2110992711847498184,,,in,,0,0,0,https://x.com/waswasilkhonnas/status/2110992711847498184,1316369124453347331,waswasilkhonnas
2110981842677740031,2026-10-16T07:14:15.000Z,0,@GusDikaOfficial Jadinya prabowo presiden adalh dosa terbesar jokowi.,2110992702007546010,,GusDikaOfficial,in,,0,0,0,https://x.com/bukan4non/status/2110992702007546010,2148752027,bukan4non
2110992698756977001,2026-10-16T07:14:14.000Z,0,"Status bencana nasional bukan satu-satunya penentu kecepatan bantuan. Meski belum berstatus nasional, penanganan karhutla Kalimantan tetap melibatkan personel gabungan, pemadaman darat, hingga operasi udara. 
#KawalPenangananKarhutla #PemerintahBergerak https://t.co/r4SV8DQNKD",2110992698756977001,https://pbs.twimg.com/amplify_video_thumb/2110992669006778368/img/63eqC6GR9JWD2yTX.jpg,,in,,0,0,0,https://x.com/Khan05074664/status/2110992698756977001,1288146217386426373,Khan05074664
2110711759325499401,2026-10-16T07:14:14.000Z,0,@piscokgede @IrawanRommi Prabowo juga mengurus koruptor kalau soal tampil seolah mengurus mah sama aja keduanya. Sama sama suka menipu orang goblok,2110992697498763540,,piscokgede,in,,0,0,0,https://x.com/GamefaqsIDN/status/2110992697498763540,1962315346893021184,GamefaqsIDN
2110609734768427251,2026-10-16T07:14:10.000Z,0,@Galehfy @BANGSAygSUJUD @prabowo Ngimpi 🤣🤣🤣👏,2110992681858105538,,Galehfy,in,,0,0,0,https://x.com/bungusleader/status/2110992681858105538,2017882226822991872,bungusleader
2110809126347722920,2026-10-16T07:14:09.000Z,0,@segaizsme hah aku bukan mau insensitive kok cuma bagi perspektif sebagai orang yg ngadepin negara2 lain di rl. kami di kl jg sakit2an jujur dan malunya jg bukan karena orang2 kalimantan/sumatra kok lebih ke malu sm pemerintah. maaf kalo kedengeran insensitive tp maksudku gak gt,2110992678100021667,,segaizsme,in,,0,0,0,https://x.com/archenized/status/2110992678100021667,932122218670186496,archenized
2110976859928433023,2026-10-16T07:14:09.000Z,0,"@msaid_didu Tumben opung berpikir cerdas, sudah jelas pasar modal itu mainan oligarki utk meruntuhkan Presiden Prabowo",2110992676359401946,,msaid_didu,in,,0,0,0,https://x.com/Da_Ajiee/status/2110992676359401946,1604136659662307330,Da_Ajiee
2110992490719502391,2026-10-16T07:14:07.000Z,0,"digunakan dalam kehidupan sehari-hari.
Kehadiran Balai Bahasa Provinsi Kalimantan Selatan merupakan bentuk dukungan terhadap sinergi antara pemerintah daerah, satuan pendidikan, dan berbagai pihak dalam upaya pelindungan bahasa daerah. Diharapkan,",2110992669279142366,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110992669279142366,700676990722924544,balaibhskalsel
2110912959849570366,2026-10-16T07:14:05.000Z,0,@belvinvvipreal Bisa2nya bikin king ga makan hari ini. Tega @prabowo,2110992661327065159,,belvinvvipreal,in,,0,0,0,https://x.com/ModalAvgD/status/2110992661327065159,2031665488837885953,ModalAvgD
2110992621426651623,2026-10-16T07:13:55.000Z,0,"in this economy masih ada yang antri iphone 18, padahal di sisi lain masih ada yang antri bensin di bali, antri air di jawa barat, antri utk akses bantuan oksigen di kalimantan, dan antri masuk ke pesawat rute singapura - indonesia (pak gubernur kalimantan contohnya)",2110992621426651623,,,in,,0,0,0,https://x.com/crypto_menfess/status/2110992621426651623,1280522160377942018,crypto_menfess
2110826694982668742,2026-10-16T07:13:55.000Z,0,@NyaiNeneng Hercules versi Kalimantan,2110992619379859718,,NyaiNeneng,in,,0,0,0,https://x.com/paman_ojek/status/2110992619379859718,2400248299,paman_ojek
2110732178837602642,2026-10-16T07:13:53.000Z,0,@susipudjiastuti @prabowo Langsung Japri saja ke Beliau Ibu. 😁,2110992611892994393,,susipudjiastuti,in,,0,0,0,https://x.com/nygoews/status/2110992611892994393,164079141,nygoews
2110992602694869477,2026-10-16T07:13:51.000Z,0,IY LG MONYEEETTT baru mau menjalani hidup beneran apes dapet era prabowo shitt shittttt,2110992602694869477,,,in,,0,0,0,https://x.com/pixieyyo/status/2110992602694869477,1009466964203302912,pixieyyo
1112546208554221568,2026-10-16T07:13:48.000Z,0,"@Uki23 @prabowo anda ini mendukung jokowi 100 persen ya, sampai pak prabowo anda hajar habis di sosmed.",2110992589801595008,,Uki23,in,,0,0,0,https://x.com/sr6723/status/2110992589801595008,97611062,sr6723
2110992244027326874,2026-10-16T07:12:25.000Z,1,terus kapan gorok gubernur se Kalimantan raya yang tone deaf dan malah cabut ke Singapur itu?,2110992244027326874,,,in,,0,0,0,https://x.com/hujanyangturun_/status/2110992244027326874,710280429442441216,hujanyangturun_
2110992217439715610,2026-10-16T07:12:19.000Z,0,Penjilat akan tetap penjilat. Walau pun harus menjadi anjing. Cc. @prabowo,2110992217439715610,,,in,,0,0,0,https://x.com/DM_Sihombing16/status/2110992217439715610,832458432271704065,DM_Sihombing16
2110992209638314356,2026-10-16T07:12:17.000Z,0,"Boleh, kasih ke Paman Xi Jinping aja Kalimantan

Nanti panglima² tatoan itu dimasukin kamp pendidikan sama dia🤣",2110992209638314356,,,in,,0,0,0,https://x.com/KarinaShen54587/status/2110992209638314356,1948776122575192069,KarinaShen54587
2110980523091022082,2026-10-16T07:12:17.000Z,0,@dav_m_ib ehhh ikan yg cuma nemu kalok pas di Kalimantan,2110992207461351623,,dav_m_ib,in,,0,0,0,https://x.com/eko_neko3/status/2110992207461351623,1260723134358908928,eko_neko3
2110939022382309503,2026-10-16T07:12:16.000Z,0,"@JonghoJoestarr Prabowo tidak pernah mengatakan pakar tolol secara terbuka di kampanye Pilpres. Antek² asing itu adalah propaganda. 

Kalau agitasi kamu tetap merendahkan rakyat, itu akan menjadi propaganda bisa mengarah pada totaliterisme = hanya pendapat elite yg benar, rakyat tidak tahu apa²",2110992203804024837,,frmsrgr,in,,0,0,0,https://x.com/frmsrgr/status/2110992203804024837,1638681500,frmsrgr
2110992125383135234,2026-10-16T07:11:57.000Z,0,"Tragedi Karhutla Bromo, 3 Petugas dan Relawan Tewas Saat Padamkan Api
#kebakaran #gunungbromoterbakar #gunungbromo #korbankebakaranbromo #karhutlabromo2026 #poldajatim @HumasPoldaJatim 

https://t.co/s1NAZAGQDQ",2110992125383135234,,,in,,0,0,0,https://x.com/BongkahI/status/2110992125383135234,1226400848080539650,BongkahI
2110992124732915919,2026-10-16T07:11:57.000Z,0,"Wakapolres Melawi Kompol Aang Permana mengajak masyarakat untuk bersama-sama mencegah kebakaran hutan dan lahan (karhutla) serta memanfaatkan layanan Call Center 110 Polri saat membutuhkan bantuan kepolisian.

#polisibersamamasyarakat #polresmelawisiap #jumatkeliling #jagamelawi https://t.co/jWytLTlP8Z",2110992124732915919,https://pbs.twimg.com/media/HUvAIKwagAAKTis.jpg,,in,,0,0,0,https://x.com/polres_melawi86/status/2110992124732915919,1747090307798441984,polres_melawi86
2110992123872866545,2026-10-16T07:11:57.000Z,0,Orang yg enggak punya etika begini kau jadikan mentri...wo wo..😅🤣😜👎❤️🇮🇩😍✌️👌 cc. @prabowo @kompascom @tempodotco @Metro_TV @tvOneNews @msaid_didu @mohmahfudmd @MataNajwa https://t.co/sqBvkHaibJ,2110992123872866545,https://pbs.twimg.com/media/HUvAJVrbIAALUUB.jpg,,in,,0,0,0,https://x.com/wa_one1/status/2110992123872866545,81386247,wa_one1
2110609734768427251,2026-10-16T07:11:51.000Z,1,@farhanrizkippp @BANGSAygSUJUD @prabowo Yahahaha berita pesanan dipercaya miris cok 🤣🤣,2110992100636737946,,farhanrizkippp,in,,0,0,0,https://x.com/bungusleader/status/2110992100636737946,2017882226822991872,bungusleader
2110992051722748403,2026-10-16T07:11:51.000Z,0,"Kegiatan ini membahas teknis  pelaksanaan FTBI Tingkat Provinsi Kalimantan Selatan Tahun 2026 yang akan diselenggarakan pada Kamis, 29 September 2026 di Balai Bahasa Provinsi Kalimantan Selatan, dengan melibatkan peserta jenjang SD dan SMP.",2110992098065592493,,balaibhskalsel,in,,0,1,0,https://x.com/balaibhskalsel/status/2110992098065592493,700676990722924544,balaibhskalsel
2110992081753915765,2026-10-16T07:11:47.000Z,0,matlis lagi tapi kali ini karena kebakaran di blok sebelah huhu kasihan sekali :(,2110992081753915765,,,in,,0,1,0,https://x.com/stegoland/status/2110992081753915765,1989704537687691269,stegoland
2110992051722748403,2026-10-16T07:11:40.000Z,0,"Halo, #SabahatBahasa!

Dalam rangka persiapan pelaksanaan Festival Tunas Bahasa Ibu (FTBI) Tingkat Provinsi Kalimantan Selatan Tahun 2026, telah dilaksanakan kegiatan taklimat secara daring. https://t.co/5zxkFAJDRf",2110992051722748403,https://pbs.twimg.com/media/HUvAELbbEAAzEax.jpg,,in,,0,1,0,https://x.com/balaibhskalsel/status/2110992051722748403,700676990722924544,balaibhskalsel
2110696076517019781,2026-10-16T07:11:32.000Z,0,"@Ambakarok007 Tolong dibiasakan ngetik KEBAKARAN HUTAN bang, jangan karhutla karhutla. Apa itu karhutla? Singkatan yg ga semua orang paham. Biar algoritmanya tuh paham oh ada kebakaran hutan.",2110992018386411563,,Ambakarok007,in,,0,0,0,https://x.com/boreochoco/status/2110992018386411563,1813414170966302720,boreochoco
2110992009695744079,2026-10-16T07:11:30.000Z,15,"Kabarnya X lagi bagi duit $3000 buat yang mau post video vertikal doang 

syaratnya post 15 video ngata2in prabowo selama sebulan

ini beneran gak sih?",2110992009695744079,,,in,,0,15,0,https://x.com/isishaki/status/2110992009695744079,1105824703891988482,isishaki
2110738555723255947,2026-10-16T07:11:28.000Z,0,@Ozyyd @sosmedkeras @prabowo iya juga yaaa😅😅,2110992002162761842,,Ozyyd,in,,0,0,0,https://x.com/ciperamanuk/status/2110992002162761842,1603697958230593537,ciperamanuk
2110991989999358121,2026-10-16T07:11:25.000Z,2,"Kalo Kata buzzer 100 perak, “keluar aja sana kalo ga suka sama Prabowo”.

Gw: ACC bosku https://t.co/oo8gvBWQXP",2110991989999358121,https://pbs.twimg.com/media/HUvABmqawAApV2R.jpg,,in,,0,1,0,https://x.com/Jacksepertiga/status/2110991989999358121,1477114168536829952,Jacksepertiga
2110528247364747629,2026-10-16T07:11:25.000Z,0,"@MAzka58885102 @ferrykoto @SyedSaddiq Ga usah banding2in. Dr Jokowi smp prabowo udh berusaha. Nnt malu sendiri. Klo mau bs dibandingin jg sama data jaman pak harto.

Skrg 1 kejadian diviralin 1000 orang jd 1000 kejadian. https://t.co/a6ko3ENun4",2110991988686200979,https://pbs.twimg.com/media/HUvABbrakAAnNyk.jpg,MAzka58885102,in,,0,1,0,https://x.com/Nugrohoisme/status/2110991988686200979,353749113,Nugrohoisme
2110991973121417430,2026-10-16T07:11:21.000Z,0,semoga prabowo masuk neraka dan disiksa sedahsyat2nya siksaan neraka,2110991973121417430,,,in,,0,0,0,https://x.com/blckroot/status/2110991973121417430,1344919778436083714,blckroot
2110567694856769717,2026-10-16T07:11:15.000Z,0,"@yaniarsim @aniesbaswedan @prabowo Jika Melawan bencana Alami atau Buatan Manusia seperti Karhutla ini ibarat suatu Medan Peperangan, Maka Prabodo Subiantolol sebagai Jeneral Peperangan GAGAL TOTAL !!!

Omon-Omon aja tidak memastikan Karhutla. Pak Jeneral sendiri gak tahu dimana Kawasan terbakar besar.",2110991948006015304,,yaniarsim,in,,0,0,0,https://x.com/Salahuddin4yub1/status/2110991948006015304,1726029634083733504,Salahuddin4yub1
2110991945757765697,2026-10-16T07:11:14.000Z,0,"KATA ISTRIMU, KEBAKARAN HUTAN TERTANGANI 80% WOK??",2110991945757765697,,,in,,0,0,0,https://x.com/sighforlyfe/status/2110991945757765697,791250813767213056,sighforlyfe


--- cleaner.py ---

import pandas as pd


def hapus_kosong(df, kolom_penting):
    """
    Hapus baris yang kosong di kolom penting (mis. full_text).
    
    Parameter:
        df (DataFrame): data tweet
        kolom_penting (list): daftar kolom yang tidak boleh kosong
    
    Return:
        DataFrame: data tanpa baris kosong
    """
    return df.dropna(subset=kolom_penting)


def hapus_duplikat(df, kolom_kunci):
    """
    Hapus baris duplikat berdasarkan kolom kunci (mis. id_str).
    """
    return df.drop_duplicates(subset=kolom_kunci)


def filter_jumlah_kata(df, kolom_teks, min_kata=3):
    """
    Filter tweet yang jumlah katanya kurang dari min_kata.
    
    Parameter:
        df (DataFrame): data tweet
        kolom_teks (str): nama kolom teks (mis. "full_text")
        min_kata (int): jumlah kata minimum
    
    Return:
        DataFrame: tweet dengan >= min_kata kata
    """
    df = df.copy()
    df[kolom_teks] = df[kolom_teks].fillna("")           # NaN → ""
    jumlah_kata = df[kolom_teks].str.split().str.len()   # hitung kata
    return df[jumlah_kata >= min_kata]


def filter_bahasa(df, kolom_lang, bahasa):
    """
    Filter tweet berdasarkan kode bahasa.
    Kalau bahasa == "all", kembalikan semua.
    """
    if bahasa == "all":
        return df
    return df[df[kolom_lang] == bahasa]


def bersihkan(df, kolom_penting, kolom_kunci, kolom_teks, min_kata=3):
    """
    Pipeline cleaning lengkap (tanpa filter bahasa).
    Filter bahasa di-handle terpisah di app.py.
    """
    df = hapus_kosong(df, kolom_penting)
    df = hapus_duplikat(df, kolom_kunci)
    df = filter_jumlah_kata(df, kolom_teks, min_kata)
    return df

--- crawler.py ---

import subprocess

x_auth_token="1be9854751ed1d174baf5281f627dcae5c0b3da4" # (Pastikan token lu bener ya)

# Definisi fungsinya sekarang disamakan jadi input_keywords
def crawl_x(input_keywords, filename, since, until, limit):
    # 1. Pecah string koma-komaan dari UI menjadi list, lalu buang spasi kosongnya
    list_kw = [k.strip() for k in input_keywords.split(",") if k.strip()]

    # Keamanan tambahan: kalau ternyata setelah dipecah list-nya kosong
    if not list_kw:
        return False, "❌ Gagal crawl. Keyword tidak boleh kosong."

    # 2. Cek jumlah keyword buat nentuin format
    if len(list_kw) == 1:
        # Kalau cuma 1 keyword, biarin polos aja (misal: Fiony Alveria)
        gabungan_kw = list_kw[0]
    else:
        # Kalau > 1 keyword, dibungkus kutip dan OR (misal: ("Fiony" OR "Freya" OR "JKT48"))
        list_kutip = [f'"{k}"' for k in list_kw]
        gabungan_kw = f"({' OR '.join(list_kutip)})"

    # 3. Rangkai query akhir
    search_keyword = f"{gabungan_kw} since:{since} until:{until} lang:in"
    
    # Cetak ke terminal biar gampang nge-debug kalau query-nya aneh
    print(f"[*] MENJALANKAN QUERY: {search_keyword}")

    command = [
        "npx", "-y", "tweet-harvest@latest",
        "-o", filename,
        "-s", search_keyword,
        "--tab", "LATEST",
        "-l", str(limit),
        "--token", x_auth_token
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        return True, f"✅ Berhasil crawl. File: {filename}"
    else:
        return False, f"❌ Gagal crawl. Error:\n{result.stderr}"

--- data/slang.csv ---

slang,formal
udah,sudah
gua,aku
ntar,nanti
be like,seperti
aja,saja
dah,sudah
anjir,anjing
begimana,bagaimana
online,daring
offline,luring
gpp,tidak apa
the,sebuah
struggle,perjuangan
is,adalah
real,nyata
okeh,oke
mak,ibu
tp,tapi
xpa,apa
yg,yang
faham,paham
gue,aku
korona,corona
labtop,laptop
sohib,rekat
gak,tidak
tak,tidak
gru,guru
klo,kalau
ksi,kasih
g,tidak
dgn,dengan
trs,terus
lgi,lagi
ny,nya
lgi,lagi
jdi,jadi
dobell,ganda
scroll,gulir
lo,kamu
nggak,tidak
byk,banyak
maksuf,maksud
responsive,responsif
good luck,beruntung
nih,ini
ad,ada
karna,karena
tsb,tersebut
njing,anjing
deadline,batas waktu
group,grup
parents,orang tua
ayolohhh,ayo
mamah,ibu
twt,twitter
akhibat,akibat
tu,itu
org,orang
saya,aku
pinjem,pinjam
ortu,orang tua
yookkk,ayo
cutiepie,sayang
mami,ibu
d,di
ngeblank,kosong
ibuk,ibu
lgsg,langsung
hadeeeh,aduh
memori,ingatan
anjim,anjing
plis,tolong
bund,ibu
listri,listrik
ottoke,bagaimana
ampe,sampai
kek,seperti
ga,tidak
bener,benar
amat,sekali
yak,ya
nanya,tanya
jgn,jangan
yuk,ayo
tdk,tidak
waduh,aduh
kalo,kalau
gamampu,tidak mampu
yauda,yasudah
my,punyaku
story,cerita
end,akhir
ajaa,saja
budget,biaya
exactly,tepat
gaada,tidak ada
gunanyaa,guna
onlen,daring
banget,sekali
alhamdulillah,alhamdulilah
bgt,sekali
gaperlu,tidak perlu
gaes,teman
dapet,dapat
hadu,aduh
gaess,teman
susar,susah
belamra,belajar
bagaiman,bagaimana
sm,sama
kaya,seperti
privacy,pribadi
yaudah,yasudah
orng,orang
pd,pada
udh,sudah
kl,kalau
ky,seperti
tim,grup
I did,aku
asik,asyik
mampis,mati
mampos,mati
mampus,mati
yu,ayo
dlu,dulu
baubau,bau
new,baru
pake,pakai
naruh,taruh
job,pekerjaan
kel,kelas
on,nyala
ni,ini
nk,ingin
share,bagi
math,matematika
sikit,sedikit
take,ambil
guys,teman
gengs,teman
girls,gadis
yuks,ayo
check,cek
ngabs,bagaimana
on,nyala
cam,kamera
buk,ibu
pengin,ingin
ngak,tidak
klau,kalau
bnget,sekali
dear,sayang
bangettt,sekali
anjinggg,anjing
muluuu,selalu
taii,tahi
taii,tahi
bego,bodoh
kek,seperti
abisan,habis
yukk,ayo
request,minta
yng,yang
chattingan,obrolan
horror,seram
horor,seram
jilbab,kerudung
tura,tidur
turu,tidur
ujug,akhir
japri,hubungi
mhsw,mahasiswa
rek,teman
piye,bagaimana
masamu,menurutmu
pen,ingin
ngk,tidak
open,buka
santuy,santai
cuman,hanya
cuma,hanya
kayanya,seperti
anda,kamu
pc,komputer
fix,tetap
bejibun,banyak
hunting,buru
alesan,alasan
cekkkk,cek
emang,memang
fighting,berjuang
mahasiswai,mahasswa
taik,tahi
doi,dia
panikgogi,panik
inj,ini
onlineshittt,tahi
apaa,apa
nihhh,ini
ama,sama
selese,selesai
gegara,karena
kelarrrr,selesai
jadika,jadi
kongkret,konkret
smpe,sampai
mls,malas
boker,beol
buanyakkkk,banyak
bangettt,sekali
sampek,sampai
tapiiiii,tapi
teross,terus
weekend,akhir pekan
utk,untuk
mamposs,mati
kao,kamu
nak,anak
bnr,benar
gw,aku
pliss,tolong
pak,bapak
bu,ibu
kg,tidak
tetep,tetap
onlineeeeeeeee,daring
taudehhh,tahu
ngantukkkk,ngantuk
nggk,tidak
midtest,uts
bgst,bangsat
classroom,kelas
class,kelas
dedlen,batas waktu
njim,anjing
abis,habis
mid,uts
human,manusia
diacc,terima
acc,terima
ngelag,lambat
trus,terus
bun,ibu
rekomendasii,rekomendasi
tetp,tetap
bpkny,bapak
ngantuqqq,ngantuk
gasi,tidak
momen,peristiwa
moment,peristiwa
moments,peristiwa
mantapp,mantap
pala,kepala
ibuknyaa,ibu
mon,mohon
maap,maaf
ye,ya
lelet,lambat
aamiin,amin
notif,pemberitahuan
njirr,anjing
kayak,seperti
linglung,lupa
wa,whatsapp
whatsap,whatsapp
tibatiba,tiba
tggl,tanggal
tgl,tanggal
sem,semester
poor,miskin
me,aku
mabok,mabuk
dikiiit,sedikit
diem,diam
rule,aturan
kaga,tidak
paakk,bapak
pak,bapak
ceritaa,cerita
ceritaaa,cerita
please,tolong
lemot,lambat
reposted,ulang
moodiyan,murung
moody,murung
cewe,gadis
tranding,populer
trending,populer
paansi,apa
mles,malas
bet,sekali
sopinter,sok pintar
au,tahu
bangsaadd,bangsat
beloom ,belum
ajg,anjing
ngg,tidak
sobi,teman
sobat,teman
apalagu,apalagi
tgs,tugas
allaah,allah
apain,apa
bangub,bangun
lag,lambat
ambyar,hancur
trosss,terus
tross,terus
anying,anjing
nanyak,tanya
kyk,seperti
skrng,sekarang
skrg,sekarang
e learning,elearning
gae,buat
pdhl,padahal
pdahal,padahal
pdhal,padahal
mimin,admin
min,admin
engga,tidak
iyaa,iya
iyaaa,iya
iyy,iya
iy,iya
yes,iya
y,iya
dr,dari
dri,dari
sumbe,sumber
swipe,geser
bngt,sekali
kir,kira
dosenya,dosen
log out,keluar
biasany,biasa
ternyta,nyata
msih,masih
join,gabung
bapanya,bapak
tpi,tapi
pda,pada
here,sini
we,kita
go,pergi
again,lagi
poto,foto
photo,foto
ss,screenshot
dpt,dapat
idung,hidung
glowing,cahaya
wlwpun,walau
kw,kawasan
belon,belum
pakabar,apa kabar
ntah,entah
gaberani,tidak berani
seblm,sebelum
kezzzel,kesal
capek,kesal
cape,kesal
nnti,nanti
nti,nanti
tahajuddan,tahajud
gwe,aku
belom,belum
mw,ingin
bwt,untuk
amatt,sekali
yuuuu,ayo
yuu,ayo
bbrp,beberapa
plus,tambah
jg,juga
ituu,itu
tuuu,itu
tuh,itu
anjp,anjing
anj,anjing
essensial,penting
jugak,juga
sebel,kesal
unek,uneg
next,lanjut
krusial,penting
tar,nanti
berenti,berhenti
takan,tidak
dlm,dalam
adl,adalah
hrs,harus
handsanitazer,handsanitizer
mba,kakak
mas,kakak
mbak,kakak
error,gangguan
eror,gangguan
gokill,gokil
gokilll,gokil
read,baca
shop,toko
bangt,sekali
gaksuka,tidak suka
drakor,drama korea
drama korea,drama korea
toddler,balita
kasian,kasihan
why,kenapa
what,apa
how,bagaimana
also,juga
blur,buram
elah,allah
mulu,selalu
nongol,muncul
bug,virus
sekolahhh,sekolah
sekolahh,sekolah
leyeh,santai
thank ,terimakasih
you,kamu
mood,suka
ofline,luring
knp,kenapa
power,kekuatan
mkn,makan
bs,bisa
yaallah,allah
ajaa,saja
ancur,hancur
facial,perawatan muka
nder,teman
rapog,raport
sbb,karena
pgi,pagi
liat,lihat
off,mati
assignment,tugas
assignments,tugas
right,benar
so,jadi
kal,kalian
gt,gitu
duhh,aduh
trs,terus
logout,keluar
amattt,sekali
kaliii,kali
yaah,ya
xmau,tidak
bljar,belajar
pingin,ingin
somehow,bagaimana
miss,rindu
life,hidup
almost,hampir
every,setiap
day,hari
meninggoy,mati
idup,hidup
interacting,interaksi
with,dengan
people,orang
blas,sekali
standart,standar
amburadul,acak
atuh,aduh
bat,sekali
bangettt,sekali
mmbuat,buat
anjj,anjing
screenshots,screenshot
krn,karena
runut,runtut
bnyk,banyak
emak,ibu
ud,sudah
samaa,sama
sedihhh,sedih
sedihh,sedih
banyaaak,banyak
banyaak,banyak
rilek,santai
je,saja
exam,ujian
dahla,sudah
tak,tidak
room,ruang
worth it,guna
storytell,cerita
ttg,tentang
bosen,bosan
bocah,anak
fis,fisika
bio,biologi
ujan,hujan
gada,tidak
udahlah,sudah
sambi,sambil
gimanaaa,bagaimana
ak,aku
ayok,ayo
reply,balas
too,juga
pusingg,pusing
pusinggg,pusing
duh,aduh
kls,kelas
krna,karena
feel,merasa
u,kamu
ade,adik
lg,lagi
pngn,ingin
spt,seperti
duel,tanding
circle,lingkaran
kopid,covid
cok,jancuk
semangatt,semangat
semangattt,semangat
have,punya
nice,baik
first,pertama
all,semua
sbaikmya,baik
anxiety,gelisah
submit,kirim
etc,dsb
dll,dsb
sekarangg,sekarang
course,kursus
courses,kursus
kesel,kesal
super,sangat
mencar,pisah
ato,atau
udeh,sudah
enggak,tidak
smt,semester
workshop,seminar
amat,sekali
kdg,kadang
karna,karena
tpb,tapi
see,melihat
mayan,lumayan
mayann,lumayan
pdaku,pada
secape,kesal
time,waktu
w,aku
setaun,tahun
taun,tahun
mamposla,mati
focus,fokus
twit,twitter
cepet,cepat
help,bantu
emg,memang
gmn,bagaimana
lets,ayo
support,dukung
each,sesama
other,lain
public,publik
speaking,bicara
poll,paling
kea,seperti
gestur,sikap
gesture,sikap
enaaa,enak
haih,aduh
jhe,saja
face,wajah
to,ke
convert,konfersi
clinical,klinik
years,tahun
inimah,ini
abistu,habis
february,februari
january,januari
reti,sampai
wis,sudah
wae,saja
apply,lamar
project,proyek
twit,twitter
respect,hormat
kudu,harus
them,mereka
set,setengah
bsk,besok
hadie,aduh
iyha,iya
mama,ibu
mami,ibu
jug,juga
then,lalu
fully,penuh
boss,bos
hallo,halo
aje,saja
bundz,ibu
apus,hapus
itung,hitung
nnton,nonton
trouble,masalah
diuruss,urus
njir,anjing
takda,tidak
gtgt,gitu
practical,praktikal
boong,bohong
kepake,pakai
suke,suka
sapa,siapa
semuanyaaaaaa,semua
student,siswa
students,siswa
slalu,selalu
miiin,admin
telp,telpon
aj,saja
mudeng,paham
loss,hilang
ilang,hilang
emmak,ibu
jjur,jujur
bru,baru
semwa,semua
gedeg,kesal
yabalik,balik
and,dan
login,masuk
mo,ingin
ngapaain,apa
offcam,tutup kamera
oncam,buka kamera
bomat,bodoamat
sad,sedih
mmg,memang
masuklh,masuk
diem,diam
bln,bulan
je,saja
jatoh,jatuh
jatohnya,jatuh
mmf,maaf
jbjb,tiba
gtu,gitu
heyy,halo
morning,pagi
dh,sudah
gi,lagi
smngt,semangat
kuis,quiz
cardi,cardigan
kampretos,kampret
wkt,waktu
bestfriend,teman
morningg,pagi
morninggg,pagi
kak,kakak
everyone,semua
met,selamat
she,dia
like,seperti
ngadi,ada
split,pisah
saking,sampai
smkin,semakin
rajiiiin,rajin
stand by,siap
pls,tolong
uda,sudah
shit,tahi
shits,tahi
really,benar
need,butuh
someone,orang
talk,bicara
bodo,bodoh
amat,sekali
group,grup
adek,adik
masi,masih
school,sekolah
relate,hubung
gimanaa,bagaimana
puyeng,pusing
achievement,penghargaan
tai,tahi
kasi,kasih
leha,santai
perfect,sempurna
attendaance,hadir
jawapan,jawaban
jadual,jadwal
hape,hp
slow,lambat
noti,pemberitahuan
because,karena
sekaliii,sekali
msh,masih
inget,ingat
bang,kakak
last,akhir
hapyyy,senang
dikick,usir
intern,magang
tidurrrrrr,tidur
ngzoom,zoom
damn,sial
mostly,sering
braw,kakak
temen,teman
cont,lanjut
sregep,rajin
jugaaa,juga
blended,gabung
dg,dengan
kanca,teman
akeh,banyak
seko,dari
lol,tertawa
ges,teman
flat,datar
fandom,fan
fangirl,fan
abang,kakak
ttp,tetap
moto,foto
anjirt,anjing
fak,anjing
abs,habis
wtf,anjing
out,keluar
drpd,daripada
puter,putar
make,buat
waktuny,waktu
selaluu,selalu
troboos,trobos
berenti,berhenti
stop,berhenti
emhnya,memang
td,tadi
grgr,gara
sob,teman
ngga,tidak
stupid,bodoh
nyambi,sambil
badmood,murung
demen,suka
kolor,boxer
diaa,dia
diaaa,dia
bukaan,bukan
international,internasional
officeeee,kantor
free,gratis
gitcu,gitu
darii,dari
uni,universitas
buna,ibu
bunanya,ibu
upload,unggah
story,cerita
kalii,kali
positip,positif
brooooooo,teman
bruuuhhhh,teman
webminar,webinar
skolah,sekolah
gimanasi,bagaimana
skap,skip
cmn,cuma
gblk,bodoh
jim,anjing
eek,beol
cuk,jancuk
sgt,sangat
taekk,tahi
that,itu
hate,benci
college,kuliah
offlen,luring
offlennya,luring
dama,sama
gapapaa,tidak apa
tell,beritahu
us,kami
will,akan
nannya,tanya
anjrit,anjing
smpt,sempat
ayen,aku
univ,universitas
nile,nilai
anjlog,turun
boi,anak
siah,bagaimana
napas,nafas
bernapas,nafas
robb,allah
dgrin,dengar
sek,masih
dikongkon,suruh
kongkon,suruh
najan,karena
salahno,salah
dkk,dsb
mder,teman
dat,itu
prnh,pernah
mhswnya,mahasiswa
mhsw,mahasiswa
kick,usir
paniiikkk,panik
paniikkk,panik
idupin,hidup
rank,peringkat
fav,favorit
masup,masuk
psti,pasti
dpn,depan
kamerlah,kamera
kamer,kamera
bangett,sekali
ngntuk,ngantuk
yutub,youtube
reeeeekk,teman
bangeeeeeeeeddd,sekali
even,bahkan
biasae,biasa
ttg,tentang
trmsk,termasuk
subject,subjek
he,dia
wants,ingin
happy,senang
combination,kombinasi
dude,teman
what,apa
wrong,salah
crack,pecah
serek,serak
or,atau
jwb,jawab
scr,secara
balance,imbang
left,keluar
kat,dekat
dek,dik
nyokap,ibu
bokap,bapak
wit,twitter
brisik,berisik
bcs,karena
dikasi,kasih
slese,selesai
mggu,minggu
menabahh,tambah
nabah,tambah
gasin,gas
gass,gas
gasss,gas
hayu,ayo
abah,bapak
sklh,sekolah
boring,bosan
pagiiiiii,pagi
hayo,ayo
home,rumah
ketiwi,tawa
ketawa,tawa
sampe,sampai
alfa,alpa
hr,hari
br,baru
mincot,admin
iyhh,iya
team,grup
gemeter,getar
kelar,selesai
kaak,kakak
bobooo,tidur
bobo,tidur
bobok,tidur
njirrrr,anjing
mellow,lembut
prefer,suka
naok,naik
naro,taruh
by,dari
ori,asli
yt,youtube
jk,gurau
mtk,matematika
saiki,sekarang
blass,blas
po,apa
call,telpon
mhs,mahasiswa
tauu,tahu
arek,anak
ambis,ambisius
blank,kosong
sja,saja
voice,suara
syg,sayang
fake,palsu
mblenger,terlalu
walo,walau
walopun,walau
kekeuh,kukuh
yaambunnn,allah
punggu,punggung
alesan,alasan
redirect,alih
nyatet,catat
bakal,akan
bakalan,akan
bkalan,akan
leave,keluar
cengini,siang
gi,lagi
dm,pesan
volunteer,relawan
kagok,susah
ngelambe,bicara
personal,pribadi
rotate,putar
takpa,tidak apa
dpt,dapat
ssejak,sejak
coroni,corona
beres,selesai
sumpahh,sumpah
sumpahhh,sumpah
tuhhh,itu
harusnyaa,harus
praktek,praktik
les,kursus
mimin,admin
mas,kakak
bapack,bapak
drop,jatuh
pulak,pula
give,beri
away,jauh
aslii,asli
mksudnya,maksud
mksud,maksud
kyknya,seperti
ja,saja
duk,duduk
cakap,bicara
rejeki,rezeki
rizki,rezeki
rizkinya,rezeki
rejekinya,rezeki
ujan,hujan
maybe,mungkin
brou,kakak
keep,simpan
spirit,semangat
focus,fokus
prayer,doa
believe,percaya
can,dapat
skola,sekolah
gatauuu,tidak tahu
perna,pernah
tolol,bodoh
murid,siswa
ngaco,kacau
jela,saja
book,buku
ikit,ikut
pape,apa
hrsnya,harus
mlu,selalu
see,lihat
liat,lihat
pertma,pertama
tdr,tidur
anjm,anjing
repeat,ulang
pgn,ingin
gtloh,gitu
ktmu,temu
bodo,bodoh
sik,masih
smlm,malam
looooove,cinta
in,di
sembuhhhhh,sembuh
mcm,macam
dgr,dengar
tgk,lihat
dst,dsb
cepetaaan,cepat
university,universitas
coronces,corona
apsen,absen
apalgi,apa
ade,adik
adenya,adik
buanyak,banyak
baique,baik
as,sebagai
contact,kontak
jur,jurusan
mnyimak,simak
fifty,limapuluh
dedel,susah
sby,surabaya
mna,mana
pagii,pagi
sbg,sebagai
beginiiiiii,begini
sekaliiii,sekali
kawan,teman
listen,dengar
up,atas
pede,percaya diri
pd,percaya diri
maleeees,malas
like,suka
duit,uang
duid,uang
money,uang
triak,teriak
noooo,tidak
ajj,anjing
sister,kakak
brother,kakak
nite,malam
esok,besok
equals,sama
lamaaaaa,lama
lamaaaa,lama
lamaaa,lama
lamaa,lama
yailaaah,allah
maksain,paksa
manaa,mana
full,penuh
award,penghargaan
kene,sini
mention,sebut
degdegan,deg
gituu,gitu
gituuu,gitu
yainti,inti
yaintinya,inti
gatau,tidak tahu
hype,terkenal
burem,buram
smpe,sampai
muluu,selalu
alhasil,hasil
cont,lanjut
makasii,terimakasih
makasi,terimakasih
touch,sentuh
ileran,liur
thinking,pikir
maksd,maksud
maksdny,maksud
maksdnya,maksud
mkst,maksud
mkstnya,maksud
ngewe,mesum
pr,tugas
justice,adil
manjun,manjur
stadd,ustaz
stay,tinggal
healthy,sehat
brrti,arti
ka,kakak
kreta,kereta
berbeza,beda
mantep,mantap
friver,kemudi
bgsd,bangsat
ngapa,apa
ngapain,apa
stres,stress
back,kembali
start,mulai
batre,baterai
batrenya,baterai
pengen,ingin
tuker,tukar
tukeran,tukar
time,waktu
oncam,kamera
msuk,masuk
socialize,sosialisasi
need,butuh
don,tidak
lngsung,langsung
bngun,bangun
shopping,belanja
postpone,tunda
comment,komentar
sorry,maaf
not,tidak
for,untuk
kuh,aku
akuu,aku
bcs,karena
yukkk,ayo
sendiriiii,sendiri
nderrr,teman
sirkel,lingkaran
boro,jangan
tkt,takut
graduate,lulus
hactic,sibuk
hectic,sibuk
malem,malam
fikiran,pikir
fikir,pikir
begokk,bodoh
btw,omong
berasaaa,rasa
guee,aku
gasi,tidak
allahuu,allah
bisnes,bisnis
sebenarnyaaa,benar
allahu,allah
service,layan
spot,titik
anjr,anjing
dont,jangan
things,hal
getting,jadi
worse,buruk
dunt,tidak
hv,punya
friends,teman
diff,beda
bawel,cerewet
mkin,semakin
jek,ojek
giveaway,hadiah
baij,baik
sgt,sekali
nga,tidak
gada,tidak ada
ocehan,omong
oceh,omong
lbh,lebih
pass,pas
gk,tidak
terbaikkkkk,baik
very,sangat
nice,baik
idea,ide
pandemik,pandemi
rapih,rapi
manage,atur
mgga,tidak
pastu,pasti
signal,jaringan
inimah,ini
benr,benar
fuck,persetan
luama,lama
tegor,tegur
ditegor,tegur
anjeng,anjing
quota,kuota
dsj,dsb
unfair,tidak adil
btul,betul
ofc,tentu
kerumahz,rumah
rumahz,rumah
enek,eneg
encourage,semangat
hadeh,aduh
automatically,auto
done,sudah
thanks,terimakasih
wish,harap
luck,beruntung
mantau,pantau
donlod,unduh
download,unduh
least,setidaknya
bye,selamat tinggal
byebye,selamat tinggal
mamah,ibu
enau,enak
god,tuhan
nimb,nimbun
mlah,malah
smst,semester
set,setengah
weekdays,pekan
uninstal,uninstall
gausah,tidak
cman,cuma
aing,aku
manteman,teman
gapake,tidak pakai
hijab,kerudung
anjae,anjing
anjayani,anjing
proper,layak
dec,desember
brng,bareng
gaspol,gas
rapot,raport
rampyungg,sudah
maning,lagi
ngesuk,besok
esih,masih
pressure,tekanan
maloe,malu
astagaaa,astaga
lalen,lupa
hustle,ramai
kebablasan,kelewat
bablasa,kelewat
lebi,lebih
abiji,nilai
event,acara
setidakmungkin,tidak mungkin
berak,beol
thought,pikir
cuddling,peluk
deadass,mati
refers,tuju
satuu,satu
sakitt,sakit
semogaaa,semoga
teruss,terus
everyday,setiap hari
gils,gila
uga,juga
dengaaaan,dengan
maraton,marathon
dinner,makan malam
client,klien
useless,tidak berguna
caper,cari perhatian
caperr,cari perhatian
caperrr,cari perhatian
item,hitam
belajarpun,belajar
elahhh,allah
mapelah,mapel
only,hanya
our,kami
one,satu
angell,susah
pleciden,presiden
through,lewat
dag,deg
dig,deg
dug,deg
sagne,mesum
ngekick,usir
hbis,habis
maniiis,manis
details,detil
wasap,whatsapp
standby,tinggal
love,suka
texting,obrol
text,obrol
outfit,pakaian
kantung,kantong
mrasa,merasa
thdp,hadap
malaya,malaysia
indo,indonesia
play,main
sleep,tidur
skrang,sekarang
jirr,anjing
flop,gagal
survive,bertahan
best,terbaik
feeling,perasaan
poadcast,podcast
sometimes,kadang
test,ujian
quiz,kuis
final,akhir
dewee,sendiri
crash,tabrak
yaudahlaa,sudah
months,bulan
dahhh,sudah
jwabin,jawab
mislkn,misal
jwbn,jawab
tkut,takut
mirit,siswa
hqq,hakiki
aminn,amin
poop,beol
sndri,sendiri
camping,kemah
doh,aduh
apps,aplikasi
app,aplikasi
sya,aku
bkan,bukan
spupu,sepupu
laqnat,laknat
eskul,ekstrakulikuler
ngilang,hilang
sist,kakak
luv,sayang
sabi,bisa
interact,interaksi
muridnya,siswa
apakbar,apa kabar
opsi,pilihan
recorder,rekam
nongkrong,kumpul
nongki,kumpul
wonge,orang
ancen,memang
iki,ini
lag,lambat
asu,anjing
udahan,sudah
aq,aku
ibun,ibu
ayah,bapak
gasanggup,tidak sanggup
manut,nurut
rank,peringkat
rangking,peringkat
skarang,sekarang
mindset,pikir
jugaaaaa,juga
asuuuuuu,anjing
bokep,porno
ngebokep,porno
taiiii,tahi
point,titik
pasrahh,pasrah
yaudahla,sudah
kagettt,kaget
tricky,rumit
edgy,gelisah
buosen,bosan
expectation,harap
reality,realitas
attack,serang
dahal,padahal
ttep,tetap
msk,masuk
silent,diam
kulaih,kuliah
ijin,izin
emng,memang
smph,sumpah
excited,semangat
makasih,terimakasih
mngkin,mungkin
apala,apa
decided,memutuskan
masturbate,masturbasi
denger,dengar
kmrn,kemarin
kemaren,kemarin
bdg,bandung
ikutt,ikut
oengen,ingin
kelen,kalian
lamaaaaa,lama
fresh,segar
kuliat,lihat
isoo,bisa
abes,habis
muzikgempak,musik
pinter,pintar
diaa,dia
jugaa,juga
males,malas
hariini,hari
smgt,semangat
konsen,konsentrasi
fav,suka
tehthering,tethering
sialllllllllll,sial
tmn,teman
cowo,cowok
sumpe,sumpah
cheating,curang
cheat,curang
kakel,kakak tingkat
sangatttt,sangat
habisla,habis
keasikan,asyik
regis,registrasi
itung,hitung
welcome,selamat datang
muk,ingin
masterpiece,mahakarya
cororong,corona
gatay,tidak tahu
entar,nanti
nongkrrong,kumpul
eren,keren
iyegahhh,tidak
dirumaahh,rumah
mandipun,mandi
dha,sudah
korona,corona
klen,kalian
anjg,anjing
beneerr,benar
bangeettt,sekali
bpk,bapak
macem,macam
adlh,adalah
penat,pusing
sekola,sekolah
tapii,tapi
kdng,kadang
kaliam,kalian
hayuk,ayo
party,pesta
embo,tidak tahu
bolot,tuli
budeg,tuli
omg,tuhan
bundir,bunuh diri
pengin,ingin
sad,sedih
alpokat,alpukat
avocado,alpukat
reformasj,reformasi
tkut,tidak
mengajarr,ajar
ajarr,ajar
cintaim,cinta
probably,mungkin
overthinking,pikir
betulllll,benar
doswn,dosen
seger,segar
rona,corona
sepineee,sepi
polllllll,sangat
orgorg,orang
dn,dan
mudeng,paham
problem,masalah
hrus,harus
schedule,jadwal
gasik,tidak
stgh,setengah
goblokkk,bodoh
lagiiii,lagi
alloh,allah
ln,lain
gaadak,tidak ada
jaman,zaman
etapi,tapi
bgtt,sekali
iyaaaaa,iya
sng,senang
connection,koneksi
ikt,ikut
adapted,adaptasi
seneng,senang
weird,aneh
konsul,konsultasi
pa,bapak
maloee,malu
lagii,lagi
pakek,pakai
semangak,semangat
menurutgw,nurut
tbh,jujur
internship,magang
scholarship,beasiswa
ilmunyaaa,ilmu
djancokk,jancuk
serep,serap
enjoy,nikmat
plan,rencana
hopefully,harap
ginii,begini
brpa,berapa
tarsoktarsok,nanti
panikk,panik
bangeeet,sekali
ambyarrrrr,hancur
ampunddd,ampun
maen,main
wayahe,waktu
hape,hp
entok,dapat
kiraiin,kira
asw,anjing
monangesss,nangis
punyaaaaa,punya
adi,adik
pgen,ingin
music,musik
favorite,suka
sbgai,sebagai
gabs,tidak bisa
jdny,jadi
gada,tidak ada
sajahh,saja
bapa,bapak
without,tanpa
bilding,gedung
stuffs,barang
normalize,normal
kmi,kami
afternoon,sore
gilak,gila
ndaa,tidak
gituu,gitu
mslah,masalah
drumah,rumah
tntang,tentang
ripyuu,tinjau
sinyal,jaringan
meneh,lagi
anaku,anak


--- data/stopwordbahasa.csv ---

ada
adalah
adanya
adapun
agak
agaknya
agar
akan
akankah
akhir
akhiri
akhirnya
aku
akulah
amat
amatlah
anda
andalah
antar
antara
antaranya
apa
apaan
apabila
apakah
apalagi
apatah
artinya
asal
asalkan
atas
atau
ataukah
ataupun
awal
awalnya
bagai
bagaikan
bagaimana
bagaimanakah
bagaimanapun
bagi
bagian
bahkan
bahwa
bahwasanya
baik
bakal
bakalan
balik
banyak
bapak
baru
bawah
beberapa
begini
beginian
beginikah
beginilah
begitu
begitukah
begitulah
begitupun
bekerja
belakang
belakangan
belum
belumlah
benar
benarkah
benarlah
berada
berakhir
berakhirlah
berakhirnya
berapa
berapakah
berapalah
berapapun
berarti
berawal
berbagai
berdatangan
beri
berikan
berikut
berikutnya
berjumlah
berkali-kali
berkata
berkehendak
berkeinginan
berkenaan
berlainan
berlalu
berlangsung
berlebihan
bermacam
bermacam-macam
bermaksud
bermula
bersama
bersama-sama
bersiap
bersiap-siap
bertanya
bertanya-tanya
berturut
berturut-turut
bertutur
berujar
berupa
besar
betul
betulkah
biasa
biasanya
bila
bilakah
bisa
bisakah
boleh
bolehkah
bolehlah
buat
bukan
bukankah
bukanlah
bukannya
bulan
bung
cara
caranya
cukup
cukupkah
cukuplah
cuma
dahulu
dalam
dan
dapat
dari
daripada
datang
dekat
demi
demikian
demikianlah
dengan
depan
di
dia
diakhiri
diakhirinya
dialah
diantara
diantaranya
diberi
diberikan
diberikannya
dibuat
dibuatnya
didapat
didatangkan
digunakan
diibaratkan
diibaratkannya
diingat
diingatkan
diinginkan
dijawab
dijelaskan
dijelaskannya
dikarenakan
dikatakan
dikatakannya
dikerjakan
diketahui
diketahuinya
dikira
dilakukan
dilalui
dilihat
dimaksud
dimaksudkan
dimaksudkannya
dimaksudnya
diminta
dimintai
dimisalkan
dimulai
dimulailah
dimulainya
dimungkinkan
dini
dipastikan
diperbuat
diperbuatnya
dipergunakan
diperkirakan
diperlihatkan
diperlukan
diperlukannya
dipersoalkan
dipertanyakan
dipunyai
diri
dirinya
disampaikan
disebut
disebutkan
disebutkannya
disini
disinilah
ditambahkan
ditandaskan
ditanya
ditanyai
ditanyakan
ditegaskan
ditujukan
ditunjuk
ditunjuki
ditunjukkan
ditunjukkannya
ditunjuknya
dituturkan
dituturkannya
diucapkan
diucapkannya
diungkapkan
dong
dua
dulu
empat
enggak
enggaknya
entah
entahlah
guna
gunakan
hal
hampir
hanya
hanyalah
hari
harus
haruslah
harusnya
hendak
hendaklah
hendaknya
hingga
ia
ialah
ibarat
ibaratkan
ibaratnya
ibu
ikut
ingat
ingat-ingat
ingin
inginkah
inginkan
ini
inikah
inilah
itu
itukah
itulah
jadi
jadilah
jadinya
jangan
jangankan
janganlah
jauh
jawab
jawaban
jawabnya
jelas
jelaskan
jelaslah
jelasnya
jika
jikalau
juga
jumlah
jumlahnya
justru
kala
kalau
kalaulah
kalaupun
kalian
kami
kamilah
kamu
kamulah
kan
kapan
kapankah
kapanpun
karena
karenanya
kasus
kata
katakan
katakanlah
katanya
ke
keadaan
kebetulan
kecil
kedua
keduanya
keinginan
kelamaan
kelihatan
kelihatannya
kelima
keluar
kembali
kemudian
kemungkinan
kemungkinannya
kenapa
kepada
kepadanya
kesampaian
keseluruhan
keseluruhannya
keterlaluan
ketika
khususnya
kini
kinilah
kira
kira-kira
kiranya
kita
kitalah
kok
kurang
lagi
lagian
lah
lain
lainnya
lalu
lama
lamanya
lanjut
lanjutnya
lebih
lewat
lima
luar
macam
maka
makanya
makin
malah
malahan
mampu
mampukah
mana
manakala
manalagi
masa
masalah
masalahnya
masih
masihkah
masing
masing-masing
mau
maupun
melainkan
melakukan
melalui
melihat
melihatnya
memang
memastikan
memberi
memberikan
membuat
memerlukan
memihak
meminta
memintakan
memisalkan
memperbuat
mempergunakan
memperkirakan
memperlihatkan
mempersiapkan
mempersoalkan
mempertanyakan
mempunyai
memulai
memungkinkan
menaiki
menambahkan
menandaskan
menanti
menanti-nanti
menantikan
menanya
menanyai
menanyakan
mendapat
mendapatkan
mendatang
mendatangi
mendatangkan
menegaskan
mengakhiri
mengapa
mengatakan
mengatakannya
mengenai
mengerjakan
mengetahui
menggunakan
menghendaki
mengibaratkan
mengibaratkannya
mengingat
mengingatkan
menginginkan
mengira
mengucapkan
mengucapkannya
mengungkapkan
menjadi
menjawab
menjelaskan
menuju
menunjuk
menunjuki
menunjukkan
menunjuknya
menurut
menuturkan
menyampaikan
menyangkut
menyatakan
menyebutkan
menyeluruh
menyiapkan
merasa
mereka
merekalah
merupakan
meski
meskipun
meyakini
meyakinkan
minta
mirip
misal
misalkan
misalnya
mula
mulai
mulailah
mulanya
mungkin
mungkinkah
nah
naik
namun
nanti
nantinya
nyaris
nyatanya
oleh
olehnya
pada
padahal
padanya
pak
paling
panjang
pantas
para
pasti
pastilah
penting
pentingnya
per
percuma
perlu
perlukah
perlunya
pernah
persoalan
pertama
pertama-tama
pertanyaan
pertanyakan
pihak
pihaknya
pukul
pula
pun
punya
rasa
rasanya
rata
rupanya
saat
saatnya
saja
sajalah
saling
sama
sama-sama
sambil
sampai
sampai-sampai
sampaikan
sana
sangat
sangatlah
satu
saya
sayalah
se
sebab
sebabnya
sebagai
sebagaimana
sebagainya
sebagian
sebaik
sebaik-baiknya
sebaiknya
sebaliknya
sebanyak
sebegini
sebegitu
sebelum
sebelumnya
sebenarnya
seberapa
sebesar
sebetulnya
sebisanya
sebuah
sebut
sebutlah
sebutnya
secara
secukupnya
sedang
sedangkan
sedemikian
sedikit
sedikitnya
seenaknya
segala
segalanya
segera
seharusnya
sehingga
seingat
sejak
sejauh
sejenak
sejumlah
sekadar
sekadarnya
sekali
sekali-kali
sekalian
sekaligus
sekalipun
sekarang
sekarang
sekecil
seketika
sekiranya
sekitar
sekitarnya
sekurang-kurangnya
sekurangnya
sela
selain
selaku
selalu
selama
selama-lamanya
selamanya
selanjutnya
seluruh
seluruhnya
semacam
semakin
semampu
semampunya
semasa
semasih
semata
semata-mata
semaunya
sementara
semisal
semisalnya
sempat
semua
semuanya
semula
sendiri
sendirian
sendirinya
seolah
seolah-olah
seorang
sepanjang
sepantasnya
sepantasnyalah
seperlunya
seperti
sepertinya
sepihak
sering
seringnya
serta
serupa
sesaat
sesama
sesampai
sesegera
sesekali
seseorang
sesuatu
sesuatunya
sesudah
sesudahnya
setelah
setempat
setengah
seterusnya
setiap
setiba
setibanya
setidak-tidaknya
setidaknya
setinggi
seusai
sewaktu
siap
siapa
siapakah
siapapun
sini
sinilah
soal
soalnya
suatu
sudah
sudahkah
sudahlah
supaya
tadi
tadinya
tahu
tahun
tak
tambah
tambahnya
tampak
tampaknya
tandas
tandasnya
tanpa
tanya
tanyakan
tanyanya
tapi
tegas
tegasnya
telah
tempat
tengah
tentang
tentu
tentulah
tentunya
tepat
terakhir
terasa
terbanyak
terdahulu
terdapat
terdiri
terhadap
terhadapnya
teringat
teringat-ingat
terjadi
terjadilah
terjadinya
terkira
terlalu
terlebih
terlihat
termasuk
ternyata
tersampaikan
tersebut
tersebutlah
tertentu
tertuju
terus
terutama
tetap
tetapi
tiap
tiba
tiba-tiba
tidak
tidakkah
tidaklah
tiga
tinggi
toh
tunjuk
turut
tutur
tuturnya
ucap
ucapnya
ujar
ujarnya
umum
umumnya
ungkap
ungkapnya
untuk
usah
usai
waduh
wah
wahai
waktu
waktunya
walau
walaupun
wong
yaitu
yakin
yakni
yang

--- preprocessing/__init__.py ---



--- preprocessing/pipeline.py ---

import os
import re
import pandas as pd
import nltk
from nltk.corpus import stopwords
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

# --- 1. SET UP NLTK & PATH KAMUS ---
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '..', 'data')

# A. Load Kamus Slang CSV
kamus_slang = {}
slang_path = os.path.join(DATA_DIR, 'slang.csv')
if os.path.exists(slang_path):
    try:
        df_slang = pd.read_csv(slang_path)
        if 'slang' in df_slang.columns and 'formal' in df_slang.columns:
            kamus_slang = pd.Series(df_slang['formal'].values, index=df_slang['slang']).to_dict()
    except Exception:
        pass

# B. Load Stopwords (NLTK + CSV + Manual)
stop_words_set = set(stopwords.words('indonesian'))
stop_path = os.path.join(DATA_DIR, 'stopwordbahasa.csv')
if os.path.exists(stop_path):
    try:
        df_stop = pd.read_csv(stop_path, header=None, names=['kata_stop'])
        stop_words_set.update(df_stop['kata_stop'].dropna().astype(str).str.strip().tolist())
    except Exception:
        pass

stop_manual = {
    'nya', 'sih', 'tuh', 'dong', 'deh', 'loh', 'kan', 'kok', 'lah', 'buat',
    'nder', 'rep', 'twt', 'aja', 'saja', 'ya', 'yang', 'pas', 'mah'
}
stop_words_set.update(stop_manual)

# Context-Aware: Pertahankan kata negasi penting
kata_negasi = {'tidak', 'bukan', 'belum', 'jangan', 'kurang'}
stop_words_final = stop_words_set - kata_negasi

# C. Inisialisasi Stemmer Sastrawi
factory = StemmerFactory()
stemmer = factory.create_stemmer()


# --- 2. FUNGSI PEMBANTU ---
def clean_text(content):
    if pd.isna(content) or not str(content).strip():
        return ""

    content = str(content)
    # 1. Hapus RT khas Twitter
    content = re.sub(r'^rt\s+@\w+:', ' ', content, flags=re.IGNORECASE)
    content = re.sub(r'\brt\b', ' ', content, flags=re.IGNORECASE)
    # 2. Hapus URL / Link
    content = re.sub(r"http\S+", "", content)
    # 3. Hapus Mention (@username)
    content = re.sub(r"@\w+", "", content)
    # 4. Hapus Emoji & Spesial Karakter (simpan huruf, angka & spasi)
    content = re.sub(r"[^a-zA-Z0-9\s]", "", content)
    # 5. Case folding & hapus spasi berlebih
    return re.sub(r"\s+", " ", content.lower()).strip()


def eksekusi_normalisasi(list_kata):
    if not isinstance(list_kata, list):
        return []

    kata_normal = []
    for kata in list_kata:
        # Reduksi karakter berulang (misal: "nderrrr" -> "nder")
        teks_bersih = re.sub(r'(.)\1{2,}', r'\1', str(kata))
        # Ganti dengan kata formal dari kamus jika ada
        kata_akhir = kamus_slang.get(teks_bersih, teks_bersih)
        kata_normal.append(kata_akhir)

    return kata_normal


def hapus_stopword(list_kata):
    if not isinstance(list_kata, list):
        return []
    return [kata for kata in list_kata if kata not in stop_words_final and len(kata) > 1]


# --- 3. PIPELINE UTAMA EXECUTOR ---
def jalankan_pipeline(df, kolom_target='full_text', min_kata=3):
    if df is None or df.empty or kolom_target not in df.columns:
        return df

    df_proses = df.copy()

    # 1. Hapus Tweet Duplikat
    df_proses = df_proses.drop_duplicates(subset=[kolom_target], keep='first').reset_index(drop=True)

    # 2. Cleaning & Case Folding
    df_proses['clean_text'] = df_proses[kolom_target].apply(clean_text)

    # 3. Tokenisasi dasar & Normalisasi Kata
    df_proses['tokenized'] = df_proses['clean_text'].apply(lambda x: x.split())
    df_proses['normalized'] = df_proses['tokenized'].apply(eksekusi_normalisasi)

    # 4. Stopword Removal
    df_proses['stopword_removed'] = df_proses['normalized'].apply(hapus_stopword)

    # 5. Fast Stemming (Optimasi Kata Unik)
    term_dict = {}
    for doc in df_proses['stopword_removed']:
        for term in doc:
            if term not in term_dict:
                term_dict[term] = ""

    # Stemming hanya dilakukan pada kata unik
    for term in term_dict:
        term_dict[term] = stemmer.stem(term)

    # Mapping kembali kata hasil stemming ke dokumen
    df_proses['stemmed_list'] = df_proses['stopword_removed'].apply(
        lambda doc: [term_dict[term] for term in doc if term in term_dict]
    )

    # 6. Gabungkan token jadi teks utuh & Filter Minimum Kata
    df_proses['final_text'] = df_proses['stemmed_list'].apply(lambda x: " ".join(x))
    df_proses['word_count'] = df_proses['final_text'].apply(lambda x: len(x.split()))
    
    df_hasil = df_proses[df_proses['word_count'] >= min_kata].copy()

    # Rapikan kolom sementara jika perlu
    df_hasil = df_hasil.drop(columns=['clean_text', 'tokenized', 'normalized', 'stopword_removed', 'stemmed_list', 'word_count'])

    return df_hasil

--- test.py ---

import pandas as pd
from cleaner import bersihkan

df = pd.read_csv("tweets-data/freya.csv")
print("SEBELUM:", df.shape)

df_bersih = bersihkan(
    df,
    kolom_penting=["full_text"],   # ← hanya full_text, bukan id_str
    kolom_kunci="id_str",
    kolom_teks="full_text",
    min_kata=3                     # ← 3 KATA, bukan 3 karakter
)
print("SETELAH:", df_bersih.shape)

# Simpan
df_bersih.to_csv("tweets-data/freya_bersih.csv", index=False)
print("Disimpan.")