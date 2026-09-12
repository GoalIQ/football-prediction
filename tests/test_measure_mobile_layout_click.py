# -*- coding: utf-8 -*-
"""measure_mobile_layout: klikkaus ennen mittausta, ja peitetty napautus nakyy.

Tausta 12.9.2026: pelaajakortti avataan napautuksesta. Skripti mittasi vain
latautuneen sivun, joten dialogin ensimmainen ruutu olisi mitattu suljettuna,
ja JS-klikkaus onnistuu myos toisen kerroksen alla olevalle elementille.
Valeajuri: ei Chromea eika seleniumia CI:ssa.
"""
import pytest

from scripts import measure_mobile_layout as mml


class Vale:
    def __init__(self, dom=None, peitetty=()):
        self.dom = set(dom or ())
        self.peitetty = set(peitetty)
        self.loki = []

    def execute_cdp_cmd(self, cmd, args):
        self.loki.append(("cdp", cmd))

    def get(self, url):
        self.loki.append(("get", url))

    def execute_script(self, js, *args):
        if "document.querySelector(arguments[0]).click()" in js:
            self.loki.append(("click", args[0]))
            # Klikkaus avaa dialogin (kuten oikea kortti).
            self.dom.add("dialog[open]")
            return None
        if js.startswith("return !!document.querySelector"):
            self.loki.append(("poll", args[0]))
            return args[0] in self.dom
        if "elementFromPoint" in js:
            self.loki.append(("osuma", args[0]))
            return {"loytyi": args[0] in self.dom,
                    "klikattava": args[0] not in self.peitetty}
        if "const sels = arguments[0]" in js:
            self.loki.append(("mittaa", tuple(args[0])))
            auki = "dialog[open]" in self.dom
            return {"viewport": "390x844", "dpr": 3, "sivu_vaakascroll": False,
                    "sivun_leveys_px": 390, "sivun_korkeus_px": 900,
                    "elementit": {s: ({"korkeus_px": 700} if auki else None) for s in args[0]}}
        self.loki.append(("js", js[:30]))
        return None

    def save_screenshot(self, p):
        self.loki.append(("shot", p))

    def quit(self):
        self.loki.append(("quit",))


def _aja(vale, **kw):
    return mml.mittaa("http://x/", 390, 844, 3, ["dialog[open]"], None, None,
                      ajuri=lambda: vale, uni=lambda s: None, aikaraja_s=1.0, **kw)


def test_mittaus_tapahtuu_klikkauksen_ja_odotuksen_jalkeen():
    v = Vale(dom={".row", "button.name"})
    tulos = _aja(v, wait=".row", clicks=["button.name"], wait_after="dialog[open]")
    tapahtumat = [e[0] for e in v.loki]
    assert tapahtumat.index("click") < tapahtumat.index("mittaa"), v.loki
    # Dialogi mitattiin auki, ei suljettuna.
    assert tulos["elementit"]["dialog[open]"] == {"korkeus_px": 700}
    assert tulos["klikkaukset"] == [{"sel": "button.name", "loytyi": True, "klikattava": True}]
    assert tulos["odotukset"] == {".row": True, "dialog[open]": True}


def test_ilman_klikkausta_dialogi_on_suljettu():
    """Negatiivinen kontrolli: sama sivu ilman --clickia mittaa suljetun tilan."""
    v = Vale(dom={".row", "button.name"})
    tulos = _aja(v, wait=".row")
    assert tulos["elementit"]["dialog[open]"] is None
    assert tulos["klikkaukset"] == []


def test_peitetty_napautus_raportoidaan_ja_main_palauttaa_2(monkeypatch):
    v = Vale(dom={".row", "button.name"}, peitetty={"button.name"})
    tulos = _aja(v, wait=".row", clicks=["button.name"])
    assert tulos["klikkaukset"][0]["klikattava"] is False

    monkeypatch.setattr(mml, "mittaa", lambda *a, **k: tulos)
    assert mml.main(["http://x/", "--click", "button.name"]) == 2


def test_puuttuva_odotus_kaatuu_aaneen_eika_mittaa_tyhjaa():
    v = Vale(dom=set())
    with pytest.raises(SystemExit) as e:
        _aja(v, wait=".row")
    assert "--wait" in str(e.value)
    assert not any(ev[0] == "mittaa" for ev in v.loki)
    assert v.loki[-1] == ("quit",), "ajuri suljetaan myos virheessa"
