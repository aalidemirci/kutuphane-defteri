"""Geri yükleme provasının ALT SÜREÇ betiği — gerçek ayarlar, gerçek veritabanı (F11).

Masaüstü testleri asgari Django ayarlarıyla koşar (`conftest.py`); temiz makinede
geri yükleme provası ise gerçek şemayı, gerçek şifrelemeyi ve gerçek yedek
kapsayıcısını ister. Bu betik `python -m desktop.tests.prova_betigi <komut>` ile
AYRI süreçte koşar ve sonucunu stdout'un son satırına JSON olarak yazar. Toplanmaz
(`test_` ile başlamaz).

Komutlar:

* `hazirla --data-dir A --usb U` — göç, yönetici parolası + kurtarma anahtarı
  (doğrulanmış), uydurma kişi/katalog/üyelik/ödünç, **dış yedek** (kullanıcının
  indirdiği şifreli yedek, `encrypted_backup`) U klasörüne; ardından yedekten
  SONRA bir kart daha verilir (basılıp dağıtılmış sayılır).
* `dogrula --data-dir B (--parola P | --kurtarma K --yeni-parola P2)` — kilidi
  açar, özet ve verilmiş kart defterini yazar.
* `kart-dene --data-dir B --parola P --govde 123456 …` — rastgele gövde yerine
  verilen gövdeleri sırayla dener; verilen kartı yazar (defter ve `IssuedCard`
  denetimi gerçek servisten geçer).
* `gelecek-yedek --data-dir A --parola P --usb U` — veritabanına programın
  tanımadığı bir göç kaydı yazıp dış yedek alır, sonra kaydı siler (daha yeni bir
  sürümün yedeği; eski-sürüm kapısının geri yükleme yolu).
* `sihirbaz --data-dir B --parola P2` — yeni bilgisayarda kurucunun "programı
  çalıştır" kutusuyla açılan programda sihirbazın BAŞKA bir parolayla kurulması
  (göç + parola + doğrulanmış anahtar, kişi verisi yok). Geri yüklemeden önce
  yabancı bir güvenlik dosyası, yedek anahtarı ve boş veritabanı bırakır (F11
  düzeltme turu).
* `gun-kapisi --data-dir A --parola P` — gün değişimi kapısını (`kd-gunluk`) gerçek
  işleriyle bir kez çalıştırır: yerleşik günlük yedek + backend'in kayıtlı bütün
  işleri (çok okunanlar, saklama taraması …). Ağ tuzağı altında koşar (F11 düzeltme
  turu: açılışta dış istek yok testinin kapıyı da kapsaması).

Bütün veriler UYDURMADIR (CLAUDE.md §2-12). Argon2 ucuz profille kurulur: parametreler
güvenlik dosyasına yazılır ve yedeğin başlığıyla taşınır; algoritma aynıdır.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from desktop.django_bootstrap import prepare_django, run_migrations
from desktop.paths import ENV_APP_HOME, resolve_app_paths, resolve_backend_dir

#: Uydurma yönetici parolası (yalnız bu provanın geçici veri dizini için).
PAROLA = "Prova-Yonetici-Parolasi-1"
YENI_PAROLA = "Prova-Yeni-Parola-2"
#: Sahte "gelecek sürüm" göçü (program tanımaz).
GELECEK_GOC = ("okul", "9999_gelecek_surum")

_UCUZ_KDF = {"time_cost": 1, "memory_cost": 8, "parallelism": 1}


def _django(veri_koku: str) -> Path:
    os.environ[ENV_APP_HOME] = veri_koku
    paths = resolve_app_paths()
    paths.ensure()
    prepare_django(resolve_backend_dir(), paths.data)
    return paths.data


def _ozet() -> dict[str, Any]:
    """Veri eşitliğinin ölçüsü: şifreli adlar ÇÖZÜLMÜŞ olarak, TR sırasıyla değil pk ile."""
    from apps.kutuphane.models import Copy, IssuedCard, Loan, LoanStatus, Membership, Work
    from apps.okul.models import Personnel, Student

    return {
        "ogrenciler": [
            [o.first_name, o.last_name, o.student_number, o.class_level, o.class_section]
            for o in Student.objects.order_by("pk")
        ],
        "personel": [[p.first_name, p.last_name] for p in Personnel.objects.order_by("pk")],
        "eserler": [[w.title, w.authors] for w in Work.objects.order_by("pk")],
        "nushalar": [[c.barcode, c.status] for c in Copy.objects.order_by("pk")],
        "uyelikler": [[m.card_no, m.status] for m in Membership.objects.order_by("pk")],
        "acik_odunc": [
            [loan.copy.barcode, loan.membership.card_no if loan.membership else ""]
            for loan in Loan.objects.filter(status=LoanStatus.OPEN).order_by("pk")
        ],
        "verilmis_kart_sayisi": IssuedCard.objects.count(),
    }


def hazirla(args: argparse.Namespace) -> dict[str, Any]:
    _django(args.data_dir)  # backend/ sys.path'e ÖNCE girer; `apps` ancak sonra import edilir
    from apps.kutuphane.models import AcquisitionMethod
    from apps.kutuphane.services import catalog, circulation, memberships
    from apps.okul.models import MemberKind, Personnel, Student
    from apps.okul.services import app_password, encrypted_backup
    from shared import crypto

    run_migrations()
    crypto.DEFAULT_KDF = crypto.KdfParams.from_dict(_UCUZ_KDF)
    kurtarma = app_password.enable(password=PAROLA)
    app_password.confirm_recovery_key(kurtarma)

    ogrenci = Student.objects.create(
        first_name="Deneme Çağla",
        last_name="Öğrenci Işıklı",
        student_number="700123",
        class_level=9,
        class_section="A",
    )
    Student.objects.create(
        first_name="Deneme İlkay",
        last_name="Şahinoğlu",
        student_number="700124",
        class_level=10,
        class_section="B",
    )
    ogretmen = Personnel.objects.create(
        first_name="Deneme Şükrü", last_name="Öğretmenoğlu", member_kind=MemberKind.TEACHER
    )
    edinim = catalog.create_acquisition(
        method=AcquisitionMethod.EXISTING_STOCK, date=date(2026, 9, 1)
    )
    eser = catalog.create_work(title="Kürk Mantolu Madonna", authors="Sabahattin Ali")
    ikinci = catalog.create_work(title="İnce Memed", authors="Yaşar Kemal")
    birinci_nusha = catalog.create_copy(work=eser, acquisition=edinim)
    catalog.create_copy(work=eser, acquisition=edinim)
    catalog.create_copy(work=ikinci, acquisition=edinim)
    uyelik = memberships.create_membership(student=ogrenci)
    circulation.checkout(copy=birinci_nusha, membership=uyelik)

    # Dış yedek: kullanıcının Ayarlar → Güvenlik'ten indirip USB'ye aldığı şifreli yedek.
    icerik, ad = encrypted_backup.create_encrypted_backup()
    usb = Path(args.usb)
    usb.mkdir(parents=True, exist_ok=True)
    yedek = usb / ad
    yedek.write_bytes(icerik)
    beklenen = _ozet()

    # Yedekten SONRA verilen kart: basılıp dağıtılmış sayılır, geri yükleme onu
    # geri sarsa bile numarası bir daha verilmemeli (F6, `card_ledger`).
    sonra = memberships.create_membership(personnel=ogretmen)
    return {
        "parola": PAROLA,
        "kurtarma": kurtarma,
        "yedek": str(yedek),
        "beklenen": beklenen,
        "kart_once": uyelik.card_no,
        "kart_sonra": sonra.card_no,
    }


def dogrula(args: argparse.Namespace) -> dict[str, Any]:
    _django(args.data_dir)
    from apps.kutuphane import card_ledger
    from apps.okul.services import app_password

    if args.parola:
        app_password.unlock(password=args.parola)
    else:
        app_password.unlock_with_recovery(recovery_key=args.kurtarma, new_password=args.yeni_parola)
    return {
        "ozet": _ozet(),
        "defter_satiri": len(card_ledger.issued_indexes()),
        "durum": app_password.status(),
    }


def kart_dene(args: argparse.Namespace) -> dict[str, Any]:
    _django(args.data_dir)
    from django.db import transaction

    from apps.kutuphane import card_numbers
    from apps.kutuphane.services import memberships
    from apps.okul.services import app_password

    app_password.unlock(password=args.parola)
    govdeler: Iterator[str] = itertools.chain(
        iter(args.govde), iter(card_numbers.random_body, None)
    )
    card_numbers.random_body = lambda: next(govdeler)
    with transaction.atomic():
        kart = memberships.issue_card_number()
    return {"kart": kart}


def gelecek_yedek(args: argparse.Namespace) -> dict[str, Any]:
    _django(args.data_dir)
    from django.db import connection
    from django.db.migrations.recorder import MigrationRecorder

    from apps.okul.services import app_password, encrypted_backup

    app_password.unlock(password=args.parola)
    kayit = MigrationRecorder(connection)
    kayit.record_applied(*GELECEK_GOC)
    try:
        icerik, _ad = encrypted_backup.create_encrypted_backup()
    finally:
        kayit.record_unapplied(*GELECEK_GOC)
    usb = Path(args.usb)
    usb.mkdir(parents=True, exist_ok=True)
    yedek = usb / "gelecek-surum-yedegi.kdbak"
    yedek.write_bytes(icerik)
    return {"yedek": str(yedek)}


def sihirbaz(args: argparse.Namespace) -> dict[str, Any]:
    _django(args.data_dir)
    from apps.okul.services import app_password
    from shared import crypto

    run_migrations()
    crypto.DEFAULT_KDF = crypto.KdfParams.from_dict(_UCUZ_KDF)
    kurtarma = app_password.enable(password=args.parola)
    app_password.confirm_recovery_key(kurtarma)
    return {"durum": app_password.status()}


def gun_kapisi(args: argparse.Namespace) -> dict[str, Any]:
    _django(args.data_dir)
    from apps.okul.services import app_password
    from desktop.gunluk import GunDegisimiKapisi
    from desktop.main import gunluk_yedek_isi

    app_password.unlock(password=args.parola)
    paths = resolve_app_paths()
    kapi = GunDegisimiKapisi(damga_yolu=paths.data / "kapi-sinamasi.json")
    kapi.kaydet("gunluk-yedek", gunluk_yedek_isi(paths))
    backend_is_sayisi = kapi.backend_islerini_ekle()
    biten = kapi.tik()
    return {"isler": list(kapi.is_adlari), "backend_is_sayisi": backend_is_sayisi, "biten": biten}


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(prog="prova_betigi")
    alt = ayristirici.add_subparsers(dest="komut", required=True)
    h = alt.add_parser("hazirla")
    h.add_argument("--data-dir", required=True)
    h.add_argument("--usb", required=True)
    d = alt.add_parser("dogrula")
    d.add_argument("--data-dir", required=True)
    d.add_argument("--parola", default="")
    d.add_argument("--kurtarma", default="")
    d.add_argument("--yeni-parola", default=YENI_PAROLA)
    k = alt.add_parser("kart-dene")
    k.add_argument("--data-dir", required=True)
    k.add_argument("--parola", required=True)
    k.add_argument("--govde", nargs="+", required=True)
    g = alt.add_parser("gelecek-yedek")
    g.add_argument("--data-dir", required=True)
    g.add_argument("--parola", required=True)
    g.add_argument("--usb", required=True)
    s = alt.add_parser("sihirbaz")
    s.add_argument("--data-dir", required=True)
    s.add_argument("--parola", required=True)
    c = alt.add_parser("gun-kapisi")
    c.add_argument("--data-dir", required=True)
    c.add_argument("--parola", required=True)
    args = ayristirici.parse_args(argv)
    islem = {
        "hazirla": hazirla,
        "dogrula": dogrula,
        "kart-dene": kart_dene,
        "gelecek-yedek": gelecek_yedek,
        "sihirbaz": sihirbaz,
        "gun-kapisi": gun_kapisi,
    }[args.komut]
    sonuc = islem(args)
    sys.stdout.write(json.dumps(sonuc, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
