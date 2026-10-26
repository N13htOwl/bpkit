"""owl-admin step 07: WBP_OwlPlayerMenu -- the player menu (Shift+I), for every player.

The same frame as the admin menu (menu_shell), with one tab per player-facing board on the
design canvas (menu_defs.PLAYER_TABS: Transmog Outfits, Pet Shop, Animal Masks, Equipment &
Owl Mask, Bug Report). Each page is a placeholder card for now; the boards get built out one
at a time. No login: nothing here is admin-only.

Parent class WindowRoot + the OwlPlayerMenu row (06) make it a GUIModule like the admin menu.

Run with Play STOPPED:  python ue_run.py mods/owl-admin/07_player_menu.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "umg_text", "menu_defs", "menu_shell"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D
from umg_text import Umg
from menu_shell import Shell

eal = unreal.EditorAssetLibrary
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.PLAYER_MENU_WBP)
FULL = MOD.full(PKG, MOD.PLAYER_MENU_WBP)

u = Umg(MOD.BOARD_SCALE)
s = Shell(u, "PLAYER MENU · PRIVATE REALM", D.PLAYER_TABS, MOD.PLAYER_MODULE, (MOD.FONT_BOLD, MOD.FONT_REGULAR),
          badge="PLAYER", status="These screens are coming in later steps.")
s.header()
s.sidebar()
body = s.pages(lambda tab: [(s.placeholder("Ph_" + tab, "%s: coming in a later step." % dict(
    (t, title) for t, title, _h in D.PLAYER_TABS)[tab]), ["Padding=%s" % u.margin(t=6)])])
s.footer()
s.root(body)
wbp, wbp_ptr = s.paste(unreal, eal, bp, PKG, MOD.PLAYER_MENU_WBP, FULL)

g = ir.Graph("EventGraph")
s.graph(g)
s.tick_highlight(g, g.event("Tick", parent="/Script/UMG.UserWidget", pos=(0, 3800)))
rep = build.build_graph(FULL, g)
assert rep["ok"], "player menu graph not clean: %r" % {k: rep[k] for k in (
    "dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}

assert unreal.load_object(None, FULL + "_C"), "no generated class"
assert bp.root_widget(wbp_ptr) == s.root_ptr, "root changed during compile"
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s  (%d widgets, %d tabs)%s" % (
    MOD.VERSION, FULL, len(u.cls), len(D.PLAYER_TABS),
    "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
