# -*- coding: utf-8 -*-
"""SPA-VALUE-EVENT-TUPLAKIRJAUS (7.9.2026): Value.svelte haki uudelleen ja
capturasi 'fantasy_tools_used' KERRAN PER NAPPAINPAINALLUS.

TAUSTA. `Value.svelte`:n haku-`$effect` lukee `currentEntryId()`, joka
palauttaa jaetun `fplEntry.entry`-kentan (RateTeam/TransferPlanner bindaavat
siihen suoraan) heti kun se lapaisee loyhan `VALID = /^\\d{1,10}$/`-tarkistuksen
- eli JOKAINEN numero riittaa. Muut tyokalut hakevat vain submitilla, mutta
Value haki suoraan efektissa. Seuraus: FPL-entryn kirjoittaminen ("116920")
tuotti kuusi hakua ja kuusi 'fantasy_tools_used'-eventtia yhdesta oikeasta
kaytosta, joten Value nayttaisi mittareissa suositummalta kuin se on.

Korjaus: sama debounssikaava kuin `draft.ts`:n `pushRemoteDraftSoon` -
`setTimeout` + edellisen `clearTimeout`, joten vain viimeisin (asettunut)
entry-arvo hakee ja kirjaa eventin.

Portti lukee Svelte-lahdetta tekstina, koska SPA:lla ei ole omaa
testiajuria. Jokaiselle vahdille on negatiivinen kontrolli joka osoittaa
etta se kaatuu vanhasta, debounssittomasta muodosta.
"""
import re
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src" / "lib"
       / "components" / "Value.svelte")


@pytest.fixture(scope="module")
def s() -> str:
    assert SRC.exists(), f"{SRC} puuttuu - porttia ei voi todentaa (fail-closed)"
    return SRC.read_text(encoding="utf-8")


def _effect_block(s: str) -> str:
    """Poimii fetchValue-kutsun sisaltavan $effect-lohkon.

    Karkea mutta riittava: hakee ekan '$effect(() => {' jonka rungossa on
    'fetchValue(' ja katkaisee seuraavaan '});'-riviin.
    """
    for m in re.finditer(r"\$effect\(\(\) => \{", s):
        loppu = s.find("\n\t});", m.end())
        assert loppu != -1, "$effect-lohkoa ei voitu rajata"
        lohko = s[m.start():loppu]
        if "fetchValue(" in lohko:
            return lohko
    raise AssertionError("fetchValue-kutsua sisaltavaa $effect-lohkoa ei loydy")


def test_hakuefekti_on_debounssattu(s):
    lohko = _effect_block(s)
    assert "setTimeout(" in lohko, "fetchValue ei ole setTimeoutin sisalla"
    assert "clearTimeout(fetchTimer)" in lohko, (
        "efekti ei tyhjenna edellista ajastinta - jokainen muutos ajaisi silti oman hakunsa")


def test_fetchvalue_ei_ole_suoraan_efektin_runnossa(s):
    """NEGATIIVINEN KONTROLLI: juuri se muoto joka oli rikki 7.9 asti -
    fetchValue kutsuttiin heti $effectin sisalla, ei ajastimen callbackissa."""
    lohko = _effect_block(s)
    # Vanha rikki muoto: "loading = true;\n\t\tfetchValue(" ilman setTimeoutia
    # valissa. Jos fetchValue seuraa suoraan loading=true -riviaan ilman
    # setTimeout-sanaa niiden valissa, debounssi puuttuu.
    valissa = lohko.split("fetchValue(", 1)[0]
    assert "setTimeout(" in valissa, (
        "fetchValue kutsutaan efektin rungossa suoraan - debounssi puuttuu "
        "(tama on tasan 7.9-asti vallinnut rikki muoto)")


def test_timer_nollataan_myos_efektin_siivouksessa(s):
    """Efektin tulee palauttaa siivousfunktio joka tyhjentaa ajastimen, jottei
    komponentin purku (esim. valilehden vaihto) jata viivastettya hakua
    roikkumaan."""
    lohko = _effect_block(s)
    assert re.search(r"return \(\) => \{\s*if \(fetchTimer\) clearTimeout\(fetchTimer\);",
                      lohko), "efekti ei siivoa ajastinta purkautuessaan"


def test_debounssi_ei_estä_myöhempää_hakua():
    """NEGATIIVINEN KONTROLLI itse tunnistimelle: pelkka `setTimeout(...)`
    jossain muualla tiedostossa (esim. jaon renderöinnissa) ei saa riittaa -
    tunnistimen on katsottava NIMENOMAAN fetchValuen ymparilta rajattua
    lohkoa, ei koko tiedostoa."""
    huono = (
        "\tfunction unrelated() {\n"
        "\t\tsetTimeout(() => {}, 500);\n"
        "\t}\n"
        "\t$effect(() => {\n"
        "\t\tconst entry = currentEntryId();\n"
        "\t\tloading = true;\n"
        "\t\tfetchValue(entry)\n"
        "\t\t\t.then((d) => (data = d));\n"
        "\t});\n"
    )
    lohko = _effect_block(huono)
    valissa = lohko.split("fetchValue(", 1)[0]
    assert "setTimeout(" not in valissa, (
        "tunnistin osui väärään setTimeoutiin - se ei erota debounssattua "
        "hakua vahingossa vierella olevasta ajastimesta")
