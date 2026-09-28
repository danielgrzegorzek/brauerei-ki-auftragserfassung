# Designentscheidungen

Dieses Dokument hält fest, **welche Entscheidungen** in diesem Projekt getroffen wurden und
**warum** – jeweils mit der verworfenen Alternative oder der bewussten Grenze.

## Architektur im Überblick

```
app.py                 Rahmen: Datenbank sicherstellen, Gestaltung laden, Seitennavigation
ui.py                  Oberflächen-Bausteine im Fiori-Stil (Seitenkopf, Kacheln, Illustrationen)
assets/                Logo, SVG-Illustrationen, Stylesheet
pages/                 Oberfläche (Streamlit) – nur Anzeige und Eingaben
  home.py              Startseite mit Datenbasis und Plausibilitäts-Check
  dashboard.py         Vertriebs-Dashboard
  order_entry.py       KI-Auftragserfassung mit Bestätigung durch den Menschen
src/                   Logik ohne Streamlit – vollständig testbar
  database.py          Schema, Verbindung, Schemaversion
  master_data.py       Stammdaten: Artikel, Leergut, Preise, Kunden
  order_generator.py   simulierte Auftragshistorie (2 Jahre)
  empties_generator.py simulierte Leergut-Bewegungen
  data_setup.py        Aufbau der Datenbank beim Start
  plausibility.py      fachliche Prüfungen der simulierten Daten
  analytics.py         Auswertungen (SQL → pandas)
  charts.py            Diagramme (Plotly)
  order_models.py      Zielformat der KI-Auswertung
  demo_messages.py     Beispielnachrichten für den Demo-Modus
  order_capture.py     Abgleich → Prüfung → Speichern
tests/                 automatische Tests (pytest)
```

Ablauf der KI-Auftragserfassung:

```
Freitext-Nachricht
   │  KI (Demo-Modus: vorbereitete Antwort im selben Format)
   ▼
ExtractedOrder (JSON: Kunde, Termin, Sorte/Einheit/Menge je Position)
   │  Abgleich mit Stammdaten → Hinweise, wie zugeordnet wurde
   ▼
Auftragsentwurf ──► Mensch ändert Kunde, Termin, Positionen
   │  Prüfung der Geschäftsregeln – nach jeder Änderung neu
   ▼
„Bestätigen & speichern“ (gesperrt bei Fehlern) → erneute Prüfung → Datenbank → Dashboard
```

---

## 1. Technologie und Projektaufbau

| Entscheidung | Begründung | Alternative / Grenze |
|---|---|---|
| **Streamlit** als Oberfläche | Web-App in reinem Python, schnell gebaut, kostenloses Hosting. Der Fokus liegt auf Daten, KI und Prozess, nicht auf Frontend-Technik. | React/Flask: mehr gestalterische Kontrolle, deutlich mehr Aufwand. Streamlit ist nicht für große Mehrbenutzer-Anwendungen gedacht. |
| **SQLite** als Datenbank | Eine Datei, kein Datenbankserver, in Python eingebaut – reicht für eine Demo. | Im Echtbetrieb lägen die Aufträge im ERP (z. B. SAP S/4HANA), die App wäre die Erfassungs- und Analyseschicht davor. |
| **Plotly** für Diagramme | Interaktiv (Tooltips, Zoom). | matplotlib: nur statische Bilder. |
| **Claude-API**, austauschbar gebaut | Gutes Textverständnis und strukturierte Ausgabe; austauschbar, um keine Abhängigkeit von einem Anbieter aufzubauen. | OpenAI, lokale Modelle. |
| Code auf Englisch, Oberfläche und Kommentare auf Deutsch | Englisch ist Standard im Code; Nutzer des Szenarios sind deutschsprachig. | – |
| **Oberfläche (`pages/`) und Logik (`src/`) getrennt** | Logik ist ohne Oberfläche testbar und wiederverwendbar. | Alles in einer Datei: am Anfang schneller, später unübersichtlich. |
| **Feste Paketversionen** (`==`) | Die App läuft in der Cloud mit exakt denselben Versionen wie lokal. | Ohne feste Versionen kann ein Update die App unbemerkt verändern. |
| Entwicklungspakete (pytest) in `requirements-dev.txt` | Die Cloud installiert nur, was die App zum Laufen braucht. | – |
| **Ein Commit pro Arbeitsschritt** | Jede Änderung ist einzeln nachvollziehbar und rückgängig zu machen. | – |

## 2. Datenmodell

| Entscheidung | Begründung | Alternative / Grenze |
|---|---|---|
| Trennung **Stammdaten** (Kunden, Artikel, Leergutarten, Preise) und **Bewegungsdaten** (Aufträge, Leergut-Bewegungen) | Entspricht dem Aufbau eines ERP-Systems. | – |
| Auftrag in **Kopf und Positionen** (`orders` / `order_items`), Positionen in 10er-Schritten | Wie SAP-Verkaufsbelege (Kopf-/Positionstabellen); 10er-Schritte lassen Platz zum Einfügen. | – |
| **Primär- und Fremdschlüssel**, `CHECK`-Regeln, `STRICT`-Tabellen; Fremdschlüssel-Prüfung pro Verbindung eingeschaltet | Die Datenbank selbst lehnt ungültige Daten ab – letzte Sicherung, auch gegen fehlerhafte KI-Vorschläge. | – |
| Zusammengesetzte Schlüssel für Positionen (Auftrag + Position) und Preise (Artikel + Kundengruppe + gültig ab) | Eindeutigkeit ergibt sich erst aus der Kombination. | – |
| **Preis wird in die Auftragsposition kopiert** | Historische Richtigkeit: Nach einer Preiserhöhung dürfen alte Aufträge nicht neu bewertet werden. Bewusste Ausnahme von der Normalisierung. | – |
| Preise mit **Gültigkeitsdatum** je Kundengruppe | Stark vereinfachte Konditionen; bildet die Preiserhöhung zum 01.01.2026 ab. | – |
| Artikel mit **Sorte** und **Warengruppe** | Die KI erkennt die Sorte („Weizen“ → Weißbier), das Dashboard wertet nach Warengruppe aus. | – |
| Kasten/Fass nur über die **Leergutart** des Artikels | Normalisierung: jede Information an genau einer Stelle. | – |
| **Leergut als einzelne Bewegungen** (+ Auslieferung, − Rückgabe) statt Saldo-Spalte | Jeder Stand ist nachvollziehbar und für jeden Stichtag berechenbar. | Saldo-Spalte: nach einem Fehler nicht mehr erklärbar. |
| Kundengruppen als `CHECK`-Regel statt eigener Tabelle | Kleine, feste Liste ohne weitere Merkmale. | Eigene Tabelle, sobald Kundengruppen Eigenschaften bekommen (z. B. Standardrabatt). |
| Geldbeträge als `REAL` | Vereinfachung für die Demo. | Im Produktivsystem: Cent als Ganzzahl oder Dezimaltyp (keine Rundungsfehler). |
| Datum als Text `JJJJ-MM-TT` | SQLite hat keinen Datumstyp; das ISO-Format sortiert korrekt und passt zu den SQLite-Datumsfunktionen. | – |
| Spalte `orders.source` („Historie“ / „KI-Erfassung“) | Erfasste Aufträge sind unterscheidbar (Anzeige, Demo zurücksetzen, Plausibilitäts-Check nur für die Historie). | – |

## 3. Simulierte Daten

| Entscheidung | Begründung | Alternative / Grenze |
|---|---|---|
| Fester Zufalls-Seed (`random.Random(42)`) | Reproduzierbar: gleicher Seed und gleicher Code → exakt gleiche Daten, auch in Tests. | Jede Code-Änderung am Generator verschiebt den Zufallsstrom und damit alle Zahlen. |
| Simulation in drei Ebenen: Verhalten je **Kundengruppe**, **Profil** je Kunde (Größe, festes Sortiment), **Tag-für-Tag**-Würfeln | Ergibt realistische Schwankungen und konsistentes Kundenverhalten (z. B. immer dieselbe Fassgröße). | Feste Bestellrhythmen: wirken künstlich. |
| Saisonfaktoren je Monat, Sommeraufschlag für Weißbier und Radler, Biergärten nur April–September, Veranstalter nur rund um Feste | Starke Saisonalität ist typisch für Brauereien; Faktoren wurden gemessen und nachjustiert (Sommer ≈ 1,7 × Winter). | – |
| WhatsApp-Anteil steigt über die zwei Jahre | Bildet den Anlass des Projekts ab: unstrukturierte Bestellungen nehmen zu. | – |
| **Preise:** Grundpreis Gastronomie × Faktor je Kundengruppe; keine Fasspreise für den Lebensmittelhandel | Kompakt und leicht änderbar; ein fehlender Preis bedeutet „nicht freigegeben“. | 112 Einzelpreise von Hand. |
| Feste **Demo-Kunden** mit festen Profilen, übrige Kunden aus Namensbausteinen | Die Demo-Nachrichten brauchen verlässliche Kunden mit passender Historie. | – |
| Leergut-Rückgabe bei der **nächsten Lieferung**, nach 21 Tagen Pause separate **Abholung**; kleiner Schwund, bei ~10 % der Kunden höher | So läuft es in der Praxis; Rückgaben sind auf den Bestand beim Kunden begrenzt, der Saldo wird nie negativ. | – |
| Keine echten Marken, Handelsketten oder Domains („Cola-Mix“, E-Mail-Adressen auf `.example`) | Das Szenario ist fiktiv und soll niemanden abbilden. | – |
| Aufbau in **Temp-Datei + Umbenennen** | Bricht der Aufbau ab, gibt es nie eine halb gefüllte Datenbank. | – |
| **Schemaversion** in `PRAGMA user_version`; `ensure_database()` baut beim Start neu, wenn die Datei fehlt oder veraltet ist | Ändert sich das Schema, braucht es keinen manuellen Schritt – auch nicht in der Cloud. | Im Echtbetrieb: Migration, die vorhandene Daten erhält. |
| Aufbau über `st.cache_resource` | Läuft nur einmal pro Serverprozess, nicht bei jedem Klick. | – |
| **Plausibilitäts-Check** (13 fachliche Prüfungen) getrennt von den Tests | Tests prüfen den Code, der Check prüft die fachliche Sinnhaftigkeit der Daten – und hat einen echten Generatorfehler gefunden. | – |

## 4. Dashboard

| Entscheidung | Begründung | Alternative / Grenze |
|---|---|---|
| Drei Schichten: Abfragen (`analytics.py`) – Diagramme (`charts.py`) – Seite | Jede Schicht hat eine Aufgabe; Abfragen sind ohne Oberfläche testbar. | – |
| Werte in SQL nur über **`?`-Platzhalter** | Schutz vor SQL-Injection. | Werte in den SQL-Text einsetzen. |
| Filter als **unveränderliche Dataclass**; **eine** zwischengespeicherte Ladefunktion je Filterkombination (`st.cache_data`) | Streamlit führt bei jedem Klick das ganze Skript aus; so laufen Abfragen nur bei neuen Filtern. Nach dem Speichern eines Auftrags wird der Cache geleert. | – |
| **Eine Filterzeile oben**, gültig für alle Zahlen darunter | Alle Werte beziehen sich immer auf dieselbe Auswahl. | Filter in einzelnen Diagrammen. |
| Standardzeitraum „letzte 12 Monate“; **Vorjahresvergleich** nur, wenn das Vorjahr vollständig in den Daten liegt | Sonst wäre der Vergleich verzerrt. | – |
| Offenes Pfand mit **umgekehrter Farblogik** | Mehr offenes Pfand ist schlecht. | – |
| Diagrammform nach Aufgabe: Säulen (Zeitverlauf), Rangfolge-Balken (Vergleich), Heatmap (Muster), Linien mit **Hervorhebung** (Trend eines Kanals), Kacheln (Einzelwerte) | Die Frage bestimmt das Diagramm. Kein Kreisdiagramm, **keine zweite y-Achse** (erzeugt scheinbare Zusammenhänge). | – |
| **Eine Akzentfarbe** plus Grau, mit Prüfskript validiert; eigene Farbstufen für den Dunkelmodus | Kontrast ≥ 3:1 und unterscheidbar bei Farbsehschwäche; Kategorien ohne Reihenfolge brauchen keine bunten Farben. | – |
| **Tabellenansicht** zu jedem Diagramm | Werte nachprüfbar und ohne Farbe oder Tooltip lesbar; als CSV exportierbar. | – |
| **Berechnete Kernaussage** über jedem Diagramm | Das Dashboard sagt, was die Zahlen bedeuten – passend zu den Filtern. | Feste Texte: im Grenzfall falsch. |
| **Saisonindex** (100 = Durchschnittsmonat) statt absoluter Menge | Warengruppen unterschiedlicher Größe werden vergleichbar. | – |
| Monate/Quartale ohne Aufträge werden **aufgefüllt** (0 bzw. Lücke) | Sonst verschwinden sie von der Zeitachse. | – |
| Deutsche Zahlenformate an einer Stelle (`formatting.py`) | Einheitlich und getestet. | – |
| Theme-Farbe unter `[theme.light]` und `[theme.dark]` | Nur so folgt die App der Hell-/Dunkel-Einstellung des Betrachters. | Eintrag direkt unter `[theme]` erzwingt ein helles Theme. |

## 5. KI-Auftragserfassung

| Entscheidung | Begründung | Alternative / Grenze |
|---|---|---|
| **Die KI versteht nur – der Code entscheidet** | Sprachmodelle können sich irren oder etwas erfinden. Artikelzuordnung, Preise und Regeln sind im Code nachvollziehbar, testbar und unabhängig vom Modell. | KI liefert direkt Artikelnummern und Preise. |
| **Festes Zielformat** (`ExtractedOrder`, JSON) für Demo-Modus und echte KI | Der Demo-Modus nutzt denselben Weg; für die echte KI wird nur die Quelle des JSON ausgetauscht. | – |
| **Demo-Modus** mit vorbereiteten KI-Antworten; Liefertermine relativ zu „heute“ | Die App ist ohne API-Schlüssel und kostenlos testbar; „Freitag“ ist immer der nächste Freitag. Abgleich, Prüfung und Speichern laufen live. | – |
| Mehrdeutigkeit über die **Bestellhistorie** auflösen; zwischen Kasten und Fass **nie raten** | Nutzt vorhandenes Wissen; wo es keins gibt, entscheidet der Mensch. | Feste Standardannahme für alle Kunden. |
| Ähnliche Kundennamen (`difflib`, Ähnlichkeit ≥ 0,75) nur **mit Warnung** übernehmen | Kurzformen und Tippfehler werden erkannt, aber nie still zugeordnet. | – |
| **Drei Stufen:** Fehler blockieren, Warnungen bitten um Prüfung, Infos zur Kenntnis | Nicht jede Auffälligkeit ist ein Fehler; bei Warnungen entscheidet der Mensch. | – |
| **Abgleich gibt nur Hinweise, die Prüfung entscheidet** | Nur die Prüfung läuft nach jeder Änderung des Menschen neu; sonst blieben veraltete Fehler stehen. Durch einen Test abgesichert. | – |
| „Nicht freigegeben“ = **kein Preis** für die Kundengruppe | Die Stammdaten steuern das Verhalten – keine Sonderregel im Code. | – |
| Mengenwarnung ab dem **Doppelten** der bisher größten Menge des Kunden | Einfach, erklärbar und findet typische Tippfehler (Zehnerstelle). | – |
| **Human-in-the-Loop:** Speichern erst nach Klick, gesperrt solange Fehler bestehen | Die KI spart Tipparbeit, die Verantwortung bleibt beim Menschen. | Vollautomatische Übernahme. |
| `save_order` **prüft erneut** und schreibt Kopf und Positionen in **einer Transaktion** | Die Regeln greifen dort, wo gespeichert wird – unabhängig von der Oberfläche; nie ein Auftrag ohne Positionen. | – |
| **Kein Leergut** beim Erfassen buchen | Leergut bewegt sich erst bei der Lieferung (in der Praxis im ERP über den Lieferschein); die Erfassung zeigt das Pfand nur an. | – |
| Plausibilitäts-Check bewertet **nur die simulierte Historie** | Neue Aufträge prüft die Erfassung selbst (z. B. darf ein Fest auch im Oktober stattfinden). | – |
| Versionsnummer in den Widget-Schlüsseln | Eine neue Auswertung bekommt frische Eingabefelder. | – |
| In der Prüftabelle nur ein **kurzer Status**, vollständige Hinweise darunter | Lange Texte in Tabellenzellen werden abgeschnitten – Fehler müssen vollständig lesbar sein. | – |

## 6. Oberfläche im Fiori-Stil

| Entscheidung | Begründung | Alternative / Grenze |
|---|---|---|
| Gestaltung **angelehnt an SAP Fiori (Horizon)**: Launchpad-Kacheln, Shell Bar, Object-Page-Kopf, Filter Bar, Liste/Detail-Layout, Illustrated Message | Vertraute Muster für Anwender aus dem SAP-Umfeld; ruhige, kartenbasierte Oberfläche. | Streamlit-Standardoptik. |
| **Angelehnt, nicht kopiert:** eigenes Logo, eigene Farbwerte, keine SAP-Schrift, kein SAP-Logo | SAP ist eine geschützte Marke; die App soll nicht wie ein SAP-Produkt wirken. | – |
| Farben, Schriftgröße (17 px) und Radien über die **Theme-Einstellungen** in `config.toml`, hell und dunkel | Offizieller, update-sicherer Weg; nur der Rest per CSS. | Alles per CSS. |
| **Wenig CSS**, angesprochen über die von Streamlit dokumentierten Klassen `st-key-<key>` | Container mit `key` lassen sich gezielt gestalten; interne Klassennamen ändern sich bei Updates. | CSS kann bei Streamlit-Updates brechen – deshalb feste Paketversionen. |
| Oberflächen-Bausteine in **`ui.py`** außerhalb von `src/` | `src/` bleibt frei von Streamlit und testbar; das Aussehen ist an einer Stelle definiert. | – |
| **Eigene SVG-Illustrationen** statt Fotos | Keine Lizenzfragen, scharf in jeder Größe, passend zu hell und dunkel; Fiori selbst nutzt Illustrationen. | Lizenzfreie Fotos. |
| SVGs als `<img>` mit **eingebetteten Farben des aktuellen Modus** | `st.html` filtert `<svg>` heraus; ins `<img>` wirkt das Stylesheet der Seite nicht – deshalb schreibt `ui.py` die Farben direkt ins SVG. | – |
| Ganze Kachel klickbar („stretched link“) | Wie im Fiori-Launchpad; der Link bleibt ein normaler Streamlit-Seitenlink. | – |
| Diagramme mit **transparentem Hintergrund** | Gehen nahtlos in die Karte über, auf der sie stehen. | – |
| Heatmap **Blau ↔ Orange** | Rot ist bei Fiori für Fehler reserviert; ein Sommerhoch ist nichts Schlechtes. | Blau ↔ Rot. |
| Kennzahlen unter 1100 px Breite kleiner (Media Query) | Fünf Kennzahlen passen auch auf kleine Laptops. | – |

## 7. Betrieb

| Entscheidung | Begründung | Alternative / Grenze |
|---|---|---|
| Hosting auf **Streamlit Community Cloud**, direkt aus dem GitHub-Repository | Kostenlos und öffentlich erreichbar; jeder Push auf `main` aktualisiert die App automatisch. | Die App „schläft“ nach längerer Inaktivität und braucht beim Aufwecken einen Moment. |
| Datenbank wird **beim Start erzeugt**, nicht im Repository mitgeliefert | Keine Binärdatei in Git; dank festem Seed entstehen lokal (Windows) und in der Cloud (Linux) identische Daten. | Erster Start dauert etwas länger. |
| **Python-Version** in der Cloud wie lokal (3.13), feste Paketversionen | Gleiche Umgebung wie in der Entwicklung – keine Überraschungen durch andere Versionen. | – |
| **Keine Secrets** für den Demo-Modus | Die Demo funktioniert ohne API-Schlüssel; ein Schlüssel für den echten KI-Modus kommt ausschließlich in die Secrets-Verwaltung der Cloud, nie in den Code. | – |

## 8. Bewusste Grenzen

- **Auftragsnummer = höchste Nummer + 1** – ausreichend für die Demo, nicht für viele
  gleichzeitige Nutzer (dafür: Nummernkreis bzw. Sequenz in der Datenbank).
- **SQLite und flüchtiger Speicher:** Auf Streamlit Community Cloud gehen erfasste Aufträge
  beim Neustart der App verloren; die simulierte Historie wird automatisch neu erzeugt.
- **Keine Benutzerverwaltung, keine Kreditlimitprüfung, keine Lieferabwicklung** – im
  Echtbetrieb gehört die Buchung in das ERP-System.
- **Simulierte Daten:** Alle Firmen, Personen und Zahlen sind frei erfunden.
