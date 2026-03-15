"""Merge occupations.csv + scores.json into site/data.json for the treemap."""

import json
import pandas as pd
from pathlib import Path

OCCUPATIONS_CSV = Path("occupations.csv")
SCORES_FILE = Path("scores.json")
SITE_DATA = Path("site/data.json")


def main() -> None:
    print("Loading occupations...")
    df = pd.read_csv(OCCUPATIONS_CSV, dtype={"noc_code": str})
    print(f"  {len(df)} occupations")

    # Load scores
    if SCORES_FILE.exists():
        scores = json.loads(SCORES_FILE.read_text())
        print(f"  {len(scores)} scores loaded")
    else:
        print("  WARNING: No scores.json found — using placeholder scores of 5")
        scores = {}

    # Build compact data structure for the site
    occupations = []
    for _, row in df.iterrows():
        noc = str(row["noc_code"]).zfill(5)
        score_data = scores.get(noc, {})

        occ = {
            "noc": noc,
            "title": row["title"],
            "broad_category": int(row["broad_category"]),
            "broad_category_name": row["broad_category_name"],
            "teer": int(row["teer"]),
            "wage_median": row["wage_median"] if pd.notna(row["wage_median"]) else None,
            "wage_low": row["wage_low"] if pd.notna(row["wage_low"]) else None,
            "wage_high": row["wage_high"] if pd.notna(row["wage_high"]) else None,
            "ai_score": score_data.get("score", 5),
            "ai_rationale": score_data.get("rationale", ""),
            "timeline": row.get("timeline", "") if pd.notna(row.get("timeline")) else "",
            "outlook": row.get("outlook", "") if pd.notna(row.get("outlook")) else "",
            "employment": int(row["employment"]) if pd.notna(row.get("employment")) else None,
            "alpha": round(row["alpha"], 3) if pd.notna(row.get("alpha")) else None,
            "beta": round(row["beta"], 3) if pd.notna(row.get("beta")) else None,
            "gamma": round(row["gamma"], 3) if pd.notna(row.get("gamma")) else None,
        }
        occupations.append(occ)

    # Sort by broad category then title
    occupations.sort(key=lambda x: (x["broad_category"], x["title"]))

    SITE_DATA.parent.mkdir(exist_ok=True)
    SITE_DATA.write_text(json.dumps(occupations, indent=None))
    print(f"\nSaved {len(occupations)} occupations to {SITE_DATA}")
    print(f"  File size: {SITE_DATA.stat().st_size:,} bytes")

    # Stats
    scored = [o for o in occupations if o["ai_rationale"]]
    print(f"  With real scores: {len(scored)}")
    print(f"  With placeholder scores: {len(occupations) - len(scored)}")


if __name__ == "__main__":
    main()
