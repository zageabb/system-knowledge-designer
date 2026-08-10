from database import db
from models import AppSetting


CODEX_CONTROL_ENABLED = "codex_control_enabled"
EXTERNAL_RESEARCH_ENABLED = "external_research_enabled"


def get_bool(key: str, default: bool = False) -> bool:
    setting = db.session.get(AppSetting, key)
    return default if setting is None else setting.value.casefold() == "true"


def set_bool(key: str, value: bool) -> None:
    setting = db.session.get(AppSetting, key)
    if setting is None:
        setting = AppSetting(key=key)
        db.session.add(setting)
    setting.value = "true" if value else "false"


def get_text(key: str, default: str = "") -> str:
    setting = db.session.get(AppSetting, key)
    return default if setting is None else setting.value


def set_text(key: str, value: str) -> None:
    setting = db.session.get(AppSetting, key)
    if setting is None:
        setting = AppSetting(key=key)
        db.session.add(setting)
    setting.value = value
