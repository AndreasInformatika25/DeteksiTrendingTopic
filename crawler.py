import os
import re
import json
import inspect
import pandas as pd
from dotenv import load_dotenv
from Scweet.scweet import scrape

load_dotenv()

# Mengambil token dari .env jika ada, atau menggunakan token bawaan dari kode sebelumnya
X_AUTH_TOKEN = os.getenv("X_AUTH_TOKEN", "a9d38ab97c5eaf665be777ce4e88bf6fa406194e")


def _siapkan_cookie_auth(token, cookie_path="cookies.json"):
    """Membuat file cookie X dari auth_token agar Scweet bisa melewati halaman login."""
    cookies = [
        {
            "name": "auth_token",
            "value": token,
            "domain": ".x.com",
            "path": "/",
            "secure": True,
            "httpOnly": True
        },
        {
            "name": "auth_token",
            "value": token,
            "domain": ".twitter.com",
            "path": "/",
            "secure": True,
            "httpOnly": True
        }
    ]
    with open(cookie_path, "w") as f:
        json.dump(cookies, f, indent=2)
    return cookie_path


def _normalisasi_kolom_scweet(df):
    """
    Menyamakan nama kolom hasil Scweet agar sesuai dengan struktur
    tweet-harvest (full_text, created_at, id_str, lang) yang dipakai app.py.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # 1. Mapping kolom teks utama -> 'full_text'
    if "full_text" not in df.columns:
        if "Text" in df.columns:
            df["full_text"] = df["Text"]
        elif "Embedded_text" in df.columns:
            df["full_text"] = df["Embedded_text"]
        else:
            kolom_obj = df.select_dtypes(include=["object"]).columns
            if len(kolom_obj) > 0:
                df["full_text"] = df[kolom_obj[0]]

    # 2. Mapping waktu -> 'created_at'
    if "created_at" not in df.columns and "Timestamp" in df.columns:
        df["created_at"] = df["Timestamp"]

    # 3. Mapping ID Tweet dari Tweet URL -> 'id_str'
    if "id_str" not in df.columns:
        if "Tweet URL" in df.columns:
            df["id_str"] = df["Tweet URL"].astype(str).apply(
                lambda url: re.search(r"/status/(\d+)", url).group(1)
                if re.search(r"/status/(\d+)", url)
                else url
            )
        else:
            df["id_str"] = df.index.astype(str)

    # 4. Mapping metadata tambahan jika tersedia
    rename_opsional = {
        "UserScreenName": "name",
        "UserName": "username",
        "Likes": "favorite_count",
        "Retweets": "retweet_count",
        "Comments": "reply_count",
        "Tweet URL": "tweet_url",
    }
    for lama, baru in rename_opsional.items():
        if lama in df.columns and baru not in df.columns:
            df[baru] = df[lama]

    # 5. Tambahkan kolom 'lang' default 'in'
    if "lang" not in df.columns:
        df["lang"] = "in"

    # Bersihkan baris yang full_text-nya kosong
    df = df.dropna(subset=["full_text"])
    df = df[df["full_text"].astype(str).str.strip() != ""].reset_index(drop=True)

    return df


def crawl_x(input_keywords, filename, since, until, limit):
    # 1. Pecah string keyword koma-komaan menjadi list
    list_kw = [k.strip() for k in input_keywords.split(",") if k.strip()]

    if not list_kw:
        return False, "❌ Gagal crawl. Keyword tidak boleh kosong."

    # 2. Pastikan folder output 'tweets-data' tersedia (sesuai ekspektasi app.py)
    os.makedirs("tweets-data", exist_ok=True)
    nama_bersih = filename.replace(".csv", "").strip()
    output_path = f"tweets-data/{nama_bersih}.csv"

    print(f"[*] MENJALANKAN SCWEET | Keywords: {list_kw} | Since: {since} | Until: {until} | Limit: {limit}")

    try:
        # 3. Siapkan parameter dasar Scweet
        scrape_kwargs = {
            "words": list_kw,
            "since": str(since),
            "until": str(until),
            "from_account": None,
            "interval": 1,
            "headless": True,
            "display_type": "Latest",
            "save_images": False,
            "lang": "id",
            "resume": False,
            "filter_replies": False,
            "proximity": False,
            "limit": int(limit),
        }

        # 4. Cek dukungan parameter autentikasi di versi Scweet yang terinstal
        sig_params = inspect.signature(scrape).parameters
        if X_AUTH_TOKEN and "cookies_path" in sig_params:
            scrape_kwargs["cookies_path"] = _siapkan_cookie_auth(X_AUTH_TOKEN)
        elif os.path.exists(".env") and "env" in sig_params:
            scrape_kwargs["env"] = ".env"

        df_scweet = scrape(**scrape_kwargs)

        # 5. Normalisasi kolom agar cocok dengan pipeline & database MySQL
        df_final = _normalisasi_kolom_scweet(df_scweet)

        if df_final.empty:
            return False, "⚠️ Scweet selesai berjalan, tetapi tidak ada tweet yang ditemukan untuk keyword & rentang tanggal tersebut."

        df_final = df_final.head(int(limit))

        # 6. Simpan ke CSV lokal di folder tweets-data/
        df_final.to_csv(output_path, index=False)

        return True, f"✅ Berhasil crawl {len(df_final)} tweet via Scweet. File: {output_path}"

    except Exception as e:
        return False, f"❌ Gagal crawl via Scweet. Error:\n{str(e)}"