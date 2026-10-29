"""owl-admin step 08: the server-side SaveGames.

    BP_OwlAdminSave    (slot OwlAdmin)          Password: the Owl Admin password
    BP_OwlSettingsSave (slot OwlAdminSettings)  Settings: the admin menu's applied values, one
                                                string per menu_defs.SETTINGS entry, in order
    BP_OwlTransmogSave (slot OwlTransmog_<net id>, one per player)  Look: 5 item row names, one
                                                per transmog slot ("" = worn gear); OutfitNames;
                                                OutfitLooks: 5 row names per outfit, flattened
    BP_OwlCeSave       (slot OwlCe_<net id>, one per player)  Balance: their Owl wallet; Log: the
                                                admin changes made to them, newest last (capped)
    BP_OwlEconomySave  (slot OwlEconomy)        CurOn: 1/0 per menu_defs.CE_CURRENCIES entry,
                                                accepted in trades; SellQ / BuyQ: NPC price
                                                multipliers in quarters (4 = 1.00x). Saved only:
                                                nothing trades with them yet
    BP_OwlBugSave      (slot OwlBugReports)     Reports: "time|player|server|kind|title|where|text",
                                                oldest first (capped at BUG_MAX); Done: 1/0 each
    BP_OwlHudSave      (slot OwlHud)            On: 1/0 per menu_defs.HUD_ITEMS; Text: one string
                                                per text item (menu_defs.HUD_TEXTS)
    BP_OwlRestartSave  (slot OwlRestart)        Vals: the Server Restart tab, one int per
                                                menu_defs.RS_LIMITS entry (daily, time, warnings, sound)
    BP_OwlKitsSave     (slot OwlKits)           Names: one per kit (menu_defs.N_KITS); per kit entry, in
                                                parallel: EKit (which kit), EIds (item template id),
                                                EQty, ENames (the item's name, for the menus)
    BP_OwlKitClaimSave (slot OwlKit_<net id>, one per player)  Last: per kit, the minute (Unix time /
                                                60) the player last claimed it, 0 = never

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
int_t = bel.get_basic_type_by_name("int")

strings_t = bel.get_array_type(string_t)
for name, variables in ((MOD.SAVEGAME, [("Password", string_t, "")]),
                        (MOD.SETTINGS_SAVEGAME, [("Settings", strings_t, [])]),
                        (MOD.TM_SAVEGAME, [("Look", strings_t, []), ("OutfitNames", strings_t, []),
                                           ("OutfitLooks", strings_t, [])]),
                        (MOD.CE_SAVEGAME, [("Balance", int_t, 0), ("Log", strings_t, [])]),
                        (MOD.ECON_SAVEGAME, [("CurOn", bel.get_array_type(int_t), []), ("SellQ", int_t, 0),
                                             ("BuyQ", int_t, 0)]),
                        (MOD.BUG_SAVEGAME, [("Reports", strings_t, []), ("Done", bel.get_array_type(int_t), [])]),
                        (MOD.HUD_SAVEGAME, [("On", bel.get_array_type(int_t), []), ("Text", strings_t, [])]),
                        (MOD.RESTART_SAVEGAME, [("Vals", bel.get_array_type(int_t), [])]),
                        (MOD.KITS_SAVEGAME, [("Names", strings_t, []), ("EKit", bel.get_array_type(int_t), []),
                                             ("EIds", bel.get_array_type(int_t), []),
                                             ("EQty", bel.get_array_type(int_t), []), ("ENames", strings_t, [])]),
                        (MOD.KITCLAIM_SAVEGAME, [("Last", bel.get_array_type(int_t), [])])):
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
