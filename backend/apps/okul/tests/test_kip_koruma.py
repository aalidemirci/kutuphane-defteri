"""Kip koruma testleri — tasarım §5.10-8 (F1 iskeleti) ve §5.10-14.

§5.10-8: görevli kipinde izin listesi dışındaki BÜTÜN `/api/` uçları, her
yöntemde 403 `kip_yetkisiz` döner. Uç listesi ELLE TUTULMAZ: URL desenleri
çalışma anında dolaşılır (`katalog/tests/test_koruma.py::_api_desenleri`, F0
§5.10-2 gezgini; dönüştürücüler örnek değerle doldurulur). Başka kolların
eklediği her yeni uç (takvim, kütüphane şablonu, F2+ dolaşım…) bu teste
kendiliğinden girer ve izin listesine bilinçli eklenmedikçe kapalıdır.
F6'da doldu: uç + PARAMETRE kuralları (`override_reason` ya da kartsız ödünç
alanı taşıyan ödünç 403, katalog okumada sorgu parametresi sınırı) burada;
görevli yanıtlarının alan listesi anlık görüntüsü
`apps/kutuphane/tests/test_masa_gorevli_yuzeyi.py`'dedir.

§5.10-14: `X-KD-Etkinlik` başlığı olmayan periyodik istekler yönetici kipini
canlı tutmaz; başlıklı istekler tutar; mutlak süre dolunca görevli kipine
inilir ve yükseltme yönetici parolası ister.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from typing import Any

import pytest
from desktop.server import HEALTH_PATH
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.urls import resolve

from apps.okul import kip_middleware
from apps.okul.kip import KIP, KipSureleri
from apps.okul.kip_izinleri import (
    IZIN_LISTESI,
    IzinKurali,
    govdede_yok,
    izinli_mi,
    yalniz_sorgu,
)
from apps.okul.kip_middleware import (
    HIC_KESILMEYEN_YOLLAR,
    HIC_KESILMEYEN_YONTEMLER,
    KipMiddleware,
)
from apps.okul.services import app_password
from apps.okul.tests.kip_ortak import (
    DOGRU_PAROLA,
    SahteSaat,
    kurulum_durumunu_yaz,
    sahte_dogrulayici,
)
from katalog.tests.test_koruma import SAGLIK_YOLU, _api_desenleri

pytestmark = pytest.mark.django_db

YONTEMLER = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
ETKINLIK = {"X-KD-Etkinlik": "1"}
VERI_UCU = "/api/v1/grade-levels/"
MOD = "/api/v1/security/mode/"


def _api_uclari() -> list[tuple[str, str, str]]:
    """(Django rotası, örnek yol, URL adı) — her `/api/` deseni için."""
    return [(rota, ornek, resolve(ornek).view_name) for rota, ornek in _api_desenleri()]


def _izinli_cift(uc: str, yontem: str) -> bool:
    return any(k.uc == uc and k.yontem == yontem for k in IZIN_LISTESI)


def _gecti(_request: HttpRequest) -> HttpResponse:
    return HttpResponse("gecti")


def _yalniz_kip_kapisi(yontem: str, yol: str) -> HttpResponse:
    """Yalnız KipMiddleware'den geçirir; görünüm KOŞMAZ (yan etkisiz)."""
    istek = RequestFactory().generic(yontem, yol)
    return KipMiddleware(_gecti)(istek)


def _kip_yetkisiz_mi(resp: Any, yontem: str) -> bool:
    if resp.status_code != 403:
        return False
    if yontem == "HEAD":  # test istemcisi HEAD yanıtının gövdesini atar
        return True
    govde: dict[str, Any] = resp.json()
    return govde.get("code") == "kip_yetkisiz"


@pytest.fixture
def gorevli() -> Iterator[None]:
    KIP.gorevliye_gec()
    yield
    assert KIP.durum() == "gorevli", "dolaşma sırasında kip değişti"


# ============================================================ §5.10-8 izin listesi


def test_izin_listesi_anlik_goruntuyle_sabittir() -> None:
    """Listeye uç eklemek bilinçli bir karardır: bu anlık görüntü de güncellenir."""
    assert sorted((k.uc, k.yontem) for k in IZIN_LISTESI) == [
        # Çık (F5, §4.2-4): görevli kipinde gövdede yönetici parolası ister, parolasız
        # istek görünümde 403 alır (test_cikis_ucu.py, §5.10-18).
        ("app-quit", "POST"),
        # F6 dolaşım masası (§4.4 tablosu, §7.3): ödünç ver, barkodla iade.
        ("library-checkout", "POST"),
        # Katalog okuma (F6, §4.4): works/copies GET, yanıt Ağ Kataloğuna denk.
        ("library-copy-list", "GET"),
        # F7 teslimden geri alma okutması (§4.4, U11); yanıt görevli kipinde daralır.
        ("library-delivery-take-back", "POST"),
        # GA-7: art arda geçersiz kart okutmasından sonra gövdede yönetici parolası.
        ("library-desk-card-unlock", "POST"),
        # Nüsha durum sorgusu ve kartla üye çözme (yalnız ad + kalan hak).
        ("library-desk-copy-status", "GET"),
        ("library-desk-member", "POST"),
        # F9 (madde 26): masanın kişisiz durumu — hizmet arası ve süren sayımın okutması.
        ("library-desk-state", "GET"),
        # Etiket doğrulama okutması (F4, kullanıcı kararı 24.09.2026). Yanıt görevli
        # kipinde daralır; öbür etiket uçları kapalıdır (test_etiket_kuyrugu_uclari.py).
        ("library-label-verify", "POST"),
        ("library-return", "POST"),
        # F9 sayım okutması (madde 24, kullanıcı kararı 25.09.2026). Yanıt görevli kipinde
        # daralır; öbür sayım uçları kapalıdır (test_sayim_uclari.py).
        ("library-stocktake-scan", "POST"),
        ("library-work-detail", "GET"),
        ("library-work-list", "GET"),
        ("security-lock", "POST"),
        ("security-mode", "GET"),
        ("security-mode-admin", "POST"),
        ("security-status", "GET"),
        ("setup-status", "GET"),
    ]


def test_parametre_kurallari_anlik_goruntuyle_sabittir() -> None:
    """§5.10-8 (F6 dolu): uç + PARAMETRE. Görevli istisnalı/kartsız ödünç veremez,
    üyeyi üyelik kaydıyla açamaz; katalogda edinim partisine, eski kayıt no'ya göre süzemez."""
    kurallar = {(k.uc, k.yontem): k.parametre for k in IZIN_LISTESI if k.parametre is not None}
    assert kurallar == {
        ("library-checkout", "POST"): govdede_yok(
            "override_reason", "override_note", "cardless", "cardless_reason", "membership_id"
        ),
        ("library-desk-member", "POST"): govdede_yok("membership_id"),
        ("library-desk-copy-status", "GET"): yalniz_sorgu("barcode"),
        ("library-desk-state", "GET"): yalniz_sorgu(),
        ("library-work-list", "GET"): yalniz_sorgu(
            "q", "order", "resource_type", "section", "limit", "offset"
        ),
        ("library-work-detail", "GET"): yalniz_sorgu(),
        ("library-copy-list", "GET"): yalniz_sorgu(
            "work", "section", "status", "only_loanable", "limit", "offset"
        ),
    }


ODUNC_YOLU = "/api/v1/library/checkout/"
UYE_YOLU = "/api/v1/library/desk/member/"


@pytest.mark.parametrize(
    "govde",
    [
        {"override_reason": "COURSE_NEED", "override_note": "x"},
        {"override_reason": ""},
        {"override_note": "x"},
        {"cardless": True},
        {"cardless_reason": "CARD_LOST"},
        {"membership_id": 1},
    ],
)
def test_gorevli_kipinde_istisnali_ya_da_kartsiz_odunc_403(
    gorevli: None, govde: dict[str, Any]
) -> None:
    """`override_reason` (ya da kartsız ödünç alanı) TAŞIYAN ödünç 403 — değeri boş olsa da."""
    resp = Client().post(
        ODUNC_YOLU, {"card_no": "94718263", "barcode": "2026000001", **govde}, "application/json"
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "kip_yetkisiz"


def test_gorevli_kipinde_yasak_alan_sorgu_dizesinde_de_403(gorevli: None) -> None:
    resp = Client().post(
        ODUNC_YOLU + "?override_reason=COURSE_NEED",
        {"card_no": "94718263", "barcode": "2026000001"},
        "application/json",
    )
    assert resp.status_code == 403


@pytest.mark.parametrize(
    ("icerik", "govde"),
    [
        ("application/x-www-form-urlencoded", "card_no=94718263&override_reason=X"),
        ("text/plain", '{"card_no": "94718263"}'),
        ("application/json", "[1, 2]"),
        ("application/json", "{bozuk"),
    ],
)
def test_gorevli_kipinde_json_olmayan_ya_da_okunamayan_govde_403(
    gorevli: None, icerik: str, govde: str
) -> None:
    """Denetçi okuyamadığı gövdeyi geçirmez (fail-closed)."""
    resp = Client().generic("POST", ODUNC_YOLU, govde, content_type=icerik)
    assert resp.status_code == 403
    assert resp.json()["code"] == "kip_yetkisiz"


@pytest.mark.parametrize(
    ("charset", "govde"),
    [
        # utf-7'de "+AF8-" alt çizgidir: denetçi `override+AF8-reason`, DRF `override_reason`
        # görürdü (F6 düzeltme turu).
        ("utf-7", b'{"card_no":"94718263","barcode":"1","override+AF8-reason":"OTHER"}'),
        ("utf-16", '{"card_no":"94718263","barcode":"1"}'.encode("utf-16")),
        ("UTF-7", b'{"card_no":"94718263","barcode":"1"}'),
        ("latin-1", b'{"card_no":"94718263","barcode":"1"}'),
    ],
)
def test_gorevli_kipinde_utf8_disi_karakter_kumesi_403(
    gorevli: None, charset: str, govde: bytes
) -> None:
    """Denetçi ile görünüm aynı baytları farklı okuyamasın: `charset` yalnız UTF-8."""
    for yol in (ODUNC_YOLU, UYE_YOLU):
        resp = Client().generic(
            "POST", yol, govde, content_type=f"application/json; charset={charset}"
        )
        assert resp.status_code == 403, (yol, charset)
        assert resp.json()["code"] == "kip_yetkisiz"


@pytest.mark.parametrize("charset", ["utf-8", "UTF-8", "utf8", '"utf-8"'])
def test_gorevli_kipinde_utf8_karakter_kumesi_gecer(gorevli: None, charset: str) -> None:
    resp = Client().generic(
        "POST",
        UYE_YOLU,
        b'{"card_no":"94718263"}',
        content_type=f"application/json; charset={charset}",
    )
    assert resp.status_code == 200


def test_gorevli_kipinde_kartla_odunc_ve_uye_cozme_kapidan_gecer(gorevli: None) -> None:
    """Yasak alan yoksa istek görünüme ulaşır (görünüm kendi kararını verir; 403 değil)."""
    odunc = Client().post(
        ODUNC_YOLU, {"card_no": "94718263", "barcode": "2026000001"}, "application/json"
    )
    uye = Client().post(UYE_YOLU, {"card_no": "94718263"}, "application/json")
    assert odunc.status_code != 403
    assert uye.status_code == 200
    kartsiz = Client().post(UYE_YOLU, {"membership_id": 1}, "application/json")
    assert kartsiz.status_code == 403


@pytest.mark.parametrize(
    ("yol", "sorgu", "gecer"),
    [
        ("/api/v1/library/works/", "?q=%C5%9Fiir&order=title&limit=25&offset=0", True),
        ("/api/v1/library/works/", "?acquisition=1", False),
        ("/api/v1/library/works/", "?q=x&format=json", False),
        ("/api/v1/library/works/1/", "", True),
        ("/api/v1/library/works/1/", "?x=1", False),
        ("/api/v1/library/copies/", "?work=1&only_loanable=true", True),
        ("/api/v1/library/copies/", "?acquisition=1", False),
        ("/api/v1/library/copies/", "?old_register_no=12", False),
        ("/api/v1/library/copies/", "?barcode=2026000001", False),
        ("/api/v1/library/desk/copy-status/", "?barcode=2026000001", True),
        ("/api/v1/library/desk/copy-status/", "?barcode=2026000001&loan=1", False),
    ],
)
def test_gorevli_kipinde_katalog_okumada_sorgu_parametresi_siniri(
    gorevli: None, yol: str, sorgu: str, gecer: bool
) -> None:
    resp = _yalniz_kip_kapisi("GET", yol + sorgu)
    assert (resp.content == b"gecti") is gecer


def test_izin_listesindeki_her_uc_gercekten_vardir() -> None:
    """Bayat kural kalmasın: yeniden adlandırılan uç listede sessizce ölü kalmaz."""
    adlar = {ad for _, _, ad in _api_uclari()}
    assert {k.uc for k in IZIN_LISTESI} <= adlar


def test_dolasma_butun_api_yuzeyini_goruyor() -> None:
    """Boş liste yanlış yeşil verirdi; kip uçları ve sağlık yolu listede olmalı."""
    uclar = _api_uclari()
    adlar = {ad for _, _, ad in uclar}
    assert len(uclar) >= 30
    assert {"security-mode", "security-mode-staff", "security-mode-admin"} <= adlar
    assert HEALTH_PATH in {ornek for _, ornek, _ in uclar}


def test_gorevli_kipinde_izin_listesi_disindaki_her_uc_her_yontemde_403(
    gorevli: None,
) -> None:
    client = Client()
    kesilmeyen: list[str] = []
    denenen = 0
    for rota, ornek, ad in _api_uclari():
        for yontem in YONTEMLER:
            # Muafiyet yalnız okuma yöntemlerindedir; hiç kesilmeyen yollara POST/PUT…
            # da bu dolaşmaya girer (ileride eklenecek yazma yöntemi açık kalmasın).
            if ornek in HIC_KESILMEYEN_YOLLAR and yontem in HIC_KESILMEYEN_YONTEMLER:
                continue
            if _izinli_cift(ad, yontem):
                continue
            denenen += 1
            resp = client.generic(yontem, ornek)
            if not _kip_yetkisiz_mi(resp, yontem):
                kesilmeyen.append(f"{yontem} {ornek} ({rota}, {ad}) → {resp.status_code}")
    assert denenen > 100
    assert kesilmeyen == []


def test_gorevli_kipinde_izin_listesindekiler_kesilmez(gorevli: None) -> None:
    uclar = {ad: ornek for _, ornek, ad in _api_uclari()}
    for kural in IZIN_LISTESI:
        resp = _yalniz_kip_kapisi(kural.yontem, uclar[kural.uc])
        assert resp.content == b"gecti", f"{kural.yontem} {kural.uc} kesildi"


def test_hic_kesilmeyen_yollar_gorevli_kipinde_yalniz_okumada_muaftir(gorevli: None) -> None:
    """Denetim bulgusu: muafiyet eskiden HER yöntemdeydi. Bugün bu görünümler yalnız GET
    sunar, ama ileride eklenecek bir yazma yöntemi görevli kipinde parolasız açık kalırdı.
    Okuma dışı yöntemler olağan izin listesinden geçer; listede olmadıkları için 403."""
    assert frozenset({"GET", "HEAD"}) == HIC_KESILMEYEN_YONTEMLER
    for yol in HIC_KESILMEYEN_YOLLAR:
        for yontem in YONTEMLER:
            resp = _yalniz_kip_kapisi(yontem, yol)
            if yontem in HIC_KESILMEYEN_YONTEMLER:
                assert resp.content == b"gecti", f"{yontem} {yol} kesildi"
            else:
                # Yalnız kapı koştuğu için yanıt ham JsonResponse'tur (`.json()` yok).
                assert resp.status_code == 403, f"{yontem} {yol} kesilmedi"
                assert json.loads(resp.content)["code"] == "kip_yetkisiz"


def test_api_uc_adlari_tekildir() -> None:
    """Denetim bulgusu: izin listesi URL ADIYLA eşleşir ve dolaşan test ada göre atlar.
    `apps.okul.urls` ile `apps.kutuphane.urls` aynı düz ad uzayındadır; izin listesindeki
    bir adı taşıyan ikinci bir desen (kopyala-yapıştır) görevli kipinde sessizce açılır,
    dolaşan test de yeşil kalırdı. §5.10-8 kanıtı bu tekliğe dayanır."""
    sayac = Counter(ad for _, _, ad in _api_uclari())
    ciftler = sorted(ad for ad, adet in sayac.items() if adet > 1)
    assert ciftler == []
    # İzin listesindeki her ad tam olarak BİR desene çözülür.
    assert all(sayac[kural.uc] == 1 for kural in IZIN_LISTESI)


def test_hic_kesilmeyenler_saglik_yolunu_ve_durum_uclarini_icerir() -> None:
    assert HEALTH_PATH == SAGLIK_YOLU
    assert {
        HEALTH_PATH,
        "/api/v1/security/status/",
        "/api/v1/security/mode/",
    } == HIC_KESILMEYEN_YOLLAR


def test_gorevli_kipinde_cozulemeyen_api_yolu_403(gorevli: None) -> None:
    resp = Client().get("/api/v1/boyle-bir-uc-yok/")

    assert resp.status_code == 403
    assert resp.json()["code"] == "kip_yetkisiz"


def test_red_govdesi_sabittir_ve_ucu_yankilamaz(gorevli: None) -> None:
    resp = Client().get("/api/v1/students/")

    assert resp.json() == {
        "code": "kip_yetkisiz",
        "message": "Bu işlem görevli kipinde yapılamaz. Yönetici kipine geçin.",
        "fields": {},
    }


def test_gorevli_kipinde_api_disi_yollar_kesilmez(gorevli: None) -> None:
    """SPA ve statik dosyalar kip kapısının konusu değildir (ekranı ön yüz seçer)."""
    resp = _yalniz_kip_kapisi("GET", "/kisiler")
    assert resp.content == b"gecti"


def test_yonetici_kipinde_hicbir_uc_kip_kapisinda_kesilmez() -> None:
    for _, ornek, _ in _api_uclari():
        for yontem in YONTEMLER:
            resp = _yalniz_kip_kapisi(yontem, ornek)
            assert resp.content == b"gecti", f"{yontem} {ornek} yönetici kipinde kesildi"


# ------------------------------------------------------------ sağlık yolu, her durumda


@pytest.mark.parametrize("ortam", ["yonetici", "gorevli", "kilitli", "parolasiz", "kayip"])
def test_saglik_yolu_hicbir_durumda_kip_kapisinda_kesilmez(
    ortam: str, request: pytest.FixtureRequest
) -> None:
    if ortam == "gorevli":
        KIP.gorevliye_gec()
    elif ortam == "kayip":
        request.getfixturevalue("parmak_izi_yazili")
        app_password.state_path().unlink()
        assert KIP.durum() == "guvenlik_dosyasi_kayip"
    elif ortam in ("kilitli", "parolasiz"):
        request.getfixturevalue(ortam)

    for yontem in HIC_KESILMEYEN_YONTEMLER:
        assert _yalniz_kip_kapisi(yontem, HEALTH_PATH).content == b"gecti"
    # Tam zincirde de (kilit kapısı dahil) açılış sağlık denetimi yanıt alır.
    resp = Client().get(HEALTH_PATH)
    assert resp.status_code == 200, resp.content


# ------------------------------------------------------------ kayıp kilidiyle kesişim


def test_kayip_kilidinin_cikis_yollari_gorevli_kipinde_de_acik(parmak_izi_yazili: str) -> None:
    """Güvenlik dosyası kayıp kilidi (GA-2) ile kip kapısının kesişimi.

    Anahtar bellekteyken `guvenlik.json` kaybolur ve kip görevliye inmiştir (ör.
    kullanıcı kayıp ekranında 3 dk'dan uzun kaldı). Bu durumda kip geçişi
    yapılamaz (409) ve Kilitle de kapalıdır (423); kip kapısı yedek listesini ve
    geri yüklemeyi de keserse kayıp kilidinin program içindeki tek çıkış yolu
    kapanırdı. Kayıp durumunda neyin açık olduğuna kilit kapısı karar verir.
    """
    KIP.gorevliye_gec()
    app_password.state_path().unlink()
    assert KIP.durum() == "guvenlik_dosyasi_kayip"
    client = Client()

    assert client.get("/api/v1/backups/").status_code == 200
    geri_yukleme = client.post("/api/v1/backups/restore/", {}, content_type="application/json")
    # Gövde eksik: görünüm doğrulamayla reddeder — kapılardan geçtiğinin kanıtı.
    assert geri_yukleme.status_code == 400, geri_yukleme.content
    # Kilit kapısının kayıp listesi dışı her şey yine 423'tür (403 değil).
    veri = client.get(VERI_UCU)
    assert veri.status_code == 423
    assert veri.json()["code"] == "guvenlik_dosyasi_kayip"
    assert client.post(MOD + "staff/").status_code == 423


# ------------------------------------------------------------ yapı


def test_kip_kapisi_kilit_kapisindan_sonra_durur() -> None:
    zincir = list(settings.MIDDLEWARE)
    kip = zincir.index("apps.okul.kip_middleware.KipMiddleware")
    assert kip > zincir.index("apps.okul.lock_middleware.AppLockMiddleware")
    assert kip > zincir.index("apps.okul.restart_gate.RestartRequiredMiddleware")


def test_kilitliyken_kilit_kapisi_once_keser(kilitli: None) -> None:
    """Kilitliyken istek kip kapısına hiç gelmez: 423, 403 değil."""
    resp = Client().get("/api/v1/students/")
    assert resp.status_code == 423


def test_parametre_denetcisi_yanlis_derse_istek_kesilir() -> None:
    """F6'nın `override_reason` kuralı bu mekanizmayla yazılacak."""
    istek = RequestFactory().post("/api/v1/x/", {"override_reason": "gerekçe"})
    kurallar = (
        IzinKurali("odunc", "POST", parametre=lambda r: "override_reason" not in r.POST),
        IzinKurali("iade", "POST"),
    )

    assert izinli_mi("odunc", "POST", istek, kurallar=kurallar) is False
    assert izinli_mi("odunc", "POST", RequestFactory().post("/"), kurallar=kurallar) is True
    assert izinli_mi("iade", "post", istek, kurallar=kurallar) is True
    assert izinli_mi("iade", "GET", istek, kurallar=kurallar) is False
    assert izinli_mi(None, "POST", istek, kurallar=kurallar) is False


def test_ad_alanli_uc_adi_cozulur() -> None:
    assert kip_middleware.uc_adi("/api/v1/security/mode/") == "security-mode"
    assert kip_middleware.uc_adi("/api/v1/boyle-bir-uc-yok/") is None


# ============================================================ §5.10-14 boşta dönüş


@pytest.fixture
def saat() -> SahteSaat:
    """§5.10-14 testleri kurulumu TAMAMLANMIŞ ortamda koşar.

    Kurulum bitene kadar süreler kipi düşürmez (F1 eki, karar 2-1); o davranış
    `test_kurulum_surerken_basliksiz_istekler_yonetici_kipini_dusurmez`'dedir.
    """
    kurulum_durumunu_yaz(tamam=True)
    saat = SahteSaat()
    KIP._reset_for_tests(saat=saat)
    return saat


def _kip(client: Client) -> str:
    durum: str = client.get(MOD).json()["durum"]
    return durum


def test_basliksiz_periyodik_istekler_yonetici_kipini_canli_tutmaz(saat: SahteSaat) -> None:
    client = Client()
    assert _kip(client) == "yonetici"
    for _ in range(6):  # 30 sn'de bir durum ve pano sorguları, 3 dk boyunca
        saat.ilerlet(30)
        client.get(MOD)
        client.get(HEALTH_PATH)
        client.get("/api/v1/security/status/")
        client.get(VERI_UCU)

    assert _kip(client) == "gorevli"
    resp = client.get(VERI_UCU)
    assert resp.status_code == 403
    assert resp.json()["code"] == "kip_yetkisiz"


def test_basliksiz_ama_yonetici_kipinde_veri_ucu_calisir(saat: SahteSaat) -> None:
    client = Client()
    saat.ilerlet(60)
    assert client.get(VERI_UCU).status_code == 200


def test_etkinlik_basligi_yonetici_kipini_canli_tutar(saat: SahteSaat) -> None:
    client = Client()
    assert _kip(client) == "yonetici"
    for _ in range(10):  # 10 dk boyunca dakikada bir kullanıcı eylemi
        saat.ilerlet(60)
        assert client.get(VERI_UCU, headers=ETKINLIK).status_code == 200

    assert _kip(client) == "yonetici"


def test_bosta_sure_dolduktan_sonra_gelen_etkinlik_dirilmez(saat: SahteSaat) -> None:
    client = Client()
    assert _kip(client) == "yonetici"
    saat.ilerlet(3 * 60 + 1)

    resp = client.get(VERI_UCU, headers=ETKINLIK)

    assert resp.status_code == 403
    assert _kip(client) == "gorevli"


def test_mutlak_sure_dolunca_gorevliye_iner_ve_parola_istenir(
    saat: SahteSaat, monkeypatch: pytest.MonkeyPatch
) -> None:
    cagrilar: list[str] = []
    monkeypatch.setattr(app_password, "verify_password", sahte_dogrulayici(cagrilar))
    client = Client()
    assert _kip(client) == "yonetici"
    for _ in range(29):
        saat.ilerlet(60)
        assert client.get(VERI_UCU, headers=ETKINLIK).status_code == 200
    saat.ilerlet(60)

    assert client.get(VERI_UCU, headers=ETKINLIK).status_code == 403
    assert _kip(client) == "gorevli"
    # Parolasız yükseltme yok; parola sorulur.
    assert client.post(MOD + "admin/", {}, content_type="application/json").status_code == 400
    assert _kip(client) == "gorevli"
    resp = client.post(
        MOD + "admin/",
        {"password": DOGRU_PAROLA},
        content_type="application/json",
        headers=ETKINLIK,
    )
    assert resp.status_code == 200
    assert _kip(client) == "yonetici"
    assert client.get(VERI_UCU).status_code == 200


def test_kurulum_surerken_basliksiz_istekler_yonetici_kipini_dusurmez(saat: SahteSaat) -> None:
    """Sihirbazda kurtarma anahtarı ekrandayken süre dolup görevliye inilmez (karar 2-1).

    Kurulum tamamlanınca (`setup/complete/`) aynı §5.10-14 kuralı işlemeye başlar.
    """
    kurulum_durumunu_yaz(tamam=False)
    client = Client()
    assert _kip(client) == "yonetici"
    for _ in range(40):  # 40 dk boyunca yalnız başlıksız durum ve pano sorguları
        saat.ilerlet(60)
        client.get(MOD)
        client.get(HEALTH_PATH)
        assert client.get(VERI_UCU).status_code == 200
    assert _kip(client) == "yonetici"
    assert client.get(MOD).json()["bosta_kalan_sn"] is None  # geri sayım gösterilmez

    kurulum_durumunu_yaz(tamam=True)
    saat.ilerlet(3 * 60)
    assert client.get(VERI_UCU).status_code == 403
    assert _kip(client) == "gorevli"


def test_kisa_sureli_ayarla_da_ayni_kural(saat: SahteSaat) -> None:
    """Süre sağlayıcısı değişirse (F6 ayarı) kapı yeni süreyle karar verir."""
    KIP._reset_for_tests(saat=saat, sureler=lambda: KipSureleri(bosta_sn=60, mutlak_sn=120))
    client = Client()
    assert _kip(client) == "yonetici"
    saat.ilerlet(61)
    assert client.get(VERI_UCU).status_code == 403
