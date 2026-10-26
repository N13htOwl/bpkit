"""owl-admin step 01: WBP_OwlAlerts -- the HUD board's server alert banner + notice cards
as a display-only UMG overlay (no input; HitTestInvisible so it never eats the mouse).

Tree (board px x1.5, see oa_config.BOARD_SCALE):
    CanvasPanel OwlAlertsRoot
      AlertOutline (Border #b3121a)  top-centre, y=36
        AlertStack (VBox): AlertAccent (6px #e5242b strip) / AlertFill (Border)
          AlertRow (HBox): AlertLabel "SERVER ALERT" | AlertText
      NoticesBox (SizeBox w=510)  top-left, NOTICES_POS
        Notices (VBox): one card per NOTICES entry
          NoticeNOutline (Border #4a1a1d) > NoticeNRow (HBox):
            NoticeNAccent (4.5px strip) | NoticeNFill (Border) > NoticeNStack (VBox):
              NoticeNLabel / NoticeNText

Every TextBlock is a variable, so later steps can set the copy at runtime.

Placement vs Conan's own HUD (measured in PIE 2026-10-26, UMG units): the vitals frame +
status icons fill the top-left to y=145, so the notice cards sit below them at NOTICES_POS
instead of the board's (24, 60). The banner keeps the board's top-centre spot: at 16:9 it
spans x 582-1338, clear of the vitals (x<=357) and the tutorial panel (right 67-392).

Run with Play STOPPED:  python ue_run.py mods/owl-admin/01_alerts_widget.py
Falls back to /Game/_Scratch/OwlAdmin (DRY RUN) when /Game/Mods/OwlAdmin isn't mounted.
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "umg_text"):
    sys.modules.pop(_m, None)
import oa_config as MOD
from umg_text import Umg, prepare_wbp, verify_tree

eal = unreal.EditorAssetLibrary

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"
for f in (MOD.FONT_BOLD, MOD.FONT_REGULAR):
    assert isinstance(eal.load_asset(f), unreal.Font), "font missing on this build: " + f

PKG = MOD.resolve_pkg()     # mod root if mounted+writable, else scratch dry-run
PATH = "%s/%s" % (PKG, MOD.ALERTS_WBP)
FULL = MOD.full(PKG, MOD.ALERTS_WBP)

# ---------------------------------------------------------------- board copy + colours
ALERT_LABEL = "Server alert"
ALERT_TEXT = "Server will restart in 10 minutes."
NOTICES_POS = (24, 170)   # UMG units: Conan's HUD left edge, below its vitals + status icons
NOTICES = [   # (label, body, accent strip, label colour) -- placeholders straight off the board
    ("Server notice", "[Server message appears here]", "#e5242b", "#f0343a"),
    ("Restriction", "[Active restriction, e.g. building limit]", "#4a1a1d", "#b8a29c"),
]

u = Umg(MOD.BOARD_SCALE)
S, B, R = MOD.BOARD_SCALE, MOD.FONT_BOLD, MOD.FONT_REGULAR

# -- server alert banner (board: top 24, centred; 1px #b3121a frame, 4px #e5242b top)
u.text("AlertLabel", ALERT_LABEL.upper(), B, 15, "#f0343a", spacing_px=2)
u.text("AlertText", ALERT_TEXT, B, 22, "#ffffff")
u.box("HorizontalBox", "AlertRow", [
    ("AlertLabel", ["Padding=%s" % u.margin(r=14), "VerticalAlignment=VAlign_Center"]),
    ("AlertText", ["VerticalAlignment=VAlign_Center"]),
])
u.border("AlertFill", "#1a0809", 0.95, u.margin(24, 12, 24, 12), "AlertRow")
u.strip("AlertAccent", "#e5242b", u.margin(t=4))
u.box("VerticalBox", "AlertStack", [("AlertAccent", ["HorizontalAlignment=HAlign_Fill"]),
                                    ("AlertFill", ["HorizontalAlignment=HAlign_Fill"])])
u.border("AlertOutline", "#b3121a", 1.0, u.margin(1, 0, 1, 1), "AlertStack")

# -- notice cards (board: w 340, 8px apart; 1px #4a1a1d frame, 3px left accent)
cards = []
for i, (label, body, accent, label_hex) in enumerate(NOTICES, 1):
    n = "Notice%d" % i
    u.text(n + "Label", label.upper(), B, 15, label_hex, spacing_px=2)
    u.text(n + "Text", body, R, 17, "#f2e6e2", wrap=True)
    u.box("VerticalBox", n + "Stack", [(n + "Label", []), (n + "Text", [])])
    u.border(n + "Fill", "#0a0505", 0.85, u.margin(14, 10, 14, 10), n + "Stack")
    u.strip(n + "Accent", accent, u.margin(l=3))
    u.box("HorizontalBox", n + "Row", [
        (n + "Accent", ["VerticalAlignment=VAlign_Fill"]),
        (n + "Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"]),
    ])
    u.border(n + "Outline", "#4a1a1d", 1.0, u.margin(1, 1, 1, 1), n + "Row")
    cards.append((n + "Outline", ["Padding=%s" % u.margin(b=8), "HorizontalAlignment=HAlign_Fill"]))
u.box("VerticalBox", "Notices", cards)
u.sized("NoticesBox", "Notices", w=340, valign="VAlign_Top")

# -- root canvas
u.widget("/Script/UMG.CanvasPanel", "OwlAlertsRoot", ["Visibility=HitTestInvisible"], [
    ("/Script/UMG.CanvasPanelSlot", "AlertOutline", [
        "LayoutData=(Offsets=(Left=0.000000,Top=%.6f,Right=0.000000,Bottom=0.000000),"
        "Anchors=(Minimum=(X=0.500000,Y=0.000000),Maximum=(X=0.500000,Y=0.000000)),"
        "Alignment=(X=0.500000,Y=0.000000))" % (24 * S),
        "bAutoSize=True", "ZOrder=1"]),
    ("/Script/UMG.CanvasPanelSlot", "NoticesBox", [
        "LayoutData=(Offsets=(Left=%.6f,Top=%.6f,Right=0.000000,Bottom=0.000000),"
        "Anchors=(Minimum=(X=0.000000,Y=0.000000),Maximum=(X=0.000000,Y=0.000000)))" % NOTICES_POS,
        "bAutoSize=True"]),
])

# ---------------------------------------------------------------- paste + root + compile
wbp, wbp_ptr = prepare_wbp(eal, bp, PKG, MOD.ALERTS_WBP, FULL)
pasted = bp.import_widgets(wbp_ptr, u.render())
print("pasted %d/%d widgets" % (pasted, len(u.cls)))
assert pasted == len(u.cls), "paste dropped widgets"
root = bp.find_object("OwlAlertsRoot", outer=bp.widget_tree(wbp_ptr))
assert root, "root canvas not found after paste"
assert bp.set_root_widget(wbp_ptr, root), "RootWidget write did not read back"
bp.mark_structurally_modified(wbp_ptr)
unreal.BlueprintEditorLibrary.compile_blueprint(wbp)

# ---------------------------------------------------------------- verify
missing, loose = verify_tree(bp, wbp_ptr, u.cls, "OwlAlertsRoot")
gen = unreal.load_object(None, FULL + "_C")
print("widgets in tree: %d | missing: %s | unparented: %s | generated class: %s"
      % (len(bp.tree_widgets(wbp_ptr)), missing or "(none)", loose or "(none)", gen.get_name() if gen else None))
assert not missing and not loose and gen, "widget tree not clean"
assert bp.root_widget(wbp_ptr) == root, "root changed during compile"
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
