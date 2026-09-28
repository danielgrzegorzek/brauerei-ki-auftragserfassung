"""Aufbau der Datenbank: Schema anlegen und mit simulierten Daten füllen.

Die App ruft beim Start `ensure_database()` auf. Neu aufbauen von Hand (PowerShell):
    .venv\\Scripts\\python.exe -m src.data_setup
"""

import random
from pathlib import Path

from src.database import DB_PATH, SCHEMA_VERSION, create_schema, get_connection, read_schema_version
from src.empties_generator import generate_empties_movements
from src.master_data import insert_master_data
from src.order_generator import generate_orders, insert_orders

# Fester Startwert für den Zufallsgenerator → bei jedem Aufbau exakt dieselben Daten
SEED = 42


def build_database(db_path: Path = DB_PATH, seed: int = SEED) -> None:
    """Erzeugt die komplette Datenbank neu.

    Geschrieben wird zuerst in eine Temp-Datei, die erst am Ende die echte Datei ersetzt.
    So gibt es nie eine halb fertige Datenbank, falls unterwegs etwas schiefgeht.
    """
    tmp_path = db_path.with_suffix(".tmp")
    tmp_path.unlink(missing_ok=True)
    rng = random.Random(seed)
    conn = get_connection(tmp_path)
    try:
        create_schema(conn)
        insert_master_data(conn, rng)
        insert_orders(conn, generate_orders(conn, rng))
        generate_empties_movements(conn, rng)
        conn.commit()
    finally:
        conn.close()
    tmp_path.replace(db_path)


def ensure_database(db_path: Path = DB_PATH) -> bool:
    """Baut die Datenbank, falls sie fehlt oder ein veraltetes Schema hat.

    Gibt True zurück, wenn sie neu erzeugt wurde.
    """
    if db_path.exists():
        conn = get_connection(db_path)
        try:
            is_current = read_schema_version(conn) == SCHEMA_VERSION
        finally:
            conn.close()
        if is_current:
            return False
    build_database(db_path)
    return True


if __name__ == "__main__":
    build_database()
    print(f"Datenbank neu erzeugt: {DB_PATH}")
