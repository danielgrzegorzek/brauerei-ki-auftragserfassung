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

- `app.py` – Rahmen: Datenbank sicherstellen (`ensure_database`), `ui.apply_style()`, Navigation (`st.navigation`),
  Hinweiszeile „Portfolio-Projekt von … · Simulation mit fiktiven Daten“ (Container `portfolio-note`) über
  jeder Seite
- `ui.py` – Oberflächen-Bausteine im Fiori-Stil (bewusst außerhalb von `src/`): `page_header` (ohne Karte),
  `illustrated_message`, `img`/`svg_uri`, `image_uri`, `raw_html`, `chart_legend`; Farbvariablen je
  Hell/Dunkel in `COLORS`
  (auch `--chat-*` für den Messenger und `--step-*` für „Auftrag entsteht“)
- `ui_capture.py` – Bausteine der Auftragserfassung für beide Reiter: `show_proposal` (Formular, Prüfung,
  Speichern mit `on_saved`-Callback), `order_steps`/`show_steps` („Auftrag entsteht“), `new_capture`,
  Schlüssel/Client/Kontingent (`api_key`, `claude_client`, `live_calls_left`, `register_live_call`)
- `ui_tour.py` – geführte Tour: `show(page, pages)` zeichnet in `app.py` vor jeder Seite das Tour-Band
  (Zurück/Weiter/Beenden, `st.switch_page`); `start()` am Knopf der Startseite. Inhalt: `src/tour.py`
- `ui_chat.py` – Messenger-Ansicht (`chat_view`): Callbacks `use_example`, `send`, `choose`, `order_saved`;
  `process` (Live-KI, sonst Demo-Rückfall); Chat-HTML immer über `html.escape`
- `assets/` – `style.css` (Seiten-CSS), `illustrations.css` (Farben der SVGs), Logo, Leerzustands-Illustration
  (`empty_inbox`), Piktogramme
- `pages/` – Streamlit-Seiten (nur Oberfläche); Grundsatz seit der Design-Überarbeitung: höchstens ein Satz
  unter dem Titel, Details eingeklappt oder im Fragezeichen
  - `home.py` – Launchpad: Titel, ein Satz, Tour-Knopf, Kacheln (`tile` in der Seite selbst; Titel = Seitenlink
    über der ganzen Kachel; je eine fachliche Kennzahl, Making-of nur Symbol)
  - `dashboard.py` – `filter_bar`, `kpi_tiles`, `chart_grid` im Fragment `dashboard()`
  - `order_entry.py` (Reiter „Live-Chat“ = `ui_chat.chat_view`, Reiter „Posteingang“ = 7 Beispiele)
  - `business_case.py` – Fragment `calculator()`: drei Kennzahlen, Diagramm, Badges; „Annahmen anpassen“ und
    „Rechenweg“ eingeklappt
  - `process.py` – Kennzahlen vorher → nachher, Schwimmbahnen (Ist-Schwachstellen als Tooltip), SAP-Übergabe
    als Object Page im Fragment `sap_handover()` (Kopf, Reiter, Fußleiste mit Message Strip und
    „Übergabe simulieren“; `sap_simulated` = (Auswahl, JSON)); Vorauswahl über
    `st.session_state.sap_order_id`, das beide Speicher-Callbacks setzen
  - `making_of.py` – Rolle (zwei Sätze), Zeitleiste (eine Zeile je Entscheidung), vier Links
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
  - Making-of: `making_of.py` (`ROLE_INTRO`, `DECISIONS` – nur Entscheidungen, die Daniel getroffen hat –,
    Links; `WHY`, `BRIDGE`, `EVALUATION_STEPS`, `LEARNINGS`, `TESTS`/`COMMITS` werden seit der
    Design-Überarbeitung nicht mehr angezeigt, sind aber getestet)
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
- `tools/record_demo.py` – Demo-Video (ca. 45 s, stumm, 1920 × 1080, 30 fps, Zoom 125 %): Playwright steuert Edge
  durch die Live-App (Start → Dialekt-Chat → Auftrag → SAP-Übergabe → Business Case → Making-of), Einblendungen und
  Mauszeiger per `evaluate` im App-iframe, Bilder per CDP-Screencast, ffmpeg macht MP4 (< 8 MB), Vorschaubild,
  README-GIF und Prüfbilder je Szene in `data/demo/`. Live-KI ca. 1 US-Cent (prüft das Kennzeichen, bricht sonst ab),
  `--demo` kostenlos, `--url` für lokal. Aufnahme zu jeder Uhrzeit (nach 14 Uhr zeigt sie den verschobenen Termin).
  Fertiges Video liegt im Portfolio-Repo unter `assets/demo.mp4`
- Grundsatz Auftragserfassung: **Die KI versteht nur (liefert `ExtractedOrder`), der Code entscheidet.**
  Abgleich (`build_draft`) gibt nur Hinweise (Warnung/Info); blockierende Fehler kommen nur aus
  `check_order`. `save_order` prüft erneut. Erfasste Aufträge: `orders.source = 'KI-Erfassung'`,
  kein Leergut bis zur Lieferung. **Bestellschluss** `ORDER_CUTOFF` = 14 Uhr (deutsche Zeit): danach für den
  nächsten Liefertag bestellt → `apply_order_cutoff` (nach `build_draft`, in `ui_capture.new_capture`) legt den
  Termin auf den übernächsten Liefertag, Hinweis `moved_after_cutoff` in `Draft.date_hints`, Satz in der
  Chat-Antwort; stellt der Mensch zurück → Warnung `after_cutoff`. Die Oberfläche übergibt `after_cutoff()`.
- `tests/` – pytest; `conftest.py` baut einmal pro Lauf eine Test-Datenbank im Temp-Ordner;
  KI-Aufrufe nur mit Schein-Client (`FakeClient`), nie mit der echten API
- `docs/ENTSCHEIDUNGEN.md` – Designentscheidungen mit Begründung (öffentlich)
- Diagramm-Regeln: eine Akzentfarbe (`charts.PALETTES`, hell/dunkel), Tabellenansicht zu jedem
  Diagramm, keine zweite y-Achse; Theme-Farbe nur unter `[theme.light]`/`[theme.dark]`
- Nach Änderungen in `src/` oder `ui.py` den Streamlit-Server neu starten (lädt Module nicht immer neu)
- Oberfläche angelehnt an **SAP Fiori (Horizon)** – eigenes Logo, keine SAP-Marken; UI5 Web Components geprüft
  und verworfen (siehe `docs/ENTSCHEIDUNGEN.md`, Abschnitt 15). Karten entstehen über Container-Keys: `card-…`,
  `tile-…`, `message-bubble` (CSS über `st-key-<key>`-Klassen); `page-header` steht ohne Karte.
- **Streamlit legt um jeden Container eine Hülle** (`[data-testid="stLayoutWrapper"]`) und gibt dem Container
  `flex: 1` – feste Größen und `position: sticky` gehören an die Hülle (`…:has(> .st-key-…)`).
  Markdown-Blöcke haben unten einen negativen Rand; Kennzahl-Beschriftungen kürzt Streamlit mit „…“.
- **Layout:** zentrierter Inhaltsbereich, eine Regel in `assets/style.css` (`--content-max`: 1200 px, Dashboard und
  Auftragserfassung 1400 px, erkannt an `card-filters` bzw. `card-chat`); Kopfleiste an denselben Rändern,
  `scrollbar-gutter` in Inhalt und Kopfleiste; Lesebreite 70ch; auf dem Handy unverändert.
  **Browser-Prüfung immer bei 390, 1280, 1920 und 2560 px, hell und dunkel.**
- **`st.fragment`** für Business Case, Dashboard und SAP-Übergabe (nur dieser Teil lädt neu); in Fragmenten
  `return` statt `st.stop()`. Nicht in der Auftragserfassung (Chat, Vorschlag und Tabelle eng gekoppelt).
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

# Demo-Video aufnehmen (Standard: Live-App; Ergebnis in data/demo/)
.venv\Scripts\python.exe -m tools.record_demo                                       # Live-KI, ca. 1 US-Cent
.venv\Scripts\python.exe -m tools.record_demo --url http://localhost:8502 --demo   # lokaler Probelauf, kostenlos
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
  - Live: https://braeu-am-stein-ki.streamlit.app · Repo: https://github.com/danielgrzegorzek/brauerei-ki-auftragserfassung
  - **Jeder Push auf `main` aktualisiert die Live-App automatisch** → vor dem Push Tests laufen lassen.
  - Achtung: Die Cloud behält beim Update bereits geladene Module im Speicher. Kommen neue Namen in
    bestehende Module (z. B. neue Konstante in `src/…`), entsteht ein `ImportError` → App in Streamlit
    Cloud neu starten (Manage app → ⋮ → Reboot app; nur über Daniels Konto). Nach jedem Push die Live-App prüfen.
    Deshalb neuen Code möglichst in **neue Module**; frisch geladene Dateien (`app.py`, `pages/`, neue Module)
    importieren keine neuen Namen aus bestehenden Modulen. Auch **geänderte Texte oder Logik in bestehenden
    Modulen** (z. B. `src/tour.py`, `ui_chat.py`) erscheinen erst nach dem Reboot – `pages/`, `app.py` und
    `assets/*.css` dagegen sofort (bei der Design-Überarbeitung am 29.09.2026 live beobachtet).
  - GitHub-Name seit 29.09.2026 `danielgrzegorzek` (vorher `danig204`). Streamlit erkennt eine App an ihren
    GitHub-Koordinaten (Besitzer, Repo, Branch, Startdatei). Die Umbenennung ohne vorheriges Löschen hat die alte
    App verwaist: nicht mehr verwaltbar, Adresse `braeu-am-stein` blockiert (Support-Anfrage offen). Seitdem
    läuft die App unter `braeu-am-stein-ki`. Auch `braeu-am-stein-app` war nach Löschen und sofortigem
    Neuanlegen blockiert.
  - **Vor jeder Umbenennung von GitHub-Konto, Repo, Branch oder `app.py`:** erst die App in Streamlit Cloud
    löschen, dann umbenennen, dann neu bereitstellen (mit Python 3.13 und Secrets) – und dabei eine
    **neue** Subdomain wählen. Danach Links in README und Portfolio anpassen.
- [x] **Phase 5 – Echter KI-Modus:** Claude Sonnet 5, strukturierte Ausgabe, austauschbarer Anbieter,
  Kostenschutz, eigene Nachrichten, Evaluation (7/7)
- [ ] **Phase 5b – Präsentation:** Teil 1 [x] Live-Chat im Messenger-Stil, Prompt-Injection-Test,
  Modellvergleich (Sonnet 5 bleibt) · Teil 2 [x] Business Case · Teil 3 [x] geführte Tour, Startseite, README
- [x] **Phase 6 – Prozess & ERP:** Ist/Soll-Prozess als Schwimmbahnen, Übergabe an SAP S/4HANA als
  Kundenauftrag für die OData-API (JSON + Feld-Mapping, Simulation), 6. Tour-Schritt
- [x] **Making-of:** Seite „Making-of“, Hinweiszeile auf jeder Seite, Bestellschluss 14 Uhr;
  dazu Daniels Portfolio-Seite im eigenen Repo `danielgrzegorzek.github.io` (statisches HTML/CSS)
- [x] **Design-Überarbeitung:** ruhiger, weniger Text; Startseite als Launchpad, SAP-Übergabe als Object Page,
  Fragmente, Tour mit je einem Satz
- [ ] **Phase 7 – Regel-Parser (optional):** Vergleich „Regeln vs. KI“
- [ ] **Phase 8 – Feinschliff:** Tests ergänzen, README komplett, Demo-Video [x] (im Portfolio, per Skript)

Umgebung geprüft (2026-09-28): Python 3.13.15, pip 26.2.1, Git 2.55.0.
