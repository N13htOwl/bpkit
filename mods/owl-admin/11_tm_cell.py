"""owl-admin step 11: WBP_OwlTmCell -- one appearance in the player menu's transmog grid.

Layout + variables come from tm_cell (07 makes a layout-only cell first, so it can create
them). This step rebuilds the layout and adds the graph:
    Construct      -> tooltip = Label; frame red if Selected; if IconPath is set, load that
                      texture into Icon and show it instead of the gem
    CellBtn click  -> Menu (the player menu).OwlTmPick(Index)

Run with Play STOPPED, after 07:  python ue_run.py mods/owl-admin/11_tm_cell.py
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
from menu_shell import clicked

eal = unreal.EditorAssetLibrary
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.TM_CELL_WBP)
FULL = MOD.full(PKG, MOD.TM_CELL_WBP)
MENU_CLS = MOD.full(PKG, MOD.PLAYER_MENU_WBP) + "_C"
assert unreal.load_object(None, MENU_CLS), "build 07 first: no " + MENU_CLS
wbp, wbp_ptr, root = tm_cell.build_layout(unreal, eal, bp, PKG, FULL)

KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
UW = "/Script/UMG.UserWidget"
WIDGET = "/Script/UMG.Widget"
IMAGE = "/Script/UMG.Image"
BORDER = "/Script/UMG.Border"
LCOLOR = ir.struct_path("/Script/CoreUObject.LinearColor")
SLATEVIS = ir.enum_path("/Script/UMG.ESlateVisibility")
u = Umg(MOD.BOARD_SCALE)
g = ir.Graph("EventGraph")


def ref(name, cls, pos):
    return g.var_get(name, "object", ir.obj_path(cls), pos=pos)


def show(prev, prev_pin, name, cls, vis, pos):
    sv = g.call("SetVisibility", WIDGET, pos=pos)
    g.typed_input(sv, "InVisibility", vis, "byte", SLATEVIS)
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
g.typed_input(col, "A", u.lin(tm_cell.FRAME_SELECTED), "struct", LCOLOR)
g.typed_input(col, "B", u.lin(tm_cell.FRAME_IDLE), "struct", LCOLOR)
g.wire(g.var_get("Selected", "bool", pos=(300, 500)), "Selected", col, "bPickA", exec=False)
fr = g.call("SetBrushColor", BORDER, pos=(650, 0))
g.wire(ref("Frame", BORDER, (450, 200)), "Frame", fr, "self", exec=False)
g.wire(col, "ReturnValue", fr, "InBrushColor", exec=False)
g.wire(tip, "then", fr, "execute")
plen = g.call("Len", KSTR, pos=(800, 350))
g.wire(g.var_get("IconPath", "string", pos=(600, 500)), "IconPath", plen, "S", exec=False)
has = g.call("Greater_IntInt", KML, pos=(1000, 350))
g.wire(plen, "ReturnValue", has, "A", exec=False)
g.typed_input(has, "B", "0", "int")
bIc = g.branch(pos=(1000, 0))
g.wire(fr, "then", bIc, "execute")
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
show(show(sb, "then", "Icon", IMAGE, "HitTestInvisible", (2200, 0)), "then", "Gem", "/Script/UMG.SizeBox", "Collapsed",
     (2500, 0))

# ---- click -> the menu
cev = clicked(g, "CellBtn", (0, 900))
mc = g.cast(MENU_CLS, pos=(300, 900))
g.wire(g.var_get("Menu", "object", ir.obj_path(UW), pos=(100, 1100)), "Menu", mc, "Object", exec=False)
g.wire(cev, "then", mc, "execute")
call = g.call("OwlTmPick", MENU_CLS, pos=(650, 900))
g.wire(mc, "AsWBP Owl Player Menu", call, "self", exec=False)
g.wire(g.var_get("Index", "int", pos=(450, 1100)), "Index", call, "Index", exec=False)
g.wire(mc, "then", call, "execute")

rep = build.build_graph(FULL, g)
assert rep["ok"], "cell graph not clean: %r" % {k: rep[k] for k in (
    "dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}
assert unreal.load_object(None, FULL + "_C"), "no generated class"
assert bp.root_widget(wbp_ptr) == root, "root changed during compile"
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s" % (MOD.VERSION, FULL))
