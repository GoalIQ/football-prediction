"""Uudet tilit MailerLiten ryhmään "GoalIQ users" (18.10.2026, Villen päätös: tervetuloviesti).

MIKSI: viikoittainen deadline-viesti koko listalle ei toiminut (GW5 18.9: 125 vastaanottajaa, avattu
7,2 %, klikkejä 0). Villen päätös 18.10: ei blastia, vaan tervetuloviesti silloin kun kiinnostus on
korkeimmillaan. Viestin lähettää MailerLiten oma automaatio, kun tilaaja liittyy ryhmään. Tämä
tiedosto huolehtii vain siitä, että uusi tili liittyy ryhmään. Ennen tätä ryhmä täytettiin käsin
(viimeksi 25.9), joten uusia tilejä ei tavoitettu lainkaan.

Turvat, jotka eivät ole muistin varassa:
  * Upsert ei koskaan tilaa uudelleen sitä, joka on perunut (MailerLite: ilman `resubscribe: true`
    perunut tila säilyy). `resubscribe`-kenttää ei lähetetä.
  * Ilmaispaketin katto on 250 tilaajaa. Synkka lisää vain sen verran kuin tilaa on varan kanssa, ja
    kertoo esteestä (`katto_esti`), jotta työnkulku muuttuu punaiseksi eikä uusi tili jää hiljaa ulos.
  * Vastauksessa ei ole sähköpostiosoitteita eikä tilikohtaisia rivejä.
"""
from __future__ import annotations

import datetime as _dt
import time

import requests

ML_API = "https://connect.mailerlite.com/api"
RYHMA = "GoalIQ users"
KATTO = 250   # MailerLite Free: up to 250 subscribers (Plan and Billing 18.10.2026)
VARA = 5
TESTIVERKKOTUNNUKSET = ("example.com", "example.org", "test.com", "goaliq.app")


def _aika(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def synkattavat(users: list[dict], nyt: _dt.datetime, paivia: int) -> list[str]:
    """Vahvistetut sähköpostit tileiltä, jotka on luotu viimeisen `paivia` vuorokauden aikana."""
    raja = nyt - _dt.timedelta(days=paivia)
    out = []
    for u in users:
        email = (u.get("email") or "").strip().lower()
        if not email or "@" not in email or u.get("is_anonymous"):
            continue
        if email.rsplit("@", 1)[1] in TESTIVERKKOTUNNUKSET:
            continue
        if not u.get("email_confirmed_at"):
            continue
        luotu = _aika(u.get("created_at"))
        if luotu is None or luotu < raja:
            continue
        out.append(email)
    return sorted(set(out))


class MailerLite:
    def __init__(self, token: str, session=None, tauko: float = 0.6):
        self.s = session or requests.Session()
        self.h = {"Authorization": f"Bearer {token}", "Accept": "application/json",
                  "Content-Type": "application/json"}
        self.tauko = tauko  # MailerLite: 120 pyyntöä minuutissa

    def _get(self, polku, **params):
        r = self.s.get(f"{ML_API}{polku}", headers=self.h, params=params or None, timeout=20)
        time.sleep(self.tauko)
        return r

    def ryhman_id(self, nimi: str) -> str | None:
        r = self._get("/groups", **{"filter[name]": nimi, "limit": 50})
        r.raise_for_status()
        for g in r.json().get("data", []):
            if g.get("name") == nimi:
                return str(g["id"])
        return None

    def tilaajia(self) -> int:
        r = self._get("/subscribers", limit=0)
        r.raise_for_status()
        return int(r.json()["total"])

    def on_olemassa(self, email: str) -> bool:
        r = self._get(f"/subscribers/{requests.utils.quote(email, safe='')}")
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return True

    def lisaa(self, email: str, ryhma_id: str) -> int:
        r = self.s.post(f"{ML_API}/subscribers", headers=self.h,
                        json={"email": email, "groups": [ryhma_id]}, timeout=20)
        time.sleep(self.tauko)
        return r.status_code


def synkkaa(users: list[dict], ml: MailerLite, nyt: _dt.datetime | None = None, paivia: int = 14) -> dict:
    nyt = nyt or _dt.datetime.now(_dt.timezone.utc)
    ehdokkaat = synkattavat(users, nyt, paivia)
    ryhma = ml.ryhman_id(RYHMA)
    if ryhma is None:
        return {"tila": "virhe", "syy": f"ryhmää '{RYHMA}' ei löydy MailerLitesta"}
    tilaa = KATTO - VARA - ml.tilaajia()
    jo, lisatty, esti, virheet = 0, 0, 0, 0
    for email in ehdokkaat:
        try:
            if ml.on_olemassa(email):
                jo += 1
                continue
        except requests.RequestException:
            virheet += 1
            continue
        if tilaa <= 0:
            esti += 1
            continue
        koodi = ml.lisaa(email, ryhma)
        if koodi in (200, 201):
            lisatty += 1
            tilaa -= 1
        else:
            virheet += 1
    if virheet:
        tila = "virhe"
    elif esti:
        tila = "katto"
    else:
        tila = "ok"
    return {"tila": tila, "paivia": paivia, "ehdokkaita": len(ehdokkaat), "jo_listalla": jo,
            "lisatty": lisatty, "katto_esti": esti, "virheita": virheet, "tilaa_jaljella": max(tilaa, 0),
            "katto": KATTO}
