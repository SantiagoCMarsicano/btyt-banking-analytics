"""Create the 'Resumen ejecutivo' page in the Power BI project (PBIR format).

The page is the executive opener for a start-of-year meeting: an automatic
headline, six KPI tiles (value, change vs previous year, six-year trend), the
net-income bridge, the monthly credit-loss shock and BTYT's market share.

All visuals use measures from the 'Resumen Ejecutivo' display folder and the
'Bridge Steps' table. Visual JSON follows the structure Power BI Desktop
writes for the same visual types elsewhere in this report and declares the
published visualContainer 2.13.0 schema so it can be validated offline.

Usage (Power BI Desktop must be closed):

    python scripts/dashboard/build_executive_summary_page.py            # dry run
    python scripts/dashboard/build_executive_summary_page.py --apply    # write
"""
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGES = REPO_ROOT / "powerbi" / "BTYT_Banking_Analytics.Report" / "definition" / "pages"
PAGE_ID = "b7a1e0c4d2f9e8a3c5d1"
PAGE_NAME = "Resumen ejecutivo"
VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

ACCENT = "#5B9CF5"
WARN = "#D29922"
GOOD = "#3FB950"
BAD = "#F85149"
PANEL = "#171B21"   # visual background in the BTYT Oscuro theme
FG_2 = "#A3ACB8"


# --------------------------------------------------------------------------- helpers
def vid(key: str) -> str:
    return hashlib.sha1(f"{PAGE_ID}:{key}".encode()).hexdigest()[:20]


def lit(value):
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = f"{value}L"
    elif isinstance(value, float):
        text = f"{value:g}D"
    else:
        text = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def color(hex_value):
    return {"solid": {"color": lit(hex_value)}}


def measure(name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": name}}


def column(table, name):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def proj(field, display=None):
    kind = "Measure" if "Measure" in field else "Column"
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": display or prop}
    if display:
        p["displayName"] = display
    return p


def props(**kw):
    return [{"properties": {k: (v if isinstance(v, dict) and ("expr" in v or "solid" in v) else lit(v))
                            for k, v in kw.items()}}]


def container(title=None, subtitle=None, background=True, border=True, title_size=None):
    out = {
        "background": props(show=background),
        "border": props(show=border),
        "dropShadow": props(show=False),
    }
    if title:
        t = {"show": True, "text": title}
        if title_size:
            t["fontSize"] = float(title_size)
        out["title"] = props(**t)
    else:
        out["title"] = props(show=False)
    # Always explicit: otherwise Power BI fills in an automatic English subtitle.
    out["subTitle"] = props(show=True, text=subtitle) if subtitle else props(show=False)
    return out


MILLIONS = {"labelDisplayUnits": 1000000.0, "labelPrecision": 1}


def visual(key, vtype, x, y, w, h, z, query_state, objects=None, vco=None, sort=None, filters=None):
    v = {
        "$schema": VISUAL_SCHEMA,
        "name": vid(key),
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": {
            "visualType": vtype,
            "query": {"queryState": {role: {"projections": ps} for role, ps in query_state.items()}},
            "objects": objects or {},
            "visualContainerObjects": vco or {},
            "drillFilterOtherVisuals": True,
        },
    }
    if sort:
        v["visual"]["query"]["sortDefinition"] = {"sort": sort, "isDefaultSort": False}
    if filters:
        v["filterConfig"] = {"filters": filters}
    return v


def year_from(table, column_name, year, kind=2):
    alias = table[0].lower()
    return {
        "name": vid(f"filter:{table}:{column_name}"),
        "field": column(table, column_name),
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"Comparison": {
                "ComparisonKind": kind,
                "Left": {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": column_name}},
                "Right": {"Literal": {"Value": f"{year}L"}},
            }}}],
        },
    }


# --------------------------------------------------------------------------- page layout (1920 x 1080)
M, G = 48, 24
visuals = []
z = 0


def add(v):
    global z
    visuals.append(v)
    z += 1


# Headline: two automatic sentences (results, then drivers) under the page title.
headline_panel = container(title="BTYT · Resumen ejecutivo", title_size=24, border=False)
headline_panel["title"][0]["properties"]["alignment"] = lit("center")
headline_panel["padding"] = props(top=14.0, bottom=0.0, left=16.0, right=16.0)
add(visual("headline", "card", M, 18, 1516, 113, 0,
           {"Values": [proj(measure("Exec Headline Results"), "Resultado del año")]},
           objects={
               "labels": props(fontSize=18.0, fontFamily="Segoe UI Semibold", color=color("#E8EAED")),
               "categoryLabels": props(show=False),
           },
           vco=headline_panel))
drivers_panel = container(border=False)
drivers_panel["padding"] = props(top=0.0, bottom=10.0, left=16.0, right=16.0)
add(visual("headline2", "card", M, 131, 1516, 36, 2,
           {"Values": [proj(measure("Exec Headline Drivers"), "Causas y mercado")]},
           objects={
               "labels": props(fontSize=16.0, fontFamily="Segoe UI", color=color(FG_2)),
               "categoryLabels": props(show=False),
           },
           vco=drivers_panel))

# Year selector.
year_panel = container(title="Año analizado")
year_panel["title"] = props(show=False)
add(visual("year", "slicer", 1658, 62, 140, 80, 1,
           {"Values": [proj(column("DimDate", "Year"), "Año")]},
           objects={
               "data": props(mode="Dropdown"),
               "selection": props(singleSelect=True),
               "general": [{"properties": {}}],
           },
           vco=year_panel))

# KPI tiles: value, change vs previous year, six-year trend.
TILES = [
    ("Ingresos", "Exec Revenue", "Exec Revenue YoY %", "Exec Color Revenue", "Total Revenue", "DimDate", "Year"),
    ("Resultado neto", "Exec Net Income", "Exec Net Income YoY %", "Exec Color Net Income", "Net Income", "DimDate", "Year"),
    ("Costos / Ingresos", "Exec Cost-to-Income", "Exec Cost-to-Income Change (pp)", "Exec Color Cost-to-Income", "Cost-to-Income", "DimDate", "Year"),
    ("Margen neto", "Exec Net Margin", "Exec Net Margin Change (pp)", "Exec Color Net Margin", "Net Margin", "DimDate", "Year"),
    ("Pérdida de crédito", "Exec Credit Loss", "Exec Credit Loss YoY %", "Exec Color Credit Loss", "Credit Loss", "DimDate", "Year"),
    ("Cuota de mercado", "Exec Market Share", "Exec Market Share Change (pp)", "Exec Color Market Share", "BTYT Market Share by Year", "Market Performance", "year"),
]
TILE_Y, TILE_W, TILE_H = 188, 284, 212
sparkline_ids = []
for i, (label, value_m, delta_m, color_m, trend_m, axis_table, axis_col) in enumerate(TILES):
    x = M + i * (TILE_W + G)
    is_usd = value_m in ("Exec Revenue", "Exec Net Income", "Exec Credit Loss")
    value_tile = container(border=False)
    value_tile["padding"] = props(top=10.0, bottom=0.0, left=12.0, right=12.0)
    value_labels = props(**MILLIONS) if is_usd else None
    add(visual(f"tile{i}:value", "card", x, TILE_Y, TILE_W, 96, 10 + i * 3,
               {"Values": [proj(measure(value_m), label)]},
               objects={"categoryLabels": props(show=True), **({"labels": value_labels} if value_labels else {})},
               vco=value_tile))
    delta_tile = container(border=False)
    delta_tile["padding"] = props(top=0.0, bottom=0.0, left=12.0, right=12.0)
    add(visual(f"tile{i}:delta", "card", x, TILE_Y + 96, TILE_W, 40, 11 + i * 3,
               {"Values": [proj(measure(delta_m), "frente al año anterior")]},
               objects={
                   "labels": [{"properties": {"fontSize": lit(15.0), "fontFamily": lit("Segoe UI Semibold"),
                                              "color": {"solid": {"color": {"expr": measure(color_m)}}}}}],
                   "categoryLabels": props(show=False),
               }, vco=delta_tile))
    trend_tile = container(border=False)
    trend_tile["padding"] = props(top=0.0, bottom=4.0, left=8.0, right=8.0)
    spark = visual(f"tile{i}:trend", "lineChart", x, TILE_Y + 136, TILE_W, 76, 12 + i * 3,
                   {"Category": [proj(column(axis_table, axis_col), "Año")], "Y": [proj(measure(trend_m))]},
                   objects={
                       "categoryAxis": props(show=False),
                       "valueAxis": props(show=False, gridlineShow=False),
                       "legend": props(show=False),
                       "dataPoint": [{"properties": {"fill": color(ACCENT)}, "selector": {"metadata": f"_Measures.{trend_m}"}}],
                   },
                   vco=trend_tile,
                   sort=[{"field": column(axis_table, axis_col), "direction": "Ascending"}])
    sparkline_ids.append(spark["name"])
    add(spark)

# Net-income bridge, drawn as a stacked column chart so every bar has its own
# meaning: start and end years in the accent color, increases green, decreases
# red. (A native waterfall paints the starting year as an "increase".)
# An invisible base series, in the panel color, lifts each change to its level.
ROW2_Y, ROW2_H, HALF = TILE_Y + TILE_H + G, 432, (1920 - 2 * M - G) // 2
BRIDGE_SERIES = [
    ("Bridge Base", "Base", PANEL),
    ("Bridge Total", "Resultado neto", ACCENT),
    ("Bridge Increase", "Aumenta", GOOD),
    ("Bridge Decrease", "Disminuye", BAD),
]
bridge_panel = container(title="Qué movió el resultado neto (US$ M, a tipo de cambio del año anterior)")
# Subtitle lists every change, so the small ones (no room for a bar label) are still readable.
bridge_panel["subTitle"] = [{"properties": {"show": lit(True), "text": {"expr": measure("Bridge Summary")}}}]
add(visual("bridge", "columnChart", M, ROW2_Y, HALF, ROW2_H, 40,
           {"Category": [proj(column("Bridge Steps", "Step"), "Partida")],
            "Y": [proj(measure(m), label) for m, label, _ in BRIDGE_SERIES]},
           objects={
               "dataPoint": [{"properties": {"fill": color(c)}, "selector": {"metadata": f"_Measures.{m}"}}
                             for m, _, c in BRIDGE_SERIES],
               "labels": props(show=True, labelPosition="InsideEnd", labelOverflow=True)
                         + [{"properties": {"showSeries": lit(False)}, "selector": {"metadata": "_Measures.Bridge Base"}}],
               "legend": props(show=False),
               # The axis starts just below the lowest level so the year-on-year
               # changes are visible next to two bars of ~US$ 120-150 M.
               "valueAxis": [{"properties": {"show": lit(False), "gridlineShow": lit(False),
                                             "start": {"expr": measure("Bridge Axis Start")}}}],
               "categoryAxis": props(showAxisTitle=False, innerPadding=24.0),
           },
           vco=bridge_panel,
           sort=[{"field": column("Bridge Steps", "Step"), "direction": "Ascending"}]))

# Monthly net income vs credit loss, last three years.
monthly = visual("monthly", "lineClusteredColumnComboChart", M + HALF + G, ROW2_Y, HALF, ROW2_H, 41,
                 {"Category": [proj(column("DimDate", "Date"))],
                  "Y": [proj(measure("Credit Loss"), "Pérdida de crédito")],
                  "Y2": [proj(measure("Net Income"), "Resultado neto")]},
                 objects={
                     "valueAxis": props(labelDisplayUnits=1000000.0, secLabelDisplayUnits=1000000.0),
                     # Same shapes Power BI writes elsewhere in this report: per-point color
                     # driven by a measure (data wildcard), and a fixed color per series (metadata).
                     "dataPoint": [
                         # Series color (legend) matches the normal bar color.
                         {"properties": {"fill": color("#A9B8C9")}, "selector": {"metadata": "_Measures.Credit Loss"}},
                         {"properties": {"fill": {"solid": {"color": {"expr": measure("Credit Loss Bar Color")}}}},
                          "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}},
                         {"properties": {"fill": color(ACCENT)}, "selector": {"metadata": "_Measures.Net Income"}},
                     ],
                     "legend": props(show=True, position="Top"),
                 },
                 vco=container(title="Resultado neto y pérdida de crédito por mes (US$ M)",
                               subtitle="En rojo, meses con pérdida de crédito mayor al doble de la mediana de los 12 meses previos."),
                 sort=[{"field": column("DimDate", "Date"), "direction": "Ascending"}],
                 filters=[year_from("DimDate", "Year", 2024)])
add(monthly)

# Market share and data note.
ROW3_Y = ROW2_Y + ROW2_H + G
ROW3_H = 1080 - ROW3_Y - 28
share = visual("share", "lineChart", M, ROW3_Y, HALF, ROW3_H, 42,
               {"Category": [proj(column("Market Performance", "year"), "Año")],
                "Y": [proj(measure("BTYT Market Share by Year"), "Cuota de mercado")]},
               objects={"labels": props(show=True), "legend": props(show=False),
                        "dataPoint": [{"properties": {"fill": color(ACCENT)},
                                       "selector": {"metadata": "_Measures.BTYT Market Share by Year"}}]},
               vco=container(title="Cuota de mercado de BTYT"),
               sort=[{"field": column("Market Performance", "year"), "direction": "Ascending"}])
add(share)
add(visual("note", "card", M + HALF + G, ROW3_Y, HALF, ROW3_H, 43,
           {"Values": [proj(measure("Credit Loss Data Note"), "Nota sobre los datos")]},
           objects={
               "labels": props(fontSize=14.0, fontFamily="Segoe UI", color=color(WARN)),
               "categoryLabels": props(show=False),
               "wordWrap": props(show=True),
           },
           vco=container(title="Nota sobre los datos")))

# The year selector drives the KPIs and the bridge, not the trend lines.
year_id = vid("year")
interactions = [{"source": year_id, "target": t, "type": "NoFilter"}
                for t in sparkline_ids + [monthly["name"], share["name"]]]

page = {
    "$schema": PAGE_SCHEMA,
    "name": PAGE_ID,
    "displayName": PAGE_NAME,
    "displayOption": "FitToPage",
    "height": 1080,
    "width": 1920,
    "visualInteractions": interactions,
}


def main() -> None:
    apply = "--apply" in sys.argv
    page_dir = PAGES / PAGE_ID
    print(f"page '{PAGE_NAME}' ({PAGE_ID}): {len(visuals)} visuals, {len(interactions)} interactions")
    for v in visuals:
        p = v["position"]
        print(f"  {v['visual']['visualType']:31s} x={p['x']:4d} y={p['y']:4d} w={p['width']:4d} h={p['height']:4d}")
    out_dir = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None
    if not apply and not out_dir:
        print("Dry run. Nothing written (use --apply).")
        return
    target = page_dir if apply else out_dir / PAGE_ID
    if apply and page_dir.exists():
        if "--replace" not in sys.argv:
            raise SystemExit(f"{page_dir} already exists; use --replace to rebuild it.")
        import shutil, tempfile
        backup = Path(tempfile.mkdtemp(prefix="btyt_exec_page_")) / PAGE_ID
        shutil.move(str(page_dir), str(backup))
        print(f"Previous page moved to {backup}")
    (target / "visuals").mkdir(parents=True, exist_ok=True)
    (target / "page.json").write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
    for v in visuals:
        d = target / "visuals" / v["name"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    if apply:
        meta_path = PAGES / "pages.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if PAGE_ID not in meta["pageOrder"]:
            meta["pageOrder"].insert(0, PAGE_ID)
        meta["activePageName"] = PAGE_ID
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written to {target}")


if __name__ == "__main__":
    main()
