import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("NEXTUP_DATA_DIR", "/tmp/nextup-test-placeholder")

@pytest.fixture(autouse=True)
def no_relay(monkeypatch):
    from app import tvdb

    monkeypatch.setattr(tvdb, "RELAY_URL", None)

@pytest.fixture()
def data_dir(tmp_path):
    from app import config, secretstore

    directory = tmp_path / "data"
    directory.mkdir()

    config.DATA_DIR = str(directory)
    config.DB_PATH = str(directory / "nextup.db")
    config.CACHE_DIR = str(directory / "images")
    config.KEY_PATH = str(directory / "secret.key")

    secretstore._fernet = None

    return directory

@pytest.fixture()
def app(data_dir):
    from app import create_app

    application = create_app(start_sync=False)
    application.config.update(TESTING=True)
    return application

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def signed_in(client):
    client.post("/login", data={"username": "admin", "password": "nextup"})
    with client.session_transaction() as sess:
        sess["starter"] = False
        sess["skip_welcome"] = True
    return client
