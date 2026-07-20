"""
SEM Panel JSON üreticisi.

Çalıştırma:
  python scripts/sem_generate.py                   # giriş listesinden (simülasyon)
  python scripts/sem_generate.py --live            # cs-390 canlı veri
  python scripts/sem_generate.py --live --loop 60  # 60s döngüyle canlı güncelleme

Çıktılar:
  data/results.json
  panel/data.js   (file:// erişimi için gömülü veri)
"""

import sys
import os
import json
import time
import argparse
import datetime

# Hem doğrudan hem de scripts/ içinden çalışabilmek için path ayarı
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from sem_config import (
    ENTRY_PATH, OUT_JSON, OUT_DATA_JS, PANEL_DIR, DATA_DIR,
    COMP_NAME, COMP_LOCATION, COMP_DATES, RACE_URL,
    AGE_LABELS, MEDAL_CUTOFFS, PROGRAM, POINTS,
)
from sem_entry import load_entry_list
from sem_score import (
    compute_event_rankings,
    build_individual_rankings,
    compute_city_rankings,
)


def _tr_now() -> str:
    tz_tr = datetime.timezone(datetime.timedelta(hours=3))
    return datetime.datetime.now(tz_tr).strftime("%Y-%m-%d %H:%M (TR)")


def _merge_live_into_entries(entries: list[dict], live: list[dict]) -> list[dict]:
    """
    Canlı sonuçları giriş listesiyle birleştirir.
    Önce giriş listesindeki sporcuyu bul (isim + yb eşleşmesi),
    varsa süre ve şehri canlı veriden al, yoksa giriş listesindeki kalsın.
    """
    from sem_entry import norm

    # Canlı veriyi (yb, gender, event) → {norm_name: sonuç} olarak indeksle
    live_index: dict[tuple, dict] = {}
    for r in live:
        key = (r.get("yb", ""), r.get("gender", ""), r.get("event", ""))
        nname = norm(r.get("name", ""))
        live_index[(nname, r.get("yb", ""), r.get("event", ""))] = r

    merged = []
    for sw in entries:
        new_events = []
        for ev in sw["events"]:
            lkey = (norm(sw["name"]), sw["yb"], ev["event"])
            if lkey in live_index:
                lr = live_index[lkey]
                new_events.append({
                    "event":    ev["event"],
                    "time_raw": lr.get("time_raw", ev["time_raw"]),
                    "time_sec": lr.get("time_sec", ev["time_sec"]),
                    "live_rank": lr.get("rank"),
                })
            else:
                new_events.append(ev)
        merged.append({**sw, "events": new_events})
    return merged


def build_json(entries: list[dict], live: list[dict] | None, source: str) -> dict:
    """
    Tüm veriyi JSON yapısına dönüştürür.
    source: "entry" (simülasyon) | "live" (canlı) | "mixed"
    """
    if live:
        entries = _merge_live_into_entries(entries, live)

    event_rankings  = compute_event_rankings(entries, source)
    individual      = build_individual_rankings(entries, event_rankings)
    city_rankings   = compute_city_rankings(individual)

    # Grup JSON
    groups_out = {}
    for (yb, gender), athletes in sorted(individual.items()):
        key = f"{yb}_{gender}"
        medal_cut = MEDAL_CUTOFFS.get(yb, 3)

        athletes_out = []
        for a in athletes:
            events_out = []
            for er in a.get("sorted_events", []):
                events_out.append({
                    "event":    er.get("event", ""),
                    "time_raw": er.get("time_raw", ""),
                    "rank":     er.get("rank"),
                    "points":   er.get("points", 0),
                })
            athletes_out.append({
                "rank":       a["rank"],
                "name":       a["name"],
                "city":       a.get("city", ""),
                "top3":       a.get("top3", 0),
                "top4":       a.get("top4", 0),
                "events":     events_out,
                "medal":      a["rank"] <= medal_cut,
            })

        groups_out[key] = {
            "yb":          yb,
            "gender":      gender,
            "age_label":   AGE_LABELS.get(yb, f"20{yb}"),
            "medal_cut":   medal_cut,
            "athlete_count": len(athletes),
            "athletes":    athletes_out,
        }

    # Yarış programı
    program_out = [
        {"gun": g, "seans": s, "brans": b}
        for g, s, b in PROGRAM
    ]

    # Event bazlı sonuçlar (Yarışlar sekmesi için)
    events_out = {}
    for (yb, gender, event), finishers in event_rankings.items():
        ekey = f"{event}|{yb}|{gender}"
        events_out[ekey] = {
            "event":    event,
            "yb":       yb,
            "gender":   gender,
            "finishers": [
                {
                    "rank":     f["rank"],
                    "name":     f["name"],
                    "city":     f.get("city", ""),
                    "time_raw": f["time_raw"],
                    "points":   f["points"],
                }
                for f in finishers
            ],
        }

    return {
        "generated_at":  _tr_now(),
        "source":        source,
        "comp_name":     COMP_NAME,
        "comp_location": COMP_LOCATION,
        "comp_dates":    COMP_DATES,
        "race_url":      RACE_URL,
        "total_athletes": len(entries),
        "groups":        groups_out,
        "city_rankings": city_rankings,
        "program":       program_out,
        "events":        events_out,
        "points_table":  POINTS,
    }


def save_json(data: dict):
    """JSON ve data.js dosyalarını kaydet."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PANEL_DIR, exist_ok=True)

    json_str = json.dumps(data, ensure_ascii=False, indent=2)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(json_str)

    with open(OUT_DATA_JS, "w", encoding="utf-8") as f:
        f.write(f"window.SEM_DATA = {json_str};\n")

    print(f"  ✓ {OUT_JSON}")
    print(f"  ✓ {OUT_DATA_JS}")


def run(use_live: bool = False, verbose: bool = True):
    print(f"\n[{_tr_now()}] SEM Panel verisi üretiliyor...")

    # Giriş listesi yükle
    entries = load_entry_list()
    print(f"  Giriş listesi: {len(entries)} sporcu yüklendi")

    live_results = None
    if use_live:
        print(f"  Canlı veri çekiliyor: {RACE_URL}")
        from sem_scraper import scrape_live
        live_results = scrape_live(RACE_URL, verbose=verbose)
        source = "live" if live_results else "entry"
        if not live_results:
            print("  ⚠ Canlı sonuç yok — giriş listesi kullanılıyor (simülasyon)")
    else:
        source = "entry"

    data = build_json(entries, live_results, source)
    save_json(data)

    # Özet çıktı
    total_athletes = sum(g["athlete_count"] for g in data["groups"].values())
    print(f"\n=== ÖZET ===")
    print(f"  Kaynak: {source}")
    print(f"  Toplam sporcu: {total_athletes}")
    print(f"  Grup sayısı: {len(data['groups'])}")
    print(f"  Şehir sıralaması: {len(data['city_rankings'])} şehir")
    print(f"\n  İlk 5 şehir:")
    for c in data["city_rankings"][:5]:
        print(f"    #{c['rank']:2d}  {c['city']:20s}  {c['total']:4d} puan  ({c['athletes']} sporcu)")
    print()

    return data


def main():
    parser = argparse.ArgumentParser(description="SEM Panel JSON üreticisi")
    parser.add_argument("--live",  action="store_true", help="Canlı veri çek (cs-390)")
    parser.add_argument("--loop",  type=int, default=0, help="N saniyede bir güncelle (0=tek seferlik)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.loop > 0:
        print(f"Canlı mod: her {args.loop}s güncelleniyor. Durdurmak: Ctrl+C")
        while True:
            try:
                run(use_live=args.live, verbose=not args.quiet)
                print(f"  Sonraki güncelleme: {args.loop}s sonra...")
                time.sleep(args.loop)
            except KeyboardInterrupt:
                print("\nDurduruldu.")
                break
    else:
        run(use_live=args.live, verbose=not args.quiet)


if __name__ == "__main__":
    main()
