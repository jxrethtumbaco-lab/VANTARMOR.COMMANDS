from pathlib import Path

path = Path(__file__).with_name("premium_security_system.py")
source = path.read_text(encoding="utf-8")
if "from typing import Optional" not in source:
    marker = "from pathlib import Path\n"
    if marker not in source:
        raise RuntimeError("No encontré el bloque de imports de premium_security_system.py")
    source = source.replace(marker, marker + "from typing import Optional\n", 1)
    path.write_text(source, encoding="utf-8")
