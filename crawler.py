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