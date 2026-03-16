"""Extract automation barrier/enabler themes from AI scoring rationales."""

import json
import re
from pathlib import Path
from collections import Counter

SCORES_FILE = Path("scores.json")
OUTPUT_FILE = Path("data/themes.json")

# Theme definitions: keyword patterns → theme label
THEME_PATTERNS = {
    "physical_presence": [
        r"physical", r"hands-on", r"manual", r"on-site", r"in-person",
        r"bodily", r"dexterity", r"machinery", r"equipment operation",
    ],
    "regulatory_trust": [
        r"regulat", r"compliance", r"licens", r"certif", r"legal requirement",
        r"trust", r"fiduciary", r"accountability", r"liability",
    ],
    "creative_judgment": [
        r"creative", r"artistic", r"judgment", r"intuition", r"nuance",
        r"empathy", r"emotional", r"interpersonal", r"counselling",
    ],
    "digital_data": [
        r"digital", r"data\b", r"database", r"software", r"computer",
        r"electronic", r"online", r"text-based", r"document",
    ],
    "client_relationship": [
        r"client", r"patient", r"customer", r"stakeholder", r"relationship",
        r"face-to-face", r"negotiat",
    ],
    "routine_cognitive": [
        r"routine", r"repetitive", r"standardized", r"systematic",
        r"processing", r"clerical", r"administrative",
    ],
    "complex_analysis": [
        r"complex analysis", r"strategic", r"research", r"analytical",
        r"problem-solving", r"diagnostic",
    ],
    "outdoor_environment": [
        r"outdoor", r"weather", r"terrain", r"field work", r"unpredictable environment",
        r"remote location", r"natural resource",
    ],
    "safety_critical": [
        r"safety", r"emergency", r"life-threatening", r"hazard",
        r"protective", r"security",
    ],
    "content_generation": [
        r"writing", r"editing", r"translat", r"content creat",
        r"report generat", r"drafting", r"correspondence",
    ],
}


def extract_themes(rationale: str) -> list[str]:
    """Extract theme tags from a rationale string."""
    text = rationale.lower()
    themes = []
    for theme, patterns in THEME_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text):
                themes.append(theme)
                break
    return themes


def main() -> None:
    scores = json.loads(SCORES_FILE.read_text())
    print(f"Loaded {len(scores)} rationales")

    results = {}
    theme_counts = Counter()
    unmatched = 0

    for noc_code, data in scores.items():
        rationale = data.get("rationale", "")
        themes = extract_themes(rationale)
        results[noc_code] = {
            "themes": themes,
            "rationale": rationale,
        }
        for t in themes:
            theme_counts[t] += 1
        if not themes:
            unmatched += 1

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(results, indent=2))
    print(f"Saved themes to {OUTPUT_FILE}")
    print(f"\nCoverage: {len(scores) - unmatched}/{len(scores)} ({(len(scores)-unmatched)/len(scores)*100:.0f}%) have at least one theme")
    print(f"\nTheme distribution:")
    for theme, count in theme_counts.most_common():
        label = theme.replace("_", " ").title()
        print(f"  {label}: {count} ({count/len(scores)*100:.0f}%)")


if __name__ == "__main__":
    main()
