"""Ekran görüntüleri için programı UYDURMA veriyle ayağa kaldırır (backend kabında koşar).

`ekran_goruntuleri.sh` bu betiği backend kabında başlatır; görüntüleri AYNI kabın ağ
ad alanına bağlanan geçici bir Playwright kabı alır (`ekran_cekimi.py`). Program
gerçek masaüstü yolundan kalkar (`scripts/ag_katalogu_provasi.py`'nin `sun` adımı
gibi): açılışa özel oturum belirteci, `prepare_django` + göç, yönetim sunucusu
127.0.0.1'de rastgele portta (`BackgroundServer`, belirteç koruması ve sağlık
denetimiyle), Ağ Kataloğu `KatalogKontrol` ile 8765'te. **Hiçbir güvenlik kuralı
gevşetilmez:** tarayıcı pencerenin açılış adresini (belirteçli) açar, belirteç
`HttpOnly` çereze geçer — masaüstü penceresinin yaptığının aynısı.

Veri (hepsi UYDURMADIR — CLAUDE.md §2-12):

* Kurulum sihirbazının üç adımı servislerle: yönetici parolası + kurtarma anahtarı
  doğrulaması, okul bilgileri ("Örnek Anadolu Lisesi", "Örnek İlçe"), 2026-2027 ders
  yılı, iki dönem, resmî/dini tatiller ve öğrenciye kapalı günler.
* `scripts/deneme_verisi.py`'nin e-Okul öğrenci ve personel listeleri ile ~2.000
  eserlik katalog Excel'i, programın GERÇEK içe aktarıcılarından
  (`test_deneme_verisi.py` ile aynı yol; F12 BT-3 provası).
* Eylül'ün okul günleri boyunca üyelik, ödünç ve iade (saat `timezone.now` ile o güne
  sabitlenerek; servisler tarihi kendileri yazar), bir kısmı gecikmiş açık ödünç,
  sınıf kitaplığına ve bir öğretmene teslim, çok okunanlar hesabı (en az k farklı üye),
  sayım taslağı, Ağ Kataloğu "Aç".

Kip süreleri: masadaki yöneticinin etkinliği (`KIP.etkinlik`) sunum boyunca iki saniyede
bir tazelenir; Playwright tarafı gerekirse yönetici kipine parolayla geçer. Görüntülerin
üst çubuğundaki "Yönetici kipi 3:00" geri sayımı bu yüzden tam süreye yakın görünür;
programın gerçek davranışıdır (§4.4 boşta süresi).

Durum dosyası (`<çıktı>/durum.json`) belirteçli açılış adresini ve sahne verisini
taşır; dosya depo dışı çalışma klasöründedir (`dist/`, `.gitignore`) ve sunum
bitince silinir. Belirteç yalnız bu geçici kabın ömrü kadar geçerlidir.

Kullanım (depo kökünden, `ekran_goruntuleri.sh` çağırır):

    docker compose run -d --name kd-ekran -e KD_DEBUG=0 -w /repo backend \
        python scripts/ekran_goruntuleri/ekran_sunucusu.py --cikti dist/ekran-goruntuleri
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import secrets
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock
from zoneinfo import ZoneInfo

DEPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEPO))

#: Geçici veri dizininin UYDURMA yönetici parolası (kap silinince her şeyle gider).
PAROLA = "Ekran-Goruntusu-2026"  # noqa: S105
KATALOG_PORT = 8765
ISTANBUL = ZoneInfo("Europe/Istanbul")
TOHUM = 2026

#: Sahnenin takvimi. Ders yılı 07.09.2026 pazartesi başlar; görüntü günü 30.09.2026.
YIL_BASI = date(2026, 9, 7)
BIRINCI_DONEM_SONU = date(2027, 1, 22)
IKINCI_DONEM_BASI = date(2027, 2, 8)
YIL_SONU = date(2027, 6, 25)
KURULUM_GUNU = date(2026, 9, 2)
UYELIK_GUNU = date(2026, 9, 4)
GORUNTU_GUNU = date(2026, 9, 30)

#: Öğrenciye kapalı günler (uydurma; okulun kendi takvimi girilir).
ARA_TATILLER: tuple[tuple[str, date, date], ...] = (
    ("1. dönem ara tatili", date(2026, 11, 9), date(2026, 11, 13)),
    ("Yarıyıl tatili", date(2027, 1, 25), date(2027, 2, 5)),
    ("2. dönem ara tatili", date(2027, 3, 29), date(2027, 4, 2)),
)


def _yaz(satir: str) -> None:
    print(satir, flush=True)


@contextmanager
def saat(gun: date, saat_: int = 10, dakika: int = 0) -> Iterator[None]:
    """`django.utils.timezone.now`'ı o günün o saatine sabitler (yalnız tohumlama için).

    Servisler tarihi `timezone.localdate()` / `timezone.now()` ile kendileri yazar;
    ikisi de aynı modül işlevine dayanır. Sunum başlamadan saat serbest bırakılır.
    """
    an = datetime(gun.year, gun.month, gun.day, saat_, dakika, tzinfo=ISTANBUL).astimezone(UTC)
    with mock.patch("django.utils.timezone.now", return_value=an):
        yield


def okul_gunleri(bas: date, son: date) -> list[date]:
    """[bas, son] aralığının hafta içi günleri (Eylül'de resmî tatil yoktur)."""
    gunler: list[date] = []
    gun = bas
    while gun <= son:
        if gun.weekday() < 5:
            gunler.append(gun)
        gun += timedelta(days=1)
    return gunler


def _uretici() -> ModuleType:
    """`scripts/deneme_verisi.py`'yi dosya yolundan yükler (test_deneme_verisi.py gibi)."""
    yol = DEPO / "scripts" / "deneme_verisi.py"
    spec = importlib.util.spec_from_file_location("kd_deneme_verisi", yol)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul  # dataclass'lar modülü sys.modules'tan çözer
    spec.loader.exec_module(modul)
    return modul


# --------------------------------------------------------------------------- kurulum


def kurulum() -> None:
    """Sihirbazın üç adımı (parola, okul bilgileri, ders yılı + kapalı günler)."""
    from apps.okul.models import HolidayKind, SchoolLevel
    from apps.okul.services import app_password, calendar, school_year, setup, terms

    with saat(KURULUM_GUNU, 9):
        kurtarma = app_password.enable(password=PAROLA)
        app_password.confirm_recovery_key(kurtarma)
        setup.update_school_config(
            fields={
                "school_name": "Örnek Anadolu Lisesi",
                "province": "Örnek İl",
                "district": "Örnek İlçe",
                "principal_name": "Deniz Korkmaz",
                "has_prep_class": False,
                "kademe": SchoolLevel.ORTAOGRETIM,
                "kisa_ad": "ÖAL",
                "demirbas_onayi": True,
                "demirbas_no": "255.01.02/0001",
            }
        )
        yil = school_year.create_school_year(
            name="2026-2027", start_date=YIL_BASI, end_date=YIL_SONU, activate=True
        )
        terms.configure_terms(yil, first_end=BIRINCI_DONEM_SONU, second_start=IKINCI_DONEM_BASI)
        calendar.seed_holidays(2026)
        calendar.seed_holidays(2027)
        for ad, bas, son in ARA_TATILLER:
            calendar.create_holiday(
                name=ad, start_date=bas, end_date=son, kind=HolidayKind.SCHOOL_BREAK
            )
        setup.mark_setup_completed()
    _yaz("KURULUM tamam")


def aktarimlar(kok: Path) -> Any:
    """e-Okul listeleri ve katalog: programın gerçek içe aktarıcılarından."""
    from apps.kutuphane.models import CatalogImportSource
    from apps.kutuphane.services import import_service as ia
    from apps.okul.services import imports

    uretici = _uretici()
    klasor = kok / "deneme-verisi"
    ozet = uretici.uret(klasor, tohum=TOHUM)
    with saat(KURULUM_GUNU, 11):
        ogr = imports.commit_students_file(
            file_bytes=(klasor / uretici.DOSYA_OGRENCI).read_bytes(),
            file_name=uretici.DOSYA_OGRENCI,
        )
        per = imports.commit_personnel_file(
            file_bytes=(klasor / uretici.DOSYA_PERSONEL).read_bytes(),
            file_name=uretici.DOSYA_PERSONEL,
        )
    with saat(KURULUM_GUNU + timedelta(days=1), 10):
        parsed, ozet_hash = ia.rows_from_file(
            (klasor / uretici.DOSYA_KATALOG).read_bytes(), source=CatalogImportSource.EXCEL
        )
        rapor = ia.apply_import(
            parsed,
            payload_sha256=ozet_hash,
            file_name=uretici.DOSYA_KATALOG,
            new_sections=ozet.bolumler,
        )
    _yaz(
        f"AKTARIM ogrenci={ogr.created_students} personel={per.created_personnel} "
        f"eser={rapor.stats['new_works']} nusha={rapor.stats['copies_created']}"
    )
    return ozet


# --------------------------------------------------------------------------- dolaşım


def uyelikler(rng: random.Random) -> list[Any]:
    """Öğrencilerin çoğuna (şube bazlı istek listesi) ve öğretmenlerin bir kısmına üyelik."""
    from apps.kutuphane.services import memberships
    from apps.okul.models import MemberKind, Personnel, Student, StudentStatus

    ogrenciler = sorted(
        Student.objects.filter(status=StudentStatus.ACTIVE).values_list("pk", flat=True)
    )
    secilen = [pk for pk in ogrenciler if rng.random() < 0.62]
    ogretmenler = sorted(
        Personnel.objects.filter(member_kind=MemberKind.TEACHER).values_list("pk", flat=True)
    )
    acilan: list[Any] = []
    with saat(UYELIK_GUNU, 10):
        for bas in range(0, len(secilen), 60):
            acilan += memberships.create_memberships_for_students(secilen[bas : bas + 60])
        for pk in ogretmenler:
            if rng.random() < 0.55:
                acilan.append(memberships.create_membership(personnel=Personnel.objects.get(pk=pk)))
    _yaz(f"UYELIK {len(acilan)}")
    return acilan


def raf(rng: random.Random) -> dict[str, Any]:
    """Ödünç verilebilir nüshalar, eser → nüsha eşlemesi ve çok okunacak eserler.

    Çok okunanlar için bir avuç eser çok nüshalı eserlerden seçilir; ödünçlerin bir
    kısmı bunlara yönelir (eşik: en az k FARKLI üye — profil yasağı, CLAUDE.md §2-5).
    """
    from apps.kutuphane.models import Copy
    from apps.kutuphane.selectors import LOANABLE_Q

    eser_nusha: dict[int, list[int]] = {}
    hepsi: list[int] = []
    for pk, work_id in Copy.objects.filter(LOANABLE_Q).order_by("pk").values_list("pk", "work_id"):
        hepsi.append(pk)
        eser_nusha.setdefault(work_id, []).append(pk)
    cok_nushali = [w for w, n in eser_nusha.items() if len(n) >= 3]
    rng.shuffle(cok_nushali)
    return {
        "hepsi": hepsi,
        "eser_nusha": eser_nusha,
        "populer": cok_nushali[:14],
        "rafta": set(hepsi),
    }


def dolasim(rng: random.Random, uyeler: list[Any], durum: dict[str, Any]) -> None:
    """Eylül'ün okul günleri: her gün önce planlı iadeler, sonra yeni ödünçler.

    İlk haftanın bazı ödünçleri iade edilmez: 30.09'da gecikmiş görünürler. Teslim
    edilmiş nüshalar (`teslimler`) raftan önceden düşülmüştür.
    """
    from rest_framework.exceptions import APIException

    from apps.kutuphane.models import Copy
    from apps.kutuphane.services import circulation

    eser_nusha: dict[int, list[int]] = durum["eser_nusha"]
    populer: list[int] = durum["populer"]
    rafta: set[int] = durum["rafta"]
    hepsi = sorted(rafta)
    acik: dict[int, tuple[Any, date | None]] = {}  # nüsha → (üyelik, planlı iade günü)
    uye_acik: dict[int, int] = {}
    sayac = {"odunc": 0, "iade": 0, "ret": 0}
    gunler = okul_gunleri(YIL_BASI, GORUNTU_GUNU)

    def _iade(nusha_pk: int) -> None:
        uyelik, _ = acik.pop(nusha_pk)
        circulation.return_copy(copy=Copy.objects.get(pk=nusha_pk))
        rafta.add(nusha_pk)
        uye_acik[uyelik.pk] -= 1
        sayac["iade"] += 1

    for sira, gun in enumerate(gunler):
        with saat(gun, 9, 5):
            for nusha_pk in [
                k for k, (_, plan) in acik.items() if plan is not None and plan <= gun
            ]:
                _iade(nusha_pk)
        adet = rng.randint(14, 24) if gun < GORUNTU_GUNU else 9
        for adim in range(adet):
            uyelik = rng.choice(uyeler)
            sinir = 3 if uyelik.student_id else 5
            if uye_acik.get(uyelik.pk, 0) >= sinir - 1:
                continue
            adaylar: list[int] = []
            if rng.random() < 0.5:
                adaylar = [n for w in populer for n in eser_nusha[w] if n in rafta]
            if not adaylar:
                adaylar = [rng.choice(hepsi) for _ in range(6)]
                adaylar = [n for n in adaylar if n in rafta]
            if not adaylar:
                continue
            nusha_pk = rng.choice(adaylar)
            with saat(gun, 10 + adim % 6, (adim * 7) % 60):
                try:
                    circulation.checkout(copy=Copy.objects.get(pk=nusha_pk), membership=uyelik)
                except APIException:
                    sayac["ret"] += 1
                    continue
            rafta.discard(nusha_pk)
            uye_acik[uyelik.pk] = uye_acik.get(uyelik.pk, 0) + 1
            sayac["odunc"] += 1
            if sira < 6 and rng.random() < 0.12:
                plan: date | None = None  # iade edilmez → 30.09'da gecikmiş
            else:
                ileri = sira + rng.randint(3, 11)
                plan = gunler[ileri] if ileri < len(gunler) else None
            acik[nusha_pk] = (uyelik, plan)
    durum["acik"] = acik
    _yaz(f"DOLASIM {json.dumps(sayac)} acik={len(acik)}")


def teslimler(rng: random.Random, durum: dict[str, Any]) -> None:
    """Sınıf kitaplığına (9/A) ve bir öğretmene toplu teslim (U11); dolaşımdan ÖNCE yazılır.

    Teslim edilen nüshalar raftan düşülür: dolaşım onları ödünç vermez.
    """
    from apps.kutuphane.models import Copy
    from apps.kutuphane.services import deliveries
    from apps.okul.models import ClassSection, MemberKind, Personnel

    rafta: set[int] = durum["rafta"]
    populer_nushalar = {n for w in durum["populer"] for n in durum["eser_nusha"][w]}
    aday = sorted(n for n in rafta if n not in populer_nushalar)
    rng.shuffle(aday)
    sube = ClassSection.objects.filter(class_level=9, class_section="A").first()
    ogretmen = Personnel.objects.filter(member_kind=MemberKind.TEACHER).order_by("pk")[3]
    with saat(date(2026, 9, 9), 13, 30):
        secilen = aday[:18]
        deliveries.deliver(barcodes=[Copy.objects.get(pk=n).barcode for n in secilen], section=sube)
        rafta.difference_update(secilen)
    with saat(date(2026, 9, 16), 14, 10):
        secilen = aday[18:24]
        deliveries.deliver(
            barcodes=[Copy.objects.get(pk=n).barcode for n in secilen], personnel=ogretmen
        )
        rafta.difference_update(secilen)
    _yaz("TESLIM tamam")


def sayim_taslagi() -> None:
    """Yıl sonu sayımının taslağı (kurul adları uydurma; şifreli alanlara yazılır)."""
    from apps.kutuphane.services import stocktake

    stocktake.create_stocktake(
        fiscal_year=2026,
        is_year_end=True,
        committee_chair="Deniz Korkmaz",
        committee_members="Ece Yıldız\nMert Aydın",
        committee_property_officer="Selin Kaya",
        notes="Aralık sonunda, yarıyıl öncesi yapılacak.",
    )
    _yaz("SAYIM taslak")


def yol_haritasi() -> None:
    """Başlangıç Yol Haritası: elle işaretlenen maddeler yapıldı, kart gizlendi.

    Programı birkaç haftadır kullanan kütüphanenin Genel Bakış'ı; kart yalnız bütün
    maddeler tamamlanınca gizlenebilir (`setup.set_roadmap_hidden`).
    """
    from apps.okul.services import setup

    with saat(date(2026, 9, 18), 15):
        for madde in setup.ROADMAP_MANUAL_ITEMS:
            setup.set_roadmap_mark(madde, done=True)
        setup.set_roadmap_hidden(hidden=True)


def cok_okunanlar() -> None:
    from apps.kutuphane.services import populer

    ozet = populer.hesapla(GORUNTU_GUNU)
    _yaz(f"POPULER {json.dumps(ozet['windows'])}")


def sahne(durum: dict[str, Any]) -> dict[str, Any]:
    """Dolaşım Masası sahnesi: bir açık ödüncü olan öğrenci üye + raftaki bir nüsha."""
    from django.db.models import Count

    from apps.kutuphane.models import Copy, Loan, LoanStatus, Membership, Work

    acik = Loan.objects.filter(status=LoanStatus.OPEN, membership__student__isnull=False)
    tekli = [
        satir["membership_id"]
        for satir in acik.values("membership_id").annotate(n=Count("pk")).filter(n=1)
    ]
    odunc = acik.filter(membership_id__in=tekli, due_date__gt=GORUNTU_GUNU).order_by("pk").first()
    assert odunc is not None and odunc.membership_id is not None
    uye = Membership.objects.get(pk=odunc.membership_id)
    rafta = sorted(durum["rafta"])
    kitap = Copy.objects.select_related("work").get(pk=rafta[len(rafta) // 3])
    # Eser ayrıntısı: deneme verisinin bilinen eserlerinden en çok nüshalısı (künye kişisel
    # veri değildir); eşitlikte kimlik sırası — her koşu aynı eseri seçer.
    klasikler = [k.ad for k in sys.modules["kd_deneme_verisi"].KLASIKLER]
    eser = (
        Work.objects.filter(title__in=klasikler)
        .annotate(nusha=Count("copies"))
        .order_by("-nusha", "pk")
        .first()
    )
    assert eser is not None
    return {
        "kart_no": uye.card_no,
        "kitap_barkodu": kitap.barcode,
        "kitap": kitap.work.title,
        "eser_id": eser.pk,
        "katalog_aramasi": "roman",
        # Büyük harf ve "İ": Türkçe katlama (CLAUDE.md §2-8) sorguya da uygulanır.
        "tahta_aramasi": "SABAHATTİN",
    }


# --------------------------------------------------------------------------- sunum


def sun(cikti: Path, sure_sn: int) -> int:
    token = secrets.token_urlsafe(24)
    os.environ["KD_SESSION_TOKEN"] = token  # ayarlar okunmadan ÖNCE (desktop/main.py sırası)

    from desktop.django_bootstrap import (
        assert_session_guard_installed,
        build_wsgi_application,
        prepare_django,
        run_migrations,
    )
    from desktop.paths import resolve_backend_dir

    kok = Path(tempfile.mkdtemp(prefix="kd-ekran-"))
    prepare_django(resolve_backend_dir(), kok / "data")
    run_migrations()

    rng = random.Random(TOHUM)  # noqa: S311 — tekrarlanabilir uydurma veri, kriptografi değil
    bas = time.perf_counter()
    kurulum()
    aktarimlar(kok)
    uyeler = uyelikler(rng)
    durum = raf(rng)
    teslimler(rng, durum)
    dolasim(rng, uyeler, durum)
    yol_haritasi()
    cok_okunanlar()
    sayim_taslagi()
    sahne_verisi = sahne(durum)
    _yaz(f"TOHUM {time.perf_counter() - bas:.0f} sn")

    from apps.kutuphane.services.katalog_ayari import update_katalog_ayari
    from apps.okul.kip import KIP
    from desktop.katalog_kontrol import KatalogKontrol
    from desktop.server import BackgroundServer, check_health
    from desktop.session_guard import window_url

    application = build_wsgi_application()
    assert_session_guard_installed()
    yonetim = BackgroundServer(application)
    yonetim.start()
    yonetim.wait_until_ready()
    check_health(yonetim.base_url, token)

    update_katalog_ayari(sistem_yazimi=True, acik=True, kutuphane_saatleri="Hafta içi 08.30-16.30")
    kontrol = KatalogKontrol()
    kontrol.acilista_baslat()
    kdurum = kontrol.durum()
    _yaz("KATALOG " + json.dumps({k: kdurum[k] for k in ("durum", "port", "son_hata")}))
    KIP.sureleri_yeniden_baslat()

    cikti.mkdir(parents=True, exist_ok=True)
    durum_dosyasi = cikti / "durum.json"
    bitti = cikti / "bitti"
    bitti.unlink(missing_ok=True)
    durum_dosyasi.write_text(
        json.dumps(
            {
                "yonetim": window_url(yonetim.base_url, token),
                "yonetim_taban": yonetim.base_url,
                "katalog": f"http://127.0.0.1:{KATALOG_PORT}",
                "katalog_acik": kdurum["durum"] == "acik",
                "parola": PAROLA,
                "sahne": sahne_verisi,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _yaz("EKRAN_HAZIR")
    bitis = time.monotonic() + sure_sn
    try:
        while time.monotonic() < bitis and not bitti.exists():
            KIP.etkinlik()  # masadaki yöneticinin etkinliği (§4.4 boşta süresi)
            time.sleep(2)
    finally:
        durum_dosyasi.unlink(missing_ok=True)
        bitti.unlink(missing_ok=True)
        kontrol.kapanis()
        yonetim.stop()
    _yaz("EKRAN_BITTI")
    return 0


def main(argv: list[str]) -> int:
    ayri = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ayri.add_argument("--cikti", type=Path, required=True, help="durum dosyasının klasörü")
    ayri.add_argument("--sure", type=int, default=1800, help="en uzun sunum süresi (sn)")
    secenek = ayri.parse_args(argv)
    return sun(secenek.cikti, secenek.sure)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
