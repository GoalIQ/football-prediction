# -*- coding: utf-8 -*-
"""Jakonapin teksti tulee samasta paikasta kuin jakopolku (30.8.2026).

🔴 Vaihdoin desktop-polun latauksesta leikepoydalle mutta EN nappia. 24 nappia
sanoi yha "Download image" samalla kun mitaan ei latautunut ja ruutuun tuli
"Card copied". Kayttaja olisi etsinyt tiedostoa Lataukset-kansiosta jossa sita
ei ole - sama vika jota muutos korjaa, vain toisin pain.
Julkaisutarkistajan loydos, ei omani.

Kaksi kahdestakymmenestaneljasta oli MONIRIVISENA ilmauksena ja livahti
ensimmaisen korvauksen ohi (muisti: rivi-ei-ole-skannausyksikko), joten tama
portti lukee koko tiedoston eika riveja.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SPA = ROOT / "web" / "pro-spa" / "src"
SHARE_CARD = SPA / "lib" / "shareCard.ts"
#: Nimike saa esiintya VAIN shareCard.ts:ssa, jossa se on yhdessa
#: funktiossa `deliver()`:n haaran kanssa.
LABEL_RE = re.compile(r"'(Download image|Share as image|Copy image)'")


def test_spa_source_exists():
    """Kontrolli: tyhja glob lapaisisi portin (muisti: kontrolli-lapasi-tyhjana)."""
    files = list(SPA.rglob("*.svelte"))
    assert len(files) >= 20, len(files)
    assert SHARE_CARD.exists()


def test_no_component_hardcodes_the_share_button_label():
    bad = []
    for f in sorted(SPA.rglob("*.svelte")):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for m in LABEL_RE.finditer(txt):
            bad.append(f"{f.relative_to(SPA)}:{txt[:m.start()].count(chr(10)) + 1}"
                       f" {m.group(1)!r}")
    assert not bad, ("nimike kovakoodattu komponentissa; kayta "
                     "shareButtonLabel(): %s" % bad)


def test_negative_control_the_pattern_would_catch_a_hardcode():
    """Ilman tata edellinen lapaisisi kuviolla joka ei osu mihinkaan."""
    assert LABEL_RE.search("{sharing ? 'x' : 'Download image'}")
    assert LABEL_RE.search("? 'Share as image'\n : 'Download image'")
    assert not LABEL_RE.search("{shareButtonLabel()}")


def test_label_function_covers_every_delivery_branch():
    """Nimikkeen haarojen on vastattava deliver():n haaroja.

    deliver(): natiivijako -> leikepoyta -> lataus.
    shareButtonLabel(): Share as image -> Copy image -> Download image.
    """
    src = SHARE_CARD.read_text(encoding="utf-8")
    label = src[src.index("export function shareButtonLabel"):]
    label = label[:label.index("}")]
    for needed in ("canShareToApps()", "canCopyImage()",
                   "Share as image", "Copy image", "Download image"):
        assert needed in label, needed
    deliver = src[src.index("async function deliver"):]
    for needed in ("canShareToApps()", "canCopyImage()"):
        assert needed in deliver, f"deliver ei kayta {needed}"
