// Dolaşım masası — tasarım §7.3 durum tablosu. Yönetici kipinde "Dolaşım Masası"
// sayfasında, görevli kipinde görevli ekranında (tek ekran) aynı bileşen durur;
// `gorevli` prop'u yalnız görüntüyü ve yönetici işlerinin düğmelerini ayırır —
// asıl kapı sunucudadır (izin listesi + parametre kuralı, daraltılmış yanıtlar).
//
// | Durum | Girdi | Sonuç |
// |---|---|---|
// | Boş | kart | ÜYE bağlamı: ad + kalan hak (sınıf yok) |
// | Boş | kitap | açık ödünçteyse İADE; değilse durum iletisi |
// | ÜYE | kitap | ödünç verilebilirse ödünç; değilse kişisel olmayan sebep |
// | ÜYE | kitap başka üyede | "Bu kitap başka bir üyede. Önce iade alınsın mı?" |
// | ÜYE | 60 sn işlem yok · "Bitti" · başka kart | bağlam kapanır |
// | Her durum | iptal kart | "İptal edilmiş kart — kütüphane yöneticisine yönlendirin." |
// | Her durum | tanınmayan / ISBN | özel ileti |
//
// Okutmalar tek kutudan gelir (`ui/BarcodeInput`, sıralı kuyruk): kodun türü yerel
// olarak ayrılır (`kutuphane/tarama.ts`) — üye kartı kart ucuna, geri kalan her şey
// bağlama göre iade ya da ödünç ucuna gider (ISBN ve tanınmayan kod iletisini sunucu
// verir). Kuyruk işleyicisi bağlamı REF'ten okur: art arda okutulan kart ve kitaplar
// sırayla, her biri bir öncekinin bıraktığı bağlamla işlenir.
//
// Görevli kipinde (§4.4, sözlük §5): üye bağlamında yalnız ad + kalan hak; iadede
// ödünç alanın kimliği ve gecikme günü yok; gecikmesi olan üyede yalnız "Ödünç
// verilemiyor — kütüphane yöneticisine yönlendirin."; ekrandaki son işlemler
// listesinde üye adı yok. Gerekçeli istisna ve kartsız ödünç yalnız yönetici
// kipindedir.
//
// F6 düzeltme turu:
//   * Kart okutma kilidi (GA-7) PENCERE DEĞİL, okutma kutusunun üstündeki şerittir:
//     kutu açık kalır, kilitliyken okutulan kitabın iadesi alınır (iade kilitlenmez).
//   * Gerekçeli istisna penceresi açıkken kuyruk BEKLER: pencereden sonra okutulan
//     kitaplar sıraya girer (kutu tamponu — `BarcodeInput`) ve pencere kapanınca
//     sırayla işlenir; kuyrukta bekleyen okutmalar açık pencereyi ezmez. Pencere hangi
//     kitap için açıldığını gösterir. Pencere açıkken 60 sn bağlam süresi işlemez.
//   * Üyeye bağlı retlerde (üyelik sonlanmış, yıl sonu, gecikme, sınır dolu) okutulan
//     kitabın iadesi önerilir: kitap iade için getirilmiş olabilir.
//   * "İade al ve ödünç ver" bağlamı düğmeye basıldığı an yakalar; iade sürerken
//     bağlam değiştiyse ödünç verilmez.
//   * "Yalnız durum sor" ayrı bir ses verir ve üye kartı okutulunca kendiliğinden kapanır.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../lib/api";
import { formatDate, formatNumber } from "../../lib/format";
import BarcodeInput, { okumaSesiAcikMi, okumaSesiniAyarla } from "../../ui/BarcodeInput";
import type { OkutmaGeriBildirimi } from "../../ui/BarcodeInput";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { hataOku } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { barkodBicimle, kodTuru } from "../kutuphane/tarama";
import { KARTSIZ_GEREKCELER, RED, UYEYE_BAGLI_RETLER, dolasimApi } from "./api";
import type {
  IstisnaGerekcesi,
  KartsizGerekce,
  KartSonucu,
  MasaNushasi,
  MasaUyesi,
  OduncGovdesi,
  OduncSonucu,
} from "./api";
import { IstisnaDiyalogu, KartKilidiSeridi, KartsizOduncDiyalogu } from "./MasaDiyaloglari";

/** Üye bağlamı bu kadar süre işlem yapılmazsa kapanır (§7.3). */
export const BAGLAM_SURESI_MS = 60_000;
/** Ekranda tutulan son işlem sayısı. */
const GOSTERILEN_ISLEM = 12;

export const OKUTMA_KUTUSU = "Üye kartı ya da kütüphane etiketi";
export const BITTI_DUGMESI = "Bitti";
export const KARTSIZ_DUGMESI = "Kartsız ödünç";
export const DURUM_SORGUSU = "Yalnız durum sor";
export const BASKA_UYEDE_SORUSU = "Bu kitap başka bir üyede. Önce iade alınsın mı?";
export const BU_UYEDE_SORUSU = "Bu kitap zaten bu üyede. İade alınsın mı?";
export const BASKA_UYEDEN_IADE_UYARISI =
  "Kitap başka bir üyenin ödüncündeydi; iadesi alındı. Durumu kütüphane yöneticisine bildirin.";
/** Üyeye bağlı retten sonra (sonlanmış üyelik, sınır dolu…) okutulan kitabın iadesi. */
export const IADE_ONERISI = "Kitap iade için getirildiyse iadesi alınabilir.";
/** "İade al ve ödünç ver" sürerken üye bağlamı değişti ya da kapandı. */
export const ISTEM_BAGLAM_DEGISTI =
  "İade alındı; üye bağlamı bu arada değiştiği için kitap ödünç verilmedi.";
export const DURUM_SORGUSU_KAPANDI = "“Yalnız durum sor” kapatıldı: üye kartı okutuldu.";
export const BAGLAM_ZAMAN_ASIMI = "Üye bağlamı kapandı: 60 saniye işlem yapılmadı.";
export const BAGLAM_KAPANDI = "Üye bağlamı kapandı.";

interface UyeBaglami {
  /** Okutulan kart no — ödünçte yeniden gönderilir (görevlide üyeyi kanıtlayan tek şey). */
  kart: string | null;
  /** Yalnız yönetici kipinde kartsız ödünç: üyelik kaydı ve gerekçe. */
  uyelikId: number | null;
  kartsizGerekce: KartsizGerekce | null;
  uye: MasaUyesi;
  ileti: string;
}

/** İki bağlam aynı üyenin mi? (kalan hak güncellemesi yeni nesne üretir, üye aynıdır) */
function ayniUye(a: UyeBaglami | null, b: UyeBaglami | null): boolean {
  return a !== null && b !== null && a.kart === b.kart && a.uyelikId === b.uyelikId;
}

type IslemTuru = "odunc" | "iade" | "bilgi" | "uyari" | "hata";

interface Islem {
  no: number;
  tur: IslemTuru;
  baslik: string;
  ayrinti: string;
}

interface Istem {
  /** baska_uyede: iade al + ödünç ver · bu_uyede ve iade: yalnız iade al. */
  tur: "baska_uyede" | "bu_uyede" | "iade";
  barkod: string;
}

interface Istisna {
  barkod: string;
  ileti: string;
  kitap: string;
}

const ISLEM_GORUNUMU: Record<IslemTuru, { ikon: string; sinif: string }> = {
  odunc: { ikon: "output", sinif: "bg-secondary-container text-on-secondary-container" },
  iade: { ikon: "input", sinif: "bg-secondary-container text-on-secondary-container" },
  bilgi: { ikon: "info", sinif: "bg-surface-container-high text-on-surface" },
  uyari: { ikon: "warning", sinif: "bg-tertiary-container text-on-tertiary-container" },
  hata: { ikon: "error", sinif: "bg-error-container text-on-error-container" },
};

function nushaMetni(copy: MasaNushasi | null | undefined, kod: string): string {
  return copy ? `${copy.barcode_display} — ${copy.work_title}` : `Okutulan: ${kod}`;
}

function kartsizEtiketi(gerekce: KartsizGerekce | null): string {
  return KARTSIZ_GEREKCELER.find((g) => g.value === gerekce)?.label ?? "";
}

export default function DolasimMasasi({
  gorevli,
  beklemede = false,
}: {
  gorevli: boolean;
  /** Ebeveynin diyaloğu açık (ör. yönetici kipine geçiş): okutma kutusu beklemede. */
  beklemede?: boolean;
}) {
  const kutuRef = useRef<HTMLInputElement>(null);
  const [baglam, setBaglam] = useState<UyeBaglami | null>(null);
  const baglamRef = useRef<UyeBaglami | null>(null);
  const [islemler, setIslemler] = useState<Islem[]>([]);
  const [istem, setIstem] = useState<Istem | null>(null);
  const [durumSorgusu, setDurumSorgusu] = useState(false);
  const durumSorgusuRef = useRef(false);
  const [ses, setSes] = useState(okumaSesiAcikMi);
  const [kartKilidi, setKartKilidi] = useState<string | null>(null);
  const [kilitOdakta, setKilitOdakta] = useState(false);
  const [istisna, setIstisna] = useState<Istisna | null>(null);
  const [kartsizAcik, setKartsizAcik] = useState(false);
  const [sonEtkinlik, setSonEtkinlik] = useState(0);
  const sayac = useRef(0);
  // Gerekçeli istisna penceresi açıkken kuyruğun sıradaki okutması BEKLER (pencere
  // kapanınca çözülen söz). Ref ile tutulur: pencereyi açan okutmanın hemen ardından
  // gelen okutma, React yeniden çizmeden önce de beklemeyi görür.
  const pencere = useRef<{ kapandi: Promise<void>; coz: () => void } | null>(null);

  const pencereyiBekle = useCallback(() => {
    if (pencere.current !== null) return;
    let coz: () => void = () => undefined;
    const kapandi = new Promise<void>((r) => {
      coz = r;
    });
    pencere.current = { kapandi, coz };
  }, []);

  const pencereKapandi = useCallback(() => {
    const p = pencere.current;
    pencere.current = null;
    p?.coz();
  }, []);

  // Masa kapanırken bekleyen okutma asılı kalmasın.
  useEffect(() => pencereKapandi, [pencereKapandi]);

  const baglamiYaz = useCallback((yeni: UyeBaglami | null) => {
    baglamRef.current = yeni;
    setBaglam(yeni);
  }, []);

  const ekle = useCallback((tur: IslemTuru, baslik: string, ayrinti = "") => {
    sayac.current += 1;
    const no = sayac.current;
    setIslemler((onceki) => [{ no, tur, baslik, ayrinti }, ...onceki].slice(0, GOSTERILEN_ISLEM));
  }, []);

  const etkinlik = useCallback(() => setSonEtkinlik(Date.now()), []);

  const diyalogAcik = istisna !== null || kartsizAcik;

  // 60 sn işlem yoksa üye bağlamı kapanır (§7.3). Pencere açıkken süre İŞLEMEZ:
  // pencereyi dolduran yönetici işlem yapıyordur; pencere kapanınca süre baştan başlar.
  useEffect(() => {
    if (baglam === null || diyalogAcik) return;
    const zamanlayici = setTimeout(() => {
      baglamiYaz(null);
      setIstem(null);
      ekle("bilgi", BAGLAM_ZAMAN_ASIMI);
    }, BAGLAM_SURESI_MS);
    return () => clearTimeout(zamanlayici);
  }, [baglam, sonEtkinlik, diyalogAcik, baglamiYaz, ekle]);

  const bitti = () => {
    baglamiYaz(null);
    setIstem(null);
    ekle("bilgi", BAGLAM_KAPANDI);
    kutuRef.current?.focus();
  };

  // --- kart ---
  const kartSonucunuIsle = (
    sonuc: KartSonucu,
    kart: string | null,
    kartsiz: { uyelikId: number; gerekce: KartsizGerekce } | null = null,
  ): OkutmaGeriBildirimi => {
    if (sonuc.state !== "FOUND" || sonuc.member === null) {
      // Başka (geçersiz) kart okutuldu: önceki üyenin bağlamı kapanır.
      baglamiYaz(null);
      ekle("hata", sonuc.message);
      return "hata";
    }
    baglamiYaz({
      kart,
      uyelikId: kartsiz?.uyelikId ?? null,
      kartsizGerekce: kartsiz?.gerekce ?? null,
      uye: sonuc.member,
      ileti: sonuc.message,
    });
    ekle("bilgi", "Üye kartı okundu.", gorevli ? "" : sonuc.member.full_name);
    if (durumSorgusuRef.current) {
      // Kart okutmak ödünç niyetidir: durum sorgusu açık kalırsa kitaplar ödünç
      // verilmez ama görevli verildi sanabilir.
      durumSorgusuRef.current = false;
      setDurumSorgusu(false);
      ekle("bilgi", DURUM_SORGUSU_KAPANDI);
    }
    return sonuc.member.remaining_quota > 0 ? "basari" : "uyari";
  };

  const kilitHatasiMi = (e: unknown): e is ApiError =>
    e instanceof ApiError && e.code === RED.kartKilidi;

  const kartOkut = async (kod: string): Promise<OkutmaGeriBildirimi> => {
    try {
      return kartSonucunuIsle(await dolasimApi.kartOku(kod), kod);
    } catch (e) {
      baglamiYaz(null);
      if (kilitHatasiMi(e)) {
        setKartKilidi(e.message);
        ekle("hata", e.message);
        return "hata";
      }
      ekle("hata", hataOku(e, "Kart okunamadı; yeniden okutun.").message);
      return "hata";
    }
  };

  // --- iade (boş bağlam) ---
  const iadeAl = async (kod: string): Promise<OkutmaGeriBildirimi> => {
    try {
      const sonuc = await dolasimApi.iadeAl(kod);
      if (sonuc.result === "returned") {
        const kimden =
          sonuc.loan && !gorevli
            ? ` · ${[sonuc.loan.member_name, sonuc.loan.class_label].filter(Boolean).join(" · ")}`
            : "";
        ekle("iade", sonuc.message, `${nushaMetni(sonuc.copy, kod)}${kimden}`);
        return sonuc.loan && sonuc.loan.overdue_days > 0 ? "uyari" : "basari";
      }
      ekle(
        sonuc.result === "not_on_loan" ? "uyari" : "hata",
        sonuc.message,
        nushaMetni(sonuc.copy, kod),
      );
      return sonuc.result === "not_on_loan" ? "uyari" : "hata";
    } catch (e) {
      ekle("hata", hataOku(e, "İade kaydedilemedi; kitabı yeniden okutun.").message, kod);
      return "hata";
    }
  };

  // --- ödünç (üye bağlamı) ---
  const oduncGovdesi = (b: UyeBaglami, barkod: string): OduncGovdesi =>
    b.kart !== null
      ? { barcode: barkod, card_no: b.kart }
      : {
          barcode: barkod,
          membership_id: b.uyelikId ?? undefined,
          cardless_reason: b.kartsizGerekce ?? undefined,
        };

  const oduncSonucunuYaz = (b: UyeBaglami, sonuc: OduncSonucu) => {
    baglamiYaz({ ...b, uye: { ...b.uye, ...sonuc.member } });
    const ayrinti = `${nushaMetni(sonuc.copy, "")} · İade tarihi ${formatDate(sonuc.due_date)}`;
    ekle("odunc", sonuc.message, gorevli ? ayrinti : `${ayrinti} · ${sonuc.member.full_name}`);
    for (const uyari of sonuc.warnings) ekle("uyari", uyari);
  };

  /** İstisna penceresinde gösterilecek kitap: barkod + ad (ad okunamazsa yalnız barkod). */
  const kitapEtiketi = async (kod: string): Promise<string> => {
    try {
      const durum = await dolasimApi.nushaDurumu(kod);
      if (durum.copy) return `${durum.copy.barcode_display} — ${durum.copy.work_title}`;
    } catch {
      /* ad okunamadı: barkod yeter */
    }
    return barkodBicimle(kod);
  };

  const oduncVer = async (b: UyeBaglami, kod: string): Promise<OkutmaGeriBildirimi> => {
    try {
      const sonuc = await dolasimApi.oduncVer(oduncGovdesi(b, kod));
      oduncSonucunuYaz(b, sonuc);
      return sonuc.warnings.length > 0 ? "uyari" : "basari";
    } catch (e) {
      if (!(e instanceof ApiError)) {
        ekle("hata", "Ödünç kaydedilemedi; kitabı yeniden okutun.", kod);
        return "hata";
      }
      if (e.code === RED.baskaUyede) {
        setIstem({ tur: "baska_uyede", barkod: kod });
        ekle("uyari", BASKA_UYEDE_SORUSU, `Okutulan: ${kod}`);
        return "uyari";
      }
      if (e.code === RED.buUyede) {
        setIstem({ tur: "bu_uyede", barkod: kod });
        ekle("uyari", BU_UYEDE_SORUSU, `Okutulan: ${kod}`);
        return "uyari";
      }
      if (e.code === RED.gecikme && !gorevli) {
        // Kuyruğun sıradaki okutması pencere kapanana dek bekler (pencereyi ezmez).
        pencereyiBekle();
        setIstisna({ barkod: kod, ileti: e.message, kitap: await kitapEtiketi(kod) });
        ekle("uyari", e.message, `Okutulan: ${kod}`);
        return "uyari";
      }
      if (e.code === RED.kartKilidi) {
        baglamiYaz(null);
        setKartKilidi(e.message);
      } else if (UYEYE_BAGLI_RETLER.has(e.code)) {
        // Üyeye bağlı ret: kitap iade için getirilmiş olabilir (§9-8 — sonlanmış üye
        // de iade yapar). İade önerisi kitabın kimde olduğunu söylemez.
        setIstem({ tur: "iade", barkod: kod });
      }
      ekle("hata", e.message, `Okutulan: ${kod}`);
      return "hata";
    }
  };

  // --- nüsha durum sorgusu (yazma yok) ---
  const durumSor = async (kod: string): Promise<OkutmaGeriBildirimi> => {
    try {
      const sonuc = await dolasimApi.nushaDurumu(kod);
      const kimde =
        sonuc.loan && !gorevli
          ? ` · ${sonuc.loan.member_name} · iade tarihi ${formatDate(sonuc.loan.due_date)}`
          : "";
      ekle(sonuc.copy ? "bilgi" : "hata", sonuc.message, `${nushaMetni(sonuc.copy, kod)}${kimde}`);
      // Ayrı ses: ödünç ve iadenin başarı sesiyle karışmasın (yazma yapılmadı).
      return sonuc.copy ? "bilgi" : "hata";
    } catch (e) {
      ekle("hata", hataOku(e, "Nüsha durumu okunamadı.").message, kod);
      return "hata";
    }
  };

  /** Kuyruktan gelen tek okutma — bağlam ref'ten okunur (sıralı işleme). */
  const okut = async (kod: string): Promise<OkutmaGeriBildirimi> => {
    // Gerekçeli istisna penceresi açıksa pencere kapanana dek bekle.
    while (pencere.current !== null) await pencere.current.kapandi;
    setIstem(null);
    etkinlik();
    if (kodTuru(kod) === "MEMBER_CARD") return kartOkut(kod);
    if (durumSorgusuRef.current) return durumSor(kod);
    const b = baglamRef.current;
    return b ? oduncVer(b, kod) : iadeAl(kod);
  };

  // --- istem düğmeleri ("Önce iade alınsın mı?") ---
  const istemiUygula = async () => {
    const aktif = istem;
    if (aktif === null) return;
    // Bağlam düğmeye basıldığı AN yakalanır: iade sürerken okutulan yeni kartın
    // sahibine ödünç verilmez.
    const b = baglamRef.current;
    setIstem(null);
    etkinlik();
    const iade = await dolasimApi.iadeAl(aktif.barkod).catch((e: unknown) => {
      ekle("hata", hataOku(e, "İade kaydedilemedi.").message, aktif.barkod);
      return null;
    });
    if (iade === null || iade.result !== "returned") {
      if (iade) ekle("hata", iade.message, nushaMetni(iade.copy, aktif.barkod));
      kutuRef.current?.focus();
      return;
    }
    ekle("iade", iade.message, nushaMetni(iade.copy, aktif.barkod));
    if (aktif.tur === "baska_uyede") {
      if (b === null || !ayniUye(b, baglamRef.current)) {
        ekle("uyari", ISTEM_BAGLAM_DEGISTI, nushaMetni(iade.copy, aktif.barkod));
      } else {
        ekle("uyari", BASKA_UYEDEN_IADE_UYARISI);
        await oduncVer(b, aktif.barkod);
      }
    }
    kutuRef.current?.focus();
  };

  const istisnaGonder = async (
    gerekce: IstisnaGerekcesi,
    aciklama: string,
  ): Promise<string | null> => {
    const b = baglamRef.current;
    const aktif = istisna;
    if (b === null || aktif === null) return "Üye bağlamı kapandı; üye kartını yeniden okutun.";
    try {
      const sonuc = await dolasimApi.oduncVer({
        ...oduncGovdesi(b, aktif.barkod),
        override_reason: gerekce,
        override_note: aciklama,
      });
      oduncSonucunuYaz(b, sonuc);
      ekle("bilgi", "Gerekçeli istisnayla ödünç verildi.");
      setIstisna(null);
      pencereKapandi();
      etkinlik();
      return null;
    } catch (e) {
      return hataOku(e, "Ödünç kaydedilemedi.").message;
    }
  };

  const son = islemler[0];

  return (
    <div className="space-y-4">
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-title-medium text-on-surface">Okutun</p>
            <p className="max-w-3xl text-body-medium text-on-surface-variant">
              Ödünç için önce üye kartını, sonra kitapların kütüphane etiketini okutun. Üye kartı
              okutmadan okutulan kitabın iadesi alınır. Kitabın arka kapağındaki ISBN barkodunu
              değil, kütüphane etiketini okutun.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!gorevli && (
              <Button
                variant="outlined"
                icon="badge"
                onClick={() => setKartsizAcik(true)}
                disabled={diyalogAcik}
              >
                {KARTSIZ_DUGMESI}
              </Button>
            )}
            <Button
              variant="text"
              icon={ses ? "volume_up" : "volume_off"}
              onClick={() => {
                okumaSesiniAyarla(!ses);
                setSes(!ses);
                kutuRef.current?.focus();
              }}
            >
              {ses ? "Okuma sesi açık" : "Okuma sesi kapalı"}
            </Button>
          </div>
        </div>

        {kartKilidi !== null && (
          <KartKilidiSeridi
            ileti={kartKilidi}
            onOdakIcinde={setKilitOdakta}
            onAcildi={() => {
              setKartKilidi(null);
              setKilitOdakta(false);
              ekle("bilgi", "Kart okutma yeniden açıldı.");
              kutuRef.current?.focus();
            }}
          />
        )}

        <BarcodeInput
          ref={kutuRef}
          className="max-w-xl"
          label={OKUTMA_KUTUSU}
          onOkut={okut}
          beklemede={diyalogAcik || beklemede}
          // Yönetici kilit şeridindeki parola alanına yazarken "kutu odakta değil" uyarısı çıkmaz.
          odakUyarisi={!kilitOdakta}
          placeholder="94718263 · 2026-000123"
          helperText="Okuyucuyla okutun ya da numarayı yazıp Enter'a basın."
        />

        <label className="flex w-fit cursor-pointer items-center gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            className="size-5 accent-primary"
            checked={durumSorgusu}
            onChange={(e) => {
              durumSorgusuRef.current = e.target.checked;
              setDurumSorgusu(e.target.checked);
              kutuRef.current?.focus();
            }}
          />
          {DURUM_SORGUSU}
          <span className="text-body-small text-on-surface-variant">
            (okutulan kitabın durumu gösterilir; ödünç ve iade yapılmaz)
          </span>
        </label>
      </Card>

      {baglam !== null && <UyeKarti baglam={baglam} gorevli={gorevli} onBitti={bitti} />}

      {son && (
        <div
          role="status"
          aria-live="polite"
          className={`flex items-start gap-3 rounded-shape-md px-4 py-3 ${ISLEM_GORUNUMU[son.tur].sinif}`}
        >
          <Icon name={ISLEM_GORUNUMU[son.tur].ikon} size="2xl" className="shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-title-medium">{son.baslik}</p>
            {son.ayrinti && <p className="text-body-medium">{son.ayrinti}</p>}
            {istem && (
              <div className="mt-2 space-y-2">
                {istem.tur === "iade" && <p className="text-body-medium">{IADE_ONERISI}</p>}
                <div className="flex flex-wrap gap-2">
                  <Button icon="input" onClick={() => void istemiUygula()}>
                    {istem.tur === "baska_uyede" ? "İade al ve ödünç ver" : "İade al"}
                  </Button>
                  <Button
                    variant="text"
                    onClick={() => {
                      setIstem(null);
                      kutuRef.current?.focus();
                    }}
                  >
                    Vazgeç
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {islemler.length > 1 && (
        <ol aria-label="Bu ekrandaki son işlemler" className="space-y-1 text-body-small">
          {islemler.slice(1).map((i) => (
            <li key={i.no} className="flex items-start gap-2 text-on-surface-variant">
              <Icon name={ISLEM_GORUNUMU[i.tur].ikon} size="sm" className="mt-0.5 shrink-0" />
              <span>
                {i.baslik}
                {i.ayrinti && ` ${i.ayrinti}`}
              </span>
            </li>
          ))}
        </ol>
      )}

      {!gorevli && (
        <>
          <IstisnaDiyalogu
            open={istisna !== null}
            ileti={istisna?.ileti ?? ""}
            kitap={istisna?.kitap ?? ""}
            onVazgec={() => {
              setIstisna(null);
              pencereKapandi();
              etkinlik();
            }}
            onGonder={istisnaGonder}
          />
          <KartsizOduncDiyalogu
            open={kartsizAcik}
            onVazgec={() => setKartsizAcik(false)}
            onAcildi={(sonuc, uyelikId, gerekce) => {
              setKartsizAcik(false);
              kartSonucunuIsle(sonuc, null, { uyelikId, gerekce });
              etkinlik();
            }}
          />
        </>
      )}
    </div>
  );
}

function UyeKarti({
  baglam,
  gorevli,
  onBitti,
}: {
  baglam: UyeBaglami;
  gorevli: boolean;
  onBitti: () => void;
}) {
  const { uye } = baglam;
  const acik = uye.open_loans ?? [];
  return (
    <Card
      elevation={0}
      className="space-y-3 border border-primary/40 p-[var(--kd-panel-padding)] shadow-elevation-1"
    >
      <section aria-label="Üye bağlamı" className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-label-large text-on-surface-variant">Üye</p>
            <p className="text-headline-small text-on-surface">{uye.full_name}</p>
            {!gorevli && (
              <p className="text-body-medium text-on-surface-variant">
                {[uye.member_type_display, uye.class_label, uye.status_display]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
            <p className="mt-1 text-title-medium text-on-surface">
              Kalan ödünç hakkı: {formatNumber(uye.remaining_quota)}
            </p>
            <p className="text-body-medium text-on-surface-variant">{baglam.ileti}</p>
          </div>
          <Button variant="tonal" icon="check" onClick={onBitti}>
            {BITTI_DUGMESI}
          </Button>
        </div>
        {baglam.kartsizGerekce && (
          <p className="flex items-center gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-medium text-on-tertiary-container">
            <Icon name="badge" size="lg" />
            Kartsız ödünç — gerekçe: {kartsizEtiketi(baglam.kartsizGerekce)}
          </p>
        )}
        {!gorevli && acik.length > 0 && (
          <div className="space-y-1">
            <p className="text-label-large text-on-surface-variant">
              Açık ödünçler: {formatNumber(uye.open_loan_count ?? acik.length)}
            </p>
            <ul className="space-y-1 text-body-medium">
              {acik.map((o) => (
                <li key={o.id} className="flex flex-wrap gap-x-2 text-on-surface">
                  <span className="font-mono">{o.barcode_display}</span>
                  <span>{o.work_title}</span>
                  <span className={o.overdue_days > 0 ? "text-error" : "text-on-surface-variant"}>
                    iade tarihi {formatDate(o.due_date)}
                    {o.overdue_days > 0 && ` · ${formatNumber(o.overdue_days)} gün gecikti`}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="text-body-small text-on-surface-variant">
          60 saniye işlem yapılmazsa, “{BITTI_DUGMESI}” düğmesine basılınca ya da başka bir kart
          okutulunca üye bağlamı kapanır.
        </p>
      </section>
    </Card>
  );
}
