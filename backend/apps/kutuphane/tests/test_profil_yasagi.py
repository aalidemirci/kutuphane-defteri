"""Profil yasağı — F10 kod kapısı (CLAUDE.md §2-5, tasarım §3 KVKK "Profil yasağı").

Ödünç verisi KVKK md. 6'ya kaymasın diye her madde ayrı sınanır:

1. **Üye bazında konu ya da sınıf dağılımı üretilmez** — kaynak taraması: hiçbir
   gruplama (`values`/`values_list`) kişi ekseniyle (üyelik, öğrenci, personel)
   konu eksenini (konu, sınıflama, DOS, yer no, kaynak türü, bölüm, dil) aynı ifadede
   birleştirmez (`TestKaynakTaramasi`); tarayıcının kendisi de sınanır.
2. **Şube × konu kırılımı k eşiksiz yapılmaz** — programda şube × konu kırılımı HİÇ
   yoktur: aynı tarama şube/sınıf düzeyi eksenini de kapsar. Eklenecek olursa bu test
   düşer ve k eşiğiyle bilinçli yazılmak zorunda kalır.
3. **Not ya da başarı verisi alanı eklenmez** — bütün modellerin alan adları ve
   görünen adları taranır (`test_not_ya_da_basari_alani_yok`).
4. **Adlı sıralama ağa, panoya, yıl sonu raporuna (E9) ve Ayın Kitapları afişine
   (E12) girmez** — okuma ödülü modüllerini yalnız E20 ucu içe aktarır; ağ, pano,
   E9, E12, istatistik ve çok okunanlar modülleri kişi adı alanına dokunmaz; davranış
   testi sentetik adlı öğrencilerle bütün bu çıktıları tarar (adların E20'de GÖRÜNDÜĞÜ
   de sınanır — boş kurgu yanlış yeşil verirdi). Ağ Kataloğu vitrininin taraması
   `katalog/tests/test_vitrin_cok_okunanlar.py`'dedir.
5. **Okuma ödülü iç çıktısı yalnız yönetici kipinde, "iç kullanım" ibaresiyle** —
   `test_okuma_odulu.py` (seçici + uç + belge metni).

"Ödünç ≠ okuduğu kitap": sözlüğün yasakladığı ifadeler ("okuduğu kitaplar", "okuma
karnesi", "okuma puanı") F10 modüllerinde ve şablonlarında geçmez.
"""

from __future__ import annotations

import ast
import io
import json
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.utils import timezone
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.kutuphane import (
    ayin_kitaplari_belgesi,
    okuma_odulu_belgesi,
    selectors_istatistik,
    selectors_yil_raporu,
)
from apps.kutuphane.models import Copy, Loan
from apps.kutuphane.services import circulation, populer
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.teslim_ortak import etkin_yil

BACKEND = Path(__file__).resolve().parents[3]

#: Kişi ekseni (üye bazında gruplama) ve şube/sınıf düzeyi ekseni.
KISI_EKSENI = ("membership", "student", "personnel")
SUBE_EKSENI = ("class_section", "class_level")
#: Konu ekseni: konu, sınıflama, DOS, yer no, kaynak türü, eserin/nüshanın bölümü, dil.
KONU_EKSENI = (
    "subject",
    "classification",
    "dewey",
    "call_number",
    "resource_type",
    "work__section",
    "copy__section",
    "language",
)
GRUPLAMA = frozenset({"values", "values_list"})


# ============================================================ 1-2: kaynak taraması


def _kaynak_dosyalari() -> Iterator[Path]:
    for kok in (BACKEND / "apps", BACKEND / "katalog"):
        for yol in sorted(kok.rglob("*.py")):
            parcalar = set(yol.relative_to(BACKEND).parts)
            if "tests" in parcalar or "migrations" in parcalar:
                continue
            yield yol


def _ifade_kokleri(agac: ast.AST) -> Iterator[ast.expr]:
    """Deyimlerin en dıştaki ifadeleri (bir sorgu zinciri tek ifade olarak incelenir)."""
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Expr | ast.Return | ast.Assign | ast.AnnAssign):
            deger = dugum.value
            if deger is not None:
                yield deger
        elif isinstance(dugum, ast.comprehension):
            yield dugum.iter


def _metinler(dugum: ast.AST) -> list[str]:
    """İfadedeki bütün dize sabitleri ve anahtar sözcüklü argüman adları."""
    sonuc: list[str] = []
    for alt in ast.walk(dugum):
        if isinstance(alt, ast.Constant) and isinstance(alt.value, str):
            sonuc.append(alt.value)
        elif isinstance(alt, ast.keyword) and alt.arg:
            sonuc.append(alt.arg)
    return sonuc


def _gruplama_argumanlari(dugum: ast.AST) -> list[str]:
    sonuc: list[str] = []
    for alt in ast.walk(dugum):
        if (
            isinstance(alt, ast.Call)
            and isinstance(alt.func, ast.Attribute)
            and alt.func.attr in GRUPLAMA
        ):
            sonuc += [
                a.value
                for a in alt.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
            ]
    return sonuc


def profil_ihlalleri(kaynak: str) -> list[str]:
    """Kişi ya da şube ekseninde gruplayıp konu eksenine de dokunan sorgu ifadeleri."""
    ihlaller: list[str] = []
    for ifade in _ifade_kokleri(ast.parse(kaynak)):
        gruplama = _gruplama_argumanlari(ifade)
        if not any(e in g for g in gruplama for e in (*KISI_EKSENI, *SUBE_EKSENI)):
            continue
        konu = [m for m in _metinler(ifade) if any(k in m for k in KONU_EKSENI)]
        if konu:
            ihlaller.append(f"satır {ifade.lineno}: {gruplama} × {konu}")
    return ihlaller


class TestKaynakTaramasi:
    def test_hicbir_sorgu_uye_ya_da_sube_bazinda_konu_dagilimi_uretmez(self) -> None:
        bulgular = {
            str(yol.relative_to(BACKEND)): ihlal
            for yol in _kaynak_dosyalari()
            if (ihlal := profil_ihlalleri(yol.read_text(encoding="utf-8")))
        }
        assert bulgular == {}
        assert len(list(_kaynak_dosyalari())) > 100  # tarama gerçekten dolaştı

    @pytest.mark.parametrize(
        "kaynak",
        [
            # üye bazında konu dağılımı
            'Loan.objects.values("membership_id", "copy__work__subjects").annotate(n=Count("pk"))',
            # üye bazında sınıflama (DOS) dağılımı — konu ekseni sayımda
            'Loan.objects.values("membership__student_id").annotate(n=Count("copy__work__classification_code"))',
            # belli bir konuyu alan üyeler
            'x = Loan.objects.filter(copy__work__subjects__icontains="din").values_list("membership_id")',
            # şube × konu
            'rows = [r for r in Loan.objects.values("membership__student__class_section", "copy__work__section__name")]',
            # sınıf düzeyi × kaynak türü
            'return Loan.objects.values("membership__student__class_level", "copy__work__resource_type")',
        ],
    )
    def test_tarayici_ihlali_yakalar(self, kaynak: str) -> None:
        assert profil_ihlalleri(kaynak) != []

    @pytest.mark.parametrize(
        "kaynak",
        [
            # E9 / istatistik: sınıf düzeyi kırılımı (konusuz)
            'Loan.objects.values("membership__student__class_level").annotate(n=Count("pk"))',
            # koleksiyon: bölüme göre nüsha (kişisiz)
            'Copy.objects.values_list("section__name", "work__section__name")',
            # çok okunanlar: eser bazında farklı üye
            'Loan.objects.values("copy__work_id").annotate(f=Count("membership_id", distinct=True))',
        ],
    )
    def test_tarayici_izinli_sorguya_takilmaz(self, kaynak: str) -> None:
        assert profil_ihlalleri(kaynak) == []


# ============================================================ 3: not / başarı alanı yok


#: Alan adının ALT ÇİZGİYLE ayrılmış parçaları arasında bulunmaması gerekenler.
NOT_PARCALARI = frozenset(
    {
        "grade",
        "grades",
        "gpa",
        "score",
        "scores",
        "mark",
        "marks",
        "achievement",
        "success",
        "performance",
        "basari",
        "puan",
        "karne",
        "ortalama",
        "exam",
        "sinav",
    }
)
#: Görünen addaki (verbose_name) yasak ifadeler.
NOT_IFADELERI = ("başarı", "karne", "puan", "not ortalaması", "ders notu", "sınav notu")


def test_not_ya_da_basari_alani_yok() -> None:
    bulgular: list[str] = []
    alan_sayisi = 0
    for model in [
        *django_apps.get_app_config("okul").get_models(),
        *django_apps.get_app_config("kutuphane").get_models(),
    ]:
        for alan in model._meta.get_fields():
            alan_sayisi += 1
            parcalar = set(alan.name.lower().split("_"))
            gorunen = str(getattr(alan, "verbose_name", "")).casefold()
            if parcalar & NOT_PARCALARI or any(i in gorunen for i in NOT_IFADELERI):
                bulgular.append(f"{model.__name__}.{alan.name}")
    assert bulgular == []
    assert alan_sayisi > 200


# ============================================================ 4: adlı sıralama nerelere girmez


def _modul_yolu(ad: str) -> Path:
    return BACKEND / (ad.replace(".", "/") + ".py")


def _iceri_aktaranlar(hedef: str) -> set[str]:
    """`hedef` modülünü (ya da adını) içe aktaran kaynak modüller."""
    son = hedef.rsplit(".", 1)[-1]
    sonuc: set[str] = set()
    for yol in _kaynak_dosyalari():
        for dugum in ast.walk(ast.parse(yol.read_text(encoding="utf-8"))):
            adlar: list[str] = []
            if isinstance(dugum, ast.Import):
                adlar = [a.name for a in dugum.names]
            elif isinstance(dugum, ast.ImportFrom) and dugum.module:
                adlar = [dugum.module] + [f"{dugum.module}.{a.name}" for a in dugum.names]
            if any(a == hedef or a.endswith(f".{son}") and a.startswith("apps.") for a in adlar):
                sonuc.add(".".join(yol.relative_to(BACKEND).with_suffix("").parts))
    return sonuc


def test_okuma_odulu_modullerini_yalniz_e20_yolu_ice_aktarir() -> None:
    assert _iceri_aktaranlar("apps.kutuphane.selectors_okuma_odulu") == {
        "apps.kutuphane.okuma_odulu_belgesi",
        "apps.kutuphane.views_istatistik",  # yalnız sıra sınırı sabiti
    }
    assert _iceri_aktaranlar("apps.kutuphane.okuma_odulu_belgesi") == {
        "apps.kutuphane.views_istatistik"
    }


#: Ağa, panoya, E9'a, E12'ye ve kişisiz istatistiğe giden modüller ve şablonlar.
KISISIZ_YUZEYLER = (
    "apps/kutuphane/pano.py",
    "apps/kutuphane/selectors_populer.py",
    "apps/kutuphane/services/populer.py",
    "apps/kutuphane/ayin_kitaplari_belgesi.py",
    "apps/kutuphane/selectors_istatistik.py",
    "apps/kutuphane/selectors_yil_raporu.py",
    "apps/kutuphane/yil_raporu_belgesi.py",
    "apps/kutuphane/ag_katalogu.py",
    "templates/documents/ayin_kitaplari.html",
    "templates/documents/yil_sonu_raporu.html",
)
KISI_ALANLARI = (
    "full_name",
    "first_name",
    "last_name",
    "student_number",
    "card_no",
    "person_name",
    "okuma_odulu",
)


def _kisisiz_yuzey_dosyalari() -> list[Path]:
    dosyalar = [BACKEND / y for y in KISISIZ_YUZEYLER]
    dosyalar += sorted((BACKEND / "katalog").glob("*.py"))
    dosyalar += sorted((BACKEND / "katalog" / "sablonlar").glob("*.html"))
    return dosyalar


def test_ag_pano_e9_e12_ve_istatistik_kisi_adina_dokunmaz() -> None:
    bulgular = {
        f"{yol.relative_to(BACKEND)}: {alan}"
        for yol in _kisisiz_yuzey_dosyalari()
        for alan in KISI_ALANLARI
        if alan in yol.read_text(encoding="utf-8")
    }
    assert bulgular == set()
    assert all(y.is_file() for y in _kisisiz_yuzey_dosyalari())


def test_pano_gorunumleri_kisi_adina_dokunmaz() -> None:
    import inspect

    from apps.kutuphane import views_evrak, views_istatistik

    for sinif in (views_evrak.DashboardCirculationView, views_istatistik.DashboardStatisticsView):
        kod = inspect.getsource(sinif)
        for alan in (*KISI_ALANLARI, "selectors_okuma_odulu"):
            assert alan not in kod, f"{sinif.__name__}: {alan}"


SOZLUK_YASAKLARI = ("okuduğu kitap", "okuma karnesi", "okuma puanı", "okuma geçmişi")


def test_f10_metinlerinde_sozlugun_yasakladigi_ifadeler_yok() -> None:
    dosyalar = [
        "apps/kutuphane/ayin_kitaplari_belgesi.py",
        "apps/kutuphane/okuma_odulu_belgesi.py",
        "apps/kutuphane/views_istatistik.py",
        "templates/documents/ayin_kitaplari.html",
        "templates/documents/okuma_odulu.html",
    ]
    for ad in dosyalar:
        metin = " ".join((BACKEND / ad).read_text(encoding="utf-8").casefold().split())
        for ifade in SOZLUK_YASAKLARI:
            assert ifade not in metin, f"{ad}: {ifade}"


# ============================================================ 4: davranış — sentetik adlar


ADLAR = ("Profilsentetikad", "Profilsentetiksoyad", "852741")


def _metin(icerik: bytes) -> str:
    return "\n".join(s.extract_text() or "" for s in PdfReader(io.BytesIO(icerik)).pages)


def _bol_odunclu_yil() -> tuple[list[str], date, date]:
    """Sentetik adlı öğrencinin çok ödüncü + eşiği geçen bir eser; izler ve dönem."""
    etkin_yil()
    yildiz = uye(
        ogrenci(first_name=ADLAR[0], last_name=ADLAR[1], student_number=ADLAR[2], class_level=9)
    )
    for i in range(4):
        copy = odunc_nushasi(title=f"Yıldızın Aldığı {i}")
        odunc_ver(yildiz, copy)
        circulation.return_copy(copy=copy)
    ortak: Copy = odunc_nushasi(title="Ortak Okunan")
    for uyelik in [yildiz, *(uye(ogrenci()) for _ in range(4))]:
        odunc_ver(uyelik, ortak)
        circulation.return_copy(copy=ortak)
    bugun = timezone.localdate()
    populer.hesapla(bugun)
    return [*ADLAR, yildiz.card_no], bugun - timedelta(days=30), bugun


@pytest.mark.django_db
def test_adli_siralama_yalniz_e20de_ag_disi_ciktilarda_yok() -> None:
    izler, bas, son = _bol_odunclu_yil()
    istemci = APIClient()

    # E20 adları GÖSTERİR (iç kullanım) — kurgu gerçekten adlı sıralama üretiyor.
    e20 = _metin(okuma_odulu_belgesi.ic_cikti_pdf(bas, son))
    assert f"{ADLAR[0]} {ADLAR[1]}" in e20

    ciktilar = {
        "pano (Md. 7 + çok okunanlar)": istemci.get(
            "/api/v1/library/dashboard/statistics/"
        ).content,
        "pano (dolaşım)": istemci.get("/api/v1/library/dashboard/circulation/").content,
        "çok okunanlar": istemci.get("/api/v1/library/popular/").content,
        "istatistik": istemci.get(
            "/api/v1/library/statistics/", {"start": bas.isoformat(), "end": son.isoformat()}
        ).content,
    }
    metinler = {ad: icerik.decode("utf-8") for ad, icerik in ciktilar.items()}
    metinler["E12 afişi"] = _metin(ayin_kitaplari_belgesi.afis_pdf(f"{son:%Y-%m}"))
    metinler["E9 sayıları"] = json.dumps(
        selectors_yil_raporu.annual_review_stats(etkin_yil()), ensure_ascii=False, default=str
    )
    metinler["istatistik seçicisi"] = json.dumps(
        selectors_istatistik.istatistik(bas, son), ensure_ascii=False, default=str
    )

    assert "Ortak Okunan" in metinler["E12 afişi"]  # afiş gerçekten basıldı
    for ad, metin in metinler.items():
        for iz in izler:
            assert iz.casefold() not in metin.casefold(), f"{iz} → {ad}"
        assert "Yıldızın Aldığı" not in metin, f"üyenin eserleri → {ad}"
    assert Loan.objects.count() == 9
