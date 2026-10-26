"""owl-admin step 08: the server-side SaveGames.

    BP_OwlAdminSave    (slot OwlAdmin)          Password: the Owl Admin password
    BP_OwlSettingsSave (slot OwlAdminSettings)  Settings: the admin menu's applied values, one
                                                string per menu_defs.SETTINGS entry, in order
    BP_OwlTransmogSave (slot OwlTransmog_<net id>, one per player)  Look: 5 item row names, one
                                                per transmog slot ("" = worn gear); OutfitNames;
                                                OutfitLooks: 5 row names per outfit, flattened

Password: written by `dc OwlSetPassword <password>` (Conan admins only) and read by
`dc OwlLogin`. Settings: written by `dc OwlApply ...` (the menu's APPLY) and read by the
controller (02) at BeginPlay. All of these run ON THE SERVER, so the .sav files
(Saved/SaveGames/) only ever exist on the server and the password never reaches a client.
The password is plain text in that server file -- there is no hashing function available to
a content-only mod. Separate slots, so saving one never overwrites the other.

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
bel = unreal.BlueprintEditorLibrary
string_t = bel.get_basic_type_by_name("string")

strings_t = bel.get_array_type(string_t)
for name, variables in ((MOD.SAVEGAME, [("Password", string_t, "")]),
                        (MOD.SETTINGS_SAVEGAME, [("Settings", strings_t, [])]),
                        (MOD.TM_SAVEGAME, [("Look", strings_t, []), ("OutfitNames", strings_t, []),
                                           ("OutfitLooks", strings_t, [])])):
    bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=name, parent=unreal.SaveGame)
    for var, vtype, _empty in variables:
        bel.add_member_variable(bp_obj, var, vtype)                    # no-op if present
        bel.set_blueprint_variable_instance_editable(bp_obj, var, True)   # set on a CreateSaveGameObject instance
    bel.compile_blueprint(bp_obj)
    assert unreal.EditorAssetLibrary.save_asset("%s/%s" % (PKG, name)), "save failed: " + name
    gen = unreal.load_object(None, MOD.full(PKG, name) + "_C")
    obj = unreal.GameplayStatics.create_save_game_object(gen) if gen else None
    for var, _vtype, empty in variables:
        value = obj.get_editor_property(var) if obj else None
        assert value is not None and (list(value) if isinstance(empty, list) else value) == empty, \
            "not a usable SaveGame class: %s.%s" % (name, var)
    print("BUILD OK: owl-admin v%d -> %s%s" % (
        MOD.VERSION, MOD.full(PKG, name), "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
