"""Server-side Owl Admin login pieces, shared by the console commands (04: the player is the
command's CallingPlayerController) and the relay (10: the player is the relay's owner).

    a = Auth(g, ctrl_cls, sg_cls, save_slot, caller=(node, pin))   # caller: a ConanPlayerController
    a.check_password(prev, prev_pin, (pw_node, pw_pin), pos)       # right -> unlock the caller
    a.store_password(prev, prev_pin, (pw_node, pw_pin), pos)       # save it, mark it set, unlock
    a.message(prev, prev_pin, "text", pos)                         # Conan message box for the caller
    branch, ctrl = a.require_unlocked(prev, prev_pin, pos)         # caller in admin mode? -> branch "then"

Everything here runs ON THE SERVER: the password is read from and written to the server's
SaveGame (08) and never sent to clients. Unlocking writes the server-owned, replicated
UnlockedPlayers list on the controller (02) via PendingPlayer + a controller custom event,
since the list belongs to the controller. Results come back as a Conan message box on the
caller's screen (ClientShowMessageBox is a client RPC).
"""
from bpkit import ir

GS = "/Script/Engine.GameplayStatics"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
CPC = "/Script/ConanSandbox.ConanPlayerController"
PSTATE = "/Script/Engine.PlayerState"
TITLE = "Owl Admin"
NO_PASSWORD = "No Owl Admin password is set yet. Open the admin menu (Shift+O) to set one."


class Auth:
    def __init__(self, g, ctrl_cls, sg_cls, save_slot, caller):
        self.g, self.ctrl_cls, self.sg_cls, self.slot = g, ctrl_cls, sg_cls, save_slot
        self.caller = caller

    def message(self, prev, prev_pin, text, pos):
        """Conan message box on the caller's screen."""
        g = self.g
        t = g.call("Conv_StringToText", KTXT, pos=(pos[0], pos[1] + 200))
        g.typed_input(t, "InString", text, "string")
        title = g.call("Conv_StringToText", KTXT, pos=(pos[0], pos[1] + 350))
        g.typed_input(title, "InString", TITLE, "string")
        box = g.call("ClientShowMessageBox", CPC, pos=pos)
        g.wire(self.caller[0], self.caller[1], box, "self", exec=False)
        g.wire(title, "ReturnValue", box, "Title", exec=False)
        g.wire(t, "ReturnValue", box, "Message", exec=False)
        g.wire(prev, prev_pin, box, "execute")
        return box

    def controller(self, prev, prev_pin, pos):
        """GetActorOfClass(BP_OwlAdminController), in the exec chain after prev."""
        g = self.g
        gac = g.call("GetActorOfClass", GS, pos=pos)
        ap = gac.pin("ActorClass").typed("class", ir.obj_path("/Script/Engine.Actor"), direction="EGPD_Input")
        ap.set("PinType.bIsUObjectWrapper", "True")
        ap.set("DefaultObject", '"%s"' % self.ctrl_cls)
        g.wire(prev, prev_pin, gac, "execute")
        # GetActorOfClass already returns the controller's type (a cast is flagged as redundant);
        # the controller always exists once the mod is loaded, so no validity branch here
        gac.pin("ReturnValue").typed("object", ir.obj_path(self.ctrl_cls), direction="EGPD_Output")
        return gac

    def caller_state(self, pos):
        """The caller's PlayerState (pure)."""
        ps = self.g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent="/Script/Engine.Controller", pos=pos)
        self.g.wire(self.caller[0], self.caller[1], ps, "self", exec=False)
        return ps

    def require_unlocked(self, prev, prev_pin, pos):
        """Go on only if the caller is in admin mode (the controller's UnlockedPlayers, server
        side); else tell them it's locked. Returns (branch, controller node): carry on from
        branch "then"."""
        g, (x, y) = self.g, pos
        gac = self.controller(prev, prev_pin, (x, y))
        arr = g.array_var("UnlockedPlayers", pos=(x + 250, y + 250), elem_cat="object", elem_sub=ir.obj_path(PSTATE),
                          parent=self.ctrl_cls)
        g.wire(gac, "ReturnValue", arr, "self", exec=False)
        has = g.array_fn("Array_Contains", pos=(x + 500, y + 250), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
        g.array_item_pin(has, "ItemToFind", "object", ir.obj_path(PSTATE))
        g.wire(arr, "UnlockedPlayers", has, "TargetArray", exec=False)
        g.wire(self.caller_state((x + 250, y + 400)), "PlayerState", has, "ItemToFind", exec=False)
        bIn = g.branch(pos=(x + 500, y))
        g.wire(gac, "then", bIn, "execute")
        g.wire(has, "ReturnValue", bIn, "Condition", exec=False)
        self.message(bIn, "else", "Admin mode is locked. Log in on the admin menu first.", (x + 800, y + 700))
        return bIn, gac

    def set_pending_and_call(self, prev, prev_pin, event, pos):
        """controller.PendingPlayer = caller's PlayerState; controller.<event>(). Returns the
        call node (exec out "then")."""
        g, (x, y) = self.g, pos
        gac = self.controller(prev, prev_pin, (x, y))
        ps = self.caller_state((x + 300, y + 250))
        sp = g.var_set("PendingPlayer", "object", ir.obj_path(PSTATE), pos=(x + 600, y), parent=self.ctrl_cls)
        g.wire(gac, "ReturnValue", sp, "self", exec=False)
        g.wire(ps, "PlayerState", sp, "PendingPlayer", exec=False)
        g.wire(gac, "then", sp, "execute")
        call = g.call(event, self.ctrl_cls, pos=(x + 900, y))
        g.wire(gac, "ReturnValue", call, "self", exec=False)
        g.wire(sp, "then", call, "execute")
        return call

    def check_password(self, prev, prev_pin, pw, pos):
        """Saved password == pw (case-sensitive)? -> unlock admin mode for the caller."""
        g, (x, y) = self.g, pos
        dse = g.call("DoesSaveGameExist", GS, pos=(x, y))
        g.typed_input(dse, "SlotName", self.slot, "string")
        g.typed_input(dse, "UserIndex", "0", "int")
        g.wire(prev, prev_pin, dse, "execute")
        bSet = g.branch(pos=(x + 250, y))
        g.wire(dse, "then", bSet, "execute")
        g.wire(dse, "ReturnValue", bSet, "Condition", exec=False)
        self.message(bSet, "else", NO_PASSWORD, (x + 500, y + 600))
        load = g.call("LoadGameFromSlot", GS, pos=(x + 500, y))
        g.typed_input(load, "SlotName", self.slot, "string")
        g.typed_input(load, "UserIndex", "0", "int")
        g.wire(bSet, "then", load, "execute")
        cast = g.cast(self.sg_cls, pos=(x + 800, y))
        g.wire(load, "ReturnValue", cast, "Object", exec=False)
        g.wire(load, "then", cast, "execute")
        self.message(cast, "CastFailed", NO_PASSWORD, (x + 1100, y + 900))
        saved = g.var_get("Password", "string", parent=self.sg_cls, pos=(x + 800, y + 300))
        g.wire(cast, "AsBP Owl Admin Save", saved, "self", exec=False)
        eq = g.call("EqualEqual_StrStr", KSTR, pos=(x + 1100, y + 300))     # case-sensitive compare
        g.wire(pw[0], pw[1], eq, "A", exec=False)
        g.wire(saved, "Password", eq, "B", exec=False)
        bOk = g.branch(pos=(x + 1100, y))
        g.wire(cast, "then", bOk, "execute")
        g.wire(eq, "ReturnValue", bOk, "Condition", exec=False)
        self.message(bOk, "else", "Wrong password.", (x + 1400, y + 600))
        done = self.set_pending_and_call(bOk, "then", "OwlUnlockPending", (x + 1400, y))
        self.message(done, "then", "Admin mode unlocked. Press Shift+O to open the admin menu.", (x + 2400, y))

    def store_password(self, prev, prev_pin, pw, pos):
        """Save pw as the password, tell every client a password exists (admin menus leave the
        setup page), and unlock the caller so they go straight into the menu."""
        g, (x, y) = self.g, pos
        crt = g.call("CreateSaveGameObject", GS, pos=(x, y))
        cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
        cp.set("PinType.bIsUObjectWrapper", "True")
        cp.set("DefaultObject", '"%s"' % self.sg_cls)
        # CreateSaveGameObject narrows ReturnValue to the class passed (as in mounted-followers 04)
        crt.pin("ReturnValue").typed("object", ir.obj_path(self.sg_cls), direction="EGPD_Output")
        g.wire(prev, prev_pin, crt, "execute")
        sp = g.var_set("Password", "string", pos=(x + 300, y), parent=self.sg_cls)
        g.wire(crt, "ReturnValue", sp, "self", exec=False)
        g.wire(pw[0], pw[1], sp, "Password", exec=False)
        g.wire(crt, "then", sp, "execute")
        sav = g.call("SaveGameToSlot", GS, pos=(x + 600, y))
        g.typed_input(sav, "SlotName", self.slot, "string")
        g.typed_input(sav, "UserIndex", "0", "int")
        g.wire(crt, "ReturnValue", sav, "SaveGameObject", exec=False)
        g.wire(sp, "then", sav, "execute")
        marked = self.set_pending_and_call(sav, "then", "OwlPasswordSetPending", (x + 900, y))
        done = self.set_pending_and_call(marked, "then", "OwlUnlockPending", (x + 1900, y))
        self.message(done, "then", "Owl Admin password set. Admin mode unlocked.", (x + 2900, y))
