Selected Files Directory Structure:

└── ./
    ├── preprocessing
    │   ├── __init__.py
    │   └── pipeline.py
    ├── cleaner.py
    └── crawler.py



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