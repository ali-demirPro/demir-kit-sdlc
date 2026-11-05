#!/usr/bin/env python3
"""doctor: kit ↔ Orca komut ve yanıt şekli denetimi (yalnız kit modu).

Orca yoksa veya şema okunamazsa sessizce atlanır: çevrimdışı makinelerde
doctor düşmez; sayaç yine artar.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import compat  # noqa: E402


def check_compat(
    root: Path,
    error: Callable[[str], None] | None = None,
    check: Callable[[str], None] | None = None,
) -> None:
    """`compat.check` + `compat.check_shapes` sonuçlarını doctor hatalarına yaz.

    doctor.py betik olarak çalıştığında `import doctor` ikinci bir modül
    örneği açar; bu yüzden rapor fonksiyonları çağıran taraftan geçirilir.
    """
    if error is None or check is None:
        import doctor

        error = error or doctor.error
        check = check or doctor.check
    check("compat")
    try:
        schema = compat.orca_capabilities.load_schema(root)
    except Exception:  # noqa: BLE001 - çevrimdışı/şema hatası doctor'u düşürmez
        return
    for issue in compat.check(root, schema) + compat.check_shapes():
        error(issue)
