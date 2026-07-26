"""
28 Temmuz 08:30-09:30 arası start listesi recheck.

TYF start listesini mevcut DB ile karşılaştırır:
- Daha önce çıkarılan 18 sporcu geri döndü mü?
- Tamamen yeni sporcu var mı?
Varsa Excel'e ekler, paneli günceller.

GitHub Actions tarafından çağrılır; çıktı commit + push için kullanılır.
"""
import sys, os, re, unicodedata, io, json, requests, shutil, openpyxl
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

import pdfplumber
from sem_config import HTTP_HEADERS, BASE_DIR

BASE_URL     = "https://canli.tyf.gov.tr/tyf/cs-390"
MAIN_XLSX    = os.path.join(BASE_DIR, "SEM_kontrol_liste.xlsx")
REMOVED_JSON = os.path.join(BASE_DIR, "data", "removed_athletes.json")

CODE_MAP = {
     1:("50m Kurbağalama","Kadın"),  2:("50m Kurbağalama","Erkek"),
     3:("100m Serbest","Kadın"),     4:("100m Serbest","Erkek"),
     5:("200m Karışık","Kadın"),     6:("200m Karışık","Erkek"),
     7:("100m Kelebek","Kadın"),     8:("100m Kelebek","Erkek"),
     9:("200m Kurbağalama","Kadın"),10:("200m Kurbağalama","Erkek"),
    11:("400m Serbest","Kadın"),    12:("400m Serbest","Erkek"),
    13:("50m Sırtüstü","Kadın"),    14:("50m Sırtüstü","Erkek"),
    15:("100m Kurbağalama","Kadın"),16:("100m Kurbağalama","Erkek"),
    17:("200m Kelebek","Kadın"),    18:("200m Kelebek","Erkek"),
    19:("200m Sırtüstü","Kadın"),   20:("200m Sırtüstü","Erkek"),
    21:("800m Serbest","Kadın"),    22:("800m Serbest","Erkek"),
    23:("50m Kelebek","Kadın"),     24:("50m Kelebek","Erkek"),
    25:("200m Serbest","Kadın"),    26:("200m Serbest","Erkek"),
    27:("400m Karışık","Kadın"),    28:("400m Karışık","Erkek"),
    29:("50m Serbest","Kadın"),     30:("50m Serbest","Erkek"),
    31:("100m Sırtüstü","Kadın"),   32:("100m Sırtüstü","Erkek"),
    33:("1500m Serbest","Kadın"),   34:("1500m Serbest","Erkek"),
}

LINE_RE = re.compile(
    r'^\d+\s+(.+?)\s+(0[89]|1[0-4])\s+([\wÇĞİÖŞÜçğışöşüI]+)\s+((?:\d{1,2}:)?\d{1,2}\.\d{2}|NT)\s*$'
)

CITY_FIXES = {"istanbul": "İstanbul", "izmir": "İzmir", "eskisehir": "Eskişehir",
              "canakkale": "Çanakkale", "tekirdag": "Tekirdağ", "kahramanmaras": "Kahramanmaraş"}


def norm(s):
    if not s: return ""
    s = str(s).upper().strip()
    for a, b in [("Ç","C"),("ç","C"),("Ğ","G"),("ğ","G"),("İ","I"),("ı","I"),
                 ("Ö","O"),("ö","O"),("Ş","S"),("ş","S"),("Ü","U"),("ü","U")]:
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


def fix_city(c):
    return CITY_FIXES.get(c.lower().strip(), c.strip())


# ── Mevcut DB'yi norm anahtarlarına çevir ─────────────────────────────────
def load_db_keys():
    wb = openpyxl.load_workbook(MAIN_XLSX)
    ws = wb["SEM Kontrol Listesi"]
    keys = set()
    for r in range(2, ws.max_row + 1):
        name = ws.cell(r, 4).value
        yb   = str(ws.cell(r, 5).value or "").strip()
        if name:
            keys.add((norm(str(name)), yb))
    return keys, ws.max_row, wb, ws


# ── TYF start listelerini parse et ────────────────────────────────────────
def parse_all_startlists():
    """(norm_name, yb) → {name_raw, city, events: [(brans, time)]}"""
    tyf = {}
    for code in range(1, 35):
        url = f"{BASE_URL}/StartList_{code}.pdf"
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
            if resp.status_code != 200: continue
            brans, cinsiyet = CODE_MAP.get(code, ("?","?"))
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    for line in text.split("\n"):
                        m = LINE_RE.match(line.strip())
                        if not m: continue
                        name_raw = m.group(1).strip()
                        yb       = m.group(2)
                        city_raw = m.group(3)
                        time_raw = m.group(4)
                        if len(name_raw) < 3: continue
                        key = (norm(name_raw), yb)
                        if key not in tyf:
                            tyf[key] = {
                                "name": name_raw,
                                "yb":   yb,
                                "city": fix_city(city_raw),
                                "events": [],
                                "cinsiyet": cinsiyet,
                            }
                        tyf[key]["events"].append((brans, time_raw))
        except Exception as e:
            print(f"  UYARI kod {code}: {e}")
    return tyf


# ── Sporcuyu Excel'e ekle ─────────────────────────────────────────────────
def add_athlete_to_excel(ws, next_num, ath_data, removed_record=None):
    """removed_record varsa oradan TC/kulüp al, yoksa boş bırak."""
    r = ws.max_row + 1

    # Orijinal kayıt varsa ondan al
    tc    = removed_record["tc"]    if removed_record else ""
    kulup = removed_record["kulup"] if removed_record else ""

    # Branşları al (max 4)
    events = ath_data["events"][:4]
    while len(events) < 4:
        events.append(("", ""))

    ws.cell(r, 1).value  = next_num
    ws.cell(r, 2).value  = ath_data["city"]
    ws.cell(r, 3).value  = "Bayan" if ath_data["cinsiyet"] == "Kadın" else "Erkek"
    ws.cell(r, 4).value  = ath_data["name"]
    ws.cell(r, 5).value  = ath_data["yb"]
    ws.cell(r, 6).value  = tc or ""
    for i, (ev, sure) in enumerate(events):
        ws.cell(r, 7  + i*2).value = ev   or None
        ws.cell(r, 8  + i*2).value = sure or None
    ws.cell(r, 16).value = kulup or None
    ws.cell(r, 17).value = ath_data["city"]
    ws.cell(r, 18).value = f"=Q{r}=B{r}"
    ws.cell(r, 20).value = f"=MATCH(D{r},[1]Manual!$A:$A,0)"
    return r


# ── ANA KONTROL ───────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Start listesi yeniden kontrol ediliyor...")

    db_keys, last_row, wb, ws = load_db_keys()
    print(f"  Mevcut DB: {len(db_keys)} sporcu")

    removed = []
    if os.path.exists(REMOVED_JSON):
        with open(REMOVED_JSON, encoding="utf-8") as f:
            removed = json.load(f)
    removed_keys = {(norm(a["ad_soyad"]), a["yb"]): a for a in removed}
    print(f"  Yedekteki çıkarılmış sporcu: {len(removed_keys)}")

    print("  TYF start listeleri indiriliyor...")
    tyf = parse_all_startlists()
    print(f"  TYF'de {len(tyf)} sporcu")

    # DB'de olmayan ama TYF'de olan sporcular
    new_in_tyf = {k: v for k, v in tyf.items() if k not in db_keys}
    print(f"  DB'de olmayan: {len(new_in_tyf)} sporcu")

    if not new_in_tyf:
        print("  ✅ Yeni sporcu yok. İşlem tamamlandı.")
        return False  # Değişiklik yok

    # Geri dönenler (daha önce çıkarılan 18'den)
    returned   = {k: v for k, v in new_in_tyf.items() if k in removed_keys}
    brand_new  = {k: v for k, v in new_in_tyf.items() if k not in removed_keys}

    print(f"\n  *** YENİ SPORCU BULUNDU ***")
    print(f"  Yedekten dönen : {len(returned)}")
    print(f"  Tamamen yeni   : {len(brand_new)}")

    # Excel'e ekle
    next_num = (ws.cell(ws.max_row, 1).value or 0) + 1
    added = []

    for key, ath in {**returned, **brand_new}.items():
        removed_rec = removed_keys.get(key)
        added_row   = add_athlete_to_excel(ws, next_num, ath, removed_rec)
        next_num   += 1
        tag = "(yedekten döndü)" if removed_rec else "(yeni sporcu)"
        print(f"  + Eklendi satır {added_row}: {ath['name']} YB={ath['yb']} {tag}")
        added.append(key)

    # Yedek JSON güncelle: geri dönenler çıkar
    if returned:
        remaining_removed = [a for a in removed if (norm(a["ad_soyad"]), a["yb"]) not in returned]
        with open(REMOVED_JSON, "w", encoding="utf-8") as f:
            json.dump(remaining_removed, f, ensure_ascii=False, indent=2)
        print(f"  removed_athletes.json güncellendi: {len(remaining_removed)} kaldı")

    wb.save(MAIN_XLSX)
    print(f"  Excel kaydedildi: {MAIN_XLSX}")
    return True  # Değişiklik var → panel yeniden üretilmeli


if __name__ == "__main__":
    changed = main()
    sys.exit(0 if changed else 2)   # exit 2 = değişiklik yok (workflow bunu yakalar)
