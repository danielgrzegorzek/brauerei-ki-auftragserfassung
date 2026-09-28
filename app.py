import streamlit as st

# Seiteneinstellungen: Titel im Browser-Tab, Symbol und breites Layout.
# Muss der erste Streamlit-Befehl der Seite sein.
st.set_page_config(page_title="Bräu am Stein", page_icon="🍺", layout="wide")

st.title("🍺 Bräu am Stein")
st.subheader("Vom WhatsApp-Chaos zum sauberen Auftrag")

st.write(
    "KI-gestützte Auftragserfassung und Vertriebsanalyse für eine fiktive "
    "Familienbrauerei in Niederbayern."
)

st.success("Setup erfolgreich – die App läuft!")
