"""Ekran görüntülerini alır (geçici Playwright kabında koşar; depo bağımlılığı DEĞİLDİR).

`ekran_goruntuleri.sh`, `ekran_sunucusu.py`'nin kabının ağ ad alanına bağlanan geçici
bir Playwright kabında bu betiği çalıştırır: yönetim sunucusu ve Ağ Kataloğu o kabın
127.0.0.1'inde dinler, dışarıya hiçbir port açılmaz. Tarayıcı pencerenin belirteçli
açılış adresini açar (masaüstü penceresinin yaptığı gibi); belirteç `HttpOnly` çereze
geçer, sonraki istekler çerezle yürür.

Görüntü: 1440×900 görünüm alanı, aygıt piksel oranı 2 (PNG 2880×1800), Türkçe yerel
ayar, Europe/Istanbul saat dilimi, açık tema. Genel Bakış'ta alt kenar bir kart sırasının
yalnız üst çizgisini gösterecekse görünüm alanı 16:10 korunarak biraz küçültülür
(`_alt_kenari_bosluga_al`). Site için WebP'ye çeviri ayrı adımdır (`webp_cevir.py`,
backend kabında Pillow ile).

Ağ Kataloğu ayrı bir tarayıcı bağlamında açılır: okul ağındaki tahta başka bir
bilgisayardır ve çerezler portlar arasında yalıtılmaz (CLAUDE.md §2-1).

Kullanım (kabın içinde, depo kökünden):

    python scripts/ekran_goruntuleri/ekran_cekimi.py --cikti dist/ekran-goruntuleri
    python scripts/ekran_goruntuleri/ekran_cekimi.py --cikti … --kesif   # bütün ekranlar, 1x
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

from playwright.sync_api import Browser, Page, sync_playwright

GENISLIK = 1440
YUKSEKLIK = 900
API = "/api/v1"

#: Kayıt aşaması boyunca beklenen en uzun süre (ms).
BEKLEME_MS = 20_000


def _bekle(sayfa: Page) -> None:
    """Ağ sakinleşene, iskelet yükleyiciler ve geçici bildirimler kaybolana dek bekler."""
    sayfa.wait_for_load_state("networkidle", timeout=BEKLEME_MS)
    sayfa.wait_for_function(
        """() => !document.querySelector('[aria-busy="true"], .animate-pulse')""",
        timeout=BEKLEME_MS,
    )
    # Snackbar bildirimi (kısa ömürlü, `ui/Snackbar.tsx`) görüntüye girmesin.
    sayfa.wait_for_function(
        """() => !document.querySelector('.bg-inverse-surface[role="status"]')""",
        timeout=BEKLEME_MS,
    )
    sayfa.evaluate("() => document.fonts.ready")
    sayfa.wait_for_timeout(400)


def _api(sayfa: Page, yol: str, govde: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sayfanın içinden (çerezle) API çağrısı; `{status, body}` döndürür."""
    sonuc: dict[str, Any] = sayfa.evaluate(
        """async ([yol, govde]) => {
            const secenek = govde === null
              ? {headers: {"Accept": "application/json"}}
              : {method: "POST", headers: {"Content-Type": "application/json",
                 "Accept": "application/json", "X-KD-Etkinlik": "1"},
                 body: JSON.stringify(govde)};
            const yanit = await fetch(yol, secenek);
            let body = null;
            try { body = await yanit.json(); } catch (e) { body = null; }
            return {status: yanit.status, body};
        }""",
        [API + yol, govde],
    )
    return sonuc


def yonetici_kipi(sayfa: Page, parola: str) -> None:
    """Kip görevliye inmişse yönetici parolasıyla yönetici kipine geçer (§4.4)."""
    durum = _api(sayfa, "/security/mode/")
    kip = (durum.get("body") or {}).get("mode") or (durum.get("body") or {}).get("durum")
    if kip != "yonetici":
        cevap = _api(sayfa, "/security/mode/admin/", {"password": parola})
        if cevap["status"] != 200:
            raise RuntimeError(f"Yönetici kipine geçilemedi: {cevap['status']}")


def _git(sayfa: Page, taban: str, yol: str) -> None:
    sayfa.goto(taban + yol, wait_until="domcontentloaded")
    _bekle(sayfa)


def _cek(sayfa: Page, hedef: Path) -> None:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    sayfa.screenshot(path=str(hedef), full_page=False)
    print(f"GORUNTU {hedef.name}", flush=True)


# --------------------------------------------------------------------------- sahneler


def _alt_kenari_bosluga_al(sayfa: Page) -> None:
    """Alt kenar bir kart sırasının yalnız üst çizgisini göstermesin.

    Genel Bakış'ın kartları alt alta dizilir (`space-y-5`). 1440×900'de alt kenar son tam
    kartın altındaki boşluğu birkaç piksel aşıyor, sonraki sıranın yalnız yuvarlatılmış üst
    çizgisi görünüyordu (boş kutu gibi). Bu durumda görünüm alanı 16:10 korunarak, son tam
    kartla kesilen sıra arasındaki boşluğun ortasına denk gelecek kadar küçültülür: DOM'a
    dokunulmaz, pencere yalnız biraz küçüktür. İçerik sütunu `max-w-4xl` olduğundan kartların
    eni ve boyu değişmez; WebP yine 1280×800'e ölçeklenir (`webp_cevir.py`). Kesilen sıranın
    görünen kısmı 48 px'ten büyükse (doğal kesim) hiçbir şey yapılmaz.
    """
    kenar = sayfa.evaluate(
        """(yukseklik) => {
            const kok = document.querySelector(".max-w-4xl.space-y-5");
            if (!kok) return null;
            const kutular = [...kok.children]
              .map((e) => e.getBoundingClientRect())
              .filter((r) => r.height > 0);
            const kesilen = kutular.find((r) => r.top < yukseklik && r.bottom > yukseklik);
            if (!kesilen || yukseklik - kesilen.top > 48) return null;
            const ustteki = kutular.filter((r) => r.bottom <= kesilen.top).pop();
            return ustteki ? (ustteki.bottom + kesilen.top) / 2 : null;
        }""",
        YUKSEKLIK,
    )
    if kenar is None:
        return
    yukseklik = int(kenar) // 5 * 5  # 16:10 tam sayıda kalsın
    sayfa.set_viewport_size({"width": yukseklik * 8 // 5, "height": yukseklik})
    _bekle(sayfa)


def genel_bakis(sayfa: Page, durum: dict[str, Any]) -> None:
    _git(sayfa, durum["yonetim_taban"], "/")
    _alt_kenari_bosluga_al(sayfa)


def katalog(sayfa: Page, durum: dict[str, Any]) -> None:
    """Eser listesi: Türkçe arama ("roman") ve Türkçe sıralama (Ç, Ğ, İ, Ö, Ş, Ü yerinde)."""
    _git(sayfa, durum["yonetim_taban"], "/katalog")
    sayfa.get_by_label("Ara", exact=True).fill(durum["sahne"]["katalog_aramasi"])
    sayfa.wait_for_timeout(700)  # arama kutusunun gecikmeli sorgusu
    _bekle(sayfa)


def _okut(sayfa: Page, kod: str) -> None:
    """Okuyucu gibi: kodu yazar ve Enter gönderir; masanın sırası bitene dek bekler."""
    kutu = sayfa.get_by_label("Üye kartı ya da kütüphane etiketi")
    kutu.press_sequentially(kod, delay=15)
    kutu.press("Enter")
    sayfa.wait_for_timeout(600)
    _bekle(sayfa)


def dolasim_masasi(sayfa: Page, durum: dict[str, Any]) -> None:
    """Ödünç akışı: önce üye kartı, sonra kitabın kütüphane etiketi (uydurma üye)."""
    _git(sayfa, durum["yonetim_taban"], "/dolasim")
    _okut(sayfa, durum["sahne"]["kart_no"])
    _okut(sayfa, durum["sahne"]["kitap_barkodu"])
    sayfa.wait_for_timeout(1500)  # okutma kutusunun kısa süreli başarı rengi sönsün
    _bekle(sayfa)


def etiketler(sayfa: Page, durum: dict[str, Any]) -> None:
    _git(sayfa, durum["yonetim_taban"], "/katalog/etiketler")


def raporlar(sayfa: Page, durum: dict[str, Any]) -> None:
    _git(sayfa, durum["yonetim_taban"], "/raporlar")


def eser_ayrintisi(sayfa: Page, durum: dict[str, Any]) -> None:
    _git(sayfa, durum["yonetim_taban"], f"/katalog/eser/{durum['sahne']['eser_id']}")


def ag_katalogu(sayfa: Page, durum: dict[str, Any]) -> None:
    """Tahta kipinde arama: büyük harfle yazılan sorgu Türkçe katlamayla eşleşir."""
    sayfa.goto(
        durum["katalog"] + "/ara?q=" + quote(durum["sahne"]["tahta_aramasi"]) + "&tahta=1",
        wait_until="networkidle",
    )
    sayfa.wait_for_timeout(300)


def ag_katalogu_vitrin(sayfa: Page, durum: dict[str, Any]) -> None:
    """Tahta kipinde ana sayfa: arama, dizinler, yeni gelenler ve çok okunanlar."""
    sayfa.goto(durum["katalog"] + "/?tahta=1", wait_until="networkidle")
    sayfa.wait_for_timeout(300)


Sahne = Callable[[Page, dict[str, Any]], None]

#: Görüntüler: (dosya adı, sahne, Ağ Kataloğu bağlamı mı). İlk altısı sitenin önerilen
#: sırasıdır; son ikisi seçenek olarak üretilir.
SAHNELER: tuple[tuple[str, Sahne, bool], ...] = (
    ("genel-bakis", genel_bakis, False),
    ("katalog", katalog, False),
    ("dolasim-masasi", dolasim_masasi, False),
    ("etiketler", etiketler, False),
    ("ag-katalogu", ag_katalogu, True),
    ("raporlar", raporlar, False),
    ("ag-katalogu-vitrin", ag_katalogu_vitrin, True),
    ("eser-ayrintisi", eser_ayrintisi, False),
)

#: Keşif kipinde ayrıca bakılan ekranlar (seçim için; siteye gitmez).
KESIF_YOLLARI: tuple[str, ...] = (
    "/kisiler",
    "/gecikmis-oduncler",
    "/dolasim/teslimler",
    "/katalog/sayim",
    "/katalog/edinimler",
    "/katalog/ice-aktarma",
    "/katalog/hizli-kayit",
    "/ayarlar",
    "/ag-doktoru",
    "/kilavuz",
    "/hakkinda",
)


def _baglam(tarayici: Browser, oran: float) -> Any:
    return tarayici.new_context(
        viewport={"width": GENISLIK, "height": YUKSEKLIK},
        device_scale_factor=oran,
        locale="tr-TR",
        timezone_id="Europe/Istanbul",
        color_scheme="light",
    )


def cek(cikti: Path, *, kesif: bool, secili: set[str]) -> int:
    durum_dosyasi = cikti / "durum.json"
    for _ in range(600):
        if durum_dosyasi.exists():
            break
        time.sleep(1)
    durum: dict[str, Any] = json.loads(durum_dosyasi.read_text(encoding="utf-8"))
    oran = 1.0 if kesif else 2.0
    klasor = cikti / ("kesif" if kesif else "png")
    try:
        with sync_playwright() as pw:
            # Yerleşik tarih kutuları (gg.aa.yyyy) tarayıcının ARAYÜZ dilini izler; bağlamın
            # `locale` ayarı yalnız navigator.language ve Accept-Language'dir. Yalın başsız
            # kabuk (varsayılan) `--lang`'i yok sayıp "dd.mm.yyyy" basıyor; tam Chromium'un
            # yeni başsız kipi (`channel="chromium"`) Windows'taki pencere gibi Türkçe basar.
            tarayici = pw.chromium.launch(channel="chromium", args=["--lang=tr-TR"])
            yonetim = _baglam(tarayici, oran)
            sayfa = yonetim.new_page()
            sayfa.goto(durum["yonetim"], wait_until="domcontentloaded")  # belirteç → çerez
            _bekle(sayfa)
            yonetici_kipi(sayfa, durum["parola"])
            tahta = _baglam(tarayici, oran)
            tahta_sayfasi = tahta.new_page()
            for ad, sahne, katalog_mu in SAHNELER:
                if secili and ad not in secili:
                    continue
                hedef_sayfa = tahta_sayfasi if katalog_mu else sayfa
                if not katalog_mu:
                    yonetici_kipi(sayfa, durum["parola"])
                sahne(hedef_sayfa, durum)
                _cek(hedef_sayfa, klasor / f"ekran-{ad}.png")
                # Sahne görünüm alanını küçültmüş olabilir (`_alt_kenari_bosluga_al`).
                hedef_sayfa.set_viewport_size({"width": GENISLIK, "height": YUKSEKLIK})
            if kesif:
                for yol in KESIF_YOLLARI:
                    yonetici_kipi(sayfa, durum["parola"])
                    _git(sayfa, durum["yonetim_taban"], yol)
                    _cek(sayfa, klasor / f"kesif{yol.replace('/', '-')}.png")
                tahta_sayfasi.goto(durum["katalog"] + "/?tahta=1", wait_until="networkidle")
                _cek(tahta_sayfasi, klasor / "kesif-katalog-ana.png")
            tarayici.close()
    finally:
        (cikti / "bitti").touch()
    return 0


def main(argv: list[str]) -> int:
    ayri = argparse.ArgumentParser(description="Kütüphane Defteri ekran görüntüleri")
    ayri.add_argument("--cikti", type=Path, required=True)
    ayri.add_argument("--kesif", action="store_true", help="bütün ekranlar, 1x (seçim için)")
    ayri.add_argument("--sahne", action="append", default=[], help="yalnız bu sahne(ler)")
    secenek = ayri.parse_args(argv)
    return cek(secenek.cikti, kesif=secenek.kesif, secili=set(secenek.sahne))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
