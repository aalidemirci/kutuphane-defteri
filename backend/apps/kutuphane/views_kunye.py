"""Künye getirme uçları (U13, tasarım §8.5) — **öneri üretir, hiçbir alana yazmaz**.

Ayrı dosyadır (`views.py` DEĞİL): `apps/okul`'daki `views_mode.py` /
`views_calendar.py` düzeni. Uçların hiçbiri görevli kipi izin listesinde
değildir ve olmamalıdır (CLAUDE.md §2-4): dış sorgu açmak ve künye onaylamak
yönetici işidir.

Üç uç:

* `POST library/metadata/lookup/` — tek ISBN'in künyesi. **Kullanıcının
  eylemidir**: yalnız bu uç `servis.kullanici_istegi()` bağlamını açar, yani
  toplu içe aktarma yolu dış istek atamaz (§8.5-2, §5.10-19a).
* `GET  library/metadata/offline-export/` — künyesi eksik eserlerin ISBN
  listesi (xlsx). Ağa çıkmaz; ayar kapalıyken de çalışır, çünkü çevrimdışı yol
  tam da ağı olmayan masa içindir.
* `POST library/metadata/offline-preview/` — doldurulmuş dosyanın ön izlemesi.
  Yazma yoktur.

**Onay nerede?** Kullanıcı öneriyi görüp kabul ettiğinde eseri kendi
`library/works/` isteğiyle kaydeder. Bu uçların hiçbiri `Work` satırına
dokunmaz; "onaysız yazma yok" kuralı böylece koda gömülüdür, gözetime
bırakılmaz (§8.5-5). Dolu alanın sessizce üzerine yazılmaması da bu yüzden
mümkündür: yanıt her alanın **mevcut değerini** ve dolu olup olmadığını
bildirir, ekran farkı gösterir.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from django.http import FileResponse
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane.kunye import offline, servis
from apps.kutuphane.kunye.oneri import ALAN_ETIKETLERI, WORK_ALANLARI, KunyeOnerisi
from apps.kutuphane.models import Work
from apps.kutuphane.serializers import dosya_boyutunu_dogrula

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class KunyeKapaliYaniti(APIException):
    """409 `kunye_kapali` — ayar kapalıyken sorgu istenirse (§8.5-1).

    400 değil 409: gönderilen veri hatalı değildir, programın DURUMU uygun
    değildir. Ön yüz bu kodu görünce kullanıcıyı ayara yönlendirir.
    """

    status_code = status.HTTP_409_CONFLICT
    default_code = "kunye_kapali"
    default_detail = servis.ILETI_KAPALI


class KunyeIstegiSerializer(serializers.Serializer[dict[str, Any]]):
    """Sorgu gövdesi: ISBN + (isteğe bağlı) karşılaştırılacak eser."""

    isbn = serializers.CharField(
        max_length=40,
        error_messages={
            "blank": servis.ILETI_GECERSIZ_ISBN,
            "required": servis.ILETI_GECERSIZ_ISBN,
        },
    )
    work = serializers.PrimaryKeyRelatedField(
        queryset=Work.objects.all(),
        required=False,
        allow_null=True,
        default=None,
        error_messages={"does_not_exist": "Eser bulunamadı."},
    )
    force = serializers.BooleanField(required=False, default=False)


class CevrimdisiDosyaSerializer(serializers.Serializer[dict[str, Any]]):
    """Doldurulmuş çevrimdışı künye dosyası."""

    file = serializers.FileField(
        error_messages={"required": "Doldurduğunuz künye dosyasını seçin."}
    )

    def validate_file(self, value: Any) -> Any:
        """Tavan dosya BELLEĞE ALINMADAN uygulanır (gerekçe `dosya_boyutunu_dogrula`)."""
        return dosya_boyutunu_dogrula(value, tavan=offline.MAX_DOSYA_BAYT)


def _alan_satirlari(oneri: KunyeOnerisi | None, eser: Work | None) -> list[dict[str, Any]]:
    """Her alan için: önerilen değer, eserdeki mevcut değer, alan dolu mu.

    Dolu alan sessizce üzerine YAZILMAZ (§8.5-5): fark ekranda görünür ve
    kullanıcı alan alan karar verir.
    """
    if oneri is None:
        return []
    onerilen = oneri.alan_sozlugu()
    satirlar: list[dict[str, Any]] = []
    for ad in WORK_ALANLARI:
        deger = onerilen.get(ad)
        mevcut = getattr(eser, ad, None) if eser is not None else None
        satirlar.append(
            {
                "alan": ad,
                "etiket": ALAN_ETIKETLERI[ad],
                "deger": deger,
                "mevcut_deger": mevcut,
                "dolu": bool(mevcut not in (None, "")),
                "farkli": bool(deger not in (None, "")) and deger != mevcut,
            }
        )
    return satirlar


def _sonuc_govdesi(sonuc: servis.KunyeSonucu, eser: Work | None) -> dict[str, Any]:
    oneri = sonuc.oneri
    return {
        "isbn13": sonuc.isbn13,
        "bulundu": sonuc.bulundu,
        "kaynak": sonuc.kaynak,
        "kaynak_adi": sonuc.kaynak_adi,
        "kaynak_tarihi": sonuc.kaynak_tarihi.isoformat() if sonuc.kaynak_tarihi else None,
        "kaynak_etiketi": sonuc.kaynak_etiketi,
        "kayit_sayisi": sonuc.kayit_sayisi,
        "onbellekten": sonuc.onbellekten,
        "rozet": servis.ROZET if sonuc.bulundu else "",
        "ileti": sonuc.ileti,
        "uyarilar": list(oneri.uyarilar) if oneri is not None else [],
        "ek_bilgi": {
            "pages": oneri.pages if oneri is not None else None,
            "place": oneri.place if oneri is not None else "",
        },
        "alanlar": _alan_satirlari(oneri, eser),
    }


class MetadataLookupView(APIView):
    """`POST library/metadata/lookup/` — ISBN'den künye önerisi (tek istek)."""

    def post(self, request: Request) -> Response:
        gonderi = KunyeIstegiSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        eser: Work | None = veri.get("work")
        try:
            # Bağlamı AÇAN tek yer: dış istek yalnız kullanıcının bu eyleminden çıkar.
            with servis.kullanici_istegi():
                sonuc = servis.kunye_getir(veri["isbn"], force=bool(veri.get("force")))
        except servis.KunyeKapaliHatasi as exc:
            raise KunyeKapaliYaniti() from exc
        except servis.GecersizIsbnHatasi as exc:
            raise serializers.ValidationError({"isbn": str(exc)}) from exc
        return Response(_sonuc_govdesi(sonuc, eser))


class MetadataOfflineExportView(APIView):
    """`GET library/metadata/offline-export/` — künyesi eksik eserlerin ISBN listesi.

    Ağa ÇIKMAZ ve künye ayarından bağımsızdır: çevrimdışı yol tam da interneti
    olmayan masa içindir (§8.5).
    """

    def get(self, request: Request) -> FileResponse:
        return FileResponse(
            BytesIO(offline.build_export()),
            as_attachment=True,
            filename=offline.export_filename(),
            content_type=XLSX_CONTENT_TYPE,
        )


class MetadataOfflinePreviewView(APIView):
    """`POST library/metadata/offline-preview/` — doldurulmuş dosyanın ön izlemesi."""

    def post(self, request: Request) -> Response:
        gonderi = CevrimdisiDosyaSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        yuklenen = dict(gonderi.validated_data)["file"]
        try:
            onizleme = offline.onizleme(yuklenen.read())
        except offline.CevrimdisiDosyaHatasi as exc:
            raise serializers.ValidationError({"file": str(exc)}) from exc
        return Response(
            {
                "kaynak_adi": offline.KAYNAK_ADI,
                "kaynak_etiketi": onizleme.kaynak_etiketi,
                "rozet": servis.ROZET,
                "sayilar": onizleme.sayilar,
                "atlanan_sutunlar": list(onizleme.atlanan_sutunlar),
                "satirlar": [
                    {
                        "satir_no": satir.satir_no,
                        "isbn13": satir.isbn13,
                        "durum": satir.durum,
                        "work": satir.work_id,
                        "work_title": satir.work_title,
                        "uyarilar": list(satir.oneri.uyarilar),
                        "alanlar": _alan_satirlari(satir.oneri, satir.work),
                    }
                    for satir in onizleme.satirlar
                ],
            }
        )
