"""Build Markdown occupation profiles from NOC structure + elements CSVs."""

from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")
PAGES_DIR = Path("pages")
CODE_COL = "Code - NOC 2021 V1.0"

# Order in which to render element types
SECTION_ORDER = [
    "Main duties",
    "Employment requirements",
    "Additional information",
    "Illustrative example(s)",
    "All examples",
    "Inclusion(s)",
    "Exclusion(s)",
]

SECTION_HEADINGS = {
    "Main duties": "Main Duties",
    "Employment requirements": "Employment Requirements",
    "Additional information": "Additional Information",
    "Illustrative example(s)": "Example Job Titles",
    "All examples": "All Example Titles",
    "Inclusion(s)": "Inclusions",
    "Exclusion(s)": "Exclusions",
}


def build_profile(noc_code: str, title: str, definition: str,
                  elements: pd.DataFrame) -> str:
    """Build a Markdown profile for one occupation."""
    lines = [f"# {title}", f"**NOC Code:** {noc_code}", "", definition, ""]

    occ_elements = elements[elements[CODE_COL].astype(str).str.zfill(5) == noc_code]

    for etype in SECTION_ORDER:
        section = occ_elements[occ_elements["Element Type Label English"] == etype]
        if section.empty:
            continue

        heading = SECTION_HEADINGS.get(etype, etype)
        lines.append(f"## {heading}")
        lines.append("")

        items = section["Element Description English"].tolist()
        for item in items:
            text = item.strip()
            if text.startswith("This group performs"):
                lines.append(text)
            elif text.endswith("(See") or "(See " in text:
                lines.append(f"- {text}")
            else:
                lines.append(f"- {text}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    PAGES_DIR.mkdir(exist_ok=True)

    print("Loading NOC structure...")
    structure = pd.read_csv(DATA_DIR / "noc_structure.csv")
    units = structure[structure["Level"] == 5].copy()
    units["noc_code"] = units[CODE_COL].astype(str).str.zfill(5)

    print("Loading NOC elements...")
    elements = pd.read_csv(DATA_DIR / "noc_elements.csv")
    elements = elements[elements["Level"] == 5]  # Only unit groups

    print(f"Building {len(units)} occupation profiles...")
    for _, row in units.iterrows():
        noc_code = row["noc_code"]
        title = row["Class title"]
        definition = row["Class definition"]

        md = build_profile(noc_code, title, definition, elements)

        out_path = PAGES_DIR / f"{noc_code}.md"
        out_path.write_text(md, encoding="utf-8")

    print(f"Saved {len(units)} Markdown files to {PAGES_DIR}/")

    # Show a sample
    sample = PAGES_DIR / "21233.md"
    if sample.exists():
        print(f"\n--- Sample: {sample} ---")
        print(sample.read_text()[:1000])


if __name__ == "__main__":
    main()
