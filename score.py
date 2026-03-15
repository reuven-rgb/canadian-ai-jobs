"""Score each occupation's AI exposure using Claude API."""

import json
import time
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

load_dotenv()

PAGES_DIR = Path("pages")
SCORES_FILE = Path("scores.json")
MODEL = "claude-sonnet-4-20250514"
BATCH_DELAY = 0.5  # seconds between API calls

# Cost tracking
MAX_SPEND_USD = 10.00
COST_PER_M_INPUT = 3.00   # Sonnet 4 pricing
COST_PER_M_OUTPUT = 15.00

SYSTEM_PROMPT = """You are an expert analyst assessing AI exposure for Canadian occupations.

Score each occupation on a 0-10 scale based on how much AI/LLMs could automate or augment the work:

| Score | Level | Characteristics |
|-------|-------|----------------|
| 0-1 | Minimal | Primarily physical/manual work in unpredictable environments |
| 2-3 | Low | Mostly physical with some routine cognitive tasks |
| 4-5 | Moderate | Mix of physical and cognitive; some tasks automatable |
| 6-7 | High | Primarily cognitive/knowledge work; significant portions automatable |
| 8-9 | Very high | Almost entirely digital/cognitive; most tasks could be AI-assisted |
| 10 | Maximum | Entirely digital text/data processing; AI can perform most core functions |

Key signal: Is the work product fundamentally digital? Can the job be done entirely from a home office on a computer? If yes, AI exposure is inherently high.

Consider:
- What percentage of core duties involve text, data, or digital content creation?
- How much judgment, creativity, or physical presence is required?
- Are there regulatory or trust barriers to AI adoption in this field?
- Canadian-specific factors: bilingual requirements, regulatory environment

Respond with ONLY valid JSON (no markdown fencing):
{"score": <0-10>, "rationale": "<1-2 sentence explanation>"}"""


class CostTracker:
    """Track API spend and enforce a hard cap."""

    def __init__(self, max_usd: float):
        self.max_usd = max_usd
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def total_cost(self) -> float:
        return (
            self.total_input_tokens / 1_000_000 * COST_PER_M_INPUT
            + self.total_output_tokens / 1_000_000 * COST_PER_M_OUTPUT
        )

    def record(self, usage) -> None:
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens

    def check_budget(self) -> bool:
        """Return True if we're still under budget."""
        return self.total_cost < self.max_usd

    def summary(self) -> str:
        return (
            f"${self.total_cost:.2f} spent "
            f"({self.total_input_tokens:,} in / {self.total_output_tokens:,} out)"
        )


def score_occupation(client: anthropic.Anthropic, profile_text: str, tracker: CostTracker) -> dict:
    """Send one occupation profile to Claude for scoring."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Score this occupation's AI exposure:\n\n{profile_text}"}],
    )
    tracker.record(response.usage)

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def main() -> None:
    # Load existing scores to allow resumption
    if SCORES_FILE.exists():
        scores = json.loads(SCORES_FILE.read_text())
        print(f"Loaded {len(scores)} existing scores")
    else:
        scores = {}

    # Get all occupation profiles
    profiles = sorted(PAGES_DIR.glob("*.md"))
    remaining = [p for p in profiles if p.stem not in scores]
    print(f"{len(profiles)} total occupations, {len(remaining)} remaining to score")
    print(f"Budget: ${MAX_SPEND_USD:.2f} max")

    if not remaining:
        print("All occupations already scored!")
        return

    client = anthropic.Anthropic()
    tracker = CostTracker(MAX_SPEND_USD)
    consecutive_errors = 0

    for i, profile_path in enumerate(remaining):
        # Budget check before each call
        if not tracker.check_budget():
            print(f"\n  BUDGET LIMIT REACHED: {tracker.summary()}")
            print(f"  Stopping. {len(remaining) - i} occupations remaining.")
            break

        noc_code = profile_path.stem
        text = profile_path.read_text()

        try:
            result = score_occupation(client, text, tracker)
            scores[noc_code] = result
            consecutive_errors = 0
            print(f"  [{i+1}/{len(remaining)}] NOC {noc_code}: {result['score']}/10 - "
                  f"{result['rationale'][:70]}  [{tracker.summary()}]")

            # Save after each score for resumability
            SCORES_FILE.write_text(json.dumps(scores, indent=2))

            time.sleep(BATCH_DELAY)

        except anthropic.RateLimitError:
            print(f"  Rate limited at {noc_code}, waiting 30s...")
            time.sleep(30)
            try:
                result = score_occupation(client, text, tracker)
                scores[noc_code] = result
                SCORES_FILE.write_text(json.dumps(scores, indent=2))
                print(f"  [{i+1}/{len(remaining)}] NOC {noc_code}: {result['score']}/10 (retry)")
            except Exception as e:
                print(f"  FAILED on retry for {noc_code}: {e}", file=sys.stderr)

        except (json.JSONDecodeError, KeyError) as e:
            consecutive_errors += 1
            print(f"  Bad response for {noc_code}: {e}", file=sys.stderr)

        except Exception as e:
            consecutive_errors += 1
            print(f"  ERROR scoring {noc_code}: {e}", file=sys.stderr)

        if consecutive_errors >= 5:
            print(f"\n  5 consecutive errors — stopping. Check your API key and billing.")
            break

    print(f"\nDone! {len(scores)} occupations scored, saved to {SCORES_FILE}")
    print(f"Total API cost: {tracker.summary()}")

    # Summary stats
    scored_values = [v["score"] for v in scores.values() if "score" in v]
    if scored_values:
        avg = sum(scored_values) / len(scored_values)
        print(f"Average AI exposure: {avg:.1f}/10")
        print(f"Distribution:")
        for bucket in range(0, 11, 2):
            count = sum(1 for s in scored_values if bucket <= s < bucket + 2)
            bar = "#" * count
            print(f"  {bucket}-{bucket+1}: {bar} ({count})")


if __name__ == "__main__":
    main()
