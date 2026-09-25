"""Dolaşım masası uçları — İNCE görünümler (tasarım §7.3 durum tablosu, §4.4, GA-7).

| Uç | Ad | Görevli kipi |
|---|---|---|
| `POST library/desk/member/` | `library-desk-member` | AÇIK — gövde `{card_no}`; `membership_id` 403 |
| `POST library/checkout/` | `library-checkout` | AÇIK — `override_*`, `cardless*`, `membership_id` 403 |
| `POST library/return/` | `library-return` | AÇIK — barkodla iade |
| `GET library/desk/copy-status/?barcode=` | `library-desk-copy-status` | AÇIK — nüsha durum sorgusu |
| `POST library/desk/card-unlock/` | `library-desk-card-unlock` | AÇIK — gövdede yönetici parolası (GA-7) |
| `GET library/desk/state/` | `library-desk-state` | AÇIK — kişisiz masa durumu (F9) |

Uç ve PARAMETRE kuralı ara katmandadır (`apps/okul/kip_izinleri.py`); görünüm
aynı kuralı bir kez daha söyler (savunma derinliği): gerekçeli istisna, kartsız
ödünç ve üyelik kaydıyla üye açma görevli kipinde `KipYetkisiz` (403
`kip_yetkisiz`) alır. Yanıtlar görevli kipinde daralır (`serializers_masa`);
kip ara katmanla aynı süreç içi nesneden (`KIP`) okunur, kip arada yöneticiden
görevliye inmişse yanıt daralmış döner (güvenli yön).

Okutma bir OLAYDIR: iade ve durum sorgusu her zaman 200 gövde döner (`result`,
`message`); masa ekranı iletiyi gösterir ve sıradakine geçer. Ödünç ver bir
EYLEMDİR: kural reddi 400 `DolasimReddi` (kararlı `code` — ekran "Bu kitap başka
bir üyede. Önce iade alınsın mı?" gibi akışları koda göre seçer), başarı 201.

Gövdeler YALNIZ UTF-8 JSON'dur (`parser_classes`): ara katmanın parametre denetçisi
gövdeyi JSON olarak okur; başka biçimdeki ya da başka karakter kümesindeki (ör.
`charset=utf-7`) gövde görünüme hiç ulaşmamalıdır — denetçi ile görünüm aynı
baytları farklı anahtarlar diye okuyabilirdi (`kip_izinleri.GovdeYasagi`).
Kart no URL'ye yazılmaz (POST gövdesi): adres günlüğe ve geçmişe düşebilir.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import IO, Any

from rest_framework import serializers, status
from rest_framework.exceptions import UnsupportedMediaType
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import selectors_dolasim
from apps.kutuphane.selectors_dolasim import CardLookup, CardLookupState
from apps.kutuphane.serializers_masa import (
    KartKilidiSerializer,
    MasaKodSerializer,
    MasaOduncSerializer,
    MasaUyeSerializer,
)
from apps.kutuphane.services import masa
from apps.kutuphane.services.circulation import DolasimReddi
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul.kip import KIP
from apps.okul.kip_izinleri import utf8_mi
from apps.okul.permissions import RequiresAdminPassword
from apps.okul.services import app_password

#: UTF-8 dışı karakter kümesiyle gelen gövdenin reddi (kullanıcı arayüzü bunu hiç üretmez).
UTF8_GEREKLI_MESSAGE = "İstek gövdesi yalnız UTF-8 JSON olabilir."


def _gorevli() -> bool:
    return KIP.gorevli_mi()


class Utf8JSONParser(JSONParser):
    """Yalnız UTF-8 JSON: başka `charset` 415 alır (ara katmanın denetçisiyle aynı kural)."""

    def parse(
        self,
        stream: IO[Any],
        media_type: str | None = None,
        parser_context: Mapping[str, Any] | None = None,
    ) -> Any:
        istek = (parser_context or {}).get("request")
        charset = getattr(istek, "content_params", {}).get("charset") if istek else None
        if not utf8_mi(charset):
            raise UnsupportedMediaType(media_type or "", detail=UTF8_GEREKLI_MESSAGE)
        return super().parse(stream, media_type, parser_context)


class _MasaGorunumu(APIView):
    """Masa uçlarının ortak ayarı: yalnız UTF-8 JSON gövde."""

    parser_classes = [Utf8JSONParser]


def _uyelik_kaydi(membership_id: int) -> Any:
    """Yönetici kipinde üyelik kaydıyla üye açma (kartsız ödünç — U12)."""
    require_admin_mode()
    uyelik = selectors_dolasim.get_membership(membership_id)
    if uyelik is None:
        raise DolasimReddi(masa.MEMBERSHIP_NOT_FOUND_MESSAGE, code=masa.RED_UYELIK_YOK)
    return uyelik


class MasaUyeView(_MasaGorunumu):
    """`POST library/desk/member/` — kartla üye çözme (§7.3 "Boş | kart").

    Yanıt `{state, message, member}` (her zaman 200): `FOUND` · `REVOKED` (iptal
    edilmiş kart) · `UNKNOWN` (tanınmayan kart) · `INVALID` (sağlama tutmuyor).
    Görevli kipinde `member` YALNIZ ad + kalan haktır; art arda geçersiz kart
    okutması 429 `kart_okutma_kilidi` verir (GA-7). `{membership_id}` yalnız
    yönetici kipindedir (kartsız ödünç için okul no ya da adla bulunan üye).
    """

    def post(self, request: Request) -> Response:
        gonderi = MasaUyeSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = gonderi.validated_data
        gorevli = _gorevli()
        if "membership_id" in veri:
            lookup = CardLookup(CardLookupState.FOUND, _uyelik_kaydi(int(veri["membership_id"])))
        else:
            lookup = masa.uye_coz(veri["card_no"], staff=gorevli)
        return Response(masa.kart_yaniti(lookup, staff=gorevli))


class MasaOduncView(_MasaGorunumu):
    """`POST library/checkout/` — ödünç ver (§7.3 "ÜYE | kitap"). OYS adı korunur.

    Gövde `{barcode, card_no}`; yönetici kipinde kartsız ödünç `{barcode,
    membership_id, cardless_reason}` ve gecikme engeli istisnası
    `{…, override_reason, override_note}`. Kurallar `services.circulation`'dadır.
    Ödünç kaydı üyeye bağlı kişi verisidir: `RequiresAdminPassword` (parola
    kurulmadan 409 `parola_gerekli`; `test_kisi_yazan_uclar.py`).
    """

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request) -> Response:
        gonderi = MasaOduncSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = gonderi.validated_data
        gorevli = _gorevli()
        uyelik = None
        if "membership_id" in veri:
            uyelik = _uyelik_kaydi(int(veri["membership_id"]))
        yanit = masa.odunc_ver(
            barcode=veri["barcode"],
            card_no=veri.get("card_no", ""),
            membership=uyelik,
            override_reason=str(veri.get("override_reason") or ""),
            override_note=str(veri.get("override_note") or ""),
            cardless_reason=str(veri.get("cardless_reason") or ""),
            staff=gorevli,
        )
        return Response(yanit, status=status.HTTP_201_CREATED)


class MasaIadeView(_MasaGorunumu):
    """`POST library/return/` — barkodla iade (§7.3 "Boş | kitap"; D9).

    Açık ödünçteyse iade alınır; değilse nüshanın durum iletisi döner ("Rafta —
    ödünç değil.", "Kayıp kaydında.", "Onarımda.", "Sınıf kitaplığında."). Her
    zaman 200: `result` = `returned` · `not_on_loan` · `rejected`. İade HİÇBİR
    durumda kilitlenmez. Ödünç kaydına yazar: `RequiresAdminPassword` (parola
    kurulmadan ödünç kaydı zaten olamaz; kapı savunma derinliğidir).
    """

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request) -> Response:
        gonderi = MasaKodSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        return Response(masa.iade_okut(gonderi.validated_data["barcode"], staff=_gorevli()))


class MasaNushaDurumuView(APIView):
    """`GET library/desk/copy-status/?barcode=` — nüsha durum sorgusu (yazma YOK)."""

    def get(self, request: Request) -> Response:
        sorgu = MasaKodSerializer(data=request.query_params)
        sorgu.is_valid(raise_exception=True)
        return Response(masa.durum_sorgula(sorgu.validated_data["barcode"], staff=_gorevli()))


class MasaDurumuView(APIView):
    """`GET library/desk/state/` — masanın ve görevli ekranının KİŞİSİZ durumu (F9).

    `{service_pause, stocktake_scan}`: sayım için hizmet arası sürüyor mu (masa şeridi
    açılışta çizilir — madde 26, 25.09.2026 kullanıcı kararı) ve okutması açık, süren bir
    sayım var mı (`{id, round}` ya da `null` — görevli ekranının "Sayım okutmasını aç"
    düğmesi; madde 24). Sayımın durumu, seçenekleri, ilerlemesi ve kurulu YOKTUR
    (sayım uçları yönetici işidir). Görevli kipinde de açıktır; kullanıcı eylemi değildir
    (ön yüz `X-KD-Etkinlik` göndermez).
    """

    def get(self, request: Request) -> Response:
        return Response(masa.masa_durumu())


class MasaKartKilidiView(_MasaGorunumu):
    """`POST library/desk/card-unlock/` — GA-7 kart okutma kilidini yönetici parolasıyla açar.

    Görevli kipinde açıktır: yönetici masaya gelir, parolasını yazar, görevli
    kipinden çıkmadan kart okutma sürer. Yanlış parola 400 "Parola hatalı."
    (kademeli gecikmeyle). Parola hiçbir yanıtta ve günlükte yankılanmaz.
    """

    def post(self, request: Request) -> Response:
        gonderi = KartKilidiSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        try:
            masa.kart_kilidini_ac(gonderi.validated_data["password"])
        except app_password.AppPasswordError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response({"message": masa.KART_KILIDI_ACILDI_MESSAGE})
