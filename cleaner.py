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