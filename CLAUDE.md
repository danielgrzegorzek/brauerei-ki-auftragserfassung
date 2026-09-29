# CLAUDE.md – Bräu am Stein: KI-Auftragserfassung & Vertriebsanalyse

## Über das Projekt

Portfolio-Projekt aus den Bereichen **SAP-Prozesse, KI-Automatisierung und Datenanalyse**.

Titel: **„Vom WhatsApp-Chaos zum sauberen Auftrag“** – KI-gestützte Auftragserfassung
und Vertriebsanalyse für eine fiktive Brauerei.

## Arbeitsweise (wichtig)

- Vor jedem Schritt **kurz und einfach auf Deutsch erklären**, was gemacht wird und warum – dann umsetzen.
- In **kleinen Schritten** arbeiten, ein Commit pro Schritt; nach jedem Schritt zeigen, wie man das Ergebnis prüft.
- Einfacher, lesbarer Code vor cleverem Code. Keine unnötigen Abstraktionen.
- Neue Bibliotheken nur mit kurzer Begründung einführen.
- Vor größeren Änderungen erst Plan zeigen, dann Code schreiben.
- **SAP-Begriffe** (z. B. Verkaufsorganisation, Vertriebsweg) beim ersten Auftauchen einfach erklären.
- **Designentscheidungen** mit Begründung und Alternative in `docs/ENTSCHEIDUNGEN.md` festhalten.
- Persönliche Notizen bleiben lokal (stehen in der `.gitignore`) und werden nie committet.

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
- **Claude-API** über das offizielle `anthropic`-Paket: Modell `claude-sonnet-5`, strukturierte Ausgabe
  (`messages.parse` mit Pydantic-Schema), `effort: low`

## Konventionen

- API-Schlüssel **niemals** im Code oder in Git → `.streamlit/secrets.toml` (steht in
  `.gitignore`) bzw. Secrets in der Streamlit Community Cloud.
- Der Demo-Modus muss immer ohne API-Schlüssel lauffähig bleiben.
- Simulierte Daten mit festem Zufalls-Seed erzeugen → reproduzierbar.
- Oberfläche (`pages/`) und Logik (`src/`) trennen, damit die Logik testbar ist.

## Projektstruktur

- `app.py` – Rahmen: Datenbank sicherstellen (`ensure_database`), `ui.apply_style()`, Navigation (`st.navigation`)
- `ui.py` – Oberflächen-Bausteine im Fiori-Stil (bewusst außerhalb von `src/`): `page_header`, `tile`,
  `illustration`, `illustrated_message`, `image_uri`; Farbvariablen je Hell/Dunkel in `COLORS`
  (auch `--chat-*` für den Messenger und `--step-*` für „Auftrag entsteht“)
- `ui_capture.py` – Bausteine der Auftragserfassung für beide Reiter: `show_proposal` (Formular, Prüfung,
  Speichern mit `on_saved`-Callback), `order_steps`/`show_steps` („Auftrag entsteht“), `new_capture`,
  Schlüssel/Client/Kontingent (`api_key`, `claude_client`, `live_calls_left`, `register_live_call`)
- `ui_tour.py` – geführte Tour: `show(page, pages)` zeichnet in `app.py` vor jeder Seite das Tour-Band
  (Zurück/Weiter/Beenden, `st.switch_page`); `start()` am Knopf der Startseite. Inhalt: `src/tour.py`
- `ui_chat.py` – Messenger-Ansicht (`chat_view`): Callbacks `use_example`, `send`, `choose`, `order_saved`;
  `process` (Live-KI, sonst Demo-Rückfall); Chat-HTML immer über `html.escape`
- `assets/` – `style.css` (Seiten-CSS), `illustrations.css` (Farben der SVGs), Logo, Illustrationen, Piktogramme
- `pages/` – Streamlit-Seiten (nur Oberfläche): `home.py`, `dashboard.py`, `order_entry.py`, `business_case.py`,
  `process.py` (Schwimmbahnen Ist/Soll + SAP-Übergabe; Vorauswahl über `st.session_state.sap_order_id`,
  das beide Speicher-Callbacks setzen)
  (Reiter „Live-Chat“ = `ui_chat.chat_view`, Reiter „Posteingang“ = 7 Beispiele)
- `src/` – Logik ohne Streamlit:
  - Daten: `database.py` (Schema, `SCHEMA_VERSION`), `master_data.py`, `order_generator.py`,
    `empties_generator.py`, `data_setup.py`, `plausibility.py` (prüft nur `source = 'Historie'`)
  - Auswertung: `analytics.py` (SQL → DataFrame), `charts.py` (Plotly), `formatting.py` (deutsche Formate)
  - Auftragserfassung: `order_models.py` (Zielformat der KI, JSON), `demo_messages.py`
    (7 Beispiele mit vorbereiteten KI-Antworten), `order_capture.py` (Abgleich → Prüfung → Speichern)
  - KI: `extraction.py` (`MODELS` mit Preisen/`effort` je Modell, `MODEL` = Modell der App; Vertrag
    `OrderExtractor`; `DemoExtractor` (auch `CHAT_EXAMPLES`), `ClaudeExtractor`; `SYSTEM_PROMPT`,
    `calendar_hint`, Antwortschema `OrderSchema`), `ai_usage.py` (Kostenschutz: 1.000 Zeichen,
    5 Aufrufe je Besuch, 30 je Tag; Tabelle `ai_usage`)
  - Tour: `tour.py` (`tour_steps` – sechs Schritte mit Seitenschlüssel aus `app.py`, Zahlen aus den Daten)
  - Prozess & SAP: `process.py` (`AS_IS`/`TO_BE` als `ProcessStep`, `figures` – Minuten = Business-Case-
    Annahmen, per Test gekoppelt), `sap_mapping.py` (`OrderForSap`, `sales_order_payload` für OData
    `API_SALES_ORDER_SRV`, `missing_fields`, `field_mapping`, `http_request`; ohne Preise und Leergut –
    die ermittelt SAP selbst; nur Simulation, nichts wird gesendet)
  - Business Case: `business_case.py` (`ASSUMPTIONS` mit Standardwert + Begründung, `calculate`,
    `default_result` = Standardannahmen, auch für Startseite und Tour,
    `calculation_steps`, Auftragsmenge `orders_last_12_months`, KI-Kosten `measured_ai_cost` aus
    `docs/evaluation.json`); Diagramm `charts.cost_comparison_chart` + HTML-Legende `ui.chart_legend`
  - Chat & Sicherheit: `chat.py` (Antwort der Brauerei aus dem Prüfergebnis; immer nur EINE Rückfrage,
    immer mit Knöpfen – `QuickReply` setzt Artikel, Menge oder Liefertermin; `open_quick_replies`,
    `PERSONAS`, `now_berlin`), `message_safety.py` (starke/schwache Signale im Text + Hinweis der KI →
    Warnung); `extraction.RefusalError` = Ablehnung durch die KI (≠ technischer Fehler);
    `Issue.code` ist die maschinenlesbare Art eines Prüfhinweises (z. B. `sunday`, `hard_limit`)
- `tools/evaluate_extraction.py` – 7 Demo-Nachrichten + Sicherheitstest (Prompt-Injection) an Claude,
  Vergleich mit dem Soll; hängt jeden Lauf an `docs/evaluation.json` an und erzeugt daraus
  `docs/EVALUATION.md` (Modellvergleich). Kosten je Lauf ca. 3–8 US-Cent; `--report-only` kostenlos
- Grundsatz Auftragserfassung: **Die KI versteht nur (liefert `ExtractedOrder`), der Code entscheidet.**
  Abgleich (`build_draft`) gibt nur Hinweise (Warnung/Info); blockierende Fehler kommen nur aus
  `check_order`. `save_order` prüft erneut. Erfasste Aufträge: `orders.source = 'KI-Erfassung'`,
  kein Leergut bis zur Lieferung.
- `tests/` – pytest; `conftest.py` baut einmal pro Lauf eine Test-Datenbank im Temp-Ordner;
  KI-Aufrufe nur mit Schein-Client (`FakeClient`), nie mit der echten API
- `docs/ENTSCHEIDUNGEN.md` – Designentscheidungen mit Begründung (öffentlich)
- Diagramm-Regeln: eine Akzentfarbe (`charts.PALETTES`, hell/dunkel), Tabellenansicht zu jedem
  Diagramm, keine zweite y-Achse; Theme-Farbe nur unter `[theme.light]`/`[theme.dark]`
- Nach Änderungen in `src/` oder `ui.py` den Streamlit-Server neu starten (lädt Module nicht immer neu)
- Oberfläche angelehnt an **SAP Fiori (Horizon)** – eigenes Logo, keine SAP-Marken. Karten entstehen über
  Container-Keys: `card-…`, `tile-…`, `page-header`, `message-bubble` (CSS über `st-key-<key>`-Klassen).
- **`st.html` filtert `<style>` und `<svg>`** → eigenes HTML/CSS über `ui.raw_html` (`st.markdown` mit
  `unsafe_allow_html`); SVGs als `<img>` über `ui.img`, das die Modus-Farben in ein CDATA-`<style>` im SVG schreibt.
- Läuft auf Port 8501 schon ein manuell gestarteter Server, zum Testen die Konfiguration
  `streamlit-test` (Port 8502) in `.claude/launch.json` nutzen.
- **Vorsicht Kosten:** `streamlit.testing.v1.AppTest` liest die lokale `secrets.toml` mit – Seitentests
  laufen dann mit Live-KI. Im Test immer den Schalter `chat_live` ausschalten bzw. „Demo“ wählen und den
  Zähler in `ai_usage` vorher/nachher vergleichen.
- `AppTest` übernimmt einen Seitenwechsel per `st.switch_page` nicht in den nächsten `run()` (die Tour
  scheint dann auf die Startseite zu springen) – Seitenwechsel im Browser prüfen.
- Direkt nach dem Serverstart zuerst die Startseite laden: Eine Unterseite per URL (z. B. `/process`) kam
  beim allerersten Aufruf einmal ohne Rahmen aus `app.py` (Streamlit-Seitenliste noch nicht registriert).
- **`st.cache_data` nur einfache Daten zurückgeben** (Zahlen, Texte, Tupel, Dicts, DataFrames) – keine
  Objekte eigener Klassen: Nach einem Code-Update lädt die Cloud geänderte Module neu, und Pickle lehnt
  Objekte der alten Klasse ab (`UnserializableReturnValueError`).

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

# Live-Evaluation der KI (braucht den Schlüssel in .streamlit/secrets.toml, kostet ca. 3–8 US-Cent)
.venv\Scripts\python.exe -m tools.evaluate_extraction
.venv\Scripts\python.exe -m tools.evaluate_extraction --model claude-haiku-4-5
.venv\Scripts\python.exe -m tools.evaluate_extraction --report-only   # nur Bericht, ohne API
```

Der API-Schlüssel steht nur in `.streamlit/secrets.toml` (lokal) bzw. in den Secrets der
Streamlit Community Cloud – **nie ausgeben, nie committen.** Ohne Schlüssel läuft nur der Demo-Modus.

Die Datenbank `data/brauerei.db` wird beim Start automatisch gebaut, wenn sie fehlt oder
`SCHEMA_VERSION` in `src/database.py` nicht passt (aktuell 3) → **bei Schemaänderungen die Version erhöhen.**

## Phasenplan & Status

- [x] **Phase 0 – Setup:** Git, `.gitignore`, `.venv`, `requirements.txt`, Test-Startseite
- [x] **Phase 1 – Datenbasis:** SQLite-Schema, Datengenerator (Saisonalität, Leergut), Plausibilitäts-Check
- [x] **Phase 2 – Dashboard:** KPIs, Umsatz nach Monat/Kundengruppe/Produkt, Saisonalität, Top-Kunden, Leergut
- [x] **Phase 3 – Auftragserfassung (Demo-Modus):** Zielformat, Beispielnachrichten, Stammdatenabgleich, Human-in-the-Loop
- [x] **Phase 4 – Erste Veröffentlichung:** GitHub, Streamlit Cloud, Basis-README
  - Live: https://braeu-am-stein.streamlit.app · Repo: https://github.com/danielgrzegorzek/brauerei-ki-auftragserfassung
  - **Jeder Push auf `main` aktualisiert die Live-App automatisch** → vor dem Push Tests laufen lassen.
  - Achtung: Die Cloud behält beim Update bereits geladene Module im Speicher. Kommen neue Namen in
    bestehende Module (z. B. neue Konstante in `src/…`), entsteht ein `ImportError` → App in Streamlit
    Cloud neu starten (Manage app → ⋮ → Reboot app; nur über Daniels Konto). Nach jedem Push die Live-App prüfen.
- [x] **Phase 5 – Echter KI-Modus:** Claude Sonnet 5, strukturierte Ausgabe, austauschbarer Anbieter,
  Kostenschutz, eigene Nachrichten, Evaluation (7/7)
- [ ] **Phase 5b – Präsentation:** Teil 1 [x] Live-Chat im Messenger-Stil, Prompt-Injection-Test,
  Modellvergleich (Sonnet 5 bleibt) · Teil 2 [x] Business Case · Teil 3 [x] geführte Tour, Startseite, README
- [x] **Phase 6 – Prozess & ERP:** Ist/Soll-Prozess als Schwimmbahnen, Übergabe an SAP S/4HANA als
  Kundenauftrag für die OData-API (JSON + Feld-Mapping, Simulation), 6. Tour-Schritt
- [ ] **Phase 7 – Regel-Parser (optional):** Vergleich „Regeln vs. KI“
- [ ] **Phase 8 – Feinschliff:** Tests ergänzen, README komplett, Demo-Video

Umgebung geprüft (2026-09-28): Python 3.13.15, pip 26.2.1, Git 2.55.0.
