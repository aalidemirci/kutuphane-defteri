"""Paketleme her PR'da koşar; zorunlu paket kontrolleri atlanamaz (01.10.2026).

`main`in dal korumasında "Linux paketi (.deb + .tar.gz)" ve "Windows paketi
(setup.exe + portable.zip)" ZORUNLU kontroldür (GitHub ayarıdır, depoda durmaz).
`paketleme.yml`'de iki değişiklik bu kontrolleri bozar:

* `pull_request` tetiğine yol süzgeci (`paths`, `paths-ignore`, `branches`):
  süzgeç dışında kalan PR'da iş akışı hiç başlamaz, kontrol hiç raporlanmaz ve
  PR birleşemez. Yalnız frontend/ değiştiren bir PR böyle takıldı; süzgeçte
  frontend/ yoktu, oysa arayüz pakete girer.
* Paket işine ya da bağlı olduğu işe iş düzeyinde `if:`: atlanan iş zorunlu
  kontrolde BAŞARILI sayılır ve paket derlenmeden birleştirme açılır.

Kontrol adı dal korumasındaki adla aynı kalmalıdır; adı değiştiren dal
korumasını da günceller, yoksa koruma hiç gelmeyecek eski adı bekler.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
IS_AKISI = (REPO / ".github" / "workflows" / "paketleme.yml").read_text(encoding="utf-8")

# İş anahtarı → dal korumasındaki zorunlu kontrol adı (işin `name:` alanı).
ZORUNLU_ISLER = {
    "linux": "Linux paketi (.deb + .tar.gz)",
    "windows": "Windows paketi (setup.exe + portable.zip)",
}


def _blok(metin: str, anahtar: str, girinti: int) -> list[str] | None:
    """`<girinti><anahtar>:` satırının altındaki (daha derin girintili) satırlar.

    Yorum ve boş satırlar atlanır. Anahtar o girintide yalın `anahtar:` satırı
    olarak yoksa (yok ya da `anahtar: {…}` gibi satır içi yazılmış) None döner.
    """
    satirlar = metin.splitlines()
    bas = " " * girinti + anahtar + ":"
    if bas not in satirlar:
        return None
    blok: list[str] = []
    for satir in satirlar[satirlar.index(bas) + 1 :]:
        yalin = satir.strip()
        if not yalin or yalin.startswith("#"):
            continue
        if len(satir) - len(satir.lstrip()) <= girinti:
            break
        blok.append(satir)
    return blok


def _isler(metin: str) -> str:
    return metin.split("\njobs:\n", 1)[1]


def _alan(is_blogu: list[str], alan: str) -> str | None:
    """İş düzeyindeki (4 boşluk girintili) `alan:` değeri."""
    for satir in is_blogu:
        eslesme = re.match(rf"^    {re.escape(alan)}:(.*)$", satir)
        if eslesme:
            return eslesme.group(1).strip()
    return None


def _bagli_isler(metin: str, is_adi: str) -> set[str]:
    """İşin kendisi ve `needs` zinciriyle bağlı olduğu bütün işler."""
    isler = _isler(metin)
    kume: set[str] = set()
    bekleyen = [is_adi]
    while bekleyen:
        ad = bekleyen.pop()
        if ad in kume:
            continue
        kume.add(ad)
        blok = _blok(isler, ad, 2)
        assert blok is not None, f"iş bulunamadı: {ad}"
        needs = _alan(blok, "needs") or ""
        bekleyen += [n.strip() for n in needs.strip("[]").split(",") if n.strip()]
    return kume


def _ihlaller(metin: str) -> list[str]:
    """Zorunlu kontrolleri bozan her yapıyı bir satır olarak döndürür."""
    ihlaller: list[str] = []
    on_blogu = _blok(metin, "on", 0)
    if on_blogu is None:
        return ["`on:` bloğu bulunamadı"]
    pr = _blok("\n".join(on_blogu), "pull_request", 2)
    if pr is None:
        ihlaller.append("`pull_request:` tetiği yalın satır olarak yok")
    elif pr:
        ihlaller.append(f"`pull_request` tetiğinde süzgeç: {pr[0].strip()}")
    isler = _isler(metin)
    for is_adi, kontrol in ZORUNLU_ISLER.items():
        blok = _blok(isler, is_adi, 2)
        if blok is None:
            ihlaller.append(f"zorunlu kontrolün işi yok: {is_adi}")
            continue
        if _alan(blok, "name") != kontrol:
            ihlaller.append(f"{is_adi}: ad dal korumasındakiyle aynı değil: {_alan(blok, 'name')}")
        for bagli in sorted(_bagli_isler(metin, is_adi)):
            kosul = _alan(_blok(isler, bagli, 2) or [], "if")
            if kosul is not None:
                ihlaller.append(f"{is_adi} → {bagli}: iş düzeyinde koşul: {kosul}")
    return ihlaller


def test_paket_kontrolleri_her_pr_da_kosar() -> None:
    assert _ihlaller(IS_AKISI) == []
    # Zincir gerçekten çözüldü: iki paket işi de arayüz derlemesine bağlıdır.
    assert _bagli_isler(IS_AKISI, "linux") == {"linux", "arayuz"}
    assert _bagli_isler(IS_AKISI, "windows") == {"windows", "arayuz"}


def test_denetim_suzgeci_ve_atlama_kosulunu_yakalar() -> None:
    """Denetim boşa dönmesin: bozulmuş iş akışı örneklerinde ihlal bulunur."""
    suzgecli = IS_AKISI.replace(
        "  pull_request:\n", '  pull_request:\n    paths:\n      - "backend/**"\n', 1
    )
    assert any("süzgeç" in i for i in _ihlaller(suzgecli))

    satir_ici = IS_AKISI.replace("  pull_request:\n", "  pull_request: {paths: [x]}\n", 1)
    assert any("yalın satır" in i for i in _ihlaller(satir_ici))

    atlamali = IS_AKISI.replace(
        "    name: Arayüz derlemesi\n",
        "    name: Arayüz derlemesi\n    if: github.event_name != 'pull_request'\n",
        1,
    )
    assert any("arayuz: iş düzeyinde koşul" in i for i in _ihlaller(atlamali))

    adi_degismis = IS_AKISI.replace(ZORUNLU_ISLER["windows"], "Windows paketi", 1)
    assert any("windows: ad" in i for i in _ihlaller(adi_degismis))
