"""owl-admin step 01: WBP_OwlAlerts -- the HUD board's server alert banner + notice cards
as a display-only UMG overlay (no input; HitTestInvisible so it never eats the mouse).

Tree (board px x1.5, see oa_config.BOARD_SCALE):
    CanvasPanel OwlAlertsRoot
      AlertOutline (Border #b3121a)  top-centre, y=36
        AlertStack (VBox): AlertAccent (6px #e5242b strip) / AlertFill (Border)
          AlertRow (HBox): AlertLabel "SERVER ALERT" | AlertText
      NoticesBox (SizeBox w=510)  top-left, (36, 90)
        Notices (VBox): one card per NOTICES entry
          NoticeNOutline (Border #4a1a1d) > NoticeNRow (HBox):
            NoticeNAccent (4.5px strip) | NoticeNFill (Border) > NoticeNStack (VBox):
              NoticeNLabel / NoticeNText

Every TextBlock is a variable, so later steps can set the copy at runtime.

Run with Play STOPPED:  python ue_run.py mods/owl-admin/01_alerts_widget.py
Falls back to /Game/_Scratch/OwlAdmin (DRY RUN) when /Game/Mods/OwlAdmin isn't mounted.
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
import re as _re
from bpkit import bridge as bp, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
sys.modules.pop("oa_config", None)
import oa_config as MOD

S = MOD.BOARD_SCALE
eal = unreal.EditorAssetLibrary

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"
for f in (MOD.FONT_BOLD, MOD.FONT_REGULAR):
    assert isinstance(eal.load_asset(f), unreal.Font), "font missing on this build: " + f

# mod root if mounted+writable, else scratch dry-run
if eal.does_directory_exist(MOD.OUTPUT_PKG):
    PKG = MOD.OUTPUT_PKG
else:
    PKG = MOD.SCRATCH_PKG
    print("#" * 68)
    print("##  DRY RUN: %s not mounted (OwlAdmin mod not active)" % MOD.OUTPUT_PKG)
    print("##  building into %s -- NOT shippable from there" % PKG)
    print("#" * 68)
PATH = "%s/%s" % (PKG, MOD.ALERTS_WBP)
FULL = MOD.full(PKG, MOD.ALERTS_WBP)

# ---------------------------------------------------------------- board copy + colours
ALERT_LABEL = "Server alert"
ALERT_TEXT = "Server will restart in 10 minutes."
NOTICES = [   # (label, body, accent strip, label colour) -- placeholders straight off the board
    ("Server notice", "[Server message appears here]", "#e5242b", "#f0343a"),
    ("Restriction", "[Active restriction, e.g. building limit]", "#4a1a1d", "#b8a29c"),
]


def lin(hex_, a=1.0):
    """CSS sRGB hex -> UE FLinearColor text (UMG colours are linear)."""
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return "(R=%.6f,G=%.6f,B=%.6f,A=%.6f)" % (c(r), c(g), c(b), a)


def margin(l=0, t=0, r=0, b=0):
    return "(Left=%.6f,Top=%.6f,Right=%.6f,Bottom=%.6f)" % (l * S, t * S, r * S, b * S)


# ---------------------------------------------------------------- designer clipboard text
CLS = {}       # widget name -> class path, for Content= references
BLOCKS = []


def widget(cls, name, props=(), children=()):
    """Emit one widget object. children = [(slot_cls, child_name, [slot props]), ...]."""
    CLS[name] = cls
    out = ['Begin Object Class=%s Name="%s"' % (cls, name)]
    slots = []
    for i, (slot_cls, child, sprops) in enumerate(children):
        sname = "%s_Slot%d" % (name, i)
        slots.append((slot_cls, sname))
        out += ['   Begin Object Class=%s Name="%s"' % (slot_cls, sname), "   End Object"]
    for (slot_cls, sname), (_, child, sprops) in zip(slots, children):
        out.append('   Begin Object Name="%s"' % sname)
        out += ["      " + p for p in sprops]
        out.append("""      Parent="%s'%s'\"""" % (cls, name))
        out.append("""      Content="%s'%s'\"""" % (CLS[child], child))
        out.append("   End Object")
    out += ["   " + p for p in props]
    out += ["""   Slots(%d)="%s'%s'\"""" % (i, sc, sn) for i, (sc, sn) in enumerate(slots)]
    out += ["   bIsVariable=True" if cls.endswith("TextBlock") else "   bIsVariable=False",
            '   DisplayLabel="%s"' % name, "End Object"]
    BLOCKS.append("\n".join(out))
    return name


def text(name, s, font, px, hex_, spacing_px=0, wrap=False):
    em = int(round(1000.0 * spacing_px / px)) if spacing_px else 0
    return widget("/Script/UMG.TextBlock", name, [
        'Text=INVTEXT("%s")' % s,
        """Font=(FontObject="/Script/Engine.Font'%s'",Size=%.6f,LetterSpacing=%d)""" % (font, px * S * 0.75, em),
        "ColorAndOpacity=(SpecifiedColor=%s)" % lin(hex_),
    ] + (["AutoWrapText=True"] if wrap else []))


def border(name, hex_, a, pad, child, halign="HAlign_Fill", valign="VAlign_Fill"):
    return widget("/Script/UMG.Border", name, [
        "HorizontalAlignment=%s" % halign, "VerticalAlignment=%s" % valign,
        "Padding=%s" % pad, "BrushColor=%s" % lin(hex_, a),
    ], [("/Script/UMG.BorderSlot", child,
         ["Padding=%s" % pad, "HorizontalAlignment=%s" % halign, "VerticalAlignment=%s" % valign])])


def strip(name, hex_, pad):
    """A solid bar: a childless Border whose padding is its size."""
    return widget("/Script/UMG.Border", name, ["Padding=%s" % pad, "BrushColor=%s" % lin(hex_)])


def box(cls, name, items):
    """VerticalBox/HorizontalBox; items = [(child, [slot props])]."""
    return widget("/Script/UMG.%s" % cls, name, [],
                  [("/Script/UMG.%sSlot" % cls, c, p) for c, p in items])


# children are emitted before parents so every Content= reference already has a class
B, R = MOD.FONT_BOLD, MOD.FONT_REGULAR

# -- server alert banner (board: top 24, centred; 1px #b3121a frame, 4px #e5242b top)
text("AlertLabel", ALERT_LABEL.upper(), B, 15, "#f0343a", spacing_px=2)
text("AlertText", ALERT_TEXT, B, 22, "#ffffff")
box("HorizontalBox", "AlertRow", [
    ("AlertLabel", ["Padding=%s" % margin(r=14), "VerticalAlignment=VAlign_Center"]),
    ("AlertText", ["VerticalAlignment=VAlign_Center"]),
])
border("AlertFill", "#1a0809", 0.95, margin(24, 12, 24, 12), "AlertRow")
strip("AlertAccent", "#e5242b", margin(t=4))
box("VerticalBox", "AlertStack", [("AlertAccent", ["HorizontalAlignment=HAlign_Fill"]),
                                  ("AlertFill", ["HorizontalAlignment=HAlign_Fill"])])
border("AlertOutline", "#b3121a", 1.0, margin(1, 0, 1, 1), "AlertStack")

# -- notice cards (board: left 24, top 60, w 340, 8px apart; 1px #4a1a1d frame, 3px left accent)
cards = []
for i, (label, body, accent, label_hex) in enumerate(NOTICES, 1):
    n = "Notice%d" % i
    text(n + "Label", label.upper(), B, 15, label_hex, spacing_px=2)
    text(n + "Text", body, R, 17, "#f2e6e2", wrap=True)
    box("VerticalBox", n + "Stack", [(n + "Label", []), (n + "Text", [])])
    border(n + "Fill", "#0a0505", 0.85, margin(14, 10, 14, 10), n + "Stack")
    strip(n + "Accent", accent, margin(l=3))
    box("HorizontalBox", n + "Row", [
        (n + "Accent", ["VerticalAlignment=VAlign_Fill"]),
        (n + "Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"]),
    ])
    border(n + "Outline", "#4a1a1d", 1.0, margin(1, 1, 1, 1), n + "Row")
    cards.append((n + "Outline", ["Padding=%s" % margin(b=8), "HorizontalAlignment=HAlign_Fill"]))
box("VerticalBox", "Notices", cards)
widget("/Script/UMG.SizeBox", "NoticesBox", ["WidthOverride=%.6f" % (340 * S), "bOverride_WidthOverride=True"],
       [("/Script/UMG.SizeBoxSlot", "Notices", ["HorizontalAlignment=HAlign_Fill", "VerticalAlignment=VAlign_Top"])])

# -- root canvas
widget("/Script/UMG.CanvasPanel", "OwlAlertsRoot", ["Visibility=HitTestInvisible"], [
    ("/Script/UMG.CanvasPanelSlot", "AlertOutline", [
        "LayoutData=(Offsets=(Left=0.000000,Top=%.6f,Right=0.000000,Bottom=0.000000),"
        "Anchors=(Minimum=(X=0.500000,Y=0.000000),Maximum=(X=0.500000,Y=0.000000)),"
        "Alignment=(X=0.500000,Y=0.000000))" % (24 * S),
        "bAutoSize=True", "ZOrder=1"]),
    ("/Script/UMG.CanvasPanelSlot", "NoticesBox", [
        "LayoutData=(Offsets=(Left=%.6f,Top=%.6f,Right=0.000000,Bottom=0.000000),"
        "Anchors=(Minimum=(X=0.000000,Y=0.000000),Maximum=(X=0.000000,Y=0.000000)))" % (24 * S, 60 * S),
        "bAutoSize=True"]),
])
TEXT = "\n".join(reversed(BLOCKS))      # root first, as the designer exports it
EXPECTED = len(CLS)

# ---------------------------------------------------------------- (re)create the asset
if eal.does_asset_exist(PATH):
    assert eal.delete_asset(PATH), "could not delete the previous " + PATH
factory = unreal.WidgetBlueprintFactory()
factory.set_editor_property("parent_class", unreal.UserWidget)
wbp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    MOD.ALERTS_WBP, PKG, unreal.WidgetBlueprint, factory)
assert wbp, "create_asset failed for " + PATH
wbp_ptr = bp.find_object(FULL)
before = bp.tree_widgets(wbp_ptr)
assert not before, "fresh WBP already has %d widgets; expected an empty tree" % len(before)

# ---------------------------------------------------------------- paste + root + compile
pasted = bp.import_widgets(wbp_ptr, TEXT)
print("pasted %d/%d widgets" % (pasted, EXPECTED))
assert pasted == EXPECTED, "paste dropped widgets"
root = bp.find_object("OwlAlertsRoot", outer=bp.widget_tree(wbp_ptr))
assert root, "root canvas not found after paste"
assert bp.set_root_widget(wbp_ptr, root), "RootWidget write did not read back"
bp.mark_structurally_modified(wbp_ptr)
unreal.BlueprintEditorLibrary.compile_blueprint(wbp)

# ---------------------------------------------------------------- verify
ws = bp.tree_widgets(wbp_ptr)
names = {_re.match(r'Begin Object Class=\S+ Name="([^"]+)"', bp.export_widgets([w])).group(1) for w in ws}
txt = bp.export_widgets(ws)
held = set(_re.findall(r"""Content="[^']*'([^']+)'""", txt))
missing = sorted(set(CLS) - names)
loose = sorted(names - held - {"OwlAlertsRoot"})          # parentless widgets other than the root
gen = unreal.load_object(None, FULL + "_C")
print("widgets in tree: %d | missing: %s | unparented: %s | generated class: %s"
      % (len(ws), missing or "(none)", loose or "(none)", gen.get_name() if gen else None))
assert not missing and not loose and gen, "widget tree not clean"
assert bp.root_widget(wbp_ptr) == root, "root changed during compile"
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
