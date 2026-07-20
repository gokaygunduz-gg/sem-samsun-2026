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
    for i, a in enumerate(sorted_athletes):
        a["rank"] = i + 1
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
                "time_raw": ev["time_raw"],
                "time_sec": ev["time_sec"],
                "is_live":  ev.get("is_live", False),
            })

    result = {}
    for key, bucket in event_buckets.items():
        # NT olmayanları süreye göre sırala, NT'ler sona
        timed = [e for e in bucket if e["time_sec"] is not None]
        nt    = [e for e in bucket if e["time_sec"] is None]

        timed_sorted = sorted(timed, key=lambda x: x["time_sec"])
        ranked = []
        for i, e in enumerate(timed_sorted):
            pts = event_points(i + 1)
            ranked.append({**e, "rank": i + 1, "points": pts})
        for j, e in enumerate(nt):
            ranked.append({**e, "rank": len(timed) + j + 1, "points": 0, "time_raw": "NT"})

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
                city = next((s["city"] for s in entries
                             if s["name"] == f["name"] and s["yb"] == yb), "")
                athlete_map[key] = {
                    "name":   f["name"],
                    "yb":     yb,
                    "gender": gender,
                    "city":   city,
                    "event_results": [],
                }
            if f["points"] > 0 or f["time_raw"] != "NT":
                athlete_map[key]["event_results"].append({
                    "event":    event,
                    "time_raw": f["time_raw"],
                    "time_sec": f.get("time_sec"),
                    "rank":     f["rank"],
                    "points":   f["points"],
                    "is_live":  f.get("is_live", False),
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


def compute_club_rankings(individual_rankings: dict, entries: list[dict]) -> list[dict]:
    """
    Kulüp sıralaması — entry listesinde kulüp sütunu yok, şehir bazlı yapılır.
    Eğer ileride kulüp eklenirse burası güncellenir.
    """
    # Şu an entry listesinde sadece şehir var; kulüp = şehir
    return compute_city_rankings(individual_rankings)
