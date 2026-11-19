"""Replace the hard-coded FX tables in the Power BI measures with DimDate.

Every USD measure in powerbi/.../_Measures.tmdl repeated the same table:

    SWITCH(YEAR(...), 2021, 43.6, 2022, 41.2, 2023, 38.8, 2024, 40.3, 2025, 42.0, 2026, 43.5)

The model already defines that table once, as the calculated column
DimDate[UYU per USD]. This script points every measure at it:

- inside an iterator over a fact table related to DimDate
  (SWITCH(YEAR('Fact'[year_month]), ...) or a CurrentYear variable built that way)
      -> RELATED('DimDate'[UYU per USD])
- inside an iterator over month values (VAR CurrentMonth = 'Fact'[year_month])
      -> LOOKUPVALUE('DimDate'[UYU per USD], 'DimDate'[Date], CurrentMonth)

Measure names, format strings and results do not change: every fact table's
year_month falls in 2021-2026, the years DimDate[UYU per USD] defines, so the
rate each row receives is identical. Variables left unused by the change
(CurrentYear) are removed.

It also aligns the colors returned by the 'Exec Color ...' and
'Credit Loss Bar Color' measures with the corporate report theme.

Usage (Power BI Desktop must be closed):

    python scripts/dashboard/refactor_fx_measures.py            # dry run
    python scripts/dashboard/refactor_fx_measures.py --apply    # write
"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEASURES = (
    REPO_ROOT / "powerbi" / "BTYT_Banking_Analytics.SemanticModel" / "definition"
    / "tables" / "_Measures.tmdl"
)

RATE_ROW = "RELATED('DimDate'[UYU per USD])"
RATE_MONTH = "LOOKUPVALUE('DimDate'[UYU per USD], 'DimDate'[Date], CurrentMonth)"

SWITCH_FX = re.compile(
    r"SWITCH\(\s*(?P<arg>[^,]+?),\s*"
    r"2021, 43\.6,\s*2022, 41\.2,\s*2023, 38\.8,\s*2024, 40\.3,\s*2025, 42\.0,\s*2026, 43\.5"
    r"(?:,\s*(?:1|BLANK\(\)))?\s*\)"
)
CURRENT_YEAR_DEF = re.compile(r"VAR CurrentYear =\s*(?P<expr>[^\n]+)")
MEASURE_SPLIT = re.compile(r"(?=^\tmeasure )", re.M)

# Old dark-theme colors in DAX color measures -> corporate theme colors.
COLOR_MAP = {
    '"#3FB950"': '"#2E7D32"',  # good
    '"#F85149"': '"#C0392B"',  # bad
    '"#8B949E"': '"#8A95A3"',  # neutral
    '"#6E7681"': '"#A9B8C9"',  # context bars
}


def rate_for(arg: str, measure_text: str) -> str:
    arg = " ".join(arg.split())
    if re.fullmatch(r"YEAR\('[^']+'\[year_month\]\)", arg):
        return RATE_ROW
    if arg == "YEAR(CurrentMonth)":
        return RATE_MONTH
    if arg == "CurrentYear":
        definition = " ".join(CURRENT_YEAR_DEF.search(measure_text).group("expr").split())
        if definition == "YEAR(CurrentMonth)":
            return RATE_MONTH
        if re.fullmatch(r"YEAR\('[^']+'\[year_month\]\)", definition):
            return RATE_ROW
    raise ValueError(f"Unhandled FX argument: {arg!r}")


def drop_unused_current_year(measure_text: str) -> str:
    if measure_text.count("CurrentYear") != 1:
        return measure_text
    # Remove "VAR CurrentYear =" plus its expression (same or next line) and one blank line after.
    return re.sub(
        r"\n[ \t]*VAR CurrentYear =[ \t]*(?:\n[ \t]*)?[^\n]+\n(?:[ \t]*\n)?",
        "\n",
        measure_text,
        count=1,
    )


def refactor(text: str):
    parts = MEASURE_SPLIT.split(text)
    out, changed = [], []
    for part in parts:
        if not part.startswith("\tmeasure "):
            out.append(part)
            continue
        name = part.split("\n", 1)[0][len("\tmeasure "):].rsplit(" =", 1)[0]
        new, n = part, 0
        while True:
            m = SWITCH_FX.search(new)
            if not m:
                break
            new = new[:m.start()] + rate_for(m.group("arg"), new) + new[m.end():]
            n += 1
        if n:
            new = drop_unused_current_year(new)
        recolored = new
        for old, col in COLOR_MAP.items():
            recolored = recolored.replace(old, col)
        if n or recolored != part:
            changed.append((name, n, recolored != new))
        out.append(recolored)
    return "".join(out), changed


def main() -> None:
    apply = "--apply" in sys.argv
    raw = MEASURES.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    new, changed = refactor(text)

    remaining = len(re.findall(r"2021, 43\.6", new))
    blocks = sum(n for _, n, _ in changed)
    print(f"Measures changed: {len(changed)} | FX blocks replaced: {blocks} | FX blocks left: {remaining}")
    for name, n, recolored in changed:
        print(f"  {name}: {n} FX block(s){' + colors' if recolored else ''}")
    if remaining:
        raise SystemExit("Some FX blocks were not replaced; nothing written.")

    output = new.replace("\n", "\r\n") if crlf else new
    if apply:
        # Keep the backup outside the model folder so Power BI never reads it.
        backup = Path(tempfile.gettempdir()) / "_Measures.before_fx_refactor.tmdl"
        shutil.copy2(MEASURES, backup)
        MEASURES.write_bytes(output.encode("utf-8"))
        print(f"Written. Backup: {backup}")
    else:
        preview = Path(sys.argv[sys.argv.index("--preview") + 1]) if "--preview" in sys.argv else None
        if preview:
            preview.write_bytes(output.encode("utf-8"))
            print(f"Dry run. Preview written to {preview}")
        else:
            print("Dry run. Nothing written (use --apply).")


if __name__ == "__main__":
    main()
