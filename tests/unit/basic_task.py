"""Basic unit test for platform verification."""
from robocorp.tasks import task, setup, teardown


@setup
def suite_setup(task):
    pass


@teardown
def suite_teardown(task):
    pass


@task
def test_addition():
    """Verify basic math works. Tags: smoke, P0"""
    assert 1 + 1 == 2


@task
def test_string_concat():
    """Verify string concatenation. Tags: unit, P1"""
    result = "hello" + " " + "world"
    assert result == "hello world"


@task
def test_list_length():
    """Verify list length. Tags: unit, P1"""
    items = [1, 2, 3]
    assert len(items) == 3
