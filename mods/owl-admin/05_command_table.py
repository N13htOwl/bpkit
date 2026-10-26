"""owl-admin step 05: DT_OwlAdmin_Commands -- the BlueprintCommandDataRow table that 09's
ModDataTableOperations override merges into the game's CustomConsoleCommandsDataTable, one
row per oa_config.COMMANDS entry: the command class (04), RequireAdmin (Conan admin; only
OwlSetPassword), and where it runs (OwlAdmin opens local UI -> client; the login commands
read the server's password and write the server's unlocked list -> server).

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
for _cmd, cls, *_f in MOD.COMMANDS:
    assert unreal.load_object(None, MOD.full(PKG, cls) + "_C"), "run 04_commands.py first: no " + cls
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


rows = [{"Name": cmd, col("commandactorclass"): MOD.full(PKG, cls) + "_C",
         col("requireadmin"): admin, col("runonserver"): server, col("runonclient"): client}
        for cmd, cls, admin, server, client in MOD.COMMANDS]
assert DTL.fill_data_table_from_json_string(dt, json.dumps(rows)), "fill failed"
assert eal.save_asset(PATH), "save failed"

back = json.loads(DTL.export_data_table_to_json_string(dt))
for r in back:
    print("row:", r)
assert [r["Name"] for r in back] == [c[0] for c in MOD.COMMANDS], "rows did not read back"
assert all(c[1] in str(r) for c, r in zip(MOD.COMMANDS, back)), "command classes did not read back"
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, PATH, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
