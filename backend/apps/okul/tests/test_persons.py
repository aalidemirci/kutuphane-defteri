"""Öğrenci/personel ELLE kayıt işlemleri, ayrılış yolu ve unutma kancası — servis + uç.

İçe aktarma yolu `test_imports.py` ve mutabakat testlerinde sınanır; burada
sicil ekranının elle ekleme/düzeltme/ayrılış/silme yolu sabitlenir:

- Güncelleme YALNIZ değişen alanı yazar ve `updated_at`'i elle damgalar
  (`save(update_fields=…)` `auto_now` alanını kendiliğinden yazmaz).
- Elle giriş içe aktarmayla AYNI katlamadan geçer: şube harfi Türkçe büyütülür
  ('i' → 'İ'), seviye okul içi sabite (1-12 + hazırlık bayrağı) karşı doğrulanır.
- Okul no teklik iletisi servisten gelir (kör indeks, T14).
- AYRILIŞ KAYDI SİLMEZ (F1 eki 7, kullanıcı kararı 22.09.2026): ayrılış
  LEFT / `is_active=False` + `left_at` yazar, havuzdan çıkarır, kancaları koşar;
  kayıt üyelik ve yükümlülükten bağımsız olarak KALIR (eski "hiç üye olmamış ve
  yükümlülüksüz → katı sil" dalı kalktı; bu testler o davranışı tersine sabitler).
- Kullanıcı silmesi ("Sil" düğmesi) kuralı korunur: açık yükümlülükte gerekçeyle
  reddedilir, üye olmuş kişide ayrılış yoluna yönlendirir, aksi hâlde katı siler.
  F1'de kayıtlı denetim yoktur: yollar SAHTE kayıtlı denetimlerle sınanır.

Tüm ad ve numaralar uydurmadır (KVKK).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul.models import MemberKind, Personnel, Student, StudentStatus
from apps.okul.services import persons
from apps.okul.services import setup as setup_service

pytestmark = pytest.mark.django_db

OGRENCI_URL = "/api/v1/students/"
PERSONEL_URL = "/api/v1/personnel/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def bos_kayit_defterleri(monkeypatch: pytest.MonkeyPatch) -> None:
    """Her test boş kayıt defterleriyle başlar (F6/F7 kayıtları testleri etkilemesin)."""
    for ad in (
        "_obligation_checks",
        "_membership_checks",
        "_leave_hooks",
        "_merge_hooks",
        "_deletion_blocks",
    ):
        monkeypatch.setattr(persons, ad, [])


@pytest.fixture
def uye_olmus(monkeypatch: pytest.MonkeyPatch) -> Iterator[set[tuple[str, int]]]:
    """Sahte üyelik denetimi: kümeye eklenen (model, pk) "hiç üye olmuş" sayılır."""
    uyeler: set[tuple[str, int]] = set()
    persons.register_membership_check(lambda kisi: (type(kisi).__name__, kisi.pk) in uyeler)
    yield uyeler


@pytest.fixture
def acik_yukumluluk(monkeypatch: pytest.MonkeyPatch) -> Iterator[set[tuple[str, int]]]:
    """Sahte yükümlülük denetimi: kümedekilerin "açık ödüncü" vardır (gerekçe adsız)."""
    borclular: set[tuple[str, int]] = set()

    def _denetim(kisi: persons.Person) -> list[str]:
        return ["Açık ödünç var."] if (type(kisi).__name__, kisi.pk) in borclular else []

    persons.register_obligation_check(_denetim)
    yield borclular


def _ogrenci(**alanlar: Any) -> Student:
    varsayilan: dict[str, Any] = {
        "first_name": "DENEME",
        "last_name": "ÖĞRENCİ",
        "student_number": "501",
        "class_level": 9,
        "class_section": "A",
    }
    varsayilan.update(alanlar)
    return persons.create_student(**varsayilan)


def _personel(**alanlar: Any) -> Personnel:
    varsayilan: dict[str, Any] = {"first_name": "DENEME", "last_name": "ÖĞRETMEN"}
    varsayilan.update(alanlar)
    return persons.create_personnel(**varsayilan)


def _anahtar(kisi: persons.Person) -> tuple[str, int]:
    return (type(kisi).__name__, kisi.pk)


def _eskit(kayit: Student | Personnel) -> Any:
    """`updated_at`'i geçmişe çeker → sonraki yazmanın damgayı yenilediği ölçülebilir."""
    eski = timezone.now() - timedelta(days=3)
    type(kayit).objects.filter(pk=kayit.pk).update(updated_at=eski)
    kayit.refresh_from_db()
    return eski


def _sonuclar(yanit: Any) -> list[dict[str, Any]]:
    veri = yanit.json()
    return list(veri["results"]) if isinstance(veri, dict) else list(veri)


# ---------------------------------------------------------------------------
# Servis — öğrenci
# ---------------------------------------------------------------------------


def test_ogrenci_olusturulur_ve_evrak_etiketleri_turetilir() -> None:
    """Evrak sözleşmesi üç alandır: `full_name`, `student_number`, `class_label`."""
    ogrenci = _ogrenci()

    ogrenci.refresh_from_db()
    assert ogrenci.full_name == "DENEME ÖĞRENCİ"
    assert ogrenci.student_number == "501"
    assert ogrenci.class_label == "9/A"
    assert ogrenci.status == StudentStatus.ACTIVE
    assert ogrenci.left_at is None


def test_ogrenci_guncelleme_degisen_alani_yazar_ve_damgayi_yeniler() -> None:
    """`save(update_fields=…)` `auto_now`'ı kendiliğinden yazmaz — damga elle eklenir."""
    ogrenci = _ogrenci()
    eski = _eskit(ogrenci)

    persons.update_student(ogrenci, class_section="B")

    ogrenci.refresh_from_db()
    assert ogrenci.class_label == "9/B"
    assert ogrenci.updated_at > eski


def test_ogrenci_guncelleme_degisiklik_yoksa_yazmaz() -> None:
    """Aynı değerle gelen kayıt isteği veritabanına dokunmaz (damga eskide kalır)."""
    ogrenci = _ogrenci()
    eski = _eskit(ogrenci)

    persons.update_student(ogrenci, class_section="A", student_number="501")

    ogrenci.refresh_from_db()
    assert ogrenci.updated_at == eski


def test_ogrenci_guncelleme_dokunulmayan_alani_ezmez() -> None:
    """Yalnız DEĞİŞEN alan yazılır: bellekteki bayat kopya başka alanı geri sarmaz.

    Senaryo: sicil ekranı açıkken içe aktarma öğrenciyi "ayrıldı" yaptı; ekranda
    yalnız şubesi düzeltilip kaydedilince durum yeniden AKTİF'e dönmemeli.
    """
    ogrenci = _ogrenci()
    Student.objects.filter(pk=ogrenci.pk).update(status=StudentStatus.LEFT)

    persons.update_student(ogrenci, class_section="C")  # `ogrenci` bellekte hâlâ ACTIVE

    ogrenci.refresh_from_db()
    assert ogrenci.class_section == "C"
    assert ogrenci.status == StudentStatus.LEFT


def test_ogrenci_numara_degisince_kor_indeks_de_degisir() -> None:
    ogrenci = _ogrenci(student_number="501")

    persons.update_student(ogrenci, student_number="777")

    assert Student.objects.filter(student_number_index=ogrenci.student_number_index).count() == 1
    ogrenci.refresh_from_db()
    assert ogrenci.student_number == "777"


def test_servis_okul_no_teklik_iletisi_turkcedir() -> None:
    """Teklik kör indekstedir: '0501' ile '501' aynı numaradır; ileti servisten gelir."""
    _ogrenci(student_number="501")

    with pytest.raises(ValidationError) as hata:
        _ogrenci(student_number="0501", first_name="BAŞKA")

    assert hata.value.message_dict == {"student_number": [persons.DUPLICATE_NUMBER_MESSAGE]}


# ---------------------------------------------------------------------------
# Servis — personel
# ---------------------------------------------------------------------------


def test_personel_olusturulur_varsayilan_aktif_ve_ogretmendir() -> None:
    kisi = _personel()

    kisi.refresh_from_db()
    assert kisi.full_name == "DENEME ÖĞRETMEN"
    assert kisi.is_active is True
    assert kisi.member_kind == MemberKind.TEACHER
    assert kisi.left_at is None


def test_personel_guncelleme_degisen_alani_yazar_ve_damgayi_yeniler() -> None:
    kisi = _personel()
    eski = _eskit(kisi)

    persons.update_personnel(kisi, member_kind=MemberKind.STAFF)

    kisi.refresh_from_db()
    assert kisi.member_kind == MemberKind.STAFF
    assert kisi.updated_at > eski


def test_personel_guncelleme_degisiklik_yoksa_yazmaz() -> None:
    kisi = _personel()
    eski = _eskit(kisi)

    persons.update_personnel(kisi, member_kind=MemberKind.TEACHER, first_name="DENEME")

    kisi.refresh_from_db()
    assert kisi.updated_at == eski


def test_personel_guncelleme_dokunulmayan_alani_ezmez() -> None:
    """Bayat kopya üzerinden üye türü düzeltmek, ayrılışı geri almaz."""
    kisi = _personel()
    Personnel.objects.filter(pk=kisi.pk).update(is_active=False)

    persons.update_personnel(kisi, member_kind=MemberKind.STAFF)  # `kisi` bellekte hâlâ aktif

    kisi.refresh_from_db()
    assert (kisi.member_kind, kisi.is_active) == (MemberKind.STAFF, False)


# ---------------------------------------------------------------------------
# Ayrılış yolu (§6.1, F1 eki 7) — kayıt SİLİNMEZ
# ---------------------------------------------------------------------------


def test_ayrilis_hic_uye_olmamis_ve_yukumluluksuz_ogrenciyi_silmez() -> None:
    """Eski kural tersine döndü: üyeliği ve yükümlülüğü olmayan öğrencinin kaydı da kalır."""
    ogrenci = _ogrenci()

    sonuc = persons.leave_student(ogrenci)

    assert sonuc.pk == ogrenci.pk
    ogrenci.refresh_from_db()
    assert (ogrenci.status, ogrenci.left_at) == (StudentStatus.LEFT, timezone.localdate())
    assert ogrenci.deleted_at is None
    assert Student.all_objects.count() == 1


def test_ayrilis_hic_uye_olmamis_ve_yukumluluksuz_personeli_silmez() -> None:
    kisi = _personel()

    persons.leave_personnel(kisi)

    kisi.refresh_from_db()
    assert (kisi.is_active, kisi.left_at, kisi.deleted_at) == (False, timezone.localdate(), None)
    assert Personnel.all_objects.count() == 1


def test_ayrilis_uye_olmus_ogrencide_de_kaydi_saklar(
    uye_olmus: set[tuple[str, int]],
) -> None:
    ogrenci = _ogrenci()
    uye_olmus.add(_anahtar(ogrenci))

    persons.leave_student(ogrenci)

    ogrenci.refresh_from_db()
    assert ogrenci.status == StudentStatus.LEFT
    assert ogrenci.left_at == timezone.localdate()


def test_ayrilis_acik_yukumlulugu_olan_personelde_de_kaydi_saklar(
    acik_yukumluluk: set[tuple[str, int]],
) -> None:
    kisi = _personel()
    acik_yukumluluk.add(_anahtar(kisi))

    persons.leave_personnel(kisi)
    kisi.refresh_from_db()
    assert (kisi.is_active, kisi.left_at) == (False, timezone.localdate())


def test_ayrilis_havuzdaki_kisiyi_havuzdan_cikarir() -> None:
    """Havuzdaki kişi elle "Ayrıldı olarak işaretle"nince havuz alanları aynı kayıtta temizlenir."""
    ogrenci = _ogrenci()
    kisi = _personel()
    persons.add_to_leave_pool(ogrenci, run=None)
    persons.add_to_leave_pool(kisi, run=None)

    persons.leave_student(ogrenci)
    persons.leave_personnel(kisi)

    for kayit in (ogrenci, kisi):
        kayit.refresh_from_db()
        assert (kayit.leave_candidate_since, kayit.leave_candidate_run_id) == (None, None)


def test_ayrilis_kancasi_kisiyle_ve_left_olarak_cagrilir(
    uye_olmus: set[tuple[str, int]],
) -> None:
    """Kanca (F6: üyeliği sonlandırır) kişiyi alır; kayıt o anda LEFT'tir."""
    gorulen: list[tuple[str, int, str]] = []

    def _kanca(kisi: persons.Person) -> None:
        assert isinstance(kisi, Student)
        gorulen.append((type(kisi).__name__, kisi.pk, kisi.status))

    persons.register_leave_hook(_kanca)
    persons.register_leave_hook(_kanca)  # idempotent kayıt
    ogrenci = _ogrenci()
    pk = ogrenci.pk

    persons.leave_student(ogrenci)

    assert gorulen == [("Student", pk, StudentStatus.LEFT)]


def test_ayrilis_kancasi_hata_verirse_ayrilis_geri_sarilir() -> None:
    """Kanca AYNI işlemde koşar: kanca başarısızsa öğrenci ayrılmış sayılmaz."""

    def _patla(_kisi: persons.Person) -> None:
        raise RuntimeError("kanca başarısız")

    persons.register_leave_hook(_patla)
    ogrenci = _ogrenci()

    with pytest.raises(RuntimeError):
        persons.leave_student(ogrenci)

    ogrenci.refresh_from_db()
    assert (ogrenci.status, ogrenci.left_at) == (StudentStatus.ACTIVE, None)


def test_zaten_ayrilmis_kisi_yeniden_ayrilamaz() -> None:
    ogrenci = _ogrenci()
    persons.leave_student(ogrenci)

    with pytest.raises(ValidationError, match="zaten ayrıldı"):
        persons.leave_student(ogrenci)


def test_ayrilan_ogrencinin_numarasi_yeni_ogrenciye_verilebilir() -> None:
    """Teklik yalnız AKTİF canlı kayıtları sayar: ayrılmış (saklanan) kayıt engel olmaz."""
    eski = _ogrenci(student_number="777")
    persons.leave_student(eski)

    yeni = _ogrenci(student_number="777", first_name="BAŞKA")

    assert yeni.pk != eski.pk


# ---------------------------------------------------------------------------
# Kullanıcı silmesi ("Sil" düğmesi — bilinçli eylem; kural F1 eki 7'de değişmedi)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("olustur", "sil", "model"),
    [
        (_ogrenci, persons.delete_student, Student),
        (_personel, persons.delete_personnel, Personnel),
    ],
)
def test_silme_hic_uye_olmamis_kisiyi_kati_siler(
    olustur: Callable[..., Any], sil: Callable[[Any], None], model: type[Any]
) -> None:
    kisi = olustur()
    pk = kisi.pk

    sil(kisi)

    assert not model.all_objects.filter(pk=pk).exists()
    assert model.all_objects.count() == 0


def test_ayrilmis_ve_hic_uye_olmamis_kisi_elle_silinebilir() -> None:
    """Ayrılış kaydı saklar; yanlış girilmiş kaydı kullanıcı yine "Sil" ile katı siler."""
    ogrenci = _ogrenci()
    persons.leave_student(ogrenci)

    persons.delete_student(ogrenci)

    assert not Student.all_objects.filter(pk=ogrenci.pk).exists()


def test_silme_acik_yukumlulukte_gerekceyle_reddedilir(
    acik_yukumluluk: set[tuple[str, int]],
) -> None:
    ogrenci = _ogrenci()
    acik_yukumluluk.add(_anahtar(ogrenci))

    with pytest.raises(ValidationError) as hata:
        persons.delete_student(ogrenci)

    assert hata.value.messages == ["Kayıt silinemez: Açık ödünç var."]
    assert Student.objects.filter(pk=ogrenci.pk).exists()


def test_silme_uye_olmus_kisiyi_ayrilis_yoluna_yonlendirir(
    uye_olmus: set[tuple[str, int]],
) -> None:
    kisi = _personel()
    uye_olmus.add(_anahtar(kisi))

    with pytest.raises(ValidationError) as hata:
        persons.delete_personnel(kisi)

    assert hata.value.messages == [persons.MEMBER_DELETE_MESSAGE]
    assert "Ayrıldı olarak işaretle" in persons.MEMBER_DELETE_MESSAGE
    assert Personnel.objects.filter(pk=kisi.pk).exists()


# ---------------------------------------------------------------------------
# Birleştirme (olası aynı kişi)
# ---------------------------------------------------------------------------


def test_birlestirme_kancalari_kaynak_hedef_sirasiyla_cagrilir_kaynak_silinir() -> None:
    tasinan: list[tuple[int, int]] = []
    persons.register_merge_hook(lambda kaynak, hedef: tasinan.append((kaynak.pk, hedef.pk)))
    eski = _personel(first_name="AYŞE", last_name="ESKİSOYAD")
    yeni = _personel(first_name="AYŞE", last_name="YENİSOYAD")

    eski_pk = eski.pk

    sonuc = persons.merge_personnel(eski, yeni)

    assert sonuc.pk == yeni.pk
    assert tasinan == [(eski_pk, yeni.pk)]
    assert eski_pk is not None
    assert not Personnel.all_objects.filter(pk=eski_pk).exists()
    assert Personnel.objects.filter(pk=yeni.pk).exists()


def test_kisi_kendisiyle_birlestirilemez() -> None:
    kisi = _personel()

    with pytest.raises(ValidationError, match="kendisiyle"):
        persons.merge_personnel(kisi, kisi)


def test_birlestirme_kancasi_hata_verirse_kaynak_silinmez() -> None:
    def _patla(_kaynak: Personnel, _hedef: Personnel) -> None:
        raise RuntimeError("taşıma başarısız")

    persons.register_merge_hook(_patla)
    eski, yeni = _personel(), _personel(first_name="BAŞKA")

    with pytest.raises(RuntimeError):
        persons.merge_personnel(eski, yeni)

    assert Personnel.objects.filter(pk=eski.pk).exists()


# ---------------------------------------------------------------------------
# Uç — öğrenci
# ---------------------------------------------------------------------------


def test_api_ogrenci_ekleme_sube_harfini_turkce_buyutur(client: APIClient) -> None:
    """'i' → 'İ' (çıplak `.upper()` 'I' yapardı): 10/I ile 10/İ AYRI şubelerdir."""
    yanit = client.post(
        OGRENCI_URL,
        {
            "first_name": "DENEME",
            "last_name": "ÖĞRENCİ",
            "student_number": " 601 ",
            "class_level": 10,
            "class_section": " i ",
        },
        format="json",
    )

    assert yanit.status_code == 201
    assert yanit.json()["class_section"] == "İ"
    assert yanit.json()["class_label"] == "10/İ"
    assert yanit.json()["full_name"] == "DENEME ÖĞRENCİ"
    assert yanit.json()["student_number"] == "601"
    assert yanit.json()["left_at"] is None
    ogrenci = Student.objects.get(pk=yanit.json()["id"])
    assert ogrenci.class_section == "İ"


def test_api_ogrenci_seviyesi_okul_ici_sabite_karsi_dogrulanir(client: APIClient) -> None:
    """Küme okul içi sabittir (1-12); hazırlık bayrağı 0'ı ekler, mesaj kümeyi sayar."""
    govde = {"first_name": "DENEME", "last_name": "ÖĞRENCİ", "class_section": "A"}

    ilkokul = client.post(OGRENCI_URL, {**govde, "class_level": 1}, format="json")
    assert ilkokul.status_code == 201
    assert ilkokul.json()["class_label"] == "1/A"

    kume_disi = client.post(OGRENCI_URL, {**govde, "class_level": 13}, format="json")
    assert kume_disi.status_code == 400
    assert "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12." in str(
        kume_disi.json()["fields"]["class_level"]
    )

    # Hazırlık kapalıyken 0 da geçersizdir; açılınca kabul edilir ve etiketi "Hz/…" olur.
    assert client.post(OGRENCI_URL, {**govde, "class_level": 0}, format="json").status_code == 400
    setup_service.update_school_config(fields={"has_prep_class": True})
    hazirlik = client.post(OGRENCI_URL, {**govde, "class_level": 0}, format="json")
    assert hazirlik.status_code == 201
    assert hazirlik.json()["class_label"] == "Hz/A"

    hata = client.post(OGRENCI_URL, {**govde, "class_level": 13}, format="json")
    assert "Hazırlık, 1, 2, 3" in str(hata.json()["fields"]["class_level"])


def test_api_sinifsiz_ogrenci_kaydedilebilir(client: APIClient) -> None:
    """Sınıfı henüz belli olmayan (nakil gelen) öğrenci sicile girebilir; etiketi boştur."""
    yanit = client.post(
        OGRENCI_URL,
        {"first_name": "DENEME", "last_name": "NAKİL", "class_level": None, "class_section": "  "},
        format="json",
    )

    assert yanit.status_code == 201
    assert yanit.json()["class_level"] is None
    assert yanit.json()["class_section"] == ""
    assert yanit.json()["class_label"] == ""


def test_api_aktif_ogrencide_okul_numarasi_tekildir(client: APIClient) -> None:
    """Numara içe aktarmanın eşleştirme anahtarıdır: aktif iki kayıt aynı numarayı taşıyamaz.

    Çakışma 500 (IntegrityError) DEĞİL 400'dür ve ileti servisten, Türkçe gelir
    (DRF'nin otomatik UniqueValidator'ı yoktur). Ayrılan öğrencinin numarası ise
    yeni öğrenciye verilebilir (kısıt yalnız AKTİF canlı kayıtları sayar).
    """
    eski = _ogrenci(student_number="900")
    govde = {
        "first_name": "BAŞKA",
        "last_name": "ÖĞRENCİ",
        "student_number": "0900",
        "class_level": 9,
        "class_section": "A",
    }

    cakisma = client.post(OGRENCI_URL, govde, format="json")
    assert cakisma.status_code == 400
    assert cakisma.json()["message"] == persons.DUPLICATE_NUMBER_MESSAGE
    assert cakisma.json()["fields"] == {"student_number": [persons.DUPLICATE_NUMBER_MESSAGE]}

    Student.objects.filter(pk=eski.pk).update(status=StudentStatus.LEFT)
    assert client.post(OGRENCI_URL, govde, format="json").status_code == 201


def test_api_duzeltmede_baska_ogrencinin_numarasi_alinamaz(client: APIClient) -> None:
    _ogrenci(student_number="100")
    ikinci = _ogrenci(student_number="200", first_name="İKİNCİ")

    yanit = client.patch(f"{OGRENCI_URL}{ikinci.pk}/", {"student_number": "100"}, format="json")

    assert yanit.status_code == 400
    assert yanit.json()["message"] == persons.DUPLICATE_NUMBER_MESSAGE
    # Kendi numarasını yeniden göndermek çakışma sayılmaz.
    kendi = client.patch(f"{OGRENCI_URL}{ikinci.pk}/", {"student_number": "200"}, format="json")
    assert kendi.status_code == 200


def test_api_ogrenci_durumu_govdeyle_degismez(client: APIClient) -> None:
    """`status`/`left_at` salt okunurdur: ayrılış yalnız `leave/` ayrılış yolundan geçer."""
    ogrenci = _ogrenci()

    yanit = client.patch(
        f"{OGRENCI_URL}{ogrenci.pk}/",
        {"status": "LEFT", "left_at": "2026-09-01"},
        format="json",
    )

    assert yanit.status_code == 200
    ogrenci.refresh_from_db()
    assert (ogrenci.status, ogrenci.left_at) == (StudentStatus.ACTIVE, None)


def test_api_ogrenci_duzeltme_ve_silme(client: APIClient) -> None:
    ogrenci = _ogrenci()

    duzelt = client.patch(f"{OGRENCI_URL}{ogrenci.pk}/", {"class_section": "ç"}, format="json")
    assert duzelt.status_code == 200
    assert duzelt.json()["class_label"] == "9/Ç"
    assert duzelt.json()["student_number"] == "501"  # gönderilmeyen alan korunur

    assert client.delete(f"{OGRENCI_URL}{ogrenci.pk}/").status_code == 204
    assert _sonuclar(client.get(OGRENCI_URL)) == []
    assert not Student.all_objects.filter(pk=ogrenci.pk).exists()  # katı silme
    kayip = client.get(f"{OGRENCI_URL}{ogrenci.pk}/")
    assert kayip.status_code == 404
    assert kayip.json() == {"code": "not_found", "message": "Kayıt bulunamadı.", "fields": {}}


def test_api_silme_acik_yukumlulukte_400_ve_gerekce(
    client: APIClient, acik_yukumluluk: set[tuple[str, int]]
) -> None:
    ogrenci = _ogrenci()
    acik_yukumluluk.add(_anahtar(ogrenci))

    yanit = client.delete(f"{OGRENCI_URL}{ogrenci.pk}/")

    assert yanit.status_code == 400
    assert yanit.json()["message"] == "Kayıt silinemez: Açık ödünç var."
    assert Student.objects.filter(pk=ogrenci.pk).exists()


def test_api_ogrenci_listesi_suzgecleri(client: APIClient) -> None:
    """Sicil ekranı ayrılanı da gösterir; `only_active` yalnız seçicilerin opt-in süzgecidir."""
    _ogrenci(student_number="101", class_section="Ş", first_name="IŞIL")
    _ogrenci(student_number="102", class_level=10, first_name="ÇAĞRI")
    ayrilan = _ogrenci(student_number="103", first_name="AYRILAN")
    Student.objects.filter(pk=ayrilan.pk).update(status=StudentStatus.LEFT)

    def numaralar(**params: str) -> set[str]:
        return {s["student_number"] for s in _sonuclar(client.get(OGRENCI_URL, params))}

    assert numaralar() == {"101", "102", "103"}
    assert numaralar(only_active="true") == {"101", "102"}
    assert numaralar(class_level="10") == {"102"}
    # Şube süzgeci kayıtla AYNI katlamadan geçer: küçük 'ş' ile aranan 'Ş' bulunur.
    assert numaralar(class_section="ş") == {"101"}
    # Ad şifreli → arama Python'da ve Türkçe katlamalı ('isil' → 'IŞIL').
    assert numaralar(search="isil") == {"101"}
    # Okul no şifreli → kör indeksle TAM eşleşme.
    assert numaralar(search="102") == {"102"}
    assert numaralar(search="10") == set()

    bozuk = client.get(OGRENCI_URL, {"class_level": "dokuz"})
    assert bozuk.status_code == 400
    assert "sayısal" in str(bozuk.json()["fields"]["class_level"])


def test_api_ogrenci_ayrilis_ucu_kaydi_saklar_ve_doner(client: APIClient) -> None:
    """Ayrılış ucu hiçbir durumda silmez (üye olmamış öğrencide de); ayrılmış kaydı döner."""
    ogrenci = _ogrenci(student_number="301")

    ayril = client.post(f"{OGRENCI_URL}{ogrenci.pk}/leave/")
    assert ayril.status_code == 200
    assert ayril.json()["id"] == ogrenci.pk
    assert ayril.json()["status"] == "LEFT"
    assert ayril.json()["left_at"] == timezone.localdate().isoformat()
    assert ayril.json()["leave_candidate_since"] is None
    assert "deleted" not in ayril.json()
    assert Student.all_objects.filter(pk=ogrenci.pk, deleted_at__isnull=True).exists()

    tekrar = client.post(f"{OGRENCI_URL}{ogrenci.pk}/leave/")
    assert tekrar.status_code == 400
    assert tekrar.json()["message"] == persons.ALREADY_LEFT_MESSAGE


# ---------------------------------------------------------------------------
# Uç — personel
# ---------------------------------------------------------------------------


def test_api_personel_ekleme_duzeltme_ayrilis_ve_silme(
    client: APIClient, uye_olmus: set[tuple[str, int]]
) -> None:
    ekle = client.post(
        PERSONEL_URL,
        {"first_name": "DENEME", "last_name": "ÖĞRETMEN", "member_kind": "STAFF"},
        format="json",
    )
    assert ekle.status_code == 201
    assert ekle.json()["full_name"] == "DENEME ÖĞRETMEN"
    assert ekle.json()["is_active"] is True
    assert ekle.json()["member_kind"] == "STAFF"
    kisi_id = ekle.json()["id"]
    uye_olmus.add(("Personnel", kisi_id))

    # `is_active` gövdeyle değişmez (salt okunur); ayrılış `leave/` ucundan.
    yok_sayilan = client.patch(f"{PERSONEL_URL}{kisi_id}/", {"is_active": False}, format="json")
    assert yok_sayilan.status_code == 200 and yok_sayilan.json()["is_active"] is True

    ayril = client.post(f"{PERSONEL_URL}{kisi_id}/leave/")
    assert ayril.status_code == 200
    assert ayril.json()["id"] == kisi_id
    assert ayril.json()["is_active"] is False
    assert ayril.json()["left_at"] == timezone.localdate().isoformat()
    # Sicil ekranı ayrılanı gösterir, seçiciler (only_active) göstermez.
    assert [p["id"] for p in _sonuclar(client.get(PERSONEL_URL))] == [kisi_id]
    assert _sonuclar(client.get(PERSONEL_URL, {"only_active": "true"})) == []

    # Üye olmuş kişi silinemez: ayrılış yoluna yönlendirilir.
    sil = client.delete(f"{PERSONEL_URL}{kisi_id}/")
    assert sil.status_code == 400
    assert sil.json()["message"] == persons.MEMBER_DELETE_MESSAGE


def test_api_personel_ad_soyad_zorunludur(client: APIClient) -> None:
    yanit = client.post(PERSONEL_URL, {"member_kind": "TEACHER"}, format="json")

    assert yanit.status_code == 400
    assert yanit.json()["code"] == "validation_error"
    assert set(yanit.json()["fields"]) == {"first_name", "last_name"}


def test_api_personel_uye_turu_dogrulanir_unvan_brans_yok_sayilir(client: APIClient) -> None:
    """Unvan/branş gövdede gelse bile hiçbir yere yazılmaz (alan yok); tür iki değerlidir."""
    gecersiz = client.post(
        PERSONEL_URL,
        {"first_name": "A", "last_name": "B", "member_kind": "MUDUR"},
        format="json",
    )
    assert gecersiz.status_code == 400
    assert "üye türü" in str(gecersiz.json()["fields"]["member_kind"])

    yanit = client.post(
        PERSONEL_URL,
        {"first_name": "A", "last_name": "B", "title": "Müdür", "branch": "Matematik"},
        format="json",
    )
    assert yanit.status_code == 201
    assert "title" not in yanit.json() and "branch" not in yanit.json()
    assert yanit.json()["member_kind"] == "TEACHER"


def test_api_personel_aramasi_yalniz_adda_turkce_katlar(client: APIClient) -> None:
    _personel(first_name="ÇAĞLA", last_name="ÖRNEK")
    _personel(first_name="DENEME", last_name="ÖĞRETMEN")

    def adlar(aranan: str) -> list[str]:
        return [p["first_name"] for p in _sonuclar(client.get(PERSONEL_URL, {"search": aranan}))]

    assert adlar("cagla") == ["ÇAĞLA"]
    assert adlar("ogretmen") == ["DENEME"]
    assert adlar("olmayan") == []


def test_api_personel_birlestirme_ucu(client: APIClient) -> None:
    eski = _personel(first_name="AYŞE", last_name="ESKİSOYAD")
    yeni = _personel(first_name="AYŞE", last_name="YENİSOYAD")

    yanit = client.post(f"{PERSONEL_URL}{eski.pk}/merge/", {"into_id": yeni.pk}, format="json")

    assert yanit.status_code == 200
    assert yanit.json()["id"] == yeni.pk
    assert not Personnel.all_objects.filter(pk=eski.pk).exists()


def test_api_personel_birlestirme_hatalari(client: APIClient) -> None:
    kisi = _personel()

    kendisi = client.post(f"{PERSONEL_URL}{kisi.pk}/merge/", {"into_id": kisi.pk}, format="json")
    assert kendisi.status_code == 400
    assert kendisi.json()["message"] == persons.SELF_MERGE_MESSAGE

    olmayan = client.post(f"{PERSONEL_URL}{kisi.pk}/merge/", {"into_id": 99999}, format="json")
    assert olmayan.status_code == 404

    govdesiz = client.post(f"{PERSONEL_URL}{kisi.pk}/merge/", {}, format="json")
    assert govdesiz.status_code == 400
    assert "hedef" in str(govdesiz.json()["fields"]["into_id"])
    assert Personnel.objects.filter(pk=kisi.pk).exists()


def test_api_personel_listesi_ad_sirasiyla(client: APIClient) -> None:
    for ad in ("ZEHRA", "ÇAĞLA", "CEM"):
        _personel(first_name=ad)

    assert [p["first_name"] for p in _sonuclar(client.get(PERSONEL_URL))] == [
        "CEM",
        "ÇAĞLA",
        "ZEHRA",
    ]
