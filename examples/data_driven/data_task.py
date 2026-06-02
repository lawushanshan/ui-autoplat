from __future__ import annotations

from robocorp.tasks import task

from ui_autoplat.utils.data_driven import data_driven


@data_driven("users.json")
@task
def test_login_data(row):
    """Data-driven example. Tags: example, data, P1"""
    assert row["username"]
    assert row["expected"] in {"ok", "locked"}
