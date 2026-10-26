"""Metadata for the owl-admin mod -- the Owl Admin (Beta) screens from the design canvas,
rebuilt as real Conan UMG widgets.

OUTPUT_PKG must be the mod's own content root (/Game/Mods/<ModName>) so the cook
tags the assets "(Mod Asset)". The OwlAdmin mod must exist in the DevKit (Mods tool ->
create) and be the ACTIVE mod for that package to be writable; build steps fall back
to /Game/_Scratch/OwlAdmin with a DRY RUN banner when it isn't.
"""

OUTPUT_PKG = "/Game/Mods/OwlAdmin"
SCRATCH_PKG = "/Game/_Scratch/OwlAdmin"

ALERTS_WBP = "WBP_OwlAlerts"          # HUD board: server alert banner + notice cards
CONTROLLER = "BP_OwlAdminController"  # ModController: alerts overlay, unlocked-admins list, registration
MENU_WBP = "WBP_OwlAdminMenu"         # Admin Restrictions Menu board, behind the Owl Admin login
PLAYER_MENU_WBP = "WBP_OwlPlayerMenu"  # player menu: the player-facing boards as tabs
SAVEGAME = "BP_OwlAdminSave"          # SaveGame holding the admin password (server side only)
SAVE_SLOT = "OwlAdmin"                # its slot name (Saved/SaveGames/OwlAdmin.sav on the server)
RELAY = "BP_OwlRelay"                 # one per player, owned by their PlayerController: carries
                                      # passwords to the server as RPCs, so they never hit the log
SETTINGS_SAVEGAME = "BP_OwlSettingsSave"   # SaveGame holding the applied menu settings (server side only)
SETTINGS_SLOT = "OwlAdminSettings"         # its own slot, so saving settings never touches the password

# Conan's server settings actor (a BP subclass of ServerSettings): the menu's LIVE settings
# (menu_defs.LIVE) are pushed into it -- native ones via SetServerSetting, which also writes
# the server's ServerSettings.ini; the rest are variables on this BP, re-applied at BeginPlay.
SERVER_SETTINGS_CLS = "/Game/Systems/BP_ServerSettings.BP_ServerSettings_C"

# Console commands: (command name, DataActorCommand class, RequireAdmin, RunOnServer, RunOnClient).
# Admin mode is the Owl Admin login: the password lives only on the server and is checked
# there (OwlLogin runs on the server), so a client can't unlock itself.
CMD_TABLE = "DT_OwlAdmin_Commands"    # BlueprintCommandDataRow table merged by the controller
COMMANDS = [
    ("OwlAdmin", "BP_OwlAdminMenuCommand", False, False, True),       # open the admin menu (login inside)
    ("OwlLogin", "BP_OwlLoginCommand", False, True, False),           # dc OwlLogin <password>
    ("OwlLogout", "BP_OwlLogoutCommand", False, True, False),         # lock admin mode again
    ("OwlSetPassword", "BP_OwlSetPasswordCommand", True, True, False),  # Conan admins set the password
    ("OwlApply", "BP_OwlApplyCommand", False, True, False),           # the menu's APPLY: every setting value
]
CUSTOM_CMD_TABLE = "/Game/Systems/Cheats/CustomConsoleCommandsDataTable"  # game table we merge into

# Conan only shows the mouse cursor for windows its GUIModuleController manages, so both
# menus are UI modules: a WindowRoot widget + a DT_UIModuleTable row (merged by the controller).
# Each row's ToggleActionName is an input action we register at mod init, so Conan's own key
# handling opens and closes the menu (Shift = either Shift key; action mappings can't tell
# left from right).
MENU_MODULE = "OwlAdminMenu"          # module name: GUIModuleController.ToggleModule(MENU_MODULE)
PLAYER_MODULE = "OwlPlayerMenu"
ACTIONS = [("OwlAdminToggle", "U"), ("OwlPlayerToggle", "I")]   # (action, key), both with Shift
UI_MODULE_TABLE = "DT_OwlAdmin_UIModules"   # UIModuleTableRow table, one row per menu
GAME_UI_MODULE_TABLE = "/Game/UI/Data/DataTables/DT_UIModuleTable"   # game table we merge into

# The canvas boards are drawn at 1280x720; UMG lays out at a 1080p reference (DPI
# scale 1.0), so board px * 1.5 = UMG units. UMG font Size is in points (px * 0.75).
BOARD_SCALE = 1.5

FONT_BOLD = "/Game/Fonts/Kelson_Sans_Bold.Kelson_Sans_Bold"         # board: Rajdhani 700
FONT_REGULAR = "/Game/Fonts/Kelson_Sans_Regular.Kelson_Sans_Regular"  # board: Rajdhani 500

VERSION = 9   # v2: hidden until the player has a character; v3: notice cards moved below Conan's
              # vitals; v4: hidden while a menu has the mouse cursor up; v5: `dc OwlAdmin` menu;
              # v6: Left Shift+U hotkey (polled; didn't work); v7: Shift+U / Shift+I as input
              # actions, Owl Admin login, player menu; v8: APPLY saves settings on the server and
              # pushes the LIVE ones into Conan's server settings; v9: the menu sends passwords
              # through a per-player relay RPC instead of a logged console command


def full(pkg, name):
    """'/Game/.../Name.Name' object path for an asset NAME in package pkg."""
    return "%s/%s.%s" % (pkg, name, name)


def resolve_pkg():
    """In-editor: OUTPUT_PKG if the OwlAdmin mod is mounted, else SCRATCH_PKG with a
    DRY RUN banner. Every build step uses this so they all target the same root."""
    import unreal
    if unreal.EditorAssetLibrary.does_directory_exist(OUTPUT_PKG):
        return OUTPUT_PKG
    print("#" * 68)
    print("##  DRY RUN: %s not mounted (OwlAdmin mod not active)" % OUTPUT_PKG)
    print("##  building into %s -- NOT shippable from there" % SCRATCH_PKG)
    print("#" * 68)
    return SCRATCH_PKG
