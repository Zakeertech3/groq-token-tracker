import json
import csv
import sys
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

PRICE_PER_MTOK = {
    "openai/gpt-oss-20b": {"prompt": 0.075, "completion": 0.30},
    "openai/gpt-oss-120b": {"prompt": 0.15, "completion": 0.60},
    "qwen/qwen3.6-27b": {"prompt": 0.60, "completion": 3.00},
}

def cost_for(model, prompt_tokens, completion_tokens):
    rates = PRICE_PER_MTOK.get(model)
    if not rates:
        return 0.0
    return (prompt_tokens / 1_000_000) * rates["prompt"] + (completion_tokens / 1_000_000) * rates["completion"]

def load_entries(path):
    entries = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
    except FileNotFoundError:
        print(f"Error: log file not found at {path}")
        sys.exit(1)
    return entries

def in_range(ts, start, end):
    day = ts[:10]
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True

def resolve_range(args):
    today = datetime.now().strftime("%Y-%m-%d")
    if args.today:
        return today, today
    if args.week:
        return (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"), today
    return args.start, args.end

def main():
    parser = argparse.ArgumentParser(description="Groq token spend tracker")
    parser.add_argument("logfile", nargs="?", default="spend.log")
    parser.add_argument("--today", action="store_true")
    parser.add_argument("--week", action="store_true")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--budget", type=float, default=0.10)
    parser.add_argument("--csv")
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args()

    start, end = resolve_range(args)
    entries = [e for e in load_entries(args.logfile) if in_range(e["ts"], start, end)]

    by_model = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0})
    by_day = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0})
    total_cost = 0.0
    total_tokens = 0
    cache_hits = 0

    for e in entries:
        cost = cost_for(e["model"], e["prompt_tokens"], e["completion_tokens"])
        if e.get("cached"):
            cache_hits += 1
        day = e["ts"][:10]

        by_model[e["model"]]["calls"] += 1
        by_model[e["model"]]["tokens"] += e["total_tokens"]
        by_model[e["model"]]["cost"] += cost

        by_day[day]["calls"] += 1
        by_day[day]["tokens"] += e["total_tokens"]
        by_day[day]["cost"] += cost

        total_cost += cost
        total_tokens += e["total_tokens"]

    by_model = {k: v for k, v in by_model.items()}
    by_day = {k: v for k, v in by_day.items()}

    label = f" ({start or 'start'} to {end or 'now'})" if (start or end) else ""
    print(f"Spend report for {args.logfile}{label}")

    print("\nBy model")
    for model, s in sorted(by_model.items()):
        print(f"  {model}: {s['calls']} calls, {s['tokens']} tokens, ${s['cost']:.6f}")

    print("\nBy day")
    for day, s in sorted(by_day.items()):
        print(f"  {day}: {s['calls']} calls, {s['tokens']} tokens, ${s['cost']:.6f}")

    print(f"\nTotal: {len(entries)} calls ({cache_hits} cache hits), {total_tokens} tokens, ${total_cost:.6f}")

    if total_cost > args.budget:
        print(f"\nALERT: spend ${total_cost:.6f} is over budget ${args.budget:.2f}")
    else:
        print(f"\nOK: spend ${total_cost:.6f} is under budget ${args.budget:.2f}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["group_type", "key", "calls", "tokens", "cost"])
            for model, s in sorted(by_model.items()):
                w.writerow(["model", model, s["calls"], s["tokens"], f"{s['cost']:.6f}"])
            for day, s in sorted(by_day.items()):
                w.writerow(["day", day, s["calls"], s["tokens"], f"{s['cost']:.6f}"])
        print(f"Wrote CSV to {args.csv}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({
                "by_model": by_model,
                "by_day": by_day,
                "total": {"calls": len(entries), "cache_hits": cache_hits,
                          "tokens": total_tokens, "cost": round(total_cost, 6)},
            }, f, indent=2)
        print(f"Wrote JSON to {args.json_out}")

if __name__ == "__main__":
    main()
