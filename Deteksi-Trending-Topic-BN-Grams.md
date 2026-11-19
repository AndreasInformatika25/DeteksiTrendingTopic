# DETEKSI TRENDING TOPIC DI TWITTER DENGAN METODE BN-GRAMS

**Oleh: Indra**

---

## Tahapan Metode BN-Grams
1. Pengumpulan Data
2. Preprocessing
3. Ekstraksi n-grams
4. Perangkingan n-grams
5. Klasterisasi n-grams
6. Perangkingan Klaster
7. Pengujian Trending Topic

---

## Pengumpulan Data Tweet

- Tweet dikumpulkan secara rutin minimal dua jam per hari.
- Setiap dua jam tweet dibagi dalam 30 menit per *time slots*.
- Setiap *time slots* berisi sekitar 3000 tweet.
- Satu *time slots* terbentuk satu dataset.
- Dataset tersebut merupakan output dari *time aggregation*.

**(Ilustrasi Time Slots)**
`08:00` ➔ `08:30` ➔ `09:00` ➔ `09:30` ➔ `10:00`

---

## Contoh Tweet Terkumpul

| Time | Time Slots | Index Tweet (Tn) | Tweet |
|---|---|---|---|
| Fri Jan 09, 04:00:00 – 04:30:00 | 1 | T1 | Ahok modus manipulasi ktp |
| Fri Jan 09, 04:00:00 – 04:30:00 | 1 | T2 | Ahok modus pembuatan sertifikat |
| Fri Jan 09, 04:00:00 – 04:30:00 | 1 | T3 | Jokowi natuna ratas imam bonjol |
| Fri Jan 09, 04:31:00 – 05:00:00 | 2 | T4 | Jokowi rapat natuna |
| Fri Jan 09, 04:31:00 – 05:00:00 | 2 | T5 | TNI jamin keamanan Jokowi Natuna |
| Fri Jan 09, 04:31:00 – 05:00:00 | 2 | T6 | Mari belajar dengan tekun |

---

## Preprocessing

- **Tokenisasi:** 
  - Sebelum: "Mari belajar dengan tekun"
  - Sesudah: "mari, belajar, tekun"
- **Stemming:** 
  - "mari, ajar, tekun"
- **Aggregation:**
  - *Time aggregation*
  - *Topic aggregation*

---

## Time Aggregation (Kedekatan waktu)

| Waktu | 04:00 | 04:30 | 05:00 |
|---|---|---|---|
| **Tweet** | T1, T2, T3 | T4, T5, T6 | |
| **Dataset** | **Datasets 1** | **Datasets 2** | |

---

## Topic Aggregation (Similarity antar Tweet)

**Klaster 1:**
- .T1
- .T5
- .T6

**Klaster 2:**
- .T2
- .T3
- .T4

⬇️
*Deteksi trending topic dilakukan pada setiap klaster*

---

## Ekstraksi n-grams

**Tabel 5.6 Ilustrasi ekstraksi bigrams dan trigrams dari dataset politik (Tabel 5.1)**

| Time | Time Slot | Indeks tweet (Tn) | Tweet | Bigrams | Trigrams |
|---|---|---|---|---|---|
| Thursday Jun 16 04:18:44 – 04:20:00 | 1 | T1 | Ahok modus manipulasi ktp | {ahok modus, modus manipulasi, manipulasi ktp} | {ahok modus manipulasi, modus manipulasi ktp} |
| Thursday Jun 16 04:18:44 – 04:20:00 | 1 | T2 | Ahok modus pembuatan sertifikat | {ahok modus, modus pembuatan, pembuatan sertifikat} | {ahok modus pembuatan, modus pembuatan sertifikat} |
| Thursday Jun 16 04:18:44 – 04:20:00 | 1 | T3 | jokowi natuna ratas imam bonjol | {jokowi natuna, natuna ratas, ratas imam, imam bonjol} | {jokowi natuna ratas, ratas imam bonjol} |
| Thursday Jun 16 14:20:00 – 14:22:44 | 2 | T1 | jokowi rapat natuna | {jokowi rapat, rapat natuna} | {jokowi rapat natuna} |
| Thursday Jun 16 14:20:00 – 14:22:44 | 2 | T2 | tni jamin keamanan | {tni jamin, jamin} | {tni jamin keamanan, |

---

## Perangkingan n-grams

Setiap n-grams yang terekstrak, dilakukan indexing berdasarkan persamaan (1):

$$ df - idf_t = \frac{df_i + 1}{\log\left(\frac{\sum_{j=i}^{t} df_{i-j}}{t} + 1\right) + 1} \cdot boost \quad (1) $$

**Dimana:**
- $df_i$ = document frequency time slots ke i
- $df_{i-j}$ = document frequency previous time slots ke i
- $t$ = total time slots
- **Boost** = bobot dari kata yang tergolong person, location, organizations. (bobot = 1.5 jika kata termasuk kategori tersebut. Jika sebaliknya bobot = 1.0)
- $df - idf_t$ = temporal document frequency - inverse document frequency

---

## Ilustrasi Perangkingan n-grams

**Tabel 5.7 Ilustrasi Perangkingan DF-IDF$_t$ dalam bigrams**

| Time | Time slot ke i | Bigrams | $df_i$ | $t$ | DFIDF$_t$ (Persamaan 3.1) |
|---|---|---|---|---|---|
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Ahok modus, Modus manipulasi, Manipulasi ktp, Modus pembuatan, pembuatan sertifikat, Jokowi natuna, Natuna ratas, Ratas imam, Imam bonjol | 2, 1, 1, 1, 1, 1, 1, 1, 1 | 2 | 4,5, 2, 2, 2, 2, 2, 2, 2, 2 |
| Thur Jan 16 14:20:00 – 14:22:44 | 2 | Jokowi rapat, Rapat natuna, Tni jamin, Jamin keamanan, Keamanan jokowi, Jokowi natuna | 1, 1, 1, 1, 1, 1 | 2 | 2, 2, 2, 2, 2, 2,54 |

---

## Klasterisasi n-grams

- Klasterisasi menggunakan **Klasterisasi Hirarki Group Average**
- Klasterisasi menggunakan dua tahapan:
  - **Tahap 1:** menghitung jarak antar n-grams dengan persamaan (2)
    $$ d_{12} = 1 - \frac{A}{\text{MIN}(B,C)} \qquad (2) $$
    **Dimana:**
    - $d_{12}$ = jarak kedekatan antar n-grams1 dan n-grams2
    - $A$ = jumlah tweet yang memiliki n-grams 1 dan n-grams2
    - $B$ = jumlah tweet yang memiliki n-grams 1
    - $C$ = jumlah tweet yang memiliki n-grams 2
    - Fungsi Min untuk menentukan nilai terkecil dari perbandingan B dan C
  - **Tahap 2:** menghitung jarak antar klaster dengan metode *average linkage*

---

## Ilustrasi Klasterisasi N-Grams

**Tabel 5.8. Pemetaan n-grams di setiap tweet**
*Diket: Tn = Tweet ke n; n1 = n-grams ke 1;*

| | Ahok (n-grams1) | Modus (n-grams2) | Manipulasi (n-grams3) | sertifikat (n-grams4) | Jokowi (n-grams5) |
|---|---|---|---|---|---|
| Tweet1 | 1 | 1 | 1 | 0 | 0 |
| Tweet2 | 1 | 1 | 0 | 1 | 0 |
| Tweet4 | 0 | 0 | 0 | 0 | 1 |
| Total n-grams | 2 | 2 | 1 | 1 | 1 |

---

## Matrik jarak kedekatan antar n-grams

**Tabel 5.9 Hasil matrik jarak kedekatan antar n-grams dengan Persamaan (3.3)**

| $D_{man}$ | n-grams 1 | n-grams 2 | n-grams 3 | n-grams 4 | n-grams 5 |
|---|---|---|---|---|---|
| n-grams 1 | 0 | 0 | 0 | 0 | 1 |
| n-grams 2 | 0 | 0 | 0 | 0 | 1 |
| n-grams 3 | 0 | 0 | 0 | 0 | 1 |
| n-grams 4 | 0 | 0 | 0 | 0 | 1 |
| n-grams 5 | 1 | 1 | 1 | 1 | 0 |

Berdasarkan Persamaan (3.3) jarak kedekatan antar n-grams1 dan n-grams 2 untuk memenuhi nilai dari Tabel 5.9 dapat diilustrasikan sebagai berikut:
$$d(1, 2) = 1 - \frac{2}{\min\{2, 2\}} = 1 - \frac{2}{2} = 0$$

dengan $d(1, 2)$ adalah jarak kedekatan antara n-grams1 dan n-grams2. A bernilai dua karena jumlah *tweet* yang memiliki n-grams1 dan n-grams2 berada pada dua *tweet*. Sedangkan B bernilai dua karena jumlah *tweet* yang memiliki n-grams 1 adalah dua *tweet*. C bernilai 2 karena jumlah *tweet* yang memiliki n-grams2 ada dua.

---

## Dua N-grams dengan jarak terkecil digabungkan

- N-grams 1 & 2 digabungkan karena jaraknya = 0
- Menghitung jarak antar n-grams (1 & 2) dengan n-grams tersisa: n-grams 3, 4 dan 5
$$D_{(12)3} = \text{average } \{d_{13}; d_{23}\} = \text{average } \{0; 0\} = 0$$
$$D_{(12)4} = \text{average } \{d_{14}; d_{24}\} = \text{average } \{0; 0\} = 0$$

---

## Perubahan Tabel Matriks

- Menghapus baris dan kolom matrik jarak yang bersesuaian dengan n1,2
- Menambahkan baris dan kolom untuk kelompok (1,2) maka didapatkan Tabel matriks sbb:

**Tabel 5.10 Matrik hasil pengolahan $D_{man}$ iterasi ke-1**

| $D_{man}$ | n-grams(12) | n-grams3 | n-grams4 | n-grams5 |
|---|---|---|---|---|
| n-grams(12) | 0 | 0 | 0 | 1 |
| n-grams3 | 0 | 0 | 0 | 1 |
| n-grams4 | 0 | 0 | 0 | 1 |
| n-grams5 | 1 | 1 | 1 | 0 |

---

## Kemudian dipilih jarak n-grams terkecil kembali

- N-grams 3,4 terpilih karena memiliki jarak dengan nilai 0
- Menghitung jarak dengan kelompok atau n-grams yang tersisa:
$$D_{(34)12} = \text{average} \{d_{31}; d_{32}; d_{41}; d_{42}\} = \text{average} \{0;0;0;0\} = \frac{0+0+0+0}{4} = 0$$
$$D_{(34)5} = \text{average} \{d_{34}; d_{35}\} = \text{average} \{0,1\} = \frac{0+1}{2} = 0,5$$