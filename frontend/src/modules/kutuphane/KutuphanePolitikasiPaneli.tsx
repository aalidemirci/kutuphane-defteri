// Ayarlar → Kütüphane Politikası. Ödünç sınırları, yıl sonu tarihleri, iade
// tarihi kaydırması ve saklama süreleri tek satırda tutulur.
//
// ÖDÜNÇ SÜRESİ AYAR DEĞİLDİR (Md. 18: "Bir kitabı ödünç alma süresi on beş
// gündür"). Panel bunu değiştirilemez bir bilgi satırı olarak gösterir; değer
// sunucudan gelir ki "15 gün" arayüze gömülmesin.
//
// Kaydetme KISMİDİR: yalnız buradaki alanlar gönderilir, politikanın öbür
// alanlarına dokunulmaz (sunucu sözleşmesi).
//
// KÜNYE GETİRME (U13, tasarım §8.5) bu panelin son bölümüdür ve VARSAYILAN
// OLARAK KAPALIDIR: ana bayrak kapalıyken program ISBN sorgusu için dışarıya
// hiçbir istek atmaz (sunucu 409 `kunye_kapali` döner). Kaynak seçimleri ana
// bayrak kapalıyken etkisizdir; panel onları o durumda kilitler ki kullanıcı
// "işaretledim ama çalışmıyor" durumuna düşmesin.

import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { kutuphaneApi } from "./api";
import type { LibraryPolicy, LibraryPolicyBody } from "./api";

/**
 * Sayı alanını gövdeye çevirir. Alan BOŞSA ya da sayı değilse kayıtlı değer
 * gönderilir: sınırların hepsi zorunludur ve boş bir kutu yüzünden 0 yazmak ya
 * da sunucudan alan hatası almak kullanıcıya bir şey anlatmaz — kayıttan sonra
 * form sunucunun döndürdüğü değerle yeniden dolar, kutu eski sayıyı gösterir.
 */
function sayi(deger: string, yedek: number): number {
  const temiz = deger.trim();
  if (!temiz) return yedek;
  const n = Number(temiz);
  return Number.isFinite(n) ? n : yedek;
}

function Bolum({ baslik, children }: { baslik: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-title-medium text-on-surface">{baslik}</h3>
      {children}
    </section>
  );
}

function Onay({
  label,
  checked,
  onChange,
  helperText,
  disabled = false,
}: {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  helperText?: string;
  disabled?: boolean;
}) {
  return (
    <div className={disabled ? "opacity-60" : undefined}>
      <label className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
          className="size-5 shrink-0 accent-primary"
        />
        {label}
      </label>
      {helperText && <p className="text-body-small text-on-surface-variant">{helperText}</p>}
    </div>
  );
}

export default function KutuphanePolitikasiPaneli() {
  const [politika, setPolitika] = useState<LibraryPolicy | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const { errors, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();

  // Form alanları metin tutulur (boş alan "0" yazmasın); kaydederken sayıya çevrilir.
  const [ogrenci, setOgrenci] = useState("");
  const [ogretmen, setOgretmen] = useState("");
  const [personel, setPersonel] = useState("");
  const [personeleOdunc, setPersoneleOdunc] = useState(false);
  const [kararTarihi, setKararTarihi] = useState("");
  const [kararSayisi, setKararSayisi] = useState("");
  const [gecikmedeEngelle, setGecikmedeEngelle] = useState(true);
  const [kapaliGunKaydir, setKapaliGunKaydir] = useState(true);
  const [sonOdunc, setSonOdunc] = useState("");
  const [sonOduncMezun, setSonOduncMezun] = useState("");
  const [enAzUye, setEnAzUye] = useState("");
  const [saklamaUyelik, setSaklamaUyelik] = useState("");
  const [saklamaOdunc, setSaklamaOdunc] = useState("");
  const [saklamaDosya, setSaklamaDosya] = useState("");
  const [saklamaTeslim, setSaklamaTeslim] = useState("");
  const [kunyeAcik, setKunyeAcik] = useState(false);
  const [kunyeBakanlik, setKunyeBakanlik] = useState(true);
  const [kunyeOpenLibrary, setKunyeOpenLibrary] = useState(true);

  const doldur = (p: LibraryPolicy) => {
    setPolitika(p);
    setOgrenci(String(p.max_loans_student));
    setOgretmen(String(p.max_loans_teacher));
    setPersonel(String(p.max_loans_staff));
    setPersoneleOdunc(p.staff_loans_enabled);
    setKararTarihi(p.staff_loans_decision_date ?? "");
    setKararSayisi(p.staff_loans_decision_no);
    setGecikmedeEngelle(p.block_loan_if_overdue);
    setKapaliGunKaydir(p.shift_due_date_on_school_break);
    setSonOdunc(p.last_loan_date ?? "");
    setSonOduncMezun(p.last_loan_date_graduating ?? "");
    setEnAzUye(String(p.popular_min_members));
    setSaklamaUyelik(String(p.retention_years_after_termination));
    setSaklamaOdunc(String(p.retention_years_returned_loans));
    setSaklamaDosya(String(p.retention_years_closed_cases));
    setSaklamaTeslim(String(p.retention_years_closed_deliveries));
    setKunyeAcik(p.metadata_lookup_enabled);
    setKunyeBakanlik(p.metadata_lookup_ministry);
    setKunyeOpenLibrary(p.metadata_lookup_openlibrary);
  };

  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .getPolicy()
      .then((p) => {
        if (!iptal) {
          doldur(p);
          setHata(null);
        }
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Kütüphane politikası yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, []);

  const kaydet = async () => {
    if (politika === null) return;
    clearErrors();
    setHata(null);
    const govde: LibraryPolicyBody = {
      max_loans_student: sayi(ogrenci, politika.max_loans_student),
      max_loans_teacher: sayi(ogretmen, politika.max_loans_teacher),
      max_loans_staff: sayi(personel, politika.max_loans_staff),
      staff_loans_enabled: personeleOdunc,
      staff_loans_decision_date: kararTarihi || null,
      staff_loans_decision_no: kararSayisi.trim(),
      block_loan_if_overdue: gecikmedeEngelle,
      shift_due_date_on_school_break: kapaliGunKaydir,
      last_loan_date: sonOdunc || null,
      last_loan_date_graduating: sonOduncMezun || null,
      popular_min_members: sayi(enAzUye, politika.popular_min_members),
      retention_years_after_termination: sayi(
        saklamaUyelik,
        politika.retention_years_after_termination,
      ),
      retention_years_returned_loans: sayi(saklamaOdunc, politika.retention_years_returned_loans),
      retention_years_closed_cases: sayi(saklamaDosya, politika.retention_years_closed_cases),
      retention_years_closed_deliveries: sayi(
        saklamaTeslim,
        politika.retention_years_closed_deliveries,
      ),
      metadata_lookup_enabled: kunyeAcik,
      metadata_lookup_ministry: kunyeBakanlik,
      metadata_lookup_openlibrary: kunyeOpenLibrary,
    };
    setBusy(true);
    try {
      doldur(await kutuphaneApi.updatePolicy(govde));
      snackbar.success("Kütüphane politikası kaydedildi.");
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Kütüphane politikası kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  };

  if (yukleniyor) return <SkeletonList rows={5} />;
  if (politika === null) return <ErrorBand hata={hata ?? "Kütüphane politikası yüklenemedi."} />;

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      {hata && <ErrorBand hata={hata} />}

      <Card elevation={0} className="space-y-6 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <Bolum baslik="Ödünç Sınırları">
          <p className="text-body-medium text-on-surface-variant">
            Ödünç süresi {formatNumber(politika.loan_period_days)} gündür ve değiştirilemez:
            Yönetmelik süreyi bu şekilde belirler. Sayı sınırları okulun takdirindedir, üst
            değerlerin üstüne çıkılamaz.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <TextField
              label="Öğrenci"
              inputMode="numeric"
              value={ogrenci}
              onChange={(e) => setOgrenci(e.target.value)}
              error={errors.max_loans_student}
              helperText="En çok 3."
            />
            <TextField
              label="Öğretmen"
              inputMode="numeric"
              value={ogretmen}
              onChange={(e) => setOgretmen(e.target.value)}
              error={errors.max_loans_teacher}
              helperText="En çok 5."
            />
            <TextField
              label="Diğer personel"
              inputMode="numeric"
              value={personel}
              onChange={(e) => setPersonel(e.target.value)}
              error={errors.max_loans_staff}
              helperText="Öğretmen sınırını aşamaz."
            />
          </div>
          <Onay
            label="Diğer personele ödünç verilir"
            checked={personeleOdunc}
            onChange={setPersoneleOdunc}
            helperText="Okul müdürlüğü kararıyla açılır; kararın tarihi ve sayısı zorunludur."
          />
          {personeleOdunc && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <TextField
                label="Müdürlük kararı tarihi"
                required
                type="date"
                value={kararTarihi}
                onChange={(e) => setKararTarihi(e.target.value)}
                error={errors.staff_loans_decision_date}
              />
              <TextField
                label="Müdürlük kararı sayısı"
                required
                value={kararSayisi}
                onChange={(e) => setKararSayisi(e.target.value)}
                error={errors.staff_loans_decision_no}
              />
            </div>
          )}
          <Onay
            label="Gecikmiş kitabı olana yeni ödünç verilmez"
            checked={gecikmedeEngelle}
            onChange={setGecikmedeEngelle}
          />
        </Bolum>

        <Bolum baslik="İade ve Yıl Sonu">
          <Onay
            label="İade tarihi öğrenciye kapalı günlerde kaydırılır"
            checked={kapaliGunKaydir}
            onChange={setKapaliGunKaydir}
            helperText="Ara tatil ve yarıyıl kanunen tatil değildir; bu kaydırma okulun tercihidir. Resmî ve dini tatil kaydırması bu ayardan bağımsızdır ve her zaman uygulanır."
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextField
              label="Yıl sonu son ödünç tarihi"
              type="date"
              value={sonOdunc}
              onChange={(e) => setSonOdunc(e.target.value)}
              error={errors.last_loan_date}
              helperText="Bu tarihten sonra yeni ödünç verilmez."
            />
            <TextField
              label="Son sınıflar için son ödünç tarihi"
              type="date"
              value={sonOduncMezun}
              onChange={(e) => setSonOduncMezun(e.target.value)}
              error={errors.last_loan_date_graduating}
              helperText="İsteğe bağlı; mezun olacak sınıflar için daha erken bir tarih."
            />
          </div>
        </Bolum>

        <Bolum baslik="Vitrin ve Saklama">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <TextField
              label="Çok okunanlar için en az üye sayısı"
              inputMode="numeric"
              value={enAzUye}
              onChange={(e) => setEnAzUye(e.target.value)}
              error={errors.popular_min_members}
              helperText="Bir eser vitrine ancak en az bu kadar farklı üye ödünç aldıysa girer; sayı hiçbir yerde gösterilmez."
            />
            <TextField
              label="Üyelik sonlandıktan sonra saklama (yıl)"
              inputMode="numeric"
              value={saklamaUyelik}
              onChange={(e) => setSaklamaUyelik(e.target.value)}
              error={errors.retention_years_after_termination}
            />
            <TextField
              label="İade edilmiş ödünçlerde saklama (yıl)"
              inputMode="numeric"
              value={saklamaOdunc}
              onChange={(e) => setSaklamaOdunc(e.target.value)}
              error={errors.retention_years_returned_loans}
            />
            <TextField
              label="Kapanmış kayıp/hasar dosyalarında saklama (yıl)"
              inputMode="numeric"
              value={saklamaDosya}
              onChange={(e) => setSaklamaDosya(e.target.value)}
              error={errors.retention_years_closed_cases}
            />
            <TextField
              label="Kapanmış teslimlerde saklama (yıl)"
              inputMode="numeric"
              value={saklamaTeslim}
              onChange={(e) => setSaklamaTeslim(e.target.value)}
              error={errors.retention_years_closed_deliveries}
            />
          </div>
        </Bolum>

        <Bolum baslik="Künye Getirme">
          <p className="text-body-medium text-on-surface-variant">
            Kitabın arka kapağındaki ISBN numarasıyla künye bilgilerini internetten getirir.
            Kapalıyken program bu iş için hiçbir bağlantı kurmaz. Açıksanız dışarıya yalnız
            numaranın kendisi gider: okul adı, kitap listesi ya da kişi bilgisi gönderilmez. Gelen
            künye bir öneridir; onaylamadan hiçbir alan değişmez ve çevirmen alanı dışarıdan
            doldurulmaz.
          </p>
          <Onay
            label="ISBN ile künye getirme açık"
            checked={kunyeAcik}
            onChange={setKunyeAcik}
            helperText="Varsayılan olarak kapalıdır. İnterneti olmayan masada kapalı bırakın; künyeyi Katalog → İçe Aktarma → Çevrimdışı Künye yoluyla da tamamlayabilirsiniz."
          />
          <Onay
            label="Kültür ve Turizm Bakanlığı halk kütüphaneleri kataloğunda ara"
            checked={kunyeBakanlik}
            onChange={setKunyeBakanlik}
            disabled={!kunyeAcik}
            helperText="Önce burası aranır; Türkçe kayıtlar ve sınıflama kodu buradan gelir."
          />
          <Onay
            label="Bulunamazsa Open Library'de ara"
            checked={kunyeOpenLibrary}
            onChange={setKunyeOpenLibrary}
            disabled={!kunyeAcik}
            helperText="Yedek kaynaktır; Türkçe kayıtlarında eksik harf ve yanlış tarih görülebilir, gelen künyeyi kitaptan doğrulayın."
          />
          {/* Ana anahtar açıkken iki kutu da boşsa sorgu her seferinde
              "bulunamadı" döner; sebep internet değil bu ayardır. Uyarı
              olmasaydı kullanıcı ağı ya da BTR'yi suçlardı. */}
          {kunyeAcik && !kunyeBakanlik && !kunyeOpenLibrary && (
            <p
              role="alert"
              className="rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-small text-on-tertiary-container"
            >
              Hiçbir kaynak seçili değil: künye getirme açık görünse de sorgu hiçbir yere gitmez ve
              program “İnternetten getirilemedi” der. En az bir kaynak seçin.
            </p>
          )}
        </Bolum>

        <div className="flex justify-end">
          <Button icon="check" onClick={kaydet} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
