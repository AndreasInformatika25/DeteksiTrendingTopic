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