from todo import add_task, remove_task

def test_add_task():
    assert add_task(['a'], 'b') == ['a', 'b']

def test_remove_task_present():
    assert remove_task(['a', 'b', 'c'], 'b') == ['a', 'c']

def test_remove_task_absent():
    assert remove_task(['a', 'b'], 'z') == ['a', 'b']
