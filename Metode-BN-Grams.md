# PENJABRAN DETEKSI TRENDING TOPIC MENGGUNAKAN METODE BN-GRAMS

## Tabel 5.1. Sampel data tweet

| Tweet (Ti) | Text | Username |
|---|---|---|
| T1 | ahok modus manipulasi ktp | TrcRiau |
| T2 | ahok modus pembuatan sertifikat | Fdayun |
| T3 | jokowi natuna ratas imam bonjol | Faktababelcom |
| T4 | jokowi rapat natuna | FaktaSumbarcom |
| T5 | tni jamin keamanan jokowi natuna | NHasan03 |

---

## 5.3. Metode BN-grams

Tweet yang dihasilkan dari tahapan prapemrosesan pada subbab 4.3 kemudian dilakukan deteksi *trending topic* menggunakan metode BN-grams dengan tiga tahapan yaitu:

1. Mendapatkan *keyword* dalam bentuk bigrams atau trigrams dari dataset Twitter.
2. Melakukan perangkingan setiap n-gram (bigrams atau trigrams) menggunakan perhitungan *dfidft* untuk didapatkan skor setiap bigrams atau trigrams.
3. Melakukan *clustering* dari setiap n-gram berdasarkan jarak antar n-gram untuk didapatkan *trending topic* dari setiap klaster.

---

### 5.3.1. Ekstraksi bigrams dan trigrams dari sampel tweet

Tweet dari hasil prapemrosesan dilakukan ekstraksi bigrams dan trigrams. Hasil ekstraksi bigrams dan trigrams merupakan sebuah *keyword* yang selanjutnya diberikan indeks menggunakan *Lucene*. Pemberian indeks ini digunakan untuk memudahkan dalam proses pencarian bigrams maupun trigrams. Selanjutnya, setiap bigrams dan trigrams dilakukan perangkingan pada rentang waktu ke-*i* menggunakan Persamaan (3.2). Ilustrasi dari ekstraksi bigrams dan trigrams dari dataset politik dapat dilihat pada Tabel 5.6.

Tabel 5.6 menjelaskan tentang ekstraksi fitur n-grams pada setiap tweet dalam bentuk bigrams dan trigrams dalam *time slots* ke-*i*. Setiap tweet dilakukan pemecahan term dengan mengelompokkan dua term (bigrams) atau tiga term (trigrams) secara berurutan. Kolom *Time* merupakan periode waktu penarikan tweet pada setiap *time slots*. Kolom *Time slot* adalah interval waktu dari waktu awal sampai dengan waktu akhir pengumpulan data *tweet*. Kolom *Tweet* merupakan *tweet* atau pesan yang terkumpul dari status pengguna Twitter. Indeks *tweet* ($T_n$) adalah nomor identitas *tweet* disetiap *time slot*. Kolom bigrams merupakan ekstraksi dua kata dari setiap *tweet*. Kolom trigrams merupakan ekstraksi tiga kata dari setiap *tweet*.

#### Tabel 5.6. Ilustrasi ekstraksi bigrams dan trigrams dari dataset politik (Tabel 5.1)

| Time | Time Slot | Indeks tweet (Tn) | Tweet | Bigrams | Trigrams |
|---|---|---|---|---|---|
| Thursday Jun 16 04:18:44 – 04:20:00 | 1 | T1 | Ahok modus manipulasi ktp | {ahok modus, modus manipulasi, manipulasi ktp} | {ahok modus manipulasi, modus manipulasi ktp} |
| Thursday Jun 16 04:18:44 – 04:20:00 | 1 | T2 | Ahok modus pembuatan sertifikat | {ahok modus, modus pembuatan, pembuatan sertifikat} | {ahok modus pembuatan, modus pembuatan sertifikat} |
| Thursday Jun 16 04:18:44 – 04:20:00 | 1 | T3 | jokowi natuna ratas imam bonjol | {jokowi natuna, natuna ratas, ratas imam, imam bonjol} | {jokowi natunan ratas, ratas imam bonjol} |
| Thursday Jun 16 14:20:00 – 14:22:44 | 2 | T1 | jokowi rapat natuna | {jokowi rapat, rapat natuna} | {jokowi rapat natuna} |
| Thursday Jun 16 14:20:00 – 14:22:44 | 2 | T2 | tni jamin keamanan jokowi natuna | {tni jamin, jamin keamanan, keamanan jokowi, jokowi natuna} | {tni jamin keamanan, keamanan jokowi natuna} |

---

### 5.3.2. Perangkingan BN-grams

Perangkingan dalam metode BN-grams (pada kasus ini sebagai contoh adalah bigrams) dilakukan dengan menggunakan Persamaan (3.2). Perangkingan bigrams menggunakan perhitungan skor *dfidft* pada setiap slot waktu ke-*i*. Perhitungan *dfidft* dibuat berdasarkan frekuensi kemunculan bigrams pada rentang waktu tertentu dibandingkan dengan logaritma dari rata-rata frekuensi jumlah keseluruhan frekuensi bigrams pada rentang waktu yang sebelumnya. Ilustrasi dari proses perangkingan bigrams sesuai Persamaan (3.2) dapat dilihat pada Tabel 5.7.

#### Tabel 5.7. Ilustrasi Perangkingan DF-IDF$_t$ dalam bigrams

| Time | Time slot ke i | Bigrams | $df_i$ | $t$ | DFIDF$_t$ (Persamaan 3.1) |
|---|---|---|---|---|---|
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Ahok modus | 2 | 2 | 4,5 |
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Modus manipulasi | 1 | 2 | 2 |
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Manipulasi ktp | 1 | 2 | 2 |
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Modus pembuatan | 1 | 2 | 2 |
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | pembuatan sertifikat | 1 | 2 | 2 |
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Jokowi natuna | 1 | 2 | 2 |
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Natuna ratas | 1 | 2 | 2 |
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Ratas imam | 1 | 2 | 2 |
| Thur Jan 16 04:18:44 – 04:20:00 | 1 | Imam bonjol | 1 | 2 | 2 |
| Thur Jan 16 14:20:00 – 14:22:44 | 2 | Jokowi rapat | 1 | 2 | 2 |
| Thur Jan 16 14:20:00 – 14:22:44 | 2 | Rapat natuna | 1 | 2 | 2 |
| Thur Jan 16 14:20:00 – 14:22:44 | 2 | Tni jamin | 1 | 2 | 2 |
| Thur Jan 16 14:20:00 – 14:22:44 | 2 | Jamin keamanan | 1 | 2 | 2 |
| Thur Jan 16 14:20:00 – 14:22:44 | 2 | Keamanan jokowi | 1 | 2 | 2 |
| Thur Jan 16 14:20:00 – 14:22:44 | 2 | Jokowi natuna | 1 | 2 | 2,54 |

Tabel 5.7 menunjukkan term "jokowi natuna" pada *time slot* ke-*i* (i=2) memiliki frekuensi kemunculan kata ($df_2$) berjumlah 1. Pada *time slot* ke-*i-1* (i=1) bigrams "jokowi natuna" memiliki frekuensi kemunculan kata ($df_1$) berjumlah 1.

Nilai boost pada bigrams "jokowi natuna" adalah 1,5 karena bigrams tersebut termasuk dalam kategori orang, lokasi atau organisasi. Nilai $dfidf_t$ untuk bigrams "jokowi natuna" dengan nilai ($df_i$) = 1 dan ($df_{i-1}$) = 1 serta nilai boost = 1,5 serta nilai $t$ berjumlah 2 time slot disubstitusikan ke dalam Persamaan (3.2) sehingga menghasilkan nilai skor $dfidf_t$ untuk term "jokowi natuna" sebesar 2,54. Perhitungan skor $dfidf_t$ dapat diilustrasikan sebagai berikut:

$$dfidf_t = \frac{1 + 1}{\log\left(\frac{1}{2} + 1\right) + 1}$$

$$dfidf_t = \frac{(3)}{1,18} = 2,54$$

---

### 5.3.3. Klasterisasi n-grams menggunakan metode klasterisasi hirarki *group average*

Klasterisasi hirarki pada BN-grams menggunakan metode *group average linkage* berisi dua tahapan. Tahap pertama menghitung jarak antar n-grams. Hal ini disimbolkan dengan $D_{man}$ yaitu jarak di antara n-grams x dan n-grams y seperti pada Persamaan (3.3). Penjabaran dari Persamaan (3.3) dapat diilustrasikan dengan memetakan n-grams ke dalam setiap *tweet* yang dapat dilihat pada Tabel 5.8. Tahap kedua, selanjutnya dilakukan pemilihan jarak dua kelompok berdasarkan rata-rata dari dua kelompok tersebut. Sebelum menghitung rata-rata dari dua kelompok tersebut, dilakukan pemilihan dari jarak dua kelompok terkecil berdasarkan matrik dari Tabel 5.9 sampai dengan nilai kesamaan lebih dari atau sama dengan nilai *threshold* 0,50. Tabel 5.8 menunjukkan pembentukan klaster yang berasal dari tweet T1, T2 dan T4. Tweet T1, T2 dan T4 berisi tweet dengan kalimat berturut-turut adalah "Ahok modus manipulasi ktp"; "Ahok modus pembuatan sertifikat"; dan "Jokowi rapat natuna" dengan fitur unigrams yang berada pada dataset politik seperti pada Tabel 5.1.

#### Tabel 5.8. Pemetaan n-grams di setiap *tweet*

| | Ahok (n-grams1) | Modus (n-grams2) | Manipulasi (n-grams3) | sertifikat (n-grams4) | Jokowi (n-grams5) |
|---|---|---|---|---|---|
| Tweet1 | 1 | 1 | 1 | 0 | 0 |
| Tweet2 | 1 | 1 | 0 | 1 | 0 |
| Tweet4 | 0 | 0 | 0 | 0 | 1 |
| Total n-grams | 2 | 2 | 1 | 1 | 1 |

Tabel 5.8 menunjukkan *tweet* dipengaruhi oleh fitur n-grams dan pengumpulan dataset. Tweet ke-1 (T1) berisi n-grams1 ("Ahok"), n-grams2 ("modus") dan n-grams3 ("manipulasi") berasal dari status pengguna Twitter yang dikumpulkan pada setiap dataset. Disisi lain, n-grams1 berada pada *tweets* 1 dan *tweets*2 yang disimbolkan dengan bilangan biner 1. Sedangkan n-grams 2 berada pada *tweets* 1 dan *tweet* 2. Simbol biner 1 menunjukkan bahwa *tweet* tersebut berisi n-grams, sedangkan simbol biner 0 menyatakan *tweets* tersebut tidak memiliki n-grams tersebut. Biner 0 dan 1 berlaku juga untuk pemetaan n-grams 3, n-grams 4 dan n-grams 5 dari setiap *tweet* yang ada. Hasil pemetaan n-grams pada setiap *tweet* pada Tabel 5.8 digunakan untuk perhitungan jarak antar n-grams seperti pada Tabel 5.9.

#### Tabel 5.9. Hasil matrik jarak kedekatan antar n-grams dengan Persamaan (3.3)

| $D_{man}$ | n-grams 1 | n-grams 2 | n-grams 3 | n-grams 4 | n-grams 5 |
|---|---|---|---|---|---|
| n-grams 1 | 0 | 0 | 0 | 0 | 1 |
| n-grams 2 | 0 | 0 | 0 | 0 | 1 |
| n-grams 3 | 0 | 0 | 0 | 0 | 1 |
| n-grams 4 | 0 | 0 | 0 | 0 | 1 |
| n-grams 5 | 1 | 1 | 1 | 1 | 0 |

Berdasarkan Persamaan (3.3) jarak kedekatan antara n-grams1 dan n-grams 2 untuk memenuhi nilai dari Tabel 5.9 dapat diilustrasikan sebagai berikut:

$$d(1,2) = 1 - \frac{2}{\min\{2,2\}} = 1 - \frac{2}{2} = 0$$

dengan $d(1,2)$ adalah jarak kedekatan antara n-grams1 dan n-grams2. A bernilai dua karena jumlah *tweet* yang memiliki n-grams1 dan n-grams2 berada pada dua *tweet*. Sedangkan B bernilai dua karena jumlah *tweet* yang memiliki n-grams 1 adalah dua *tweet*. C bernilai 2 karena jumlah *tweet* yang memiliki n-grams2 ada dua tweet. Perhitungan $d_{xy}$ juga berlaku untuk perhitungan jarak kedekatan antar n-grams x dengan n-grams y.

Tabel 5.9 mengindikasikan hubungan jarak kedekatan antar n-grams. Jarak kedekatan n-grams 1 dan n-grams 2 adalah 0. Hal ini dapat diartikan dari tiga tweet yang ada, dua tweet berisi n-grams 1 dan 2. Hal ini dapat disimpulkan, dua n-grams dengan jarak kedekatan sebesar 0 dapat diartikan mayoritas (lebih dari 60%) dari total tweet yang ada berisi kedua n-grams tersebut. Oleh karena itu, dua n-grams memiliki kedekatan yang tinggi dan diilustrasikan dengan nilai 0. Sebaliknya, jarak kedekatan antara n-grams 1 dan 5 adalah satu. Hal ini dapat diartikan tidak ada tweet yang berisi kedua n-grams tersebut. Oleh karena itu, dua n-grams memiliki kedekatan yang rendah sehingga diilustrasikan dengan nilai 1. Tabel 5.9 menjelaskan bahwa semakin kecil jarak dari dua n-grams maka semakin banyak tweet yang berisi dua n-grams tersebut. Sebaliknya, semakin besar jarak dua n-grams maka semakin kecil jumlah tweet yang berisi dua n-grams tersebut.

$$\text{Min (D}_{\text{man}}\text{)} = \text{min (d(1,2))} = 0$$

Terpilih n-grams 1 dan 2, sehingga kedua n-grams ini digabungkan dan dinotasikan dalam kelompok (12). Tahap berikutnya adalah menghitung jarak antar n-grams (1 dan 2) dengan kelompok lain yang tersisa, yaitu n-grams 3, n-grams 4 dan n-grams 5.

$$D_{(12)3} = \text{average} \{d_{13}; d_{23}\} = \text{average} \{0; 0\} = 0$$

$$D_{(12)4} = \text{average} \{d_{14}; d_{24}\} = \text{average} \{0; 0\} = 0$$

$$D_{(12)5} = \text{average} \{d_{15}; d_{25}\} = \text{average} \{1; 1\} = \frac{1+1}{2} = 1$$

Dengan menghapus baris dan kolom matrik jarak yang bersesuaian dengan n-grams 1 dan 2, serta menambahkan baris dan kolom untuk kelompok (12) didapatkan matrik seperti pada Tabel 5.10.

#### Tabel 5.10. Matrik hasil pengolahan Dman iterasi ke-1

| $D_{man}$ | n-grams(12) | n-grams3 | n-grams4 | n-grams5 |
|---|---|---|---|---|
| n-grams(12) | 0 | 0 | 0 | 1 |
| n-grams3 | 0 | 0 | 0 | 1 |
| n-grams4 | 0 | 0 | 0 | 1 |
| n-grams5 | 1 | 1 | 1 | 0 |

Selanjutnya dipilih jarak n-grams terkecil, kelompok n-grams3 dan n-grams4 digabung untuk menjadi kelompok tunggal dari dua data, yaitu kelompok (34) dengan jarak terdekat 0. Berikutnya adalah menghitung dengan kelompok lain yang tersisa yaitu n-grams 12 dan n-grams 5.

$$D_{(34)12} = \text{average} \{d_{31}; d_{32}; d_{41}; d_{42}\} = \text{average} \{0;0;0;0\} = \frac{0+0+0+0}{4} = 0$$

$$D_{(34)5} = \text{average} \{d_{34}; d_{35}\} = \text{average} \{0,1\} = \frac{0+1}{2} = 0,5$$

Dengan menghapus baris dan kolom matrik jarak yang bersesuaian dengan n-grams 3 dan 4, serta menambahkan baris dan kolom untuk kelompok (34) didapatkan matrik seperti pada Tabel 5.11.

#### Tabel 5.11. Matrik hasil pengolahan $D_{man}$ iterasi ke-2

| $D_{man}$ | n-grams(12) | n-grams(34) | n-grams5 |
|---|---|---|---|
| n-grams(12) | 0 | 0 | 1 |
| n-grams(34) | 0 | 0 | 0,50 |
| n-grams5 | 1 | 0,50 | 0 |

Selanjutnya dipilih jarak n-grams terkecil. Kelompok (12) dan Kelompok (34) digabung untuk menjadi kelompok tunggal dari dua data, yaitu kelompok (1234) dengan jarak terdekat 0. Berikutnya adalah menghitung dengan kelompok lain yang tersisa yaitu n-grams (5).

$$D_{(1234)(5)} = \text{average} \{d_{15}; d_{25}; d_{35}; d_{45}\} = \text{average} \{1;1;1;1\} = \frac{4}{4} = 1$$

Dengan menghapus baris dan kolom matrik jarak yang bersesuaian dengan n-grams (1234) dan n-grams (5), serta menambahkan baris dan kolom untuk kelompok (1234) didapatkan matrik seperti pada Tabel 5.12.

#### Tabel 5.12. Matrik hasil pengolahan $D_{man}$ iterasi ke-3

| $D_{man}$ | n-grams(1234) | n-grams(5) |
|---|---|---|
| n-grams(1234) | 0 | 1 |
| n-grams(5) | 1 | 0 |

Jadi kelompok (1234) dan kelompok (5) digabungkan jarak terdekat 1,00. Hasil akhir pengelompokkan n-grams dalam bentuk dendogram berdasarkan perhitungan jarak antar n-grams menggunakan *group average linkage* dapat dilihat pada Gambar 5.2.

Hasil pembentukan klaster pada Tabel 5.12 menghasilkan dua klaster. Klaster ke-1 dituliskan dengan $K1 = \{n_1, n_2, n_3, n_4\}$, sedangkan klaster ke-2 dituliskan dengan $K2 = \{n_5\}$. Simbol $n_1$ adalah jenis n-grams1. Begitu juga $n_2, n_3, n_4, n_5$ berturut-turut adalah n-grams2, n-grams3, n-grams4 dan n-grams5.

**Gambar 5.2. Ilustrasi klasterisasi hirarki *group average***

Gambar 5.2 menjelaskan hasil akhir pembentukan *cluster* antar n-grams menghasilkan empat *cluster*. Secara keseluruhan terbentuk *cluster* besar yang berisi n-grams 1 sampai n-grams 5. Selanjutnya, terbentuk dua *cluster* utama yaitu *cluster* ke-1 berisi n-grams 3, sedangkan *cluster* ke-2 berisi n-grams 1, 2, 4 dan n-grams 5. Kemudian, didalam *cluster* ke-2 terbentuk sub *cluster* yang berisi *cluster* ke-3 dengan elemen n-grams 1 dan 2, sedangkan *cluster* ke-4 dengan elemen n-grams 4 dan 5.

Pada penelitian ini, penentuan klaster menggunakan metode K-Means tidak dapat diterapkan. Hal ini terjadi karena atribut dari n-grams tidak dapat digunakan dalam perhitungan nilai centroid, sehingga metode K-Means tidak dapat diterapkan dalam clustering n-grams ini. Klasterisasi yang sesuai untuk n-grams pada Twitter ini adalah clustering hirarki. Pada penelitian ini dilakukan modifikasi clustering hirarki dengan metode Text Clustering menggunakan algoritme Frequent Term–Based Clustering (FTC) dan Hierarchical Frequent Term–Based Clustering (HFTC).

---

### 5.3.4. Topic ranking

Klaster dilakukan perangkingan berdasarkan skor DF-IDFt setiap n-grams. Klaster yang berisi n-grams dengan skor DF-IDFt tertinggi maka klaster tersebut diidentifikasikan sebagai trending topic. Berdasarkan Tabel 5.7 n-grams1 dan n-grams2 dengan term "Ahok modus" memiliki skor tertinggi dibandingkan n-grams pada time slots ke-1. Oleh karena itu, klaster yang berisi n-grams1 dan n-grams2 menjadi rangking pertama dan diidentifikasikan sebagai trending topic. Klaster tersebut adalah klaster K1 = {n1, n2, n3, n4}.