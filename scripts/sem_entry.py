"""
SEM giriş listesi okuyucu.
SEM_kontrol_liste.xlsx → sporcu listesi (dict listesi).

Sütun yapısı (1-indexed):
  1: S.     2: Şehir   3: Cinsiyet   4: Ad Soyad
  5: YB     6: TC No
  7: Yarış1  8: Süre1  9: Yarış2  10: Süre2
  11: Yarış3 12: Süre3 13: Yarış4 14: Süre4
"""

import openpyxl
from sem_config import ENTRY_PATH, NO_50M_GROUPS, PROGRAM

# Giriş listesinde yalnızca program içindeki branşlara izin ver
KNOWN_EVENTS = {b for _, _, b in PROGRAM}

TR_MAP = str.maketrans({
    "ğ": "g", "Ğ": "G", "ı": "i", "İ": "i",
    "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
    "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
})


def norm(s: str) -> str:
    if not s:
        return ""
    return str(s).translate(TR_MAP).lower().strip()


def to_sec(t) -> float | None:
    if not t:
        return None
    s = str(t).strip().upper()
    if s in ("NT", "-", "DNS", "DQ", ""):
        return None
    try:
        if ":" in s:
            parts = s.split(":")
            return int(parts[0]) * 60 + float(parts[1])
        return float(s)
    except Exception:
        return None


def load_entry_list(path: str = ENTRY_PATH) -> list[dict]:
    """
    Giriş listesini yükler.
    Dönüş: her sporcu için dict listesi:
      {name, city, gender, yb, events: [{event, time_raw, time_sec}]}
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active

    swimmers = []
    for r in range(2, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, 15)]
        if not any(vals):
            continue

        city   = vals[1] or ""
        gender = vals[2] or ""   # Bayan / Erkek
        name   = vals[3] or ""
        yb     = str(vals[4]).strip() if vals[4] is not None else ""  # "14", "13", ...
        if not name or not yb:
            continue

        # gender normalize → Kadın/Erkek
        gender_norm = "Erkek" if norm(gender) == "erkek" else "Kadın"

        events = []
        for i in range(4):
            ev   = vals[6 + i * 2]
            time = vals[7 + i * 2]
            if not ev:
                continue
            ev_str = str(ev).strip()
            # Bilinmeyen branşı atla (örn: "? Serbest" gibi bozuk hücreler)
            if ev_str not in KNOWN_EVENTS:
                continue
            # 2014-2013 50m oynamaz
            if yb in NO_50M_GROUPS and ev_str.startswith("50m"):
                continue
            t_sec = to_sec(time)
            events.append({
                "event":    ev_str,
                "time_raw": str(time).strip() if time else "NT",
                "time_sec": t_sec,
            })

        swimmers.append({
            "name":   name.strip(),
            "city":   str(city).strip(),
            "gender": gender_norm,
            "yb":     yb,
            "events": events,
        })

    wb.close()
    return swimmers


if __name__ == "__main__":
    swimmers = load_entry_list()
    print(f"Toplam sporcu: {len(swimmers)}")
    from collections import Counter
    grp = Counter((s["yb"], s["gender"]) for s in swimmers)
    for k, v in sorted(grp.items()):
        print(f"  {k}: {v}")
