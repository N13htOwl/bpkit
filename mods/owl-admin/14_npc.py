"""owl-admin step 14: BP_OwlNPC, the admins' custom NPC (the NPC editor in 03, the window in 15).

A child of the game's dialogue NPC (BP_HumanoidDialogueNPC), so it has the "Press E to Talk" prompt.
The relay (10, npc_server) spawns one per placed NPC on the server and fills in its replicated
variables; nothing here touches saves or items.

    NpcIdx (-1 = not one of ours: a leftover the relay removes), NpcName, NpcRole, NpcLine,
    NpcWIds / NpcWPrice / NpcWCur (its wares that are on, in order)   -- all replicated

Tick, every machine: the body mesh is shown (spawned without the game's NPC setup it stays
hidden), and the character name follows NpcName (NameShown, this machine's last one). The floating
name's second line, where the game puts a profession ("[Fighter]"), shows "[NpcRole]" instead.
Tick, the server, GEAR_WAIT ticks after spawning: the gear ids the relay left in NpcGear (slot by slot,
0 = empty; not replicated) go into its equipment. Items added in the frame it spawns are kept but never
drawn, so the relay doesn't add them itself; the equipment then replicates like any character's.
E (ClientInteractableActivate, on the player who pressed it): the NPC window UI module opens
(MOD.NPC_MODULE, by name like 04's OwlAdmin); the window finds the nearest Owl NPC itself.
It takes no damage (the CDO's bNoDamage) and has no AI controller, so it stands where placed.

Run with Play STOPPED, after 08:  python ue_run.py mods/owl-admin/14_npc.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
sys.modules.pop("oa_config", None)
import oa_config as MOD
sys.modules.pop("menu_defs", None)
import menu_defs as D

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
FULL = MOD.full(PKG, MOD.NPC_BP)
PARENT = unreal.load_class(None, "/Game/Characters/NPCs/Humanoid/BP_HumanoidDialogueNPC.BP_HumanoidDialogueNPC_C")
assert PARENT, "no BP_HumanoidDialogueNPC in this devkit"
ACTOR = "/Script/Engine.Actor"
IFACE = "/Script/ConanSandbox.InteractableInterface"
CHAR = "/Script/ConanSandbox.ConanCharacter"
SCENE = "/Script/Engine.SceneComponent"
SKEL = "/Script/Engine.SkeletalMeshComponent"
GUIMC = "/Script/ConanSandbox.GUIModuleController"
KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
INV = "/Script/ConanSandbox.ItemInventory"
WIDGETC = "/Script/UMG.WidgetComponent"
USERW = "/Script/UMG.UserWidget"
TEXTB = "/Script/UMG.TextBlock"
TITLE_LINE = "PlayerName"   # W_FloatingName's second line (a GeneralText)
GEAR_WAIT = 30      # ticks after spawning before the gear goes on (items added while the body is hidden aren't drawn)

bel = unreal.BlueprintEditorLibrary
REPL = unreal.BlueprintVariableReplication
bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.NPC_BP, parent=PARENT)
i_t, s_t = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("string")
for var, vtype, repl in (("NpcIdx", i_t, REPL.REPLICATED), ("NpcName", s_t, REPL.REPLICATED),
                         ("NpcRole", s_t, REPL.REPLICATED), ("NpcLine", s_t, REPL.REPLICATED),
                         ("NpcWIds", bel.get_array_type(i_t), REPL.REPLICATED),
                         ("NpcWPrice", bel.get_array_type(i_t), REPL.REPLICATED),
                         ("NpcWCur", bel.get_array_type(i_t), REPL.REPLICATED),
                         ("NameShown", s_t, REPL.NONE),
                         ("NpcGear", bel.get_array_type(i_t), REPL.NONE), ("GearWait", i_t, REPL.NONE)):
    bel.add_member_variable(bp_obj, var, vtype)
    bel.set_blueprint_variable_replication(bp_obj, var, repl)
bel.compile_blueprint(bp_obj)

g = ir.Graph("EventGraph")
# ---- Tick: show the mesh, follow the name
tick = g.event("ReceiveTick", parent=ACTOR, pos=(0, 0))
mesh = g.var_get("Mesh", "object", ir.obj_path(SKEL), pos=(0, 300))
vis = g.call("IsVisible", SCENE, pos=(250, 300))
g.wire(mesh, "Mesh", vis, "self", exec=False)
bVis = g.branch(pos=(300, 0))
g.wire(tick, "then", bVis, "execute")
g.wire(vis, "ReturnValue", bVis, "Condition", exec=False)
show = g.call("SetVisibility", SCENE, pos=(600, 150))
g.wire(mesh, "Mesh", show, "self", exec=False)
g.typed_input(show, "bNewVisibility", "true", "bool")
g.typed_input(show, "bPropagateToChildren", "true", "bool")
g.wire(bVis, "else", show, "execute")
same = g.call("EqualEqual_StrStr", KSTR, pos=(900, 300))
g.wire(g.var_get("NpcName", "string", pos=(700, 300)), "NpcName", same, "A", exec=False)
g.wire(g.var_get("NameShown", "string", pos=(700, 450)), "NameShown", same, "B", exec=False)
bName = g.branch(pos=(900, 0))
g.wire(bVis, "then", bName, "execute")
g.wire(show, "then", bName, "execute")
g.wire(same, "ReturnValue", bName, "Condition", exec=False)
txt = g.call("Conv_StringToText", KTXT, pos=(1200, 300))
g.wire(g.var_get("NpcName", "string", pos=(1000, 450)), "NpcName", txt, "InString", exec=False)
setName = g.call("SetCharacterName", CHAR, pos=(1200, 0))
g.wire(txt, "ReturnValue", setName, "name", exec=False)
g.wire(bName, "else", setName, "execute")
shown = g.var_set("NameShown", "string", pos=(1500, 0))
g.wire(g.var_get("NpcName", "string", pos=(1300, 450)), "NpcName", shown, "NameShown", exec=False)
g.wire(setName, "then", shown, "execute")

# ---- the floating name's second line (the game fills it with a profession, "[Fighter]") follows NpcRole:
# "[role]", or empty with no role. Set again whenever it differs, as the game may write it again.
fname = g.var_get("FloatingName", "object", ir.obj_path(WIDGETC), pos=(1600, 1700))
uw = g.call("GetUserWidgetObject", WIDGETC, pos=(1800, 1500))
g.wire(fname, "FloatingName", uw, "self", exec=False)
line = g.call("GetWidgetFromName", USERW, pos=(2100, 1500))
g.wire(uw, "ReturnValue", line, "self", exec=False)
lname = g.call("MakeLiteralName", KSL, pos=(1900, 1700))   # Name is by-ref: a typed default is refused
g.typed_input(lname, "Value", TITLE_LINE, "name")
g.wire(lname, "ReturnValue", line, "Name", exec=False)
tcast = g.cast(TEXTB, pos=(2400, 1500))
g.wire(line, "ReturnValue", tcast, "Object", exec=False)
uwOk = g.call("IsValid", KSL, pos=(2000, 1700))   # no widget on a dedicated server: skip, no Accessed None
g.wire(uw, "ReturnValue", uwOk, "Object", exec=False)
bUw = g.branch(pos=(2200, 1500))
g.wire(bName, "then", bUw, "execute")
g.wire(shown, "then", bUw, "execute")
g.wire(uwOk, "ReturnValue", bUw, "Condition", exec=False)
g.wire(bUw, "then", tcast, "execute")
cur = g.call("GetText", TEXTB, pos=(2700, 1500))
g.wire(tcast, "AsText", cur, "self", exec=False)
open_ = g.call("Concat_StrStr", KSTR, pos=(2500, 1900))
g.typed_input(open_, "A", "[", "string")
g.wire(g.var_get("NpcRole", "string", pos=(2300, 1950)), "NpcRole", open_, "B", exec=False)
close = g.call("Concat_StrStr", KSTR, pos=(2700, 1900))
g.wire(open_, "ReturnValue", close, "A", exec=False)
g.typed_input(close, "B", "]", "string")
noRole = g.call("IsEmpty", KSTR, pos=(2500, 2100))
g.wire(g.var_get("NpcRole", "string", pos=(2300, 2100)), "NpcRole", noRole, "InString", exec=False)
want = g.call("SelectString", KML, pos=(2900, 1900))   # A when PickA; B (left empty) otherwise
g.wire(close, "ReturnValue", want, "A", exec=False)
hasRole = g.call("Not_PreBool", KML, pos=(2700, 2100))
g.wire(noRole, "ReturnValue", hasRole, "A", exec=False)
g.wire(hasRole, "ReturnValue", want, "bPickA", exec=False)
curS = g.call("Conv_TextToString", KTXT, pos=(2900, 1700))
g.wire(cur, "ReturnValue", curS, "InText", exec=False)
same2 = g.call("EqualEqual_StrStr", KSTR, pos=(3100, 1700))
g.wire(curS, "ReturnValue", same2, "A", exec=False)
g.wire(want, "ReturnValue", same2, "B", exec=False)
bTitle = g.branch(pos=(3000, 1500))
g.wire(tcast, "then", bTitle, "execute")
g.wire(same2, "ReturnValue", bTitle, "Condition", exec=False)
wantT = g.call("Conv_StringToText", KTXT, pos=(3300, 1900))
g.wire(want, "ReturnValue", wantT, "InString", exec=False)
setT = g.call("SetText", TEXTB, pos=(3300, 1500))
g.wire(tcast, "AsText", setT, "self", exec=False)
g.wire(wantT, "ReturnValue", setT, "InText", exec=False)
g.wire(bTitle, "else", setT, "execute")

# ---- the server, GEAR_WAIT ticks after spawning: put on the gear ids the relay left in NpcGear
waiting = g.call("Less_IntInt", KML, pos=(1800, 450))
g.wire(g.var_get("GearWait", "int", pos=(1600, 450)), "GearWait", waiting, "A", exec=False)
g.typed_input(waiting, "B", str(GEAR_WAIT + 1), "int")
auth = g.call("HasAuthority", ACTOR, pos=(1800, 600))
both = g.call("BooleanAND", KML, pos=(2000, 450))
g.wire(waiting, "ReturnValue", both, "A", exec=False)
g.wire(auth, "ReturnValue", both, "B", exec=False)
bWait = g.branch(pos=(1800, 0))
for e in ((bUw, "else"), (tcast, "CastFailed"), (bTitle, "then"), (setT, "then")):
    g.wire(e[0], e[1], bWait, "execute")
g.wire(both, "ReturnValue", bWait, "Condition", exec=False)
inc = g.call("Add_IntInt", KML, pos=(2100, 300))
g.wire(g.var_get("GearWait", "int", pos=(1900, 300)), "GearWait", inc, "A", exec=False)
g.typed_input(inc, "B", "1", "int")
setWait = g.var_set("GearWait", "int", pos=(2100, 0))
g.wire(inc, "ReturnValue", setWait, "GearWait", exec=False)
g.wire(bWait, "then", setWait, "execute")
due = g.call("EqualEqual_IntInt", KML, pos=(2400, 300))
g.wire(g.var_get("GearWait", "int", pos=(2200, 300)), "GearWait", due, "A", exec=False)
g.typed_input(due, "B", str(GEAR_WAIT), "int")
glen = g.array_fn("Array_Length", pos=(2400, 450), elem_cat="int")
g.wire(g.array_var("NpcGear", pos=(2200, 450), elem_cat="int"), "NpcGear", glen, "TargetArray", exec=False)
glen.pin("ReturnValue").typed("int", direction="EGPD_Output")
full = g.call("GreaterEqual_IntInt", KML, pos=(2600, 450))
g.wire(glen, "ReturnValue", full, "A", exec=False)
g.typed_input(full, "B", str(D.NPC_GEAR), "int")
dueFull = g.call("BooleanAND", KML, pos=(2800, 300))
g.wire(due, "ReturnValue", dueFull, "A", exec=False)
g.wire(full, "ReturnValue", dueFull, "B", exec=False)
bDue = g.branch(pos=(2400, 0))
g.wire(setWait, "then", bDue, "execute")
g.wire(dueFull, "ReturnValue", bDue, "Condition", exec=False)
me = g.node("K2Node_Self", [], base="Self", pos=(2500, 900))
me.pin("self").typed("object", direction="EGPD_Output")
inv = g.call("GetInventoryByType", INV, pos=(2700, 750))
g.wire(me, "self", inv, "owner", exec=False)
g.typed_input(inv, "inventoryType", "Equipment", "byte", ir.enum_path("/Script/ConanSandbox.EInventoryType"))
exits = [(bDue, "then")]
for k in range(D.NPC_GEAR):
    x = 2700 + 450 * k
    gid = g.array_get(g.array_var("NpcGear", pos=(x, 1000), elem_cat="int"), "NpcGear", k, pos=(x + 150, 1000), elem_cat="int")
    has = g.call("Greater_IntInt", KML, pos=(x + 150, 1150))
    g.wire(gid, "Output", has, "A", exec=False)
    g.typed_input(has, "B", "0", "int")
    bk = g.branch(pos=(x, 600))
    for e in exits:
        g.wire(e[0], e[1], bk, "execute")
    g.wire(has, "ReturnValue", bk, "Condition", exec=False)
    ad = g.call("AddItemTemplate", INV, pos=(x + 200, 800))
    g.wire(inv, "ReturnValue", ad, "self", exec=False)
    g.wire(gid, "Output", ad, "templateID", exec=False)
    if k:
        g.typed_input(ad, "index", str(k), "int")
    else:   # a typed 0 can come back as 1 (bpkit zero-literal quirk)
        zero = g.call("MakeLiteralInt", KSL, pos=(x + 100, 1300))
        g.typed_input(zero, "Value", "0", "int")
        g.wire(zero, "ReturnValue", ad, "index", exec=False)
    g.typed_input(ad, "context", MOD.CE_CONTEXT, "name")
    g.typed_input(ad, "quantity", "1", "int")
    g.wire(bk, "then", ad, "execute")
    exits = [(bk, "else"), (ad, "then")]

# ---- E on this NPC (the pressing player's client): open the NPC window module
act = g.event("ClientInteractableActivate", parent=IFACE, pos=(0, 1200))
gmc = g.call("GetGUIModuleController", GUIMC, pos=(300, 1450))
gm = g.call("GetModule", GUIMC, pos=(300, 1200))
g.typed_input(gm, "Name", MOD.NPC_MODULE, "name")
g.wire(act, "then", gm, "execute")
g.wire(gmc, "ReturnValue", gm, "self", exec=False)
valid = g.call("IsValid", KSL, pos=(550, 1450))
g.wire(gm, "ReturnValue", valid, "Object", exec=False)
b = g.branch(pos=(600, 1200))
g.wire(gm, "then", b, "execute")
g.wire(valid, "ReturnValue", b, "Condition", exec=False)
load = g.call("LoadModules", GUIMC, pos=(700, 1350))
g.wire(b, "else", load, "execute")
g.wire(gmc, "ReturnValue", load, "self", exec=False)
tgl = g.call("ToggleModule", GUIMC, pos=(1000, 1200))
g.typed_input(tgl, "ModuleName", MOD.NPC_MODULE, "name")
g.wire(b, "then", tgl, "execute")
g.wire(load, "then", tgl, "execute")
g.wire(gmc, "ReturnValue", tgl, "self", exec=False)

_bp, _g = bp.find_graph(FULL, "EventGraph")
bp.clear_graph(_bp, _g)
bel.compile_blueprint(bp_obj)
rep = build.build_graph(FULL, g, verbose=False)
assert rep["ok"], "NPC graph not clean: %r" % {k: rep[k] for k in (
    "dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}
bel.compile_blueprint(bp_obj)

cdo = unreal.get_default_object(unreal.load_object(None, FULL + "_C"))
cdo.set_editor_property("NpcIdx", -1)
cdo.set_editor_property("no_damage", True)
for var in ("NpcIdx", "NpcName", "NpcRole", "NpcLine", "NpcWIds", "NpcWPrice", "NpcWCur", "NameShown", "NpcGear",
            "GearWait"):
    cdo.get_editor_property(var)
assert unreal.EditorAssetLibrary.save_asset("%s/%s" % (PKG, MOD.NPC_BP)), "save failed"
print("CDO: NpcIdx=%s no_damage=%s" % (cdo.get_editor_property("NpcIdx"), cdo.get_editor_property("no_damage")))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
