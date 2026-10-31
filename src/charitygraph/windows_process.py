"""Windows process-launch policy shared by background CharityGraph services."""
from __future__ import annotations

import os
import subprocess
from typing import Any


def quiet_subprocess_kwargs() -> dict[str, Any]:
    """Return launch options that prevent console children from showing windows.

    Background services run through ``pythonw.exe`` on Windows.  Console
    helpers such as Git otherwise create a visible window even when their
    standard streams are redirected.
    """
    if os.name != "nt":
        return {}
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"creationflags": flag} if flag else {}
