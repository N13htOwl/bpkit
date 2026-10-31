"""owl-admin step 16: BP_OwlPet, the shoulder owl an admin in admin mode gets (the relay, 10 /
owl_server, spawns one per unlocked admin and removes it when they lock).

The owl model is made in Blender by art/owl_build.py (art/out/SK_OwlPet.fbx: mesh, skeleton,
texture and the takes Perch / Flap / Glide); this imports it into <pkg>/Owl first. An Actor with
one mesh, Bird, playing Perch while sitting, Flap while taking off or landing and Glide while
circling (AnimNow, this machine's). Replicated variables, set by the server:

    Admin  -- the admin's character it belongs to (none: hidden)
    FlyAt  -- server time its next flight starts

Tick, every machine (after the characters animate, so it doesn't lag the shoulder): with t = server
time - FlyAt and e = clamp(min(t, FLY - t) / EASE, 0, 1) eased, it stands at
    lerp(shoulder, orbit(t), e)  facing  lerp(the admin's facing, along the orbit and banked, e)
where shoulder = the admin's b_R_clavicle bone + PERCH (up and out) and orbit(t) = a circle of
RADIUS around the admin, HEIGHT up, LAPS times round in FLY seconds. e is 0 outside a flight, so
it simply sits; take-off and landing are the EASE seconds at either end. Everyone computes the
same path from the replicated FlyAt and the server's clock, so no movement is replicated.
The server, once a flight is over: FlyAt = now + a random REST.

Run with Play STOPPED:  python ue_run.py mods/owl-admin/16_owl_pet.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "ce_panel"):
    sys.modules.pop(_m, None)
import oa_config as MOD
from ce_panel import _Ctx

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
FULL = MOD.full(PKG, MOD.PET_BP)
ACTOR = "/Script/Engine.Actor"
CHAR = "/Script/Engine.Character"
SCENE = "/Script/Engine.SceneComponent"
SKEL = "/Script/Engine.SkeletalMeshComponent"
GS = "/Script/Engine.GameplayStatics"
GSB = "/Script/Engine.GameStateBase"
KML = "/Script/Engine.KismetMathLibrary"

OWL_FBX = os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin", "art", "out", "SK_OwlPet.fbx")   # art/owl_build.py
OWL_DIR = PKG + "/Owl"
ANIMS = ("Perch", "Flap", "Glide")    # AnimNow 0, 1, 2: sitting, take-off / landing, circling
BIRD_SCALE = 0.8                      # the model is ~33 cm tall
BIRD_YAW = -90.0                      # the model faces +Y once imported; the actor faces +X
SHOULDER = "b_R_clavicle"
PERCH_UP, PERCH_OUT = 2.0, 17.0       # cm above the bone, and out to the side (on the shoulder, clear of the head)
FLY, EASE, LAPS = 14.0, 2.0, 2        # seconds aloft, seconds of take-off / landing, times round
RADIUS, HEIGHT, BOB = 350.0, 220.0, 30.0
BANK = 25.0                           # degrees of roll while circling
REST = (25.0, 60.0)                   # seconds perched between flights

bel = unreal.BlueprintEditorLibrary
REPL = unreal.BlueprintVariableReplication
eal = unreal.EditorAssetLibrary


# ---- the owl model: SK_OwlPet.fbx (mesh, skeleton, texture, the three takes) into OWL_DIR
def import_owl():
    assert os.path.isfile(OWL_FBX), "no owl model: run art/owl_build.py in Blender first (%s)" % OWL_FBX
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    ui.set_editor_property("import_animations", True)
    ui.set_editor_property("import_materials", True)
    ui.set_editor_property("import_textures", True)
    ui.set_editor_property("create_physics_asset", False)
    task = unreal.AssetImportTask()
    for k, v in (("filename", OWL_FBX), ("destination_path", OWL_DIR), ("destination_name", "SK_OwlPet"),
                 ("replace_existing", True), ("automated", True), ("save", True), ("options", ui)):
        task.set_editor_property(k, v)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh, anims = None, {}
    for path in eal.list_assets(OWL_DIR, recursive=True):
        a = eal.load_asset(path)
        if isinstance(a, unreal.SkeletalMesh):
            mesh = a
        elif isinstance(a, unreal.AnimSequence):
            for name in ANIMS:
                if path.split(".")[-1].endswith(name):
                    anims[name] = a
    assert mesh and len(anims) == len(ANIMS), "owl import incomplete: mesh %s, anims %s (in %s: %s)" % (
        mesh, sorted(anims), OWL_DIR, eal.list_assets(OWL_DIR, recursive=True))
    return mesh, anims


OWL_MESH, OWL_ANIMS = import_owl()
print("owl: %s, %s" % (OWL_MESH.get_path_name(), {k: v.get_path_name() for k, v in OWL_ANIMS.items()}))
bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.PET_BP, parent=unreal.Actor)

# ---- the mesh component (Bird), the root
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
handles = sds.k2_gather_subobject_data_for_blueprint(bp_obj)
names = {str(SDL.get_variable_name(SDL.get_data(hd))): hd for hd in handles}
if "Bird" not in names:
    hd, fail = sds.add_new_subobject(unreal.AddNewSubobjectParams(
        parent_handle=handles[0], new_class=unreal.SkeletalMeshComponent, blueprint_context=bp_obj))
    assert not str(fail), "could not add the Bird component: %s" % fail
    sds.rename_subobject(hd, "Bird")
    names["Bird"] = hd
bird = SDL.get_object(SDL.get_data(names["Bird"]))
bird.set_editor_property("skeletal_mesh_asset", OWL_MESH)
bird.set_editor_property("relative_scale3d", unreal.Vector(BIRD_SCALE, BIRD_SCALE, BIRD_SCALE))
bird.set_editor_property("relative_rotation", unreal.Rotator(0.0, 0.0, BIRD_YAW))
bird.set_collision_profile_name("NoCollision")
# animate even when the engine doesn't count it as rendered (perched close to the camera it didn't)
bird.set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE)
bird.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
bird.set_editor_property("animation_data", unreal.SingleAnimationPlayData(
    anim_to_play=OWL_ANIMS["Perch"], saved_looping=True, saved_playing=True))
for var, vtype, repl in (("Admin", bel.get_object_reference_type(unreal.Character), REPL.REPLICATED),
                         ("FlyAt", bel.get_basic_type_by_name("real"), REPL.REPLICATED),
                         ("AnimNow", bel.get_basic_type_by_name("int"), REPL.NONE)):
    bel.add_member_variable(bp_obj, var, vtype)
    bel.set_blueprint_variable_replication(bp_obj, var, repl)
bel.compile_blueprint(bp_obj)

# ---- graph
g = ir.Graph("EventGraph")
c = _Ctx(g, None, None, None)
real = lambda v: (repr(float(v)), "real")
fm = lambda fn, a, b, pos: c.fn(fn, KML, {"A": a if isinstance(a, tuple) else real(a),
                                          "B": b if isinstance(b, tuple) else real(b)}, pos)
admin = lambda pos: c.var("Admin", "object", pos, sub=ir.obj_path(CHAR))

tick = g.event("ReceiveTick", parent=ACTOR, pos=(0, 0))
c.exits = [(tick, "then")]
ok = c.fn("IsValid", "/Script/Engine.KismetSystemLibrary", {"Object": admin((0, 300))}, (200, 300))
hid = g.call("SetActorHiddenInGame", ACTOR, pos=(300, 0))
nv = c.fn("Not_PreBool", KML, {"A": ok}, (300, 300))
g.wire(nv[0], nv[1], hid, "bNewHidden", exec=False)
c.go(hid)
bOk = c.branch(ok, (600, 0))
c.exits = [(bOk, "then")]

# server time, and t into the flight
gst = g.call("GetGameState", GS, pos=(700, 600))
now = c.fn("GetServerWorldTimeSeconds", GSB, {"self": (gst, "ReturnValue")}, (900, 600))
t = fm("Subtract_DoubleDouble", now, c.var("FlyAt", "real", (900, 750)), (1100, 600))

# the server: a flight is over -> the next one
auth = g.call("HasAuthority", ACTOR, pos=(1100, 900))
over = c.fn("BooleanAND", KML, {"A": (auth, "ReturnValue"), "B": fm("Greater_DoubleDouble", t, FLY, (1300, 750))},
            (1500, 800))
bOver = c.branch(over, (1300, 0))
c.exits = [(bOver, "then")]
rest = c.fn("RandomFloatInRange", KML, {"Min": real(REST[0]), "Max": real(REST[1])}, (1500, 1000))
c.set_var("FlyAt", "real", fm("Add_DoubleDouble", now, rest, (1700, 1000)), (1700, 0))
c.exits += [(bOver, "else")]

# e: 0 perched, 1 aloft, eased between
x = 2100
edge = c.fn("FMin", KML, {"A": t, "B": fm("Subtract_DoubleDouble", FLY, t, (x, 750))}, (x + 200, 600))
a = c.fn("FClamp", KML, {"Value": fm("Divide_DoubleDouble", edge, EASE, (x + 400, 600)), "Min": real(0), "Max": real(1)},
         (x + 600, 600))
e = fm("Multiply_DoubleDouble", fm("Multiply_DoubleDouble", a, a, (x + 800, 750)),
       fm("Subtract_DoubleDouble", 3.0, fm("Multiply_DoubleDouble", 2.0, a, (x + 800, 900)), (x + 1000, 900)), (x + 1200, 750))

# the shoulder: the bone, up and out
x = 2100
mesh = g.var_get("Mesh", "object", ir.obj_path(SKEL), parent=CHAR, pos=(x, 1300))
g.wire(*admin((x - 200, 1300)), mesh, "self", exec=False)
bone = g.call("GetSocketLocation", SCENE, pos=(x + 200, 1300))
g.wire(mesh, "Mesh", bone, "self", exec=False)
g.typed_input(bone, "InSocketName", SHOULDER, "name")
right = c.fn("GetActorRightVector", ACTOR, {"self": admin((x, 1500))}, (x + 200, 1500))
out = c.fn("Multiply_VectorFloat", KML, {"A": right, "B": real(PERCH_OUT)}, (x + 400, 1500))
up = c.fn("MakeVector", KML, {"X": real(0), "Y": real(0), "Z": real(PERCH_UP)}, (x + 400, 1650))
shoulder = c.fn("Add_VectorVector", KML, {"A": c.fn("Add_VectorVector", KML, {"A": (bone, "ReturnValue"), "B": out},
                                                    (x + 600, 1400)), "B": up}, (x + 800, 1400))
yaw = c.fn("BreakRotator", KML, {"InRot": c.fn("K2_GetActorRotation", ACTOR, {"self": admin((x, 1800))}, (x + 200, 1800))},
           (x + 400, 1800), out="Yaw")
perch_rot = c.fn("MakeRotator", KML, {"Roll": real(0), "Pitch": real(0), "Yaw": yaw}, (x + 600, 1800))

# the orbit
x = 3300
ang = fm("Multiply_DoubleDouble", fm("Divide_DoubleDouble", t, FLY, (x, 2100)), 360.0 * LAPS, (x + 200, 2100))
bob = fm("Multiply_DoubleDouble", c.fn("DegSin", KML, {"A": fm("Multiply_DoubleDouble", ang, 1.5, (x + 200, 2400))},
                                       (x + 400, 2400)), BOB, (x + 600, 2400))
ring = c.fn("MakeVector", KML, {
    "X": fm("Multiply_DoubleDouble", c.fn("DegCos", KML, {"A": ang}, (x + 400, 2100)), RADIUS, (x + 600, 2100)),
    "Y": fm("Multiply_DoubleDouble", c.fn("DegSin", KML, {"A": ang}, (x + 400, 2250)), RADIUS, (x + 600, 2250)),
    "Z": fm("Add_DoubleDouble", bob, HEIGHT, (x + 800, 2400))}, (x + 900, 2100))
orbit = c.fn("Add_VectorVector", KML, {"A": c.fn("K2_GetActorLocation", ACTOR, {"self": admin((x + 900, 1950))},
                                                 (x + 1100, 1950)), "B": ring}, (x + 1300, 2000))
fly_rot = c.fn("MakeRotator", KML, {"Roll": real(-BANK), "Pitch": real(0),
                                    "Yaw": fm("Add_DoubleDouble", ang, 90.0, (x + 400, 2600))}, (x + 600, 2600))

# where it is, and which way it faces
x = 4800
pos_ = c.fn("VLerp", KML, {"A": shoulder, "B": orbit, "Alpha": e}, (x, 1500))
rot = c.fn("RLerp", KML, {"A": perch_rot, "B": fly_rot, "Alpha": e, "bShortestPath": ("true", "bool")}, (x, 1800))
mv = g.call("K2_SetActorLocationAndRotation", ACTOR, pos=(x + 300, 0))
g.wire(pos_[0], pos_[1], mv, "NewLocation", exec=False)
g.wire(rot[0], rot[1], mv, "NewRotation", exec=False)
g.typed_input(mv, "bTeleport", "true", "bool")
c.go(mv)

# which take: Perch sitting, Flap taking off or landing, Glide circling -- played when it changes
x = 5400
aloft = fm("Greater_DoubleDouble", e, 0.001, (x, 600))
full = fm("GreaterEqual_DoubleDouble", e, 0.999, (x, 750))
mid = c.fn("SelectInt", KML, {"A": ("1", "int"), "B": ("0", "int"), "bPickA": aloft}, (x + 200, 600))
want = c.fn("SelectInt", KML, {"A": ("2", "int"), "B": mid, "bPickA": full}, (x + 400, 600))
bNew = c.branch(c.fn("NotEqual_IntInt", KML, {"A": want, "B": c.var("AnimNow", "int", (x + 400, 900))}, (x + 600, 750)),
                (x + 600, 0))
c.exits = [(bNew, "then")]
c.set_var("AnimNow", "int", want, (x + 900, 0))
for k, name in enumerate(ANIMS):          # an exec pin leads to one node: test 0, else 1, else 2
    bk = c.branch(c.fn("EqualEqual_IntInt", KML, {"A": want, "B": (str(k), "int")}, (x + 1200 + 600 * k, 450)),
                  (x + 1200 + 600 * k, 0))
    play = g.call("PlayAnimation", SKEL, pos=(x + 1500 + 600 * k, 200))
    g.wire(*c.var("Bird", "object", (x + 1300 + 600 * k, 400), sub=ir.obj_path(SKEL)), play, "self", exec=False)
    # quoted, as 10's SpawnActor class: an unquoted DefaultObject is dropped on paste (the owl played nothing)
    play.pin("NewAnimToPlay").typed("object", ir.obj_path("/Script/Engine.AnimationAsset"),
                                    direction="EGPD_Input").set("DefaultObject", '"%s"' % OWL_ANIMS[name].get_path_name())
    g.typed_input(play, "bLooping", "true", "bool")
    g.wire(bk, "then", play, "execute")
    c.exits = [(bk, "else")]

_bp, _g = bp.find_graph(FULL, "EventGraph")
bp.clear_graph(_bp, _g)
bel.compile_blueprint(bp_obj)
rep = build.build_graph(FULL, g, verbose=False)
assert rep["ok"], "owl pet graph not clean: %r" % {k: rep[k] for k in (
    "dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}
bel.compile_blueprint(bp_obj)
_plays = [b for b in bp.export_nodes(bp.graph_nodes(_g)).split("Begin Object Class=") if 'MemberName="PlayAnimation"' in b]
_set = [b for b in _plays if OWL_DIR + "/" in b]
assert len(_plays) == len(ANIMS) and len(_set) == len(ANIMS), \
    "PlayAnimation lost its animation on paste: %d of %d set" % (len(_set), len(_plays))

cdo = unreal.get_default_object(unreal.load_object(None, FULL + "_C"))
cdo.set_editor_property("replicates", True)
cdo.set_editor_property("replicate_movement", False)
cdo.set_editor_property("AnimNow", -1)      # -1: the first tick plays Perch (the component's own start anim isn't applied)
tick_fn = cdo.get_editor_property("primary_actor_tick")
tick_fn.set_editor_property("tick_group", unreal.TickingGroup.TG_POST_UPDATE_WORK)
cdo.set_editor_property("primary_actor_tick", tick_fn)
assert unreal.EditorAssetLibrary.save_asset("%s/%s" % (PKG, MOD.PET_BP)), "save failed"
print("CDO: replicates=%s tick_group=%s" % (cdo.get_editor_property("replicates"),
                                           cdo.get_editor_property("primary_actor_tick").get_editor_property("tick_group")))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
