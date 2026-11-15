import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for scripts in (
    ROOT / "skills" / "progressive-ux-design" / "scripts",
    ROOT / "skills" / "design-refine" / "scripts",
    ROOT / "skills" / "style-switcher" / "scripts",
):
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
