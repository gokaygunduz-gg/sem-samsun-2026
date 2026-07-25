"""
SEM_kontrol.pdf ↔ SEM_kontrol_liste.xlsx karşılaştırması.

Her sporcunun PDF'de kayıtlı branşlarını Excel ile kıyaslar.
Eksik/fazla branşları raporlar.

Çalıştır:
    python scripts/check_pdf_vs_excel.py
"""
import sys, re, unicodedata, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pdfplumber
from sem_entry import load_entry_list
from sem_config import BASE_DIR

PDF_PATH = os.path.join(BASE_DIR, "SEM_kontrol.pdf")

# ── Etkinlik kodu haritası (PDF doğrulamasından) ───────────────────────────
CODE_MAP = {
     1: ("50m Kurbağalama",  "Kadın"),   2: ("50m Kurbağalama",  "Erkek"),
     3: ("100m Serbest",     "Kadın"),   4: ("100m Serbest",     "Erkek"),
     5: ("200m Karışık",     "Kadın"),   6: ("200m Karışık",     "Erkek"),
     7: ("100m Kelebek",     "Kadın"),   8: ("100m Kelebek",     "Erkek"),
     9: ("200m Kurbağalama", "Kadın"),  10: ("200m Kurbağalama", "Erkek"),
    11: ("400m Serbest",     "Kadın"),  12: ("400m Serbest",     "Erkek"),
    13: ("50m Sırtüstü",     "Kadın"),  14: ("50m Sırtüstü",     "Erkek"),
    15: ("100m Kurbağalama", "Kadın"),  16: ("100m Kurbağalama", "Erkek"),
    17: ("200m Kelebek",     "Kadın"),  18: ("200m Kelebek",     "Erkek"),
    19: ("200m Sırtüstü",    "Kadın"),  20: ("200m Sırtüstü",    "Erkek"),
    21: ("800m Serbest",     "Kadın"),  22: ("800m Serbest",     "Erkek"),
    23: ("50m Kelebek",      "Kadın"),  24: ("50m Kelebek",      "Erkek"),
    25: ("200m Serbest",     "Kadın"),  26: ("200m Serbest",     "Erkek"),
    27: ("400m Karışık",     "Kadın"),  28: ("400m Karışık",     "Erkek"),
    29: ("50m Serbest",      "Kadın"),  30: ("50m Serbest",      "Erkek"),
    31: ("100m Sırtüstü",    "Kadın"),  32: ("100m Sırtüstü",    "Erkek"),
    33: ("1500m Serbest",    "Kadın"),  34: ("1500m Serbest",    "Erkek"),
}

SKIP_LINES = {
    "SPORCU EĞİTİM", "Giriş Kontrol", "Splash Meet", "Erkekler",
    "Bayanlar", "YB", "Sayfa",
}
CITY_NAMES = {
    "Adana", "Ankara", "Bursa", "İstanbul", "İzmir", "Samsun",
    "Eskişehir", "Kocaeli", "Antalya", "Mersin", "Trabzon",
    "Konya", "Kayseri", "Diyarbakır", "Denizli", "Gaziantep",
    "Hatay", "Manisa", "Balıkesir", "Tekirdağ", "Sakarya",
}

# YB + hemen ardından TC numarası (≥6 basamak) — event satırlarındaki sürelerden ayırır
YB_RE    = re.compile(r'\b(08|09|10|11|12|13|14)\b\s*\d{6,}')
YB_VAL   = re.compile(r'\b(08|09|10|11|12|13|14)\b')
CODE_RE  = re.compile(r'\((\d{1,2})\)\s+([\d:\.]+|NT)')


def norm(s: str) -> str:
    if not s:
        return ""
    s = str(s).upper().strip()
    tr = str.maketrans("ÇĞİIÖŞÜçğışöşü", "CGIIOSUcgiossu")
    s = s.translate(tr)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


def parse_pdf(path: str) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """
    PDF'den (norm_name, yb, [(brans, sure), ...]) listesi döndürür.
    """
    athletes = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i]

                # Başlık/footer atla
                if any(kw in line for kw in SKIP_LINES) or line.strip() in CITY_NAMES:
                    i += 1
                    continue

                yb_m = YB_RE.search(line)
                if not yb_m:
                    i += 1
                    continue

                yb = yb_m.group(1)
                name_raw   = line[:yb_m.start()].strip()
                name_clean = re.sub(r'\d', '', name_raw).strip()
                name_norm  = norm(name_clean)
                if len(name_norm) < 4:
                    i += 1
                    continue

                # Bu satır + sonraki satırdan etkinlik topla
                block = line
                if i + 1 < len(lines):
                    nxt = lines[i + 1]
                    nxt_yb = YB_RE.search(nxt)
                    nxt_name = re.sub(r'\d', '', nxt[:nxt_yb.start()].strip()).strip() if nxt_yb else ""
                    if not (nxt_yb and len(norm(nxt_name)) >= 4):
                        block += " " + nxt

                events = []
                for m in CODE_RE.finditer(block):
                    code = int(m.group(1))
                    sure = m.group(2)
                    if code in CODE_MAP:
                        brans, _ = CODE_MAP[code]
                        events.append((brans, sure))

                if events:
                    athletes.append((name_norm, yb, events))
                i += 1

    return athletes


def main():
    print("PDF okunuyor...")
    pdf_athletes = parse_pdf(PDF_PATH)
    print(f"  PDF'den {len(pdf_athletes)} sporcu kaydı çekildi")

    print("Excel okunuyor...")
    excel_athletes = load_entry_list()
    print(f"  Excel'den {len(excel_athletes)} sporcu yüklendi")

    # Excel: (norm_name, yb) → branş seti
    excel_map: dict[tuple, set] = {}
    for sw in excel_athletes:
        key = (norm(sw["name"]), sw["yb"])
        excel_map[key] = set(ev["event"] for ev in sw["events"])

    missing_in_excel = []
    extra_in_excel   = []
    not_found        = []

    for name_norm, yb, pdf_evs in pdf_athletes:
        key = (name_norm, yb)
        if key not in excel_map:
            not_found.append((name_norm, yb, pdf_evs))
            continue
        ex_evs  = excel_map[key]
        pdf_set = {e[0] for e in pdf_evs}

        missing = pdf_set - ex_evs
        extra   = ex_evs - pdf_set
        if missing:
            missing_in_excel.append((name_norm, yb, sorted(missing)))
        if extra:
            extra_in_excel.append((name_norm, yb, sorted(extra)))

    SEP = "─" * 65
    print(f"\n{'='*65}")
    print(f"  PDF ↔ EXCEL KARŞILAŞTIRMA RAPORU")
    print(f"{'='*65}")
    print(f"  Excel'de EKSİK (PDF'de var, Excel'e girmemiş) : {len(missing_in_excel)} sporcu")
    print(f"  Excel'de FAZLA (Excel'de var, PDF'de kayıtlı değil): {len(extra_in_excel)} sporcu")
    print(f"  PDF sporcusu Excel'de eşleşemedi            : {len(not_found)} adet")
    print(f"{'='*65}")

    if missing_in_excel:
        print(f"\n{'—'*65}")
        print(f"  ⚠  EXCEL'DE EKSİK BRANŞLAR ({len(missing_in_excel)} sporcu)")
        print(f"{'—'*65}")
        for name, yb, evs in sorted(missing_in_excel, key=lambda x: (x[1], x[0])):
            print(f"  {name:35s} YB={yb}  →  {', '.join(evs)}")

    if extra_in_excel:
        print(f"\n{'—'*65}")
        print(f"  ⚠  EXCEL'DE FAZLA BRANŞLAR ({len(extra_in_excel)} sporcu)")
        print(f"{'—'*65}")
        for name, yb, evs in sorted(extra_in_excel, key=lambda x: (x[1], x[0])):
            print(f"  {name:35s} YB={yb}  →  {', '.join(evs)}")

    if not_found:
        print(f"\n{'—'*65}")
        print(f"  ℹ  PDF'DE OLUP EXCEL'DE BULUNAMAYANLAR ({len(not_found)} — isim farkı olabilir)")
        print(f"{'—'*65}")
        for name, yb, evs in not_found:
            ev_str = ", ".join(f"{e[0]}" for e in evs)
            print(f"  {name:35s} YB={yb}  →  {ev_str}")


if __name__ == "__main__":
    main()
