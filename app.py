import streamlit as st

from src.data_setup import ensure_database
from src.database import get_connection

# Seiteneinstellungen: Titel im Browser-Tab, Symbol und breites Layout.
# Muss der erste Streamlit-Befehl der Seite sein.
st.set_page_config(page_title="Bräu am Stein", page_icon="🍺", layout="wide")


@st.cache_resource(show_spinner="Datenbank wird beim ersten Start erzeugt …")
def init_database() -> None:
    """Stellt sicher, dass die Datenbank existiert – läuft nur einmal pro Serverprozess."""
    ensure_database()


init_database()

st.title("🍺 Bräu am Stein")
st.subheader("Vom WhatsApp-Chaos zum sauberen Auftrag")

st.write(
    "KI-gestützte Auftragserfassung und Vertriebsanalyse für eine fiktive "
    "Familienbrauerei in Niederbayern."
)

conn = get_connection()
customers, orders = conn.execute(
    "SELECT (SELECT COUNT(*) FROM customers), (SELECT COUNT(*) FROM orders)"
).fetchone()
conn.close()
orders_text = f"{orders:,}".replace(",", ".")  # deutscher Tausenderpunkt
st.success(f"Datenbank bereit: {customers} Kunden, {orders_text} Aufträge.")
