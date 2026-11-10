import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for scripts in (
    ROOT / "skills" / "design-refine" / "scripts",
    ROOT / "skills" / "style-switcher" / "scripts",
):
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))


@pytest.fixture
def tmp_workspace(tmp_path):
    return tmp_path
