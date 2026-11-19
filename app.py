# Import
import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import ast
import time

from datetime import datetime
from nltk.util import ngrams
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import pipeline
from sqlalchemy import create_engine, inspect, text

from crawler import crawl_x
from cleaner import bersihkan, filter_bahasa
from preprocessing.pipeline import jalankan_pipeline, clean_text

# Head of Pages
st.set_page_config(
    page_title="Deteksi Trending Topik",
    page_icon="📑",
    layout="wide"
)

DB_CONNECTION_STR = 'mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending'

@st.cache_resource
def get_engine():
    return create_engine(DB_CONNECTION_STR)


def get_next_time_slot(engine):
    """Mencari time_slot tertinggi dari raw_data_tweet & preprocessing_data_tweet, lalu +1."""
    max_slots = [0]
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        for tbl in ["raw_data_tweet", "preprocessing_data_tweet"]:
            if tbl in tables:
                try:
                    df_max = pd.read_sql(f"SELECT MAX(time_slot) as max_slot FROM {tbl}", con=engine)
                    val = df_max['max_slot'].iloc[0]
                    if not pd.isna(val):
                        max_slots.append(int(val))
                except Exception:
                    pass
    except Exception:
        pass

    return max(max_slots) + 1


# ==============================================================================
# 1. LOAD MODEL HUGGING FACE (LAZY & CACHED)
# ==============================================================================
@st.cache_resource
def load_ner_model():
    return pipeline("ner", model="cahya/bert-base-indonesian-NER", aggregation_strategy="simple")

@st.cache_resource
def load_sentiment_model():
    return pipeline("sentiment-analysis", model="mdhugol/indonesia-bert-sentiment-classification")


# ==============================================================================
# HALAMAN 1: CRAWLING
# ==============================================================================
def halaman_crawling():
    st.title("🔎 Crawling")
    st.markdown("This page is for retrieving data from X")

    with st.form("form_crawl", border=False):
        input_keywords = st.text_area(
            "Input Keyword", 
            placeholder="ex: prabowo, kopdes, ihsg",
            help="You can enter more than one keyword. Separate each keyword with a comma (,)"
        )

        filename = st.text_input(
            "Filename (For Local CSV Backup)",
            placeholder="ex fiony_alveria",
            help="The data will be saved in the 'raw_data_tweet' table. This is only for naming the .csv file."
        )

        col1, col2 = st.columns(2)
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
        
    engine = get_engine()
    # Counter otomatis sinkron dengan raw_data_tweet maupun upload CSV di preprocessing
    current_counter = get_next_time_slot(engine) - 1

    st.write("")

    col_counter, col_hapus = st.columns([5, 1])

    with col_counter:
        st.write(f"**Counter:** {current_counter}")

    with col_hapus:
        if st.button("🗑️ Delete Data", type="secondary", use_container_width=True, key="btn_hapus_crawl"):
            try:
                with engine.begin() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS raw_data_tweet"))
                st.success("✅ All 'raw_data_tweet' data has been successfully deleted!")
                time.sleep(2) 
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to delete data: {e}")
    
    if submitted:
        if not input_keywords.strip():
            st.error("⚠️ Keyword cannot be empty!")
            return
        
        if not filename.strip():
            st.error("⚠️ Filename cannot be empty! Please enter the filename (without .csv).")
            return
        
        since_str = since.strftime("%Y-%m-%d")
        until_str = until.strftime("%Y-%m-%d")
        
        with st.spinner("Crawling in progress, please wait..."):
            sukses, pesan = crawl_x(
                input_keywords=input_keywords,
                since=since_str,
                until=until_str,
                filename=filename,
                limit=limit
            )
        
        if sukses:
            path = f"tweets-data/{filename}.csv"
            if os.path.exists(path):
                df = pd.read_csv(path)
                st.caption(f"File: {filename} ({len(df)} baris)")
                st.success(f"💾 Saved Locally: {path}")

                try:
                    # Otomatis melanjutkan urutan time_slot terakhir (baik dari crawl maupun upload CSV)
                    time_slot_otomatis = get_next_time_slot(engine)

                    df.insert(0, 'time_slot', time_slot_otomatis)
                    waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df.insert(1, 'waktu_crawl', waktu_sekarang)

                    df.to_sql(name='raw_data_tweet', con=engine, if_exists='append', index=False)
                    st.success(f"✅ The data has been inserted into the 'raw_data_tweet' table (Time Slot {time_slot_otomatis}) and has been saved locally!")
                except Exception as e:
                    st.error(f"❌ Failed to connect to the database: {e}")

                with st.expander("preview of file"):
                    st.dataframe(df.head(10))

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
            st.error(f"❌ Crawling process failed: {pesan}")


# ==============================================================================
# HALAMAN 2: CLEANING & PREPROCESSING
# ==============================================================================
def halaman_cleaning_preprocessing():
    st.title("🧹 Cleaning & Preprocessing")
    st.markdown("This page is for cleaning and preprocessing (normalization & stemming) data from X.")
    st.write("")

    # --- 1. INISIALISASI DATABASE GLOBAL ---
    engine = None
    inspector = None
    try:
        engine = get_engine()
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
    is_upload_csv = False
    auto_slot_upload = 1

    if "raw_data_tweet" in sumber_data:
        if inspector and "raw_data_tweet" in inspector.get_table_names():
            try:
                df_raw = pd.read_sql_table("raw_data_tweet", con=engine)
                st.success(f"📦 Successfully loaded the 'raw_data_tweet' table ({len(df_raw)} rows).")
            except Exception as e:
                st.error(f"❌ Failed to load table: {e}")
        else:
            st.warning("⚠️ The 'raw_data_tweet' table has not been found. Please perform Crawling first or upload a CSV file.")
            
    elif "Upload" in sumber_data:
        is_upload_csv = True
        uploaded_file = st.file_uploader("Upload Your CSV File", type=['csv'])
        if uploaded_file is not None:
            try:
                df_raw = pd.read_csv(uploaded_file)
                auto_slot_upload = get_next_time_slot(engine) if engine else 1

                # Pasang time_slot otomatis secara berurutan
                if 'time_slot' in df_raw.columns:
                    df_raw['time_slot'] = auto_slot_upload
                else:
                    df_raw.insert(0, 'time_slot', auto_slot_upload)

                if 'waktu_crawl' not in df_raw.columns:
                    df_raw.insert(1, 'waktu_crawl', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                st.success(f"📦 CSV file '{uploaded_file.name}' loaded ({len(df_raw)} rows) — Auto-assigned to **Time Slot {auto_slot_upload}**.")
            except Exception as e:
                st.error(f"❌ Failed to read the CSV file: {e}")
        else:
            st.info("Please upload a CSV file to continue.")

    # --- 3. PREVIEW & EKSEKUSI ---
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

        if st.button("🧹 Clean & Preprocess", type="primary"):
            with st.spinner("Cleaning, Tokenizing, Stemming in progress, please wait..."):
                start_time = time.time()
                
                kolom_teks_target = "full_text" if "full_text" in df_raw.columns else df_raw.columns[0]
                df_hasil = jalankan_pipeline(df=df_raw, kolom_target=kolom_teks_target, min_kata=min_kata)
                
                if 'stemmed' in df_hasil.columns:
                    df_hasil['final_text'] = df_hasil['stemmed'].apply(lambda x: " ".join(x) if isinstance(x, list) else x)
                if 'clean_text' not in df_hasil.columns:
                    df_hasil['clean_text'] = df_hasil[kolom_teks_target].apply(clean_text)

                end_time = time.time()

            st.subheader("📈 Filtering & Cleaning Results")
            col_met1, col_met2, col_met3 = st.columns(3)
            with col_met1:
                st.metric("Before", len(df_raw))
            with col_met2:
                st.metric("After", len(df_hasil))
            with col_met3:
                st.metric("Discarded (Word & Language Filter)", len(df_raw) - len(df_hasil))
            
            st.success(f"✅ Cleaning, Tokenizing, Stemming completed in {round(end_time - start_time, 2)} seconds!")

            # --- SIMPAN KE DATABASE ---
            df_sql = df_hasil.copy()
            for col in df_sql.columns:
                df_sql[col] = df_sql[col].apply(lambda x: str(x) if isinstance(x, list) else x)

            if engine:
                try:
                    inspector_now = inspect(engine)
                    if is_upload_csv:
                        # Mode Upload CSV: tambahkan sebagai time_slot baru (append)
                        if "preprocessing_data_tweet" in inspector_now.get_table_names():
                            kolom_db = {c["name"] for c in inspector_now.get_columns("preprocessing_data_tweet")}
                            if not set(df_sql.columns).issubset(kolom_db):
                                df_sql.to_sql(name='preprocessing_data_tweet', con=engine, if_exists='replace', index=False)
                            else:
                                df_sql.to_sql(name='preprocessing_data_tweet', con=engine, if_exists='append', index=False)
                        else:
                            df_sql.to_sql(name='preprocessing_data_tweet', con=engine, if_exists='replace', index=False)

                        st.success(f"✅ Data uploaded & saved into 'preprocessing_data_tweet' as **Time Slot {auto_slot_upload}**!")
                    else:
                        # Mode dari tabel raw_data_tweet: proses seluruh time_slot dari raw_data_tweet
                        df_sql.to_sql(name='preprocessing_data_tweet', con=engine, if_exists='replace', index=False)
                        st.success("✅ All data from 'raw_data_tweet' has been processed and saved into 'preprocessing_data_tweet'!")
                except Exception as e:
                    st.error(f"❌ Failed to connect to the database: {e}")

            if filename_backup.strip():
                nama_aman_csv = filename_backup.replace(" ", "_").lower()
                os.makedirs("processed-data", exist_ok=True)
                path_output = f"processed-data/{nama_aman_csv}.csv"
                df_hasil.to_csv(path_output, index=False)
                st.success(f"💾 Saved Locally: {path_output}")

            st.subheader("📋 Final Result Preview")
            kolom_tampil = ["time_slot", "waktu_crawl", kolom_teks_target, "clean_text", "final_text"]
            kolom_ada = [k for k in kolom_tampil if k in df_hasil.columns]
            st.dataframe(df_hasil[kolom_ada].head(10))

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
    # BLOK COUNTER & TOMBOL HAPUS DATA
    # ==========================================================
    st.write("---")
    count_prep = 0
    total_slot_prep = 0
    if engine and inspector:
        try:
            if "preprocessing_data_tweet" in inspector.get_table_names():
                query_prep = "SELECT COUNT(*) as jml_prep, COUNT(DISTINCT time_slot) as jml_slot FROM preprocessing_data_tweet"
                df_prep_count = pd.read_sql(query_prep, con=engine)
                count_prep = int(df_prep_count['jml_prep'].iloc[0])
                total_slot_prep = int(df_prep_count['jml_slot'].iloc[0])
        except Exception:
            pass

    col_counter, col_hapus = st.columns([5, 1])

    with col_counter:
        st.write(f"**Status Database:** `{count_prep}` baris data (`{total_slot_prep}` Time Slot) tersimpan di tabel 'preprocessing_data_tweet'")

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
# 2. FUNGSI PEMBANTU BN-GRAMS & NER
# ==============================================================================
def buat_ngrams(teks, n):
    if not isinstance(teks, str) or not teks.strip():
        return []
    tokens = teks.split()
    if len(tokens) < n:
        return []
    return [" ".join(gram) for gram in ngrams(tokens, n)]

def deteksi_ner_dan_boost(teks, ner_pipe):
    if not isinstance(teks, str) or not teks.strip() or ner_pipe is None:
        return [], [], 1.0
    
    try:
        hasil = ner_pipe(teks[:512])
    except Exception:
        return [], [], 1.0
        
    entitas = []
    entitas_tokens = set()
    boost_val = 1.0
    
    for ent in hasil:
        label = ent.get('entity_group', '')
        word = ent.get('word', '')
        
        if label in ['PER', 'LOC', 'ORG']:
            word_bersih = word.replace('##', '').strip()
            if len(word_bersih) > 1 and word_bersih != "@": 
                entitas.append(f"{word_bersih} ({label})")
                for tok in word_bersih.lower().split():
                    entitas_tokens.add(tok)
                boost_val = 1.5 
            
    entitas_unik = list(set(entitas))
    return entitas_unik, list(entitas_tokens), boost_val


# ==============================================================================
# HALAMAN 3: BN-GRAMS & NER
# ==============================================================================
def halaman_bngram():
    st.title("📊 Ekstraksi BN-Grams & NER (Hugging Face)")
    st.markdown("This page is for extracting Bigrams & Trigrams, as well as detecting NER using Hugging Face to determine the Boost Value (1.5).")
    st.write("")

    engine = None
    inspector = None
    try:
        engine = get_engine()
        inspector = inspect(engine)
    except Exception as e:
        st.error(f"❌ Failed to connect to the database: {e}")

    sumber_data = st.radio(
        "📁 Select the data source you want to process:", 
        ["🗄️ Use 'preprocessing_data_tweet' table", "📄 Upload CSV File"],
        horizontal=True
    )
    
    df_prep = None

    if "table" in sumber_data:
        if inspector and "preprocessing_data_tweet" in inspector.get_table_names():
            try:
                df_prep = pd.read_sql_table("preprocessing_data_tweet", con=engine)
                st.success(f"📦 Successfully loaded clean data from 'preprocessing_data_tweet' ({len(df_prep)} rows).")
            except Exception as e:
                st.error(f"❌ Failed to load table: {e}")
        else:
            st.warning("⚠️ The 'preprocessing_data_tweet' table has not been found. Please perform Preprocessing first.")
            
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

    if df_prep is not None and not df_prep.empty:
        with st.expander("View Loaded Data Preview"):
            st.dataframe(df_prep.head(10))

        st.write("---")

        if st.button("🧮 BN-Grams & NER Extraction", type="primary"):
            kolom_teks = 'final_text' if 'final_text' in df_prep.columns else (
                         'full_text' if 'full_text' in df_prep.columns else None)
            
            if not kolom_teks:
                st.error("❌ No processable text column found (final_text / full_text).")
            elif 'full_text' not in df_prep.columns or 'final_text' not in df_prep.columns:
                st.error("The data must have a 'full_text' column (for NER) and a 'final_text' column (for n-grams). Pastikan CSV/tabel lu sesuai.")
            else:
                with st.spinner("Loading IndoBERT NER & extracting Bigrams, Trigrams in progress, please wait..."):
                    ner_pipe = load_ner_model()
                    df_bngram = df_prep.copy()

                    # Gunakan clean_text jika tersedia agar @mention & URL tidak ikut terbaca sebagai entitas NER
                    if 'clean_text' not in df_bngram.columns:
                        df_bngram['clean_text'] = df_bngram['full_text'].apply(clean_text)

                    df_bngram['bigrams'] = df_bngram['final_text'].apply(lambda x: buat_ngrams(str(x), 2))
                    df_bngram['trigrams'] = df_bngram['final_text'].apply(lambda x: buat_ngrams(str(x), 3))

                    hasil_ner = df_bngram['clean_text'].apply(lambda x: deteksi_ner_dan_boost(str(x), ner_pipe))
                    df_bngram['ner_tags'] = hasil_ner.apply(lambda x: x[0])
                    df_bngram['ner_tokens'] = hasil_ner.apply(lambda x: x[1])
                    df_bngram['boost_value'] = hasil_ner.apply(lambda x: x[2])

                st.success("✅ BN-Grams and NER extraction successful!")

                df_sql = df_bngram.copy()
                for col in df_sql.columns:
                    df_sql[col] = df_sql[col].apply(lambda x: str(x) if isinstance(x, list) else x)

                try:
                    df_sql.to_sql(name='bngrams_data_tweet', con=engine, if_exists='replace', index=False)
                    st.success("✅ The data has been inserted into the 'bngrams_data_tweet' table!")
                except Exception as e:
                    st.error(f"❌ Failed to save data to database: {e}")

                st.subheader("📋 Final Result Preview")
                kolom_tampil = [kolom_teks, 'bigrams', 'trigrams', 'ner_tags', 'boost_value']
                kolom_ada = [k for k in kolom_tampil if k in df_bngram.columns]
                st.dataframe(df_bngram[kolom_ada].head(15))
                
                csv_string = df_sql.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV BN-Grams",
                    data=csv_string,
                    file_name="hasil_bngrams_ner.csv",
                    mime="text/csv"
                )

    # ==========================================================
    # BLOK COUNTER & TOMBOL HAPUS DATA
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


# ==============================================================================
# HALAMAN 4: PERANGKINGAN (DF-IDFt + NER BOOST + TF-IDF)
# ==============================================================================
def halaman_perangkingan():
    st.title("🏆 Perangkingan Topic (BN-Grams & TF-IDF)")
    st.markdown("This page calculates Document Frequency (DF), TF-IDF weights, and the final DF-IDFt + NER Boost score to find the Top Trending Topic.")
    
    try:
        engine = get_engine()
    except Exception as e:
        st.error(f"❌ Failed to connect to the database: {e}")
        return

    count_rank = 0
    try:
        query_count = "SELECT COUNT(*) as jml FROM perangkingan_data_tweet"
        df_count = pd.read_sql(query_count, con=engine)
        count_rank = int(df_count['jml'].iloc[0])
    except Exception:
        count_rank = 0

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
    
    st.subheader("⚙️ Parameter Settings")
    col_p1, col_p2 = st.columns(2)
    list_slot = sorted(df_bngram['time_slot'].unique())

    with col_p1:
        target_slot = st.selectbox(
            "Select Target Time Slot (Time Slot ke-i):", 
            list_slot, 
            index=len(list_slot)-1,
            help="The current time slot for which you want to find the trending topics."
        )
    with col_p2:
        metode_urut = st.selectbox(
            "Sort Ranking By:",
            ["Skor Trending (DF-IDFt + NER)", "Skor TF-IDF (Total Weight)"],
            help="Compare trending burst score (DF-IDFt) with standard TF-IDF weighting."
        )
    
    if st.button("🧮 Calculate DF-IDFt & TF-IDF Ranking", type="primary"):
        with st.spinner("Splitting N-Grams, computing TF-IDF, and executing the DF-IDFt formula..."):
            
            df_calc = df_bngram.copy()
            df_calc['bigrams'] = df_calc['bigrams'].apply(konversi_string_ke_list)
            df_calc['trigrams'] = df_calc['trigrams'].apply(konversi_string_ke_list)
            
            # Kompatibel dengan tabel lama maupun tabel baru yang sudah punya kolom 'ner_tokens'
            if 'ner_tokens' in df_calc.columns:
                df_calc['ner_tokens'] = df_calc['ner_tokens'].apply(konversi_string_ke_list)
            else:
                df_calc['ner_tokens'] = [[] for _ in range(len(df_calc))]

            df_calc['all_ngrams'] = df_calc['bigrams'] + df_calc['trigrams']
            df_calc['doc_id'] = df_calc.index 
            
            df_exploded = df_calc[['doc_id', 'time_slot', 'all_ngrams', 'ner_tokens', 'boost_value']].explode('all_ngrams')
            df_exploded = df_exploded.dropna(subset=['all_ngrams'])
            df_exploded = df_exploded[df_exploded['all_ngrams'].str.strip() != ""] 

            # Hitung NER Boost PER N-GRAM (1.5 hanya jika N-gram mengandung entitas NER)
            def cek_boost_ngram(row):
                if len(row['ner_tokens']) > 0:
                    kata_ngram = set(str(row['all_ngrams']).lower().split())
                    return 1.5 if len(kata_ngram.intersection(set(row['ner_tokens']))) > 0 else 1.0
                return float(row['boost_value'])

            df_exploded['ngram_boost'] = df_exploded.apply(cek_boost_ngram, axis=1)
            
            # Perbaikan rumus t: jumlah time slot historis sebelum target_slot
            slot_sebelumnya = [s for s in list_slot if s < target_slot]
            t = len(slot_sebelumnya) if len(slot_sebelumnya) > 0 else 1
            
            df_target = df_exploded[df_exploded['time_slot'] == target_slot]
            df_i_counts = df_target.groupby('all_ngrams')['doc_id'].nunique().reset_index(name='df_i')
            boost_df = df_target.groupby('all_ngrams')['ngram_boost'].max().reset_index(name='boost')
            
            df_prev = df_exploded[df_exploded['time_slot'] < target_slot]
            if not df_prev.empty:
                df_prev_counts = df_prev.groupby('all_ngrams')['doc_id'].nunique().reset_index(name='sum_df_prev')
            else:
                df_prev_counts = pd.DataFrame(columns=['all_ngrams', 'sum_df_prev'])

            # --- PERHITUNGAN TF-IDF PADA SLOT TERPILIH ---
            df_slot_docs = df_calc[df_calc['time_slot'] == target_slot]
            docs_tfidf = df_slot_docs['final_text'].fillna('').tolist() if 'final_text' in df_slot_docs.columns else []
            df_tfidf_info = pd.DataFrame(columns=['all_ngrams', 'idf_tfidf', 'skor_tfidf'])
            df_matriks_tfidf = None

            if len(docs_tfidf) >= 2:
                try:
                    vec_tfidf = TfidfVectorizer(ngram_range=(2, 3))
                    mat_tfidf = vec_tfidf.fit_transform(docs_tfidf)
                    fitur_tfidf = vec_tfidf.get_feature_names_out()
                    df_tfidf_info = pd.DataFrame({
                        'all_ngrams': fitur_tfidf,
                        'idf_tfidf': vec_tfidf.idf_,
                        'skor_tfidf': np.asarray(mat_tfidf.sum(axis=0)).ravel()
                    })
                    df_matriks_tfidf = pd.DataFrame(
                        mat_tfidf.toarray(),
                        columns=fitur_tfidf,
                        index=[f"Doc {i+1}" for i in range(len(docs_tfidf))]
                    )
                except ValueError:
                    pass
                
            hasil_df = pd.merge(df_i_counts, boost_df, on='all_ngrams', how='left')
            hasil_df = pd.merge(hasil_df, df_prev_counts, on='all_ngrams', how='left')
            hasil_df = pd.merge(hasil_df, df_tfidf_info, on='all_ngrams', how='left')
            hasil_df['sum_df_prev'] = hasil_df['sum_df_prev'].fillna(0)
            hasil_df['idf_tfidf'] = hasil_df['idf_tfidf'].fillna(0)
            hasil_df['skor_tfidf'] = hasil_df['skor_tfidf'].fillna(0)
            
            def hitung_dfidft(row):
                df_i = row['df_i']
                sum_df_prev = row['sum_df_prev']
                boost_val = row['boost']
                
                pembilang = df_i + 1
                penyebut = np.log10((sum_df_prev / t) + 1) + 1 
                return (pembilang / penyebut) * float(boost_val)
                
            hasil_df['skor_dfidft'] = hasil_df.apply(hitung_dfidft, axis=1)
            
            kolom_sort = 'skor_dfidft' if "DF-IDFt" in metode_urut else 'skor_tfidf'
            hasil_df = hasil_df.sort_values(by=kolom_sort, ascending=False).reset_index(drop=True)
            hasil_df.index = hasil_df.index + 1
            hasil_df.index.name = 'Rank'

            try:
                hasil_df_sql = hasil_df.reset_index()
                hasil_df_sql['time_slot'] = target_slot 
                hasil_df_sql.to_sql(name='perangkingan_data_tweet', con=engine, if_exists='replace', index=False)
                st.success("✅ The data has been inserted into the 'perangkingan_data_tweet' table!")
            except Exception as e:
                st.error(f"❌ Failed to save data to database: {e}")
        
        st.subheader(f"📈 Top Trending Topics (Time Slot {target_slot})")
        st.dataframe(
            hasil_df.style.format({
                'boost': '{:.1f}',
                'idf_tfidf': '{:.4f}',
                'skor_tfidf': '{:.4f}',
                'skor_dfidft': '{:.4f}'
            }),
            use_container_width=True
        )

        if df_matriks_tfidf is not None:
            with st.expander("🔢 View TF-IDF Document-Term Matrix (Top 15 N-Grams)"):
                top_15_cols = [c for c in hasil_df['all_ngrams'].head(15) if c in df_matriks_tfidf.columns]
                if top_15_cols:
                    st.dataframe(df_matriks_tfidf[top_15_cols].round(4), use_container_width=True)
        
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
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM perangkingan_data_tweet"))
                st.success("✅ All 'perangkingan_data_tweet' data has been successfully deleted!")
                time.sleep(2) 
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to delete data: {e}")


# ==============================================================================
# HALAMAN 5: ANALISIS SENTIMEN (INDOBERT)
# ==============================================================================
def halaman_sentimen():
    st.title("💬 Analisis Sentimen Opini Publik")
    st.markdown("This page classifies public sentiment (Positive, Neutral, Negative) toward tweets or specific trending topics.")

    engine = None
    inspector = None
    try:
        engine = get_engine()
        inspector = inspect(engine)
    except Exception as e:
        st.error(f"❌ Failed to connect to the database: {e}")

    count_sent = 0
    if inspector and "sentiment_data_tweet" in inspector.get_table_names():
        try:
            df_count = pd.read_sql("SELECT COUNT(*) as jml FROM sentiment_data_tweet", con=engine)
            count_sent = int(df_count['jml'].iloc[0])
        except Exception:
            count_sent = 0

    st.write("---")
    sumber_data = st.radio(
        "📁 Select the data source you want to process:", 
        ["🗄️ Use 'bngrams_data_tweet' table", "📄 Upload CSV File"],
        horizontal=True,
        key="radio_sumber_sentimen"
    )

    df_sumber = None
    if "table" in sumber_data:
        if inspector and "bngrams_data_tweet" in inspector.get_table_names():
            try:
                df_sumber = pd.read_sql_table("bngrams_data_tweet", con=engine)
                st.success(f"📦 Successfully loaded {len(df_sumber)} data rows from 'bngrams_data_tweet'.")
            except Exception as e:
                st.error(f"❌ Failed to load table: {e}")
        else:
            st.warning("⚠️ Tabel 'bngrams_data_tweet' belum tersedia. Jalankan tahapan BN-Grams terlebih dahulu.")
    else:
        uploaded_file = st.file_uploader("Upload CSV file for sentiment analysis", type=['csv'], key="upload_sentimen")
        if uploaded_file is not None:
            df_sumber = pd.read_csv(uploaded_file)
            st.success(f"📦 Successfully loaded '{uploaded_file.name}' ({len(df_sumber)} rows).")

    if df_sumber is not None and not df_sumber.empty:
        st.write("---")
        st.subheader("⚙️ Filter & Parameter Settings")
        col_f1, col_f2 = st.columns(2)

        if 'time_slot' not in df_sumber.columns:
            df_sumber['time_slot'] = 1

        list_slot = sorted(df_sumber['time_slot'].unique())
        with col_f1:
            pilih_slot = st.selectbox("Select Target Time Slot:", list_slot, index=len(list_slot)-1, key="slot_sentimen")
        with col_f2:
            filter_topik = st.text_input(
                "Filter by Trending Topic / Keyword (Optional):",
                placeholder="ex: kebakaran hutan (leave blank for all tweets in this slot)"
            )

        df_target = df_sumber[df_sumber['time_slot'] == pilih_slot].copy()
        if filter_topik.strip():
            kw = filter_topik.strip().lower()
            kolom_cari = 'final_text' if 'final_text' in df_target.columns else 'full_text'
            df_target = df_target[df_target[kolom_cari].astype(str).str.lower().str.contains(kw, na=False)]

        st.caption(f"Total tweets ready for sentiment analysis: **{len(df_target)}** rows")

        if not df_target.empty and st.button("🧠 Run Sentiment Analysis", type="primary"):
            with st.spinner("Analyzing sentiment using IndoBERT, please wait..."):
                sent_pipe = load_sentiment_model()
                label_map = {"LABEL_0": "Positif", "LABEL_1": "Netral", "LABEL_2": "Negatif"}

                kolom_teks_sent = 'clean_text' if 'clean_text' in df_target.columns else 'full_text'
                hasil_label = []
                hasil_skor = []

                for teks in df_target[kolom_teks_sent].fillna(""):
                    teks_input = clean_text(str(teks))[:512]
                    if not teks_input.strip():
                        hasil_label.append("Netral")
                        hasil_skor.append(0.0)
                        continue
                    pred = sent_pipe(teks_input)[0]
                    hasil_label.append(label_map.get(pred['label'], pred['label']))
                    hasil_skor.append(round(float(pred['score']), 4))

                df_target['sentiment'] = hasil_label
                df_target['confidence'] = hasil_skor

                if engine:
                    try:
                        df_sql = df_target.copy()
                        for col in df_sql.columns:
                            df_sql[col] = df_sql[col].apply(lambda x: str(x) if isinstance(x, list) else x)
                        df_sql.to_sql(name='sentiment_data_tweet', con=engine, if_exists='replace', index=False)
                        st.success("✅ Sentiment results have been saved to the 'sentiment_data_tweet' table!")
                    except Exception as e:
                        st.error(f"❌ Failed to save data to database: {e}")

            st.subheader("📊 Sentiment Distribution")
            col_m1, col_m2, col_m3 = st.columns(3)
            jml_pos = int((df_target['sentiment'] == 'Positif').sum())
            jml_net = int((df_target['sentiment'] == 'Netral').sum())
            jml_neg = int((df_target['sentiment'] == 'Negatif').sum())

            with col_m1:
                st.metric("😊 Positif", jml_pos)
            with col_m2:
                st.metric("😐 Netral", jml_net)
            with col_m3:
                st.metric("😠 Negatif", jml_neg)

            st.bar_chart(df_target['sentiment'].value_counts())

            st.subheader("📋 Sentiment Classification Preview")
            kolom_tampil = [c for c in ['time_slot', 'full_text', 'final_text', 'sentiment', 'confidence'] if c in df_target.columns]
            st.dataframe(df_target[kolom_tampil].head(20), use_container_width=True)

            csv_sent = df_target[kolom_tampil].to_csv(index=False)
            st.download_button(
                label="📥 Download CSV Sentiment",
                data=csv_sent,
                file_name=f"sentiment_slot_{pilih_slot}.csv",
                mime="text/csv"
            )

    # ==========================================================
    # BLOK COUNTER & TOMBOL HAPUS DATA SENTIMEN
    # ==========================================================
    st.write("---")
    col_counter, col_hapus = st.columns([5, 1])
    with col_counter:
        st.write(f"**Status Database:** `{count_sent}` baris hasil sentimen tersimpan di tabel 'sentiment_data_tweet'")

    with col_hapus:
        if st.button("🗑️ Delete Data", type="secondary", use_container_width=True, key="btn_hapus_sentimen"):
            if engine:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM sentiment_data_tweet"))
                    st.success("✅ All 'sentiment_data_tweet' data has been successfully deleted!")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to delete data: {e}")
            else:
                st.error("❌ Database connection is not available.")


# Sidebar + Navigation
st.sidebar.title("Navigation")

menu = st.sidebar.radio(
    "Select page:",
    ["Crawling", "Preprocessing", "BN-Grams", "Ranking", "Sentiment"]
)

if menu == "Crawling":
    halaman_crawling()
elif menu == "Preprocessing":
    halaman_cleaning_preprocessing()
elif menu == "BN-Grams":
    halaman_bngram()
elif menu == "Ranking":
    halaman_perangkingan()
elif menu == "Sentiment":
    halaman_sentimen()