"""Classify each occupation as public/private/mixed sector using Claude API."""

import json
import time
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

load_dotenv()

PAGES_DIR = Path("pages")
SECTOR_FILE = Path("data/sectors.json")
MODEL = "claude-sonnet-4-20250514"
BATCH_DELAY = 0.3

MAX_SPEND_USD = 10.00
COST_PER_M_INPUT = 3.00
COST_PER_M_OUTPUT = 15.00

SYSTEM_PROMPT = """You are a Canadian labour market expert. For each occupation, estimate what percentage of workers are employed in the public sector vs private sector in Canada.

Public sector includes: federal/provincial/territorial/municipal government, Crown corporations, public schools, public universities, public hospitals, military, police, courts, regulatory bodies.

Private sector includes: private companies, self-employed, non-profit organizations, private practices.

Respond with ONLY valid JSON (no markdown fencing):
{"public_pct": <0-100>, "private_pct": <0-100>, "sector": "<public|private|mixed>", "rationale": "<1 sentence>"}

Rules for the "sector" field:
- "public" if public_pct >= 60
- "private" if private_pct >= 60
- "mixed" if neither exceeds 60"""


class CostTracker:
    def __init__(self, max_usd):
        self.max_usd = max_usd
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def total_cost(self):
        return (self.total_input_tokens / 1_000_000 * COST_PER_M_INPUT
                + self.total_output_tokens / 1_000_000 * COST_PER_M_OUTPUT)

    def record(self, usage):
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens

    def check_budget(self):
        return self.total_cost < self.max_usd

    def summary(self):
        return f"${self.total_cost:.2f} spent ({self.total_input_tokens:,} in / {self.total_output_tokens:,} out)"


def classify(client, profile_text, tracker):
    response = client.messages.create(
        model=MODEL,
        max_tokens=150,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Classify this Canadian occupation:\n\n{profile_text}"}],
    )
    tracker.record(response.usage)
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def main():
    if SECTOR_FILE.exists():
        sectors = json.loads(SECTOR_FILE.read_text())
        print(f"Loaded {len(sectors)} existing classifications")
    else:
        sectors = {}

    profiles = sorted(PAGES_DIR.glob("*.md"))
    remaining = [p for p in profiles if p.stem not in sectors]
    print(f"{len(profiles)} total, {len(remaining)} remaining")
    print(f"Budget: ${MAX_SPEND_USD:.2f} max")

    if not remaining:
        print("All classified!")
        show_summary(sectors)
        return

    client = anthropic.Anthropic()
    tracker = CostTracker(MAX_SPEND_USD)
    consecutive_errors = 0

    for i, path in enumerate(remaining):
        if not tracker.check_budget():
            print(f"\n  BUDGET LIMIT: {tracker.summary()}")
            break

        noc = path.stem
        text = path.read_text()

        try:
            result = classify(client, text, tracker)
            sectors[noc] = result
            consecutive_errors = 0
            print(f"  [{i+1}/{len(remaining)}] {noc}: {result['sector']} "
                  f"(pub:{result['public_pct']}% priv:{result['private_pct']}%) "
                  f"[{tracker.summary()}]")

            SECTOR_FILE.parent.mkdir(exist_ok=True)
            SECTOR_FILE.write_text(json.dumps(sectors, indent=2))
            time.sleep(BATCH_DELAY)

        except (json.JSONDecodeError, KeyError) as e:
            consecutive_errors += 1
            print(f"  Bad response for {noc}: {e}", file=sys.stderr)
        except Exception as e:
            consecutive_errors += 1
            print(f"  ERROR {noc}: {e}", file=sys.stderr)

        if consecutive_errors >= 5:
            print("  5 consecutive errors — stopping.")
            break

    print(f"\nDone! {len(sectors)} classified. {tracker.summary()}")
    show_summary(sectors)


def show_summary(sectors):
    from collections import Counter
    counts = Counter(v["sector"] for v in sectors.values())
    print(f"\nSector distribution:")
    for s, c in counts.most_common():
        print(f"  {s}: {c}")


if __name__ == "__main__":
    main()
