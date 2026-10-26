"""owl-admin step 05: DT_OwlAdmin_Commands -- the 1-row BlueprintCommandDataRow table that
02's ModDataTableOperations override merges into the game's CustomConsoleCommandsDataTable,
so `dc OwlAdmin` resolves. Row: CommandActorClass = BP_OwlAdminMenuCommand, RequireAdmin
(SP players are admin), RunOnClient (the menu is local UI), not RunOnServer.

Run with Play STOPPED, after 04:  python ue_run.py mods/owl-admin/05_command_table.py
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
PATH = "%s/%s" % (PKG, MOD.CMD_TABLE)
CMD_CLS = MOD.full(PKG, MOD.MENU_CMD) + "_C"
assert unreal.load_object(None, CMD_CLS), "run 04_menu_command.py first: no " + CMD_CLS
eal = unreal.EditorAssetLibrary
DTL = unreal.DataTableFunctionLibrary

dt = eal.load_asset(PATH)
if dt is None:
    factory = unreal.DataTableFactory()
    factory.set_editor_property("struct", unreal.BlueprintCommandDataRow.static_struct())
    dt = unreal.AssetToolsHelpers.get_asset_tools().create_asset(MOD.CMD_TABLE, PKG, unreal.DataTable, factory)
assert dt and dt.get_row_struct().get_name() == "BlueprintCommandDataRow", "bad table: %r" % dt

cols = [str(c) for c in DTL.get_data_table_column_export_names(dt)]


def col(sub):
    c = next((c for c in cols if sub in c.lower().replace("_", "")), None)
    assert c, "column %r not in %s" % (sub, cols)
    return c


row = {"Name": MOD.CMD_NAME, col("commandactorclass"): CMD_CLS,
       col("requireadmin"): True, col("runonserver"): False, col("runonclient"): True}
assert DTL.fill_data_table_from_json_string(dt, json.dumps([row])), "fill failed"
assert eal.save_asset(PATH), "save failed"

back = json.loads(DTL.export_data_table_to_json_string(dt))
print("row:", back)
assert [r["Name"] for r in back] == [MOD.CMD_NAME] and MOD.MENU_CMD in str(back[0]), "row did not read back"
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, PATH, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
