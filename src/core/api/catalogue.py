"""In‑memory signal catalogue for API MVP."""
from src.core.signals.catalogue import create_signal

_catalogue = {}
create_signal(_catalogue, "REGULATORY", ["EU"], 0.35, ["ML_MODEL", "BUSINESS_RULE_SET"])
create_signal(_catalogue, "REGULATORY", ["US"], 0.35, ["ML_MODEL"])
create_signal(_catalogue, "MACROECONOMIC", ["US"], 0.15, ["ML_MODEL"])

def get_catalogue():
    return _catalogue
