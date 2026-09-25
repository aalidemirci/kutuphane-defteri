"""Nüsha durumunun KOŞULLU geçişi — tek açık kayıt kuralının yarış güvencesi (§9-7, F7).

Bir nüsha aynı anda yalnız bir açık ödünçte YA DA açık teslimde olabilir (§9-7).
Aynı tablodaki ikinci açık kaydı kısmi teklik kısıtları keser
(`uq_loan_open_per_copy`, `uq_delivery_open_per_copy`); ama ödünç ile teslim iki
ayrı tablodadır ve tek bir DB kısıtıyla birbirini dışlayamaz. Ortak nokta nüshanın
durumudur: ödünç "Rafta"dan "Ödünçte"ye, teslim "Rafta"dan "Sınıf kitaplığında"ya
geçirir. Geçiş burada `UPDATE … WHERE status = <eski>` olarak yazılır ve
etkilenen satır sayısına bakılır: iki işlem aynı nüshayı aynı anda "Rafta"
görmüş olsa bile güncellemeyi yalnız biri yapar, öbürü 0 satır görür ve kendi
kaydını geri sarar. SQLite tek yazar + `transaction_mode=IMMEDIATE` ile işlemleri
zaten sıralar; bu güncelleme, ön denetim bayat bir okumaya dayansa da (ya da bir
gün yazma işlemi başka bir yoldan gelse de) kuralı DB düzeyinde tutar. Yarış
testi: `tests/test_teslim_tek_acik_kayit.py`.

`Copy.objects` yumuşak silinmiş nüshayı görmez: silinmiş nüsha hiçbir geçişi
kazanamaz.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.utils import timezone

from apps.kutuphane.models import Copy


def gecir(copy_pk: int, *, eski: str | Iterable[str], yeni: str) -> bool:
    """Nüsha `eski` durum(lar)dan birindeyse `yeni` duruma geçirir; geçtiyse True.

    Çağıran bir `transaction.atomic` bloğu içindedir ve False'ta kendi yazdığı
    kaydı geri saracak bir hata yükseltir.
    """
    eskiler = [eski] if isinstance(eski, str) else list(eski)
    guncellenen = Copy.objects.filter(pk=copy_pk, status__in=eskiler).update(
        status=yeni, updated_at=timezone.now()
    )
    return guncellenen == 1
