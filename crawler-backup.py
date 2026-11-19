import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TOKEN = os.getenv("X_AUTH_TOKEN", "a9d38ab97c5eaf665be777ce4e88bf6fa406194e")


def crawl_x(input_keywords, filename, since, until, limit, auth_token=None):
    token = auth_token.strip() if auth_token else DEFAULT_TOKEN
    list_kw = [k.strip() for k in input_keywords.split(",") if k.strip()]

    if not list_kw:
        return False, "❌ Gagal crawl. Keyword tidak boleh kosong."

    if len(list_kw) == 1:
        gabungan_kw = list_kw[0]
    else:
        list_kutip = [f'"{k}"' for k in list_kw]
        gabungan_kw = f"({' OR '.join(list_kutip)})"

    search_keyword = f"{gabungan_kw} since:{since} until:{until} lang:in"
    print(f"[*] MENJALANKAN QUERY: {search_keyword}")

    command = [
        "npx", "-y", "tweet-harvest@latest",
        "-o", filename,
        "-s", search_keyword,
        "--tab", "LATEST",
        "-l", str(limit),
        "--token", token
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        return True, f"✅ Berhasil crawl. File: {filename}"
    else:
        return False, f"❌ Gagal crawl. Error:\n{result.stderr}"