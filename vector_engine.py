

import math
import csv
from datetime import datetime, timedelta
from collections import defaultdict

DIMENSIONS = [
    "stress_level",
    "mood_level",
    "energy_level",
    "engagement_level",
    "motivation_level",
    "consistency_level",
]



EMOTION_MAP = {
    "stressed": 0.10,
    "sadness": 0.25,
    "neutral": 0.50,
    "relaxed": 0.75,
    "joy": 0.90,
    "fear": 0.20,
    "happy": 0.80,
    "content": 0.85,
    "excited": 0.90,
    "calm": 0.65,
    "anger": 0.15,
    "anxiety": 0.20,
    "disgust": 0.15,
    "lonely": 0.25,
    "tired": 0.20,
    "proud": 0.80,
    "surprised": 0.70,
    "bored": 0.35,
}

EVENT_INTENT = {
    "visit": 0.2,
    "click": 0.5,
    "complete": 0.7,
    "skip": 0.0,
    "reward": 0.8,
    "milestone": 1.0,
    "alert": -0.3,
}

CONTENT_PAGES = {"/chatbot", "/game", "/journal", "/planner", "/activities"}

LAMBDA_DECAY = 0.03   

EXPECTED_MAX_DURATION = 300  

def _clamp(value, lo=0.0, hi=1.0):

    return max(lo, min(hi, value))

def _normalize(value, min_val, max_val):

    if max_val <= min_val:
        return 0.5
    return _clamp((value - min_val) / (max_val - min_val))

def _time_weight(event_ts: datetime, reference_ts: datetime, lam: float = LAMBDA_DECAY) -> float:

    delta_hours = max(0.0, (reference_ts - event_ts).total_seconds() / 3600.0)
    return math.exp(-lam * delta_hours)

def _parse_datetime(ts_str: str) -> datetime | None:

    try:
        ts_str = str(ts_str).strip()

        if ts_str.endswith(" "):
            ts_str = ts_str.rstrip()
        return datetime.fromisoformat(ts_str)
    except Exception:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            try:
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

def _map_emotion(emotion_str: str) -> float | None:

    if not emotion_str or str(emotion_str).strip().lower() in ("", "nan", "none"):
        return None
    key = str(emotion_str).strip().lower()

    if key in EMOTION_MAP:
        return EMOTION_MAP[key]

    for k, v in EMOTION_MAP.items():
        if key.startswith(k) or k.startswith(key):
            return v
    return None  

def load_events(csv_path: str) -> list[dict]:

    events = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                events.append(dict(row))
    except Exception as e:
        print(f"[vector_engine] CSV load error: {e}")
    return events

def filter_user_events(
    events: list[dict],
    user_id: str,
    window_days: int = 7,
    max_events: int = 100,
    reference_ts: datetime | None = None,
) -> list[dict]:

    if reference_ts is None:
        reference_ts = datetime.now()

    cutoff = reference_ts - timedelta(days=window_days)
    user_str = str(user_id).strip()

    filtered = []
    for ev in events:
        if str(ev.get("user_id", "")).strip() != user_str:
            continue
        ts = _parse_datetime(ev.get("timestamp", ""))
        if ts is None:
            continue
        if ts < cutoff:
            continue
        ev["_ts"] = ts
        filtered.append(ev)

    filtered.sort(key=lambda e: e["_ts"], reverse=True)
    return filtered[:max_events]

def _compute_mood_level(events: list[dict], reference_ts: datetime) -> float:

    weighted_sum = 0.0
    total_weight = 0.0

    for ev in events:
        score = None

        if ev.get("event_type") == "emotion_detected":
            score = _map_emotion(ev.get("emotion", ""))

        if score is None:
            score = _map_emotion(ev.get("emotion", ""))

        if score is None:
            continue

        w = _time_weight(ev["_ts"], reference_ts)
        weighted_sum += score * w
        total_weight += w

    if total_weight == 0:
        return 0.5  
    return _clamp(weighted_sum / total_weight)

def _compute_stress_level(
    events: list[dict], mood_level: float, reference_ts: datetime
) -> float:

    base_stress = 1.0 - mood_level

    stress_emotions = {"stressed", "fear", "anger", "anxiety", "disgust"}
    stress_boost = 0.0
    boost_weight = 0.0

    for ev in events:
        emotion_raw = str(ev.get("emotion", "")).strip().lower()
        if emotion_raw in stress_emotions:
            w = _time_weight(ev["_ts"], reference_ts)
            stress_boost += 0.15 * w
            boost_weight += w

    if boost_weight > 0:

        avg_boost = (stress_boost / boost_weight) * min(boost_weight, 3.0) / 3.0
        base_stress = base_stress * 0.7 + avg_boost * 0.3

    return _clamp(base_stress)

def _compute_energy_level(events: list[dict], reference_ts: datetime) -> float:

    weighted_sum = 0.0
    total_weight = 0.0

    for ev in events:
        if ev.get("event_type") != "time_spent":
            continue
        page = str(ev.get("item_id", "")).strip()
        if page not in CONTENT_PAGES:
            continue

        try:
            dur = float(ev.get("duration") or 0)
        except (ValueError, TypeError):
            continue

        if dur <= 0:
            continue

        w = _time_weight(ev["_ts"], reference_ts)
        weighted_sum += dur * w
        total_weight += w

    if total_weight == 0:
        return 0.3  
    avg_weighted_dur = weighted_sum / total_weight
    return _normalize(avg_weighted_dur, 0, EXPECTED_MAX_DURATION)

def _compute_engagement_level(events: list[dict], reference_ts: datetime) -> float:

    content_time = 0.0
    total_time = 0.0
    content_weight = 0.0
    total_weight = 0.0

    for ev in events:
        if ev.get("event_type") != "time_spent":
            continue
        try:
            dur = float(ev.get("duration") or 0)
        except (ValueError, TypeError):
            continue
        if dur <= 0:
            continue

        page = str(ev.get("item_id", "")).strip()
        w = _time_weight(ev["_ts"], reference_ts)

        total_time += dur * w
        total_weight += w

        if page in CONTENT_PAGES:
            content_time += dur * w
            content_weight += w

    if total_weight == 0:
        return 0.0
    if total_time == 0:
        return 0.0

    ratio = content_time / total_time

    content_visits = sum(
        1 for ev in events
        if ev.get("event_type") in ("visit", "click")
        and str(ev.get("item_id", "")).strip() in CONTENT_PAGES
    )
    visit_signal = _clamp(content_visits / 10.0)  

    return _clamp(ratio * 0.7 + visit_signal * 0.3)

def _compute_motivation_level(events: list[dict], reference_ts: datetime) -> float:

    click_count = 0
    visit_count = 0
    meaningful_visits = 0  

    for ev in events:
        etype = ev.get("event_type", "")
        item = str(ev.get("item_id", "")).strip()

        if etype == "click" and item in (p.strip("/") for p in CONTENT_PAGES):
            click_count += 1
        elif etype == "visit" and item in CONTENT_PAGES:
            visit_count += 1

    page_durations = defaultdict(float)
    for ev in events:
        if ev.get("event_type") == "time_spent":
            page = str(ev.get("item_id", "")).strip()
            if page in CONTENT_PAGES:
                try:
                    page_durations[page] += float(ev.get("duration") or 0)
                except (ValueError, TypeError):
                    pass

    meaningful_visits = sum(1 for d in page_durations.values() if d > 10)

    if click_count > 0:
        base = _clamp(visit_count / click_count)
    elif visit_count > 0:
        base = 0.5  
    else:
        base = 0.1  

    quality_boost = min(meaningful_visits / 5.0, 0.3)

    return _clamp(base * 0.7 + quality_boost)

def _compute_consistency_level(events: list[dict], window_days: int = 7) -> float:

    unique_days = set()
    for ev in events:
        ts = ev.get("_ts")
        if ts:
            unique_days.add(ts.date())

    return _clamp(len(unique_days) / max(window_days, 1))

def compute_user_vector(
    user_id: str,
    csv_path: str = "user_behaviour.csv",
    window_days: int = 7,
    max_events: int = 100,
    reference_ts: datetime | None = None,
) -> dict:

    if reference_ts is None:
        reference_ts = datetime.now()

    all_events = load_events(csv_path)
    events = filter_user_events(all_events, user_id, window_days, max_events, reference_ts)

    if not events:

        neutral = [0.5, 0.5, 0.3, 0.3, 0.3, 0.0]
        return {
            "user_id": user_id,
            "vector": neutral,
            "dimensions": dict(zip(DIMENSIONS, neutral)),
            "timestamp": reference_ts.isoformat(),
            "meta": {
                "events_used": 0,
                "window_days": window_days,
                "note": "No recent events found — using neutral defaults",
            },
        }

    mood        = _compute_mood_level(events, reference_ts)
    stress      = _compute_stress_level(events, mood, reference_ts)
    energy      = _compute_energy_level(events, reference_ts)
    engagement  = _compute_engagement_level(events, reference_ts)
    motivation  = _compute_motivation_level(events, reference_ts)
    consistency = _compute_consistency_level(events, window_days)

    vector = [
        round(stress,      4),
        round(mood,        4),
        round(energy,      4),
        round(engagement,  4),
        round(motivation,  4),
        round(consistency, 4),
    ]

    return {
        "user_id": user_id,
        "vector": vector,
        "dimensions": dict(zip(DIMENSIONS, vector)),
        "timestamp": reference_ts.isoformat(),
        "meta": {
            "events_used": len(events),
            "window_days": window_days,
            "emotions_count": sum(1 for e in events if e.get("event_type") == "emotion_detected"),
            "time_spent_count": sum(1 for e in events if e.get("event_type") == "time_spent"),
        },
    }

def incremental_update(
    old_vector: list[float],
    new_event: dict,
    alpha: float = 0.85,
) -> list[float]:

    if len(old_vector) != 6:
        raise ValueError("old_vector must have exactly 6 dimensions")

    etype   = str(new_event.get("event_type", "")).strip().lower()
    item    = str(new_event.get("item_id", "")).strip()
    emotion = str(new_event.get("emotion", "")).strip().lower()

    contrib = list(old_vector)  

    mood_score = _map_emotion(emotion)
    if mood_score is not None:
        contrib[1] = mood_score                
        contrib[0] = 1.0 - mood_score          

    if etype == "time_spent" and item in CONTENT_PAGES:
        try:
            dur = float(new_event.get("duration") or 0)
            contrib[2] = _normalize(dur, 0, EXPECTED_MAX_DURATION)  
        except (ValueError, TypeError):
            pass

    if etype == "time_spent" and item in CONTENT_PAGES:
        contrib[3] = _clamp(contrib[3] + 0.05)  
    elif etype == "visit" and item in CONTENT_PAGES:
        contrib[3] = _clamp(contrib[3] + 0.02)

    if etype in ("complete", "visit") and item in CONTENT_PAGES:
        contrib[4] = _clamp(contrib[4] + 0.05)
    elif etype == "skip":
        contrib[4] = _clamp(contrib[4] - 0.08)
    elif etype == "click":
        contrib[4] = _clamp(contrib[4] + 0.02)

    new_vector = [
        round(alpha * old_vector[i] + (1 - alpha) * contrib[i], 4)
        for i in range(6)
    ]
    return new_vector

def get_all_user_ids(csv_path: str = "user_behaviour.csv") -> list[str]:

    user_ids = set()
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = str(row.get("user_id", "")).strip()
                if uid and uid.lower() not in ("", "user_id", "nan"):
                    user_ids.add(uid)
    except Exception as e:
        print(f"[vector_engine] Error reading user IDs: {e}")
    return sorted(user_ids)

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import json
    import os

    csv_file = os.path.join(os.path.dirname(__file__), "user_behaviour.csv")
    if not os.path.exists(csv_file):
        print(f"ERROR: Could not find {csv_file}")
        exit(1)

    user_ids = get_all_user_ids(csv_file)
    print(f"\n{'='*60}")
    print(f"  Oasis Vector Engine — Self Test")
    print(f"  CSV: {csv_file}")
    print(f"  Found {len(user_ids)} unique user(s): {user_ids}")
    print(f"{'='*60}\n")

    all_events = load_events(csv_file)
    parsed_ts  = [_parse_datetime(e.get("timestamp", "")) for e in all_events]
    valid_ts   = [t for t in parsed_ts if t is not None]
    ref        = max(valid_ts) + timedelta(days=1) if valid_ts else datetime.now()
    print(f"  Reference timestamp (auto): {ref.strftime('%Y-%m-%d')}\n")

    for uid in user_ids:
        result = compute_user_vector(uid, csv_file, window_days=365, reference_ts=ref)
        print(f"User: {uid}")
        print(f"  Events used : {result['meta']['events_used']}")
        for dim, val in result["dimensions"].items():
            bar = "#" * int(val * 20) + "." * (20 - int(val * 20))
            print(f"  {dim:<22} {bar}  {val:.4f}")
        print()
