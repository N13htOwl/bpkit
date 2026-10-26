"""owl-admin step 03: WBP_OwlAdminMenu -- the design canvas's Admin Restrictions Menu board
as a real, clickable UMG menu (Step 1: layout + navigation; settings not applied yet).

Layout (board px x1.5 -> fills a 1080p screen):
    CanvasPanel MenuRoot > MenuFrame (2px #5a1a1e) > MenuBg > MenuLayout (VBox):
      Header:  OWL ADMIN + BETA badge, subtitle, PREVIEW badge, CloseBtn
      Body:    Sidebar (14 TabBtn_<tab>) | TabPages (WidgetSwitcher, one ScrollBox page per tab)
               each page: title + hint, a row per setting (CheckBox or SpinBox + unit),
               and a placeholder card per special panel (menu_defs.PANELS)
      Footer:  status line, Reset, Apply Restrictions (not wired in Step 1)

Parent class: Conan's WindowRoot, so the menu is a GUIModule window (the OwlAdminMenu row,
06): Conan's GUIModuleController then owns the mouse cursor, input and Esc for it, exactly
as for its own menus. (A plain UserWidget that sets bShowMouseCursor gets it reset by the
controller within a frame -- seen in PIE 2026-10-26.)

Graph:
    TabBtn_<tab>.OnClicked -> TabPages.SetActiveWidgetIndex(i)
    CloseBtn.OnClicked     -> GetGUIModuleController.ToggleModule(OwlAdminMenu)   (closes it)
    Tick                   -> each TabBtn's background = active colour if its page is showing

Toggles are CheckBoxes and numbers are SpinBoxes (min/max/step from the board), so they
work with no graph logic; the board's -/+ buttons become a SpinBox you drag or type into.

Run with Play STOPPED:  python ue_run.py mods/owl-admin/03_menu_widget.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "umg_text", "menu_defs"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D
from umg_text import Umg, prepare_wbp, verify_tree

eal = unreal.EditorAssetLibrary
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.MENU_WBP)
FULL = MOD.full(PKG, MOD.MENU_WBP)

u = Umg(MOD.BOARD_SCALE)
B, R = MOD.FONT_BOLD, MOD.FONT_REGULAR
TAB_ACTIVE, TAB_IDLE = "#3a0b0e", "#0b0606"
CANVAS, BUTTON, SWITCHER = "/Script/UMG.CanvasPanel", "/Script/UMG.Button", "/Script/UMG.WidgetSwitcher"


def button_style(normal, hovered, pressed):
    return ("WidgetStyle=(Normal=%s,Hovered=%s,Pressed=%s,NormalPadding=%s,PressedPadding=%s)"
            % (u.brush(normal), u.brush(hovered), u.brush(pressed), u.margin(), u.margin()))


def button(name, label_name, pad, style, halign="HAlign_Center"):
    return u.widget(BUTTON, name, [style, "BackgroundColor=(R=1.000000,G=1.000000,B=1.000000,A=1.000000)",
                                   "IsFocusable=False"],
                    [("/Script/UMG.ButtonSlot", label_name,
                      ["Padding=%s" % pad, "HorizontalAlignment=%s" % halign, "VerticalAlignment=VAlign_Center"])],
                    variable=True)


def framed(name, outline, fill, child, pad, line=1, alpha=1.0):
    """1px outline Border around a fill Border (the board's border:1px + background)."""
    u.border(name + "Fill", fill, alpha, pad, child)
    return u.border(name, outline, 1.0, u.margin(line, line, line, line), name + "Fill")


# ================================================================ header
u.text("BrandTitle", "OWL ADMIN", B, 28, "#ffffff", spacing_px=4)
u.text("BetaText", "BETA", B, 15, "#ffffff", spacing_px=3)
u.border("BetaBadge", "#b3121a", 1.0, u.margin(10, 3, 10, 3), "BetaText")
u.box("HorizontalBox", "BrandRow", [("BrandTitle", ["VerticalAlignment=VAlign_Center"]),
                                    ("BetaBadge", ["Padding=%s" % u.margin(l=12), "VerticalAlignment=VAlign_Center"])])
u.text("BrandSub", "RESTRICTIONS · PRIVATE REALM", B, 15, "#f0343a", spacing_px=3)
u.box("VerticalBox", "Brand", [("BrandRow", []), ("BrandSub", ["Padding=%s" % u.margin(t=2)])])
u.text("PreviewText", "PREVIEW", B, 18, "#f2e6e2", spacing_px=1)
framed("PreviewBadge", "#5a1a1e", "#150909", "PreviewText", u.margin(16, 8, 16, 8))
u.text("CloseText", "X", B, 22, "#f2e6e2")
button("CloseBtn", "CloseText", u.margin(), button_style("#150909", "#3a0b0e", "#b3121a"))
u.sized("CloseBox", "CloseBtn", w=44, h=44)
u.box("HorizontalBox", "HeaderRow", [
    ("Brand", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
    ("PreviewBadge", ["VerticalAlignment=VAlign_Center"]),
    ("CloseBox", ["Padding=%s" % u.margin(l=20), "VerticalAlignment=VAlign_Center"]),
])
u.border("Header", "#140909", 1.0, u.margin(28, 0, 28, 0), "HeaderRow")
u.sized("HeaderBox", "Header", h=76)
u.strip("HeaderLine", "#b3121a", u.margin(t=2))

# ================================================================ sidebar
# 14 tabs are taller than the board's sidebar at its 56px tab height, so they're 36px here
# (fits a 1080p screen) inside a ScrollBox (scrolls instead of spilling over the footer).
tab_items = []
for tab, title, _hint in D.TABS:
    u.text("TabTxt_" + tab, title.upper(), B, 17, "#d8c8c3", spacing_px=1.5, variable=False)
    button("TabBtn_" + tab, "TabTxt_" + tab, u.margin(20, 0, 20, 0),
           button_style("#ffffff", "#ffffff", "#ffffff"), halign="HAlign_Left")
    u.sized("TabBox_" + tab, "TabBtn_" + tab, h=36)
    tab_items.append(("TabBox_" + tab, ["Padding=%s" % u.margin(b=2), "HorizontalAlignment=HAlign_Fill"]))
u.box("ScrollBox", "TabScroll", tab_items, props=[
    "WidgetBarStyle=(NormalThumbImage=%s,HoveredThumbImage=%s,DraggedThumbImage=%s)" % (
        u.brush("#5a1a1e"), u.brush("#8a2a2e"), u.brush("#b3121a")),
    "ScrollbarThickness=(X=4.000000,Y=4.000000)"])
u.strip("SideNoteLine", "#2a1012", u.margin(t=1))
u.text("SideNote", "Preview: these settings are not applied to the game yet.", R, 15, "#a8908a", wrap=True,
       variable=False)
u.box("VerticalBox", "SideList", [("TabScroll", ["Size=(SizeRule=Fill)", "HorizontalAlignment=HAlign_Fill"]),
                                  ("SideNoteLine", ["HorizontalAlignment=HAlign_Fill"]),
                                  ("SideNote", ["Padding=%s" % u.margin(20, 12, 20, 12)])])
u.border("Sidebar", "#0b0606", 1.0, u.margin(t=12), "SideList")
u.sized("SidebarBox", "Sidebar", w=240)
u.strip("SidebarLine", "#3a1214", u.margin(l=1))

# ================================================================ pages
page_ids = []
for tab, title, hint in D.TABS:
    items = []
    u.text("PgTitle_" + tab, title.upper(), B, 22, "#ffffff", spacing_px=3, variable=False)
    u.text("PgHint_" + tab, hint, R, 16, "#a8908a", variable=False)
    u.box("HorizontalBox", "PgHead_" + tab, [
        ("PgTitle_" + tab, ["VerticalAlignment=VAlign_Bottom"]),
        ("PgHint_" + tab, ["Size=(SizeRule=Fill)", "HorizontalAlignment=HAlign_Right", "VerticalAlignment=VAlign_Bottom"]),
    ])
    items.append(("PgHead_" + tab, ["Padding=%s" % u.margin(b=14)]))

    for s in [s for s in D.SETTINGS if s["tab"] == tab]:
        r = "R_" + s["id"]
        u.text(r + "_Lbl", s["label"], B, 20, "#ffffff", variable=False)
        u.text(r + "_Desc", s["desc"], R, 16, "#b8a29c", wrap=True, variable=False)
        u.box("VerticalBox", r + "_Txt", [(r + "_Lbl", []), (r + "_Desc", ["Padding=%s" % u.margin(t=3)])])
        ctl = "Set_" + s["id"]
        if s["type"] == "toggle":
            u.widget("/Script/UMG.CheckBox", ctl, [
                "CheckedState=%s" % ("Checked" if s["default"] else "Unchecked"),
                "WidgetStyle=(UncheckedImage=%s,UncheckedHoveredImage=%s,UncheckedPressedImage=%s,"
                "CheckedImage=%s,CheckedHoveredImage=%s,CheckedPressedImage=%s,"
                "BackgroundImage=(DrawAs=NoDrawType),BackgroundHoveredImage=(DrawAs=NoDrawType),"
                "BackgroundPressedImage=(DrawAs=NoDrawType),Padding=%s)" % (
                    u.brush("#1a0c0c", w=76, h=44), u.brush("#3a0b0e", w=76, h=44), u.brush("#5a1a1e", w=76, h=44),
                    u.brush("#b3121a", w=76, h=44), u.brush("#d01a22", w=76, h=44), u.brush("#ff4a50", w=76, h=44),
                    u.margin()),
                "IsFocusable=False"], variable=True)
            control = ctl
        else:
            frac = 1 if s["step"] < 1 else 0
            u.widget("/Script/UMG.SpinBox", ctl, [
                "Value=%.6f" % s["default"],
                "MinValue=%.6f" % s["min"], "MaxValue=%.6f" % s["max"],
                "MinSliderValue=%.6f" % s["min"], "MaxSliderValue=%.6f" % s["max"],
                "bOverride_MinValue=True", "bOverride_MaxValue=True",
                "bOverride_MinSliderValue=True", "bOverride_MaxSliderValue=True",
                "Delta=%.6f" % s["step"], "bAlwaysUsesDeltaSnap=True",
                "MinFractionalDigits=%d" % frac, "MaxFractionalDigits=%d" % frac,
                "Font=%s" % u.font(B, 24),
                "Justification=Center",
                "WidgetStyle=(BackgroundBrush=%s,HoveredBackgroundBrush=%s,ActiveFillBrush=%s,"
                "InactiveFillBrush=%s,ForegroundColor=(SpecifiedColor=%s),TextPadding=%s)" % (
                    u.brush("#1a0c0c"), u.brush("#3a0b0e"), u.brush("#b3121a"), u.brush("#5a1a1e"),
                    u.lin("#ff5a5f"), u.margin(8, 4, 8, 4)),
                "ForegroundColor=(SpecifiedColor=%s)" % u.lin("#ff5a5f"),
            ], variable=True)
            u.sized(r + "_Size", ctl, w=160, h=44)
            unit = {"x": "×"}.get(s["unit"], s["unit"])
            u.text(r + "_Unit", unit, B, 20, "#ff5a5f", variable=False)
            control = u.box("HorizontalBox", r + "_Ctl", [
                (r + "_Size", ["VerticalAlignment=VAlign_Center"]),
                (r + "_Unit", ["Padding=%s" % u.margin(l=8), "VerticalAlignment=VAlign_Center"]),
            ])
            u.sized(r + "_CtlBox", control, w=200, halign="HAlign_Left")
            control = r + "_CtlBox"
        u.box("HorizontalBox", r + "_In", [
            (r + "_Txt", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
            (control, ["Padding=%s" % u.margin(l=24), "VerticalAlignment=VAlign_Center"]),
        ])
        u.border(r + "_Fill", "#120909", 1.0, u.margin(20, 14, 20, 14), r + "_In")
        u.strip(r + "_Acc", "#4a1a1d", u.margin(l=3))
        u.box("HorizontalBox", r + "_Row", [(r + "_Acc", ["VerticalAlignment=VAlign_Fill"]),
                                             (r + "_Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
        u.border(r, "#2a1012", 1.0, u.margin(1, 1, 1, 1), r + "_Row")
        items.append((r, ["Padding=%s" % u.margin(b=10)]))

    for i, panel in enumerate(D.PANELS.get(tab, [])):
        p = "Ph_%s_%d" % (tab, i)
        u.text(p + "_Txt", "%s: coming in a later step." % panel, R, 17, "#b8a29c", wrap=True, variable=False)
        framed(p, "#4a1a1d", "#0b0505", p + "_Txt", u.margin(16, 16, 16, 16))
        items.append((p, ["Padding=%s" % u.margin(t=6, b=10)]))

    u.box("VerticalBox", "PgList_" + tab, items)
    u.box("ScrollBox", "Page_" + tab, [("PgList_" + tab, [])], props=[
        "WidgetBarStyle=(NormalThumbImage=%s,HoveredThumbImage=%s,DraggedThumbImage=%s)" % (
            u.brush("#5a1a1e"), u.brush("#8a2a2e"), u.brush("#b3121a")),
        "ScrollbarThickness=(X=6.000000,Y=6.000000)"])
    page_ids.append("Page_" + tab)

u.widget(SWITCHER, "TabPages", ["ActiveWidgetIndex=0"],
         [("/Script/UMG.WidgetSwitcherSlot", pid, ["HorizontalAlignment=HAlign_Fill", "VerticalAlignment=VAlign_Fill"])
          for pid in page_ids], variable=True)
u.border("Content", "#000000", 0.0, u.margin(28, 24, 28, 24), "TabPages")
u.box("HorizontalBox", "Body", [("SidebarBox", ["VerticalAlignment=VAlign_Fill"]),
                                ("SidebarLine", ["VerticalAlignment=VAlign_Fill"]),
                                ("Content", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])

# ================================================================ footer
u.text("StatusText", "Preview build: these settings are not applied to the game yet.", B, 18, "#f2e6e2")
u.text("ResetText", "RESET", B, 19, "#f2e6e2", spacing_px=2, variable=False)
button("ResetBtn", "ResetText", u.margin(28, 0, 28, 0), button_style("#0d0606", "#1a0c0c", "#3a0b0e"))
framed("ResetFrame", "#5a1a1e", "#0d0606", "ResetBtn", u.margin())
u.sized("ResetBox", "ResetFrame", h=48)
u.text("ApplyText", "APPLY RESTRICTIONS", B, 19, "#ffffff", spacing_px=2, variable=False)
button("ApplyBtn", "ApplyText", u.margin(36, 0, 36, 0), button_style("#b3121a", "#d01a22", "#8a2a2e"))
u.sized("ApplyBox", "ApplyBtn", h=48)
u.box("HorizontalBox", "FooterRow", [
    ("StatusText", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
    ("ResetBox", ["VerticalAlignment=VAlign_Center"]),
    ("ApplyBox", ["Padding=%s" % u.margin(l=12), "VerticalAlignment=VAlign_Center"]),
])
u.border("Footer", "#0d0606", 1.0, u.margin(28, 0, 28, 0), "FooterRow")
u.sized("FooterBox", "Footer", h=76)
u.strip("FooterLine", "#b3121a", u.margin(t=2))

# ================================================================ frame + root
u.box("VerticalBox", "MenuLayout", [
    ("HeaderBox", ["HorizontalAlignment=HAlign_Fill"]),
    ("HeaderLine", ["HorizontalAlignment=HAlign_Fill"]),
    ("Body", ["Size=(SizeRule=Fill)", "HorizontalAlignment=HAlign_Fill"]),
    ("FooterLine", ["HorizontalAlignment=HAlign_Fill"]),
    ("FooterBox", ["HorizontalAlignment=HAlign_Fill"]),
])
u.border("MenuBg", "#0b0505", 1.0, u.margin(), "MenuLayout")
u.border("MenuFrame", "#5a1a1e", 1.0, u.margin(2, 2, 2, 2), "MenuBg")
u.widget(CANVAS, "MenuRoot", [], [("/Script/UMG.CanvasPanelSlot", "MenuFrame", [
    "LayoutData=(Offsets=(Left=0.000000,Top=0.000000,Right=0.000000,Bottom=0.000000),"
    "Anchors=(Minimum=(X=0.000000,Y=0.000000),Maximum=(X=1.000000,Y=1.000000)))"])])

# ================================================================ paste + root + compile
wbp, wbp_ptr = prepare_wbp(eal, bp, PKG, MOD.MENU_WBP, FULL, parent=unreal.WindowRoot)
pasted = bp.import_widgets(wbp_ptr, u.render())
print("pasted %d/%d widgets" % (pasted, len(u.cls)))
assert pasted == len(u.cls), "paste dropped widgets"
root = bp.find_object("MenuRoot", outer=bp.widget_tree(wbp_ptr))
assert root and bp.set_root_widget(wbp_ptr, root), "could not set MenuRoot as the root"
bp.mark_structurally_modified(wbp_ptr)
unreal.BlueprintEditorLibrary.compile_blueprint(wbp)       # widget variables exist before the graph
missing, loose = verify_tree(bp, wbp_ptr, u.cls, "MenuRoot")
print("widgets in tree: %d | missing: %s | unparented: %s"
      % (len(bp.tree_widgets(wbp_ptr)), missing or "(none)", loose or "(none)"))
assert not missing and not loose, "widget tree not clean"

# ================================================================ graph
GUIMC = "/Script/ConanSandbox.GUIModuleController"
KML = "/Script/Engine.KismetMathLibrary"
LCOLOR = ir.struct_path("/Script/CoreUObject.LinearColor")
g = ir.Graph("EventGraph")


def clicked(btn, pos):
    """K2Node_ComponentBoundEvent for <btn>.OnClicked (format of shipped W_ServerInfo)."""
    n = g.node("K2Node_ComponentBoundEvent", [
        'DelegatePropertyName="OnClicked"',
        "DelegateOwnerClass=\"/Script/CoreUObject.Class'/Script/UMG.Button'\"",
        'ComponentPropertyName="%s"' % btn,
        "EventReference=(MemberParent=\"/Script/CoreUObject.Package'/Script/UMG'\","
        "MemberName=\"OnButtonClickedEvent__DelegateSignature\")",
        "bInternalEvent=True",
        'CustomFunctionName="BndEvt__%s_OnClicked"' % btn,
    ], base="ComponentBoundEvent", pos=pos)
    n.pin("then").typed("exec", direction="EGPD_Output")
    return n


pages = g.var_get("TabPages", "object", ir.obj_path(SWITCHER), pos=(300, -200))
for i, (tab, _t, _h) in enumerate(D.TABS):
    ev = clicked("TabBtn_" + tab, (0, i * 200))
    sai = g.call("SetActiveWidgetIndex", SWITCHER, pos=(400, i * 200))
    g.typed_input(sai, "Index", str(i), "int")
    g.wire(ev, "then", sai, "execute")
    g.wire(pages, "TabPages", sai, "self", exec=False)

# Close: toggle our module off -- the controller closes the window and hands the mouse back
cev = clicked("CloseBtn", (0, 3200))
gmc = g.call("GetGUIModuleController", GUIMC, pos=(200, 3400))
tgl = g.call("ToggleModule", GUIMC, pos=(500, 3200))
g.typed_input(tgl, "ModuleName", MOD.MENU_MODULE, "name")
g.wire(cev, "then", tgl, "execute")
g.wire(gmc, "ReturnValue", tgl, "self", exec=False)

# Tick: highlight the active tab
tick = g.event("Tick", parent="/Script/UMG.UserWidget", pos=(0, 3800))
idx = g.call("GetActiveWidgetIndex", SWITCHER, pos=(200, 4000))
g.wire(g.var_get("TabPages", "object", ir.obj_path(SWITCHER), pos=(0, 4000)), "TabPages", idx, "self", exec=False)
prev, prev_pin = tick, "then"
for i, (tab, _t, _h) in enumerate(D.TABS):
    x = 500 + i * 350
    eq = g.call("EqualEqual_IntInt", KML, pos=(x, 4200))
    g.wire(idx, "ReturnValue", eq, "A", exec=False)
    g.typed_input(eq, "B", str(i), "int")
    sel = g.call("SelectColor", KML, pos=(x, 4400))
    g.typed_input(sel, "A", u.lin(TAB_ACTIVE), "struct", LCOLOR)
    g.typed_input(sel, "B", u.lin(TAB_IDLE), "struct", LCOLOR)
    g.wire(eq, "ReturnValue", sel, "bPickA", exec=False)
    sbc = g.call("SetBackgroundColor", BUTTON, pos=(x, 3800))
    g.wire(g.var_get("TabBtn_" + tab, "object", ir.obj_path(BUTTON), pos=(x, 3650)), "TabBtn_" + tab,
           sbc, "self", exec=False)
    g.wire(sel, "ReturnValue", sbc, "InBackgroundColor", exec=False)
    g.wire(prev, prev_pin, sbc, "execute")
    prev, prev_pin = sbc, "then"

rep = build.build_graph(FULL, g)
assert rep["ok"], "menu graph not clean: %r" % {k: rep[k] for k in ("dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}

# ================================================================ verify
gen = unreal.load_object(None, FULL + "_C")
assert gen, "no generated class"
assert bp.root_widget(wbp_ptr) == root, "root changed during compile"
spin = bp.export_widgets([bp.find_object("Set_cap", outer=bp.widget_tree(wbp_ptr))])
print("SpinBox readback (Set_cap):", [l.strip() for l in spin.splitlines()
                                      if any(k in l for k in ("Value=", "Delta=", "bOverride_MinValue"))][:6])
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s  (%d widgets, %d tabs, %d settings)%s" % (
    MOD.VERSION, FULL, len(u.cls), len(D.TABS), len(D.SETTINGS),
    "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
