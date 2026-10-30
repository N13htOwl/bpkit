"""owl-admin step 06: DT_OwlAdmin_UIModules -- the UIModuleTableRow table that 09's
ModDataTableOperations override merges into the game's DT_UIModuleTable, registering both
menus as GUIModules: OwlAdminMenu (03, Shift+O) and OwlPlayerMenu (07, Shift+I), and the NPC window
OwlNpcWindow (15, no key: BP_OwlNPC opens it when a player presses E on the NPC).

Keys: each row's ToggleActionName names an input action that 09 registers at mod init
(oa_config.ACTIONS). Conan's GUIModuleController binds module toggles by action name -- the
same way Tab opens the inventory (row CharacterInventory, ToggleActionName=ToggleInventory)
-- so pressing the key opens the menu, pressing it again closes it. (v6 polled the keys from
the ModController's Tick instead; that never fired in PIE.)

Why a module: Conan's GUIModuleController owns the mouse cursor and input mode. It shows
the cursor only while one of its modules' windows is up, and resets bShowMouseCursor for
anything else. As a module the menu gets the cursor, Esc-to-close and the shortcut bar
hidden, like Conan's own full-screen menus. (Proven in PIE 2026-10-26 by merging this row
by hand: ActivateModule showed the cursor, deactivating hid it again.)

Rows: modelled on the shipped ModMenu row (Fullscreen, Close on Esc, z 30), but shown in
the playing state instead of the main menu.

Run with Play STOPPED, after 03, 07 and 15:  python ue_run.py mods/owl-admin/06_ui_module_table.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
import json
from bpkit import config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
sys.modules.pop("oa_config", None)
import oa_config as MOD

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.UI_MODULE_TABLE)
MODULES = [(MOD.MENU_MODULE, MOD.MENU_WBP, MOD.ACTIONS[0][0]),
           (MOD.PLAYER_MODULE, MOD.PLAYER_MENU_WBP, MOD.ACTIONS[1][0]),
           (MOD.NPC_MODULE, MOD.NPC_WINDOW_WBP, "None")]   # no key: the NPC (14) opens it when talked to
for _m, wbp, _a in MODULES:
    cls = unreal.load_object(None, MOD.full(PKG, wbp) + "_C")
    assert cls and isinstance(unreal.get_default_object(cls), unreal.WindowRoot), \
        "build 03, 07 and 15 first: %s must be a WindowRoot" % wbp
eal = unreal.EditorAssetLibrary
DTL = unreal.DataTableFunctionLibrary

dt = eal.load_asset(PATH)
if dt is None:
    factory = unreal.DataTableFactory()
    factory.set_editor_property("struct", unreal.UIModuleTableRow.static_struct())
    dt = unreal.AssetToolsHelpers.get_asset_tools().create_asset(MOD.UI_MODULE_TABLE, PKG, unreal.DataTable, factory)
assert dt and dt.get_row_struct().get_name() == "UIModuleTableRow", "bad table: %r" % dt

rows = [{"Name": module, "WidgetClass": MOD.full(PKG, wbp) + "_C", "ToggleActionName": action,
         "Category": "Fullscreen", "FullscreenGUIAction": "Close", "CloseOnESC": True, "ZOrder": 30,
         "bForceHideShortcutBar": True, "ShowInPlayingState": True, "ShowWhenDead": False,
         "ShowSelect": True, "ShowBack": True}
        for module, wbp, action in MODULES]
assert DTL.fill_data_table_from_json_string(dt, json.dumps(rows)), "fill failed"
assert eal.save_asset(PATH), "save failed"

names = [str(n) for n in DTL.get_data_table_row_names(dt)]
cols = {c: DTL.get_data_table_column_as_string(dt, c) for c in ("WidgetClass", "ToggleActionName", "Category",
                                                                 "CloseOnESC", "ShowInPlayingState")}
for i, n in enumerate(names):
    print("row %s:" % n, {c: v[i] for c, v in cols.items()})
assert names == [m[0] for m in MODULES], "rows did not read back"
assert all(m[1] in cols["WidgetClass"][i] and cols["ToggleActionName"][i] == m[2] for i, m in enumerate(MODULES)), \
    "widget class / toggle action did not read back"
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, PATH, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
