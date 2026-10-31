"""Builds the shoulder owl (16's Bird) in Blender, from nothing: a stylized tawny owl -- body, head,
heart-shaped facial disc, eyes, beak, talons, wings and tail made of separate feathers -- with a
painted feather texture baked from procedural materials, a small skeleton and three actions:

    Perch  4 s loop: wings folded, the head swivels, the body breathes
    Flap   1 s loop: wings beating (take-off and landing)
    Glide  2 s loop: wings spread, a slow sway (circling)

Blender units are metres; the owl is about 0.3 m tall, facing -Y, up +Z. Writes <out>/SK_OwlPet.fbx
(mesh + skeleton + the three takes, texture embedded) and preview renders <out>/preview_*.png.

    blender --background --factory-startup --python owl_build.py -- <out dir>
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Euler, Matrix, Quaternion, Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
TEX = 2048
SHOULDER = (0.088, 0.01, 0.195)      # wing root, left (+X); the right is mirrored
ELBOW_X, TIP_X = 0.165, 0.32

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ------------------------------------------------------------------ materials (procedural, baked later)
def mat(name, build):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.85
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    col = build(nt)
    nt.links.new(col, bsdf.inputs["Base Color"])
    return m


def rgb(nt, c):
    n = nt.nodes.new("ShaderNodeRGB")
    n.outputs[0].default_value = (*c, 1.0)
    return n.outputs[0]


def mix(nt, a, b, fac):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    nt.links.new(fac, n.inputs["Factor"])
    nt.links.new(a, n.inputs["A"])
    nt.links.new(b, n.inputs["B"])
    return n.outputs["Result"]


def ramp(nt, fac, lo, hi):
    """fac squeezed to 0..1 between lo and hi."""
    n = nt.nodes.new("ShaderNodeMapRange")
    n.inputs["From Min"].default_value, n.inputs["From Max"].default_value = lo, hi
    n.clamp = True
    nt.links.new(fac, n.inputs["Value"])
    return n.outputs["Result"]


def coords(nt):
    return nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]


def noise(nt, vec, scale, detail=6.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value, n.inputs["Detail"].default_value = scale, detail
    nt.links.new(vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def wave(nt, vec, scale, kind="BANDS", direction="Z", distortion=4.0):
    n = nt.nodes.new("ShaderNodeTexWave")
    n.wave_type = kind
    if kind == "BANDS":
        n.bands_direction = direction
    else:
        n.rings_direction = "SPHERICAL"
    n.inputs["Scale"].default_value, n.inputs["Distortion"].default_value = scale, distortion
    nt.links.new(vec, n.inputs["Vector"])
    return n.outputs["Fac"]


BROWN, DARK, CREAM, RUFOUS = (0.30, 0.17, 0.08), (0.09, 0.05, 0.03), (0.78, 0.64, 0.45), (0.50, 0.30, 0.14)


def body_col(nt):
    co = coords(nt)
    base = mix(nt, rgb(nt, BROWN), rgb(nt, RUFOUS), noise(nt, co, 9.0))
    pale = mix(nt, base, rgb(nt, CREAM), ramp(nt, noise(nt, co, 22.0), 0.45, 0.62))     # feather edges
    streak = ramp(nt, wave(nt, co, 34.0, direction="X", distortion=3.0), 0.86, 0.98)    # thin dark shaft streaks
    return mix(nt, pale, rgb(nt, DARK), streak)


def disc_col(nt):
    co = coords(nt)
    rings = ramp(nt, wave(nt, co, 70.0, kind="RINGS", distortion=3.0), 0.7, 1.0)
    return mix(nt, rgb(nt, (0.72, 0.57, 0.40)), rgb(nt, (0.58, 0.42, 0.26)), rings)


def wing_col(nt):
    co = coords(nt)
    base = mix(nt, rgb(nt, BROWN), rgb(nt, RUFOUS), noise(nt, co, 12.0))
    bars = ramp(nt, wave(nt, co, 32.0, direction="X", distortion=1.0), 0.6, 0.9)          # light bars across feathers
    return mix(nt, base, rgb(nt, CREAM), bars)


M_BODY = mat("Body", body_col)
M_DISC = mat("Disc", disc_col)
M_RIM = mat("Rim", lambda nt: rgb(nt, (0.16, 0.09, 0.05)))
M_WING = mat("Wing", wing_col)
M_EYE = mat("Eye", lambda nt: rgb(nt, (0.015, 0.012, 0.01)))
M_BEAK = mat("Beak", lambda nt: rgb(nt, (0.72, 0.66, 0.48)))
M_CLAW = mat("Claw", lambda nt: rgb(nt, (0.10, 0.09, 0.08)))


# ------------------------------------------------------------------ geometry
parts = []          # (object, bone weights: callable(world co) -> {bone: w})


def sphere(name, loc, scale, m, seg=32, rings=16, weights=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=1.0, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name, o.scale = name, scale
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    parts.append((o, weights))
    return o


def cone(name, loc, rot, r, depth, m, weights=None):
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=r, radius2=0.0005, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    parts.append((o, weights))
    return o


def feather(name, root, direction, length, width, m, weights, thick=0.006, curl=0.0):
    """A feather: a flattened ellipsoid from root along direction (x, y, z), lying flat (normal ~Z)."""
    d = Vector(direction).normalized()
    centre = Vector(root) + d * (length / 2)
    rot = Vector((1, 0, 0)).rotation_difference(d).to_euler()
    rot.rotate_axis("X", curl)
    return sphere(name, centre, (length / 2, width / 2, thick), m, seg=16, rings=8, weights=weights, rot=rot)


def only(bone):
    return lambda co: {bone: 1.0}


def taper_body(o):
    """Narrower at the bottom and the back: an owl's pear shape."""
    for v in o.data.vertices:
        if v.co.z < 0:
            k = 1.0 + 0.25 * v.co.z            # z -1 -> 0.75
            v.co.x *= k
            v.co.y *= k


body = sphere("Body", (0, 0, 0.125), (0.10, 0.09, 0.13), M_BODY, weights=only("body"))
taper_body(body)
belly = sphere("Belly", (0, -0.035, 0.11), (0.085, 0.06, 0.11), M_BODY, weights=only("body"))
head = sphere("Head", (0, -0.005, 0.262), (0.088, 0.083, 0.078), M_BODY, weights=only("head"))
for s in (-1, 1):                                       # the heart-shaped facial disc: two lobes and a rim
    sphere("Disc", (0.03 * s, -0.062, 0.262), (0.042, 0.026, 0.055), M_DISC, weights=only("head"))
    sphere("Rim", (0.034 * s, -0.056, 0.262), (0.05, 0.022, 0.063), M_RIM, weights=only("head"))
    sphere("Eye", (0.031 * s, -0.086, 0.27), (0.018, 0.012, 0.018), M_EYE, seg=16, rings=8, weights=only("head"))
cone("Beak", (0, -0.093, 0.245), (math.radians(110), 0, 0), 0.011, 0.032, M_BEAK, weights=only("head"))
for s in (-1, 1):                                       # talons
    for k, a in enumerate((-25, 0, 25)):
        cone("Talon", (0.03 * s + 0.012 * math.sin(math.radians(a)), -0.045 - 0.01 * math.cos(math.radians(a)), 0.004),
             (math.radians(80), 0, math.radians(a)), 0.006, 0.03, M_CLAW, weights=only("body"))
for k in range(5):                                      # tail: a fan pointing back and down
    a = math.radians(-24 + 12 * k)
    feather("Tail", (0.0, 0.07, 0.045), (math.sin(a), math.cos(a), -0.45), 0.11, 0.03, M_WING, only("tail"))


def wing_weights(sign):
    up, fore = ("wing_upper.L", "wing_fore.L") if sign > 0 else ("wing_upper.R", "wing_fore.R")

    def w(co):
        t = min(1.0, max(0.0, (abs(co.x) - (ELBOW_X - 0.03)) / 0.06))
        return {up: 1.0 - t, fore: t}
    return w


for s in (-1, 1):                                       # wings, modelled spread (the skeleton folds them)
    root = Vector((SHOULDER[0] * s, SHOULDER[1], SHOULDER[2]))
    ww = wing_weights(s)
    sphere("Covert", root + Vector((0.085 * s, 0.02, 0)), (0.095, 0.055, 0.012), M_WING, weights=ww)
    for k in range(6):                                  # secondaries: along the trailing edge, pointing back
        x = 0.03 + 0.025 * k
        feather("Secondary", (root.x + x * s, root.y + 0.03, root.z), (0.12 * s, 1.0, -0.05), 0.085, 0.028, M_WING, ww)
    for k in range(6):                                  # primaries: fanned from the hand
        a = math.radians(5 + 9 * k)
        feather("Primary", (root.x + (0.13 + 0.008 * k) * s, root.y + 0.01 * k, root.z),
                (math.cos(a) * s, math.sin(a), 0.0), 0.15 - 0.008 * k, 0.03, M_WING, ww)

# one object, with the weights written per part
bpy.ops.object.select_all(action="DESELECT")
groups = ["root", "body", "head", "tail", "wing_upper.L", "wing_fore.L", "wing_upper.R", "wing_fore.R"]
for o, wfn in parts:
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for gname in groups:
        o.vertex_groups.new(name=gname)
    for v in o.data.vertices:
        for gname, w in (wfn(v.co) if wfn else {"body": 1.0}).items():
            if w > 0:
                o.vertex_groups[gname].add([v.index], w, "REPLACE")
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()
owl = bpy.context.active_object
owl.name = "OwlPet"

# ------------------------------------------------------------------ bake one texture
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
bpy.ops.object.mode_set(mode="OBJECT")
img = bpy.data.images.new("T_OwlPet", TEX, TEX)
for m in owl.data.materials:
    n = m.node_tree.nodes.new("ShaderNodeTexImage")
    n.image = img
    m.node_tree.nodes.active = n
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 4
bake = scene.render.bake
bake.use_pass_direct = bake.use_pass_indirect = False
bake.use_pass_color = True
bake.margin = 8
owl.select_set(True)
bpy.context.view_layer.objects.active = owl
bpy.ops.object.bake(type="DIFFUSE")
img.filepath_raw = os.path.join(OUT, "T_OwlPet.png")
img.file_format = "PNG"
img.save()
# swap to one material using the baked texture
final = bpy.data.materials.new("M_OwlPet")
final.use_nodes = True
bsdf = final.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.8
tex = final.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = img
final.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
owl.data.materials.clear()
owl.data.materials.append(final)

# ------------------------------------------------------------------ skeleton
arm_data = bpy.data.armatures.new("OwlRig")
rig = bpy.data.objects.new("OwlRig", arm_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones


def bone(name, head, tail, parent=None):
    b = eb.new(name)
    b.head, b.tail = Vector(head), Vector(tail)
    b.roll = 0.0
    if parent:
        b.parent = eb[parent]
    return b


bone("root", (0, 0, 0), (0, 0.05, 0))
bone("body", (0, 0, 0.06), (0, 0, 0.2), "root")
bone("head", (0, 0, 0.215), (0, 0, 0.32), "body")
bone("tail", (0, 0.06, 0.07), (0, 0.15, 0.03), "body")
for s, side in ((1, "L"), (-1, "R")):
    bone("wing_upper." + side, (SHOULDER[0] * s, SHOULDER[1], SHOULDER[2]), (ELBOW_X * s, SHOULDER[1], SHOULDER[2]), "body")
    bone("wing_fore." + side, (ELBOW_X * s, SHOULDER[1], SHOULDER[2]), (TIP_X * s, SHOULDER[1], SHOULDER[2]),
         "wing_upper." + side)
bpy.ops.object.mode_set(mode="OBJECT")
owl.parent = rig
mod = owl.modifiers.new("Armature", "ARMATURE")
mod.object = rig


# ------------------------------------------------------------------ poses and actions
def world_rot(pb, euler_deg):
    """Pose pb by a rotation given in the rest (world) frame, as a local quaternion."""
    m = pb.bone.matrix_local.to_quaternion()
    r = Euler([math.radians(a) for a in euler_deg], "XYZ").to_quaternion()
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = m.inverted() @ r @ m


def wings(rig, up_deg, sweep_deg, fold_deg, fore_up=0.0):
    """Both wings: up_deg raises the upper wing (+) or droops it (-), sweep_deg swings it back,
    fold_deg folds the forearm back along it."""
    for s, side in ((1, "L"), (-1, "R")):
        world_rot(rig.pose.bones["wing_upper." + side], (0, -up_deg * s, sweep_deg * s))
        world_rot(rig.pose.bones["wing_fore." + side], (0, -fore_up * s, fold_deg * s))


FOLD = dict(up_deg=-70, sweep_deg=85, fold_deg=60)       # picked from rendered tries


def key_all(rig, frame):
    for pb in rig.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=frame)
        pb.keyframe_insert("location", frame=frame)
        pb.keyframe_insert("scale", frame=frame)


def reset(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
        pb.scale = Vector((1, 1, 1))


def action(name, frames, pose_at):
    rig.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data.action = act
    for f in frames:
        reset(rig)
        pose_at(f)
        key_all(rig, f)
    for fc in getattr(act, "fcurves", []):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    return act


FPS = 30
scene.render.fps = FPS


def perch(f):
    wings(rig, **FOLD)
    t = f / (4 * FPS)
    turn = 55 * math.sin(2 * math.pi * t) if 0.15 < t < 0.85 else 0.0      # look round, then back
    world_rot(rig.pose.bones["head"], (0, 0, turn))
    rig.pose.bones["body"].scale = Vector((1, 1, 1)) * (1 + 0.015 * math.sin(4 * math.pi * t))


def flap(f):
    t = f / FPS
    up = 40 * math.cos(2 * math.pi * t)
    wings(rig, up_deg=up, sweep_deg=0, fold_deg=-12 * math.cos(2 * math.pi * t + 0.6), fore_up=8 * math.cos(2 * math.pi * t + 0.6))
    world_rot(rig.pose.bones["tail"], (-15, 0, 0))


def glide(f):
    t = f / (2 * FPS)
    wings(rig, up_deg=6 + 3 * math.sin(2 * math.pi * t), sweep_deg=-4, fold_deg=-6)
    world_rot(rig.pose.bones["tail"], (-10, 0, 3 * math.sin(2 * math.pi * t)))


acts = [action("Perch", range(0, 4 * FPS + 1, 6), perch),
        action("Flap", range(0, FPS + 1, 3), flap),
        action("Glide", range(0, 2 * FPS + 1, 10), glide)]


# ------------------------------------------------------------------ previews
def preview(act_name, frame, path):
    rig.animation_data.action = bpy.data.actions[act_name]
    scene.frame_set(frame)
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {e.identifier for e in
        bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 900, 900
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 3.5
fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "SUN"))
fill.data.energy = 1.5
fill.rotation_euler = Euler((math.radians(60), 0, math.radians(150)))
scene.collection.objects.link(fill)
sun.rotation_euler = Euler((math.radians(50), 0, math.radians(-30)))
scene.collection.objects.link(sun)
world = bpy.data.worlds.new("W")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.07, 0.12, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
scene.world = world
for name, frame, loc in (("Perch", 0, (0.35, -0.75, 0.32)), ("Glide", 0, (0.0, -0.9, 0.55)), ("Flap", 15, (0.6, -0.8, 0.35)),
                        ("PerchBack", 0, (-0.45, 0.7, 0.4))):
    cam.location = loc
    cam.rotation_euler = (Vector((0, 0, 0.17)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    preview(name.replace("Back", ""), frame, os.path.join(OUT, "preview_%s.png" % name.lower()))

# ------------------------------------------------------------------ export
rig.animation_data.action = acts[0]
bpy.ops.object.select_all(action="DESELECT")
owl.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.fbx(
    filepath=os.path.join(OUT, "SK_OwlPet.fbx"), use_selection=True, object_types={"ARMATURE", "MESH"},
    apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", add_leaf_bones=False,
    bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
    path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "owl.blend"))
print("OWL OK: %d verts, %d actions -> %s" % (len(owl.data.vertices), len(acts), OUT))
