"""Deploy manifest for the owl-admin mod -- consumed by `/deploy` and
`bpkit/ops/deploy.py`. Shared metadata lives in oa_config.py.

    & $py ue_run.py bpkit/ops/deploy.py owl-admin
"""
import oa_config as _cfg

NAME = "owl-admin"
OUTPUT_PKG = _cfg.OUTPUT_PKG

# Order matters: 02 (controller) creates 01's widget; 03 (admin menu) reads 02's unlocked
# list; 04 (commands) uses 02 + 08 (savegame); 05/06 (tables) reference 04's commands and
# 03/07's menus; 09 (the controller's registration override) merges 05 + 06, so it runs last.
BUILD = ["01_alerts_widget.py", "02_controller.py", "08_savegame.py", "03_menu_widget.py",
         "07_player_menu.py", "04_commands.py", "05_command_table.py", "06_ui_module_table.py",
         "09_register.py"]

ASSETS = []
