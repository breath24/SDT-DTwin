import pytest
from app import app

@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c

def test_home_ok(client):
    r = client.get('/')
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}

def test_add_ok(client):
    r = client.get('/add?a=2&b=3')
    assert r.status_code == 200
    assert r.get_json() == {"result": 5}

def test_add_missing(client):
    r = client.get('/add')
    assert r.status_code == 400
    assert r.get_json() == {"error": "bad_request"}
