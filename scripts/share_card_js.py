# -*- coding: utf-8 -*-
"""Jakokortti (share as image) staattisille goaliq.app-sivuille.

TAUSTA: SPA:ssa (web/pro-spa/src/lib/shareCard.ts) on ollut 31.7. alkaen
"share as image" -kortti, joka on layoutiltaan 1:1 goaliq-appin
outputs/gen_fpl_xp_list.py:n kanssa -- eli viikkopostaus, tuote ja sivusto
kertovat saman tarinan samassa muodossa. Ilmaisilta sivuilta se puuttui,
vaikka juuri ne ovat se pinta jonne X-liikenne laskeutuu.

TAMA MODUULI on sama kortti vanilla-JS:na, jotta staattiset sivut eivat
tarvitse SPA:n build-ketjua. Mitat, varit, fontit ja rivilayout on kopioitu
shareCard.ts:n renderCard():sta SELLAISENAAN -- jos niita muuttaa, molemmat
on muutettava, muuten syntyy kolmas erinakoinen kortti.

MUUTTUJAT (korvataan kutsujassa):
  __CARD_ROWS_FN__  JS-funktio joka palauttaa {title,subtitle,nameLabel,
                    midLabel,valueLabel,rows,fileName}

🔴 ENSISIJAINEN LAHDE ON PALVELIN, EI DOM (24.8). Kortti lukee ensin
`[data-card-spec]`-attribuutin, jonka builderi kirjoittaa SAMASTA
rivilistasta josta taulukkokin renderoidaan. `__CARD_ROWS_FN__` on enaa
fallback niille sivuille joita ei ole viela siirretty.

MIKSI: elavan DOMin lukeminen tuotti brandattuja kuvia jotka sanoivat
vastakkaista kuin data. Jokainen `table.lb` saa GEN:TABLE-TOOLSilta
klikkilajittelun ja suodatinpalkin, joten "TOP 10 BY EXPECTED POINTS"
muuttui KAHDELLA klikkauksella kymmeneksi kalleimmaksi - ja suodattimet
piilottavat rivit `display:none`-tyylilla jota `querySelectorAll` ei nae,
joten kortti kantoi globaalin top-10:n vaikka jakaja katsoi DEF-listaa.
Julkaisutarkistaja blokkasi kortit nelja kierrosta perakkain, ja kaksi
yritysta korjata lukija SAILYTTAEN elava DOM tuotti kumpikin uusia
valheita. Palvelinrivit poistavat koko luokan: kortti on aina se nakyma
jonka linkista tuleva lukija nakee.
"""

import json as _json

from src.models import team_colors as _tc


def _kits_json() -> str:
    """Seurapaidat korttiin SAMASTA lahteesta kuin sivujen SVG-paidat ja
    PIL-kortit (src/models/team_colors.py). 12.10.2026: sivujen kortti sai
    paidat kuten SPA:n kortti; erillinen JS-kopio vareista olisi neljas
    totuus samasta paidasta."""
    kits = {}
    for short, (color, text) in _tc._TEAM_COLORS.items():
        pattern, secondary = _tc._KIT_BY_SHORT.get(short, ("solid", None))
        kits[short] = {"c": color, "t": text, "p": pattern, "s": secondary,
                       "L": [list(l) for l in _tc._kit_layers(pattern)] if secondary else []}
    geom = {"J": _tc._JERSEY, "SL": _tc._SLEEVE_L, "SR": _tc._SLEEVE_R,
            "CL": _tc._CUFF_L, "CR": _tc._CUFF_R, "CO": _tc._COLLAR}
    return _json.dumps({"kits": kits, "geom": geom}, separators=(",", ":"))


# Huom: tama on JS-lahdekoodia Python-merkkijonossa. Aaltosulkeita EI saa
# tuplata, koska merkkijonoa ei formatoida f-stringilla vaan replacella.
# 12.10.2026 JAKOKORTIN UUSI ULKOASU: sama kuin shareCard.ts:n renderCard
# (pieni wordmark ylakulmaan, Plex Sans -otsikko vasemmalle, rivit ilman
# kehyksia, seuran paita, metarivi nimen alla). Muuta molemmat yhdessa.
_SHARE_CARD_TEMPLATE = r"""
<script>
(function(){
 // --- Dimensions and palette: same as shareCard.ts renderCard (change both together)
 var W=1080,MX=60,ROW_H=84,FOOT_H=132,NAME_X=MX+116,KIT=46;
 var INK='#0b0a09',INK2='#141311',AMBER='#f5c542',CREAM='#f3f2f2',
     MUTED='#a8a29a',LINE='rgba(243,242,242,0.13)',CREAM_DIM='rgba(243,242,242,0.78)';
 var FONT='"IBM Plex Mono", ui-monospace, monospace';
 var SANS='"IBM Plex Sans", system-ui, sans-serif';
 function bold(px){return '700 '+px+'px '+FONT;}
 function med(px){return '500 '+px+'px '+FONT;}
 function sansBold(px){return '700 '+px+'px '+SANS;}
 function sansMed(px){return '500 '+px+'px '+SANS;}
 // Club shirts from the same table as the page's own SVG shirts.
 var KD=__KITS__;

 var wmP=null;
 function loadWordmark(){
  if(!wmP){
   wmP=new Promise(function(res){
    var img=new Image();
    img.onload=function(){res(img);};
    // The card must not fail on a missing asset: the fallback draws the
    // wordmark as text, the same contract as in the SPA.
    img.onerror=function(){res(null);};
    img.src='/assets/brand/goaliq-wordmark-teletext.png';
   });
  }
  return wmP;
 }

 function shrink(ctx,text,px,maxW,minPx,weight){
  ctx.font=weight(px);
  while(ctx.measureText(text).width>maxW&&px>minPx){px-=2;ctx.font=weight(px);}
  return px;
 }

 // Title: one line down to 58 px, then two lines, then shrink. A short title
 // broken in two leaves an orphan word and pushes the card past 4:5.
 function fitTitle(ctx,text,maxW){
  var px;
  for(px=76;px>=58;px-=2){ctx.font=sansBold(px);if(ctx.measureText(text).width<=maxW)return {px:px,lines:[text]};}
  for(px=76;px>=52;px-=4){
   ctx.font=sansBold(px);
   var words=text.split(' '),lines=[],cur='';
   for(var i=0;i<words.length;i++){
    var next=cur?cur+' '+words[i]:words[i];
    if(cur&&ctx.measureText(next).width>maxW){lines.push(cur);cur=words[i];}else{cur=next;}
   }
   if(cur)lines.push(cur);
   var ok=lines.length<=2;
   for(var j=0;j<lines.length;j++){if(ctx.measureText(lines[j]).width>maxW)ok=false;}
   if(ok)return {px:px,lines:lines};
  }
  return {px:shrink(ctx,text,52,maxW,32,sansBold),lines:[text]};
 }

 function darken(hex,f){
  var m=/^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if(!m)return hex;
  var n=parseInt(m[1],16),out='#';
  [16,8,0].forEach(function(s){var v=Math.max(0,Math.round(((n>>s)&255)*f));out+=(v<16?'0':'')+v.toString(16);});
  return out;
 }

 // Shirt without the chest mark: at 46 px the mark is a 4 px smudge.
 function drawKit(ctx,short,x,y,size){
  var k=KD.kits[(short||'').toUpperCase()];
  if(!k||typeof Path2D==='undefined')return false;
  var G=KD.geom;
  ctx.save();ctx.translate(x,y);ctx.scale(size/100,size/100);
  var sleeve=(k.p==='sleeves'&&k.s)?k.s:darken(k.c,0.7);
  ctx.fillStyle=k.c;ctx.fill(new Path2D(G.J));
  if(k.L.length){
   ctx.save();ctx.clip(new Path2D(G.J));ctx.fillStyle=k.s;
   k.L.forEach(function(l){if(l[0]==='rect')ctx.fillRect(l[1],l[2],l[3],l[4]);else ctx.fill(new Path2D(l[1]));});
   ctx.restore();
  }
  ctx.fillStyle=sleeve;ctx.fill(new Path2D(G.SL));ctx.fill(new Path2D(G.SR));
  ctx.fillStyle=k.p==='sleeves'?k.c:(k.s||darken(k.c,0.55));
  ctx.fill(new Path2D(G.CL));ctx.fill(new Path2D(G.CR));
  ctx.strokeStyle=k.s||sleeve;ctx.lineWidth=4;ctx.lineCap='round';ctx.stroke(new Path2D(G.CO));
  ctx.strokeStyle='rgba(243,242,242,0.35)';ctx.lineWidth=3;ctx.lineJoin='round';ctx.stroke(new Path2D(G.J));
  ctx.restore();
  return true;
 }

 function render(spec){
  var fonts=(document.fonts&&document.fonts.load)
   ? Promise.all([document.fonts.load(bold(46)),document.fonts.load(med(18)),
                  document.fonts.load(sansBold(72)),document.fonts.load(sansMed(24))])['catch'](function(){})
   : Promise.resolve();
  return fonts.then(loadWordmark).then(function(wm){
   var probe=document.createElement('canvas').getContext('2d');
   var title=fitTitle(probe,spec.title,W-2*MX),tLH=Math.round(title.px*1.04);
   var n=spec.rows.length;
   var TITLE_Y=150,subY=TITLE_Y+title.lines.length*tLH+14,headY=subY+76,listTop=headY+40;
   var H=listTop+n*ROW_H+FOOT_H;
   var c=document.createElement('canvas');
   c.width=W;c.height=H;
   var ctx=c.getContext('2d');
   ctx.textBaseline='top';

   var g=ctx.createLinearGradient(0,0,0,H);
   g.addColorStop(0,INK);g.addColorStop(1,INK2);
   ctx.fillStyle=g;ctx.fillRect(0,0,W,H);

   // Brand small in the top-left corner: it identifies, the title tells.
   var WM_H=46;
   if(wm){
    ctx.drawImage(wm,MX,52,Math.round(wm.width*WM_H/wm.height),WM_H);
   }else{
    ctx.font=bold(32);
    var gw=ctx.measureText('GOAL').width;
    ctx.fillStyle=CREAM;ctx.fillText('GOAL',MX,58);
    ctx.fillStyle=AMBER;ctx.fillRect(MX+gw+8,52,WM_H,WM_H);
    ctx.fillStyle=INK;ctx.font=bold(24);
    ctx.fillText('IQ',MX+gw+8+(WM_H-ctx.measureText('IQ').width)/2,63);
   }
   ctx.font=med(20);ctx.fillStyle=MUTED;
   ctx.fillText('goaliq.app',W-MX-ctx.measureText('goaliq.app').width,66);

   ctx.fillStyle=CREAM;ctx.font=sansBold(title.px);
   for(var t=0;t<title.lines.length;t++)ctx.fillText(title.lines[t],MX-2,TITLE_Y+t*tLH);
   ctx.fillStyle=AMBER;ctx.fillRect(MX,TITLE_Y-30,56,6);
   // The filter list can be long ("Goal threat, per 90, DEF, 900+ mins,
   // ARS, 42 players"), so the subtitle shrinks to fit.
   shrink(ctx,spec.subtitle,26,W-2*MX,13,sansMed);
   ctx.fillStyle=MUTED;ctx.fillText(spec.subtitle,MX,subY);

   var fxRight=W-MX-180,rowX=MX-12,rowW=W-2*(MX-12);
   // No shirt on any row (a team list without club codes): the name takes
   // the shirt column, an empty band on the left reads as a bug.
   var anyKit=spec.rows.some(function(r){var k=(r.team||r.colorTeam||'').toUpperCase();return !!KD.kits[k];});
   var nameX=anyKit?NAME_X:MX+60;
   ctx.font=med(17);ctx.fillStyle=MUTED;
   ctx.fillText(spec.nameLabel||'PLAYER',nameX,headY);
   if(spec.midLabel){ctx.fillText(spec.midLabel,fxRight-ctx.measureText(spec.midLabel).width,headY);}
   ctx.fillText(spec.valueLabel,W-MX-ctx.measureText(spec.valueLabel).width,headY);
   ctx.fillStyle=LINE;ctx.fillRect(rowX,headY+30,rowW,1);

   for(var i=0;i<n;i++){
    var r=spec.rows[i],y=listTop+i*ROW_H,first=(i===0),last=(i===n-1);
    // Empty fields drop out, so an empty tag draws nothing.
    var parts=[r.tag,r.team,r.tag2].filter(Boolean);
    var meta=parts.length>0,mid=y+ROW_H/2,nameY=meta?y+14:y+(ROW_H-34)/2;
    if(first){
     ctx.fillStyle='rgba(245,197,66,0.08)';ctx.fillRect(rowX,y+2,rowW,ROW_H-4);
     ctx.fillStyle=AMBER;ctx.fillRect(rowX,y+2,5,ROW_H-4);
    }else if(!last){
     ctx.fillStyle=LINE;ctx.fillRect(rowX,y+ROW_H-1,rowW,1);
    }

    ctx.font=bold(24);ctx.fillStyle=first?AMBER:MUTED;
    var rk=String(r.rank);
    ctx.fillText(rk,MX+30-ctx.measureText(rk).width,mid-13);

    drawKit(ctx,r.team||r.colorTeam,MX+50,mid-KIT/2-2,KIT);

    var nPx=shrink(ctx,r.name,34,fxRight-40-nameX,20,sansBold);
    ctx.font=sansBold(nPx);ctx.fillStyle=CREAM;
    ctx.fillText(r.name,nameX,nameY+(34-nPx)/2);
    if(meta){
     ctx.font=med(18);ctx.fillStyle=MUTED;
     ctx.fillText(parts.join(' · '),nameX,nameY+44);
    }

    if(r.mid){
     var fPx=shrink(ctx,r.mid,24,190,14,med);
     ctx.font=med(fPx);ctx.fillStyle=CREAM_DIM;
     ctx.fillText(r.mid,fxRight-ctx.measureText(r.mid).width,mid-fPx*0.55);
    }

    var vPx=shrink(ctx,r.value,46,170,24,bold);
    ctx.font=bold(vPx);ctx.fillStyle=first?AMBER:CREAM;
    ctx.fillText(r.value,W-MX-ctx.measureText(r.value).width,mid-vPx*0.58);
   }

   // The footer comes from the SPEC. The default text ("logged before
   // kickoff, graded in public") is a MATCH PREDICTION claim and is not
   // true of a stats list -- a shared image must not claim more than the
   // data supports. The handle reserves the right edge of the same row: a
   // footer that runs long would draw OVER it (seen in the PIL version,
   // 9 Aug).
   ctx.fillStyle=LINE;ctx.fillRect(rowX,H-FOOT_H+28,rowW,1);
   ctx.font=bold(24);
   var hw=ctx.measureText('@goaliqapp').width;
   var fn=spec.footNote||'logged before kickoff, graded in public';
   var ff=shrink(ctx,fn,20,W-2*MX-hw-24,13,sansMed);
   ctx.font=sansMed(ff);ctx.fillStyle=MUTED;
   ctx.fillText(fn,MX,H-84);
   ctx.font=bold(24);ctx.fillStyle=AMBER;
   ctx.fillText('@goaliqapp',W-MX-hw,H-74);
   var f2=spec.footNote2||'model projections, not betting advice';
   var f2s=shrink(ctx,f2,17,W-2*MX-hw-24,11,sansMed);
   ctx.font=sansMed(f2s);ctx.fillStyle='rgba(168,162,154,0.75)';
   ctx.fillText(f2,MX,H-54);
   ctx.fillStyle=AMBER;ctx.fillRect(0,H-10,W,10);

   return new Promise(function(res,rej){
    c.toBlob(function(b){b?res(b):rej(new Error('toBlob failed'));},'image/png');
   });
  });
 }

 function deliver(blob,fileName){
  var file=null;
  try{file=new File([blob],fileName,{type:'image/png'});}catch(e){}
  // On a phone the native share sheet is what the user expects; on desktop
  // and wherever sharing is unavailable, fall back to download.
  if(file&&navigator.canShare&&navigator.canShare({files:[file]})&&navigator.share){
   return navigator.share({files:[file]})['catch'](function(){download(blob,fileName);});
  }
  download(blob,fileName);
  return Promise.resolve();
 }
 function download(blob,fileName){
  var u=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=u;a.download=fileName;document.body.appendChild(a);a.click();
  a.remove();setTimeout(function(){URL.revokeObjectURL(u);},1000);
 }

 var btn=document.getElementById('sharecard');
 if(!btn)return;
 function specFromServer(){
  // Exactly one spec per page. With two tables querySelector would take
  // whichever came first in the document and the card would show the wrong
  // one silently. Refuse rather than guess.
  var els=document.querySelectorAll('[data-card-spec]');
  if(els.length!==1)return null;
  try{return JSON.parse(els[0].getAttribute('data-card-spec'));}catch(e){return null;}
 }
 btn.addEventListener('click',function(){
  var spec=specFromServer();
  if(!spec){try{spec=(__CARD_ROWS_FN__)();}catch(e){spec=null;}}
  if(!spec||!spec.rows||!spec.rows.length){
   btn.textContent='Nothing to share yet';
   return;
  }
  var label=btn.textContent;
  btn.disabled=true;btn.textContent='Building card...';
  render(spec).then(function(b){return deliver(b,spec.fileName);})
   .then(function(){btn.disabled=false;btn.textContent=label;})
   ['catch'](function(){btn.disabled=false;btn.textContent='Card failed';});
 });
})();
</script>
"""

SHARE_CARD_JS = _SHARE_CARD_TEMPLATE.replace("__KITS__", _kits_json())
