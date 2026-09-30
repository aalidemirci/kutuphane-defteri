"""GitHub Release tabanlı uygulama güncelleme denetimi ve güvenli kurucu indirme.

Yalnız sabit proje deposunun sürüm kayıtları okunur (kararlı kurulumda ``releases/latest``,
ön sürüm kurulumunda ya da hiç kararlı sürüm yokken son 10 yayının listesi). Windows kurucusu,
GitHub'ın ``sha256:...`` varlık özetiyle; eski Release kayıtlarında bu alan yoksa
aynı Release'teki ``SHA256SUMS.txt`` ile doğrulanmadan kullanıcıya verilmez.

**Hedef GitHub'da kalır** (kullanıcı kararı 27.09.2026; tasarım T11, F5 ekleri 15
kapandı): denetim `api.github.com`'a, kurulum dosyası indirmesi `github.com`'a
gider. `indir.okulapp.org` paketlerin İNDİRME alanıdır (paketleme.yml R2
yüklemesi); program o adrese istek ATMAZ. MEB ağında GitHub engellenebildiği için
ulaşılamazsa ileti bunu dürüstçe söyler ve yeni sürümün `indir.okulapp.org`'dan
elle denetlenebileceğini yazar (`ULASILAMADI_MESAJI` — yalnız metin).

Çevrimdışı ilke (tasarım §1, T11) korunur: denetim yalnız kullanıcının "Şimdi
denetle" düğmesiyle koşar; açılış zincirine, gün değişimi kapısına ya da arka plana
girmez (koruma testleri: `apps/okul/tests/test_dis_istek_kapilari.py`,
`desktop/tests/test_acilista_dis_istek.py`). Ağ yoksa Türkçe hata döner.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

GITHUB_REPOSITORY = os.environ.get("KD_UPDATE_REPOSITORY", "aalidemirci/kutuphane-defteri").strip()
GITHUB_API_VERSION = "2026-03-10"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
RELEASE_LIST_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases?per_page=10"
USER_AGENT = "Kutuphane-Defteri-Updater"
INSTALLER_PATTERN = re.compile(r"^kutuphane-defteri-.+-win64-setup\.exe$", re.IGNORECASE)
MAX_INSTALLER_BYTES = 250 * 1024 * 1024
CACHE_SECONDS = 15 * 60

#: Paketlerin elle indirildiği alan — program bu adrese istek ATMAZ, yalnız iletide anar.
INDIRME_ALANI = "indir.okulapp.org"
#: Denetim GitHub'a ulaşamadığında (kullanıcı kararı 27.09.2026, metin birebir).
ULASILAMADI_MESAJI = (
    "GitHub'a ulaşılamadı; okul ağında engellenmiş olabilir. Yeni sürümü "
    f"{INDIRME_ALANI}'dan elle denetleyebilirsiniz."
)

#: Sertifika doğrulanamadığında (F12 düzeltme turu): bu hata ağ engeli değildir; en sık
#: nedeni yanlış tarih/saat (sahada saat ileri alınmış deneme bilgisayarı) ya da güvenli
#: bağlantıları araya girerek denetleyen bir okul ağıdır. Program doğrulamayı GEVŞETMEZ.
SERTIFIKA_MESAJI = (
    "GitHub ile güvenli bağlantı doğrulanamadı. Bilgisayarın tarihi ve saati yanlışsa "
    "düzeltip yeniden deneyin; doğruysa okul ağı güvenli bağlantıları denetliyor olabilir. "
    f"Yeni sürümü {INDIRME_ALANI}'dan elle denetleyebilirsiniz."
)

_cache_lock = threading.Lock()
#: (zaman, ön sürüm kanalı mı, sürüm) — kararlı ve ön sürüm kanalı ayrı sorgulanır.
_cached_release: tuple[float, bool, ReleaseInfo] | None = None


class UpdateError(RuntimeError):
    """Kullanıcıya güvenle gösterilebilen güncelleme hatası."""


class ReleaseNotFoundError(UpdateError):
    """GitHub 404: kararlı sürüm hiç yayımlanmamış (ör. yalnız ön-sürüm var)."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int
    digest: str


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    name: str
    published_at: str
    html_url: str
    installer: ReleaseAsset | None
    checksums: ReleaseAsset | None


def _resource_root() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(str(bundle))
    return Path(__file__).resolve().parents[4]


def get_app_version() -> str:
    """Masaüstü paketi ve bağımsız Django geliştirme ortamında sürümü okur."""
    override = os.environ.get("KD_APP_VERSION")
    if override:
        return override.strip()
    try:
        return (_resource_root() / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


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


def version_key(value: str) -> tuple[tuple[int, ...], int, tuple[tuple[int, int | str], ...]]:
    """`desktop.version` ile aynı, ön sürümleri kararlı sürümden küçük sayan anahtar."""
    head, _, pre = value.strip().partition("-")
    numbers: list[int] = []
    for part in head.split("."):
        match = re.match(r"^\d+", part.strip())
        numbers.append(int(match.group(0)) if match else 0)
    numbers += [0] * (4 - len(numbers))
    return (tuple(numbers[:4]), 0 if pre else 1, _pre_key(pre))


def is_prerelease(value: str) -> bool:
    """Sürüm ön-sürüm eki taşıyor mu (`2026.10.0-beta.1` → True, `2026.10.0` → False)?"""
    return bool(value.strip().partition("-")[2])


def offered(latest: str, current: str) -> bool:
    """`latest` bu kuruluma ÖNERİLİR mi?

    Daha yeni olmalı; ayrıca KARARLI sürüm kullanan okula ön-sürüm (beta/rc)
    önerilmez (F12 kullanıcı kararı 3, 27.09.2026). `releases/latest` ucu
    ön-sürümleri zaten döndürmez; bu kural liste yolunun (`_highest_listed_release`
    — GitHub'da hiç kararlı sürüm yokken) ve indirme ucunun da aynı sözü tutmasını
    sağlar. Beta kullanıcısı hem sonraki betayı hem kararlı sürümü alır: çalışan
    sürüm ön sürümse `latest_release(prereleases=True)` doğrudan listeyi okur (ilk
    kararlı sürüm yayımlandıktan sonra da — F12 düzeltme turu).
    """
    if version_key(latest) <= version_key(current):
        return False
    return not is_prerelease(latest) or is_prerelease(current)


def update_directory() -> Path:
    """Kurucular için masaüstü uygulamasıyla aynı kullanıcı önbelleğini çözer."""
    override = os.environ.get("KD_APP_HOME")
    if override:
        return Path(override) / "cache" / "updates"
    if sys.platform.startswith("win"):
        home = Path(os.environ.get("USERPROFILE") or Path.home())
        local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
        return local / "KutuphaneDefteri" / "cache" / "updates"
    home = Path(os.environ.get("HOME") or Path.home())
    cache = Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache")
    return cache / "kutuphane-defteri" / "updates"


def _request(url: str) -> Request:
    return Request(  # noqa: S310 — çağıran yalnız HTTPS GitHub adreslerini kabul eder
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": USER_AGENT,
        },
    )


def _read_url(url: str, *, max_bytes: int) -> bytes:
    try:
        with urlopen(_request(url), timeout=20) as response:  # noqa: S310 — URL aşağıda sabitlenir
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UpdateError("Güncelleme dosyası beklenen boyut sınırını aşıyor.")
                chunks.append(chunk)
            return b"".join(chunks)
    except HTTPError as exc:
        if exc.code == 404:
            raise ReleaseNotFoundError("GitHub'da henüz yayımlanmış bir sürüm bulunmuyor.") from exc
        if exc.code in {403, 429}:
            # 403 GitHub'ın hız sınırı da olabilir, okul ağının engeli de: ikisi söylenir.
            raise UpdateError(
                "GitHub güncelleme denetimi geçici olarak sınırlandı ya da okul ağında "
                "engellendi. Daha sonra yeniden deneyin ya da yeni sürümü "
                f"{INDIRME_ALANI}'dan elle denetleyin."
            ) from exc
        raise UpdateError(f"GitHub güncelleme sunucusu HTTP {exc.code} hatası verdi.") from exc
    except URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise UpdateError(SERTIFIKA_MESAJI) from exc
        raise UpdateError(ULASILAMADI_MESAJI) from exc
    except ssl.SSLCertVerificationError as exc:
        raise UpdateError(SERTIFIKA_MESAJI) from exc
    except (TimeoutError, OSError) as exc:
        raise UpdateError(ULASILAMADI_MESAJI) from exc


def _safe_release_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "api.github.com"}:
        return ""
    return url


def _asset_from_json(value: Any) -> ReleaseAsset | None:
    if not isinstance(value, dict):
        return None
    name = str(value.get("name") or "").strip()
    # DD'den sapma (güvenlik sertleştirmesi): ad dosya yoluna çevrildiği için
    # yol bileşeni taşıyan varlık reddedilir — önbellek dizini dışına yazılamaz.
    if "/" in name or "\\" in name or ".." in name:
        return None
    url = _safe_release_url(value.get("browser_download_url"))
    if not name or not url:
        return None
    try:
        size = max(0, int(value.get("size") or 0))
    except (TypeError, ValueError):
        size = 0
    return ReleaseAsset(
        name=name,
        download_url=url,
        size=size,
        digest=str(value.get("digest") or "").strip().lower(),
    )


def _parse_release(payload: Any) -> ReleaseInfo:
    if not isinstance(payload, dict):
        raise UpdateError("GitHub sürüm yanıtı beklenen biçimde değil.")
    tag_name = str(payload.get("tag_name") or "").strip()
    version = tag_name.removeprefix("v").strip()
    if not version:
        raise UpdateError("GitHub sürüm kaydında sürüm etiketi bulunmuyor.")

    assets = [asset for raw in payload.get("assets") or [] if (asset := _asset_from_json(raw))]
    installer = next((a for a in assets if INSTALLER_PATTERN.fullmatch(a.name)), None)
    checksums = next((a for a in assets if a.name.upper() == "SHA256SUMS.TXT"), None)
    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        name=str(payload.get("name") or tag_name),
        published_at=str(payload.get("published_at") or ""),
        html_url=_safe_release_url(payload.get("html_url")),
        installer=installer,
        checksums=checksums,
    )


def _decode_payload(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        # Okul ağının engelleme sayfası (HTML) da buraya düşer.
        raise UpdateError(
            "GitHub sürüm yanıtı okunamadı; yanıt okul ağının engelleme sayfası olabilir. "
            f"Yeni sürümü {INDIRME_ALANI}'dan elle denetleyebilirsiniz."
        ) from exc


def _highest_listed_release() -> ReleaseInfo:
    """Sürüm LİSTESİNDEN (son 10 yayın, taslaklar hariç) en yüksek sürümü seçer.

    F9 yayın işi `-dev/-beta/-rc` etiketlerini `--prerelease` yayımlar; GitHub'ın
    `releases/latest` ucu ön-sürümleri DÖNDÜRMEZ. İki yerde koşar: (1) çalışan sürüm
    ön sürümse (beta kanalı — kararlı sürüm yayımlandıktan sonra da sonraki beta
    ancak buradan görülür) ve (2) kararlı kurulumda GitHub'da hiç kararlı sürüm
    yokken (404). Kararlı kuruluma ön sürüm önerilmemesini `offered` sağlar.
    """
    payload = _decode_payload(_read_url(RELEASE_LIST_URL, max_bytes=4 * 1024 * 1024))
    if not isinstance(payload, list):
        raise UpdateError("GitHub sürüm yanıtı beklenen biçimde değil.")
    releases: list[ReleaseInfo] = []
    for item in payload:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        try:
            releases.append(_parse_release(item))
        except UpdateError:
            continue
    if not releases:
        raise ReleaseNotFoundError("GitHub'da henüz yayımlanmış bir sürüm bulunmuyor.")
    return max(releases, key=lambda release: version_key(release.version))


def latest_release(*, force: bool = False, prereleases: bool = False) -> ReleaseInfo:
    """Yayımlanan son sürüm (15 dk önbellekli).

    `prereleases=False` (kararlı kurulum): `releases/latest`, yoksa liste. `True`
    (çalışan sürüm ön sürüm — beta kanalı): doğrudan liste, en yüksek sürüm; böylece
    ilk kararlı sürümden sonra da sonraki beta bulunur. İki kanal ayrı önbelleklenir.
    """
    global _cached_release

    now = time.monotonic()
    with _cache_lock:
        onbellek = _cached_release
        if (
            not force
            and onbellek is not None
            and onbellek[1] == prereleases
            and now - onbellek[0] < CACHE_SECONDS
        ):
            return onbellek[2]

    if prereleases:
        release = _highest_listed_release()
    else:
        try:
            raw = _read_url(LATEST_RELEASE_URL, max_bytes=2 * 1024 * 1024)
            release = _parse_release(_decode_payload(raw))
        except ReleaseNotFoundError:
            release = _highest_listed_release()
    with _cache_lock:
        _cached_release = (now, prereleases, release)
    return release


def installer_supported() -> bool:
    """Uygulama içi indirme yalnız Windows kurulum dosyasını (setup.exe) bilir.

    Pardus/Linux'ta aynı düğme Windows `setup.exe`'sini indirmeyi öneriyordu —
    çalıştırılamayan bir dosya. O platformda güncelleme paket (.deb / .tar.gz)
    olarak sürüm sayfasından alınır; arayüz `platform` alanına göre yönlendirir.
    """
    return sys.platform.startswith("win")


def update_status(*, force: bool = False, current_version: str | None = None) -> dict[str, Any]:
    current = current_version or get_app_version()
    release = latest_release(force=force, prereleases=is_prerelease(current))
    available = offered(release.version, current)
    downloadable = installer_supported() and release.installer is not None
    return {
        "current_version": current,
        "latest_version": release.version,
        "update_available": available,
        "release_name": release.name,
        "published_at": release.published_at,
        "release_url": release.html_url,
        "platform": "windows" if installer_supported() else "linux",
        "can_download": available and downloadable,
        "installer_name": release.installer.name if downloadable and release.installer else "",
        "installer_size": release.installer.size if downloadable and release.installer else 0,
    }


def _expected_digest(release: ReleaseInfo) -> str:
    installer = release.installer
    if installer is None:
        raise UpdateError("Bu sürümde Windows kurulum dosyası bulunmuyor.")
    if installer.digest.startswith("sha256:"):
        digest = installer.digest.removeprefix("sha256:")
        if re.fullmatch(r"[0-9a-f]{64}", digest):
            return digest
    if release.checksums is None:
        raise UpdateError("Kurulum dosyasının SHA-256 doğrulama özeti bulunmuyor.")
    checksum_text = _read_url(release.checksums.download_url, max_bytes=256 * 1024).decode(
        "utf-8", errors="replace"
    )
    for line in checksum_text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        digest, filename = parts
        if filename.lstrip("*") == installer.name and re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            return digest.lower()
    raise UpdateError("SHA256SUMS.txt içinde Windows kurulum dosyası bulunmuyor.")


def download_latest_installer(*, force: bool = False) -> Path:
    if not installer_supported():
        raise UpdateError(
            "Uygulama içi indirme yalnız Windows'ta çalışır. Pardus/Linux için yeni "
            "paketi (.deb ya da .tar.gz) sürüm sayfasından indirip kurun."
        )
    current = get_app_version()
    release = latest_release(force=force, prereleases=is_prerelease(current))
    if not offered(release.version, current):
        raise UpdateError("Uygulama zaten güncel; indirilecek daha yeni bir sürüm yok.")
    installer = release.installer
    if installer is None:
        raise UpdateError("Yeni sürümde Windows kurulum dosyası bulunmuyor.")
    if installer.size > MAX_INSTALLER_BYTES:
        raise UpdateError("Kurulum dosyası güvenli boyut sınırını aşıyor.")

    expected = _expected_digest(release)
    content = _read_url(installer.download_url, max_bytes=MAX_INSTALLER_BYTES)
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        raise UpdateError("İndirilen kurulum dosyasının SHA-256 doğrulaması başarısız.")

    update_dir = update_directory()
    update_dir.mkdir(parents=True, exist_ok=True)
    target = update_dir / installer.name
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(target)
    return target
