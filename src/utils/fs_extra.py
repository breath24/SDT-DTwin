from __future__ import annotations

import os
import stat
import shutil
from pathlib import Path


def _on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def force_rmtree(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target, ignore_errors=False, onerror=_on_rm_error)


