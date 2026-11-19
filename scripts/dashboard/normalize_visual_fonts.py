"""Let the report theme control text sizes: drop per-visual font-size overrides.

Several visuals carried their own font sizes (titles at 18 pt, plus one-off
12/13/16/21/30 pt values), so the report mixed sizes and ignored the theme's
type scale. This script removes those overrides from every visual.json so all
visuals use the sizes defined by the active theme (BTYT Oscuro).

Kept on purpose: overrides scoped to a specific field (a "selector"), such as
the percentage drawn in the centre of a donut, which is sized for its slot.

Nothing else changes: positions, fields, colors and other formatting stay.

It can also refresh the theme embedded in the report with the generated one.

Usage (Power BI Desktop must be closed):

    python scripts/dashboard/normalize_visual_fonts.py              # dry run
    python scripts/dashboard/normalize_visual_fonts.py --apply      # write
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "powerbi" / "BTYT_Banking_Analytics.Report"
PAGES = REPORT / "definition" / "pages"
THEME_SOURCE = REPO_ROOT / "powerbi" / "themes" / "BTYT_Oscuro.json"
SIZE_PROP = re.compile(r"(?i)^(fontSize|textSize)$")


def strip_sizes(container: dict, log: list, where: str) -> bool:
    """Remove size properties from the cards of an objects/visualContainerObjects dict."""
    changed = False
    for card in list(container):
        entries = container[card]
        kept_entries = []
        card_changed = False
        for entry in entries:
            props = entry.get("properties", {})
            sizes = [p for p in props if SIZE_PROP.match(p)]
            if entry.get("selector") or not sizes:
                kept_entries.append(entry)   # untouched, including entries that were already empty
                continue
            for name in sizes:
                value = json.dumps(props[name])
                log.append(f"{where}: {card}.{name} = {re.search(r'[0-9.]+', value).group(0)}")
                del props[name]
            changed = card_changed = True
            if props or set(entry) - {"properties"}:
                kept_entries.append(entry)
        if kept_entries:
            container[card] = kept_entries
        elif card_changed:
            del container[card]
    return changed


SIZE_BLOCK = r'"(?:fontSize|textSize)":\s*\{\s*"expr":\s*\{\s*"Literal":\s*\{\s*"Value":\s*"[^"]*"\s*\}\s*\}\s*\}'


def remove_size_text(raw: str) -> str:
    """Remove size properties from the raw text, keeping Power BI's own formatting."""
    out = re.sub(r",\s*" + SIZE_BLOCK, "", raw)              # property preceded by another one
    out = re.sub(SIZE_BLOCK + r"\s*,", "", out)               # first property followed by others
    out = re.sub(r"(\{)\s*" + SIZE_BLOCK + r"\s*(\})", r"\1\2", out)  # only property
    return out


def expected(doc: dict) -> dict:
    """Original document minus size properties outside selector-scoped entries."""
    visual = doc.get("visual", {})
    for key in ("objects", "visualContainerObjects"):
        for entries in visual.get(key, {}).values():
            for entry in entries:
                if entry.get("selector"):
                    continue
                for name in [p for p in entry.get("properties", {}) if SIZE_PROP.match(p)]:
                    del entry["properties"][name]
    return doc


def main() -> None:
    apply = "--apply" in sys.argv
    pages = {p.parent.name: json.loads(p.read_text(encoding="utf-8")).get("displayName", p.parent.name)
             for p in PAGES.glob("*/page.json")}
    log, files = [], []
    for f in sorted(PAGES.rglob("visual.json")):
        raw = f.read_bytes().decode("utf-8")
        doc = json.loads(raw)
        visual = doc.get("visual", {})
        where = f"{pages[f.parent.parent.parent.name]} / {visual.get('visualType')}"
        probe = json.loads(raw)
        changed = False
        for key in ("objects", "visualContainerObjects"):
            if key in probe.get("visual", {}):
                changed |= strip_sizes(probe["visual"][key], log, where)
        if not changed:
            continue
        has_scoped = any(e.get("selector") and any(SIZE_PROP.match(p) for p in e.get("properties", {}))
                         for k in ("objects", "visualContainerObjects")
                         for es in visual.get(k, {}).values() for e in es)
        if has_scoped:
            raise SystemExit(f"{f}: mixes scoped and unscoped sizes; edit by hand.")
        new_raw = remove_size_text(raw)
        if json.loads(new_raw) != expected(json.loads(raw)):
            raise SystemExit(f"{f}: text edit does not match the expected document; nothing written.")
        files.append((f, new_raw))

    print(f"visual files changed: {len(files)} | size overrides removed: {len(log)}")
    for line in log:
        print("  -", line)

    embedded = None
    report_json = json.loads((REPORT / "definition" / "report.json").read_text(encoding="utf-8"))
    custom = report_json.get("themeCollection", {}).get("customTheme", {})
    if custom.get("type") == "RegisteredResources":
        embedded = REPORT / "StaticResources" / "RegisteredResources" / custom["name"]
        print(f"embedded theme: {embedded.name} -> will be refreshed from {THEME_SOURCE.name}")

    if not apply:
        print("Dry run. Nothing written (use --apply).")
        return

    backup = Path(tempfile.mkdtemp(prefix="btyt_visual_fonts_"))
    for f, text in files:
        target = backup / f.relative_to(REPORT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        f.write_bytes(text.encode("utf-8"))
    if embedded and embedded.exists():
        shutil.copy2(embedded, backup / embedded.name)
        embedded.write_text(THEME_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Written. Backup: {backup}")


if __name__ == "__main__":
    main()
