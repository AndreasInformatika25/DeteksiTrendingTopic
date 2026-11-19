import os
import json
import math
import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text, inspect
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from transformers import pipeline
from dotenv import load_dotenv

from crawler import crawl_x
from cleaner import bersihkan, filter_bahasa
from preprocessing.pipeline import jalankan_pipeline, clean_text

load_dotenv()

st.set_page_config(page_title="Deteksi Trending Topic & Sentimen X", layout="wide")


# --- KONEKSI DATABASE & AUTO-SCHEMA HANDLER ---
@st.cache_resource
def get_engine():
    db_url = os.getenv("DATABASE_URL", "mysql+pymysql://root:fiony@127.0.0.1:3306/deteksi_trending")
    return create_engine(db_url)


def simpan_per_slot(df, nama_tabel, time_slot):
    """Menyimpan data per time_slot. Jika skema kolom berubah, tabel otomatis diperbarui."""
    engine = get_engine()
    inspector = inspect(engine)

    if inspector.has_table(nama_tabel):
        kolom_db = {col["name"] for col in inspector.get_columns(nama_tabel)}
        kolom_df = set(df.columns)
        if not kolom_df.issubset(kolom_db):
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE {nama_tabel}"))
        else:
            with engine.begin() as conn:
                conn.execute(text(f"DELETE FROM {nama_tabel} WHERE time_slot = :slot"), {"slot": int(time_slot)})

    df.to_sql(nama_tabel, con=engine, if_exists="append", index=False)


# --- LOAD MODEL HUGGINGFACE ---
@st.cache_resource
def load_ner_model():
    return pipeline(
        "ner",
        model="cahya/bert-base-indonesian-NER",
        tokenizer="cahya/bert-base-indonesian-NER",
        aggregation_strategy="simple"
    )


@st.cache_resource
def load_sentiment_model():
    return pipeline(
        "sentiment-analysis",
        model="mdhugol/indonesia-bert-sentiment-classification",
        tokenizer="mdhugol/indonesia-bert-sentiment-classification"
    )


def ekstrak_entitas_ner(teks, ner_pipe):
    if not teks or not str(teks).strip():
        return [], []
    hasil = ner_pipe(str(teks)[:512])
    entitas_kata = set()
    label_ringkas = []
    for ent in hasil:
        grup = ent.get("entity_group", "")
        kata = ent.get("word", "").lower().strip()
        if grup in ["PER", "LOC", "ORG"] and len(kata) > 1:
            for token in kata.split():
                entitas_kata.add(token)
            label_ringkas.append(f"{kata} ({grup})")
    return list(entitas_kata), list(set(label_ringkas))


def ekstrak_ngrams_teks(teks, n_range):
    if not teks or len(str(teks).split()) < n_range[0]:
        return []
    try:
        vec = CountVectorizer(ngram_range=n_range)
        vec.fit([str(teks)])
        return list(vec.get_feature_names_out())
    except ValueError:
        return []


# ==========================================
# HALAMAN 1: CRAWLING DATA X
# ==========================================
def halaman_crawling():
    st.header("1. Crawling Data X (Twitter)")
    col1, col2 = st.columns(2)
    with col1:
        keywords = st.text_input("Keyword Pencarian (pisahkan koma jika > 1)", placeholder="Contoh: Fiony, JKT48")
        since = st.date_input("Dari Tanggal (Since)")
        time_slot = st.number_input("Time Slot (Urutan Jam/Sesi ke-)", min_value=1, value=1, step=1)
    with col2:
        filename = st.text_input("Nama File Output CSV", value="hasil_crawl.csv")
        until = st.date_input("Sampai Tanggal (Until)")
        limit = st.number_input("Limit Jumlah Tweet", min_value=10, max_value=2000, value=100, step=10)

    if st.button("Mulai Crawling", type="primary"):
        with st.spinner("Sedang mengambil data dari X..."):
            sukses, pesan = crawl_x(keywords, filename, str(since), str(until), limit)
            if sukses:
                st.success(pesan)
                path_csv = os.path.join("tweets-data", filename) if os.path.exists(os.path.join("tweets-data", filename)) else filename
                if os.path.exists(path_csv):
                    df_crawl = pd.read_csv(path_csv)
                    df_crawl["time_slot"] = int(time_slot)
                    simpan_per_slot(df_crawl, "raw_data_tweet", time_slot)
                    st.info(f"Berhasil menyimpan {len(df_crawl)} baris ke `raw_data_tweet` (Slot {time_slot}).")
                    st.dataframe(df_crawl.head(10))
            else:
                st.error(pesan)


# ==========================================
# HALAMAN 2: CLEANING & PREPROCESSING
# ==========================================
def halaman_preprocessing():
    st.header("2. Cleaning & Preprocessing Teks")
    engine = get_engine()

    sumber = st.radio("Pilih Sumber Data:", ["Dari Database (`raw_data_tweet`)", "Upload File CSV Manual"])
    df_raw = None

    if sumber == "Dari Database (`raw_data_tweet`)":
        try:
            slots = pd.read_sql("SELECT DISTINCT time_slot FROM raw_data_tweet ORDER BY time_slot", engine)["time_slot"].tolist()
            if slots:
                pilih_slot = st.selectbox("Pilih Time Slot yang akan diproses:", slots)
                df_raw = pd.read_sql(f"SELECT * FROM raw_data_tweet WHERE time_slot = {int(pilih_slot)}", engine)
            else:
                st.warning("Tabel `raw_data_tweet` masih kosong.")
        except Exception as e:
            st.error(f"Gagal membaca database: {e}")
    else:
        uploaded = st.file_uploader("Upload CSV Mentah", type=["csv"])
        slot_manual = st.number_input("Tentukan Time Slot untuk file ini:", min_value=1, value=1)
        if uploaded:
            df_raw = pd.read_csv(uploaded)
            df_raw["time_slot"] = int(slot_manual)

    if df_raw is not None and not df_raw.empty:
        st.write(f"Total data mentah: **{len(df_raw)}** baris")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            bahasa = st.selectbox("Filter Bahasa (`lang`):", ["in", "all", "en"])
        with col_f2:
            min_kata = st.slider("Minimum Jumlah Kata Bersih:", 1, 10, 3)

        if st.button("Jalankan Preprocessing", type="primary"):
            with st.spinner("Menjalankan cleaning, normalisasi slang, stopword removal, dan stemming..."):
                df_clean = df_raw.copy()
                if "lang" in df_clean.columns:
                    df_clean = filter_bahasa(df_clean, "lang", bahasa)
                kunci = "id_str" if "id_str" in df_clean.columns else "full_text"
                df_clean = bersihkan(df_clean, ["full_text"], kunci, "full_text", min_kata=1)
                df_hasil = jalankan_pipeline(df_clean, kolom_target="full_text", min_kata=min_kata)

                slot_aktif = int(df_hasil["time_slot"].iloc[0])
                simpan_per_slot(df_hasil, "preprocessing_data_tweet", slot_aktif)
                st.success(f"Selesai! Tersisa **{len(df_hasil)}** tweet bersih dan disimpan ke `preprocessing_data_tweet` (Slot {slot_aktif}).")
                st.dataframe(df_hasil[["time_slot", "full_text", "clean_text", "final_text"]].head(15))


# ==========================================
# HALAMAN 3: PEMBOBOTAN TF-IDF (TUGAS DOSEN)
# ==========================================
def halaman_tfidf():
    st.header("3. Pembobotan Kata & Frasa (TF-IDF)")
    engine = get_engine()

    try:
        slots = pd.read_sql("SELECT DISTINCT time_slot FROM preprocessing_data_tweet ORDER BY time_slot", engine)["time_slot"].tolist()
    except Exception:
        slots = []

    if not slots:
        st.warning("Belum ada data di `preprocessing_data_tweet`. Jalankan tahap 2 terlebih dahulu.")
        return

    col1, col2 = st.columns(2)
    with col1:
        pilih_slot = st.selectbox("Pilih Time Slot:", slots)
    with col2:
        opsi_ngram = st.selectbox(
            "Rentang N-Gram TF-IDF:",
            ["Unigram (1, 1)", "Bigram (2, 2)", "Trigram (3, 3)", "BN-Grams: Bigram + Trigram (2, 3)", "Semua (1, 3)"],
            index=3
        )

    ngram_map = {
        "Unigram (1, 1)": (1, 1),
        "Bigram (2, 2)": (2, 2),
        "Trigram (3, 3)": (3, 3),
        "BN-Grams: Bigram + Trigram (2, 3)": (2, 3),
        "Semua (1, 3)": (1, 3)
    }
    n_range = ngram_map[opsi_ngram]

    if st.button("Hitung & Simpan Bobot TF-IDF", type="primary"):
        df_prep = pd.read_sql(f"SELECT * FROM preprocessing_data_tweet WHERE time_slot = {int(pilih_slot)}", engine)
        docs = df_prep["final_text"].fillna("").tolist()

        if len(docs) < 2:
            st.warning("Minimal butuh 2 dokumen bersih untuk menghitung TF-IDF.")
            return

        # 1. Hitung TF-IDF menggunakan Scikit-Learn
        vectorizer = TfidfVectorizer(ngram_range=n_range)
        tfidf_matrix = vectorizer.fit_transform(docs)
        fitur = vectorizer.get_feature_names_out()

        # 2. Hitung komponen DF dan IDF secara eksplisit untuk transparansi perhitungan
        count_vec = CountVectorizer(ngram_range=n_range, binary=True)
        df_matrix = count_vec.fit_transform(docs)
        doc_freq = np.asarray(df_matrix.sum(axis=0)).ravel()
        total_docs = len(docs)

        df_ringkasan_tfidf = pd.DataFrame({
            "time_slot": int(pilih_slot),
            "term": fitur,
            "df": doc_freq,
            "idf": np.round(vectorizer.idf_, 4),
            "total_tfidf": np.round(np.asarray(tfidf_matrix.sum(axis=0)).ravel(), 4),
            "rata_rata_tfidf": np.round(np.asarray(tfidf_matrix.mean(axis=0)).ravel(), 4)
        }).sort_values(by="total_tfidf", ascending=False).reset_index(drop=True)

        simpan_per_slot(df_ringkasan_tfidf, "tfidf_data_tweet", pilih_slot)
        st.success(f"Perhitungan TF-IDF selesai untuk **{total_docs}** dokumen (Slot {pilih_slot}) dan disimpan ke tabel `tfidf_data_tweet`.")

        tab_rank, tab_matriks = st.tabs(["🏆 Peringkat Bobot TF-IDF", "🔢 Matriks TF-IDF per Dokumen"])
        with tab_rank:
            st.dataframe(df_ringkasan_tfidf, use_container_width=True)
            st.bar_chart(df_ringkasan_tfidf.head(15).set_index("term")["total_tfidf"])

        with tab_matriks:
            top_20_terms = df_ringkasan_tfidf["term"].head(20).tolist()
            idx_top = [list(fitur).index(t) for t in top_20_terms]
            df_mat = pd.DataFrame(
                tfidf_matrix[:, idx_top].toarray(),
                columns=top_20_terms,
                index=[f"Tweet {i+1}" for i in range(total_docs)]
            )
            st.caption("Menampilkan matriks bobot TF-IDF untuk 20 term teratas:")
            st.dataframe(df_mat.round(4), use_container_width=True)


# ==========================================
# HALAMAN 4: EKSTRAKSI BN-GRAMS & NER
# ==========================================
def halaman_bngram():
    st.header("4. Ekstraksi BN-Grams & Entity Recognition (NER)")
    engine = get_engine()

    try:
        slots = pd.read_sql("SELECT DISTINCT time_slot FROM preprocessing_data_tweet ORDER BY time_slot", engine)["time_slot"].tolist()
    except Exception:
        slots = []

    if not slots:
        st.warning("Belum ada data di `preprocessing_data_tweet`. Jalankan tahap 2 terlebih dahulu.")
        return

    pilih_slot = st.selectbox("Pilih Time Slot untuk Ekstraksi Fitur:", slots)
    if st.button("Proses BN-Grams & NER", type="primary"):
        df_prep = pd.read_sql(f"SELECT * FROM preprocessing_data_tweet WHERE time_slot = {int(pilih_slot)}", engine)
        if "clean_text" not in df_prep.columns:
            df_prep["clean_text"] = df_prep["full_text"].apply(clean_text)

        with st.spinner("Memuat IndoBERT NER & mengekstrak Bigram/Trigram..."):
            ner_pipe = load_ner_model()
            records = []

            for _, row in df_prep.iterrows():
                final_txt = str(row["final_text"])
                clean_txt = str(row["clean_text"])

                bigrams = ekstrak_ngrams_teks(final_txt, (2, 2))
                trigrams = ekstrak_ngrams_teks(final_txt, (3, 3))
                all_ngrams = bigrams + trigrams

                entitas_tokens, ner_labels = ekstrak_entitas_ner(clean_txt, ner_pipe)

                ngram_boost_map = {}
                for ng in all_ngrams:
                    kata_ng = set(ng.split())
                    ada_entitas = len(kata_ng.intersection(entitas_tokens)) > 0
                    ngram_boost_map[ng] = 1.5 if ada_entitas else 1.0

                records.append({
                    "time_slot": int(row["time_slot"]),
                    "full_text": row["full_text"],
                    "clean_text": clean_txt,
                    "final_text": final_txt,
                    "ner_tags": ", ".join(ner_labels) if ner_labels else "-",
                    "all_ngrams_json": json.dumps(all_ngrams),
                    "ngram_boost_json": json.dumps(ngram_boost_map)
                })

            df_bngram = pd.DataFrame(records)
            simpan_per_slot(df_bngram, "bngrams_data_tweet", pilih_slot)
            st.success(f"Ekstraksi BN-Grams & NER selesai untuk **{len(df_bngram)}** tweet (Slot {pilih_slot}).")
            st.dataframe(df_bngram[["clean_text", "final_text", "ner_tags"]].head(15))


# ==========================================
# HALAMAN 5: PERANGKINGAN TRENDING (DF-IDFt + TF-IDF)
# ==========================================
def halaman_perangkingan():
    st.header("5. Perangkingan Trending Topic")
    engine = get_engine()

    try:
        df_all = pd.read_sql("SELECT * FROM bngrams_data_tweet", engine)
    except Exception:
        st.warning("Tabel `bngrams_data_tweet` belum tersedia.")
        return

    if df_all.empty:
        st.warning("Data BN-Grams masih kosong.")
        return

    # Validasi skema baru
    if "ngram_boost_json" not in df_all.columns:
        st.error(
            "⚠️ Struktur tabel `bngrams_data_tweet` di database masih menggunakan versi lama. "
            "Silakan buka menu **4. Ekstraksi BN-Grams & NER** dan klik **Proses BN-Grams & NER** ulang agar struktur tabel diperbarui otomatis."
        )
        return

    list_slot = sorted(df_all["time_slot"].unique())
    col1, col2 = st.columns(2)
    with col1:
        target_slot = st.selectbox("Pilih Target Time Slot (i):", list_slot, index=len(list_slot) - 1)
    with col2:
        top_k = st.slider("Tampilkan Top-N Trending Topic:", 5, 30, 10)

    df_curr = df_all[df_all["time_slot"] == target_slot]
    df_prev = df_all[df_all["time_slot"] < target_slot]

    slot_sebelumnya = [s for s in list_slot if s < target_slot]
    t = len(slot_sebelumnya) if len(slot_sebelumnya) > 0 else 1

    # Hitung TF-IDF pada slot aktif sebagai pengayaan skor / pembanding
    docs_curr = df_curr["final_text"].fillna("").tolist()
    tfidf_lookup = {}
    if len(docs_curr) >= 2:
        vec_tfidf = TfidfVectorizer(ngram_range=(2, 3))
        mat_tfidf = vec_tfidf.fit_transform(docs_curr)
        skor_tfidf_arr = np.asarray(mat_tfidf.sum(axis=0)).ravel()
        tfidf_lookup = dict(zip(vec_tfidf.get_feature_names_out(), skor_tfidf_arr))

    df_i_counter = {}
    boost_accumulator = {}

    for _, row in df_curr.iterrows():
        boost_map = json.loads(row["ngram_boost_json"])
        for ng, b_val in boost_map.items():
            df_i_counter[ng] = df_i_counter.get(ng, 0) + 1
            boost_accumulator.setdefault(ng, []).append(b_val)

    df_prev_counter = {}
    for _, row in df_prev.iterrows():
        ngrams_prev = set(json.loads(row["all_ngrams_json"]))
        for ng in ngrams_prev:
            df_prev_counter[ng] = df_prev_counter.get(ng, 0) + 1

    hasil_ranking = []
    for ng, df_i in df_i_counter.items():
        sum_df_prev = df_prev_counter.get(ng, 0)
        avg_boost = sum(boost_accumulator[ng]) / len(boost_accumulator[ng])
        nilai_tfidf = tfidf_lookup.get(ng, 0.0)

        penyebut = math.log10((sum_df_prev / t) + 1) + 1
        skor_dfidft = ((df_i + 1) / penyebut) * avg_boost

        hasil_ranking.append({
            "Topik (BN-Gram)": ng,
            "DF Sekarang (DF_i)": df_i,
            "Total DF Sebelumnya": sum_df_prev,
            "NER Boost": round(avg_boost, 2),
            "Bobot TF-IDF": round(nilai_tfidf, 4),
            "Skor Trending (DF-IDFt)": round(skor_dfidft, 4)
        })

    df_rank = pd.DataFrame(hasil_ranking)
    urutan = st.radio("Urutkan Peringkat Berdasarkan:", ["Skor Trending (DF-IDFt)", "Bobot TF-IDF"], horizontal=True)
    df_rank = df_rank.sort_values(by=urutan, ascending=False).head(top_k)

    st.caption(f"Membandingkan **Slot {target_slot}** terhadap **{len(slot_sebelumnya)}** slot sebelumnya (`t = {t}`).")
    st.dataframe(df_rank, use_container_width=True)
    st.bar_chart(df_rank.set_index("Topik (BN-Gram)")[urutan])


# ==========================================
# HALAMAN 6: ANALISIS SENTIMEN TRENDING TOPIC
# ==========================================
def halaman_sentimen():
    st.header("6. Analisis Sentimen Opini Publik")
    engine = get_engine()

    try:
        df_bngram = pd.read_sql("SELECT * FROM bngrams_data_tweet", engine)
    except Exception:
        st.warning("Belum ada data di `bngrams_data_tweet`. Jalankan tahap sebelumnya terlebih dahulu.")
        return

    if df_bngram.empty:
        st.warning("Data masih kosong.")
        return

    list_slot = sorted(df_bngram["time_slot"].unique())
    pilih_slot = st.selectbox("Pilih Time Slot untuk Analisis Sentimen:", list_slot, index=len(list_slot) - 1)
    filter_topik = st.text_input("Filter berdasarkan kata/topik tertentu (opsional):", placeholder="Kosongkan untuk analisis semua tweet di slot ini")

    df_target = df_bngram[df_bngram["time_slot"] == pilih_slot].copy()
    if filter_topik.strip():
        kw = filter_topik.strip().lower()
        df_target = df_target[df_target["final_text"].str.contains(kw, na=False) | df_target["clean_text"].str.contains(kw, na=False)]

    st.write(f"Jumlah tweet yang akan dianalisis: **{len(df_target)}** tweet.")

    if not df_target.empty and st.button("Jalankan Analisis Sentimen", type="primary"):
        with st.spinner("Menganalisis sentimen dengan IndoBERT..."):
            sent_pipe = load_sentiment_model()
            label_map = {
                "LABEL_0": "Positif",
                "LABEL_1": "Netral",
                "LABEL_2": "Negatif"
            }

            hasil_sentimen = []
            skor_sentimen = []

            for teks in df_target["clean_text"].fillna(""):
                pred = sent_pipe(str(teks)[:512])[0]
                raw_lbl = pred["label"]
                hasil_sentimen.append(label_map.get(raw_lbl, raw_lbl))
                skor_sentimen.append(round(pred["score"], 4))

            df_target["Sentimen"] = hasil_sentimen
            df_target["Confidence"] = skor_sentimen

            col1, col2 = st.columns([1, 2])
            with col1:
                ringkasan = df_target["Sentimen"].value_counts()
                st.write("**Distribusi Sentimen:**")
                st.dataframe(ringkasan)
                st.bar_chart(ringkasan)
            with col2:
                st.write("**Detail Klasifikasi Tweet:**")
                st.dataframe(df_target[["full_text", "Sentimen", "Confidence"]], use_container_width=True)


# ==========================================
# NAVIGASI SIDEBAR
# ==========================================
st.sidebar.title("Navigasi Pipeline")
menu = st.sidebar.radio(
    "Pilih Tahapan:",
    [
        "1. Crawling Data X",
        "2. Cleaning & Preprocessing",
        "3. Pembobotan TF-IDF",
        "4. Ekstraksi BN-Grams & NER",
        "5. Perangkingan Trending",
        "6. Analisis Sentimen"
    ]
)

if menu == "1. Crawling Data X":
    halaman_crawling()
elif menu == "2. Cleaning & Preprocessing":
    halaman_preprocessing()
elif menu == "3. Pembobotan TF-IDF":
    halaman_tfidf()
elif menu == "4. Ekstraksi BN-Grams & NER":
    halaman_bngram()
elif menu == "5. Perangkingan Trending":
    halaman_perangkingan()
elif menu == "6. Analisis Sentimen":
    halaman_sentimen()