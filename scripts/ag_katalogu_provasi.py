"""Ağ Kataloğu provası: ikinci bilgisayardan arama + 50 istemcili yük (tasarım §14.1 F5).

İki Docker kabı iki ayrı bilgisayar yerine geçer (aynı compose ağı, farklı IP).
`ag_katalogu_provasi.sh` bu betiği alt komutlarla çağırır:

    sun [sn]                  kap A: gerçek masaüstü yolu — prepare_django + göç, yönetici
                              parolası, 10.000 eserlik sentetik katalog, yönetim sunucusu
                              127.0.0.1'de (oturum belirteçli), "Aç" ayarı ve
                              `KatalogKontrol` ile Ağ Kataloğu 0.0.0.0:8765'te
    iste <A-ip> <yön-port>    kap B: "ŞİİR" araması (TR katlama → "Safahat"), imza, CSP,
                              çerez yok; yönetim yolu katalog portunda 404; A'nın
                              yönetim portuna ağdan bağlantı KURULAMAZ
    yokla <sn> <etiket>       kap A'da AYRI süreç: yönetim API'sine düzenli istek (masadaki
                              kişinin pano ve liste sorguları), gecikme ölçümü
    yuk <A-ip> <sn> <n> <ağ> <ilk> <son> <düşünme-sn>
                              kap B: n eşzamanlı istemci, her biri AYRI kaynak IP'den
                              (NET_ADMIN ile ağ kartına ikincil adres — okul ağında her
                              tahta ayrı bir IP'dir; hız sınırı ve TB2 bağlantı sınırı
                              gerçek dağılımla sınanır)

Her adım başarıda bir nöbetçi satırı basar (`ADIM_OK_<ad>`); kabuk betiği onları
arar (bu makinede `docker compose run` çıkış kodunu zaman zaman yutar).

Kanıt için katalog uygulaması bir sarmalla sarılır: YENİ görülen istemci adresini
yalnız BU PROVADA standart çıktıya yazar. Üründe erişim günlüğü YOKTUR (§5.5).
Veriler uydurmadır (`apps/kutuphane/tests/sentetik_katalog.py`: kamu malı eser
adları, sağlaması tutan uydurma ISBN); kişi kaydı yoktur.
"""

from __future__ import annotations

import asyncio
import errno
import ipaddress
import json
import os
import random
import secrets
import socket
import statistics
import struct
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

DEPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEPO))

PORT = 8765
IMZA = b'<meta name="kd-katalog" content="1">'
DURUM_DOSYASI = Path("/tmp/kd-prova.json")  # noqa: S108 — yalnız prova kabının içi
PAROLA = "Prova-Parolasi-2026"  # noqa: S105 — uydurma; geçici veri dizini
ESER_SAYISI = int(os.environ.get("KD_PROVA_ESER", "10000"))

#: Eşikler. Yönetim p95 tavanı `desktop/tests/test_katalog_yuk.py` ile aynıdır.
#: Katalog tavanı kaba bir akıl sınırıdır: düşünmesiz yükte gecikmenin çoğu
#: 4 iş parçacıklı havuzun kuyruğudur (Little: 50 istemci / saniyedeki istek).
YONETIM_P95_TAVANI_MS = 500.0
KATALOG_P95_TAVANI_MS = 2000.0


# --------------------------------------------------------------------------- A: sun


def _katalog_tohumla(adet: int) -> tuple[int, int]:
    """`katalog/tests/test_olcum.py` ile aynı toplu yazım (anahtarlar `keys`'ten)."""
    from datetime import date

    from apps.kutuphane import isbn as isbn_module
    from apps.kutuphane import keys
    from apps.kutuphane.models import Acquisition, AcquisitionMethod, Copy, CopyStatus, Work
    from apps.kutuphane.tests import sentetik_katalog

    edinim = Acquisition.objects.create(
        method=AcquisitionMethod.EXISTING_STOCK, date=date(2026, 9, 1)
    )
    eserler = []
    for sira, satir in enumerate(sentetik_katalog.sentetik_satirlar(adet), start=1):
        baslik = str(satir["title"])
        yazar = str(satir.get("authors") or "")
        konu = str(satir.get("subjects") or "")
        isbn = str(satir.get("isbn") or "")
        isbn13 = isbn_module.to_isbn13(isbn)
        eserler.append(
            Work(
                title=baslik,
                authors=yazar,
                subjects=konu,
                isbn=isbn,
                isbn13=isbn13,
                classification_code=f"{sira % 10}{sira % 100:02d}",
                search_key=keys.work_search_key(
                    title=baslik, authors=yazar, subjects=konu, isbn=isbn, isbn13=isbn13
                ),
                sort_key=keys.tr_collation_key(baslik),
                author_sort_key=keys.tr_collation_key(keys.author_sort_name(yazar)),
                subject_sort_key=keys.tr_collation_key(keys.first_subject(konu)),
            )
        )
    Work.objects.bulk_create(eserler, batch_size=2000)
    nushalar = []
    no = 0
    for work in Work.objects.only("pk").order_by("pk"):
        for kopya in range(2):
            no += 1
            nushalar.append(
                Copy(
                    work_id=work.pk,
                    acquisition=edinim,
                    accession_no=2026_000000 + no,
                    barcode=f"{2026_000000 + no}",
                    status=CopyStatus.ON_LOAN if (no % 7 == 0) else CopyStatus.AVAILABLE,
                    is_reference=kopya == 1 and no % 11 == 0,
                )
            )
    Copy.objects.bulk_create(nushalar, batch_size=5000)
    kimlikler = list(Work.objects.order_by("pk").values_list("pk", flat=True))
    return kimlikler[0], kimlikler[-1]


def _sun(sure_sn: int) -> int:
    token = secrets.token_urlsafe(24)
    os.environ["KD_SESSION_TOKEN"] = token  # ayarlar okunmadan ÖNCE (desktop/main.py sırası)

    from desktop.django_bootstrap import (
        assert_session_guard_installed,
        build_wsgi_application,
        prepare_django,
        run_migrations,
        wal_checkpoint,
    )
    from desktop.paths import resolve_backend_dir

    veri = Path(tempfile.mkdtemp(prefix="kd-prova-"))
    prepare_django(resolve_backend_dir(), veri)
    run_migrations()

    bas = time.perf_counter()
    ilk, son = _katalog_tohumla(ESER_SAYISI)
    print(
        f"TOHUM {ESER_SAYISI} eser, {ESER_SAYISI * 2} nüsha, {time.perf_counter() - bas:.1f} sn",
        flush=True,
    )

    from apps.okul.services import app_password

    app_password.enable(password=PAROLA)  # gerçek kurulum: parola kurulu, yönetici kipi

    from katalog import app as katalog_app

    from apps.kutuphane.services.katalog_ayari import update_katalog_ayari
    from desktop.katalog_kontrol import KatalogKontrol
    from desktop.katalog_server import CatalogApp, load_catalog
    from desktop.server import BackgroundServer, check_health

    application = build_wsgi_application()
    assert_session_guard_installed()
    yonetim = BackgroundServer(application)
    yonetim.start()
    yonetim.wait_until_ready()
    check_health(yonetim.base_url, token)

    update_katalog_ayari(sistem_yazimi=True, acik=True)  # Ayarlar → Ağ Kataloğu → Aç

    katalog = load_catalog()
    gorulen: set[str] = set()
    kilit = threading.Lock()

    def kanitli(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        adres = str(environ.get("REMOTE_ADDR"))
        with kilit:
            yeni = adres not in gorulen
            gorulen.add(adres)
        if yeni:
            print(f"YENI_ADRES {adres}\n", end="", flush=True)
        return katalog.application(environ, start_response)

    kontrol = KatalogKontrol(yukleyici=lambda: CatalogApp(kanitli, katalog.signature))
    kontrol.acilista_baslat()
    durum = kontrol.durum()
    ozet = {k: durum[k] for k in ("durum", "tum_arayuzler", "port", "adres", "son_hata")}
    print("KONTROL_DURUMU " + json.dumps(ozet, ensure_ascii=False), flush=True)
    if durum["durum"] != "acik":
        kontrol.kapanis()
        yonetim.stop()
        return 1

    DURUM_DOSYASI.write_text(
        json.dumps({"yonetim_port": yonetim.port, "token": token}), encoding="utf-8"
    )
    kendi_ip = socket.gethostbyname(socket.gethostname())
    print(
        f"KATALOG_HAZIR {kendi_ip}:{PORT} yonetim_port={yonetim.port} eser={ilk}-{son}",
        flush=True,
    )

    bitis = time.monotonic() + sure_sn
    son_canli = time.monotonic()
    try:
        while time.monotonic() < bitis:
            time.sleep(5)
            if time.monotonic() - son_canli > 60:
                # Masadaki yöneticinin etkinliği (§4.4 boşta süresi 3 dk): prova uzarsa
                # yönetici kipi görevli kipine inip yönetim ölçümünü 403'e çevirmesin.
                _yonetim_istegi(yonetim.port, token, "/api/v1/security/mode/")
                son_canli = time.monotonic()
            sayac = {
                "gun": katalog_app.application.sayaclar.gun(),
                "reddedilen_baglanti": kontrol.durum()["reddedilen_baglanti"],
                "farkli_adres": len(gorulen),
            }
            print("SAYAC " + json.dumps(sayac, ensure_ascii=False), flush=True)
    finally:
        kontrol.kapanis()
        yonetim.stop()
        wal_checkpoint(veri / "db.sqlite3")
    return 0


# --------------------------------------------------------------------------- A: yokla


def _yonetim_istegi(port: int, token: str, yol: str) -> tuple[int, float]:
    istek = urllib.request.Request(  # noqa: S310 — sabit http://127.0.0.1
        f"http://127.0.0.1:{port}{yol}",
        headers={"X-KD-Token": token, "X-KD-Etkinlik": "1", "Accept": "application/json"},
    )
    bas = time.perf_counter()
    try:
        with urllib.request.urlopen(istek, timeout=30) as yanit:  # noqa: S310
            yanit.read()
            kod = int(yanit.status)
    except urllib.error.HTTPError as hata:
        hata.read()
        kod = int(hata.code)
    except OSError:
        kod = 0
    return kod, time.perf_counter() - bas


def _yuzdelik(degerler: list[float], oran: float) -> float:
    sirali = sorted(degerler)
    return sirali[min(len(sirali) - 1, max(0, round(oran * len(sirali)) - 1))]


def _ozet_ms(degerler: list[float]) -> dict[str, float]:
    if not degerler:
        return {}
    return {
        "medyan_ms": round(statistics.median(degerler) * 1000, 1),
        "p95_ms": round(_yuzdelik(degerler, 0.95) * 1000, 1),
        "p99_ms": round(_yuzdelik(degerler, 0.99) * 1000, 1),
        "en_uzun_ms": round(max(degerler) * 1000, 1),
    }


#: Masadaki kişinin arayüzünün attığı istek türleri: durum yoklaması, kip
#: göstergesi, katalog araması ve sayfalı liste (TR sıralı, 10.000 eserde).
YONETIM_YOLLARI = (
    ("saglik", "/api/v1/setup/status/"),
    ("kip", "/api/v1/security/mode/"),
    ("eser_arama", "/api/v1/library/works/?q=roman&page=1"),
    ("eser_listesi", "/api/v1/library/works/?page=3"),
)


def _yokla(sure_sn: float, etiket: str) -> int:
    bilgi = json.loads(DURUM_DOSYASI.read_text(encoding="utf-8"))
    port, token = int(bilgi["yonetim_port"]), str(bilgi["token"])
    sureler: dict[str, list[float]] = {ad: [] for ad, _ in YONETIM_YOLLARI}
    kodlar: Counter[str] = Counter()
    bitis = time.monotonic() + sure_sn
    sira = 0
    while time.monotonic() < bitis:
        ad, yol = YONETIM_YOLLARI[sira % len(YONETIM_YOLLARI)]
        sira += 1
        kod, sure = _yonetim_istegi(port, token, yol)
        kodlar[f"{ad}:{kod}"] += 1
        if kod == 200:
            sureler[ad].append(sure)
        time.sleep(0.1)
    tumu = [s for liste in sureler.values() for s in liste]
    tumu_ozet = _ozet_ms(tumu)
    basarisiz = sum(n for k, n in kodlar.items() if not k.endswith(":200"))
    sonuc = {
        "etiket": etiket,
        "istek": sira,
        "basarisiz": basarisiz,
        "kodlar": dict(kodlar),
        "tumu": tumu_ozet,
        "uclar": {ad: {"n": len(liste), **_ozet_ms(liste)} for ad, liste in sureler.items()},
    }
    print("YONETIM_SONUC " + json.dumps(sonuc, ensure_ascii=False), flush=True)
    if basarisiz or not tumu:
        print(f"HATA: yönetim isteklerinden {basarisiz} tanesi başarısız.", file=sys.stderr)
        return 1
    p95 = tumu_ozet["p95_ms"]
    if p95 >= YONETIM_P95_TAVANI_MS:
        print(f"HATA: yönetim p95 {p95} ms ≥ {YONETIM_P95_TAVANI_MS} ms.", file=sys.stderr)
        return 1
    print(f"ADIM_OK_yonetim_{etiket}", flush=True)
    return 0


# --------------------------------------------------------------------------- B: iste


def _get(hedef: str, yol: str) -> tuple[int, bytes, Any]:
    try:
        with urllib.request.urlopen(f"http://{hedef}:{PORT}{yol}", timeout=10) as yanit:  # noqa: S310
            return int(yanit.status), yanit.read(), yanit.headers
    except urllib.error.HTTPError as hata:
        return int(hata.code), hata.read(), hata.headers


def _iste(hedef: str, yonetim_port: int) -> int:
    kendi_ip = socket.gethostbyname(socket.gethostname())
    durum, govde, basliklar = _get(hedef, "/ara?" + urllib.parse.urlencode({"q": "ŞİİR"}))
    assert durum == 200, durum
    assert IMZA in govde, "katalog imzası yok"
    assert b"Safahat" in govde, "TR katlamalı arama sonucu yok (ŞİİR → konu 'şiir')"
    assert "default-src 'none'" in basliklar.get("Content-Security-Policy", "")
    assert basliklar.get("X-Content-Type-Options") == "nosniff"
    assert basliklar.get("Set-Cookie") is None
    assert basliklar.get("Server") is None
    kucuk, govde2, _ = _get(hedef, "/ara?" + urllib.parse.urlencode({"q": "şiir"}))
    assert kucuk == 200 and b"Safahat" in govde2
    yonetim_yolu, _, _ = _get(hedef, "/api/v1/setup/status/")
    assert yonetim_yolu == 404, yonetim_yolu
    try:
        socket.create_connection((hedef, yonetim_port), timeout=3).close()
        yonetim_portu = "ACIK"
    except OSError as exc:
        yonetim_portu = f"kapali ({type(exc).__name__})"
    assert yonetim_portu.startswith("kapali"), "yönetim portu ağdan erişilebilir"
    print(
        f"ARAMA_TAMAM kaynak={kendi_ip} hedef={hedef}:{PORT} q=ŞİİR durum={durum} imza=var "
        f"safahat=bulundu csp=var cerez=yok yonetim_yolu={yonetim_yolu} "
        f"yonetim_portu[{yonetim_port}]={yonetim_portu}",
        flush=True,
    )
    print("ADIM_OK_ikinci_bilgisayar", flush=True)
    return 0


# --------------------------------------------------------------------------- B: yuk


def _varsayilan_arayuz() -> str:
    for satir in Path("/proc/net/route").read_text().splitlines()[1:]:
        alanlar = satir.split()
        if len(alanlar) > 1 and alanlar[1] == "00000000":
            return alanlar[0]
    return "eth0"


def _ip_ekle(arayuz: str, ip: str, onek: int) -> None:
    """Ağ kartına ikincil IPv4 adresi (netlink RTM_NEWADDR; imajda `ip` aracı yok)."""
    rtm_newaddr, ifa_address, ifa_local = 20, 1, 2
    bayrak = 0x1 | 0x4 | 0x200 | 0x400  # REQUEST | ACK | EXCL | CREATE
    adres = socket.inet_aton(ip)
    govde = (
        struct.pack("BBBBI", socket.AF_INET, onek, 0, 0, socket.if_nametoindex(arayuz))
        + struct.pack("HH", 8, ifa_local)
        + adres
        + struct.pack("HH", 8, ifa_address)
        + adres
    )
    ileti = struct.pack("IHHII", 16 + len(govde), rtm_newaddr, bayrak, 1, 0) + govde
    with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE) as s:
        s.bind((0, 0))
        s.send(ileti)
        yanit = s.recv(4096)
    if struct.unpack_from("H", yanit, 4)[0] == 2:  # NLMSG_ERROR
        kod = struct.unpack_from("i", yanit, 16)[0]
        if kod not in (0, -errno.EEXIST):
            raise OSError(-kod, f"ikincil adres eklenemedi: {os.strerror(-kod)}")


ARAMALAR = ("şiir", "ROMAN", "madonna", "Çalıkuşu", "tanpınar", "dostoyevski", "sözlük", "ılık")
HARFLER = tuple("ABÇGHKMSŞT")


def _sayfa_sec(rng: random.Random, ilk: int, son: int) -> tuple[str, str]:
    """Tahtadaki bir öğrencinin gezinmesine benzeyen karışım: (tür, yol)."""
    zar = rng.random()
    if zar < 0.10:
        return "ana", "/"
    if zar < 0.45:
        return "ara", "/ara?" + urllib.parse.urlencode({"q": rng.choice(ARAMALAR)})
    if zar < 0.55:
        sayfa = rng.randint(2, 40)
        return "ara_sayfa", "/ara?" + urllib.parse.urlencode({"q": "roman", "sayfa": sayfa})
    if zar < 0.75:
        return "eser", f"/eser/{rng.randint(ilk, son)}"
    if zar < 0.85:
        return "eserler_harf", "/eserler/" + urllib.parse.quote(rng.choice(HARFLER))
    if zar < 0.90:
        return "yazarlar_harf", "/yazarlar/" + urllib.parse.quote(rng.choice(HARFLER))
    if zar < 0.95:
        return "konular", "/konular"
    if zar < 0.98:
        return "hakkinda", "/hakkinda"
    return "css", "/katalog.css"


async def _istek(hedef: str, kaynak: str, yol: str) -> tuple[int, bool]:
    """Tek istek, her seferinde YENİ bağlantı (`Connection: close` — en kötü durum)."""
    okuyucu, yazici = await asyncio.wait_for(
        asyncio.open_connection(hedef, PORT, local_addr=(kaynak, 0)), 10
    )
    try:
        yazici.write(
            (
                f"GET {yol} HTTP/1.1\r\nHost: {hedef}:{PORT}\r\nUser-Agent: kd-yuk-provasi\r\n"
                "Accept: text/html\r\nConnection: close\r\n\r\n"
            ).encode("ascii")
        )
        await yazici.drain()
        veri = await asyncio.wait_for(okuyucu.read(-1), 30)
    finally:
        yazici.close()
    if not veri.startswith(b"HTTP/1."):
        return -1, False
    return int(veri.split(b" ", 2)[1]), IMZA in veri


async def _istemci(
    hedef: str,
    kaynak: str,
    aralik: tuple[int, int],
    bitis: float,
    dusunme_sn: float,
    tohum: int,
    sonuclar: list[tuple[str, int, float, bool]],
) -> None:
    rng = random.Random(tohum)  # noqa: S311 — yük karışımı, güvenlik değil
    while time.monotonic() < bitis:
        tur, yol = _sayfa_sec(rng, *aralik)
        bas = time.perf_counter()
        try:
            kod, imzali = await _istek(hedef, kaynak, yol)
        except TimeoutError:
            kod, imzali = -2, False
        except OSError:
            kod, imzali = 0, False
        sonuclar.append((tur, kod, time.perf_counter() - bas, imzali))
        if dusunme_sn:
            await asyncio.sleep(rng.uniform(0.5, 1.5) * dusunme_sn)


def _yuk(
    hedef: str, sure_sn: float, istemci: int, ag: str, aralik: tuple[int, int], dusunme_sn: float
) -> int:
    arayuz = _varsayilan_arayuz()
    alt_ag = ipaddress.ip_network(ag)
    ust = int(alt_ag.broadcast_address) - 1  # Docker adresleri alttan dağıtır; üstten al
    kaynaklar = [str(ipaddress.ip_address(ust - i)) for i in range(istemci)]
    for ip in kaynaklar:
        _ip_ekle(arayuz, ip, alt_ag.prefixlen)
    print(f"KAYNAK_ADRESLER {istemci} adet: {kaynaklar[-1]} … {kaynaklar[0]}", flush=True)

    sonuclar: list[tuple[str, int, float, bool]] = []

    async def hepsi() -> float:
        bas = time.monotonic()
        bitis = bas + sure_sn
        await asyncio.gather(
            *(
                _istemci(hedef, ip, aralik, bitis, dusunme_sn, 1000 + i, sonuclar)
                for i, ip in enumerate(kaynaklar)
            )
        )
        return time.monotonic() - bas

    gecen = asyncio.run(hepsi())
    kodlar = Counter(kod for _, kod, _, _ in sonuclar)
    basarili = [sure for _, kod, sure, _ in sonuclar if kod == 200]
    yanit_ozet = _ozet_ms(basarili)
    imzasiz = sum(1 for tur, kod, _, imz in sonuclar if kod == 200 and tur != "css" and not imz)
    turler: dict[str, list[float]] = {}
    for tur, kod, sure, _ in sonuclar:
        if kod == 200:
            turler.setdefault(tur, []).append(sure)
    hata = sum(n for kod, n in kodlar.items() if kod not in (200, 429))
    sonuc = {
        "istemci": istemci,
        "kaynak_ip": len(set(kaynaklar)),
        "sure_sn": round(gecen, 1),
        "dusunme_sn": dusunme_sn,
        "istek": len(sonuclar),
        "saniyede": round(len(sonuclar) / gecen, 1),
        "kodlar": {str(k): n for k, n in sorted(kodlar.items())},
        "hata": hata,
        "hiz_siniri_429": kodlar.get(429, 0),
        "imzasiz_html_200": imzasiz,
        "yanit_200": yanit_ozet,
        "turler": {t: {"n": len(v), **_ozet_ms(v)} for t, v in sorted(turler.items())},
    }
    print("YUK_SONUC " + json.dumps(sonuc, ensure_ascii=False), flush=True)
    sorunlar = []
    if not basarili:
        sorunlar.append("hiç başarılı yanıt yok")
    if hata:
        sorunlar.append(f"{hata} hatalı yanıt ya da bağlantı hatası")
    if kodlar.get(429, 0):
        sorunlar.append(f"{kodlar[429]} istek hız sınırına takıldı (her istemci ayrı IP'de)")
    if imzasiz:
        sorunlar.append(f"{imzasiz} sayfada katalog imzası yok")
    if basarili and yanit_ozet["p95_ms"] >= KATALOG_P95_TAVANI_MS:
        sorunlar.append(f"katalog p95 ≥ {KATALOG_P95_TAVANI_MS} ms")
    if sorunlar:
        print("HATA: " + "; ".join(sorunlar), file=sys.stderr)
        return 1
    print("ADIM_OK_yuk", flush=True)
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["sun"]:
        return _sun(int(argv[1]) if len(argv) > 1 else 1200)
    if argv[:1] == ["yokla"] and len(argv) == 3:
        return _yokla(float(argv[1]), argv[2])
    if argv[:1] == ["iste"] and len(argv) == 3:
        return _iste(argv[1], int(argv[2]))
    if argv[:1] == ["yuk"] and len(argv) == 8:
        hedef, sure, istemci, ag, ilk, son, dusunme = argv[1:]
        return _yuk(hedef, float(sure), int(istemci), ag, (int(ilk), int(son)), float(dusunme))
    print(
        "kullanım: ag_katalogu_provasi.py sun [sn] | yokla <sn> <etiket> | "
        "iste <A-ip> <yön-port> | yuk <A-ip> <sn> <istemci> <ağ> <ilk> <son> <düşünme-sn>",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
