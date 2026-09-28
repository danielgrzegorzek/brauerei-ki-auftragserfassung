# CLAUDE.md – Bräu am Stein: KI-Auftragserfassung & Vertriebsanalyse

## Über das Projekt

Portfolio-Projekt aus den Bereichen **SAP-Prozesse, KI-Automatisierung und Datenanalyse**.

Titel: **„Vom WhatsApp-Chaos zum sauberen Auftrag“** – KI-gestützte Auftragserfassung
und Vertriebsanalyse für eine fiktive Brauerei.

## Arbeitsweise (wichtig)

- Vor jedem Schritt **kurz und einfach auf Deutsch erklären**, was gemacht wird und warum – dann umsetzen.
- In **kleinen Schritten** arbeiten; nach jedem Schritt zeigen, wie man das Ergebnis prüft/testet.
- Einfacher, lesbarer Code vor cleverem Code. Keine unnötigen Abstraktionen.
- Neue Bibliotheken nur mit kurzer Begründung einführen.
- Vor größeren Änderungen erst Plan zeigen, dann Code schreiben.
- **SAP-Begriffe** (z. B. Verkaufsorganisation, Vertriebsweg) beim ersten Auftauchen einfach erklären.

## Szenario (fiktiv)

- **Bräu am Stein GmbH**, Familienbrauerei in Niederbayern, ca. 150 Mitarbeiter.
- **Sortiment:** Helles, Weißbier, Pils, Alkoholfreies, Limonaden – in Flaschen (Kasten) und Fässern.
- **Kunden:** Gastronomie, Getränkegroßhändler, Supermärkte, Volksfest-Veranstalter.
- **Problem heute:** Bestellungen kommen unstrukturiert per Telefon, E-Mail und WhatsApp.
- **Leergut/Pfand** (Kästen, Fässer) muss verrechnet werden.
- **Starke Saisonalität** (Sommer, Volksfeste).
- Alle Firmen, Personen und Daten sind frei erfunden.

## Funktionsumfang der App

1. **Datenbasis:** Realistisch simulierte Stammdaten (Kunden, Produkte, Preise) und
   Auftragsdaten über 2 Jahre inkl. Saisonalität und Leergut.
2. **Dashboard:** Umsatz nach Monat / Kundengruppe / Produkt, Saisonalität, Top-Kunden,
   offenes Leergut.
3. **KI-Auftragserfassung:** Freitext (z. B. „Servus, bräucht für Freitag 5 Fass Helles
   und 10 Kasten Weißbier“) → per LLM-API in strukturierten Auftrag umwandeln → gegen
   Stammdaten prüfen → vom Nutzer bestätigen (**Human-in-the-Loop**).
   **Pflicht: Demo-Modus** mit Beispielnachrichten, der **ohne API-Schlüssel** funktioniert
   (damit Recruiter die App kostenlos testen können).
4. **Prozessseite:** Ist-Prozess vs. Soll-Prozess und Übergabe des Auftrags an ein
   ERP-System wie SAP S/4HANA.

## Getroffene Entscheidungen

- **LLM:** Claude-API (Anthropic), aber **austauschbar** gebaut (Anbieter hinter einer
  schmalen Schnittstelle, damit z. B. OpenAI ergänzt werden könnte).
- **Sprache:** Code (Variablen, Funktionen, Dateien) auf **Englisch**; **Kommentare und
  Oberfläche auf Deutsch**.
- **Demo-Modus:** zuerst nur hinterlegte Beispielnachrichten mit vorbereiteten Ergebnissen.
  Regel-Parser später als optionaler Zusatz für den Vergleich „Regeln vs. KI“.
- **Veröffentlichung vorgezogen:** Sobald Dashboard + Demo-Modus laufen → GitHub +
  Streamlit Community Cloud; alles Weitere kommt als Updates.

## Technik

- **Python 3.13** (Windows 11, PowerShell), virtuelle Umgebung in `.venv`
- **Streamlit** (Oberfläche), **Plotly** (Diagramme), **SQLite** (Datenbank), **pandas**
- **Claude-API** über das offizielle `anthropic`-Paket (ab Phase 5)

## Konventionen

- API-Schlüssel **niemals** im Code oder in Git → `.streamlit/secrets.toml` (steht in
  `.gitignore`) bzw. Secrets in der Streamlit Community Cloud.
- Der Demo-Modus muss immer ohne API-Schlüssel lauffähig bleiben.
- Simulierte Daten mit festem Zufalls-Seed erzeugen → reproduzierbar.
- Oberfläche (`pages/`) und Logik (`src/`) trennen, damit die Logik testbar ist.

## Projektstruktur

- `app.py` – Rahmen: Datenbank sicherstellen (`ensure_database`), Navigation (`st.navigation`)
- `pages/` – Streamlit-Seiten (nur Oberfläche): `home.py`, `dashboard.py`, `order_entry.py`
- `src/` – Logik ohne Streamlit:
  - Daten: `database.py` (Schema, `SCHEMA_VERSION`), `master_data.py`, `order_generator.py`,
    `empties_generator.py`, `data_setup.py`, `plausibility.py` (prüft nur `source = 'Historie'`)
  - Auswertung: `analytics.py` (SQL → DataFrame), `charts.py` (Plotly), `formatting.py` (deutsche Formate)
  - Auftragserfassung: `order_models.py` (Zielformat der KI, JSON), `demo_messages.py`
    (7 Beispiele mit vorbereiteten KI-Antworten), `order_capture.py` (Abgleich → Prüfung → Speichern)
- Grundsatz Auftragserfassung: **Die KI versteht nur (liefert `ExtractedOrder`), der Code entscheidet.**
  Abgleich (`build_draft`) gibt nur Hinweise (Warnung/Info); blockierende Fehler kommen nur aus
  `check_order`. `save_order` prüft erneut. Erfasste Aufträge: `orders.source = 'KI-Erfassung'`,
  kein Leergut bis zur Lieferung.
- `tests/` – pytest; `conftest.py` baut einmal pro Lauf eine Test-Datenbank im Temp-Ordner
- Diagramm-Regeln: eine Akzentfarbe (`charts.PALETTES`, hell/dunkel), Tabellenansicht zu jedem
  Diagramm, keine zweite y-Achse; Theme-Farbe nur unter `[theme.light]`/`[theme.dark]`
- Nach Änderungen in `src/` den Streamlit-Server neu starten (lädt Module nicht immer neu)

## Befehle

```powershell
# App starten (ohne die virtuelle Umgebung aktivieren zu müssen)
.venv\Scripts\python.exe -m streamlit run app.py

# Datenbank von Hand neu erzeugen (passiert sonst automatisch beim App-Start)
.venv\Scripts\python.exe -m src.data_setup

# Plausibilitäts-Check der Daten
.venv\Scripts\python.exe -m src.plausibility

# Tests (einmalig vorher: pip install -r requirements-dev.txt)
.venv\Scripts\python.exe -m pytest -q
```

Die Datenbank `data/brauerei.db` wird beim Start automatisch gebaut, wenn sie fehlt oder
`SCHEMA_VERSION` in `src/database.py` nicht passt → **bei Schemaänderungen die Version erhöhen.**

## Phasenplan & Status

- [x] **Phase 0 – Setup:** Git, `.gitignore`, `.venv`, `requirements.txt`, Test-Startseite
- [x] **Phase 1 – Datenbasis:** SQLite-Schema, Datengenerator (Saisonalität, Leergut), Plausibilitäts-Check
- [x] **Phase 2 – Dashboard:** KPIs, Umsatz nach Monat/Kundengruppe/Produkt, Saisonalität, Top-Kunden, Leergut
- [x] **Phase 3 – Auftragserfassung (Demo-Modus):** Zielformat, Beispielnachrichten, Stammdatenabgleich, Human-in-the-Loop
- [ ] **Phase 4 – Erste Veröffentlichung:** GitHub, Streamlit Cloud, Basis-README
  (Git-E-Mail ist bereits auf die GitHub-noreply-Adresse umgestellt – alle Commits nutzen sie)
- [ ] **Phase 5 – Echter KI-Modus:** Claude-API, strukturierte Ausgabe, austauschbarer Anbieter
- [ ] **Phase 6 – Prozess & ERP:** Ist/Soll-Prozess, Übergabe an SAP S/4HANA (JSON + Feld-Mapping)
- [ ] **Phase 7 – Regel-Parser (optional):** Vergleich „Regeln vs. KI“
- [ ] **Phase 8 – Feinschliff:** Tests ergänzen, README komplett, Demo-Video

Umgebung geprüft (2026-09-28): Python 3.13.15, pip 26.2.1, Git 2.55.0.
