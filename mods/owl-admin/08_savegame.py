"""owl-admin step 08: BP_OwlAdminSave : SaveGame -- holds the Owl Admin password.

Written by `dc OwlSetPassword <password>` (Conan admins only) and read by `dc OwlLogin`; both
run ON THE SERVER, so the .sav (Saved/SaveGames/OwlAdmin.sav) only ever exists on the server
and the password never reaches a client. Stored as plain text in that server file -- there
is no hashing function available to a content-only mod.

Run with Play STOPPED:  python ue_run.py mods/owl-admin/08_savegame.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
sys.modules.pop("oa_config", None)
import oa_config as MOD

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.SAVEGAME)
FULL = MOD.full(PKG, MOD.SAVEGAME)
bel = unreal.BlueprintEditorLibrary

bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.SAVEGAME, parent=unreal.SaveGame)
bel.add_member_variable(bp_obj, "Password", bel.get_basic_type_by_name("string"))   # no-op if present
bel.set_blueprint_variable_instance_editable(bp_obj, "Password", True)   # set on a CreateSaveGameObject instance
bel.compile_blueprint(bp_obj)
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"

gen = unreal.load_object(None, FULL + "_C")
obj = unreal.GameplayStatics.create_save_game_object(gen) if gen else None
assert obj and obj.get_editor_property("Password") == "", "not a usable SaveGame class"
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
