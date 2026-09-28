"""MINILIIGA-JULKISUUSSAANTO (Villen kysymys 4.9.2026, lähde
x.com/fplshattered/status/2095596736769323032 + heidän podcast-sivunsa).

FPL Shattered julkaisi podcast-jakson jossa kayttajan oma mini-liiga kaydaan
lapi NIMELTA (kaikki 10-20 manageria), vaikka vain liigan OMISTAJA suostui
esiintymaan. Heidan omassa demoliigassaan nimet ovat anonymisoitu ("Tom B.",
"Priya R.") - raja on heille tuttu, video on se paikka jossa se lipsuu.

GoalIQ:lla ei ole viela mini-liiga-podcast-tyyppista julkista formaattia,
mutta `/api/fantasy/league/{id}` palauttaa jo FPL:n oman `player_name`-kentan
(manageri koko nimella) MiniLeague- ja RivalPanel-pinnoille, ja se on tasan
se kentta josta tallainen ominaisuus joskus lukisi. Tama moduuli tekee
vaarasta valinnasta mahdottoman SILLOIN KUN se rakennetaan (saanto 6a):
yksi lukija (`public_manager_label`) joka ei voi palauttaa koko nimea
vahingossa, ja yksi portti (`assert_no_other_manager_full_names`) joka
kaataa buildin jos joku silti liittaa raakaa `player_name`-tekstia suoraan
julkiseen korttiin.

SAANTO (koskee MiniLeague-, RivalPanel- ja EdgeMode-pintoja seka
jakokortteja):
1. Tuotteen SISALLA nimet nakyvat vain saman liigan jasenille - sama mita
   FPL itse nayttaa. Tama moduuli ei koske sita nakymaa.
2. JULKISELLA pinnalla (X, video, jakokortti, artikkeli) nimeltä vain se
   joka antoi liigan; muut `public_manager_label`-muodossa (etunimi +
   sukunimen alkukirjain).
3. Pejoratiivista lappua ei kiinniteta nimettyyn ihmiseen - editorinen
   paatos, ei tama moduuli mittaa.
4. Yhden klikkauksen poistumistie - tuoteominaisuus, ei tama moduuli mittaa.

Tama moduuli mittaa saannot 1-2 mekaanisesti. 3-4 jaavat julkaisutarkistajan
ja tuotesuunnittelun harkintaan.
"""
from __future__ import annotations

import re


def public_manager_label(player_name: str | None, is_submitter: bool) -> str:
    """Manageri julkisella pinnalla: koko nimi VAIN liigan antajalle.

    Muu manageri -> "Etunimi S." (etunimi + sukunimen ensimmainen kirjain).
    Nimi jolla ei ole sukunimea (yksi sana) jaa sellaisenaan - lyhentaminen
    yhdesta sanasta ei suojaisi mitaan eika ole tarkoitus paljastaa enempaa
    kuin alkuperainen nimi jo teki.
    """
    name = (player_name or "").strip()
    if not name:
        return ""
    if is_submitter:
        return name
    parts = name.split()
    if len(parts) < 2:
        return parts[0] if parts else ""
    etunimi = parts[0]
    sukunimen_alku = parts[-1][0]
    return f"{etunimi} {sukunimen_alku}."


class OtherManagerNameLeaked(ValueError):
    """Julkinen teksti sisaltaa toisen managerin koko nimen. Ei ohitusta -
    tama on tasan se vika jonka takia taman moduulin piti syntya."""


def assert_no_other_manager_full_names(
    public_text: str,
    all_manager_names: list[str],
    submitter_name: str | None = None,
) -> None:
    """Kaataa buildin jos `public_text` sisaltaa jonkun MUUN managerin kuin
    `submitter_name`in koko nimen (etu + suku, sanarajalla, ei osamerkkina).

    Tama on se portti joka kaataa buildin ENNEN kuin teksti paatyy
    julkaisutarkistajalle asti - sama periaate kuin `assert_public_copy`
    (build_fpl_page.py): vaara ei saa paasta niin pitkalle etta se on
    ihmisen luettava vasta lopussa.
    """
    for name in all_manager_names:
        name = (name or "").strip()
        if not name or (submitter_name and name == submitter_name.strip()):
            continue
        parts = name.split()
        if len(parts) < 2:
            # Yksisanainen "nimi" ei voi vuotaa etu+suku-parina; ei koske tata porttia.
            continue
        pattern = r"\b" + r"\s+".join(re.escape(p) for p in parts) + r"\b"
        if re.search(pattern, public_text, flags=re.IGNORECASE):
            raise OtherManagerNameLeaked(
                f"public text names a non-submitting manager in full: {name!r}")
