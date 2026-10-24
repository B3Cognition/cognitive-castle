import os
import time

import pytest

from cognitive_castle import palace


def test_aged_held_lock_is_never_unlinked(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    root = str(tmp_path / "palace")
    with palace.mine_palace_lock(root):
        locks = list((tmp_path / ".castle/locks").glob("*.lock"))
        inode = locks[0].stat().st_ino
        os.utime(locks[0], (time.time() - 90000,) * 2)
        assert palace.clean_stale_locks(str(locks[0].parent)) == (0, 1)
        assert locks[0].stat().st_ino == inode
        with pytest.raises(palace.MineAlreadyRunning):
            with palace.mine_palace_lock(root):
                pass


def test_mutation_session_nests_but_independent_writer_cannot(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    root = tmp_path / "palace"
    with palace.mutation_session(root):
        with palace.mutation_session(root):
            pass
        with pytest.raises(palace.MineAlreadyRunning):
            with palace.mine_palace_lock(root):
                pass
