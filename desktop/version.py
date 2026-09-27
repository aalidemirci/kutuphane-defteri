"""Uygulama sürümü + veri sürüm damgası (tasarım §4.2; F11: eski exe yeni DB'yi AÇMAZ).

**Karar — damga TABLO değil DOSYA:** veri dizinindeki `surum.json`.
Gerekçe: (1) veritabanı açılamadığında/bozukken bile okunabilir, yani sürüm
denetimi bütünlük denetiminden önce koşabilir; (2) yeni bir tablo eklemek için
migration gerekmez ve Django'nun şema karşılaştırmasına gölge düşürmez;
(3) yedekten geri dönüşte damga eksik/eski kalırsa program yine de açılır
(eksik damga engel sayılmaz) — kullanıcıyı kilitlemeyen tarafta hata yapar.

Damga her başarılı `migrate` sonrası yazılır. Damgadaki sürüm çalışan programdan
YENİYSE program açılmaz: eski sürüm, yeni şemayı tanımadığı için veriyi bozardı.

**İkinci hat (F11):** damga yoksa kapı açık kalırdı — ve geri yükleme damgayı
SİLER (yedeğin hangi sürümle alındığı bilinmez). Daha yeni bir sürümün yedeği eski
programa geri yüklenince veritabanının göç kaydı konuşur:
`ensure_no_unknown_migrations` programın tanımadığı uygulanmış göç varsa aynı
`SchemaTooNewError` (çıkış kodu 4) ile açılışı durdurur. Uçtan uca kanıt
`desktop/tests/test_eski_surum_kapisi.py`'dedir (gerçek süreç, gerçek göç).
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from desktop.errors import SchemaTooNewError
from desktop.paths import resource_root

ENV_APP_VERSION = "KD_APP_VERSION"
VERSION_FILE_NAME = "VERSION"
FALLBACK_VERSION = "0.0.0"

logger = logging.getLogger("kutuphane_defteri.version")

_LEADING_DIGITS = re.compile(r"^\d+")


@dataclass(frozen=True)
class VersionStamp:
    """Veriyi en son yazan program sürümünün damgası."""

    app_version: str
    written_at: str


def get_app_version(*, environ: Mapping[str, str] | None = None) -> str:
    """Çalışan programın sürümü — `KD_APP_VERSION` > paketlenmiş `VERSION` dosyası."""
    env = os.environ if environ is None else environ
    override = env.get(ENV_APP_VERSION)
    if override:
        return override.strip()
    version_file = resource_root() / VERSION_FILE_NAME
    try:
        text = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        logger.warning("Sürüm dosyası okunamadı; %s varsayılıyor.", FALLBACK_VERSION)
        return FALLBACK_VERSION
    return text or FALLBACK_VERSION


def _pre_key(pre: str) -> tuple[tuple[int, int | str], ...]:
    """Ön-sürüm ekinin DOĞAL sıralama anahtarı: "beta.10" > "beta.9".

    Ek eskiden DİZGE olarak karşılaştırılıyordu ('beta.10' < 'beta.9'): onuncu
    ön-sürümde beta.9 kullanıcısına güncelleme hiç önerilmez, sürüm listesinden
    "en yeni" diye beta.9 seçilirdi. Rakam öbekleri sayı, gerisi metin olarak
    karşılaştırılır; sayısal parça metinden küçüktür (semver önceliği). İki
    `version_key` kopyası (`desktop/version.py` ve `okul/services/updates.py`)
    AYNI kalmalıdır.
    """
    parts = re.findall(r"\d+|[^\d.]+", pre)
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower()) for part in parts)


def version_key(
    value: str,
) -> tuple[tuple[int, ...], int, tuple[tuple[int, int | str], ...]]:
    """Sürümü karşılaştırılabilir anahtara çevirir ("1.0.0-dev" < "1.0.0")."""
    head, _, pre = value.strip().partition("-")
    numbers: list[int] = []
    for part in head.split("."):
        match = _LEADING_DIGITS.match(part.strip())
        numbers.append(int(match.group(0)) if match else 0)
    numbers += [0] * (4 - len(numbers))
    # Ön-sürüm (-dev/-rc1) kesin sürümden ÖNCE gelir → 0, kesin sürüm → 1.
    return (tuple(numbers[:4]), 0 if pre else 1, _pre_key(pre))


def read_version_stamp(path: Path) -> VersionStamp | None:
    """Damgayı okur. Dosya yoksa veya bozuksa None (program kilitlenmez)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    app_version = str(raw.get("app_version") or "").strip()
    if not app_version:
        return None
    return VersionStamp(app_version=app_version, written_at=str(raw.get("written_at") or ""))


def write_version_stamp(path: Path, app_version: str) -> None:
    """Damgayı yazar (başarılı `migrate` sonrası çağrılır)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "app_version": app_version,
        "written_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_no_unknown_migrations(unknown: Sequence[str], app_version: str) -> None:
    """Veritabanında bu programın tanımadığı göç varsa açılışı durdurur (F11, ikinci hat).

    Damga (`surum.json`) yoksa `ensure_stamp_compatible` geçer — geri yükleme
    damgayı siler (`backup_restore.restore_database`), çünkü yedeğin hangi sürümle
    alındığı bilinmez. Daha yeni bir sürümle alınmış yedek eski programa geri
    yüklenirse kapı buradadır: veritabanının kendi göç kaydı, programın
    tanımadığı adımları gösterir (`django_bootstrap.unknown_applied_migrations`).
    Çıkış kodu ve başlık sürüm damgasıyla AYNIDIR (`SchemaTooNewError`, 4).

    Göç adları YALNIZ günlüğe (`uygulama.log`) yazılır; kullanıcı iletisi sade Türkçedir
    (27.09.2026 ana oturum kararı — sözlük §2 "iç kimlikler yüzeye çıkmaz" ve "Eski
    program, yeni veri" satırı: kullanıcı metninde şema, migration, göç geçmez). Tanı
    için BTR günlüğe bakar; iletinin ipucu günlük dosyasını anar. Günlüğe bütün adlar
    yazılır (ileti kutusu taşması kaygısı günlükte yoktur).
    """
    if not unknown:
        return
    logger.error(
        "Veritabanında bu sürümün (%s) tanımadığı %d göç var: %s",
        app_version,
        len(unknown),
        ", ".join(unknown),
    )
    raise SchemaTooNewError(
        "Bu veri, programın daha yeni bir sürümüyle güncellenmiş: veritabanında bu "
        f"sürümün ({app_version}) tanımadığı değişiklikler var.",
        hint=(
            "Veriyi bozmamak için program açılmadı. Bu bilgisayardaki programı güncel "
            "sürüme yükseltip yeniden açın. Bu durum daha yeni bir sürümle alınmış bir "
            "yedeği eski programa geri yükleyince de görülür. Tanınmayan değişikliklerin "
            "listesi programın günlük dosyasındadır (logs/uygulama.log)."
        ),
    )


def ensure_stamp_compatible(path: Path, app_version: str) -> None:
    """Veri, çalışan programdan yeni bir sürümle yazılmışsa açılışı durdurur."""
    stamp = read_version_stamp(path)
    if stamp is None:
        return
    if version_key(stamp.app_version) > version_key(app_version):
        raise SchemaTooNewError(
            "Bu veri, programın daha yeni bir sürümüyle "
            f"({stamp.app_version}) oluşturulmuş. Çalışan sürüm: {app_version}.",
            hint=(
                "Veriyi bozmamak için program açılmadı. Bu bilgisayardaki programı "
                "güncel sürüme yükseltip yeniden açın."
            ),
        )
