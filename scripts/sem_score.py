"""
SEM puanlama motoru.

Bireysel sıralama:
  - Her branştaki sıraya göre puan: {1:9, 2:7, 3:6, 4:5, 5:4, 6:3, 7:2, 8:1}
  - En iyi 3 yarışın puanı toplanır (4. yarış beraberlik bozma)
  - Eşitlikte: 4. yarış puanı karşılaştırılır

Şehir/Kulüp sıralaması:
  - Her sporcunun bireysel puanı (top3) şehir/kulübüne eklenir
"""

from sem_config import POINTS


def event_points(rank: int) -> int:
    """Bireysel sıralamaya karşılık gelen puanı döndürür. 8. sonrası 0."""
    return POINTS.get(rank, 0)


def athlete_score(event_results: list[dict]) -> dict:
    """
    Bir sporcunun tüm yarış sonuçlarından top3 + top4 skoru hesapla.

    event_results: [{"event": "100m Serbest", "rank": 3, "points": 6}, ...]
    Döner: {"top3": int, "top4": int, "sorted_events": [...]}
    """
    pts = sorted([e["points"] for e in event_results], reverse=True)
    top3 = sum(pts[:3])
    top4 = sum(pts[:4])
    return {
        "top3":  top3,
        "top4":  top4,
        "sorted_events": sorted(event_results, key=lambda x: -x["points"]),
    }


def rank_group(athletes: list[dict]) -> list[dict]:
    """
    Bir yaş grubu/cinsiyet içinde sporcuları sırala.
    athletes: her elemanın 'top3' ve 'top4' alanları dolu olmalı.
    Döner: 'rank' alanı eklenmiş aynı liste.
    """
    sorted_athletes = sorted(
        athletes,
        key=lambda a: (-a.get("top3", 0), -a.get("top4", 0), a.get("name", ""))
    )
    prev_top3 = None
    prev_top4 = None
    prev_rank = 0
    for i, a in enumerate(sorted_athletes):
        curr_top3 = a.get("top3", 0)
        curr_top4 = a.get("top4", 0)
        if curr_top3 == prev_top3 and curr_top4 == prev_top4:
            a["rank"] = prev_rank         # eşit top3+top4 → paylaşılan sıra
        else:
            a["rank"] = i + 1             # gerçek konum (beraberlik boşlukları dahil)
            prev_rank = a["rank"]
            prev_top3 = curr_top3
            prev_top4 = curr_top4
    return sorted_athletes


def compute_event_rankings(
    entries: list[dict],
    source: str = "entry"
) -> dict[tuple, list[dict]]:
    """
    Giriş listesinden branş bazlı sıralamaları hesapla.

    entries: load_entry_list() çıktısı
    source: "entry" (giriş zamanı) | "live" (canlı sonuç)

    Dönüş: {(yb, gender, event_name): [{"name", "city", "time_raw", "time_sec", "rank", "points"}, ...]}
    """
    # Her (yb, gender, event) kombinasyonu için sporcuları topla
    from collections import defaultdict
    event_buckets: dict[tuple, list] = defaultdict(list)

    for sw in entries:
        for ev in sw["events"]:
            key = (sw["yb"], sw["gender"], ev["event"])
            event_buckets[key].append({
                "name":     sw["name"],
                "city":     sw["city"],
                "club":     sw.get("club", ""),
                "time_raw": ev["time_raw"],
                "time_sec": ev["time_sec"],
                "is_live":  ev.get("is_live", False),
                "is_dns":   ev.get("is_dns", False),
            })

    result = {}
    for key, bucket in event_buckets.items():
        # is_dns ve is_live alanlarını koru
        timed = [e for e in bucket if e["time_sec"] is not None]
        nt    = [e for e in bucket if e["time_sec"] is None]

        timed_sorted = sorted(timed, key=lambda x: x["time_sec"])
        ranked = []
        prev_time = None
        prev_rank = 0
        for i, e in enumerate(timed_sorted):
            if e["time_sec"] == prev_time:
                rank = prev_rank          # aynı süre → aynı sıra
            else:
                rank = i + 1              # gerçek konum (beraberlik boşlukları dahil)
                prev_rank = rank
                prev_time = e["time_sec"]
            pts = event_points(rank)
            ranked.append({**e, "rank": rank, "points": pts})
        for j, e in enumerate(nt):
            # time_raw'u koru: DNS veya NT ayrımını sakla
            ranked.append({**e, "rank": len(timed) + j + 1, "points": 0})

        result[key] = ranked

    return result


def build_individual_rankings(
    entries: list[dict],
    event_rankings: dict[tuple, list[dict]]
) -> dict[tuple, list[dict]]:
    """
    Her (yb, gender) grubu için bireysel sıralama oluştur.

    Dönüş: {(yb, gender): [sporcu_dict, ...]} — rank'e göre sıralı
    """
    # Sporcu başına puan topla
    athlete_map: dict[tuple, dict] = {}

    for (yb, gender, event), finishers in event_rankings.items():
        for f in finishers:
            key = (f["name"], yb, gender)
            if key not in athlete_map:
                sw = next((s for s in entries if s["name"] == f["name"] and s["yb"] == yb), {})
                athlete_map[key] = {
                    "name":   f["name"],
                    "yb":     yb,
                    "gender": gender,
                    "city":   sw.get("city", f.get("city", "")),
                    "club":   sw.get("club", f.get("club", "")),
                    "event_results": [],
                }
            athlete_map[key]["event_results"].append({
                "event":    event,
                "time_raw": f["time_raw"],
                "time_sec": f.get("time_sec"),
                "rank":     f["rank"],
                "points":   f["points"],
                "is_live":  f.get("is_live", False),
                "is_dns":   f.get("is_dns", False),
            })

    # Puan hesapla
    for key, a in athlete_map.items():
        scores = athlete_score(a["event_results"])
        a.update(scores)

    # Grupla ve sırala
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for (name, yb, gender), a in athlete_map.items():
        groups[(yb, gender)].append(a)

    ranked_groups = {}
    for group_key, athletes in groups.items():
        ranked_groups[group_key] = rank_group(athletes)

    return ranked_groups


def compute_city_rankings(individual_rankings: dict) -> list[dict]:
    """
    Şehir sıralaması: her sporcunun top3 puanları şehre eklenir.
    """
    from collections import defaultdict
    city_totals: dict[str, dict] = defaultdict(lambda: {"total": 0, "athletes": 0, "events_won": 0})

    for (yb, gender), athletes in individual_rankings.items():
        for a in athletes:
            city = a.get("city", "Bilinmiyor") or "Bilinmiyor"
            city_totals[city]["total"]    += a.get("top3", 0)
            city_totals[city]["athletes"] += 1

    ranked = sorted(city_totals.items(), key=lambda x: -x[1]["total"])
    return [{"rank": i + 1, "city": c, **v} for i, (c, v) in enumerate(ranked)]


def compute_club_rankings(individual_rankings: dict) -> list[dict]:
    """
    Kulüp sıralaması: her sporcunun top3 puanları kulübüne eklenir.
    """
    from collections import defaultdict
    club_totals: dict[str, dict] = defaultdict(lambda: {"total": 0, "athletes": 0})

    for (yb, gender), athletes in individual_rankings.items():
        for a in athletes:
            club = a.get("club", "") or "Bağımsız"
            club_totals[club]["total"]    += a.get("top3", 0)
            club_totals[club]["athletes"] += 1

    ranked = sorted(club_totals.items(), key=lambda x: -x[1]["total"])
    return [{"rank": i + 1, "club": c, "city": c, **v} for i, (c, v) in enumerate(ranked)]
