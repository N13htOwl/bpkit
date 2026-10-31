"""The shoulder owl, the server side: the relay's (10) step that gives its owner a BP_OwlPet (16)
while they are in admin mode, and takes it away when they lock.

    tick(R, prevs, ctl, y0)   server, every OWL_CHECK ticks (SvOwlCount): wanted = the owner is in
                              the controller's UnlockedPlayers and has a character.
                              wanted, no owl   -> spawn one at the character, FlyAt = now + OWL_FIRST
                              wanted           -> Admin = the character (new owl, or a respawn)
                              not wanted, owl  -> destroyed
    variables(...)            SvOwlPet (the owl), SvOwlCount -- the relay's own, not replicated

The owl does the rest itself (16: perched on the right shoulder, flights from its replicated FlyAt);
it hides itself while it has no Admin.
"""
from bpkit import ir
from ce_server import helpers, T, KML, GS, PSTATE
from ce_panel import _Ctx

ACTOR = "/Script/Engine.Actor"
CTRL = "/Script/Engine.Controller"
CHARACTER = "/Script/Engine.Character"
KSL = "/Script/Engine.KismetSystemLibrary"
GSB = "/Script/Engine.GameStateBase"
OWL_CHECK = 30          # ticks between checks (GetActorOfClass walks the actors)
OWL_FIRST = 8.0         # seconds after appearing before its first flight


def variables(unreal, bel, pet_cls):
    return [("SvOwlPet", bel.get_object_reference_type(pet_cls)), ("SvOwlCount", bel.get_basic_type_by_name("int"))]


def _admin(g, pet, PET, pos):
    n = g.var_get("Admin", "object", ir.obj_path(CHARACTER), parent=PET, pos=pos)
    g.wire(pet[0], pet[1], n, "self", exec=False)
    return (n, "Admin")


def tick(R, prevs, ctl, y0):
    """Server, entered from prevs; ctl = the owner as a Controller (node, pin). Returns the exits."""
    g, MOD = R.g, R.MOD
    PET = MOD.full(R.PKG, MOD.PET_BP) + "_C"
    T.setdefault("pet", ("object", ir.obj_path(PET)))
    h = helpers(R, {})
    c = _Ctx(g, None, None, None)
    c.exits = list(prevs)
    x, y = 0, y0
    pet = lambda pos: h.get("SvOwlPet", "pet", pos)
    have_owl = lambda pos: c.fn("IsValid", KSL, {"Object": pet(pos)}, (pos[0] + 200, pos[1]))

    # every OWL_CHECK ticks
    cnt = c.fn("Add_IntInt", KML, {"A": h.get("SvOwlCount", "int", (x, y + 300)), "B": ("1", "int")}, (x + 200, y + 300))
    c.set_var("SvOwlCount", "int", cnt, (x + 300, y))
    due = c.fn("GreaterEqual_IntInt", KML, {"A": h.get("SvOwlCount", "int", (x + 400, y + 450)),
                                            "B": (str(OWL_CHECK), "int")}, (x + 600, y + 450))
    bDue = c.branch(due, (x + 600, y))
    out = [(bDue, "else")]
    c.exits = [(bDue, "then")]
    c.set_var("SvOwlCount", "int", "1", (x + 900, y))     # 1, not 0: a typed 0 can paste back as 1

    # wanted: unlocked, with a character
    x = 1300
    gac = R.Auth(g, R.CTRL_CLS, R.SG_CLS, MOD.SAVE_SLOT, None).controller(c.exits[0][0], c.exits[0][1], (x, y))
    arr = g.array_var("UnlockedPlayers", pos=(x + 200, y + 300), elem_cat="object", elem_sub=ir.obj_path(PSTATE),
                      parent=R.CTRL_CLS)
    g.wire(gac, "ReturnValue", arr, "self", exec=False)
    ps = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent=CTRL, pos=(x + 200, y + 450))
    g.wire(ctl[0], ctl[1], ps, "self", exec=False)
    has = g.array_fn("Array_Contains", pos=(x + 400, y + 300), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
    g.array_item_pin(has, "ItemToFind", "object", ir.obj_path(PSTATE))
    g.wire(arr, "UnlockedPlayers", has, "TargetArray", exec=False)
    g.wire(ps, "PlayerState", has, "ItemToFind", exec=False)
    pawn = g.call("K2_GetPawn", CTRL, pos=(x + 200, y + 600))
    g.wire(ctl[0], ctl[1], pawn, "self", exec=False)
    cast = g.cast(CHARACTER, pos=(x + 300, y))
    g.wire(pawn, "ReturnValue", cast, "Object", exec=False)
    g.wire(gac, "then", cast, "execute")
    me = (cast, "AsCharacter")
    c.exits = [(cast, "then")]
    bWant = c.branch((has, "ReturnValue"), (x + 700, y))
    nowant = [(bWant, "else"), (cast, "CastFailed")]      # no character counts as not wanted

    # wanted: an owl, whose Admin is this character
    c.exits = [(bWant, "then")]
    x = 2300
    bHave = c.branch(have_owl((x, y + 300)), (x + 300, y))
    c.exits = [(bHave, "else")]
    xf = c.fn("GetTransform", ACTOR, {"self": me}, (x + 400, y + 600))
    spawn = g.node("K2Node_SpawnActorFromClass", [], base="SpawnActor", pos=(x + 600, y + 300))
    sc = spawn.pin("Class").typed("class", ir.obj_path(ACTOR), direction="EGPD_Input")
    sc.set("DefaultObject", '"%s"' % PET)
    spawn.pin("ReturnValue").typed("object", ir.obj_path(PET), direction="EGPD_Output")
    g.typed_input(spawn, "CollisionHandlingOverride", "AlwaysSpawn", "byte",
                  ir.enum_path("/Script/Engine.ESpawnActorCollisionHandlingMethod"))
    g.wire(xf[0], xf[1], spawn, "SpawnTransform", exec=False)
    c.go(spawn)
    sp = g.var_set("SvOwlPet", "object", ir.obj_path(PET), pos=(x + 900, y + 300))
    g.wire(spawn, "ReturnValue", sp, "SvOwlPet", exec=False)
    c.go(sp)
    gst = g.call("GetGameState", GS, pos=(x + 1000, y + 900))
    now = c.fn("GetServerWorldTimeSeconds", GSB, {"self": (gst, "ReturnValue")}, (x + 1200, y + 900))
    first = c.fn("Add_DoubleDouble", KML, {"A": now, "B": (repr(OWL_FIRST), "real")}, (x + 1400, y + 900))
    fa = g.var_set("FlyAt", "real", parent=PET, pos=(x + 1200, y + 300))
    g.wire(*pet((x + 1000, y + 600)), fa, "self", exec=False)
    g.wire(first[0], first[1], fa, "FlyAt", exec=False)
    c.go(fa)
    c.exits += [(bHave, "then")]
    x = 4000
    same = c.fn("EqualEqual_ObjectObject", KML, {"A": me, "B": _admin(g, pet((x, y + 600)), PET, (x + 200, y + 600))},
                (x + 400, y + 450))
    bSame = c.branch(same, (x + 400, y))
    out += [(bSame, "then")]
    c.exits = [(bSame, "else")]
    sa = g.var_set("Admin", "object", ir.obj_path(CHARACTER), parent=PET, pos=(x + 700, y))
    g.wire(*pet((x + 500, y + 300)), sa, "self", exec=False)
    g.wire(me[0], me[1], sa, "Admin", exec=False)
    c.go(sa)
    out += c.exits

    # not wanted: no owl
    c.exits = nowant
    x = 2300
    bGone = c.branch(have_owl((x, y + 1500)), (x + 300, y + 1200))
    out += [(bGone, "else")]
    c.exits = [(bGone, "then")]
    d = g.call("K2_DestroyActor", ACTOR, pos=(x + 600, y + 1200))
    g.wire(*pet((x + 400, y + 1500)), d, "self", exec=False)
    c.go(d)
    return out + c.exits
