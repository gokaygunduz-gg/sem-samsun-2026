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
    USERS, REGISTRATION_OPEN, _sha256,
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


def _merge_live_into_entries(
    entries: list[dict], live: list[dict]
) -> tuple[list[dict], set[tuple]]:
    """
    Canlı sonuçları giriş listesiyle birleştirir.
    Döner: (merged_entries, completed_event_keys)
    completed_event_keys: canlı sonucu olan (yb, event) çiftleri.
    """
    from sem_entry import norm

    live_index: dict[tuple, dict] = {}
    completed_events: set[tuple] = set()
    for r in live:
        nname = norm(r.get("name", ""))
        yb    = r.get("yb", "")
        ev    = r.get("event", "")
        live_index[(nname, yb, ev)] = r
        completed_events.add((yb, ev))

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
                    "is_live":  True,
                })
            else:
                new_events.append({**ev, "is_live": False})
        merged.append({**sw, "events": new_events})
    return merged, completed_events


def _build_athletes_out(athletes, medal_cut):
    out = []
    for a in athletes:
        events_out = []
        for er in a.get("sorted_events", []):
            events_out.append({
                "event":    er.get("event", ""),
                "time_raw": er.get("time_raw", ""),
                "rank":     er.get("rank"),
                "points":   er.get("points", 0),
                "is_live":  er.get("is_live", False),
            })
        out.append({
            "rank":   a["rank"],
            "name":   a["name"],
            "city":   a.get("city", ""),
            "top3":   a.get("top3", 0),
            "top4":   a.get("top4", 0),
            "events": events_out,
            "medal":  a["rank"] <= medal_cut,
            "prize":  a["rank"] <= 2,  # bireysel ödül: her grupta ilk 2
        })
    return out


def build_json(entries: list[dict], live: list[dict] | None, source: str) -> dict:
    """
    Tüm veriyi JSON yapısına dönüştürür.
    source: "entry" | "live"

    Canlı modda iki ayrı sıralama üretilir:
      - "current"  : yalnızca tamamlanan yarışların puanları
      - "forecast" : tamamlanan + henüz koşulmayan yarışların giriş-süre tahminleri
    """
    completed_events: set[tuple] = set()

    if live:
        merged, completed_events = _merge_live_into_entries(entries, live)
    else:
        merged = [{**sw, "events": [{**ev, "is_live": False} for ev in sw["events"]]}
                  for sw in entries]

    # --- Forecast sıralaması (tüm yarışlar; canlı + giriş tahmini) ---
    ev_rankings_forecast = compute_event_rankings(merged, source)
    individual_forecast  = build_individual_rankings(merged, ev_rankings_forecast)
    city_rankings        = compute_city_rankings(individual_forecast)

    # --- Current (anlık) sıralaması (yalnızca canlı sonucu olan yarışlar) ---
    if completed_events:
        # Yalnızca is_live=True olan event'leri filtrele
        current_entries = []
        for sw in merged:
            live_evs = [ev for ev in sw["events"] if ev.get("is_live")]
            if live_evs:
                current_entries.append({**sw, "events": live_evs})
        if current_entries:
            ev_rankings_current = compute_event_rankings(current_entries, "live")
            individual_current  = build_individual_rankings(current_entries, ev_rankings_current)
        else:
            ev_rankings_current = {}
            individual_current  = {}
    else:
        ev_rankings_current = ev_rankings_forecast
        individual_current  = individual_forecast

    # --- Grup JSON (forecast + current birleşik) ---
    groups_out = {}
    for (yb, gender), athletes in sorted(individual_forecast.items()):
        key      = f"{yb}_{gender}"
        medal_cut = MEDAL_CUTOFFS.get(yb, 3)
        groups_out[key] = {
            "yb":            yb,
            "gender":        gender,
            "age_label":     AGE_LABELS.get(yb, f"20{yb}"),
            "medal_cut":     medal_cut,
            "athlete_count": len(athletes),
            "athletes":      _build_athletes_out(athletes, medal_cut),
            "athletes_current": _build_athletes_out(
                individual_current.get((yb, gender), []), medal_cut
            ),
        }

    # --- Şehir detay verisi ---
    city_ath_map: dict[str, list] = {}
    for (yb, gender), athletes in individual_forecast.items():
        for a in athletes:
            city = a.get("city", "Bilinmiyor") or "Bilinmiyor"
            city_ath_map.setdefault(city, []).append({
                "name":          a["name"],
                "group":         f"20{yb} {gender}",
                "yb":            yb,
                "gender":        gender,
                "top3":          a.get("top3", 0),
                "rank_in_group": a["rank"],
            })

    for cr in city_rankings:
        city = cr["city"]
        aths = city_ath_map.get(city, [])
        cr["athlete_list"]  = sorted(aths, key=lambda x: (-x["top3"], x["name"]))
        cr["medal_list"]    = sorted(
            [a for a in aths if a["rank_in_group"] <= 2],
            key=lambda x: (x["yb"], x["gender"], x["rank_in_group"])
        )
        cr["medal_count"]   = len(cr["medal_list"])
        cr["gold_count"]    = sum(1 for a in aths if a["rank_in_group"] == 1)
        cr["silver_count"]  = sum(1 for a in aths if a["rank_in_group"] == 2)

    # Aynı yapıyı city_rankings current için de ekle
    if completed_events:
        city_rankings_current = compute_city_rankings(individual_current)
    else:
        city_rankings_current = city_rankings

    # --- Yarış programı ---
    program_out = [{"gun": g, "seans": s, "brans": b} for g, s, b in PROGRAM]

    # --- Event bazlı sonuçlar ---
    events_out = {}
    for (yb, gender, event), finishers in ev_rankings_forecast.items():
        is_completed = (yb, event) in completed_events
        ekey = f"{event}|{yb}|{gender}"
        events_out[ekey] = {
            "event":        event,
            "yb":           yb,
            "gender":       gender,
            "is_completed": is_completed,
            "medal_cut":    MEDAL_CUTOFFS.get(yb, 3),
            "finishers": [
                {
                    "rank":     f["rank"],
                    "name":     f["name"],
                    "city":     f.get("city", ""),
                    "time_raw": f["time_raw"],
                    "points":   f["points"],
                    "is_live":  f.get("is_live", False),
                }
                for f in finishers
            ],
        }
    # Current event sonuçları (yalnızca gerçekten tamamlanan yarışlar)
    events_current_out = {}
    if completed_events:  # simülasyon modunda boş kalır
        for (yb, gender, event), finishers in ev_rankings_current.items():
            if (yb, event) not in completed_events:
                continue  # sadece is_live sonucu olan yarışlar
            ekey = f"{event}|{yb}|{gender}"
            events_current_out[ekey] = {
                "event":        event,
                "yb":           yb,
                "gender":       gender,
                "is_completed": True,
                "medal_cut":    MEDAL_CUTOFFS.get(yb, 3),
                "finishers": [
                    {
                        "rank":     f["rank"],
                        "name":     f["name"],
                        "city":     f.get("city", ""),
                        "time_raw": f["time_raw"],
                        "points":   f["points"],
                        "is_live":  True,
                    }
                    for f in finishers
                ],
            }

    return {
        "generated_at":           _tr_now(),
        "source":                 source,
        "comp_name":              COMP_NAME,
        "comp_location":          COMP_LOCATION,
        "comp_dates":             COMP_DATES,
        "race_url":               RACE_URL,
        "total_athletes":         len(entries),
        "completed_event_count":  len(completed_events),
        "groups":                 groups_out,
        "city_rankings":          city_rankings,
        "city_rankings_current":  city_rankings_current,
        "program":                program_out,
        "events":                 events_out,
        "events_current":         events_current_out,
        "points_table":           POINTS,
        "auth": {
            "initial_users": [
                {"username": u["username"], "hash": _sha256(u["password"]), "role": u["role"]}
                for u in USERS
            ],
            "registration_open": REGISTRATION_OPEN,
        },
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
