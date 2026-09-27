// Ayarlar → Saklama (F11 — tasarım §6.4). Süresi dolan kayıtların kişisiz listesi,
// "ne silinecek, ne kalacak" önizlemesi, yönetici parolasıyla GERİ DÖNÜŞSÜZ onay, son
// işlemin bilgisi, altı ay uyarısı ve bedel adımında bekleyen dosyaların yıllık listesi.
//
// Program süresi dolan kayıtları her gün tarar ama KENDİLİĞİNDEN hiçbir şey silmez: işlem
// yalnız buradaki onayla yapılır. Onaydan önce şifreli yedek alınır (14 gün kalır).
//
// Önizleme İKİ gruptur (sözlük §4.18 — anonimleştirme ≠ silme): "Silinecek" (kaydın kendisi
// kalkar: kişi kaydı, sona ermiş üyelik kaydı) ve "Kişiyle bağı koparılacak" (kayıt kalır,
// yalnız kişiyle bağı ve açıklamaları temizlenir). Önce yalnız SAYILAR görünür; adlar yalnız
// "Silinecek kişileri göster" ile ve yalnız yönetici kipinde (ekran ve uçlar görevli kipinde
// kapalıdır) gelir: kaydı silinecek kişiler ve kişi kaydı kalıp yalnız üyelik kaydı
// silinecekler ayrı tablolarda. Onaylanan önizleme parmak iziyle tetiğe gider: liste arada
// değiştiyse sunucu 409 döner ve hiçbir şey yazılmaz — önizleme tetikle birebirdir.
//
// F11 bağlantısı (yedek kolu): işlem USB bellekteki eski yedeklere dokunamaz. "Son İşlem"
// kartı, işlemden sonra şifreli yedek indirilmediyse bunu söyler ve Güvenlik'e yönlendirir
// (son indirme anı `backups/external/`'dan okunur; okunamazsa uyarı çizilmez).
//
// "İmha" sözcüğü burada kullanılmaz (yalnız imha tutanağı bağlamındadır).

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatDate, formatDateTime, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { GUVENLIK_ADRESI } from "../guvenlik/DisYedekKarti";
import { guvenlikApi } from "../guvenlik/api";
import type { DisYedekDurumu } from "../guvenlik/api";
import { KAYIP_HASAR_ADRESI, KAYIP_HASAR_BASLIGI } from "../kayip/KayipHasarPage";
import {
  ANONIM_KOPYA_IBARESI,
  LISTE_DEGISTI_KODU,
  YEDEK_GUN,
  anonimlestirmeSatirlari,
  beklemeSuresi,
  saklamaApi,
  silmeSatirlari,
} from "./api";
import type { BedelHatirlatmasi, SaklamaDurumu, SilinecekKisi, SonTetik } from "./api";

/** KVKK md. 4/2-d — docs/mevzuat/6698-kvkk.md ile BİREBİR (backend `KVKK_4_2_D`, test sınar). */
export const KVKK_4_2_D =
  "İlgili mevzuatta öngörülen veya işlendikleri amaç için gerekli olan süre kadar muhafaza edilme.";

export const TANITIM_METNI =
  "Kişisel veriler işlendikleri amaç için gerekli süre kadar saklanır. Program süresi dolan kayıtları her gün tarar ama kendiliğinden hiçbir şey silmez: silme ve kişiyle bağı koparma yalnız sizin onayınızla, bu ekrandan yapılır. İşlem geri alınamaz; hemen öncesinde şifreli yedek alınır.";

/** Önizlemenin iki grubunun başlıkları (sözlük §4.18). */
export const SILINECEK_BASLIGI = "Silinecek";
export const BAG_BASLIGI = "Kişiyle bağı koparılacak (kayıt kalır)";

/**
 * "Ne Kalır" kartının maddeleri — kılavuzun "Ne kalır" listesi aynı sırayı izler (sözlük
 * §4.18; `KilavuzPage.test.tsx` karşılaştırır). F11 düzeltme turu: bağı koparılan kayıt
 * "kişisiz" diye sunulmaz — belge no ya da dosya numarası arşivdeki asılla eşleşebilir
 * (KVKK 3/1-b "başka verilerle eşleştirilerek dahi").
 */
export const KALANLAR = [
  "Ödünç, kayıp/hasar ve teslim kayıtları kişiyle bağı koparılmış olarak kalır: sayım, istatistik ve yıl sonu raporu için. Belge no ya da dosya numarası okul arşivindeki ıslak imzalı asılla eşleşebilir; asılların saklanması arşiv kurallarına tabidir.",
  "Verilmiş kart numaraları hiçbir zaman yeniden verilmez; silinen üyeliğin kartı okutulursa “iptal edilmiş kart” denir.",
  "Resmî belgelerin ıslak imzalı asılları okul arşivindedir. Program yalnız belgenin kişisiz izini tutar; anonimleştirilmiş kayıttan yeniden basılan belgenin başında “" +
    ANONIM_KOPYA_IBARESI +
    "” yazar.",
  "Çok okunanların kapanmış dönemleri ve sonlandırılmış yıl sonu raporu değişmez.",
  "Bedeli belirlenmiş ya da teslim alınmış ama kapanmamış kayıp/hasar dosyası silinmez; aşağıdaki yıllık listede kalır.",
];

/** İşlemden sonra şifreli yedek indirilmediyse "Son İşlem" kartındaki uyarı. */
export const DIS_YEDEK_UYARISI =
  "Bu işlemden sonra şifreli yedek indirilmedi. USB bellekteki eski yedekler silinen ve kişiyle bağı koparılan kayıtları taşımayı sürdürür: yeni şifreli yedeği indirip USB belleğe alın, eskilerini okul müdürlüğünün kararıyla silin.";

export function altiAyUyarisi(bekleme: string | null, sonGun: string | null, ay: number): string {
  return `Onay bekleme süresi (${beklemeSuresi(ay)}) doldu: ${formatDate(bekleme)} tarihinden beri onay bekleyen kayıtlar var, en geç ${formatDate(sonGun)} tarihinde onaylanmalıydı. Kişisel veriler gereğinden uzun saklanıyor; listeyi gözden geçirip onaylayın.`;
}

/** Son işlemden sonra şifreli yedek indirildi mi? (Son indirme bilinmiyorsa hayır.) */
export function islemdenSonraYedekVar(son: SonTetik, disYedek: DisYedekDurumu): boolean {
  if (!disYedek.last_download) return false;
  return Date.parse(disYedek.last_download) >= Date.parse(son.ran_at);
}

function Bolum({
  baslik,
  simge,
  children,
}: {
  baslik: string;
  simge: string;
  children: ReactNode;
}) {
  return (
    <Card className="p-6">
      <div className="mb-3 flex items-center gap-3">
        <Icon name={simge} className="text-primary" />
        <h2 className="text-title-large text-on-surface">{baslik}</h2>
      </div>
      <div className="space-y-3 text-body-medium text-on-surface">{children}</div>
    </Card>
  );
}

/** Önizlemenin bir grubu: başlık + kişisiz satırlar (boşsa çizilmez). */
function Grup({ baslik, satirlar }: { baslik: string; satirlar: string[] }) {
  if (satirlar.length === 0) return null;
  return (
    <div>
      <h3 className="text-title-small text-on-surface">{baslik}</h3>
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {satirlar.map((metin) => (
          <li key={metin}>{metin}</li>
        ))}
      </ul>
    </div>
  );
}

function KisiTablosu({
  baslik,
  kisiler,
  tarihBasligi,
  tarih,
}: {
  baslik: string;
  kisiler: SilinecekKisi[];
  tarihBasligi: string;
  tarih: (k: SilinecekKisi) => string | null;
}) {
  if (kisiler.length === 0) return null;
  return (
    <table className="w-full text-body-medium">
      <caption className="pb-1 text-left text-title-small text-on-surface">{baslik}</caption>
      <thead>
        <tr className="text-left text-label-large text-on-surface-variant">
          {/* Sözlük §4.18: ad tablolarının sütunları "Ad soyad" · "Sınıf / üye türü" —
              program personelin görevini ya da unvanını tutmaz (V2-01). */}
          <th scope="col" className="py-1 pr-3">
            Ad soyad
          </th>
          <th scope="col" className="py-1 pr-3">
            Sınıf / üye türü
          </th>
          <th scope="col" className="py-1">
            {tarihBasligi}
          </th>
        </tr>
      </thead>
      <tbody>
        {kisiler.map((k) => (
          <tr
            key={`${k.scope}-${k.kind}-${k.person_id}`}
            className="border-t border-outline-variant"
          >
            <td className="py-1 pr-3">{k.full_name}</td>
            <td className="py-1 pr-3">{k.person_label || "—"}</td>
            <td className="py-1">{formatDate(tarih(k))}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function KisiListesi({ kisiler }: { kisiler: SilinecekKisi[] }) {
  if (kisiler.length === 0) {
    return <p className="text-body-medium text-on-surface-variant">Silinecek kişi kaydı yok.</p>;
  }
  return (
    <div className="space-y-4">
      <KisiTablosu
        baslik="Kaydı silinecek kişiler"
        kisiler={kisiler.filter((k) => k.scope === "person")}
        tarihBasligi="Ayrılış"
        tarih={(k) => k.left_at}
      />
      <KisiTablosu
        baslik="Yalnız üyelik kaydı silinecek kişiler (kişi kaydı kalır)"
        kisiler={kisiler.filter((k) => k.scope === "membership")}
        tarihBasligi="Üyeliğin sonu"
        tarih={(k) => k.terminated_at}
      />
    </div>
  );
}

function BedelListesi({ satirlar }: { satirlar: BedelHatirlatmasi[] }) {
  if (satirlar.length === 0) {
    return (
      <p className="text-body-medium text-on-surface-variant">
        Bir yıldan uzun süredir bedel adımında bekleyen dosya yok.
      </p>
    );
  }
  return (
    <table className="w-full text-body-medium">
      <caption className="sr-only">Bedel adımında bekleyen dosyalar</caption>
      <thead>
        <tr className="text-left text-label-large text-on-surface-variant">
          <th scope="col" className="py-1 pr-3">
            Barkod
          </th>
          <th scope="col" className="py-1 pr-3">
            Kaynak adı
          </th>
          <th scope="col" className="py-1 pr-3">
            Durum
          </th>
          <th scope="col" className="py-1">
            Bekliyor
          </th>
        </tr>
      </thead>
      <tbody>
        {satirlar.map((s) => (
          <tr key={s.case_id} className="border-t border-outline-variant">
            <td className="py-1 pr-3 font-mono">{s.barcode}</td>
            <td className="py-1 pr-3">{s.title}</td>
            <td className="py-1 pr-3">
              {s.case_type} · {s.resolution} ({formatDate(s.step_date)})
            </td>
            <td className="py-1">{formatNumber(s.years_waiting)} yıldır</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function SaklamaPaneli() {
  const snackbar = useSnackbar();
  const [durum, setDurum] = useState<SaklamaDurumu | null>(null);
  const [bedel, setBedel] = useState<BedelHatirlatmasi[]>([]);
  const [disYedek, setDisYedek] = useState<DisYedekDurumu | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [kisiler, setKisiler] = useState<SilinecekKisi[] | null>(null);
  const [acik, setAcik] = useState(false);
  const [parola, setParola] = useState("");
  const [anladim, setAnladim] = useState(false);
  const [onayHatasi, setOnayHatasi] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);
  const parolaAlani = useRef<HTMLInputElement>(null);

  const yukle = useCallback(() => {
    Promise.all([saklamaApi.durum(), saklamaApi.bedelListesi()])
      .then(([d, b]) => {
        // Liste yeniden okununca eski adlar ekranda kalmaz (önizleme değişmiş olabilir).
        setKisiler(null);
        setDurum(d);
        setBedel(b);
        setHata(null);
      })
      .catch((e: unknown) => setHata(hataOku(e, "Saklama durumu yüklenemedi.")));
    guvenlikApi
      .disYedek()
      .then(setDisYedek)
      .catch(() => setDisYedek(null));
  }, []);
  useEffect(yukle, [yukle]);

  function kapat() {
    setAcik(false);
    setParola("");
    setAnladim(false);
    setOnayHatasi(null);
  }

  async function kisileriGoster() {
    if (kisiler !== null) {
      setKisiler(null);
      return;
    }
    try {
      setKisiler(await saklamaApi.kisiler());
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Kişi listesi yüklenemedi.");
    }
  }

  async function uygula(e: FormEvent) {
    e.preventDefault();
    if (durum === null) return;
    setOnayHatasi(null);
    setCalisiyor(true);
    try {
      const sonuc = await saklamaApi.uygula(parola, durum.digest);
      kapat();
      snackbar.success(
        `Saklama işlemi uygulandı: ${formatNumber(sonuc.summary.total)} kayıt. İşlemden hemen önce alınan yedek: ${sonuc.backup_name}. Yeni şifreli yedeği indirip USB belleğe alın.`,
      );
      yukle();
    } catch (err) {
      if (err instanceof ApiError && err.code === LISTE_DEGISTI_KODU) {
        kapat();
        snackbar.error(err.message);
        yukle();
      } else {
        setOnayHatasi(err instanceof ApiError ? err.message : "Saklama işlemi uygulanamadı.");
      }
    } finally {
      setCalisiyor(false);
    }
  }

  if (hata) return <ErrorBand hata={hata} />;
  if (durum === null) return <SkeletonList rows={4} />;

  const silinecek = silmeSatirlari(durum.candidates);
  const baglar = anonimlestirmeSatirlari(durum.candidates);
  const adayVar = silinecek.length + baglar.length > 0;
  const adVar =
    durum.candidates.students + durum.candidates.personnel + durum.candidates.memberships > 0;
  const s = durum.policy;
  const yedekUyarisi =
    durum.last_run !== null &&
    disYedek !== null &&
    !islemdenSonraYedekVar(durum.last_run, disYedek);

  return (
    <div className="space-y-6">
      {durum.overdue && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
        >
          <Icon name="warning" size="lg" />
          <span>
            {altiAyUyarisi(durum.pending_since, durum.approval_deadline, durum.max_wait_months)}
          </span>
        </div>
      )}

      <Bolum baslik="Saklama ve Anonimleştirme" simge="auto_delete">
        <p>{TANITIM_METNI}</p>
        <p className="text-on-surface-variant">
          Kişisel Verilerin Korunması Kanunu md. 4/2-d: “{KVKK_4_2_D}” Süreler Ayarlar → Kütüphane
          Politikası → Vitrin ve Saklama&apos;dadır: okuldan ayrılan kişinin kaydı{" "}
          {s.left_person_years} yıl, sona eren üyelik {s.after_termination_years} yıl, iade edilmiş
          ödünç ders yılı sonundan {s.returned_loans_years} yıl, kapanmış kayıp/hasar dosyası{" "}
          {s.closed_cases_years} yıl, öğretmene teslim geri alınmasından {s.closed_deliveries_years}{" "}
          yıl sonra.
        </p>
      </Bolum>

      <Bolum baslik="Süresi Dolan Kayıtlar" simge="pending_actions">
        {!adayVar ? (
          <p className="text-on-surface-variant">Süresi dolmuş kayıt yok.</p>
        ) : (
          <>
            <Grup baslik={SILINECEK_BASLIGI} satirlar={silinecek} />
            <Grup baslik={BAG_BASLIGI} satirlar={baglar} />
            <p className="text-body-small text-on-surface-variant">
              Onay bekleme başlangıcı {formatDate(durum.pending_since)}; en geç{" "}
              {formatDate(durum.approval_deadline)} tarihine kadar onaylayın (
              {beklemeSuresi(durum.max_wait_months)}).
            </p>
          </>
        )}
        {durum.candidates.persons_held > 0 && (
          <p className="text-body-small text-on-surface-variant">
            Ayrılışının üzerinden süre geçtiği hâlde {formatNumber(durum.candidates.persons_held)}{" "}
            kişinin kaydı silinmeyecek: kütüphaneyle açık işi (iade edilmemiş kaynak, geri alınmamış
            teslim, kapanmamış kayıp/hasar dosyası) ya da süresi henüz dolmamış bir kaydı var.
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {adVar && (
            <Button
              variant="tonal"
              icon={kisiler === null ? "group" : "visibility_off"}
              onClick={() => void kisileriGoster()}
            >
              {kisiler === null ? "Silinecek kişileri göster" : "Adları gizle"}
            </Button>
          )}
          {adayVar && (
            <Button icon="auto_delete" onClick={() => setAcik(true)}>
              Onayla ve uygula
            </Button>
          )}
        </div>
        {kisiler !== null && <KisiListesi kisiler={kisiler} />}
      </Bolum>

      <Bolum baslik="Ne Kalır" simge="inventory_2">
        <ul className="list-disc space-y-1 pl-5">
          {KALANLAR.map((metin) => (
            <li key={metin}>{metin}</li>
          ))}
        </ul>
        {/* 27.09.2026 kullanıcı kararı: işlem, geri yüklemenin kenara aldığı önceki veritabanı
            dosyalarından YEDEK_GUN günden eskilerini siler (ölçü adındaki geri yükleme tarihi);
            yenileri dönüş yolu olarak kalır, elle silme önerisi yalnız onlar içindir. */}
        <p className="text-body-small text-on-surface-variant">
          Yedeklerde kalan: günlük yedekler ve işlemden hemen önce alınan yedek {YEDEK_GUN} gün
          kalır (şu an {formatNumber(durum.residue.pre_anonim)} işlem öncesi yedek). İşlem,
          kendinden önce alınmış güncelleme öncesi yedekleri (şu an{" "}
          {formatNumber(durum.residue.pre_migrate)}) ve geri yüklemeden kalan önceki veritabanı
          dosyalarından {YEDEK_GUN} günden eski olanları siler (şu an{" "}
          {formatNumber(durum.residue.old_databases)} önceki veritabanı;{" "}
          {formatNumber(durum.residue.old_databases_expired)} tanesi {YEDEK_GUN} günden eski). Daha
          yenileri yakın tarihli bir geri yüklemeden dönüş için kalır: artık gerekmiyorlarsa okul
          müdürlüğünün kararıyla siz silin. İndirdiğiniz yedekler programın dışındadır; kılavuzdaki
          “Saklama ve Anonimleştirme” bölümüne bakın.
        </p>
      </Bolum>

      <Bolum baslik="Bedel Bekleyen Dosyalar" simge="request_quote">
        <p className="text-on-surface-variant">
          “Bedel belirlendi” ya da “Bedel teslim alındı” adımında bir yıldan uzun süredir bekleyen
          dosyalar. Saklama işlemi bunlara dokunmaz; dosyayı{" "}
          <Link to={KAYIP_HASAR_ADRESI} className="text-primary underline underline-offset-2">
            {KAYIP_HASAR_BASLIGI}
          </Link>{" "}
          ekranından kapatın.
        </p>
        <BedelListesi satirlar={bedel} />
      </Bolum>

      <Bolum baslik="Son İşlem" simge="history">
        {durum.last_run === null ? (
          <p className="text-on-surface-variant">Saklama işlemi henüz uygulanmadı.</p>
        ) : (
          <>
            <p>
              {formatDateTime(durum.last_run.ran_at)} · {formatNumber(durum.last_run.summary.total)}{" "}
              kayıt · işlem öncesi yedek{" "}
              <span className="font-mono">{durum.last_run.backup_name}</span>
            </p>
            <p className="text-body-small text-on-surface-variant">
              Silinen güncelleme öncesi yedek: {formatNumber(durum.last_run.pre_migrate_removed)}.
              Silinen önceki veritabanı: {formatNumber(durum.last_run.old_db_removed)}.
            </p>
          </>
        )}
        {yedekUyarisi && (
          <div className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
            <Icon name="save" />
            <div className="space-y-1">
              <p>{DIS_YEDEK_UYARISI}</p>
              <Link
                to={GUVENLIK_ADRESI}
                className="inline-flex text-label-large text-primary underline underline-offset-2"
              >
                Ayarlar → Güvenlik&apos;i aç
              </Link>
            </div>
          </div>
        )}
        {durum.last_scan_on && (
          <p className="text-body-small text-on-surface-variant">
            Son tarama: {formatDate(durum.last_scan_on)}.
          </p>
        )}
      </Bolum>

      <Dialog
        open={acik}
        onClose={kapat}
        title="Saklama işlemi uygulansın mı?"
        initialFocusRef={parolaAlani}
      >
        <form onSubmit={uygula} className="flex flex-col gap-4">
          <div className="space-y-3 text-body-medium text-on-surface">
            <Grup baslik={SILINECEK_BASLIGI} satirlar={silinecek} />
            <Grup baslik={BAG_BASLIGI} satirlar={baglar} />
          </div>
          <p className="text-body-medium text-on-surface-variant">
            İşlem geri alınamaz. Hemen öncesinde şifreli yedek alınır ve {YEDEK_GUN} gün saklanır;
            kendinden önce alınmış güncelleme öncesi yedekler ve geri yüklemeden kalan önceki
            veritabanı dosyalarından {YEDEK_GUN} günden eski olanlar silinir.
          </p>
          <TextField
            ref={parolaAlani}
            label="Yönetici parolası"
            type="password"
            value={parola}
            onChange={(e) => setParola(e.target.value)}
            autoComplete="current-password"
            error={onayHatasi ?? undefined}
            required
          />
          <label className="flex items-center gap-2 text-body-medium text-on-surface">
            <input
              type="checkbox"
              checked={anladim}
              onChange={(e) => setAnladim(e.target.checked)}
            />
            <span>Bu işlemin geri alınamayacağını anladım</span>
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="text" type="button" onClick={kapat}>
              Vazgeç
            </Button>
            <Button type="submit" icon="auto_delete" disabled={calisiyor || !parola || !anladim}>
              {calisiyor ? "Uygulanıyor…" : "Uygula"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
