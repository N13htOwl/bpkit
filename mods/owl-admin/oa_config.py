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
LOGO_TEX = "T_OwlLogo"                # both menus' header logo (13 imports art/owl_logo.png)
LOGO_PNG = "art/owl_logo.png"         # drawn by art/owl_logo.py, relative to this folder
SAVEGAME = "BP_OwlAdminSave"          # SaveGame holding the admin password (server side only)
SAVE_SLOT = "OwlAdmin"                # its slot name (Saved/SaveGames/OwlAdmin.sav on the server)
RELAY = "BP_OwlRelay"                 # one per player, owned by their PlayerController: carries
                                      # passwords to the server as RPCs, so they never hit the log
TM_CELL_WBP = "WBP_OwlTmCell"         # one appearance in the player menu's transmog grid (made at runtime)
TM_SAVEGAME = "BP_OwlTransmogSave"    # a player's look + saved outfits (server side only)
TM_SLOT_PREFIX = "OwlTransmog_"       # its slot: OwlTransmog_<player net id>, one file per player
TM_MAX_OUTFITS = 6                    # saved outfits per player (the menu has this many rows)
SETTINGS_SAVEGAME = "BP_OwlSettingsSave"   # SaveGame holding the applied menu settings (server side only)
SETTINGS_SLOT = "OwlAdminSettings"         # its own slot, so saving settings never touches the password
# Character editor (the admin menu's Characters tab)
CE_SAVEGAME = "BP_OwlCeSave"          # one player's Owl wallet + the admin changes made to them
CE_SLOT_PREFIX = "OwlCe_"             # its slot: OwlCe_<player net id>, one file per player
CE_LOG_MAX = 50                       # log lines kept per player (oldest dropped)
ECON_SAVEGAME = "BP_OwlEconomySave"   # accepted currencies + NPC price multipliers (saved, no effect yet)
ECON_SLOT = "OwlEconomy"
CE_CONTEXT = "OwlAdmin"               # the context Name given to the game's inventory add/delete calls
CE_CELL_WBP = "WBP_OwlCeCell"         # one item in the Inventory / Item catalog grids (made at runtime)
# Bug reports (the player menu's Bug Report tab -> the admin menu's Bug Reports tab)
BUG_SAVEGAME = "BP_OwlBugSave"       # every player's reports, server side
BUG_SLOT = "OwlBugReports"
BUG_MAX = 50                          # reports kept (oldest dropped)
BUG_WAIT = 60.0                       # seconds a player waits between two reports
# HUD (the admin menu's HUD tab -> every player's WBP_OwlAlerts)
HUD_SAVEGAME = "BP_OwlHudSave"        # On: 1/0 per menu_defs.HUD_ITEMS; Text: one per text item
HUD_SLOT = "OwlHud"
# Server Restart (the admin menu's Server Restart tab -> every player's alert banner + sound)
RESTART_SAVEGAME = "BP_OwlRestartSave"   # Vals: one int per menu_defs.RS_LIMITS entry
RESTART_SLOT = "OwlRestart"
# Kits: what is in each kit (server-wide), and each player's last claim per kit
KITS_SAVEGAME = "BP_OwlKitsSave"      # Names (one per kit); per entry: EKit, EIds, EQty, ENames
KITS_SLOT = "OwlKits"
KITCLAIM_SAVEGAME = "BP_OwlKitClaimSave"   # Last: per kit, the minute (Unix time / 60) it was claimed, 0 = never
KITCLAIM_SLOT_PREFIX = "OwlKit_"           # OwlKit_<player net id>
# Scripting: the admins' command scripts (server-wide; sent only to unlocked admins)
SCRIPTS_SAVEGAME = "BP_OwlScriptsSave"     # Names (one per script); Lines (SCRIPT_LINES per script, in order)
SCRIPTS_SLOT = "OwlScripts"
# Trading: the trade log the admin menu's Trading page shows
TRADES_SAVEGAME = "BP_OwlTradeSave"        # Log: "time|line", newest last, at most TRADE_LOG_MAX
TRADES_SLOT = "OwlTrades"
# NPCs: the admins' custom NPCs (placed in the world, talk + wares), and the window players use
NPC_BP = "BP_OwlNPC"                       # the NPC character (a child of the game's dialogue NPC)
NPC_SAVEGAME = "BP_OwlNpcSave"             # every NPC: name, role, line, where, gear, wares
NPC_SLOT = "OwlNpcs"
NPC_WINDOW_WBP = "WBP_OwlNpcWindow"        # the talk / wares window (a UI module, opened by the NPC)
NPC_MODULE = "OwlNpcWindow"
PET_BP = "BP_OwlPet"                       # the shoulder owl admins in admin mode get (16, spawned by the relay)

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
ACTIONS = [("OwlAdminToggle", "O"), ("OwlPlayerToggle", "I")]   # (action, key), both with Shift. Not U:
                                                                # Tot ! Enhanced Sudo's admin panel is Shift+U
UI_MODULE_TABLE = "DT_OwlAdmin_UIModules"   # UIModuleTableRow table, one row per menu
GAME_UI_MODULE_TABLE = "/Game/UI/Data/DataTables/DT_UIModuleTable"   # game table we merge into

# The canvas boards are drawn at 1280x720; UMG lays out at a 1080p reference (DPI
# scale 1.0), so board px * 1.5 = UMG units. UMG font Size is in points (px * 0.75).
BOARD_SCALE = 1.5

FONT_BOLD = "/Game/Fonts/Kelson_Sans_Bold.Kelson_Sans_Bold"         # board: Rajdhani 700
FONT_REGULAR = "/Game/Fonts/Kelson_Sans_Regular.Kelson_Sans_Regular"  # board: Rajdhani 500

VERSION = 10  # v2: hidden until the player has a character; v3: notice cards moved below Conan's
              # vitals; v4: hidden while a menu has the mouse cursor up; v5: `dc OwlAdmin` menu;
              # v6: Left Shift+U hotkey (polled; didn't work); v7: Shift+U / Shift+I as input
              # actions, Owl Admin login, player menu; v8: APPLY saves settings on the server and
              # pushes the LIVE ones into Conan's server settings; v9: the menu sends passwords
              # through a per-player relay RPC instead of a logged console command; v10: the
              # player menu's Transmog tab (looks + outfits saved per player on the server)
STEAM_FILE_ID = "3828691613"  # the Workshop item (first upload 2026-10-28, Hidden). Every update must
                              # go to this id: check the Dev Kit's mod window shows it before uploading
VERSION_NAME = "V1.2"  # fallback for version_name(); VERSION above is the internal build number
                       # (build logs, the controller's OwlVersion)


def version_name():
    """What players see (Bug Report form): "V<major>.<minor>" from the mod's modinfo.json at build
    time, so it follows the version set in the Dev Kit's mod window (set it before building 07).
    VERSION_NAME if the file can't be read."""
    import json
    import os
    import unreal
    path = os.path.join(unreal.Paths.project_content_dir(), "Mods", OUTPUT_PKG.rsplit("/", 1)[-1], "modinfo.json")
    try:
        with open(path, encoding="utf-8-sig") as f:
            info = json.load(f)
        return "V%d.%d" % (info["versionMajor"], info["versionMinor"])
    except (OSError, ValueError, KeyError):
        return VERSION_NAME


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
