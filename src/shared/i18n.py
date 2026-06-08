"""
国际化模块 — 从第一天起支持多语言。
"""
import json
import os
from pathlib import Path
from typing import Dict

I18N_DIR = Path(__file__).parent.parent.parent / "i18n"


def load_locale(lang: str) -> Dict[str, str]:
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        path = I18N_DIR / "zh.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_cache: Dict[str, Dict[str, str]] = {}


def t(key: str, lang: str = "zh") -> str:
    if lang not in _cache:
        _cache[lang] = load_locale(lang)
    return _cache[lang].get(key, key)
