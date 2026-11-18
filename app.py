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