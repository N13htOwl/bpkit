"""Deploy manifest for the owl-admin mod -- consumed by `/deploy` and
`bpkit/ops/deploy.py`. Shared metadata lives in oa_config.py.

    & $py ue_run.py bpkit/ops/deploy.py owl-admin
"""
import oa_config as _cfg

NAME = "owl-admin"
OUTPUT_PKG = _cfg.OUTPUT_PKG

# Order matters: 02 (controller) CreateWidget-references 01's generated widget class.
BUILD = ["01_alerts_widget.py", "02_controller.py"]

ASSETS = []
