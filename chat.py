import os
import json
import time
import hashlib
from groq import Groq

CONFIG_FILE = "config.json"
LOG_FILE = "spend.log"
HISTORY_FILE = "history.json"
CACHE_FILE = "cache.json"

PRICE_PER_MTOK = {
    "openai/gpt-oss-20b": {"prompt": 0.075, "completion": 0.30},
    "openai/gpt-oss-120b": {"prompt": 0.15, "completion": 0.60},
    "qwen/qwen3.6-27b": {"prompt": 0.60, "completion": 3.00},
}

client = Groq(api_key=os.environ["GROQ_API_KEY"])

def load_config():
    defaults = {
        "default_model": "openai/gpt-oss-20b",
        "default_temperature": 0.7,
        "budget": 0.10,
        "max_history": 10,
    }
    try:
        with open(CONFIG_FILE) as f:
            defaults.update(json.load(f))
    except FileNotFoundError:
        pass
    return defaults

def load_json_file(path, fallback):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback

def save_json_file(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def cost_for(model, prompt_tokens, completion_tokens):
    rates = PRICE_PER_MTOK.get(model)
    if not rates:
        return 0.0
    return (prompt_tokens / 1_000_000) * rates["prompt"] + (completion_tokens / 1_000_000) * rates["completion"]

def cheapest_priciest(prompt_tokens, completion_tokens):
    costs = {m: cost_for(m, prompt_tokens, completion_tokens) for m in PRICE_PER_MTOK}
    low = min(costs, key=costs.get)
    high = max(costs, key=costs.get)
    return (low, costs[low]), (high, costs[high])

def estimate_tokens(text):
    return max(1, len(text) // 4)

def cache_key(model, temperature, prompt):
    raw = f"{model}|{temperature}|{prompt}"
    return hashlib.sha256(raw.encode()).hexdigest()

def log_usage(model, temperature, usage, latency, cached):
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": model,
        "temperature": temperature,
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
        "latency_s": round(latency, 3),
        "cached": cached,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def print_help():
    print("Commands:")
    print("  exit          quit and save history")
    print("  /model        switch model")
    print("  /models       list models")
    print("  /temp         set temperature (0 to 2)")
    print("  /stats        show session totals")
    print("  /help         show this list")

def main():
    config = load_config()
    model = config["default_model"]
    temperature = config["default_temperature"]
    budget = config["budget"]
    max_history = config["max_history"]

    if model not in PRICE_PER_MTOK:
        print(f"Config model '{model}' not in table, falling back to gpt-oss-20b.")
        model = "openai/gpt-oss-20b"

    messages = load_json_file(HISTORY_FILE, [])
    cache = load_json_file(CACHE_FILE, {})

    session_tokens = 0
    session_cost = 0.0

    print("Chat started. Type /help for commands.")
    print(f"Model: {model} | Temp: {temperature}")
    if messages:
        print(f"Loaded {len(messages)} messages from previous session.")

    while True:
        user_input = input("\nYou: ")
        stripped = user_input.strip()
        low = stripped.lower()

        if low == "exit":
            break

        if low == "/help":
            print_help()
            continue

        if low == "/models":
            for name in PRICE_PER_MTOK:
                print(f"  {name}")
            continue

        if low == "/model":
            choice = input("Enter model name: ").strip()
            if choice in PRICE_PER_MTOK:
                model = choice
                print(f"Switched to {model}")
            else:
                print("Unknown model. Type /models to see options.")
            continue

        if low == "/temp":
            raw = input("Enter temperature (0 to 2): ").strip()
            try:
                t = float(raw)
                if 0.0 <= t <= 2.0:
                    temperature = t
                    print(f"Temperature set to {temperature}")
                else:
                    print("Out of range. Use 0 to 2.")
            except ValueError:
                print("Not a number.")
            continue

        if low == "/stats":
            print(f"Session: {session_tokens} tokens, ${session_cost:.6f}")
            print(f"Status: {'OVER' if session_cost > budget else 'under'} budget ${budget:.2f}")
            continue

        print(f"(estimated prompt tokens: ~{estimate_tokens(user_input)})")

        key = cache_key(model, temperature, user_input)
        if key in cache:
            reply = cache[key]
            print(f"\nAssistant (cached): {reply}")
            print(f"\n[CACHE HIT | {model} | turn: 0 tokens, $0.000000 | session: {session_tokens} tokens, ${session_cost:.6f}]")
            log_usage(model, temperature,
                      {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                      0.0, True)
            continue

        messages.append({"role": "user", "content": user_input})
        messages = messages[-max_history:]

        start = time.time()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
        except Exception as e:
            print(f"\nError: {e}")
            messages.pop()
            continue
        latency = time.time() - start

        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        messages = messages[-max_history:]

        u = response.usage
        usage = {
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "total_tokens": u.total_tokens,
        }

        cache[key] = reply
        save_json_file(CACHE_FILE, cache)

        log_usage(model, temperature, usage, latency, False)

        turn_cost = cost_for(model, u.prompt_tokens, u.completion_tokens)
        session_tokens += u.total_tokens
        session_cost += turn_cost

        (low_m, low_c), (high_m, high_c) = cheapest_priciest(u.prompt_tokens, u.completion_tokens)

        print(f"\nAssistant: {reply}")
        print(f"\n[{model} | temp {temperature} | {u.total_tokens} tokens | ${turn_cost:.6f} | {latency:.2f}s]")
        print(f"[session: {session_tokens} tokens, ${session_cost:.6f}]")
        print(f"[same exchange: cheapest {low_m} ${low_c:.6f} | priciest {high_m} ${high_c:.6f}]")

    save_json_file(HISTORY_FILE, messages)
    print(f"\nSession ended. Total: {session_tokens} tokens, ${session_cost:.6f}")
    print("History saved.")

if __name__ == "__main__":
    main()
