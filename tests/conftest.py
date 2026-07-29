import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def data_dir(tmp_path):
    """An isolated data_dir with the tx/la subdirs the pipeline expects."""
    for state in ("tx", "la"):
        (tmp_path / state).mkdir(parents=True)
    return tmp_path
