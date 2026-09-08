"""UEFA-turnausten yhteisfitti: kotiliigojen data + liigan voimakkuustermi.

ONGELMA (Villen bugiraportti 8.9.2026). Mestarien liigan malli fitataan VAIN
CL-otteluista. Kauden alussa se tarkoittaa etta puolet osallistujista puuttuu
kokonaan: 26/27:n sarjavaiheeseen tuli 18 uutta seuraa 36:sta, ja 12 ottelua
18:sta ei ollut ennustettavissa. Villen kaveri: "champpari ei anna mun
ennustaa esim aston villan pelia".

Aston Villalla on 38 Valioliiga-ottelua. Data on olemassa; se on vain toisessa
mallissa.

MIKSI EI SUORAA RATINGIN SIIRTOA (mitattu ja hylatty 8.9): kalibroin
kotiliigan ja CL:n ratingien eron paallekkaisista seuroista ja tein
leave-one-out -takatestin (n=28). Attack-MAE 0,2042 vs naiivi 0,2220 eli 8 %
parempi, mutta defence-MAE 0,1837 vs naiivi 0,1016 eli **81 % HUONOMPI**.
Ratingin kartoitus liigasta toiseen jalkikateen lisaa virhetta.

MIKA TOIMII: yksi yhteinen fitti jossa CL-ottelut ovat SILTA liigojen valilla.
Silloin siirtymaa ei arvata - se estimoidaan samasta datasta.

    Kotiliigojen ottelut  ->  seurakohtainen attack/defence
    CL-ottelut            ->  liigakohtainen voimakkuussiirtyma

Mitattu 8.9 (kausipari 25/26+26/27, 3121 ottelua, 9 liigaa):

    ENG-Premier League   +0,205      <- vahvin
    GER-Bundesliga-FD    +0,106
    FRA-Ligue 1-FD       +0,089
    ITA-Serie A-FD       +0,047
    ESP-La Liga-FD       -0,018
    NED-Eredivisie       -0,254      <- heikoin

Jarjestys on se jonka kuka tahansa jalkapalloa seuraava tunnistaa, eika sita
ole syotetty malliin mistaan - se tulee otteluista.

🔴 KALIBROINTIPORTTI ON TAMAN MODUULIN TARKEIN OSA. Ilman sita liiga jolla ei
ole CL-siltaotteluita saa siirtyman NOLLA, eli mallia kohdellaan kuin sen
sarjataso olisi CL:n tasoa. Mitattu tasan nain:

    FC Porto            att +0,316  def -0,478   (Primeira Liga)
    Manchester City FC  att +0,315  def -0,204   (Valioliiga)

Porto dominoi Portugalin liigaa, ja koska **Primeira Ligalla on 0 CL-
siltaottelua** taman kauden ikkunassa, mikaan ei korjannut sita. Malli antoi
Porto 48 % / City 27 %; markkina on vahvasti painvastoin. Villen havainto:
"Porto 48% city 27% ?? Markkina antaa reilusti toistepain."

Siksi seura kelpaa vain jos sen kotiliigalla on **vahintaan
`MIN_BRIDGE_MATCHES` CL-siltaottelua**. Mitattu siltamaara 8.9: PL 59,
La Liga 58, Bundesliga 44, Serie A 40, Ligue 1 35, Eredivisie 8,
Primeira Liga 0. Kynnys 25 hyvaksyy viisi ensimmaista ja hylkaa Portugalin -
eli tasan sen ottelun jonka Ville nappasi.

MITATTU LOPPUTULOS (8.9, kolme mittaria):

                              kattavuus  Opta-poikkeama  log-loss (72 ott.)
    Tuotanto (vain CL)          6/18        11,5 pp          0,8883
    Yhteisfitti, jkl-kotietu   10/18        10,6 pp          0,8965
    Yhteisfitti, yht. kotietu  10/18         8,6 pp          0,8957

Opta-vertailu on theanalyst.comin supertietokoneen julkaisemat prosentit
MD1:lle, 13 vertailulukua, verrattuna kuin kuhunkin (kotiluku kotilukuun,
vierasluku vieraslukuun). Log-loss-ero CL-malliin ei ole tilastollisesti
merkitseva: parittainen keskivirhe 0,0299, 95 % LV [-0,057, +0,060].

🔴 KUMPIKAAN MALLI EI OLE TARKKUUSINSTRUMENTTI. Keskimaarin 9-11 pp Optasta
on paljon, ja Club Brugge vs Aston Villa menee meilla eri suuntaan kuin
Optalla (me 45/33, Opta 35,5/38,9). Talla mallilla saa nayttaa suuntaa, ei
vahvoja vaitteita yksittaisen ottelun todennakoisyyksista.

TAMA MODUULI EI KOSKE DOMESTIC-ENNUSTEISIIN. Se rakentaa oman mallinsa
UEFA-turnauksille; jokaisen liigan oma `/api/predict` kulkee entista polkua
bittitarkasti.
"""
from __future__ import annotations

import collections
import math
import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.models.dixon_coles import DixonColesModel

# Klubimuoto-tokenit jotka eivat erota seuroja toisistaan. Sama lista kuin
# scripts/accuracy_pipeline.py:n `_CLUB_TOKENS` - nimien kanonisointi on
# nimenomaan se kohta jossa "Aston Villa" ja "Aston Villa FC" on saatava
# samaksi entiteetiksi, tai koko yhteisfitti on turha.
_CLUB_TOKENS = {
    "fc", "afc", "cf", "sc", "ac", "as", "ss", "ssc", "us", "usl", "sv", "vfb",
    "vfl", "tsg", "fsv", "bsc", "sk", "fk", "nk", "gnk", "rc", "rcd", "cd",
    "ud", "sd", "club", "de", "the", "1", "04", "05", "07", "09", "1907",
    "1909", "1913", "1846", "1899", "1900", "1901", "1902", "1903", "1904",
}

MAX_LEAGUE_SHIFT = 0.60
"""Liigasiirtyman itseisarvon katto (log-skaala).

🔴 EI KOSMETIIKKAA: ilman kattoa iteraatio voi ajaa siirtyman niin suureksi
etta `exp(shift)` rajahtaa, maaliodotus menee kymmeniin ja koko
tulosmatriisi alivuotaa nollaksi - jolloin ennuste ei ole vaara vaan
olematon. Testidata paljasti taman (ZeroDivisionError), mutta sama voi
tapahtua tuotannossa jos jokin liiga saa muutaman poikkeuksellisen
siltaottelun.

Katto on mitattu: todelliset siirtymat 8.9 olivat -0,254 (Eredivisie) ...
+0,205 (Valioliiga), eli 0,60 on yli kaksinkertainen suurimpaan havaittuun.
Se ei siis rajoita mitaan realistista, mutta estaa karkaamisen."""

SUPPORT_LEAGUES: tuple[str, ...] = (
    "ENG-Premier League",
    "ESP-La Liga-FD",
    "GER-Bundesliga-FD",
    "ITA-Serie A-FD",
    "FRA-Ligue 1-FD",
    "POR-Primeira Liga",
    "NED-Eredivisie",
    "ENG-Championship",
)
"""Kotiliigat jotka ladataan turnausmallin tueksi.

Mukana on MYOS liigoja joita ei voi kalibroida (Primeira, Championship,
Eredivisie). Se on tarkoituksellista: ne tuovat siltaotteluita joista muiden
liigojen siirtymat tarkentuvat, ja kalibrointiportti hoitaa sen ettei niiden
omia seuroja tarjota. Liigan poistaminen taalta EI ole tapa piilottaa seuraa -
se tehdaan portilla."""

MIN_BRIDGE_MATCHES = 25
"""Kuinka monta CL-siltaottelua liiga tarvitsee ennen kuin sen seurat
kelpaavat. Mitattu, ei valittu: 8.9 siltamaarat olivat PL 59, La Liga 58,
Bundesliga 44, Serie A 40, Ligue 1 35, Eredivisie 8, Primeira Liga 0.
Kynnys 25 erottaa viisi kalibroituvaa kolmesta joita ei voi kalibroida."""


def canonical_name(name: str) -> str:
    """Seuran nimi kanoniseen muotoon: aksentit ja klubimuoto-tokenit pois.

    'Aston Villa FC' ja 'Aston Villa' -> 'aston villa'. Ilman tata sama seura
    on kahtena entiteettina eika kotiliigan data auta CL-ennusteessa lainkaan:
    mitattu 8.9, ilman kanonisointia CL-osallistujista loytyi 25/36, sen
    kanssa 28/36.
    """
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in _CLUB_TOKENS]
    return " ".join(tokens)


def _clamp(x: float) -> float:
    return max(-MAX_LEAGUE_SHIFT, min(MAX_LEAGUE_SHIFT, x))


@dataclass
class UefaJointModel:
    """Yhteisfitti + liigasiirtymat + kelpoisuussaanto."""

    dc: DixonColesModel
    club_league: dict[str, str]
    league_attack: dict[str, float]
    league_defence: dict[str, float]
    bridge_counts: dict[str, int] = field(default_factory=dict)
    tournament_clubs: frozenset[str] = frozenset()
    display_names: dict[str, str] = field(default_factory=dict)

    def calibrated_leagues(self) -> set[str]:
        return {L for L, n in self.bridge_counts.items() if n >= MIN_BRIDGE_MATCHES}

    def is_eligible(self, club: str) -> bool:
        """Kelpaako seura turnausennusteeseen?

        Kaksi reittia: seuralla on omia turnausotteluita (silloin rating on
        suoraan oikealta tasolta), TAI sen kotiliiga on kalibroituva. Muuten
        ei - `FC Porto` on tasan tama tapaus.
        """
        c = canonical_name(club)
        if c not in self.dc.attack:
            return False
        if c in self.tournament_clubs:
            return True
        return self.club_league.get(c) in self.calibrated_leagues()

    def eligible_clubs(self) -> list[str]:
        return sorted(c for c in self.dc.attack if self.is_eligible(c))

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        h, a = canonical_name(home), canonical_name(away)
        lam, mu = self.dc.expected_goals(h, a)
        lh = lam * math.exp(
            self.league_attack.get(self.club_league.get(h, ""), 0.0)
            - self.league_defence.get(self.club_league.get(a, ""), 0.0)
        )
        la = mu * math.exp(
            self.league_attack.get(self.club_league.get(a, ""), 0.0)
            - self.league_defence.get(self.club_league.get(h, ""), 0.0)
        )
        return lh, la

    def outcome_probabilities(self, home: str, away: str) -> tuple[float, float, float]:
        """(koti, tasa, vieras). Heittaa jos jompikumpi ei kelpaa - kelpoisuus
        on kutsujan tarkistettava, jottei epakelpo seura livahda ennusteeseen
        hiljaa."""
        for club in (home, away):
            if not self.is_eligible(club):
                raise ValueError(
                    f"{club}: ei kelpaa turnausennusteeseen (ei turnausotteluita "
                    f"eika kalibroituvaa kotiliigaa)"
                )
        lh, la = self.expected_goals(home, away)
        # 🔴 rho:n KELPOISUUSEHTO, ei viritys. Bivariate-Poisson-hajotelma on
        # lam3 = max(0, -rho) * min(lam, mu), ja lam1 = lam - lam3 on oltava
        # positiivinen. Se pitaa vain jos rho > -1. Jos fitti antaa
        # pienemman, lam1 ja lam2 painuvat nollaan, koko tulosmatriisi
        # alivuotaa ja "ennuste" olisi nan-jakauma joka nayttaa luvulta.
        # Testidata paljasti taman tasmalleen nain: lam=2,82, mu=2,18 eli
        # taysin normaalit maaliodotukset, ja silti nolla matriisi.
        rho = getattr(self.dc, "rho", 0.0) or 0.0
        rho = max(rho, -0.9)
        M = self.dc._bp_score_matrix(lh, la, rho, 10)
        total = float(M.sum())
        if not np.isfinite(total) or total <= 0.0:
            # Alivuoto: maaliodotus on karannut niin suureksi etta koko
            # matriisi on nollia. Parempi heittaa kuin palauttaa nan-jakauma
            # joka nayttaa ennusteelta.
            raise ValueError(
                f"{home} vs {away}: tulosmatriisi alivuoti "
                f"(lam={lh:.2f}, mu={la:.2f}) - ennustetta ei anneta"
            )
        return (
            float(np.tril(M, -1).sum()) / total,
            float(np.trace(M)) / total,
            float(np.triu(M, 1).sum()) / total,
        )


def _fold_shifts(model: "UefaJointModel") -> DixonColesModel:
    """Taita liigasiirtymat suoraan ratingeihin ja palauta tavallinen DC-malli.

    🔴 MIKSI NAIN EIKA OMANA ENNUSTEPOLKUNAAN: `/api/predict` ei palauta vain
    1X2:ta vaan xG:n, todennakoisimmat tulokset, reilut kertoimet, over/under-
    ja BTTS-luvut. Jos turnausmalli olisi oma polkunsa, jokainen niista pitaisi
    kirjoittaa uudelleen - ja jokainen olisi uusi paikka olla eri mielta
    domestic-polun kanssa.

    Siirtyma on multiplikatiivinen lambdaan, eli additiivinen log-skaalassa:

        lh = exp(attack[h] + defence[a] + home_adv + gamma) * exp(la[Lh] - ld[La])
           = exp( (attack[h] + la[Lh]) + (defence[a] - ld[La]) + home_adv + gamma )

    joten sama tulos syntyy tavallisesta DC-mallista jonka kertoimiin siirtyma
    on taitettu. Alavirta ei siis tieda mitaan turnausmallista, ja kaikki
    johdetut luvut pysyvat keskenaan johdonmukaisina.

    Mallissa on VAIN kelpoiset seurat: epakelpo ei voi vuotaa ennusteeseen
    edes vahingossa, koska sita ei ole avaimissa.
    """
    out = DixonColesModel(per_team_home_adv=False)
    out.attack, out.defence, out.home_advantage_per_team = {}, {}, {}
    for canon in model.dc.attack:
        if not model.is_eligible(canon):
            continue
        L = model.club_league.get(canon, "")
        nimi = model.display_names.get(canon, canon)
        out.attack[nimi] = model.dc.attack[canon] + model.league_attack.get(L, 0.0)
        out.defence[nimi] = model.dc.defence[canon] - model.league_defence.get(L, 0.0)
        out.home_advantage_per_team[nimi] = 0.0
    out.home_advantage = model.dc.home_advantage
    # rho:n kelpoisuusehto: hajotelma vaatii rho > -1, muuten lam1 painuu
    # nollaan ja koko tulosmatriisi alivuotaa. Sama raja kuin
    # `outcome_probabilities`issa.
    out.rho = max(getattr(model.dc, "rho", 0.0) or 0.0, -0.9)
    out.teams_ = sorted(out.attack)
    return out


def fit_uefa_joint(
    df: pd.DataFrame,
    tournament_league: str = "INT-Champions League",
    decay: float = 0.0035,
    iterations: int = 2,
    stale_seasons: frozenset[str] = frozenset(),
) -> UefaJointModel:
    """Sovita yhteismalli ja estimoi liigasiirtymat turnausotteluista.

    `stale_seasons`: turnauskaudet jotka kelpaavat SILLAKSI (liigasiirtyman
    estimointiin) mutta EIVAT tee seurasta ennustettavaa.

    🔴 MIKSI TAMA ERO ON OLEMASSA. Leveampi turnausikkuna on hyodyllinen:
    siltaotteluita tulee kolminkertaisesti ja liigasiirtymat tarkentuvat
    (mitattu: La Liga 58 -> 151, Valioliiga 59 -> 137). Mutta se toisi myos
    seuroja joiden AINOA turnausdata on vuosia vanhaa, ja ne nayttaisivat
    keskiverroilta kotietuineen. Tasan niin kavi FC Portolle: ainoa CL-data
    kaudelta 23/24, viimeisin ottelu 2024-03-12, ja malli antoi Porto 48 % /
    Manchester City 27 % - markkina vahvasti painvastoin.

    Vanha kausi siis OPETTAA liigojen tasoeroa muttei tee sen omista
    seuroista ennustettavia.
    """
    d = df.dropna(subset=["home_score", "away_score"]).copy()
    d["home_team"] = d["home_team"].map(canonical_name)
    d["away_team"] = d["away_team"].map(canonical_name)

    club_league: dict[str, str] = {}
    for row in d[d.league != tournament_league].itertuples(index=False):
        club_league.setdefault(row.home_team, row.league)
        club_league.setdefault(row.away_team, row.league)

    tour = d[d.league == tournament_league]
    tuore = tour[~tour["season"].astype(str).isin(stale_seasons)] if "season" in tour.columns else tour
    bridge: collections.Counter = collections.Counter()
    for row in tour.itertuples(index=False):
        for club in (row.home_team, row.away_team):
            L = club_league.get(club)
            if L:
                bridge[L] += 1

    # 🔴 YHTEINEN KOTIETU, EI JOUKKUEKOHTAINEN (mitattu 8.9 Optan
    # supertietokonetta vasten, 13 vertailulukua). Joukkuekohtainen kotietu
    # fitataan ohuesta turnausdatasta ja tuottaa systemaattista
    # kotiylivarmuutta:
    #
    #   joukkuekohtainen  keskipoikkeama +4,4 pp  itseisarvo 10,6  suurin 23,2
    #   yhteinen          keskipoikkeama +2,7 pp  itseisarvo  8,6  suurin 22,6
    #
    # Sama suunta myos oikeilla tuloksilla (72 CL-ottelua, log-loss 0,8965 ->
    # 0,8957). Kotiylivarmuus oli viisi kuudesta suurimmasta virheesta.
    dc = DixonColesModel(per_team_home_adv=False)
    dc.fit(d, decay=decay, date_col="date")

    la: dict[str, float] = collections.defaultdict(float)
    ld: dict[str, float] = collections.defaultdict(float)
    for _ in range(iterations):
        sa: dict[str, list[float]] = collections.defaultdict(list)
        sd: dict[str, list[float]] = collections.defaultdict(list)
        for row in tour.itertuples(index=False):
            h, a = row.home_team, row.away_team
            if h not in dc.attack or a not in dc.attack:
                continue
            lam, mu = dc.expected_goals(h, a)
            Lh, La = club_league.get(h, ""), club_league.get(a, "")
            lh = lam * math.exp(la[Lh] - ld[La])
            lam_a = mu * math.exp(la[La] - ld[Lh])
            rh = math.log((row.home_score + 0.5) / max(lh, 1e-6))
            ra = math.log((row.away_score + 0.5) / max(lam_a, 1e-6))
            sa[Lh].append(rh)
            sa[La].append(ra)
            sd[La].append(-rh)
            sd[Lh].append(-ra)
        # Puolikas askel: taysi paivitys heiluu, koska sama ottelu paivittaa
        # seka hyokkaysta etta puolustusta.
        for L, vals in sa.items():
            if L:
                la[L] = _clamp(la[L] + 0.5 * float(np.mean(vals)))
        for L, vals in sd.items():
            if L:
                ld[L] = _clamp(ld[L] + 0.5 * float(np.mean(vals)))

    # Nayttonimi: ensisijaisesti se muoto jossa seura esiintyy TURNAUS-
    # datassa (football-data.orgin taysnimi), koska /api/fixtures kayttaa
    # sita ja klientti sovittaa ottelut sen mukaan. Muuten seuran oman
    # liigan nimi.
    display: dict[str, str] = {}
    for row in d[d.league != tournament_league].itertuples(index=False):
        display.setdefault(row.home_team, row.home_team)
        display.setdefault(row.away_team, row.away_team)
    alkup: dict[str, str] = {}
    for row in df.itertuples(index=False):
        if getattr(row, "league", None) == tournament_league:
            alkup.setdefault(canonical_name(row.home_team), str(row.home_team))
            alkup.setdefault(canonical_name(row.away_team), str(row.away_team))
    for row in df.itertuples(index=False):
        alkup.setdefault(canonical_name(row.home_team), str(row.home_team))
        alkup.setdefault(canonical_name(row.away_team), str(row.away_team))
    display.update(alkup)

    return UefaJointModel(
        display_names=display,
        dc=dc,
        club_league=club_league,
        league_attack=dict(la),
        league_defence=dict(ld),
        bridge_counts=dict(bridge),
        # Kelpoisuus tulee VAIN tuoreista turnauskausista; koko `tour` on
        # yha sillan estimoinnissa mukana.
        tournament_clubs=frozenset(set(tuore.home_team) | set(tuore.away_team)),
    )
