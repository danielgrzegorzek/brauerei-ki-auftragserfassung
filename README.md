# 🍺 Bräu am Stein – Vom WhatsApp-Chaos zum sauberen Auftrag

KI-gestützte Auftragserfassung und Vertriebsanalyse für eine fiktive Familienbrauerei in Niederbayern.

**▶ Live-Demo: [braeu-am-stein.streamlit.app](https://braeu-am-stein.streamlit.app/)** – kostenlos testbar, ohne Anmeldung.
Im Modus **KI live** wertet Claude auch eigene Nachrichten aus (begrenzte Anzahl pro Tag).
*(Nach längerer Pause „schläft“ die App – dann einmal auf „Yes, get this app back up“ klicken und kurz warten.)*

---

## Das Problem

Wirtshäuser, Getränkehändler, Supermärkte und Festveranstalter bestellen bei der Brauerei per
Telefon, E-Mail und immer öfter per **WhatsApp** – als Freitext, oft im Dialekt:

> *„Servus, bräucht für Freitag 5 Fass Helles und 10 Kasten Weißbier. Pfiat di, Sepp“*

Der Vertriebsinnendienst tippt jede Bestellung von Hand ab, ergänzt fehlende Angaben, prüft
Preise und rechnet Leergut und Pfand mit. Das kostet Zeit und ist fehleranfällig – besonders in
der Hochsaison mit Biergärten und Volksfesten.

## Die Lösung

**1. KI-Auftragserfassung mit Human-in-the-Loop**

```
Freitext ─► KI versteht die Nachricht ─► Abgleich mit Stammdaten ─► Prüfung der Regeln ─► Mensch bestätigt
```

- Die KI (**Claude Sonnet 5**) übersetzt die Nachricht in ein festes Format (Kunde, Liefertermin,
  Sorte, Einheit, Menge) – auch Dialekt wie „3 Fassl Weizn“ oder „5 Kistn Spezi“. Die API garantiert
  dieses Format (strukturierte Ausgabe); Sorten außerhalb des Sortiments sind gar nicht möglich.
- Normaler, getesteter Code ordnet Kunde und Artikel den Stammdaten zu (fehlt die Fassgröße,
  entscheidet die Bestellhistorie) und prüft die Geschäftsregeln: Freigabe des Artikels für die
  Kundengruppe, Liefertermin, auffällige Mengen, offenes Leergut.
- Der Mensch sieht einen fertigen Vorschlag, kann alles ändern und bestätigt. Bei Fehlern ist das
  Speichern gesperrt, bei Warnungen entscheidet er selbst.

**Grundsatz:** *Die KI versteht, der Code entscheidet, der Mensch bestätigt.*

**2. Vertriebs-Dashboard**

Umsatz, Absatz in Hektolitern und offenes Pfand mit Vorjahresvergleich; Umsatz je Monat,
Kundengruppe und Artikel; Saisonalität je Warengruppe; Entwicklung der Bestellkanäle;
Top-Kunden und offenes Leergut je Kunde. Jedes Diagramm hat eine Tabellenansicht und eine
automatisch berechnete Kernaussage.

**3. Datenbasis**

Zwei Jahre simulierte Aufträge mit Saisonalität, Preiserhöhung, Leergut-Kreislauf und
steigendem WhatsApp-Anteil – reproduzierbar erzeugt und durch 13 fachliche
Plausibilitätsprüfungen abgesichert.

## Demo ausprobieren

Auf der Seite **KI-Auftragserfassung** stehen sieben Beispielnachrichten bereit:

| Beispiel | Was passiert |
|---|---|
| Stammwirt per WhatsApp | Fehlende Fassgröße wird aus der Bestellhistorie ergänzt |
| Großhändler per E-Mail | Sauberer Fall – nur noch bestätigen |
| Biergarten im Dialekt | „Weizn“, „Kistn Spezi“, „bis morgn“ werden richtig zugeordnet |
| Feuerwehrfest (Telefonnotiz) | „Limo gemischt“ ist mehrdeutig – der Mensch wählt den Artikel |
| Supermarkt möchte Fässer | Artikel für die Kundengruppe nicht freigegeben – blockiert |
| Tippfehler bei der Menge | 50 statt 5 Fässer – Warnung aus der Historie |
| Neukunde, unbekannter Artikel | Kunde nicht im Stamm, Artikel nicht im Sortiment – blockiert |

Zwei Modi:

- **Demo:** Die KI-Antworten sind vorbereitet – im exakt gleichen Format, das die echte KI liefert.
  Kostenlos und ohne API-Schlüssel.
- **KI live:** Claude wertet die Beispiele wirklich aus – oder eine **eigene Nachricht**. Eine
  Auswertung dauert etwa 3 Sekunden und kostet rund 1 US-Cent; angezeigt werden Dauer und Kosten.
  Kostenschutz: höchstens 1.000 Zeichen je Nachricht, 5 Auswertungen je Besuch, 30 je Tag.

In beiden Modi laufen Abgleich, Prüfung und Speichern live; gespeicherte Aufträge erscheinen sofort
im Dashboard.

**Wie gut ist die KI?** Ein Evaluationsskript schickt die sieben Beispiele an Claude und vergleicht
das Ergebnis mit dem geprüften Soll: **7 von 7 Aufträgen identisch** (Kunde, Termin, Artikel, Mengen),
Kosten ca. 6 US-Cent je Lauf → [docs/EVALUATION.md](docs/EVALUATION.md). Der erste Lauf ergab nur
4 von 7 – die gefundenen Schwächen (Kundennamen wie „FF Hengersberg“, Wochentagsrechnung) wurden
im Code und im Prompt behoben.

## Technik

| Bereich | Werkzeuge |
|---|---|
| Oberfläche | Streamlit (mehrseitig), Plotly – Gestaltung angelehnt an die SAP-Fiori-Designrichtlinien (Launchpad, Object Page, Illustrated Message), eigene SVG-Illustrationen |
| Daten | SQLite, pandas |
| KI | Claude Sonnet 5 über die Claude-API (offizielles `anthropic`-Paket, strukturierte Ausgabe), Anbieter austauschbar |
| Qualität | pytest (111 Tests, KI-Aufrufe mit Schein-Client), Plausibilitäts-Check der Daten, Live-Evaluation der KI |
| Sprache | Python 3.13 |

Warum welche Entscheidung getroffen wurde – mit Begründung und verworfener Alternative –
steht in **[docs/ENTSCHEIDUNGEN.md](docs/ENTSCHEIDUNGEN.md)**.

## Projektstruktur

```
app.py        Einstieg: Datenbank sicherstellen, Gestaltung laden, Seitennavigation
ui.py         Oberflächen-Bausteine im Fiori-Stil (Seitenkopf, Kacheln, Illustrationen)
assets/       Logo, SVG-Illustrationen, Stylesheet
pages/        Oberfläche: Start, Dashboard, KI-Auftragserfassung
src/          Logik ohne Oberfläche: Datenmodell, Datengenerator, Auswertungen, Auftragserfassung, KI-Anbindung
tests/        automatische Tests
tools/        Evaluation der KI-Auswertung
docs/         Designentscheidungen, Evaluationsbericht
```

## Lokal starten

Voraussetzung: Python 3.13. Die Datenbank wird beim ersten Start automatisch erzeugt.

```bash
git clone https://github.com/danig204/brauerei-ki-auftragserfassung.git
cd brauerei-ki-auftragserfassung
python -m venv .venv
```

Windows (PowerShell):

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Tests: `pip install -r requirements-dev.txt`, dann `python -m pytest`.

**Optional – KI live lokal:** Datei `.streamlit/secrets.toml` anlegen (steht in der `.gitignore`)
mit der Zeile `ANTHROPIC_API_KEY = "sk-ant-…"` (eigener Schlüssel aus der Anthropic Console).
Ohne Schlüssel läuft die App vollständig im Demo-Modus. Evaluation:
`python -m tools.evaluate_extraction` (kostet ca. 6 US-Cent).

## Stand und nächste Schritte

- [x] Datenbasis mit Plausibilitäts-Check
- [x] Vertriebs-Dashboard
- [x] KI-Auftragserfassung im Demo-Modus
- [x] Echter KI-Modus mit der Claude-API, Kostenschutz und Evaluation
- [ ] Prozessseite: Ist- vs. Soll-Prozess und Übergabe an SAP S/4HANA
- [ ] Regelbasierter Parser als Vergleich „Regeln vs. KI“

## Hinweise

- **Alle Firmen, Personen und Zahlen sind frei erfunden.**
- Im Modus **KI live** werden eingegebene Texte zur Auswertung an Anthropic übertragen – bitte keine
  echten personenbezogenen Daten eingeben.
- Die Oberfläche ist an die SAP-Fiori-Designrichtlinien angelehnt; Logo und Illustrationen sind
  eigene Entwürfe. Es handelt sich nicht um ein SAP-Produkt.
- Entwickelt mit Claude Code als KI-Pair-Programming-Werkzeug.
