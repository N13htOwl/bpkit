"""owl-admin step 12: WBP_OwlCeCell -- one item in the admin menu's Inventory and Item catalog
grids (the Characters tab, ce_panel).

Layout + variables come from tm_cell (counted: a stack count in the corner; 03 makes a
layout-only cell first, so it can create them). This step rebuilds the layout and adds the
graph (tm_cell.graph):
    Construct      -> tooltip = Label; frame red if Selected; Count text; the icon, or the gem
    CellBtn click  -> Menu (the admin menu).OwlCePick(Index, Kind)

Run with Play STOPPED, after 03:  python ue_run.py mods/owl-admin/12_ce_cell.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "umg_text", "menu_shell", "tm_cell"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import tm_cell
from umg_text import Umg

eal = unreal.EditorAssetLibrary
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.CE_CELL_WBP)
FULL = MOD.full(PKG, MOD.CE_CELL_WBP)
MENU_CLS = MOD.full(PKG, MOD.MENU_WBP) + "_C"
assert unreal.find_object(None, MENU_CLS + ":OwlCePick"), "build 03 first: no OwlCePick on " + MENU_CLS
wbp, wbp_ptr, root = tm_cell.build_layout(unreal, eal, bp, PKG, FULL, MOD.CE_CELL_WBP, counted=True)

g = ir.Graph("EventGraph")
tm_cell.graph(g, Umg(MOD.BOARD_SCALE), MENU_CLS, "AsWBP Owl Admin Menu", "OwlCePick", ["Index", "Kind"], counted=True)

rep = build.build_graph(FULL, g)
assert rep["ok"], "cell graph not clean: %r" % {k: rep[k] for k in (
    "dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}
assert unreal.load_object(None, FULL + "_C"), "no generated class"
assert bp.root_widget(wbp_ptr) == root, "root changed during compile"
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s" % (MOD.VERSION, FULL))
