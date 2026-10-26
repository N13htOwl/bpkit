"""WBP_OwlTmCell's layout and variables -- one appearance in the player menu's transmog grid
(the Transmog board's .slot: a 76px framed square with the item's icon, or the board's red
gem when the item has no icon). The player menu (07) creates one per shown item at runtime
and sets its variables; 11 adds the graph (icon load, selected frame, click -> menu).

    build_layout(unreal, eal, bp, pkg, full)   # (re)build the tree + variables
    ensure(unreal, eal, bp, pkg, full)         # build only if the asset doesn't exist yet

Variables the menu sets before adding it: Index (into the menu's catalogue arrays), Menu (the
player menu), IconPath, Label (item name, the tooltip), Selected.
"""
import oa_config as MOD
from umg_text import Umg, prepare_wbp, verify_tree
from menu_shell import button, button_style

VARS = (("Index", "int"), ("IconPath", "string"), ("Label", "string"), ("Selected", "bool"))
FRAME_IDLE, FRAME_SELECTED = "#3a1214", "#ff4a50"


def build_layout(unreal, eal, bp, pkg, full):
    existing = eal.load_asset("%s/%s" % (pkg, MOD.TM_CELL_WBP))
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
    u.widget("/Script/UMG.Overlay", "Stack", [], [
        ("/Script/UMG.OverlaySlot", w, ["HorizontalAlignment=HAlign_Center", "VerticalAlignment=VAlign_Center"])
        for w in ("Gem", "Icon")])
    button(u, "CellBtn", "Stack", u.margin(), button_style(u, "#0f0707", "#1a0c0c", "#2a0b0d"))
    u.border("Frame", FRAME_IDLE, 1.0, u.margin(2, 2, 2, 2), "CellBtn", variable=True)
    u.sized("CellRoot", "Frame", w=76, h=76)
    wbp, wbp_ptr = prepare_wbp(eal, bp, pkg, MOD.TM_CELL_WBP, full)
    pasted = bp.import_widgets(wbp_ptr, u.render())
    assert pasted == len(u.cls), "cell paste dropped widgets (%d/%d)" % (pasted, len(u.cls))
    root = bp.find_object("CellRoot", outer=bp.widget_tree(wbp_ptr))
    assert root and bp.set_root_widget(wbp_ptr, root), "could not set CellRoot as the root"
    bp.mark_structurally_modified(wbp_ptr)
    bel = unreal.BlueprintEditorLibrary
    for var, t in VARS:
        bel.add_member_variable(wbp, var, bel.get_basic_type_by_name(t))
    bel.add_member_variable(wbp, "Menu", bel.get_object_reference_type(unreal.UserWidget.static_class()))
    bel.compile_blueprint(wbp)
    missing, loose = verify_tree(bp, wbp_ptr, u.cls, "CellRoot")
    assert not missing and not loose, "cell tree not clean: missing %s, unparented %s" % (missing, loose)
    assert eal.save_asset("%s/%s" % (pkg, MOD.TM_CELL_WBP)), "cell save failed"
    return wbp, wbp_ptr, root


def ensure(unreal, eal, bp, pkg, full):
    if not unreal.load_object(None, full + "_C"):
        build_layout(unreal, eal, bp, pkg, full)
        print("created %s (layout only; 11 adds its graph)" % MOD.TM_CELL_WBP)
