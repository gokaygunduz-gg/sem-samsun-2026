# SEM Türkiye Finali 2026 — Proje Günlüğü

**Proje:** SEM (Sporcu Eğitim Merkezleri) Türkiye Finali Canlı Panel  
**Tarih:** 28-29-30 Temmuz 2026, Samsun Olimpik Yüzme Havuzu  
**Yarış URL:** https://canli.tyf.gov.tr/tyf/cs-390/  
**Reglament:** https://dosya.tyf.gov.tr/public/upload/0/2026-07/SEMREGLEMAN11062026.pdf  
**Panel Linki:** https://gokaygunduz-gg.github.io/sem-samsun-2026/ ✅ YAYINDA

---

## Proje Gereksinimler

1. Edirne paneli gibi (https://gokaygunduz-gg.github.io/bolge-karma-2026/) canlı web paneli
2. Yeni GitHub reposu
3. Önceki tüm SEM çalışmaları buraya taşındı:
   - SEM_kontrol_liste.xlsx (349 sporcu, giriş listesi)
   - SEM_kontrol.pdf (PDF giriş listesi)
   - SEM_süre_karsilastirma.xlsx (sporcu_yildizlar ile karşılaştırma)
   - SEM_yarisma_siralama.xlsx (Excel sıralama çıktısı)
4. Panel özellikleri:
   - Bireysel sıralama (yaş grubu + cinsiyet bazlı)
   - Şehir sıralaması (toplam puan)
   - Kulüp sıralaması
   - Yarış programı görünümü
   - Canlı veri + giriş listesi modu

---

## Reglament Özeti

- **Yaş grupları:** 2008, 2009, 2010, 2011, 2012, 2013, 2014 (Kadın-Erkek)
- **50m kısıtı:** 2013-2014 doğumlular 50m yarışlara katılamaz
- **Max yarış:** Her sporcu en fazla 4 yarışa katılabilir
- **Puanlama:** 1→9, 2→7, 3→6, 4→5, 5→4, 6→3, 7→2, 8→1
- **Bireysel skor:** En iyi 3 yarış puanı toplamı
- **Eşitlik bozma:** 4. yarış puanı
- **Madalya sınırları:** 2014→8., 2013→6., 2012→4., 2011/10/09/08→3.
- **Yarış programı:** 3 gün, sabah/akşam seansları

## Yarış Programı

| Gün | Seans  | Branşlar |
|-----|--------|----------|
| 1   | Sabah  | 50m Kurbağalama, 100m Serbest, 200m Karışık |
| 1   | Akşam  | 100m Kelebek, 200m Kurbağalama, 400m Serbest |
| 2   | Sabah  | 50m Sırtüstü, 100m Kurbağalama, 200m Kelebek |
| 2   | Akşam  | 200m Sırtüstü, 800m Serbest, 1500m Serbest |
| 3   | Sabah  | 50m Kelebek, 200m Serbest, 400m Karışık |
| 3   | Akşam  | 50m Serbest, 100m Sırtüstü |

---

## Giriş Listesi Özeti (SEM_kontrol_liste.xlsx)

- 349 sporcu
- Şehir, cinsiyet, doğum yılı, 4 yarış girişi
- Giriş zamanları sporcu_yildizlar.xlsx ile karşılaştırıldı (son karşılaştırma: 155 farklı süre)

---

## Dosya Yapısı

```
2026 Temmuz SEM Final/
├── scripts/
│   ├── sem_config.py       — sabitler ve yapılandırma
│   ├── sem_entry.py        — SEM_kontrol_liste.xlsx okuyucu
│   ├── sem_score.py        — puanlama motoru
│   ├── sem_scraper.py      — canli.tyf.gov.tr/cs-390 scraper
│   └── sem_generate.py     — ana üretici (giriş+canlı → JSON)
├── panel/
│   ├── index.html          — web paneli
│   └── data.js             — gömülü veri (file:// için)
├── data/
│   └── results.json        — son sonuçlar
├── .github/workflows/
│   └── update.yml          — GitHub Actions otomatik güncelleme
├── SEM_kontrol_liste.xlsx
├── SEM_kontrol.pdf
├── SEM_süre_karsilastirma.xlsx
├── SEM_yarisma_siralama.xlsx
└── PROJE_GUNLUGU.md        — BU DOSYA
```

---

## Çalışma Geçmişi

### 2026-07-20 — Proje Başlatma

**Ne yapıldı:**
- Bölge Karmaları 2026 projesinden esinlenilerek SEM Final paneli kuruldu
- Tüm SEM çalışma dosyaları `indirilen - sil` klasöründen buraya taşındı
- Git reposu başlatıldı (main branch)
- 5 Python script + HTML panel yazıldı

**Neden:**
- Kullanıcı, Edirne yarışları için yapılan panele (https://gokaygunduz-gg.github.io/bolge-karma-2026/) benzer
  bir panel Samsun SEM Final için de istedi
- Yeni GitHub reposu istendiği için ayrı proje olarak kuruldu

**Kullanılan kaynaklar:**
- Edirne proje kodu: `C:\Users\Gokay\Desktop\Claude\Bölge Karmaları 2026\`
- SEM giriş listesi: `SEM_kontrol_liste.xlsx` (349 sporcu)
- Reglament: `SEMREGLEMAN11062026.pdf` (pdfplumber ile okutuldu)

**Önemli kararlar:**
1. Bağımsız (standalone) proje — Edirne projesine bağımlılık yok
2. Giriş listesini "simülasyon modu" olarak kullan (yarış başlamadan önce)
3. Yarış başlayınca cs-390 scraper devreye girer (sem_scraper.py)
4. Kulüp kolonu yoksa şehir = kulüp (giriş listesi sadece şehir içeriyor)

---

## Hatalar ve Çözümler

### sporcu_yildizlar.xlsx Bozulma (2026-07-20 01:09)
**Hata:** Başka bir AI süreci dosyayı yazarken kesintiye uğradı → BadZipFile hatası
**Çözüm:** `.bak` dosyası (00:59 tarihli) kopyalanıp .xlsx olarak kullanıldı
**Sonuç:** Karşılaştırma başarıyla çalıştı, 0 eşleşmeyen, 155 farklı süre

**Ders:** Her çalışmadan önce backup alınmalı.

---

## GitHub Deployment (2026-07-20 Tamamlandı)

**Repo:** https://github.com/gokaygunduz-gg/sem-samsun-2026  
**Pages:** https://gokaygunduz-gg.github.io/sem-samsun-2026/ ✅ **CANLI (built)**

### Deployment Notları
- GitHub Pages `/` (main) kaynak olarak ayarlandı (`/docs` veya alt klasör desteklenmiyor)
- Root `index.html` → `panel/index.html` yönlendirmesi yapıldı
- `git pull --rebase` ile uzak değişiklikler alındı, sonra push
- Git user ayarlandı: gokaygunduz@gmail.com / Gokay

### Validation (Tüm kontroller geçti ✅)
| Kontrol | Sonuç |
|---------|-------|
| Puan aralığı (0-27) | ✅ Tüm 348 sporcu |
| 50m kısıtı (2013-2014) | ✅ Hiç 50m kaydı yok |
| Sıralama tutarlılığı | ✅ Rank serileri tam |
| Puan mantığı (azalan top3) | ✅ |
| Sporcu sayısı | ✅ 348 (1 header) |
| Grup tamlığı | ✅ 13 grup (2008K yok = normal) |

### Çıktı İstatistikleri
- 348 sporcu, 22 şehir, 13 grup
- Top 5 şehir: İstanbul 892pt (48 sporcu), Bursa 600pt (40), Ankara 554pt (50), İzmir 396pt (34), Samsun 300pt (28)

---

## Panel v2 (2026-07-20 — İkinci Oturum)

**Ne yapıldı:**

### Bug Düzeltmeler
- **"? Serbest" bug:** Excel'deki bozuk hücre değerleri artık `KNOWN_EVENTS` filtresiyle engelleniyor (sem_entry.py)
- Branş dropdown sıraması düzeltildi: Serbest→Sırtüstü→Kurbağalama→Kelebek→Karışık

### Yeni Özellikler
1. **Şifre koruması:** Kullanıcı + Yönetici şifre sistemi (SHA-256, sem_config.py'den değiştirilebilir)
2. **Anlık + Tahmin sıralama:** Tamamlanan yarışlar "Anlık", tümü "Tahmin" olarak ayrı hesaplanıyor
3. **Yarışlar sub-tabları:** Giriş ve Sonuç ayrı görünümler
4. **Şehir detayı:** Şehire tıklayınca → "En Yüksek Puanlılar" + "Bireysel Ödüller (ilk 2)"
5. **Kulüpler sekmesi:** Puana göre + Madalya sayısına göre ayrı sıralama
6. **Program tıkla:** Yarışa tıklayınca tüm yaş/cinsiyet gruplarına göre sporcular
7. **Madalya vurgusu:** Per-event medal_cut (2014→8, 2013→6, vb.) + Bireysel ödül (🎖 ilk 2)
8. **Admin paneli:** Yönetim sekmesi (Yönetici şifresiyle) — veri durumu, JSON indir

### Teknik
- JSON'a `athletes_current`, `events_current`, `city_rankings.athlete_list`, `auth` alanları eklendi
- `sem_score.py` ve `sem_generate.py`: `is_live` flag'i tüm event zincirinden geçiyor
- `sem_config.py`: şifre yönetimi + SHA-256 hash hesaplama
- Tüm kontroller 10/10 geçti ✅

---

## Auth Sistemi v2 (2026-07-20 — Üçüncü Oturum)

**Ne yapıldı:**

### Kullanıcı Adı + Şifre Sistemi
- Auth ekranı: **Giriş Yap** + **Kayıt Ol** iki ayrı tab
- Giriş: kullanıcı adı + şifre (SHA-256)
- Kayıt: admin onayı gerekli (approved=false); admin panelden onaylama
- `localStorage['sem_users']`: kullanıcı DB (hash'li şifre, rol, onay durumu)
- `localStorage['sem_session']`: aktif oturum {username, role}
- `localStorage['sem_seed_ver']`: data.js generated_at ile tohum takibi

### Kullanıcılar (sem_config.py USERS)
| Kullanıcı adı | Rol | Şifre |
|---|---|---|
| Admin | admin | Koray2013 |
| gokaygunduz | user | Asya2017 |
| Vamos | user | Vamos202607 |

### Admin Kullanıcı Yönetimi
- Kullanıcı listesi: tüm onaylı kullanıcılar
- Şifre değiştir, rol değiştir (admin ↔ kullanıcı), kullanıcı sil
- Kayıt aç/kapat butonu (`localStorage['sem_reg_open']`)
- Onay bekleyen kayıtlar ayrı bölümde gösterilir
- "users_config.py" indir butonu (kalıcı ekleme için)

### Teknik Notlar
- `initial_users` tohum: data.js yeniden üretilince (yeni generated_at) tüm cihazlarda yeniden seeder
- Yerel eklentiler (`local: true` flag) tohum sırasında korunur
- Kayıt: admin onayı olmadan giriş yapılamaz
- Admin kendi hesabını silemez / kendi rolünü değiştiremez

---

## Gelecek Adımlar

1. ✅ GitHub reposu oluştur: `gokaygunduz-gg/sem-samsun-2026`
2. ✅ GitHub Pages aktive et (main branch, / kök)
3. ✅ GitHub Actions ile auto-update (yarış süresince her 5 dk)
4. ✅ Panel v2: şifre, madalya, forecast/anlık, şehir/kulüp detay
5. ✅ Auth v2: kullanıcı adı + kayıt/giriş + admin kullanıcı yönetimi
6. ⏳ Yarış başlangıcında (28 Temmuz): cs-390 URL aktif olduktan sonra canlı test
7. ⏳ Eğer URL değişirse: `sem_config.py` içindeki `RACE_URL` güncelle

---

## Notlar

- Kullanıcı başka bir AI kullananıyor (paralel çalışıyor), o AI bazen dosyaları bozuyor/siliyor
- Her major değişiklikten önce backup alınacak
- Fable 5 modeli ile kod review yapılacak
- Panel mobil-öncelikli tasarlanmalı (antrenörler telefonda bakıyor)
