"""Deploy manifest for the owl-admin mod -- consumed by `/deploy` and
`bpkit/ops/deploy.py`. Shared metadata lives in oa_config.py.

    & $py ue_run.py bpkit/ops/deploy.py owl-admin
"""
import oa_config as _cfg

NAME = "owl-admin"
OUTPUT_PKG = _cfg.OUTPUT_PKG

# Order matters: 13 (the header logo texture) comes first, 03 and 07 reference it; 02 (controller) creates 01's widget, loads 08's settings save and spawns the
# relay (10 fills it in, using 02's events); 03 (admin menu) reads 02's unlocked list and
# settings and calls 10's server events; 07 (player menu) uses 10's transmog state and
# creates 11's grid cells, which call back into 07 (03 likewise creates 12's, which call back
# into 03); 14 (the custom NPC) and 16 (the shoulder owl) come before 10, which spawns them, and 15 (the NPC window) after 10,
# whose buy event it calls; 04 (commands) uses 02 + 08 (savegames); 05/06 (tables) reference 04's
# commands and 03/07/15's windows; 09 (the controller's registration override) merges 05 + 06, so it runs last.
BUILD = ["13_logo.py", "01_alerts_widget.py", "08_savegame.py", "02_controller.py", "14_npc.py", "16_owl_pet.py", "10_relay.py",
         "03_menu_widget.py", "07_player_menu.py", "15_npc_window.py", "11_tm_cell.py", "12_ce_cell.py",
         "04_commands.py", "05_command_table.py", "06_ui_module_table.py", "09_register.py"]

ASSETS = []
