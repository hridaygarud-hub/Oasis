import urllib.request, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:5033"

print("\n" + "="*60)
print("  LIVE API TEST — Oasis Vector + Recommendation System")
print("="*60)

r    = urllib.request.urlopen(f"{BASE}/api/all_user_ids")
data = json.loads(r.read())
print(f"\n[1] User IDs:  {data['user_ids']}")

for uid in data["user_ids"]:
    r    = urllib.request.urlopen(f"{BASE}/api/user_vector?user_id={uid}&window_days=365")
    d    = json.loads(r.read())
    print(f"\n[2] Vector for user {uid}:")
    print(f"    Events used : {d['meta']['events_used']}")
    for dim, val in d["dimensions"].items():
        bar = "#" * int(val * 20) + "." * (20 - int(val * 20))
        print(f"    {dim:<22} {bar}  {val:.4f}")

for uid in data["user_ids"]:
    r    = urllib.request.urlopen(f"{BASE}/api/recommendations?user_id={uid}&top_k=3&window_days=365")
    d    = json.loads(r.read())
    print(f"\n[3] Recommendations for user {uid}:")
    print(f"    State : {d['state_summary']}")
    if d.get("safety_alert"):
        print(f"    SAFETY TRIGGERED: {d['safety_alert']['message'][:60]}...")
    for i, rec in enumerate(d["recommendations"], 1):
        print(f"\n    [{i}] {rec['name']}  (score={rec['score']:.3f}, match={round(rec['score']*100)}%)")
        print(f"         Why : {rec['why'][:90]}")
        deltas = rec["future_state"]["deltas"]
        if deltas:
            ds = ", ".join(f"{k.split('_')[0]}:{v:+.2f}" for k, v in deltas.items())
            print(f"         After: {ds}")

print("\n" + "="*60)
print("  All systems operational.")
print("="*60)
print("\nOpen in browser:")
print(f"  Main app          ->  {BASE}/")
print(f"  For You (new)     ->  {BASE}/recommend")
print(f"  Vector Dashboard  ->  {BASE}/vector-dashboard")
print(f"  Activities        ->  {BASE}/activities")
