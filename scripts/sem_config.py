"""
SEM Türkiye Finali 2026 — Samsun
Tüm sabitler ve yapılandırma buradadır.
"""
import os
import hashlib


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ── Kullanıcılar (değiştirin, sonra sem_generate.py çalıştırın) ──────────────
# role: "admin" veya "user"
USERS = [
    {"username": "Admin",       "role": "admin", "password": "Koray2013"},
    {"username": "gokaygunduz", "role": "user",  "password": "Asya2017"},
    {"username": "Vamos",       "role": "user",  "password": "Vamos202607"},
]

# Herkes kayıt olabilsin mi? (True = evet, admin onaylar; False = yalnızca admin ekler)
REGISTRATION_OPEN = True
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY_PATH     = os.path.join(BASE_DIR, "SEM_kontrol_liste.xlsx")
PANEL_DIR      = os.path.join(BASE_DIR, "panel")
DATA_DIR       = os.path.join(BASE_DIR, "data")
OUT_JSON       = os.path.join(DATA_DIR, "results.json")
OUT_DATA_JS    = os.path.join(PANEL_DIR, "data.js")

RACE_URL       = "https://canli.tyf.gov.tr/tyf/cs-390/"
COMP_NAME      = "SEM Türkiye Finali 2026"
COMP_LOCATION  = "Samsun Olimpik Yüzme Havuzu"
COMP_DATES     = "28-29-30 Temmuz 2026"

# Yıl grubu label
AGE_LABELS = {
    "08": "2008 (18 Yaş)", "09": "2009 (17 Yaş)",
    "10": "2010 (16 Yaş)", "11": "2011 (15 Yaş)",
    "12": "2012 (14 Yaş)", "13": "2013 (13 Yaş)",
    "14": "2014 (12 Yaş)",
}

# Puan tablosu (bireysel sıralama → puan)
POINTS = {1: 9, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}

# 2014-2013 doğumlular 50m yarışlara katılamaz
NO_50M_GROUPS = {"14", "13"}

# Madalya sınırları (her yaş grubunda kaçıncıya kadar)
MEDAL_CUTOFFS = {
    "14": 8, "13": 6, "12": 4,
    "11": 3, "10": 3, "09": 3, "08": 3,
}

# Yarış programı (gün, seans, branş)
PROGRAM = [
    (1, "Sabah",  "50m Kurbağalama"),
    (1, "Sabah",  "100m Serbest"),
    (1, "Sabah",  "200m Karışık"),
    (1, "Akşam",  "100m Kelebek"),
    (1, "Akşam",  "200m Kurbağalama"),
    (1, "Akşam",  "400m Serbest"),
    (2, "Sabah",  "50m Sırtüstü"),
    (2, "Sabah",  "100m Kurbağalama"),
    (2, "Sabah",  "200m Kelebek"),
    (2, "Akşam",  "200m Sırtüstü"),
    (2, "Akşam",  "800m Serbest"),
    (3, "Sabah",  "50m Kelebek"),
    (3, "Sabah",  "200m Serbest"),
    (3, "Sabah",  "400m Karışık"),
    (3, "Akşam",  "50m Serbest"),
    (3, "Akşam",  "100m Sırtüstü"),
    (3, "Akşam",  "1500m Serbest"),
]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}
HTTP_TIMEOUT = 30
