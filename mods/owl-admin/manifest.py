"""Deploy manifest for the owl-admin mod -- consumed by `/deploy` and
`bpkit/ops/deploy.py`. Shared metadata lives in oa_config.py.

    & $py ue_run.py bpkit/ops/deploy.py owl-admin
"""
import oa_config as _cfg

NAME = "owl-admin"
OUTPUT_PKG = _cfg.OUTPUT_PKG

# Order matters: 05 (command table) references 04's class, 06 (UI module table) references
# 03's menu class, and 02 (controller) references 01's widget class + merges 05's and 06's tables.
BUILD = ["01_alerts_widget.py", "03_menu_widget.py", "04_menu_command.py", "05_command_table.py",
         "06_ui_module_table.py", "02_controller.py"]

ASSETS = []
