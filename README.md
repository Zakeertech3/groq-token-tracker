# groq-token-tracker

A command-line tool to track token usage, cost, and latency across Groq models. Chat with any supported Groq model and see exactly what each call costs in tokens, dollars, and time, then roll up your spend by model and by day.

## Features

- Interactive chat with multi-turn context across Groq models
- Per-call breakdown of tokens, cost, and latency
- Running session totals for tokens and cost
- Cost comparison showing the same exchange priced against every model
- Exact-match response cache, repeated prompts return instantly at zero cost
- Persistent chat history and cache that survive restarts
- Adjustable temperature and model switching mid-session
- Spend tracker with date filters, budget alerts, and CSV/JSON export
- Config-driven defaults with no code edits required

## Supported models

| Model | Input ($/M tokens) | Output ($/M tokens) |
| --- | --- | --- |
| openai/gpt-oss-20b | 0.075 | 0.30 |
| openai/gpt-oss-120b | 0.15 | 0.60 |
| qwen/qwen3.6-27b | 0.60 | 3.00 |

Pricing last verified against https://groq.com/pricing on 2026-06-27. Prices and model availability change; verify against the official page before relying on the figures.

## Requirements

- Python 3.11 or newer
- A Groq API key (free tier works): https://console.groq.com/keys

## Installation

```bash
git clone git@github.com:Zakeertech3/groq-token-tracker.git
cd groq-token-tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your API key:

```bash
export GROQ_API_KEY="your_key_here"
```

## Usage

### Chat

```bash
python chat.py
```

Available commands inside the chat:

| Command | Action |
| --- | --- |
| `/model` | Switch to a different model |
| `/models` | List supported models |
| `/temp` | Set temperature (0 to 2) |
| `/stats` | Show session totals |
| `/help` | List all commands |
| `exit` | Quit and save history |

Every reply prints the model, temperature, token count, cost, and latency, along with a comparison of what the same exchange would cost on the cheapest and priciest models.

### Tracker

Roll up spend from the log the chat produces:

```bash
python tracker.py                          # all-time totals
python tracker.py --today                  # today only
python tracker.py --week                   # last 7 days
python tracker.py --start 2026-06-01 --end 2026-06-27
python tracker.py --budget 0.05            # custom budget threshold
python tracker.py --today --csv report.csv # export to CSV
python tracker.py --json report.json       # export to JSON
```

Because the tracker reads a log path, it works on any project that writes the same log format:

```bash
python tracker.py path/to/other/spend.log --week
```

## Configuration

Defaults live in `config.json`:

```json
{
  "default_model": "openai/gpt-oss-20b",
  "default_temperature": 0.7,
  "budget": 0.10,
  "max_history": 10
}
```

## How it works

The chat app and the tracker are decoupled. The chat app writes one JSON line per call to `spend.log` (model, temperature, tokens, latency, cache status). The tracker reads that log and produces the rollups. They share nothing but the log file, so the tracker can point at any compatible log.

Each log entry looks like:

```json
{"ts": "2026-06-27T08:08:27", "model": "openai/gpt-oss-20b", "temperature": 0.7, "prompt_tokens": 39, "completion_tokens": 501, "total_tokens": 540, "latency_s": 5.83, "cached": false}
```

## Notes and limitations

- The cache keys on model, temperature, and prompt text, not full conversation history, so an identical prompt in a different context returns the cached answer.
- The pre-send token estimate is an approximation; the exact count comes from the API response.
- `spend.log`, `history.json`, and `cache.json` are gitignored, your usage data stays local.

## License

MIT
