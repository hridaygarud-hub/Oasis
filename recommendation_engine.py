

import json
import os
import math
from datetime import datetime
from copy import deepcopy

ACTIVITIES = [
    {
        "id": "box_breathing",
        "name": "Box Breathing",
        "icon": "",
        "description": "4-4-4-4 breathing cycle to calm your nervous system",
        "tags": ["calming", "quick", "stress_relief"],
        "tier": 1,
        "duration": 3,
        "url": "/meditation",
        "vector": [0.9, 0.3, 0.1, 0.2, 0.2, 0.3],
        "effect": [-0.15, 0.10, 0.05, 0.05, 0.05, 0.0],
    },
    {
        "id": "guided_meditation",
        "name": "Guided Meditation",
        "icon": "",
        "description": "5-minute mindfulness session to reset your mind",
        "tags": ["calming", "stress_relief", "mood_boost"],
        "tier": 1,
        "duration": 5,
        "url": "/meditation",
        "vector": [0.85, 0.2, 0.1, 0.3, 0.2, 0.4],
        "effect": [-0.20, 0.15, 0.08, 0.05, 0.05, 0.0],
    },
    {
        "id": "progressive_relaxation",
        "name": "Progressive Muscle Relaxation",
        "icon": "",
        "description": "Systematically tense and release muscles to release tension",
        "tags": ["calming", "stress_relief"],
        "tier": 1,
        "duration": 8,
        "url": "/yoga",
        "vector": [0.80, 0.3, 0.2, 0.2, 0.2, 0.3],
        "effect": [-0.18, 0.12, 0.08, 0.05, 0.05, 0.0],
    },
    {
        "id": "gratitude_journal",
        "name": "Gratitude Journal",
        "icon": "",
        "description": "Write 3 things you're grateful for today",
        "tags": ["reflective", "mood_boost", "quick"],
        "tier": 1,
        "duration": 5,
        "url": "/journal",
        "vector": [0.3, 0.6, 0.2, 0.5, 0.4, 0.5],
        "effect": [-0.05, 0.18, 0.05, 0.08, 0.08, 0.05],
    },
    {
        "id": "mood_journal",
        "name": "Mood Journal",
        "icon": "",
        "description": "Reflect on how you're feeling and why",
        "tags": ["reflective", "mood_boost"],
        "tier": 2,
        "duration": 10,
        "url": "/journal",
        "vector": [0.4, 0.5, 0.3, 0.5, 0.5, 0.4],
        "effect": [-0.08, 0.15, 0.05, 0.10, 0.10, 0.05],
    },
    {
        "id": "self_reflection",
        "name": "Self-Reflection",
        "icon": "",
        "description": "Deep dive into your thoughts, goals and blockers",
        "tags": ["reflective", "high_engagement"],
        "tier": 2,
        "duration": 15,
        "url": "/journal",
        "vector": [0.3, 0.5, 0.4, 0.7, 0.6, 0.5],
        "effect": [-0.05, 0.12, 0.05, 0.12, 0.12, 0.08],
    },
    {
        "id": "daily_planning",
        "name": "Daily Planning",
        "icon": "",
        "description": "Set your top 3 priorities for today",
        "tags": ["productive", "quick_win"],
        "tier": 2,
        "duration": 5,
        "url": "/planner",
        "vector": [0.2, 0.5, 0.5, 0.6, 0.7, 0.6],
        "effect": [0.0, 0.05, 0.0, 0.10, 0.15, 0.10],
    },
    {
        "id": "weekly_review",
        "name": "Weekly Review",
        "icon": "",
        "description": "Reflect on what worked this week and plan ahead",
        "tags": ["productive", "reflective", "high_engagement"],
        "tier": 3,
        "duration": 20,
        "url": "/planner",
        "vector": [0.1, 0.5, 0.6, 0.7, 0.8, 0.7],
        "effect": [0.0, 0.08, 0.0, 0.15, 0.18, 0.15],
    },
    {
        "id": "talk_to_oasis",
        "name": "Talk to Oasis",
        "icon": "",
        "description": "Share what's on your mind with your AI companion",
        "tags": ["social", "mood_boost", "stress_relief"],
        "tier": 1,
        "duration": 5,
        "url": "/chatbot",
        "vector": [0.6, 0.4, 0.2, 0.5, 0.3, 0.3],
        "effect": [-0.10, 0.12, 0.05, 0.08, 0.05, 0.0],
    },
    {
        "id": "relaxing_game",
        "name": "Relaxing Game",
        "icon": "",
        "description": "A calming mini-game to take your mind off things",
        "tags": ["fun", "stress_relief", "quick"],
        "tier": 1,
        "duration": 5,
        "url": "/game",
        "vector": [0.5, 0.4, 0.3, 0.4, 0.2, 0.2],
        "effect": [-0.08, 0.10, 0.05, 0.05, 0.0, 0.0],
    },
    {
        "id": "focus_challenge",
        "name": "Focus Challenge",
        "icon": "",
        "description": "Sharpen your mind with a cognitive mini-challenge",
        "tags": ["fun", "high_engagement", "energizing"],
        "tier": 2,
        "duration": 8,
        "url": "/game",
        "vector": [0.2, 0.5, 0.6, 0.7, 0.7, 0.4],
        "effect": [0.0, 0.08, 0.05, 0.12, 0.10, 0.05],
    },
    {
        "id": "quick_stretch",
        "name": "Quick Stretch",
        "icon": "",
        "description": "2-minute desk stretch to re-energize your body",
        "tags": ["energizing", "quick", "quick_win"],
        "tier": 1,
        "duration": 2,
        "url": "/yoga",
        "vector": [0.3, 0.5, 0.7, 0.4, 0.5, 0.3],
        "effect": [-0.05, 0.08, 0.15, 0.05, 0.08, 0.0],
    },
    {
        "id": "power_walk",
        "name": "Power Walk",
        "icon": "",
        "description": "10-minute brisk walk to boost energy and mood",
        "tags": ["energizing", "mood_boost"],
        "tier": 2,
        "duration": 10,
        "url": "/activities",
        "vector": [0.2, 0.5, 0.8, 0.5, 0.6, 0.4],
        "effect": [-0.05, 0.15, 0.20, 0.08, 0.10, 0.05],
    },
]

WEIGHTS_FILE = "activity_weights.json"

def _load_weights() -> dict:
    if os.path.exists(WEIGHTS_FILE):
        try:
            with open(WEIGHTS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {a["id"]: 1.0 for a in ACTIVITIES}

def _save_weights(weights: dict):
    try:
        with open(WEIGHTS_FILE, "w") as f:
            json.dump(weights, f, indent=2)
    except Exception as e:
        print(f"[rec_engine] Weight save error: {e}")

def apply_feedback(activity_id: str, feedback: str):

    weights = _load_weights()
    current = weights.get(activity_id, 1.0)
    if feedback == "complete":
        weights[activity_id] = min(current + 0.15, 2.0)
    elif feedback == "skip":
        weights[activity_id] = max(current - 0.20, 0.1)
    _save_weights(weights)
    return weights[activity_id]

def _similarity(a: list, b: list) -> float:

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))

    return dot / len(a)

def _rule_filter(activities: list, user_vec: list) -> list:

    stress      = user_vec[0]
    mood        = user_vec[1]
    energy      = user_vec[2]
    motivation  = user_vec[4]

    filtered = []
    for act in activities:
        tags   = act.get("tags", [])
        effort = act.get("effort", 2)

        if stress > 0.95 and mood < 0.20:
            if "calming" in tags or "stress_relief" in tags or "social" in tags:
                filtered.append(act)
            continue  

        if stress > 0.80:
            if not any(t in tags for t in ["calming", "stress_relief", "mood_boost", "social", "quick"]):
                continue

        if energy < 0.30 and effort >= 3:
            continue

        if motivation < 0.35 and "quick_win" not in tags and effort >= 3:
            continue

        filtered.append(act)

    return filtered if filtered else activities  

def score_activities(
    user_vec: list,
    top_k: int = 3,
) -> list[dict]:

    weights = _load_weights()

    candidates = _rule_filter(ACTIVITIES, user_vec)

    scored = []
    for act in candidates:
        raw_score = _similarity(user_vec, act["vector"])
        weight    = weights.get(act["id"], 1.0)

        final = raw_score * weight

        scored.append({
            **act,
            "score": round(min(1.0, final), 4), 
            "raw_similarity": round(raw_score, 4),
            "weight": round(weight, 2),
            "why": _explain(act, user_vec),
            "future_state": _simulate_future(user_vec, act["effect"]),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

def _explain(activity: dict, user_vec: list) -> str:

    stress     = user_vec[0]
    mood       = user_vec[1]
    energy     = user_vec[2]
    motivation = user_vec[4]
    tags       = activity.get("tags", [])

    reasons = []

    if stress > 0.75 and "stress_relief" in tags:
        reasons.append(f"your stress is elevated ({stress*100:.0f}%)")
    if stress > 0.75 and "calming" in tags:
        reasons.append("this is designed to calm your nervous system")
    if mood < 0.45 and "mood_boost" in tags:
        reasons.append(f"your mood is low ({mood*100:.0f}%) and this tends to help")
    if energy < 0.35 and activity.get("effort", 2) == 1:
        reasons.append("it's low-effort — perfect when you're running low on energy")
    if motivation < 0.40 and "quick_win" in tags:
        reasons.append("it's a quick win to re-spark your motivation")
    if energy > 0.65 and "energizing" in tags:
        reasons.append(f"your energy is high ({energy*100:.0f}%) — great time to be active")
    if motivation > 0.65 and "productive" in tags:
        reasons.append(f"you're motivated ({motivation*100:.0f}%) — make the most of it")
    if "reflective" in tags and mood > 0.5:
        reasons.append("you're in a good headspace for self-reflection")

    if not reasons:
        reasons.append("it aligns well with your current mental state")

    why = "We suggested this because " + " and ".join(reasons) + "."
    return why[0].upper() + why[1:]

def _simulate_future(user_vec: list, effect: list) -> dict:

    DIMS = ["stress_level","mood_level","energy_level",
            "engagement_level","motivation_level","consistency_level"]
    future = [max(0.0, min(1.0, user_vec[i] + effect[i])) for i in range(6)]
    return {
        "future_vector": [round(v, 3) for v in future],
        "deltas": {
            DIMS[i]: round(effect[i], 3)
            for i in range(6)
            if abs(effect[i]) > 0.001
        }
    }

def safety_check(user_vec: list) -> dict | None:

    stress = user_vec[0]
    mood   = user_vec[1]
    if stress > 0.95 and mood < 0.20:
        return {
            "triggered": True,
            "message": (
                "You seem to be going through a very difficult time. Please reach out for support if you need it."
            ),
            "resources": [
                {"name": "Talk to Oasis", "url": "/chatbot"},
                {"name": "Crisis Text Line", "url": "https://www.crisistextline.org"},
                {"name": "Breathing Exercise", "url": "/activities"},
            ]
        }
    return None

def apply_activity_effect(user_vec: list, activity_id: str) -> list:

    act = next((a for a in ACTIVITIES if a["id"] == activity_id), None)
    if not act:
        return user_vec
    effect  = act.get("effect", [0.0] * 6)
    updated = [max(0.0, min(1.0, user_vec[i] + effect[i])) for i in range(6)]
    return [round(v, 4) for v in updated]

def get_recommendations(user_vec: list, top_k: int = 3) -> dict:

    safety = safety_check(user_vec)
    recs   = score_activities(user_vec, top_k=top_k)

    stress      = user_vec[0]
    mood        = user_vec[1]
    energy      = user_vec[2]
    motivation  = user_vec[4]
    consistency = user_vec[5]

    state_labels = []
    if stress > 0.75:      state_labels.append("high stress")
    elif stress < 0.35:    state_labels.append("low stress")
    if mood > 0.65:        state_labels.append("good mood")
    elif mood < 0.40:      state_labels.append("low mood")
    if energy > 0.65:      state_labels.append("energized")
    elif energy < 0.35:    state_labels.append("low energy")
    if motivation > 0.65:  state_labels.append("motivated")
    elif motivation < 0.35:state_labels.append("low motivation")
    if consistency > 0.5:  state_labels.append("consistent")

    state_summary = (
        "You are experiencing " + ", ".join(state_labels) + " right now."
        if state_labels else "Your mental state is balanced."
    )

    return {
        "recommendations": recs,
        "safety_alert": safety,
        "state_summary": state_summary,
        "user_vector": user_vec,
        "timestamp": datetime.now().isoformat(),
    }

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    test_cases = [
        {"label": "High stress, low energy",  "vec": [0.9, 0.3, 0.2, 0.4, 0.3, 0.5]},
        {"label": "Good mood, high energy",   "vec": [0.2, 0.8, 0.8, 0.6, 0.7, 0.6]},
        {"label": "Low mood, low motivation", "vec": [0.5, 0.3, 0.4, 0.3, 0.2, 0.3]},
        {"label": "Crisis state",             "vec": [0.98, 0.15, 0.1, 0.1, 0.1, 0.1]},
    ]
    for tc in test_cases:
        print(f"\n{'='*55}")
        print(f"  {tc['label']}")
        print(f"  Vector: {tc['vec']}")
        print(f"{'='*55}")
        result = get_recommendations(tc["vec"])
        if result["safety_alert"]:
            print(f"  [!] SAFETY: {result['safety_alert']['message'][:70]}...")
        print(f"  >> {result['state_summary']}")
        for i, r in enumerate(result["recommendations"], 1):
            print(f"\n  [{i}] {r['name']}  (score: {r['score']:.3f})")
            print(f"       {r['why']}")
            deltas = r["future_state"]["deltas"]
            if deltas:
                delta_str = ", ".join(f"{k.split('_')[0]}:{v:+.2f}" for k, v in deltas.items())
                print(f"       After: {delta_str}")

