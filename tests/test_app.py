from api_activity import app, create_app
import pytest

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_hello(client):
    response = client.get('/', base_url="https://localhost")
    assert response.status_code == 200
    assert response.json == {"message": "Hello World!"}

def test_square(client):
    response = client.get('/square/5', base_url="https://localhost")
    assert response.status_code == 200
    assert response.json == {'Shape': 'Square', 'Area': 25}

def test_echo(client):
    response = client.get('/echo?arg1=value1&arg2=value2', base_url="https://localhost")
    assert response.status_code == 200
    assert response.json == {'arg1': 'arg1', 'arg2': 'arg2'}

def test_profile_requires_auth(client):
    response = client.get('/profile', base_url="https://localhost")
    assert response.status_code == 401

def test_profile_with_valid_auth(client):
    client.put('/register', json={"username": "testuser", "password": "testpass123"},
               base_url="https://localhost",)
    response = client.get('/profile', auth=("testuser", "testpass123"),
                          base_url="https://localhost",)
    assert response.status_code == 200
    assert "testuser" in response.json["message"]

@pytest.fixture
def client():
    with create_app().test_client() as client:
        yield client

def test_hello(client):
    response = client.get('/')
    assert response.status_code == 200