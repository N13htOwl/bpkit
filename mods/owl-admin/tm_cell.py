"""A grid cell's layout, variables and graph -- one item in a menu's grid (the boards' .slot: a
76px framed square with the item's icon, or the board's red gem when the item has no icon).
WBP_OwlTmCell is an appearance in the player menu's transmog grid (07 creates them, 11 adds the
graph); WBP_OwlCeCell (counted: a stack count in the corner) is an item in the admin menu's
Inventory and Item catalog grids (03 creates them, 12 adds the graph).

    build_layout(unreal, eal, bp, pkg, full, asset, counted)   # (re)build the tree + variables
    ensure(unreal, eal, bp, pkg, full, asset, counted)         # build only if the asset doesn't exist yet
    graph(g, u, menu_cls, cast_pin, event, args, counted)      # Construct, and click -> menu.<event>(args)

Variables the menu sets before adding it: Index (into the menu's arrays), Menu, IconPath, Label
(item name, the tooltip), Selected; counted cells also Kind (which grid) and Count (the corner
text, "" for none).
"""
from bpkit import ir
import oa_config as MOD
from umg_text import Umg, prepare_wbp, verify_tree
from menu_shell import button, button_style, clicked

VARS = (("Index", "int"), ("IconPath", "string"), ("Label", "string"), ("Selected", "bool"))
COUNTED_VARS = (("Kind", "int"), ("Count", "string"))
FRAME_IDLE, FRAME_SELECTED = "#3a1214", "#ff4a50"


def build_layout(unreal, eal, bp, pkg, full, asset=MOD.TM_CELL_WBP, counted=False):
    existing = eal.load_asset("%s/%s" % (pkg, asset))
    if existing:        # an open designer tab breaks a rebuild (menu_shell.Shell.paste)
        unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(existing)
    u = Umg(MOD.BOARD_SCALE)
    u.widget("/Script/UMG.Image", "Icon", ["Brush=%s" % u.brush("#ffffff", w=56, h=56),
                                          "Visibility=Collapsed"], variable=True)
    # the board's .gem: a 28px square turned 45 degrees, red outline on dark red
    u.strip("GemCore", "#6b1a1e", u.margin(9, 9, 9, 9))
    u.border("GemEdge", "#f0343a", 1.0, u.margin(2, 2, 2, 2), "GemCore")
    u.widget("/Script/UMG.SizeBox", "Gem", [
        "WidthOverride=%.6f" % (22 * u.S), "bOverride_WidthOverride=True",
        "HeightOverride=%.6f" % (22 * u.S), "bOverride_HeightOverride=True",
        "RenderTransform=(Angle=45.000000)", "RenderTransformPivot=(X=0.500000,Y=0.500000)"],
        [("/Script/UMG.SizeBoxSlot", "GemEdge", ["HorizontalAlignment=HAlign_Fill", "VerticalAlignment=VAlign_Fill"])],
        variable=True)
    layers = [(w, ["HorizontalAlignment=HAlign_Center", "VerticalAlignment=VAlign_Center"]) for w in ("Gem", "Icon")]
    if counted:     # the stack count, bottom right over the icon
        u.text("CountText", "", MOD.FONT_BOLD, 15, "#ffffff",
               props=["ShadowOffset=(X=1.000000,Y=1.000000)", "ShadowColorAndOpacity=%s" % u.lin("#000000")])
        layers.append(("CountText", ["Padding=%s" % u.margin(0, 0, 4, 1), "HorizontalAlignment=HAlign_Right",
                                 "VerticalAlignment=VAlign_Bottom"]))
    u.widget("/Script/UMG.Overlay", "Stack", [], [("/Script/UMG.OverlaySlot", w, p) for w, p in layers])
    button(u, "CellBtn", "Stack", u.margin(), button_style(u, "#0f0707", "#1a0c0c", "#2a0b0d"))
    u.border("Frame", FRAME_IDLE, 1.0, u.margin(2, 2, 2, 2), "CellBtn", variable=True)
    u.sized("CellRoot", "Frame", w=76, h=76)
    wbp, wbp_ptr = prepare_wbp(eal, bp, pkg, asset, full)
    pasted = bp.import_widgets(wbp_ptr, u.render())
    assert pasted == len(u.cls), "cell paste dropped widgets (%d/%d)" % (pasted, len(u.cls))
    root = bp.find_object("CellRoot", outer=bp.widget_tree(wbp_ptr))
    assert root and bp.set_root_widget(wbp_ptr, root), "could not set CellRoot as the root"
    bp.mark_structurally_modified(wbp_ptr)
    bel = unreal.BlueprintEditorLibrary
    for var, t in VARS + (COUNTED_VARS if counted else ()):
        bel.add_member_variable(wbp, var, bel.get_basic_type_by_name(t))
    bel.add_member_variable(wbp, "Menu", bel.get_object_reference_type(unreal.UserWidget.static_class()))
    bel.compile_blueprint(wbp)
    missing, loose = verify_tree(bp, wbp_ptr, u.cls, "CellRoot")
    assert not missing and not loose, "cell tree not clean: missing %s, unparented %s" % (missing, loose)
    assert eal.save_asset("%s/%s" % (pkg, asset)), "cell save failed"
    return wbp, wbp_ptr, root


def ensure(unreal, eal, bp, pkg, full, asset=MOD.TM_CELL_WBP, counted=False):
    if not unreal.load_object(None, full + "_C"):
        build_layout(unreal, eal, bp, pkg, full, asset, counted)
        print("created %s (layout only; its build step adds the graph)" % asset)


# ================================================================ graph
KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
UW = "/Script/UMG.UserWidget"
WIDGET = "/Script/UMG.Widget"
IMAGE = "/Script/UMG.Image"
BORDER = "/Script/UMG.Border"
TEXT = "/Script/UMG.TextBlock"


def graph(g, u, menu_cls, cast_pin, event, args, counted=False):
    """Construct -> tooltip = Label; frame red if Selected; (counted) Count text; if IconPath is
    set, load that texture into Icon and show it instead of the gem.
    CellBtn click -> Menu (cast to menu_cls, cast_pin its output).<event>(the int cell variables in args)."""
    lcolor = ir.struct_path("/Script/CoreUObject.LinearColor")
    slatevis = ir.enum_path("/Script/UMG.ESlateVisibility")

    def ref(name, cls, pos):
        return g.var_get(name, "object", ir.obj_path(cls), pos=pos)

    def show(prev, prev_pin, name, cls, vis, pos):
        sv = g.call("SetVisibility", WIDGET, pos=pos)
        g.typed_input(sv, "InVisibility", vis, "byte", slatevis)
        g.wire(ref(name, cls, (pos[0] - 200, pos[1] + 200)), name, sv, "self", exec=False)
        g.wire(prev, prev_pin, sv, "execute")
        return sv

    # ---- Construct
    con = g.event("Construct", parent=UW, pos=(0, 0))
    tip = g.call("SetToolTipText", WIDGET, pos=(300, 0))
    g.wire(ref("CellBtn", "/Script/UMG.Button", (100, 200)), "CellBtn", tip, "self", exec=False)
    lt = g.call("Conv_StringToText", KTXT, pos=(100, 350))
    g.wire(g.var_get("Label", "string", pos=(-100, 350)), "Label", lt, "InString", exec=False)
    g.wire(lt, "ReturnValue", tip, "InToolTipText", exec=False)
    g.wire(con, "then", tip, "execute")
    col = g.call("SelectColor", KML, pos=(500, 350))
    g.typed_input(col, "A", u.lin(FRAME_SELECTED), "struct", lcolor)
    g.typed_input(col, "B", u.lin(FRAME_IDLE), "struct", lcolor)
    g.wire(g.var_get("Selected", "bool", pos=(300, 500)), "Selected", col, "bPickA", exec=False)
    fr = g.call("SetBrushColor", BORDER, pos=(650, 0))
    g.wire(ref("Frame", BORDER, (450, 200)), "Frame", fr, "self", exec=False)
    g.wire(col, "ReturnValue", fr, "InBrushColor", exec=False)
    g.wire(tip, "then", fr, "execute")
    last = fr
    if counted:
        ct = g.call("Conv_StringToText", KTXT, pos=(700, -150))
        g.wire(g.var_get("Count", "string", pos=(500, -150)), "Count", ct, "InString", exec=False)
        st = g.call("SetText", TEXT, pos=(850, -400))
        g.wire(ref("CountText", TEXT, (650, -300)), "CountText", st, "self", exec=False)
        g.wire(ct, "ReturnValue", st, "InText", exec=False)
        g.wire(fr, "then", st, "execute")
        last = st
    plen = g.call("Len", KSTR, pos=(800, 350))
    g.wire(g.var_get("IconPath", "string", pos=(600, 500)), "IconPath", plen, "S", exec=False)
    has = g.call("Greater_IntInt", KML, pos=(1000, 350))
    g.wire(plen, "ReturnValue", has, "A", exec=False)
    g.typed_input(has, "B", "0", "int")
    bIc = g.branch(pos=(1000, 0))
    g.wire(last, "then", bIc, "execute")
    g.wire(has, "ReturnValue", bIc, "Condition", exec=False)
    path = g.call("MakeSoftObjectPath", KSL, pos=(1100, 500))
    g.wire(g.var_get("IconPath", "string", pos=(900, 650)), "IconPath", path, "PathString", exec=False)
    sref = g.call("Conv_SoftObjPathToSoftObjRef", KSL, pos=(1350, 500))
    g.wire(path, "ReturnValue", sref, "SoftObjectPath", exec=False)
    ld = g.call("LoadAsset_Blocking", KSL, pos=(1300, 0))
    g.wire(sref, "ReturnValue", ld, "Asset", exec=False)
    g.wire(bIc, "then", ld, "execute")
    tc = g.cast("/Script/Engine.Texture2D", pos=(1600, 0))
    g.wire(ld, "ReturnValue", tc, "Object", exec=False)
    g.wire(ld, "then", tc, "execute")
    sb = g.call("SetBrushFromTexture", IMAGE, pos=(1900, 0))
    g.wire(ref("Icon", IMAGE, (1700, 200)), "Icon", sb, "self", exec=False)
    g.wire(tc, "AsTexture 2D", sb, "Texture", exec=False)
    g.wire(tc, "then", sb, "execute")
    show(show(sb, "then", "Icon", IMAGE, "HitTestInvisible", (2200, 0)), "then", "Gem", "/Script/UMG.SizeBox",
         "Collapsed", (2500, 0))

    # ---- click -> the menu
    cev = clicked(g, "CellBtn", (0, 900))
    mc = g.cast(menu_cls, pos=(300, 900))
    g.wire(g.var_get("Menu", "object", ir.obj_path(UW), pos=(100, 1100)), "Menu", mc, "Object", exec=False)
    g.wire(cev, "then", mc, "execute")
    call = g.call(event, menu_cls, pos=(650, 900))
    g.wire(mc, cast_pin, call, "self", exec=False)
    for k, a in enumerate(args):
        g.wire(g.var_get(a, "int", pos=(450, 1100 + 150 * k)), a, call, a, exec=False)
    g.wire(mc, "then", call, "execute")
