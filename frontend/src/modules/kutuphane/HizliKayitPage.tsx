// Hızlı Kayıt — "önce etiket" yolunun (yöntem B) masa ekranı (tasarım §8.1).
//
// NEDEN ASIL YOL: okulda hazır bir Excel listesi yoktur (S8, 23.09.2026). Kitap
// elde, ISBN okutulur, künye gelir ya da elle yazılır, nüsha açılır. Kullanıcı
// TEK ekranda kalır; okuyucunun odağı kutudan çıkmaz: kayıttan sonra imleç
// yeniden ISBN kutusuna döner ki sıradaki kitap doğrudan okutulabilsin.
//
// Okutulan kodun türü yerel olarak ayrılır (`tarama.ts`, §7.1): kütüphane
// etiketi, üye kartı ve ISBN barkodu karışmasın. Yanlış kod okutulduğunda kayıt
// başlamaz, kullanıcı ne okutması gerektiğini okur.
//
// KÜNYE GETİRME AYARI KAPALIYSA BU EKRANDAN HİÇBİR DIŞ İSTEK ÇIKMAZ (§8.5-1):
// ayar okunur, kapalıysa sorgu kodu hiç çağrılmaz ve kullanıcı künyeyi elle
// yazar — elle giriş her koşulda tam işlevlidir (fail-open, §8.5-9).
//
// Katalogda aynı ISBN'li eser varsa kullanıcıya SORULUR: yeni eser açmak yerine
// var olan esere nüsha eklemek, yöntem B'de en sık yapılan iştir (aynı kitaptan
// ikinci nüsha). Bu arama yereldir, dışarıya çıkmaz.
//
// KİTAPTAKİ ETİKET (F4, yöntem B): boş barkod etiketleri önceden basılıp
// kitaplara yapıştırıldıysa nüsha O numarayla açılır. Sıra bağlayıcıdır:
//   1. etiket sunucuya SORULUR (`check/`, yazma yok) — bağlanamayacak bir etiket
//      için eser açılıp nüshasız kalmasın;
//   2. eser açılır (ya da seçilen esere eklenir);
//   3. nüsha etiketin numarasıyla açılır (`copies/from-label/`).
// Etiketi olmayan kitap için "Etiket yok — yeni numara ver" yolu F3'teki
// davranıştır (sayaçtan yeni numara) ve açılan nüshanın etiketi aynı ekrandan
// tek etiket kısayoluyla basılır. Açık boş etiket varsa ekran etiket yoluyla açılır.
//
// Eser açılıp nüsha açılamazsa (ör. etiket o arada başka kitaba bağlandı) eser
// SEÇİLİ kalır: yeniden denemede ikinci bir eser açılmaz.

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import ModuleHeader from "../../ui/ModuleHeader";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { CLASSIFICATION_SOURCE_TR, RESOURCE_TYPE_TR, kutuphaneApi } from "./api";
import type {
  Acquisition,
  ClassificationSource,
  Copy,
  KunyeSonucu,
  ResourceType,
  Work,
  WorkBody,
} from "./api";
import { etiketApi } from "./etiketApi";
import type { EtiketIcerigi } from "./etiketApi";
import KunyeAlanlari, { kunyeGovdesi, varsayilanSecim } from "./KunyeAlanlari";
import type { KunyeSecimi } from "./KunyeAlanlari";
import {
  SECICI_SINIRI,
  bolumSecenekleri,
  kodSecenekleri,
  secimKesildiMetni,
  secimKesildiMi,
  useBolumler,
} from "./ortak";
import { isbnNormalize, kodTuru } from "./tarama";
import TekEtiketBasimi from "./TekEtiketBasimi";

/** Sayfanın başlığı — üst çubuktaki başlıkla aynıdır (docs/sozluk.md §4). */
export const HIZLI_KAYIT_BASLIGI = "Hızlı Kayıt";

/**
 * Kitabın etiketi için iki yol (docs/sozluk.md §4.7). Adlar sunucu iletileriyle
 * aynıdır: etiket reddedilince sunucu "“Etiket yok — yeni numara ver”
 * seçeneğini kullanın" der.
 */
export const ETIKET_YOLLARI = {
  etiket: "Kitaptaki etiketi okutun",
  yeni: "Etiket yok — yeni numara ver",
} as const;

type EtiketYolu = keyof typeof ETIKET_YOLLARI;

/** Etiket yolunda ISBN kutusuna kütüphane etiketi okutulursa. */
const ETIKET_ISBN_KUTUSUNDA =
  "Bu bir kütüphane etiketi. Önce kitabın arka kapağındaki ISBN barkodunu okutun; etiketi “Kütüphane etiketi” kutusuna okutun.";

/** Yanlış kod okutulduğunda gösterilen iletiler (§7.1; sözlük dili). */
const KOD_ILETILERI: Record<string, string> = {
  COPY: "Bu bir kütüphane etiketi. Hızlı kayıtta kitabın arka kapağındaki ISBN barkodu okutulur.",
  MEMBER_CARD: "Bu bir üye kartı numarası. Kitabın arka kapağındaki ISBN barkodunu okutun.",
  UNKNOWN:
    "Bu numara ISBN'e benzemiyor. Kitabın arka kapağındaki numarayı okutun ya da künyeyi elle yazın.",
};

/** Edinim seçicisinin etiketi (bağışçı adı listede GÖSTERİLMEZ — şifreli alan). */
function edinimEtiketi(edinim: Acquisition): string {
  return `${edinim.method_display} — ${edinim.date}`;
}

interface KayitSonucu {
  eser: Work;
  nushalar: Copy[];
  yeniEser: boolean;
  /** Nüsha kitaptaki önceden basılmış etiketin numarasıyla mı açıldı? */
  etiketli: boolean;
}

export default function HizliKayitPage() {
  const navigate = useNavigate();
  const bolumler = useBolumler();
  const snackbar = useSnackbar();
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();

  // --- okutma ---
  const kodRef = useRef<HTMLInputElement>(null);
  const [kod, setKod] = useState("");
  const [kodUyarisi, setKodUyarisi] = useState("");

  // --- künye getirme ---
  const [kunyeAcik, setKunyeAcik] = useState(false);
  const [kunye, setKunye] = useState<KunyeSonucu | null>(null);
  const [kunyeSecim, setKunyeSecim] = useState<KunyeSecimi>({});
  const [kunyeAraniyor, setKunyeAraniyor] = useState(false);

  // --- katalogdaki eşleşmeler ---
  const [benzerler, setBenzerler] = useState<Work[]>([]);
  const [eser, setEser] = useState<Work | null>(null);

  // --- künye formu ---
  const [title, setTitle] = useState("");
  const [authors, setAuthors] = useState("");
  const [translator, setTranslator] = useState("");
  const [publisher, setPublisher] = useState("");
  const [publishYear, setPublishYear] = useState("");
  const [isbn, setIsbn] = useState("");
  const [subjects, setSubjects] = useState("");
  const [classificationCode, setClassificationCode] = useState("");
  const [classificationSource, setClassificationSource] = useState<ClassificationSource>("MANUAL");
  const [callNumber, setCallNumber] = useState("");
  const [language, setLanguage] = useState("");
  const [resourceType, setResourceType] = useState<ResourceType>("BOOK");

  // --- nüsha ---
  const [edinimler, setEdinimler] = useState<Acquisition[]>([]);
  const [edinim, setEdinim] = useState("");
  const [adet, setAdet] = useState("1");
  const [bolum, setBolum] = useState("");
  const [eskiKayitNo, setEskiKayitNo] = useState("");
  const [danisma, setDanisma] = useState(false);

  // --- kitaptaki etiket (yöntem B) ---
  const [etiketYolu, setEtiketYolu] = useState<EtiketYolu>("yeni");
  // Kullanıcı yolu kendisi seçtiyse açılıştaki kendiliğinden seçim onu ezmez.
  const yolSecildi = useRef(false);
  const etiketRef = useRef<HTMLInputElement>(null);
  // Etiket kutusu fareyle odak alınca metin seçili kalsın diye (bkz. onMouseUp).
  const etiketFareyleOdak = useRef(false);

  /**
   * Etiket kutusunda duran kod SEÇİLİR: okuyucunun sıradaki okutması eskisinin
   * sonuna eklenmez, onu siler. Yalnız odak zaten kutudaysa (odak çalınmaz).
   */
  const etiketiSec = (): void => {
    if (document.activeElement === etiketRef.current) etiketRef.current?.select();
  };
  const [etiketKodu, setEtiketKodu] = useState("");
  const [etiketIpucu, setEtiketIpucu] = useState("");

  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [sonuc, setSonuc] = useState<KayitSonucu | null>(null);
  // Tek etiket kısayolu: sonuç kartından açılır, sıradaki kitap okutulunca da kalır.
  const [basim, setBasim] = useState<{ nushalar: Copy[]; icerik: EtiketIcerigi } | null>(null);

  // Bağlanmamış boş etiket varsa okul önce etiket yolundadır: ekran o yolla açılır.
  useEffect(() => {
    let iptal = false;
    etiketApi
      .ozet()
      .then((ozet) => {
        if (!iptal && !yolSecildi.current && ozet.reservations.open > 0) setEtiketYolu("etiket");
      })
      .catch(() => {
        // Sayaç okunamazsa bugünkü yol (yeni numara) kalır; kullanıcı seçebilir.
      });
    return () => {
      iptal = true;
    };
  }, []);

  // Ayar okunur; okunamazsa KAPALI sayılır — dış istek kapısı fail-closed'dır.
  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .getPolicy()
      .then((politika) => {
        if (!iptal) setKunyeAcik(politika.metadata_lookup_enabled);
      })
      .catch(() => {
        if (!iptal) setKunyeAcik(false);
      });
    return () => {
      iptal = true;
    };
  }, []);

  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .listAcquisitions({ limit: SECICI_SINIRI })
      .then((sayfa) => {
        if (iptal) return;
        setEdinimler(sayfa.results);
        if (sayfa.results.length > 0) setEdinim(String(sayfa.results[0].id));
      })
      .catch(() => {
        if (!iptal) setEdinimler([]);
      });
    return () => {
      iptal = true;
    };
  }, []);

  useEffect(() => {
    kodRef.current?.focus();
  }, []);

  /** Formun o anki değerleri — künye önerisi "dolu alan" karşılaştırmasını buradan yapar.
   *
   * Sunucunun `dolu`/`mevcut_deger` alanları EKRANDAKİ formu bilmez (sorguya
   * eser verilmediğinde hepsi boş gelir). §8.5-5 "dolu alan sessizce üzerine
   * yazılmaz" kuralı bu yüzden ekranda uygulanır.
   */
  const formDegerleri: Record<string, string> = {
    title,
    authors,
    publisher,
    edition: "",
    publish_year: publishYear,
    isbn,
    subjects,
    classification_code: classificationCode,
    call_number: callNumber,
    language,
  };
  const formBos = Object.values(formDegerleri).every((deger) => deger.trim() === "");

  /** Öneriyi formdaki güncel değerlerle karşılaştırır (sunucu alanını değil). */
  const formaGoreAlanlar = (sonucKunye: KunyeSonucu): KunyeSonucu["alanlar"] =>
    sonucKunye.alanlar.map((alan) => {
      const mevcut = formDegerleri[alan.alan] ?? "";
      return {
        ...alan,
        mevcut_deger: mevcut === "" ? null : mevcut,
        dolu: mevcut.trim() !== "",
        farkli: alan.deger !== null && alan.deger !== "" && String(alan.deger) !== mevcut,
      };
    });

  /** Künye önerisini forma yazar (yalnız işaretli ve dolu alanlar). */
  const formaYaz = (sonucKunye: KunyeSonucu, secim: KunyeSecimi): void => {
    const govde = kunyeGovdesi(sonucKunye.alanlar, secim);
    if (govde.title !== undefined) setTitle(govde.title);
    if (govde.authors !== undefined) setAuthors(govde.authors);
    if (govde.publisher !== undefined) setPublisher(govde.publisher);
    if (govde.publish_year !== undefined && govde.publish_year !== null) {
      setPublishYear(String(govde.publish_year));
    }
    if (govde.isbn !== undefined) setIsbn(govde.isbn);
    if (govde.subjects !== undefined) setSubjects(govde.subjects);
    if (govde.classification_code !== undefined) {
      setClassificationCode(govde.classification_code);
      // Kod dış kataloğdan geldi: kaynağı "Katalogdan bulundu" olarak ÖNERİR ama
      // kutuyu kilitlemez — kullanıcı seçimi görür ve değiştirebilir.
      setClassificationSource("CATALOG");
    }
    if (govde.call_number !== undefined) setCallNumber(govde.call_number);
    if (govde.language !== undefined) setLanguage(govde.language);
  };

  /** Künye sorgusu — "Yeniden getir" aynı yolu `force` ile kullanır (§8.5-6). */
  const kunyeSor = async (numara: string, { force = false } = {}): Promise<void> => {
    setKunyeAraniyor(true);
    try {
      const gelen = await kutuphaneApi.kunyeGetir(numara, { force });
      // Karşılaştırma FORMDAKİ değerlere göre yapılır: sorguya eser verilmediği
      // için sunucunun `dolu`/`mevcut_deger` alanları boş gelir ve "Kayıttaki
      // değer" sütunu hep "—" görünürdü.
      const sonucKunye: KunyeSonucu = { ...gelen, alanlar: formaGoreAlanlar(gelen) };
      setKunye(sonucKunye);
      const secim = varsayilanSecim(sonucKunye.alanlar);
      setKunyeSecim(secim);
      // Kendiliğinden yazma YALNIZ form boşken: dolu alanın üzerine sessizce
      // yazılmaz (§8.5-5). Form doluysa kullanıcı "Seçilenleri forma yaz" der.
      if (sonucKunye.bulundu && formBos) formaYaz(sonucKunye, secim);
    } catch (e) {
      // Fail-open: uç ölse de akış sürer, kullanıcı künyeyi elle yazar.
      setKunye(null);
      setHata(hataOku(e, "İnternetten getirilemedi, elle girebilirsiniz."));
    } finally {
      setKunyeAraniyor(false);
    }
  };

  /** ISBN okutuldu ya da yazıldı: tür ayrılır, katalog aranır, künye istenir. */
  const kodGirildi = async (): Promise<void> => {
    // Yeniden giriş kapısı: okuyucu kodun sonuna Enter gönderir; kayıt ya da
    // sorgu sürerken gelen ikinci okutma, biten isteğin `setKod("")`i yüzünden
    // sessizce kaybolur ya da iki yanıt yarışırdı.
    if (busy || kunyeAraniyor) return;
    const ham = kod.trim();
    if (!ham) return;
    setHata(null);
    setSonuc(null);
    const tur = kodTuru(ham);
    if (tur !== "ISBN") {
      setKodUyarisi(
        tur === "COPY" && etiketYolu === "etiket"
          ? ETIKET_ISBN_KUTUSUNDA
          : (KOD_ILETILERI[tur] ?? KOD_ILETILERI.UNKNOWN),
      );
      // Tanınmayan kodun HAM metni ISBN alanına yazılmaz: raf etiketi, QR ya da
      // URL parçası olabilir ve alanda duran değeri ezerdi. Sadeleştirilmiş
      // biçim yalnız alan boşken yazılır (elle yazılan ISBN-10 kolaylığı).
      const sade = isbnNormalize(ham);
      if (tur === "UNKNOWN" && sade && !isbn.trim()) setIsbn(sade);
      kodRef.current?.select();
      return;
    }
    const numara = isbnNormalize(ham);
    setKodUyarisi("");
    setIsbn(numara);

    // Yerel katalog araması: aynı kitabın ikinci nüshası yöntem B'nin olağan işi.
    let benzerSayisi = 0;
    try {
      const sayfa = await kutuphaneApi.listWorks({ q: numara, limit: 5 });
      setBenzerler(sayfa.results);
      benzerSayisi = sayfa.results.length;
    } catch {
      setBenzerler([]);
    }

    if (kunyeAcik) await kunyeSor(numara);

    // Etiket yolunda sıradaki iş kitaptaki etiketi okutmaktır: odak oraya geçer.
    // Katalogda aynı numarayla eser varsa geçmez — önce "Bu esere nüsha ekle"
    // kararı verilmeli, yoksa etiket okutulunca ikinci bir eser açılırdı.
    // Odak okutma kutusunda kalırsa ISBN seçilir: sıradaki okutma onun sonuna
    // eklenmez, onu siler.
    if (etiketYolu === "etiket" && benzerSayisi === 0) etiketRef.current?.focus();
    else if (document.activeElement === kodRef.current) kodRef.current?.select();
  };

  /** Formu sıfırlar ve odağı okutma kutusuna döndürür.
   *
   * KAYITTAN SONRA DA ÇAĞRILIR: "Formu temizle" düğmesiyle aynı yer. Ayrı bir
   * kısmi sıfırlama tutulsaydı (yalnız kod + künye) sıradaki kitap öncekinin
   * künyesiyle, eski kayıt numarasıyla ve danışma işaretiyle kaydedilirdi.
   * Edinim ve bölüm seçimi BİLİNÇLİ olarak korunur: aynı parti arka arkaya
   * girilir.
   */
  const temizle = (): void => {
    setKod("");
    setKodUyarisi("");
    setKunye(null);
    setKunyeSecim({});
    setBenzerler([]);
    setEser(null);
    setTitle("");
    setAuthors("");
    setTranslator("");
    setPublisher("");
    setPublishYear("");
    setIsbn("");
    setSubjects("");
    setClassificationCode("");
    setClassificationSource("MANUAL");
    setCallNumber("");
    setLanguage("");
    setResourceType("BOOK");
    setAdet("1");
    setEskiKayitNo("");
    setDanisma(false);
    setEtiketKodu("");
    setEtiketIpucu("");
    clearErrors();
    setHata(null);
    kodRef.current?.focus();
  };

  const yolDegisti = (yol: EtiketYolu): void => {
    yolSecildi.current = true;
    setEtiketYolu(yol);
    setEtiketIpucu("");
    clearErrors();
  };

  const kaydet = async (): Promise<void> => {
    // Okuyucunun Enter'ı ile tıklama üst üste gelirse ikinci istek gitmesin.
    if (busy) return;
    clearErrors();
    setHata(null);
    setEtiketIpucu("");
    const etiketle = etiketYolu === "etiket";
    const etiket = etiketKodu.trim();
    // Erken dönüşlerde okutulmuş etiket kutuda SEÇİLİ kalır: künye tamamlanıp
    // etiket yeniden okutulunca iki kod birleşmesin ("2026-0001012026-000101").
    if (eser === null && !title.trim()) {
      setFieldError("title", "Kaynak adı yazılmalıdır.");
      if (etiketle) etiketiSec();
      return;
    }
    if (!edinim) {
      setFieldError("acquisition", "Edinim seçilmelidir.");
      if (etiketle) etiketiSec();
      return;
    }
    const sayi = etiketle ? 1 : Number(adet);
    if (!Number.isInteger(sayi) || sayi < 1) {
      setFieldError("count", "Nüsha sayısı en az 1 olmalıdır.");
      return;
    }
    if (etiketle && !etiket) {
      setFieldError("label_code", "Kitaba yapıştırdığınız kütüphane etiketini okutun.");
      etiketRef.current?.focus();
      return;
    }
    setBusy(true);
    // Bu kayıtta açılan eser: nüsha açılamazsa seçili kalır (yeniden denemede ikinci eser açılmaz).
    let acilanEser: Work | null = null;
    try {
      // 1) Etiket ÖNCE sorulur: bağlanamayacak etiket için eser açılmaz.
      if (etiketle) {
        const denetim = await etiketApi.etiketDenetle(etiket);
        if (!denetim.bindable) {
          setFieldError("label_code", denetim.message);
          setEtiketIpucu(denetim.hint);
          etiketRef.current?.select();
          return;
        }
      }
      const yeniEser = eser === null;
      const govde: WorkBody = {
        title: title.trim(),
        authors: authors.trim(),
        translator: translator.trim(),
        publisher: publisher.trim(),
        publish_year: publishYear.trim() ? Number(publishYear.trim()) : null,
        isbn: isbn.trim(),
        subjects: subjects.trim(),
        classification_code: classificationCode.trim(),
        classification_source: classificationSource,
        call_number: callNumber.trim(),
        resource_type: resourceType,
        language: language.trim(),
        section: bolum ? Number(bolum) : null,
      };
      if (eser === null) acilanEser = await kutuphaneApi.createWork(govde);
      const kayit = eser ?? (acilanEser as Work);
      if (kayit.isbn_warning) snackbar.show(kayit.isbn_warning, { duration: 6000 });
      const nushaAlanlari = {
        work: kayit.id,
        acquisition: Number(edinim),
        section: bolum ? Number(bolum) : (kayit.section ?? null),
        old_register_no: eskiKayitNo.trim(),
        is_reference: danisma,
      };
      let nushalar: Copy[];
      if (etiketle) {
        // 3) Nüsha kitaptaki etiketin numarasıyla açılır.
        const nusha = await etiketApi.etiketleNushaAc({ ...nushaAlanlari, label_code: etiket });
        nushalar = [nusha];
        snackbar.success(`Nüsha ${nusha.barcode_display} numarasıyla açıldı.`);
      } else {
        const sonucNushalar = await kutuphaneApi.createCopies({ ...nushaAlanlari, count: sayi });
        nushalar = sonucNushalar.results;
        snackbar.success(`${formatNumber(sonucNushalar.count)} nüsha açıldı.`);
      }
      // Form SIFIRLANIR ve odak okutma kutusuna döner: sıradaki kitap doğrudan
      // okutulabilsin. Sıfırlanmasaydı B kitabı A'nın künyesiyle, A'nın eski
      // kayıt numarasıyla ve A'nın danışma işaretiyle kaydedilirdi.
      temizle();
      setSonuc({ eser: kayit, nushalar, yeniEser, etiketli: etiketle });
    } catch (e) {
      applyApiError(e);
      const okunan = hataOku(e, "Kayıt tamamlanamadı.");
      if (acilanEser !== null) {
        // Eser açıldı, nüsha açılamadı: eser seçili kalır ki yeniden denemede
        // ikinci bir eser açılmasın. Künye formu kapanır, "Seçilen eser" görünür.
        setEser(acilanEser);
        setHata({
          ...okunan,
          message: `${okunan.message} Eser kaydedildi; sorunu giderip yeniden “Nüshayı aç” deyin.`,
        });
      } else {
        setHata(okunan);
      }
      if (etiketle) etiketRef.current?.select();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader backTo="/katalog" moduleLabel="Katalog" title={HIZLI_KAYIT_BASLIGI} />

      <p className="kd-page-description max-w-4xl">
        Kitap elinizdeyken ISBN barkodunu okutun: künye önerisi gelir ya da elle yazarsınız. Kitaba
        önceden basılmış boş barkod etiketi yapıştırdıysanız etiketi okutursunuz ve nüsha o
        numarayla açılır; etiketsiz kitaba program yeni numara verir. Numara asla yeniden
        kullanılmaz.
      </p>

      {hata && <ErrorBand hata={hata} />}

      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Kitabın ISBN'ini okutun</p>
        <div className="flex flex-wrap items-end gap-3">
          <TextField
            className="min-w-[18rem] flex-1"
            label="ISBN barkodu"
            ref={kodRef}
            value={kod}
            onChange={(e) => setKod(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void kodGirildi();
              }
            }}
            placeholder="9789750812345"
            helperText="Okuyucuyla okutabilir ya da elle yazıp Enter'a basabilirsiniz."
          />
          <Button
            variant="tonal"
            icon="search"
            onClick={() => void kodGirildi()}
            disabled={busy || kunyeAraniyor}
          >
            {kunyeAraniyor ? "Aranıyor…" : "Künyeyi getir"}
          </Button>
          <Button variant="text" icon="restart_alt" onClick={temizle} disabled={busy}>
            Formu temizle
          </Button>
        </div>

        {kodUyarisi && (
          <p
            role="status"
            className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container"
          >
            <Icon name="info" size="lg" className="mt-0.5 shrink-0" />
            {kodUyarisi}
          </p>
        )}

        {!kunyeAcik && (
          <p className="text-body-small text-on-surface-variant">
            ISBN ile künye getirme kapalı; künyeyi elle yazabilirsiniz. Açmak için{" "}
            <Link to="/ayarlar?tab=politika" className="text-primary underline underline-offset-2">
              Ayarlar → Kütüphane Politikası
            </Link>{" "}
            ekranına bakın.
          </p>
        )}

        {kunye && !kunye.bulundu && (
          <p className="text-body-medium text-on-surface-variant">{kunye.ileti}</p>
        )}

        {kunye && kunye.bulundu && (
          <div className="space-y-3 rounded-shape-md bg-surface-container-low p-3">
            <p className="text-body-small text-on-surface-variant">
              {kunye.kaynak_etiketi}
              {kunye.kayit_sayisi > 1 &&
                ` · bu numarayla ${formatNumber(kunye.kayit_sayisi)} kayıt bulundu, en ayrıntılısı alındı`}
              {kunye.onbellekten && " · daha önce sorulduğu için yeniden sorulmadı"}
            </p>
            <KunyeAlanlari
              alanlar={kunye.alanlar}
              secim={kunyeSecim}
              onSecim={(alan, secili) => setKunyeSecim((onceki) => ({ ...onceki, [alan]: secili }))}
              kaynakEtiketi={kunye.kaynak_etiketi}
              rozet={kunye.rozet}
              uyarilar={kunye.uyarilar}
            />
            <div className="flex flex-wrap justify-end gap-2">
              {/* Önbellek kaçışı (§8.5-6): bozuk ya da eksik gelen bir künye
                  ISBN başına kalıcı olmasın; kullanıcı kaynağa yeniden sorabilsin. */}
              <Button
                variant="text"
                icon="refresh"
                onClick={() => void kunyeSor(isbn.trim() || kunye.isbn13, { force: true })}
                disabled={busy || kunyeAraniyor}
              >
                Yeniden getir
              </Button>
              <Button variant="text" icon="edit_note" onClick={() => formaYaz(kunye, kunyeSecim)}>
                Seçilenleri forma yaz
              </Button>
            </div>
          </div>
        )}

        {benzerler.length > 0 && (
          <div className="space-y-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-on-secondary-container">
            <p className="text-label-large">
              Katalogda bu numarayla {formatNumber(benzerler.length)} eser var
            </p>
            <p className="text-body-small">
              Aynı kitabın yeni bir nüshasıysa yeni eser açmayın: aşağıdan eseri seçin, künye formu
              kapanır ve nüsha o esere eklenir.
            </p>
            <ul className="space-y-1">
              {benzerler.map((aday) => (
                <li key={aday.id} className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-body-medium">
                    {aday.title}
                    {aday.authors && ` — ${aday.authors}`} ({formatNumber(aday.copy_count)} nüsha)
                  </span>
                  <Button
                    variant="outlined"
                    icon="library_add"
                    onClick={() => {
                      setEser(aday);
                      setBolum(aday.section === null ? "" : String(aday.section));
                      // Odak düğmede kalırsa okuyucunun gönderdiği rakamlar
                      // kaybolur, sondaki Enter düğmeye yeniden basar. Etiket
                      // yolunda sıradaki iş etiketi okutmaktır; yeni numara
                      // yolunda odak okutma kutusuna döner (ISBN seçili).
                      if (etiketYolu === "etiket") {
                        etiketRef.current?.focus();
                      } else {
                        kodRef.current?.focus();
                        kodRef.current?.select();
                      }
                    }}
                  >
                    Bu esere nüsha ekle
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {eser ? (
        <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-title-medium text-on-surface">Seçilen eser</p>
          <p className="text-body-medium text-on-surface">
            {eser.title}
            {eser.authors && ` — ${eser.authors}`}
          </p>
          <p className="text-body-small text-on-surface-variant">
            Künye yeniden yazılmaz; nüsha bu esere eklenir.
          </p>
          <div className="flex justify-end">
            <Button variant="text" icon="close" onClick={() => setEser(null)}>
              Seçimi bırak
            </Button>
          </div>
        </Card>
      ) : (
        <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-title-medium text-on-surface">Künye</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextField
              className="sm:col-span-2"
              label="Kaynak adı"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              error={errors.title}
            />
            <TextField
              label="Yazar(lar)"
              value={authors}
              onChange={(e) => setAuthors(e.target.value)}
              error={errors.authors}
            />
            <TextField
              label="Çevirmen"
              value={translator}
              onChange={(e) => setTranslator(e.target.value)}
              error={errors.translator}
              helperText="Dış kaynaklardan doldurulmaz; çeviri eserde elle yazılır."
            />
            <TextField
              label="Yayınevi"
              value={publisher}
              onChange={(e) => setPublisher(e.target.value)}
              error={errors.publisher}
            />
            <TextField
              label="Yayın yılı"
              inputMode="numeric"
              value={publishYear}
              onChange={(e) => setPublishYear(e.target.value)}
              error={errors.publish_year}
            />
            <TextField
              label="ISBN"
              value={isbn}
              onChange={(e) => setIsbn(e.target.value)}
              error={errors.isbn}
              helperText="Sağlama hatası kaydı engellemez, uyarı verilir."
            />
            <TextField
              label="Konu(lar)"
              value={subjects}
              onChange={(e) => setSubjects(e.target.value)}
              error={errors.subjects}
            />
            <Select
              label="Kaynak türü"
              value={resourceType}
              onChange={(e) => setResourceType(e.target.value as ResourceType)}
              options={kodSecenekleri(RESOURCE_TYPE_TR)}
              error={errors.resource_type}
              helperText="E-kitap ve e-veri tabanında nüsha açılmaz."
            />
            <TextField
              label="Dil"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              error={errors.language}
            />
            <TextField
              label="Sınıflama kodu"
              value={classificationCode}
              onChange={(e) => setClassificationCode(e.target.value)}
              error={errors.classification_code}
              helperText="Dewey Onlu Sınıflama (DOS) kodu."
            />
            <Select
              label="Sınıflama kaynağı"
              value={classificationSource}
              onChange={(e) => setClassificationSource(e.target.value as ClassificationSource)}
              options={kodSecenekleri(CLASSIFICATION_SOURCE_TR)}
              error={errors.classification_source}
            />
            <TextField
              label="Yer numarası"
              value={callNumber}
              onChange={(e) => setCallNumber(e.target.value)}
              error={errors.call_number}
              helperText="Boş bırakılırsa sınıflama kodu ve yazar kodundan üretilir."
            />
          </div>
        </Card>
      )}

      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Kitabın etiketi</p>
        <fieldset className="flex flex-wrap gap-x-6 gap-y-1">
          <legend className="sr-only">Kitabın etiketi</legend>
          {(Object.keys(ETIKET_YOLLARI) as EtiketYolu[]).map((yol) => (
            <label
              key={yol}
              className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface"
            >
              <input
                type="radio"
                name="etiket-yolu"
                checked={etiketYolu === yol}
                onChange={() => yolDegisti(yol)}
                className="size-5 shrink-0 accent-primary"
              />
              {ETIKET_YOLLARI[yol]}
            </label>
          ))}
        </fieldset>
        {etiketYolu === "etiket" ? (
          <>
            <TextField
              className="max-w-xl"
              label="Kütüphane etiketi"
              ref={etiketRef}
              value={etiketKodu}
              autoComplete="off"
              onChange={(e) => setEtiketKodu(e.target.value)}
              // Kutu odak alınca kod seçilir: yeniden okutulan etiket eskisinin
              // siler. Fareyle tıklamada tarayıcı fare bırakılınca seçimi
              // kaldırır; o bırakma bir kez yutulur.
              onFocus={(e) => e.currentTarget.select()}
              onMouseDown={() => {
                etiketFareyleOdak.current = document.activeElement !== etiketRef.current;
              }}
              onMouseUp={(e) => {
                if (etiketFareyleOdak.current) {
                  e.preventDefault();
                  etiketFareyleOdak.current = false;
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void kaydet();
                }
              }}
              placeholder="2026-000123"
              error={errors.label_code}
              helperText="Kitaba yapıştırdığınız boş barkod etiketini okutun; okutunca nüsha o numarayla açılır."
            />
            {etiketIpucu && (
              <p className="text-body-small text-on-surface-variant">{etiketIpucu}</p>
            )}
          </>
        ) : (
          <p className="text-body-small text-on-surface-variant">
            Program sayaçtan yeni numara verir. Nüsha açıldıktan sonra etiketini bu ekrandan
            basabilirsiniz.
          </p>
        )}
      </Card>

      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Nüsha</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Select
            label="Edinim"
            required
            placeholder="Seçin"
            value={edinim}
            onChange={(e) => setEdinim(e.target.value)}
            options={edinimler.map((a) => ({ value: String(a.id), label: edinimEtiketi(a) }))}
            error={errors.acquisition}
            helperText={
              edinimler.length === 0
                ? "Önce Edinimler ve Bağışlar ekranından bir edinim açın."
                : secimKesildiMi(edinimler.length)
                  ? secimKesildiMetni("“Edinimler ve Bağışlar” ekranını")
                  : "Her nüsha bir edinim partisinden gelir."
            }
          />
          {etiketYolu === "yeni" && (
            <TextField
              label="Nüsha sayısı"
              inputMode="numeric"
              value={adet}
              onChange={(e) => setAdet(e.target.value)}
              error={errors.count}
              helperText="Aynı künyeden birden çok nüsha açabilirsiniz."
            />
          )}
          <Select
            label="Bölüm"
            placeholder="— yok —"
            value={bolum}
            onChange={(e) => setBolum(e.target.value)}
            options={bolumSecenekleri(bolumler)}
            error={errors.section}
          />
          <TextField
            label="Eski kayıt no"
            value={eskiKayitNo}
            onChange={(e) => setEskiKayitNo(e.target.value)}
            error={errors.old_register_no}
            helperText="Kitaptaki eski damga; yalnız tek nüsha açarken yazılır."
          />
        </div>
        <label className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            checked={danisma}
            onChange={(e) => setDanisma(e.target.checked)}
            className="size-5 shrink-0 accent-primary"
          />
          Danışma kaynağı (ödünç verilmez)
        </label>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button icon="check" onClick={() => void kaydet()} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Nüshayı aç"}
          </Button>
        </div>
      </Card>

      {sonuc && (
        <SonucKarti
          sonuc={sonuc}
          onAc={() => navigate(`/katalog/eser/${sonuc.eser.id}`)}
          onEtiketBas={() =>
            setBasim({ nushalar: sonuc.nushalar, icerik: sonuc.etiketli ? "SPINE" : "BOTH" })
          }
        />
      )}

      {basim && (
        <TekEtiketBasimi
          // Başka nüshanın kısayolu açılınca kart sıfırdan kurulur.
          key={basim.nushalar.map((n) => n.id).join(",")}
          nushalar={basim.nushalar}
          ilkIcerik={basim.icerik}
          onKapat={() => {
            setBasim(null);
            kodRef.current?.focus();
          }}
        />
      )}
    </div>
  );
}

function SonucKarti({
  sonuc,
  onAc,
  onEtiketBas,
}: {
  sonuc: KayitSonucu;
  onAc: () => void;
  onEtiketBas: () => void;
}) {
  return (
    <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <p className="flex items-center gap-2 text-title-medium text-on-surface">
        <Icon name="check_circle" size="lg" className="text-primary" />
        {sonuc.yeniEser ? "Eser ve nüsha açıldı" : "Nüsha açıldı"}
      </p>
      <p className="text-body-medium text-on-surface">
        {sonuc.eser.title} — barkod{" "}
        {sonuc.nushalar.map((nusha) => nusha.barcode_display).join(", ")}
      </p>
      <p className="text-body-small text-on-surface-variant">
        {sonuc.etiketli
          ? "Nüsha kitaptaki etiketin numarasıyla açıldı; barkod etiketi okutulmuş sayılır. Sırt etiketi Etiketler → Basım Kuyruğu'nda bekler."
          : "Bu nüshanın etiketi henüz basılmadı; Etiketler → Basım Kuyruğu'nda bekler. Kitap elinizdeyse etiketini şimdi basabilirsiniz."}
      </p>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outlined" icon="print" onClick={onEtiketBas}>
          {sonuc.etiketli ? "Sırt etiketini bas" : "Etiketini bas"}
        </Button>
        <Button variant="text" icon="open_in_new" onClick={onAc}>
          Künyeyi aç
        </Button>
      </div>
    </Card>
  );
}
