"""Kütüphane uygulama tanımı.

Katalog çekirdeği (F2): bölüm, eser, nüsha, edinim, komisyon kararı, bağış ön
kaydı, politika ve numara sayacı — OYS `apps/kutuphane`'den uyarlanarak
(tasarım §6.2, §12). Katalog Excel şablonu ve sütun sözlüğü F1'den gelir
(tasarım §8.1); içe aktarımın kendisi F3'tedir.

F6: üyelik, kart ve ödünç modelleri. Kişi kayıt defterlerine (açık yükümlülük,
"hiç üye olmuş mu", ayrılış, personel birleştirme) buradan kaydolunur
(`services.memberships.register_person_hooks`) ve bu sürecin başlangıcı
işaretlenir (beklenmedik kapanıştan sonra "son oturumdaki işlemler" listesinin
sınırı — T15). Teslim, ayıklama ve sayım modelleri kendi fazlarında (F7-F9)
eklenir.

F5: Ağ Kataloğu görünümlerinin (`kd_katalog_*`) yaşam döngüsü kancaları burada
bağlanır — göçten önce düşürülür, bütün göçler bitince yeniden kurulur
(`katalog_gorunumleri`, tasarım §5.3 UY-10). Süreç içi katalog uygulaması da
burada veriye bağlanır (`ag_katalogu`).
"""

from __future__ import annotations

from django.apps import AppConfig
from django.db.models.signals import post_migrate, pre_migrate


class KutuphaneConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.kutuphane"
    verbose_name = "Kütüphane"

    def ready(self) -> None:
        from apps.kutuphane import ag_katalogu, katalog_gorunumleri, selectors_dolasim
        from apps.kutuphane.services import memberships, populer
        from apps.okul import masaustu_kanca

        # F6: kişi kayıt defterleri (bağımlılık yönü kütüphane → okul; kayıt
        # fikirdeştir, `ready()` iki kez koşsa da kanca bir kez çağrılır).
        memberships.register_person_hooks()
        # T15: bu oturumun başlangıcı — "son oturumdaki işlemler" bundan öncekilerdir.
        selectors_dolasim.mark_process_start()

        # Süreç içi Ağ Kataloğu uygulaması veriye bağlanır (veritabanı yolu
        # istek anında okunur); dinleyiciyi masaüstü kolu açar (§4.1, T16).
        ag_katalogu.varsayilan_katalogu_kur()

        # Çok okunanlar yazıcısı gün değişimi kapısına kaydolur (T9, §5.3). Kayıt
        # `kd-gunluk` kurulmadan (`backend_islerini_ekle`) ÖNCE olmalıdır:
        # `prepare_django` ready()'yi masaüstü kapıyı kurmadan çağırır. Kapı
        # `False`'ı "bir saat sonra yeniden dene" diye okur (bakımda ya da hata).
        masaustu_kanca.gunluk_is_kaydet(populer.GUNLUK_IS_ADI, populer.kapi_isi)

        # `sender=self`: iki kanca da her `migrate`'te bu uygulama için BİR KEZ
        # çalışır. `pre_migrate` hiçbir göç koşmadan, `post_migrate` bütün
        # uygulamaların göçleri bittikten sonra gönderilir.
        pre_migrate.connect(
            katalog_gorunumleri.pre_migrate_gorunumleri_dusur,
            sender=self,
            dispatch_uid="kd_katalog_gorunumleri_dusur",
        )
        post_migrate.connect(
            katalog_gorunumleri.post_migrate_gorunumleri_kur,
            sender=self,
            dispatch_uid="kd_katalog_gorunumleri_kur",
        )
