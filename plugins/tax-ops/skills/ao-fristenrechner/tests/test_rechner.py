"""Tests für core/calc/ao_fristen/rechner.py — AO-Fristberechnung (P3/P4).

Deckt ab: Einspruchsfrist (Bekanntgabefiktion, Fiktion-vor-2025-Ablehnung,
Werktag-/Samstag-/Feiertag-Verschiebung je Bundesland, Monatsende-Fall
§ 188 Abs. 3 BGB, Jahresfrist § 356 Abs. 2 AO), Abgabefrist-Tabelle je VZ
(inkl. Wochenend-Verschiebung, Regelfrist ab VZ 2025, Land-/Forstwirte-
Ablehnung), Vorauszahlungstermine (fixe Termine, Wochenend-Verschiebung,
Dauerfristverlängerung, SV-Bankarbeitstag ohne § 108-Verweis) und
Verspätungszuschlag (Mindestbetrag, Höchstbetrag, angefangene Monate).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from ao_fristen import rechner as r


# --------------------------------------------------------------------------
# Baustein 1 — Einspruchsfrist
# --------------------------------------------------------------------------

def test_einspruch_direktes_bekanntgabedatum_werktag_kein_wochenende():
    erg = r.berechne_einspruchsfrist(bundesland="NW", bekanntgabe_datum=dt.date(2026, 6, 1))
    # 01.06.2026 (Mo) -> Fristbeginn 02.06., Ende rechnerisch 01.07.2026 (Mi, Werktag)
    assert erg.fristbeginn == dt.date(2026, 6, 2)
    assert erg.fristende_rechnerisch == dt.date(2026, 7, 1)
    assert erg.fristende == dt.date(2026, 7, 1)
    assert erg.verschoben is False


def test_einspruch_fristende_auf_samstag_verschiebt_auf_montag():
    # Bekanntgabe 15.01.2026 (Do) -> Ende rechnerisch 15.02.2026 (So) -> 16.02.2026 (Mo)
    erg = r.berechne_einspruchsfrist(bundesland="NW", bekanntgabe_datum=dt.date(2026, 1, 15))
    assert erg.fristende_rechnerisch == dt.date(2026, 2, 15)
    assert erg.fristende == dt.date(2026, 2, 16)
    assert erg.verschoben is True


def test_einspruch_fristende_auf_bundesweitem_feiertag():
    # Bekanntgabe 03.09.2026 -> Ende rechnerisch 03.10.2026: Tag der Deutschen
    # Einheit UND ein Samstag zugleich -> Verschiebung über Sonntag auf Montag.
    erg = r.berechne_einspruchsfrist(bundesland="SN", bekanntgabe_datum=dt.date(2026, 9, 3))
    assert erg.fristende_rechnerisch == dt.date(2026, 10, 3)
    assert erg.fristende == dt.date(2026, 10, 5)


def test_einspruch_fristende_auf_landesspezifischen_feiertag():
    # Reformationstag (31.10.2028, ein Dienstag — kein Wochenende) ist in SN
    # gesetzlicher Feiertag, in BY nicht: die § 108 Abs. 3 AO-Verschiebung
    # der gemeinsamen Werktag-Kette greift nur in SN.
    kette_sn: list = []
    warnungen_sn: list = []
    ende_sn = r._verschiebe_mit_kette(dt.date(2028, 10, 31), "SN", kette_sn, warnungen_sn)
    assert ende_sn == dt.date(2028, 11, 1)

    kette_by: list = []
    warnungen_by: list = []
    ende_by = r._verschiebe_mit_kette(dt.date(2028, 10, 31), "BY", kette_by, warnungen_by)
    assert ende_by == dt.date(2028, 10, 31)


def test_einspruch_monatsende_ueberlauf_paragraf_188_abs_3():
    # Bekanntgabe 31.01.2026 (Sa) -> Ende hätte "31.02" (nicht existent) ->
    # letzter Tag Februar (28., da 2026 kein Schaltjahr).
    erg = r.berechne_einspruchsfrist(bundesland="NW", bekanntgabe_datum=dt.date(2026, 1, 31))
    assert erg.fristende_rechnerisch == dt.date(2026, 2, 28)
    normen = [s.norm for s in erg.rechenkette]
    assert "§ 188 Abs. 3 BGB" in normen


def test_einspruch_jahresfrist_356():
    erg = r.berechne_einspruchsfrist(
        bundesland="NW", bekanntgabe_datum=dt.date(2026, 1, 15), jahresfrist=True)
    assert erg.fristende_rechnerisch == dt.date(2027, 1, 15)


def test_einspruch_aufgabe_zur_post_vor_2025_nicht_abgedeckt():
    with pytest.raises(r.AONichtAbgedeckt):
        r.berechne_einspruchsfrist(
            bundesland="NW", aufgabe_zur_post_datum=dt.date(2024, 12, 31))


def test_einspruch_aufgabe_zur_post_ab_2025_vier_tage():
    erg = r.berechne_einspruchsfrist(
        bundesland="NW", aufgabe_zur_post_datum=dt.date(2025, 1, 1))
    assert erg.bekanntgabe_datum == dt.date(2025, 1, 5)


def test_einspruch_fiktion_verschieben_default_false():
    # Aufgabe Di 03.02.2026 -> Fiktionstag Sa 07.02.2026 -> ohne Option NICHT verschoben.
    erg = r.berechne_einspruchsfrist(
        bundesland="BY", aufgabe_zur_post_datum=dt.date(2026, 2, 3))
    assert erg.bekanntgabe_datum == dt.date(2026, 2, 7)
    assert any("nicht verschoben" in h for h in erg.hinweise)


def test_einspruch_fiktion_verschieben_true_verschiebt_fiktionstag():
    erg = r.berechne_einspruchsfrist(
        bundesland="BY", aufgabe_zur_post_datum=dt.date(2026, 2, 3),
        fiktion_verschieben=True)
    # Fiktionstag Sa 07.02. -> So 08.02. -> Mo 09.02.
    assert erg.bekanntgabe_datum == dt.date(2026, 2, 9)
    assert any("fiktion_verschieben=true" in h for h in erg.hinweise)


def test_einspruch_verlangt_genau_ein_datumsfeld():
    with pytest.raises(r.AOEingabeFehler):
        r.berechne_einspruchsfrist(bundesland="NW")
    with pytest.raises(r.AOEingabeFehler):
        r.berechne_einspruchsfrist(
            bundesland="NW", bekanntgabe_datum=dt.date(2026, 1, 1),
            aufgabe_zur_post_datum=dt.date(2026, 1, 1))


def test_einspruch_unbekanntes_bundesland():
    with pytest.raises(r.AOEingabeFehler):
        r.berechne_einspruchsfrist(bundesland="XX", bekanntgabe_datum=dt.date(2026, 1, 1))


# --------------------------------------------------------------------------
# Baustein 2 — Abgabefrist
# --------------------------------------------------------------------------

@pytest.mark.parametrize("vz, gruppe, erwartet_nominal", [
    (2020, "nicht_beraten", dt.date(2021, 10, 31)),
    (2021, "beraten", dt.date(2023, 8, 31)),
    (2022, "land_forstwirt", dt.date(2024, 12, 31)),
    (2023, "nicht_beraten", dt.date(2024, 8, 31)),
    (2024, "beraten", dt.date(2026, 4, 30)),
])
def test_abgabefrist_egao_tabelle_je_vz(vz, gruppe, erwartet_nominal):
    erg = r.berechne_abgabefrist(veranlagungszeitraum=vz, gruppe=gruppe, bundesland="NW")
    assert erg.nominal_datum == erwartet_nominal


def test_abgabefrist_vz2023_beraten_samstag_verschiebt_auf_montag():
    # Dossier-Beispiel: 31.05.2025 ist ein Samstag -> Montag 02.06.2025.
    erg = r.berechne_abgabefrist(veranlagungszeitraum=2023, gruppe="beraten", bundesland="NW")
    assert erg.nominal_datum == dt.date(2025, 5, 31)
    assert erg.nominal_datum.weekday() == 5
    assert erg.fristende == dt.date(2025, 6, 2)
    assert erg.verschoben is True


def test_abgabefrist_vz2025_regelfrist_nicht_beraten():
    erg = r.berechne_abgabefrist(
        veranlagungszeitraum=2025, gruppe="nicht_beraten", bundesland="NW")
    assert erg.nominal_datum == dt.date(2026, 7, 31)


def test_abgabefrist_vz2025_regelfrist_beraten():
    erg = r.berechne_abgabefrist(veranlagungszeitraum=2025, gruppe="beraten", bundesland="NW")
    assert erg.nominal_datum == dt.date(2027, 2, 28)


def test_abgabefrist_vz2025_land_forstwirt_nicht_abgedeckt():
    with pytest.raises(r.AONichtAbgedeckt):
        r.berechne_abgabefrist(
            veranlagungszeitraum=2025, gruppe="land_forstwirt", bundesland="NW")


def test_abgabefrist_vor_2020_nicht_abgedeckt():
    with pytest.raises(r.AONichtAbgedeckt):
        r.berechne_abgabefrist(veranlagungszeitraum=2019, gruppe="beraten", bundesland="NW")


def test_abgabefrist_unbekannte_gruppe():
    with pytest.raises(r.AOEingabeFehler):
        r.berechne_abgabefrist(veranlagungszeitraum=2024, gruppe="unbekannt", bundesland="NW")


# --------------------------------------------------------------------------
# Baustein 3 — Vorauszahlungs-/Anmeldetermine
# --------------------------------------------------------------------------

def test_vorauszahlung_est_feste_termine():
    erg = r.berechne_vorauszahlungstermine(jahr=2026, steuerart="est", bundesland="NW")
    daten = [t.datum for t in erg.termine]
    assert daten == [dt.date(2026, 3, 10), dt.date(2026, 6, 10),
                     dt.date(2026, 9, 10), dt.date(2026, 12, 10)]


def test_vorauszahlung_termin_auf_wochenende_wird_verschoben():
    # ESt-Termin 10.03.2029 ist ein Samstag -> Montag 12.03.2029.
    assert dt.date(2029, 3, 10).weekday() == 5
    erg = r.berechne_vorauszahlungstermine(jahr=2029, steuerart="est", bundesland="NW")
    erster = erg.termine[0]
    assert erster.nominal_datum == dt.date(2029, 3, 10)
    assert erster.datum == dt.date(2029, 3, 12)


def test_vorauszahlung_ustva_monatlich_zwoelf_termine():
    erg = r.berechne_vorauszahlungstermine(
        jahr=2026, steuerart="ustva", bundesland="NW", rhythmus="monatlich")
    assert len(erg.termine) == 12
    assert erg.termine[0].nominal_datum == dt.date(2026, 2, 10)  # Jan-Ende + 10 Tage


def test_vorauszahlung_ustva_quartalsweise_vier_termine():
    erg = r.berechne_vorauszahlungstermine(
        jahr=2026, steuerart="ustva", bundesland="NW", rhythmus="quartalsweise")
    assert len(erg.termine) == 4
    assert erg.termine[0].nominal_datum == dt.date(2026, 4, 10)  # Q1-Ende (31.03) + 10 Tage


def test_vorauszahlung_ustva_dauerfristverlaengerung_plus_ein_monat():
    ohne = r.berechne_vorauszahlungstermine(
        jahr=2026, steuerart="ustva", bundesland="NW", rhythmus="monatlich")
    mit = r.berechne_vorauszahlungstermine(
        jahr=2026, steuerart="ustva", bundesland="NW", rhythmus="monatlich",
        dauerfristverlaengerung=True)
    assert mit.termine[0].nominal_datum == dt.date(2026, 3, 10)
    assert ohne.termine[0].nominal_datum == dt.date(2026, 2, 10)


def test_vorauszahlung_dauerfristverlaengerung_nur_bei_ustva():
    with pytest.raises(r.AOEingabeFehler):
        r.berechne_vorauszahlungstermine(
            jahr=2026, steuerart="est", bundesland="NW", dauerfristverlaengerung=True)


def test_vorauszahlung_periodisch_verlangt_rhythmus():
    with pytest.raises(r.AOEingabeFehler):
        r.berechne_vorauszahlungstermine(jahr=2026, steuerart="ustva", bundesland="NW")


def test_vorauszahlung_zm_monatlich_25_tage():
    erg = r.berechne_vorauszahlungstermine(jahr=2026, steuerart="zm", bundesland="NW")
    assert len(erg.termine) == 12
    assert erg.termine[0].nominal_datum == dt.date(2026, 2, 25)  # 31.01. + 25 Tage


def test_vorauszahlung_sv_zwoelf_termine_kein_108_verweis():
    erg = r.berechne_vorauszahlungstermine(jahr=2026, steuerart="sv", bundesland="NW")
    assert len(erg.termine) == 12
    for t in erg.termine:
        # Nominal- und Enddatum sind identisch: keine § 108 Abs. 3 AO-Verschiebung.
        assert t.datum == t.nominal_datum
        assert t.datum.weekday() < 5
    normen = [s.norm for s in erg.rechenkette]
    assert all(n != "§ 108 Abs. 3 AO" for n in normen)


def test_vorauszahlung_sv_ist_stets_werktag_ohne_bundesweiten_feiertag():
    # Dezember: drittletzter Bankarbeitstag darf nicht der 25./26.12. sein.
    erg = r.berechne_vorauszahlungstermine(jahr=2026, steuerart="sv", bundesland="NW")
    dezember = erg.termine[-1].datum
    assert dezember not in (dt.date(2026, 12, 25), dt.date(2026, 12, 26))


def test_vorauszahlung_unbekannte_steuerart():
    with pytest.raises(r.AOEingabeFehler):
        r.berechne_vorauszahlungstermine(jahr=2026, steuerart="unbekannt", bundesland="NW")


# --------------------------------------------------------------------------
# Baustein 4 — Verspätungszuschlag
# --------------------------------------------------------------------------

def test_verspaetungszuschlag_keine_verspaetung_kein_zuschlag():
    erg = r.berechne_verspaetungszuschlag(
        festgesetzte_steuer=10000, anzurechnende_betraege=0,
        abgabedatum=dt.date(2026, 7, 31), fristende=dt.date(2026, 7, 31))
    assert erg.angefangene_monate == 0
    assert erg.zuschlag_gesamt == Decimal("0")


def test_verspaetungszuschlag_mindestbetrag():
    erg = r.berechne_verspaetungszuschlag(
        festgesetzte_steuer=1000, anzurechnende_betraege=0,
        abgabedatum=dt.date(2026, 10, 15), fristende=dt.date(2026, 7, 31))
    assert erg.angefangene_monate == 3
    assert erg.zuschlag_pro_monat == Decimal("25")
    assert erg.zuschlag_gesamt == Decimal("75")


def test_verspaetungszuschlag_prozentsatz_ueber_mindestbetrag():
    erg = r.berechne_verspaetungszuschlag(
        festgesetzte_steuer=100000, anzurechnende_betraege=10000,
        abgabedatum=dt.date(2027, 1, 5), fristende=dt.date(2026, 7, 31))
    assert erg.bemessungsgrundlage == Decimal("90000")
    assert erg.angefangene_monate == 6
    assert erg.zuschlag_pro_monat == Decimal("225")
    assert erg.zuschlag_gesamt == Decimal("1350")


def test_verspaetungszuschlag_monatsbetrag_ungerundet_bis_zum_schluss():
    # § 152 Abs. 10 AO rundet nur den Gesamtbetrag, nicht Bemessungsgrundlage
    # oder Monatsbetrag: 0,25 % von 43.000 € = 107,50 € je Monat (ungerundet)
    # × 4 angefangene Monate = 430 € — nicht 428 € (Rundung des Monatsbetrags
    # auf 107 € vor der Multiplikation wäre falsch).
    erg = r.berechne_verspaetungszuschlag(
        festgesetzte_steuer=43000, anzurechnende_betraege=0,
        abgabedatum=dt.date(2026, 11, 15), fristende=dt.date(2026, 7, 31))
    assert erg.angefangene_monate == 4
    assert erg.zuschlag_pro_monat == Decimal("107.5")
    assert erg.zuschlag_gesamt == Decimal("430")


def test_verspaetungszuschlag_hoechstbetrag_gedeckelt():
    erg = r.berechne_verspaetungszuschlag(
        festgesetzte_steuer=5000000, anzurechnende_betraege=0,
        abgabedatum=dt.date(2030, 7, 31), fristende=dt.date(2026, 7, 31))
    assert erg.zuschlag_gesamt == Decimal("25000")
    assert erg.hoechstbetrag_erreicht is True


def test_verspaetungszuschlag_angefangener_monat_zaehlt_voll():
    # Genau 1 Tag über einer vollen Monatsgrenze -> 2 angefangene Monate,
    # nicht 1 (jeder angefangene Monat zählt voll).
    erg = r.berechne_verspaetungszuschlag(
        festgesetzte_steuer=1000, anzurechnende_betraege=0,
        abgabedatum=dt.date(2026, 9, 1), fristende=dt.date(2026, 7, 31))
    assert erg.angefangene_monate == 2


def test_verspaetungszuschlag_negative_werte_sind_eingabefehler():
    with pytest.raises(r.AOEingabeFehler):
        r.berechne_verspaetungszuschlag(
            festgesetzte_steuer=-1, anzurechnende_betraege=0,
            abgabedatum=dt.date(2026, 1, 1), fristende=dt.date(2026, 1, 1))


def test_verspaetungszuschlag_pflicht_ermessen_nur_hinweis_ungewertet():
    erg = r.berechne_verspaetungszuschlag(
        festgesetzte_steuer=1000, anzurechnende_betraege=0,
        abgabedatum=dt.date(2026, 10, 15), fristende=dt.date(2026, 7, 31))
    assert not hasattr(erg, "pflichtfall")
    assert any("Ermessensfall" in h for h in erg.hinweise)
