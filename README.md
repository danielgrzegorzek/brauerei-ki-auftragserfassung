# 🍺 Bräu am Stein – Vom WhatsApp-Chaos zum sauberen Auftrag

KI-gestützte Auftragserfassung und Vertriebsanalyse für eine fiktive Familienbrauerei in Niederbayern.

**▶ Live-Demo:** *Link folgt* – kostenlos testbar, kein API-Schlüssel nötig.

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

- Die KI übersetzt die Nachricht in ein festes Format (Kunde, Liefertermin, Sorte, Einheit, Menge) –
  auch Dialekt wie „3 Fassl Weizn“ oder „5 Kistn Spezi“.
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

Im **Demo-Modus** sind die KI-Antworten vorbereitet – im exakt gleichen Format, das die echte
KI liefert. Abgleich, Prüfung und Speichern laufen live; gespeicherte Aufträge erscheinen sofort
im Dashboard.

## Technik

| Bereich | Werkzeuge |
|---|---|
| Oberfläche | Streamlit (mehrseitig), Plotly |
| Daten | SQLite, pandas |
| KI | Claude-API (Anthropic), austauschbar gebaut – *echter KI-Modus in Arbeit* |
| Qualität | pytest (93 Tests), Plausibilitäts-Check der Daten |
| Sprache | Python 3.13 |

Warum welche Entscheidung getroffen wurde – mit Begründung und verworfener Alternative –
steht in **[docs/ENTSCHEIDUNGEN.md](docs/ENTSCHEIDUNGEN.md)**.

## Projektstruktur

```
app.py        Einstieg: Datenbank sicherstellen, Seitennavigation
pages/        Oberfläche: Start, Dashboard, KI-Auftragserfassung
src/          Logik ohne Oberfläche: Datenmodell, Datengenerator, Auswertungen, Auftragserfassung
tests/        automatische Tests
docs/         Designentscheidungen
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

## Stand und nächste Schritte

- [x] Datenbasis mit Plausibilitäts-Check
- [x] Vertriebs-Dashboard
- [x] KI-Auftragserfassung im Demo-Modus
- [ ] Echter KI-Modus mit der Claude-API
- [ ] Prozessseite: Ist- vs. Soll-Prozess und Übergabe an SAP S/4HANA
- [ ] Regelbasierter Parser als Vergleich „Regeln vs. KI“

## Hinweise

- **Alle Firmen, Personen und Zahlen sind frei erfunden.**
- Entwickelt mit Claude Code als KI-Pair-Programming-Werkzeug.
