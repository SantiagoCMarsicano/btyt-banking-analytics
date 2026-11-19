"""Build the BTYT Power BI report themes: 'BTYT Oscuro' and 'BTYT Corporativo'.

'BTYT Oscuro' starts from the report's former built-in dark theme (so every
visual type it styles keeps a valid structure) and replaces its palette,
neutrals, typography, borders and semantic colors:

- one accent color for BTYT series, muted neutrals for context;
- green / red reserved for good / bad changes;
- Segoe UI throughout, Segoe UI Semibold for titles and headline numbers;
- panels with a thin border and 8 px corners on a slightly darker canvas;
- frameless slicers and navigation buttons.

'BTYT Corporativo' is the light variant for printed or projected reports.

Usage (from the repository root):

    python scripts/dashboard/build_powerbi_theme.py

Writes powerbi/themes/BTYT_Oscuro.json and powerbi/themes/BTYT_Corporativo.json.
"""
import copy
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "powerbi" / "themes" / "BTYT_Oscuro.json"
# Structure source: the built-in dark theme the report used before the custom
# theme was applied. Once Power BI replaces it, the previously generated dark
# theme is used instead (re-applying the tokens below to it is idempotent).
SOURCE_CANDIDATES = [
    REPO_ROOT / "powerbi" / "BTYT_Banking_Analytics.Report" / "StaticResources"
    / "SharedResources" / "BuiltInThemes" / "ReportThemeDark.json",
    OUTPUT,
    REPO_ROOT / "powerbi" / "themes" / "BTYT_Pulso.json",   # former name
]
SOURCE = next((p for p in SOURCE_CANDIDATES if p.exists()), SOURCE_CANDIDATES[-1])

# Design tokens ---------------------------------------------------------------
CANVAS = "#0F1216"        # page background / outspace
PANEL = "#171B21"         # visual background
PANEL_RAISED = "#1E232A"  # hover, headers
BORDER = "#2A3039"        # visual borders, gridlines base
GRID = "#232830"          # chart gridlines
FG = "#E8EAED"            # primary text
FG_2 = "#A3ACB8"          # secondary text, axis labels
FG_3 = "#6E7783"          # tertiary text
ACCENT = "#5B9CF5"        # BTYT series
ACCENT_SOFT = "#7DB3F7"   # links, selection
GOOD = "#3FB950"
BAD = "#F85149"
WARN = "#D29922"
MUTED = "#6E7681"         # context series (e.g. normal credit loss bars)

# Accent first, then restrained supporting hues for categorical breakdowns.
DATA_COLORS = [
    ACCENT, "#9AA6B8", "#E0B062", "#6CC4A4", "#C28BD8", "#F0896E",
    "#7FA3D9", "#B7C25A", "#5FB3C8", "#D98BB0", "#8C96A3", "#C9A27E",
]

# Hard-coded colors in the source dark theme mapped to the new tokens.
HEX_MAP = {
    "#F5F5F5": FG,
    "#1F1F1F": PANEL,
    "#414141": BORDER,
    "#111111": CANVAS,
    "#75B7FF": ACCENT_SOFT,
    "#FFFFFF": "#F5F7FA",
    "#4DA6FF": ACCENT,
    "#292929": PANEL_RAISED,
    "#4A4A4A": "#2E343E",
    "#767676": FG_3,
    "#1A1A1A": CANVAS,
    "#45D5F5": "#8FB8E8",
}

SANS = "Segoe UI"
SANS_SEMIBOLD = "Segoe UI Semibold"
NUMBERS = SANS_SEMIBOLD   # headline numbers: the standard Office / Power BI face

# Type scale (pt) for 1920 x 1080 report pages shown fit-to-page on a laptop or
# projector. Visual titles keep the 18 pt the report already used, and every
# other size is derived from it so all pages read the same.
TYPE = {
    "kpi": 24,       # headline numbers in cards (fits the ~150-220 px KPI cards)
    "title": 18,     # visual titles
    "body": 14,      # tables
    "axis": 13,      # axis labels, legends, data labels, subtitles
    "control": 12,   # slicers, navigation buttons, card captions (50-70 px tall)
    "inside": 18,    # labels drawn inside large shapes (treemap tiles)
}
PADDING = 12


def remap(node):
    if isinstance(node, dict):
        return {k: remap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [remap(v) for v in node]
    if isinstance(node, str) and node.upper() in HEX_MAP:
        return HEX_MAP[node.upper()]
    return node


def solid(color):
    return {"solid": {"color": color}}


def merge(target, patch):
    """Merge theme cards: dicts recurse, the first object of a card list is updated."""
    for key, value in patch.items():
        if isinstance(value, dict):
            merge(target.setdefault(key, {}), value)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            current = target.setdefault(key, [{}])
            if not current:
                current.append({})
            current[0].update(value[0])
        else:
            target[key] = value


def build() -> dict:
    theme = remap(copy.deepcopy(json.loads(SOURCE.read_text(encoding="utf-8"))))
    theme["name"] = "BTYT Oscuro"
    theme.update({
        "dataColors": DATA_COLORS,
        "tableAccent": ACCENT,
        "good": GOOD,
        "neutral": WARN,
        "bad": BAD,
        "maximum": ACCENT,
        "center": "#2E343E",
        "minimum": PANEL_RAISED,
        "null": FG_3,
        "hyperlink": ACCENT_SOFT,
        "visitedHyperlink": "#B39DDB",
        "foreground": FG,
        "foregroundNeutralSecondary": FG_2,
        "foregroundNeutralTertiary": FG_3,
        "foregroundNeutralLight": "#4A525D",
        "background": PANEL,
        "backgroundLight": PANEL_RAISED,
        "backgroundNeutral": "#2E343E",
        "backgroundDark": CANVAS,
        "accent": ACCENT,
        "shapeStroke": BORDER,
        "disabledText": FG_3,
        "textClasses": {
            "callout": {"fontSize": TYPE["kpi"], "fontFace": NUMBERS, "color": FG},
            "title": {"fontSize": TYPE["title"], "fontFace": SANS_SEMIBOLD, "color": FG},
            "header": {"fontSize": TYPE["body"], "fontFace": SANS_SEMIBOLD, "color": FG},
            "label": {"fontSize": TYPE["axis"], "fontFace": SANS, "color": FG_2},
        },
    })

    styles = theme.setdefault("visualStyles", {})
    body = {"fontSize": TYPE["body"], "fontFamily": SANS}
    control = {"fontSize": TYPE["control"], "fontFamily": SANS}
    merge(styles, {
        "*": {"*": {
            "background": [{"show": True, "color": solid(PANEL), "transparency": 0}],
            "border": [{"show": True, "color": solid(BORDER), "radius": 8, "width": 1}],
            "dropShadow": [{"show": False}],
            "padding": [{"top": PADDING, "bottom": PADDING, "left": PADDING, "right": PADDING}],
            "title": [{"show": True, "fontColor": solid(FG), "fontSize": TYPE["title"], "bold": False,
                       "fontFamily": SANS_SEMIBOLD, "alignment": "left"}],
            "subTitle": [{"fontColor": solid(FG_2), "fontSize": TYPE["axis"], "fontFamily": SANS}],
            "categoryAxis": [{"gridlineColor": solid(GRID), "labelColor": solid(FG_2),
                              "fontSize": TYPE["axis"], "titleFontSize": TYPE["axis"], "fontFamily": SANS}],
            "valueAxis": [{"gridlineColor": solid(GRID), "labelColor": solid(FG_2),
                           "fontSize": TYPE["axis"], "titleFontSize": TYPE["axis"], "fontFamily": SANS}],
            "legend": [{"labelColor": solid(FG_2), "fontSize": TYPE["axis"], "fontFamily": SANS}],
            "labels": [{"color": solid(FG), "fontSize": TYPE["axis"], "fontFamily": SANS}],
            "lineStyles": [{"strokeWidth": 2.5}],
        }},
        # Headline numbers: classic card and new card share the same size and face.
        "card": {"*": {
            "labels": [{"fontSize": TYPE["kpi"], "fontFamily": NUMBERS}],
            "categoryLabels": [dict(control)],
        }},
        "cardVisual": {"*": {
            "value": [{"fontSize": TYPE["kpi"], "fontFamily": NUMBERS}],
            "label": [dict(control)],
            "referenceLabelTitle": [{"titleFontSize": TYPE["control"]}],
            "referenceLabelValue": [{"valueFontSize": TYPE["control"]}],
            "referenceLabelDetail": [{"detailFontSize": TYPE["control"]}],
        }},
        # Filters and navigation: compact text so 50-70 px tall controls fit.
        "slicer": {"*": {
            "title": [dict(control)],
            "header": [{"textSize": TYPE["control"], "fontFamily": SANS}],
            "items": [{"textSize": TYPE["control"], "fontFamily": SANS}],
        }},
        "advancedSlicerVisual": {"*": {
            "title": [dict(control)],
            "value": [{"fontSize": 11, "fontFamily": SANS}],   # 33 px tall toggle buttons
        }},
        "bookmarkNavigator": {"*": {"text": [dict(control)]}},
        # Tables.
        "tableEx": {"*": {
            "values": [dict(body)], "columnHeaders": [dict(body)], "total": [dict(body)],
        }},
        "pivotTable": {"*": {
            "values": [dict(body)], "columnHeaders": [dict(body)], "rowHeaders": [dict(body)],
            "columnTotal": [dict(body)], "rowTotal": [dict(body)],
        }},
        # Labels drawn inside large shapes.
        "treemap": {"*": {
            "labels": [{"fontSize": TYPE["inside"], "fontFamily": SANS}],
            "categoryLabels": [{"fontSize": TYPE["body"], "fontFamily": SANS}],
        }},
        "page": {"*": {
            "background": [{"color": solid(CANVAS), "transparency": 0}],
            "outspace": [{"color": solid(CANVAS)}],
        }},
        "waterfallChart": {"*": {
            "sentimentColors": [{
                "increaseFill": solid(GOOD),
                "decreaseFill": solid(BAD),
                "totalFill": solid(ACCENT),
                "otherFill": solid(MUTED),
            }],
        }},
        "textbox": {"*": {
            "background": [{"show": False}],
            "border": [{"show": False}],
        }},
    })
    merge(styles, control_styles())
    # Drop container-style padding entries a previous build left on visuals whose
    # 'padding' card only takes content margins (keep their own '$id' entries).
    for v in ("advancedSlicerVisual", "cardVisual"):
        star = styles.get(v, {}).get("*", {})
        if "padding" in star:
            kept = [e for e in star["padding"] if not {"top", "bottom", "left", "right"} & set(e)]
            if kept:
                star["padding"] = kept
            else:
                del star["padding"]
    return theme


def control_styles() -> dict:
    """Frameless filters and navigation, compact cards, no automatic subtitles.

    The panel look ('*': background, border, title, padding) suits charts. Slicers,
    bookmark buttons and the small hidden helper slicers are controls: framing them
    as panels draws boxes around them and squeezes their content, and an automatic
    container title duplicates the slicer's own header.
    """
    frameless = {
        "background": [{"show": False}],
        "border": [{"show": False}],
        "dropShadow": [{"show": False}],
        "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}],
        "subTitle": [{"show": False}],
    }
    compact = {"top": 8, "bottom": 8, "left": 10, "right": 10}
    return {
        "*": {"*": {"subTitle": [{"show": False}]}},   # visuals that want one set it explicitly
        "slicer": {"*": {**frameless, "title": [{"show": False}]}},
        # advancedSlicerVisual and cardVisual use 'padding' for their content margins
        # (topMargin, ...), not the container, so their own defaults are kept.
        "advancedSlicerVisual": {"*": {k: v for k, v in frameless.items() if k != "padding"}},
        "bookmarkNavigator": {"*": {**frameless, "title": [{"show": False}]}},
        "card": {"*": {"title": [{"show": False}], "subTitle": [{"show": False}], "padding": [dict(compact)]}},
        "cardVisual": {"*": {"title": [{"show": False}], "subTitle": [{"show": False}]}},
    }


# -----------------------------------------------------------------------------
# BTYT Corporativo: light theme for professional reports and presentations
# -----------------------------------------------------------------------------
#
# A custom theme is layered on top of the report's base theme (Fluent 2, light),
# so this one only sets what differs: palette, typography, panels and the
# semantic colors. Everything it does not mention keeps the light Fluent 2 look.

CORP_OUTPUT = REPO_ROOT / "powerbi" / "themes" / "BTYT_Corporativo.json"

C_CANVAS = "#F3F5F8"      # page background
C_PANEL = "#FFFFFF"       # visual background
C_BORDER = "#DDE2E8"      # visual borders
C_GRID = "#EDF0F4"        # chart gridlines
C_FG = "#1B2533"          # primary text
C_FG_2 = "#5A6675"        # secondary text, axis labels
C_FG_3 = "#8A95A3"        # tertiary text, neutral state
C_NAVY = "#1F4E79"        # BTYT / primary series
C_GOOD = "#2E7D32"
C_BAD = "#C0392B"
C_GOLD = "#C8963E"        # highlight / warning
C_CONTEXT = "#A9B8C9"     # context series

C_DATA_COLORS = [
    C_NAVY, "#5B8DB8", C_CONTEXT, C_GOLD, "#2E8B7A", "#7A5C99",
    "#D1665A", "#6B7C8F", "#9DB4A0", "#B5838D", "#3E6E9E", "#C4B27D",
]


def build_corporate() -> dict:
    theme = {
        "name": "BTYT Corporativo",
        "dataColors": C_DATA_COLORS,
        "tableAccent": C_NAVY,
        "good": C_GOOD,
        "neutral": C_GOLD,
        "bad": C_BAD,
        "maximum": C_NAVY,
        "center": "#C9D6E3",
        "minimum": "#F1F5F9",
        "null": C_FG_3,
        "hyperlink": C_NAVY,
        "visitedHyperlink": "#5E4B8B",
        "foreground": C_FG,
        "foregroundNeutralSecondary": C_FG_2,
        "foregroundNeutralTertiary": C_FG_3,
        "foregroundNeutralLight": "#C2CAD3",
        "background": C_PANEL,
        "backgroundLight": "#F7F9FB",
        "backgroundNeutral": "#E6EAF0",
        "backgroundDark": C_CANVAS,
        "accent": C_NAVY,
        "shapeStroke": C_BORDER,
        "disabledText": C_FG_3,
        "textClasses": {
            "callout": {"fontSize": 24, "fontFace": SANS_SEMIBOLD, "color": C_FG},
            "title": {"fontSize": 12, "fontFace": SANS_SEMIBOLD, "color": C_FG},
            "header": {"fontSize": 11, "fontFace": SANS_SEMIBOLD, "color": C_FG},
            "label": {"fontSize": 10, "fontFace": SANS, "color": C_FG_2},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": solid(C_PANEL), "transparency": 0}],
                "border": [{"show": True, "color": solid(C_BORDER), "radius": 4, "width": 1}],
                "dropShadow": [{"show": False}],
                "padding": [{"top": 12, "bottom": 12, "left": 14, "right": 14}],
                "title": [{"show": True, "fontColor": solid(C_FG), "fontSize": 12, "bold": False,
                           "fontFamily": SANS_SEMIBOLD, "alignment": "left"}],
                "subTitle": [{"fontColor": solid(C_FG_2), "fontSize": 10, "fontFamily": SANS}],
                "categoryAxis": [{"gridlineColor": solid(C_GRID), "labelColor": solid(C_FG_2),
                                  "fontSize": 9, "fontFamily": SANS}],
                "valueAxis": [{"gridlineColor": solid(C_GRID), "labelColor": solid(C_FG_2),
                               "fontSize": 9, "fontFamily": SANS}],
                "legend": [{"labelColor": solid(C_FG_2), "fontSize": 9, "fontFamily": SANS}],
                "labels": [{"color": solid(C_FG), "fontSize": 9, "fontFamily": SANS}],
                "lineStyles": [{"strokeWidth": 2}],
            }},
            "page": {"*": {
                "background": [{"color": solid(C_CANVAS), "transparency": 0}],
                "outspace": [{"color": solid(C_CANVAS)}],
            }},
            "waterfallChart": {"*": {
                "sentimentColors": [{
                    "increaseFill": solid(C_GOOD),
                    "decreaseFill": solid(C_BAD),
                    "totalFill": solid(C_NAVY),
                    "otherFill": solid(C_CONTEXT),
                }],
            }},
            "textbox": {"*": {
                "background": [{"show": False}],
                "border": [{"show": False}],
            }},
        },
    }
    merge(theme["visualStyles"], control_styles())
    return theme


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for path, theme in ((OUTPUT, build()), (CORP_OUTPUT, build_corporate())):
        path.write_text(json.dumps(theme, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {path.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
