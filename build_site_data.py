"""Merge occupations.csv + scores.json + themes.json into site/data.json."""

import json
import ast
import pandas as pd
from pathlib import Path

OCCUPATIONS_CSV = Path("occupations.csv")
SCORES_FILE = Path("scores.json")
THEMES_FILE = Path("data/themes.json")
SECTOR_FILE = Path("data/sectors.json")
SITE_DATA = Path("site/data.json")


def safe_float(val, decimals=3):
    if pd.notna(val):
        return round(float(val), decimals)
    return None


def safe_int(val):
    if pd.notna(val):
        return int(val)
    return None


def main() -> None:
    print("Loading occupations...")
    df = pd.read_csv(OCCUPATIONS_CSV, dtype={"noc_code": str})
    print(f"  {len(df)} occupations")

    # Load scores
    scores = {}
    if SCORES_FILE.exists():
        scores = json.loads(SCORES_FILE.read_text())
        print(f"  {len(scores)} scores loaded")

    # Load themes
    themes = {}
    if THEMES_FILE.exists():
        themes = json.loads(THEMES_FILE.read_text())
        print(f"  {len(themes)} theme entries loaded")

    # Load sector classifications
    sectors = {}
    if SECTOR_FILE.exists():
        sectors = json.loads(SECTOR_FILE.read_text())
        print(f"  {len(sectors)} sector classifications loaded")

    # Build data structure
    occupations = []
    for _, row in df.iterrows():
        noc = str(row["noc_code"]).zfill(5)
        score_data = scores.get(noc, {})
        theme_data = themes.get(noc, {})
        sector_data = sectors.get(noc, {})

        # Parse growth_by_year from string repr of list
        growth_by_year = None
        raw = row.get("growth_by_year")
        if pd.notna(raw) and raw:
            try:
                growth_by_year = ast.literal_eval(str(raw))
            except (ValueError, SyntaxError):
                pass

        occ = {
            "noc": noc,
            "title": row["title"],
            "broad_category": int(row["broad_category"]),
            "broad_category_name": row["broad_category_name"],
            "teer": int(row["teer"]),
            "wage_median": safe_float(row.get("wage_median"), 0),
            "wage_low": safe_float(row.get("wage_low"), 0),
            "wage_high": safe_float(row.get("wage_high"), 0),
            "ai_score": score_data.get("score", 5),
            "ai_rationale": score_data.get("rationale", ""),
            "timeline": row.get("timeline", "") if pd.notna(row.get("timeline")) else "",
            "outlook": row.get("outlook", "") if pd.notna(row.get("outlook")) else "",
            "employment": safe_int(row.get("employment")),
            "alpha": safe_float(row.get("alpha")),
            "beta": safe_float(row.get("beta")),
            "gamma": safe_float(row.get("gamma")),
            # New: supply/demand
            "job_openings": safe_int(row.get("job_openings")),
            "job_seekers": safe_int(row.get("job_seekers")),
            "supply_demand_ratio": safe_float(row.get("supply_demand_ratio")),
            "immigration": safe_int(row.get("immigration")),
            "immigration_share": safe_float(row.get("immigration_share")),
            # New: rater disagreement
            "human_alpha": safe_float(row.get("human_alpha")),
            "ai_alpha": safe_float(row.get("ai_alpha")),
            "disagreement": safe_float(row.get("disagreement")),
            # New: growth trajectory
            "growth_by_year": growth_by_year,
            # New: themes
            "themes": theme_data.get("themes", []),
            # New: sector
            "sector": sector_data.get("sector", ""),
            "public_pct": sector_data.get("public_pct"),
            "private_pct": sector_data.get("private_pct"),
        }
        occupations.append(occ)

    occupations.sort(key=lambda x: (x["broad_category"], x["title"]))

    SITE_DATA.parent.mkdir(exist_ok=True)
    SITE_DATA.write_text(json.dumps(occupations, indent=None))
    print(f"\nSaved {len(occupations)} occupations to {SITE_DATA}")
    print(f"  File size: {SITE_DATA.stat().st_size:,} bytes")

    # Stats
    with_themes = sum(1 for o in occupations if o["themes"])
    with_supply = sum(1 for o in occupations if o["supply_demand_ratio"] is not None)
    with_growth = sum(1 for o in occupations if o["growth_by_year"])
    print(f"  With themes: {with_themes}")
    print(f"  With supply/demand: {with_supply}")
    print(f"  With growth curves: {with_growth}")


if __name__ == "__main__":
    main()
