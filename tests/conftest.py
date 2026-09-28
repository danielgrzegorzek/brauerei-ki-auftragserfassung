"""Gemeinsame Test-Fixtures: vorbereitete Testumgebungen, die pytest automatisch bereitstellt."""

import shutil

import pytest

from src.data_setup import build_database
from src.database import get_connection


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    """Baut EINMAL pro Testlauf eine komplette Test-Datenbank in einem Temp-Ordner."""
    path = tmp_path_factory.mktemp("data") / "test.db"
    build_database(path)
    return path


@pytest.fixture
def conn(db_path):
    """Lesende Verbindung zur gemeinsamen Test-Datenbank."""
    connection = get_connection(db_path)
    yield connection
    connection.close()


@pytest.fixture
def writable_conn(db_path, tmp_path):
    """Verbindung zu einer eigenen Kopie der Test-Datenbank – für Tests, die Daten verändern."""
    copy_path = tmp_path / "copy.db"
    shutil.copy(db_path, copy_path)
    connection = get_connection(copy_path)
    yield connection
    connection.close()
