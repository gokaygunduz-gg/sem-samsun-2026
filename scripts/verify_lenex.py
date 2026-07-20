"""
Lenex/LXF verisi ile mevcut PDF-scrape sonuçlarını karşılaştırır.

Kullanım:
  python scripts/verify_lenex.py                      # cs-390'dan Lenex otomatik arar
  python scripts/verify_lenex.py --url <lenex-url>    # doğrudan URL
  python scripts/verify_lenex.py --file <dosya.lxf>   # yerel dosya

Çıktı: eşleşmeyen/eksik/fazla kayıtlar listelenir.
"""

import sys
import os
import json
import argparse

_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from sem_config import OUT_JSON, RACE_URL, HTTP_HEADERS, HTTP_TIMEOUT
from sem_scraper import scrape_lenex_live, parse_lenex, _norm


def load_current_results() -> dict:
    try:
        with open(OUT_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ {OUT_JSON} yüklenemedi: {e}")
        sys.exit(1)


def extract_pdf_results(data: dict) -> list[dict]:
    """Mevcut data/results.json'daki canlı (PDF) sonuçlarını düzleştir."""
    rows = []
    for ev_key, ev in (data.get("events_current") or {}).items():
        for f in ev.get("finishers", []):
            rows.append({
                "name":     f["name"],
                "yb":       ev.get("yb", ""),
                "event":    ev.get("event", ""),
                "gender":   ev.get("gender", ""),
                "rank":     f["rank"],
                "time_raw": f["time_raw"],
                "time_sec": None,
            })
    return rows


def make_index(results: list[dict]) -> dict:
    """(norm_name, event, gender) → result"""
    idx = {}
    for r in results:
        key = (_norm(r.get("name", "")), r.get("event", ""), r.get("gender", ""))
        idx[key] = r
    return idx


def compare(pdf: list[dict], lenex: list[dict]) -> None:
    pdf_idx   = make_index(pdf)
    lenex_idx = make_index(lenex)
    all_keys  = sorted(set(pdf_idx) | set(lenex_idx), key=lambda k: (k[1], k[2], k[0]))

    mismatches = []
    only_pdf   = []
    only_lenex = []

    for key in all_keys:
        in_pdf, in_lenex = key in pdf_idx, key in lenex_idx
        if in_pdf and not in_lenex:
            only_pdf.append(key)
        elif in_lenex and not in_pdf:
            only_lenex.append(key)
        else:
            p, lx = pdf_idx[key], lenex_idx[key]
            rank_diff = p.get("rank") != lx.get("rank")
            time_diff = abs((p.get("time_sec") or 0) - (lx.get("time_sec") or 0)) > 0.1
            if rank_diff or time_diff:
                mismatches.append((key, p, lx))

    SEP = "─" * 60
    print(f"\n{'='*60}")
    print("  LENEX ↔ PDF KARŞILAŞTIRMA")
    print(f"{'='*60}")
    print(f"  PDF sonuç  : {len(pdf)}")
    print(f"  Lenex sonuç: {len(lenex)}")
    print(f"  Uyuşmazlık : {len(mismatches)}")
    print(f"  Yalnız PDF : {len(only_pdf)}")
    print(f"  Yalnız Lenex: {len(only_lenex)}")

    if mismatches:
        print(f"\n{SEP}\nFARKLI SONUÇLAR ({len(mismatches)}):")
        for (name, event, gender), p, lx in mismatches:
            print(f"  {name} | {event} {gender}")
            print(f"    PDF  : {p.get('rank')}. sıra  {p.get('time_raw')}")
            print(f"    Lenex: {lx.get('rank')}. sıra  {lx.get('time_raw')}")

    def show_list(title, items, limit=30):
        if not items:
            return
        print(f"\n{SEP}\n{title} ({len(items)}):")
        for name, event, gender in items[:limit]:
            print(f"  {name} | {event} {gender}")
        if len(items) > limit:
            print(f"  … ve {len(items)-limit} tane daha")

    show_list("SADECE PDF'DE OLAN", only_pdf)
    show_list("SADECE LENEX'TE OLAN", only_lenex)

    print(f"\n{'='*60}")
    if not mismatches and not only_pdf and not only_lenex:
        print("✅ Tüm sonuçlar eşleşiyor!")
    elif not mismatches:
        print(f"⚠  Sıralama/süre farkı yok. {len(only_pdf)+len(only_lenex)} kayıt yalnızca bir kaynakta.")
    else:
        print(f"⚠  {len(mismatches)} uyuşmazlık, kontrol edin.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Lenex vs PDF doğrulama")
    parser.add_argument("--url",  help="Lenex dosyası URL'i")
    parser.add_argument("--file", help="Yerel Lenex dosyası (.lxf veya .xml)")
    args = parser.parse_args()

    data = load_current_results()
    pdf_results = extract_pdf_results(data)

    if not pdf_results:
        print("ℹ  Canlı (PDF) sonuç yok — simülasyon modunda karşılaştırma yapılamaz.")
        print("   Yarış sırasında --live ile üretilen data/results.json üzerinde çalıştırın.")
        sys.exit(0)

    print(f"PDF kaynağı: {len(pdf_results)} sonuç yüklendi.")

    if args.file:
        print(f"Yerel Lenex okunuyor: {args.file}")
        with open(args.file, "rb") as f:
            lenex_results = parse_lenex(f.read())
    elif args.url:
        import requests
        print(f"Lenex indiriliyor: {args.url}")
        r = requests.get(args.url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        lenex_results = parse_lenex(r.content)
    else:
        lenex_results = scrape_lenex_live(RACE_URL, verbose=True)

    if not lenex_results:
        print("❌ Lenex verisi alınamadı. --url veya --file ile belirtin.")
        sys.exit(1)

    compare(pdf_results, lenex_results)


if __name__ == "__main__":
    main()
