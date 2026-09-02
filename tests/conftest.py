import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Set before the app package is imported, so nothing ever touches a real /data.
os.environ.setdefault("NEXTUP_DATA_DIR", "/tmp/nextup-test-placeholder")


@pytest.fixture()
def data_dir(tmp_path):
    """A fresh data directory per test, so no test can see another's database."""
    from app import config, secretstore

    directory = tmp_path / "data"
    directory.mkdir()

    config.DATA_DIR = str(directory)
    config.DB_PATH = str(directory / "nextup.db")
    config.CACHE_DIR = str(directory / "images")
    config.KEY_PATH = str(directory / "secret.key")

    # The encryption key is cached at module level; drop it with the directory.
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
    return client
