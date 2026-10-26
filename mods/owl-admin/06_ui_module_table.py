"""owl-admin step 06: DT_OwlAdmin_UIModules -- the 1-row UIModuleTableRow table that 02's
ModDataTableOperations override merges into the game's DT_UIModuleTable, registering the
admin menu as a GUIModule named OwlAdminMenu.

Why a module: Conan's GUIModuleController owns the mouse cursor and input mode. It shows
the cursor only while one of its modules' windows is up, and resets bShowMouseCursor for
anything else. As a module the menu gets the cursor, Esc-to-close and the shortcut bar
hidden, like Conan's own full-screen menus. (Proven in PIE 2026-10-26 by merging this row
by hand: ActivateModule showed the cursor, deactivating hid it again.)

Row: modelled on the shipped ModMenu row (Fullscreen, Close on Esc, z 30), but shown in
the playing state instead of the main menu.

Run with Play STOPPED, after 03:  python ue_run.py mods/owl-admin/06_ui_module_table.py
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
MENU_CLS = MOD.full(PKG, MOD.MENU_WBP) + "_C"
assert isinstance(unreal.get_default_object(unreal.load_object(None, MENU_CLS)), unreal.WindowRoot), \
    "run 03_menu_widget.py first: %s must be a WindowRoot" % MENU_CLS
eal = unreal.EditorAssetLibrary
DTL = unreal.DataTableFunctionLibrary

dt = eal.load_asset(PATH)
if dt is None:
    factory = unreal.DataTableFactory()
    factory.set_editor_property("struct", unreal.UIModuleTableRow.static_struct())
    dt = unreal.AssetToolsHelpers.get_asset_tools().create_asset(MOD.UI_MODULE_TABLE, PKG, unreal.DataTable, factory)
assert dt and dt.get_row_struct().get_name() == "UIModuleTableRow", "bad table: %r" % dt

row = {"Name": MOD.MENU_MODULE, "WidgetClass": MENU_CLS, "Category": "Fullscreen", "FullscreenGUIAction": "Close",
       "CloseOnESC": True, "ZOrder": 30, "bForceHideShortcutBar": True,
       "ShowInPlayingState": True, "ShowWhenDead": False, "ShowSelect": True, "ShowBack": True}
assert DTL.fill_data_table_from_json_string(dt, json.dumps([row])), "fill failed"
assert eal.save_asset(PATH), "save failed"

names = [str(n) for n in DTL.get_data_table_row_names(dt)]
back = dict(zip(names, DTL.get_data_table_column_as_string(dt, "WidgetClass")))
print("rows:", names, "| WidgetClass:", back)
assert names == [MOD.MENU_MODULE] and MOD.MENU_WBP in back[MOD.MENU_MODULE], "row did not read back"
for col in ("Category", "CloseOnESC", "ShowInPlayingState"):
    print("  %s = %s" % (col, DTL.get_data_table_column_as_string(dt, col)[0]))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, PATH, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
