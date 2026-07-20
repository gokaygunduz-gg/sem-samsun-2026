"""
SEM canlı yarış scraper'ı.
canli.tyf.gov.tr/tyf/cs-390/ → yarış sonuçları (dict listesi)

Akış:
  1. Ana sayfayı çek → ResultList_N.pdf linklerini bul
  2. Her PDF'i indir → pdfplumber ile parse et
  3. Sporcu ismi/yb/kulüp/süre/sıra extract et
"""

import re
import logging
from collections import namedtuple

import requests
import pdfplumber
from bs4 import BeautifulSoup

from sem_config import RACE_URL, HTTP_HEADERS, HTTP_TIMEOUT, NO_50M_GROUPS

logger = logging.getLogger(__name__)

TR_MAP = str.maketrans({
    "ğ": "g", "Ğ": "G", "ı": "i", "İ": "i",
    "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
    "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
})


def _norm(s: str) -> str:
    return str(s).translate(TR_MAP).lower().strip() if s else ""


# Stil normalize haritası
_STROKE_MAP = {
    "serbest":     "Serbest",
    "sirtüstü":    "Sırtüstü",  "sirtustu":    "Sırtüstü",
    "sirtustü":    "Sırtüstü",  "sirtüstu":    "Sırtüstü",
    "kurbagalama": "Kurbağalama",
    "kelebek":     "Kelebek",
    "karisik":     "Karışık",
}

_GENDER_MAP = {
    "erkekler": "Erkek", "oglanlar": "Erkek",
    "kizlar":   "Kadın", "kadinlar": "Kadın", "bayanlar": "Kadın",
}

EventInfo = namedtuple("EventInfo", ["gender", "distance", "stroke", "pdf_seq"])


def _parse_event_from_text(text: str) -> tuple[str | None, int | None, str | None]:
    """'Erkekler 100m Serbest' gibi metinden (gender, distance, stroke) çıkarır."""
    n = _norm(text)
    gender = None
    for k, v in _GENDER_MAP.items():
        if k in n:
            gender = v
            break

    dist_m = re.search(r"(\d{2,4})\s*m\b", n)
    distance = int(dist_m.group(1)) if dist_m else None

    stroke = None
    for k, v in _STROKE_MAP.items():
        if k in n:
            stroke = v
            break

    return gender, distance, stroke


def fetch_race_page(url: str = RACE_URL) -> dict:
    """
    Ana yarış sayfasını çeker ve ResultList PDF linklerini + event bilgisini döndürür.

    Dönüş: {"events": [(pdf_url, EventInfo), ...], "title": str}
    """
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Sayfa çekilemedi: {url} — {e}")
        return {"events": [], "title": ""}

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.text.strip() if soup.title else ""

    base_url = url.rstrip("/")
    events = []

    # ResultList_N.pdf linklerini bul
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "ResultList" in href and ".pdf" in href.lower():
            # Tam URL oluştur
            if href.startswith("http"):
                pdf_url = href
            else:
                pdf_url = base_url + "/" + href.lstrip("/")

            # PDF sıra numarasını al (ResultList_5.pdf → 5)
            seq_m = re.search(r"ResultList_?(\d+)\.pdf", href, re.I)
            pdf_seq = int(seq_m.group(1)) if seq_m else 0

            # Event bilgisini satır context'inden çıkar
            parent = a.find_parent("tr") or a.find_parent("td") or a.parent
            row_text = parent.get_text(" ", strip=True) if parent else ""
            gender, distance, stroke = _parse_event_from_text(row_text)

            events.append((pdf_url, EventInfo(gender, distance, stroke, pdf_seq)))

    logger.info(f"Bulunan ResultList PDF sayısı: {len(events)}")
    return {"events": events, "title": title}


def _parse_result_pdf(pdf_bytes: bytes, event_info: EventInfo) -> list[dict]:
    """
    Tek bir ResultList PDF'inden sonuçları çıkarır.

    Dönüş: [{"name", "yb", "city", "rank", "time_raw", "time_sec", "gender", "distance", "stroke"}, ...]
    """
    import io

    results = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                # Önce tablo olarak dene
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if not row:
                                continue
                            r = _parse_result_row(row, event_info)
                            if r:
                                results.append(r)
                else:
                    # Tablo yoksa metin parse et
                    text = page.extract_text() or ""
                    for line in text.split("\n"):
                        r = _parse_result_line(line, event_info)
                        if r:
                            results.append(r)
    except Exception as e:
        logger.error(f"PDF parse hatası: {e}")

    return results


def _to_sec(t: str) -> float | None:
    if not t:
        return None
    t = str(t).strip().upper()
    if t in ("NT", "DNS", "DQ", "DSQ", ""):
        return None
    try:
        t = t.replace(",", ".")
        if ":" in t:
            parts = t.split(":")
            return int(parts[0]) * 60 + float(parts[1])
        return float(t)
    except Exception:
        return None


def _parse_result_row(row: list, event_info: EventInfo) -> dict | None:
    """
    Tablo satırından sporcu bilgisi çıkarır.
    TYF PDF formatı genellikle: [Sıra, İsim, YB, Kulüp, Süre, (Puan)]
    """
    if not row or len(row) < 4:
        return None

    # Temizle
    cells = [str(c).strip() if c else "" for c in row]

    # Sıra (1. sütun genelde rakam)
    rank_str = cells[0]
    if not re.match(r"^\d+$", rank_str):
        return None
    rank = int(rank_str)

    # İsim (2. sütun)
    name = cells[1] if len(cells) > 1 else ""
    if not name or len(name) < 3:
        return None

    # YB — 4 haneli veya 2 haneli yıl
    yb = ""
    for cell in cells[2:5]:
        m = re.match(r"^(20\d{2}|\d{2})$", cell.strip())
        if m:
            raw_yb = m.group(1)
            yb = raw_yb[-2:]  # 2013 → "13"
            break

    # Süre — MM:SS.cc veya SS.cc formatı
    time_raw = ""
    time_sec = None
    for cell in reversed(cells[2:]):
        ts = _to_sec(cell)
        if ts is not None:
            time_raw = cell
            time_sec = ts
            break

    # Kulüp / Şehir
    city = cells[3] if len(cells) > 3 else ""

    if not time_raw and not yb:
        return None

    return {
        "name":     name,
        "yb":       yb,
        "city":     city,
        "rank":     rank,
        "time_raw": time_raw or "NT",
        "time_sec": time_sec,
        "gender":   event_info.gender,
        "distance": event_info.distance,
        "stroke":   event_info.stroke,
    }


def _parse_result_line(line: str, event_info: EventInfo) -> dict | None:
    """
    Metin satırından sporcu bilgisi çıkarır (tablo yoksa fallback).
    """
    line = line.strip()
    if not line:
        return None
    # İlk token rakam olmalı (sıra numarası)
    parts = line.split()
    if not parts or not re.match(r"^\d+$", parts[0]):
        return None
    rank = int(parts[0])
    if rank > 100:
        return None

    # Süre arama: MM:SS.cc veya SS.cc
    time_m = re.search(r"\b(\d{1,2}:\d{2}\.\d{2}|\d{2}\.\d{2})\b", line)
    if not time_m:
        return None
    time_raw = time_m.group(1)
    time_sec = _to_sec(time_raw)

    # YB
    yb_m = re.search(r"\b(20\d{2}|\d{2})\b", line)
    yb = yb_m.group(1)[-2:] if yb_m else ""

    # İsim: sıra ile yb arasındaki metin
    name_part = line[len(parts[0]):].strip()
    # YB'yi ve sonrasını çıkar
    if yb_m:
        name_part = name_part[:yb_m.start()].strip()
    # Süreyi çıkar
    name_part = name_part.replace(time_raw, "").strip()

    name = " ".join(name_part.split())
    if len(name) < 3:
        return None

    return {
        "name":     name,
        "yb":       yb,
        "city":     "",
        "rank":     rank,
        "time_raw": time_raw,
        "time_sec": time_sec,
        "gender":   event_info.gender,
        "distance": event_info.distance,
        "stroke":   event_info.stroke,
    }


def scrape_live(url: str = RACE_URL, verbose: bool = True) -> list[dict]:
    """
    Canlı yarış verilerini çeker ve düz sonuç listesi döndürür.

    Dönüş: [{"name", "yb", "city", "rank", "time_raw", "time_sec",
              "gender", "distance", "stroke", "event"}, ...]
    """
    page = fetch_race_page(url)
    if not page["events"]:
        if verbose:
            print("  ⚠ Henüz yayınlanmış sonuç yok.")
        return []

    all_results = []
    for pdf_url, event_info in page["events"]:
        if verbose:
            g = event_info.gender or "?"
            d = event_info.distance or "?"
            s = event_info.stroke or "?"
            print(f"  PDF çekiliyor: {pdf_url.split('/')[-1]} ({g} {d}m {s})")
        try:
            resp = requests.get(pdf_url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            rows = _parse_result_pdf(resp.content, event_info)
            for r in rows:
                event_label = f"{r.get('distance', '?')}m {r.get('stroke', '?')}"
                r["event"] = event_label
            all_results.extend(rows)
            if verbose:
                print(f"    → {len(rows)} sonuç")
        except Exception as e:
            logger.error(f"PDF indirilemedi: {pdf_url} — {e}")

    if verbose:
        print(f"  ✓ Toplam canlı sonuç: {len(all_results)}")
    return all_results


def fetch_lenex_url(url: str = RACE_URL) -> str | None:
    """
    Ana sayfada Lenex/LXF dosyası linkini arar.
    Bulamazsa yaygın path'leri dener. Yoksa None döner.
    """
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith((".lxf", ".lef")):
                if href.startswith("http"):
                    return href
                return url.rstrip("/") + "/" + href.lstrip("/")
    except Exception as e:
        logger.warning(f"Lenex link arama hatası: {e}")

    base = url.rstrip("/")
    for path in ["/Results.lxf", "/ResultsLenex.lxf", "/EntryList.lxf", "/lenex.lxf", "/result.lxf"]:
        candidate = base + path
        try:
            r = requests.head(candidate, headers=HTTP_HEADERS, timeout=10)
            if r.status_code == 200:
                return candidate
        except Exception:
            continue
    return None


def parse_lenex(content: bytes) -> list[dict]:
    """
    Lenex/LXF içeriğini parse eder (ZIP veya düz XML).

    Dönüş: [{"name", "yb", "city", "rank", "time_raw", "time_sec", "gender", "event"}, ...]
    """
    import io
    import zipfile
    import xml.etree.ElementTree as ET

    xml_bytes = None
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in sorted(zf.namelist()):
                if name.lower().endswith((".xml", ".lef")):
                    xml_bytes = zf.read(name)
                    break
    except zipfile.BadZipFile:
        xml_bytes = content

    if not xml_bytes:
        logger.error("Lenex: XML içerik bulunamadı")
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.error(f"Lenex XML parse hatası: {e}")
        return []

    # Namespace strip
    def strip_ns(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    def fnd(el, tag):
        for child in el:
            if strip_ns(child.tag) == tag:
                return child
        return None

    def fndall(el, tag):
        return [c for c in el if strip_ns(c.tag) == tag]

    def deep(el, *path):
        cur = el
        for p in path:
            cur = fnd(cur, p)
            if cur is None:
                return None
        return cur

    def deepall(el, *path):
        cur = el
        for p in path[:-1]:
            cur = fnd(cur, p)
            if cur is None:
                return []
        return fndall(cur, path[-1]) if cur is not None else []

    _STROKE_LENEX = {
        "free": "Serbest", "back": "Sırtüstü", "breast": "Kurbağalama",
        "fly": "Kelebek", "medley": "Karışık",
    }

    # Athlete lookup — tüm MEET altındaki ATHLETES
    athlete_map: dict[str, dict] = {}
    for meet in deepall(root, "MEETS", "MEET") or deepall(root, "MEET"):
        for ath in deepall(meet, "ATHLETES", "ATHLETE"):
            ath_id    = ath.get("athleteid", "")
            lastname  = ath.get("lastname", "")
            firstname = ath.get("firstname", "")
            name      = (lastname + " " + firstname).strip()
            bd        = ath.get("birthdate", "")  # "2013-05-12"
            yb        = bd[:4][-2:] if bd else ""
            club_el   = fnd(ath, "CLUB")
            city      = club_el.get("name", "") if club_el is not None else ath.get("nation", "")
            athlete_map[ath_id] = {"name": name, "yb": yb, "city": city}

    results: list[dict] = []
    for meet in deepall(root, "MEETS", "MEET") or deepall(root, "MEET"):
        for session in deepall(meet, "SESSIONS", "SESSION"):
            for event in deepall(session, "EVENTS", "EVENT"):
                swimstyle = fnd(event, "SWIMSTYLE")
                if swimstyle is None:
                    continue
                dist   = swimstyle.get("distance", "?")
                stk    = _STROKE_LENEX.get(swimstyle.get("stroke", "").lower(), swimstyle.get("stroke", ""))
                gender = "Erkek" if event.get("gender", "M").upper() == "M" else "Kadın"
                ev_lbl = f"{dist}m {stk}"

                for result in deepall(event, "RESULTS", "RESULT"):
                    place_str = result.get("place", "")
                    try:
                        rank = int(place_str)
                    except ValueError:
                        continue
                    swimtime = result.get("swimtime", "")
                    time_sec = _to_sec(swimtime)

                    # ATHLETE referansı
                    ath_el  = fnd(result, "ATHLETE")
                    ath_id  = ath_el.get("athleteid", "") if ath_el is not None else result.get("athleteid", "")
                    ath_dat = athlete_map.get(ath_id, {})
                    if not ath_dat.get("name"):
                        continue

                    results.append({
                        "name":     ath_dat["name"],
                        "yb":       ath_dat["yb"],
                        "city":     ath_dat.get("city", ""),
                        "rank":     rank,
                        "time_raw": swimtime or "NT",
                        "time_sec": time_sec,
                        "gender":   gender,
                        "event":    ev_lbl,
                    })

    return results


def scrape_lenex_live(url: str = RACE_URL, verbose: bool = True) -> list[dict]:
    """
    Ana sayfadan Lenex dosyasını bulup indirir ve parse eder.
    """
    lxf_url = fetch_lenex_url(url)
    if not lxf_url:
        if verbose:
            print("  ⚠ Lenex dosyası bulunamadı.")
        return []

    if verbose:
        print(f"  Lenex indiriliyor: {lxf_url}")
    try:
        resp = requests.get(lxf_url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        results = parse_lenex(resp.content)
        if verbose:
            print(f"  ✓ Lenex: {len(results)} sonuç")
        return results
    except Exception as e:
        logger.error(f"Lenex indirilemedi: {e}")
        return []


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else RACE_URL
    results = scrape_live(url, verbose=True)
    print(f"\nÖrnek sonuçlar ({min(5, len(results))}):")
    for r in results[:5]:
        print(f"  {r}")
