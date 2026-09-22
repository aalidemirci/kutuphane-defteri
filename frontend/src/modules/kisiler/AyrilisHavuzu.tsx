// Ayrılış Havuzu (Kişiler → `?tab=havuz`) — tasarım §6.1, §8.3, F1 eki 7.
//
// Kullanıcı kararı (22.09.2026): e-Okul aktarımı kimseyi ayırmaz ve silmez. Listede
// bulunmayan aktif öğrenci ve personel burada bekler; durumları aktif kalır. Karar
// yöneticinindir, tek tek ya da toplu:
//   - "Ayrıldı olarak işaretle" (onay diyaloğu): okuldan ayrılmış sayılır, kaydı
//     SİLİNMEZ (iade etmediği kitap izlenebilsin), "Ayrıldı · gg.aa.yyyy" rozetiyle kalır.
//   - "Aktif kalsın": yalnız havuzdan çıkar; sonraki listede yine yoksa geri gelir.
// Yıl sonu mezunları sınıf süzgeciyle seçilip toplu ayrılır. Personelde "olası aynı
// kişi" (ör. soyadı değişimi) adayları gösterilir, onaylı "Birleştir" buradan da yapılır.
//
// Karar tek işlemdir: seçilenlerden biri başka pencerede çözülmüşse backend hiçbir
// kararı uygulamaz (400) — liste yenilenir, kullanıcı yeniden seçer. Adlar yalnız bu
// yönetim ekranında görünür; ekran görevli kipinde kapalıdır.

import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { formatDate, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { MEMBER_KIND_TR, okulApi } from "../okul/api";
import type {
  LeavePool,
  LeavePoolPersonnel,
  LeavePoolRun,
  LeavePoolSimilar,
  LeavePoolStudent,
} from "../okul/api";
import { ErrorBand, hataOku } from "./ortak";
import type { SayfaHatasi } from "./ortak";

const TH = "p-2 text-left text-label-medium text-on-surface-variant";
const TD = "p-2 align-top text-on-surface";

/** Aktarım sütunu: dosya adı; pano yapıştırmasında dosya adı yoktur. */
function aktarimAdi(run: LeavePoolRun | null): string {
  if (run === null) return "—";
  return run.file_name || "Yapıştırılan liste";
}

/** Sınıf süzgecinin seçeneği: sınıfsız öğrenciler tek başlık altında toplanır. */
function sinifEtiketi(ogrenci: { class_label: string }): string {
  return ogrenci.class_label || "Sınıfsız";
}

/** Seçim kümesinden yalnız hâlâ listede olanları bırakır (liste yenilenince). */
function kesisim(secili: Set<number>, kimlikler: number[]): Set<number> {
  const var_ = new Set(kimlikler);
  return new Set([...secili].filter((id) => var_.has(id)));
}

export default function AyrilisHavuzu({ onDegisti }: { onDegisti?: () => void }) {
  const [havuz, setHavuz] = useState<LeavePool | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [ogrenciSecimi, setOgrenciSecimi] = useState<Set<number>>(new Set());
  const [personelSecimi, setPersonelSecimi] = useState<Set<number>>(new Set());
  const [sinif, setSinif] = useState("");
  const [yenile, setYenile] = useState(0);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    okulApi
      .getLeavePool()
      .then((veri) => {
        if (iptal) return;
        setHavuz(veri);
        // Süzgeç listeyle birlikte tazelenir: 12/A'yı toplu ayırınca o seçenek
        // listeden düşer; süzgeç bayat kalsaydı tablo boş görünür, seçici ise
        // eşleşen seçenek bulamadığı için "Tümü" yazardı (süzgeç görünmez olurdu).
        const etiketler = veri.students.map(sinifEtiketi);
        setSinif((s) => (s && !etiketler.includes(s) ? "" : s));
        setOgrenciSecimi((s) =>
          kesisim(
            s,
            veri.students.map((o) => o.id),
          ),
        );
        setPersonelSecimi((s) =>
          kesisim(
            s,
            veri.personnel.map((p) => p.id),
          ),
        );
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Ayrılış havuzu yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [yenile]);

  const tazele = useCallback(() => setYenile((k) => k + 1), []);

  const siniflar = useMemo(() => {
    const etiketler: string[] = [];
    for (const o of havuz?.students ?? []) {
      const etiket = sinifEtiketi(o);
      if (!etiketler.includes(etiket)) etiketler.push(etiket);
    }
    return etiketler; // backend sırası: sınıf, şube (Türk alfabesi)
  }, [havuz]);

  const gorunenOgrenciler = useMemo(
    () => (havuz?.students ?? []).filter((o) => !sinif || sinifEtiketi(o) === sinif),
    [havuz, sinif],
  );

  /** Kararı uygular; başarıda listeyi ve seçimi yeniler. */
  const uygula = async (
    tur: "students" | "personnel",
    eylem: "leave" | "keep",
    kimlikler: number[],
  ) => {
    setMesgul(true);
    setHata(null);
    try {
      const sonuc = await okulApi.resolveLeavePool({ [tur]: { [eylem]: kimlikler } });
      const sayi =
        tur === "students"
          ? eylem === "leave"
            ? sonuc.students_left
            : sonuc.students_kept
          : eylem === "leave"
            ? sonuc.personnel_left
            : sonuc.personnel_kept;
      const kisi = tur === "students" ? "öğrenci" : "kişi";
      snackbar.success(
        eylem === "leave"
          ? `${formatNumber(sayi)} ${kisi} ayrıldı olarak işaretlendi.`
          : `${formatNumber(sayi)} ${kisi} aktif kalacak; havuzdan çıkarıldı.`,
      );
      if (tur === "students") setOgrenciSecimi(new Set());
      else setPersonelSecimi(new Set());
      onDegisti?.();
    } catch (e) {
      setHata(hataOku(e, "Karar uygulanamadı."));
    } finally {
      setMesgul(false);
      tazele();
    }
  };

  const ayril = async (tur: "students" | "personnel") => {
    const kimlikler = [...(tur === "students" ? ogrenciSecimi : personelSecimi)];
    if (kimlikler.length === 0) return;
    const ogrenci = tur === "students";
    const ok = await confirm({
      title: ogrenci
        ? `${formatNumber(kimlikler.length)} öğrenci ayrıldı olarak işaretlensin mi?`
        : `${formatNumber(kimlikler.length)} kişi ayrıldı olarak işaretlensin mi?`,
      message: `Seçilen ${ogrenci ? "öğrenciler" : "kişiler"} okuldan ayrılmış sayılır ve seçicilerden düşer. Kayıtları silinmez; sicilde “Ayrıldı · gg.aa.yyyy” rozetiyle kalır, iade etmedikleri kitap varsa izlenebilir. Sonraki bir e-Okul listesinde yeniden görünen kişinin kaydı yeniden aktif olur.`,
      confirmLabel: "Ayrıldı olarak işaretle",
    });
    if (!ok) return;
    await uygula(tur, "leave", kimlikler);
  };

  const kalsin = async (tur: "students" | "personnel") => {
    const kimlikler = [...(tur === "students" ? ogrenciSecimi : personelSecimi)];
    if (kimlikler.length === 0) return;
    await uygula(tur, "keep", kimlikler);
  };

  const birlestir = async (kisi: LeavePoolPersonnel, aday: LeavePoolSimilar) => {
    const ok = await confirm({
      title: "Kayıtlar birleştirilsin mi?",
      message: `“${kisi.full_name}” kaydının kütüphane bağları “${aday.full_name}” kaydına taşınır ve eski kayıt silinir. Bu işlem geri alınamaz.`,
      confirmLabel: "Birleştir",
    });
    if (!ok) return;
    setMesgul(true);
    setHata(null);
    try {
      await okulApi.mergePersonnel(kisi.id, aday.id);
      snackbar.success("Kayıtlar birleştirildi.");
      onDegisti?.();
    } catch (e) {
      setHata(hataOku(e, "Kayıtlar birleştirilemedi."));
    } finally {
      setMesgul(false);
      tazele();
    }
  };

  const bos = havuz !== null && havuz.student_count === 0 && havuz.personnel_count === 0;

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div>
        <h2 className="text-title-medium text-on-surface">Ayrılış Havuzu</h2>
        <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">
          e-Okul aktarımı kimseyi ayırmaz ve kimsenin kaydını silmez. Listede bulunmayan öğrenci,
          öğretmen ve diğer personel burada bekler; durumları aktif kalır. Okuldan ayrılanlar için
          “Ayrıldı olarak işaretle”yi, okulda kalanlar için “Aktif kalsın”ı seçin. Ayrılan kişinin
          kaydı silinmez: iade etmediği kitap varsa izlenebilir.
        </p>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor && havuz === null ? (
        <SkeletonList rows={4} />
      ) : bos ? (
        <EmptyState
          icon="task_alt"
          title="Ayrılış kararı bekleyen kişi yok"
          description="e-Okul aktarımında listede bulunmayan kişiler burada görünür."
        />
      ) : havuz !== null ? (
        <>
          {havuz.students.length > 0 && (
            <OgrenciBolumu
              ogrenciler={gorunenOgrenciler}
              toplam={havuz.student_count}
              siniflar={siniflar}
              sinif={sinif}
              onSinif={setSinif}
              secim={ogrenciSecimi}
              onSecim={setOgrenciSecimi}
              mesgul={mesgul}
              onAyril={() => void ayril("students")}
              onKalsin={() => void kalsin("students")}
            />
          )}
          {havuz.personnel.length > 0 && (
            <PersonelBolumu
              kisiler={havuz.personnel}
              secim={personelSecimi}
              onSecim={setPersonelSecimi}
              mesgul={mesgul}
              onAyril={() => void ayril("personnel")}
              onKalsin={() => void kalsin("personnel")}
              onBirlestir={(kisi, aday) => void birlestir(kisi, aday)}
            />
          )}
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ortak parçalar
// ---------------------------------------------------------------------------

function degistir(secim: Set<number>, id: number, secili: boolean): Set<number> {
  const yeni = new Set(secim);
  if (secili) yeni.add(id);
  else yeni.delete(id);
  return yeni;
}

/** Seçim sayısı + iki toplu eylem (seçim yokken kapalı). */
function KararCubugu({
  seciliSayi,
  birim,
  mesgul,
  onAyril,
  onKalsin,
}: {
  seciliSayi: number;
  birim: string;
  mesgul: boolean;
  onAyril: () => void;
  onKalsin: () => void;
}) {
  const kapali = mesgul || seciliSayi === 0;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-body-small text-on-surface-variant" aria-live="polite">
        {seciliSayi === 0
          ? `Karar vermek için ${birim} seçin.`
          : `${formatNumber(seciliSayi)} ${birim} seçili.`}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="tonal" icon="how_to_reg" onClick={onKalsin} disabled={kapali}>
          Aktif kalsın
        </Button>
        <Button icon="logout" onClick={onAyril} disabled={kapali}>
          Ayrıldı olarak işaretle
        </Button>
      </div>
    </div>
  );
}

/** Tablo başlığındaki "görünenlerin tümünü seç" kutusu (kısmi seçimde belirsiz). */
function TumunuSec({
  kimlikler,
  secim,
  onSecim,
  etiket,
}: {
  kimlikler: number[];
  secim: Set<number>;
  onSecim: (s: Set<number>) => void;
  etiket: string;
}) {
  const secilen = kimlikler.filter((id) => secim.has(id)).length;
  const hepsi = kimlikler.length > 0 && secilen === kimlikler.length;
  return (
    <input
      type="checkbox"
      aria-label={etiket}
      checked={hepsi}
      ref={(el) => {
        if (el) el.indeterminate = secilen > 0 && !hepsi;
      }}
      onChange={(e) => {
        const yeni = new Set(secim);
        for (const id of kimlikler) {
          if (e.target.checked) yeni.add(id);
          else yeni.delete(id);
        }
        onSecim(yeni);
      }}
      className="size-5 accent-primary"
    />
  );
}

// ---------------------------------------------------------------------------
// Öğrenciler
// ---------------------------------------------------------------------------

function OgrenciBolumu({
  ogrenciler,
  toplam,
  siniflar,
  sinif,
  onSinif,
  secim,
  onSecim,
  mesgul,
  onAyril,
  onKalsin,
}: {
  ogrenciler: LeavePoolStudent[];
  toplam: number;
  siniflar: string[];
  sinif: string;
  onSinif: (s: string) => void;
  secim: Set<number>;
  onSecim: (s: Set<number>) => void;
  mesgul: boolean;
  onAyril: () => void;
  onKalsin: () => void;
}) {
  const baslikId = useId();
  return (
    <section aria-labelledby={baslikId}>
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)]">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h3 id={baslikId} className="text-title-small text-on-surface">
            Öğrenciler ({formatNumber(toplam)})
          </h3>
          <Select
            className="w-44"
            label="Sınıf"
            placeholder="Tümü"
            value={sinif}
            onChange={(e) => onSinif(e.target.value)}
            options={siniflar.map((s) => ({ value: s, label: s }))}
            helperText="Yıl sonunda mezun sınıfları seçip toplu ayırabilirsiniz."
          />
        </div>
        <KararCubugu
          seciliSayi={secim.size}
          birim="öğrenci"
          mesgul={mesgul}
          onAyril={onAyril}
          onKalsin={onKalsin}
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-body-small">
            <caption className="sr-only">Ayrılış kararı bekleyen öğrenciler</caption>
            <thead>
              <tr className="border-b border-outline-variant">
                <th className={TH}>
                  <TumunuSec
                    kimlikler={ogrenciler.map((o) => o.id)}
                    secim={secim}
                    onSecim={onSecim}
                    etiket="Görünen öğrencilerin tümünü seç"
                  />
                </th>
                <th className={TH}>Okul no</th>
                <th className={TH}>Ad soyad</th>
                <th className={TH}>Sınıf</th>
                <th className={TH}>Havuza giriş</th>
                <th className={TH}>Aktarım</th>
              </tr>
            </thead>
            <tbody>
              {ogrenciler.map((o) => (
                <tr key={o.id} className="border-t border-outline-variant/50">
                  <td className={TD}>
                    <input
                      type="checkbox"
                      aria-label={`${o.full_name} seç`}
                      checked={secim.has(o.id)}
                      onChange={(e) => onSecim(degistir(secim, o.id, e.target.checked))}
                      className="size-5 accent-primary"
                    />
                  </td>
                  <td className={TD}>{o.student_number || "—"}</td>
                  <td className={TD}>{o.full_name}</td>
                  <td className={TD}>{o.class_label || "Sınıfsız"}</td>
                  <td className={TD}>{formatDate(o.leave_candidate_since)}</td>
                  <td className={TD}>{aktarimAdi(o.run)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Öğretmenler ve diğer personel
// ---------------------------------------------------------------------------

function PersonelBolumu({
  kisiler,
  secim,
  onSecim,
  mesgul,
  onAyril,
  onKalsin,
  onBirlestir,
}: {
  kisiler: LeavePoolPersonnel[];
  secim: Set<number>;
  onSecim: (s: Set<number>) => void;
  mesgul: boolean;
  onAyril: () => void;
  onKalsin: () => void;
  onBirlestir: (kisi: LeavePoolPersonnel, aday: LeavePoolSimilar) => void;
}) {
  const baslikId = useId();
  const ciftVar = kisiler.some((k) => k.similar.length > 0);
  return (
    <section aria-labelledby={baslikId}>
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)]">
        <h3 id={baslikId} className="text-title-small text-on-surface">
          Öğretmenler ve Diğer Personel ({formatNumber(kisiler.length)})
        </h3>
        {ciftVar && (
          <p className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container">
            <Icon name="info" />
            <span>
              “Olası aynı kişi” sütunundaki kayıt listede yeni adla görünen aynı kişi olabilir (ör.
              soyadı değişimi). Öyleyse ayrıldı diye işaretlemeyin; “Birleştir” ile eski kaydın
              kütüphane bağlarını yeni kayda taşıyın. Adaylar yalnız ad benzerliğine göre
              listelenir: okula yeni gelen bir adaş da burada görünebilir. Birleştirmeden önce aynı
              kişi olduğunu doğrulayın; birleştirme geri alınamaz.
            </span>
          </p>
        )}
        <KararCubugu
          seciliSayi={secim.size}
          birim="kişi"
          mesgul={mesgul}
          onAyril={onAyril}
          onKalsin={onKalsin}
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-body-small">
            <caption className="sr-only">
              Ayrılış kararı bekleyen öğretmen ve diğer personel
            </caption>
            <thead>
              <tr className="border-b border-outline-variant">
                <th className={TH}>
                  <TumunuSec
                    kimlikler={kisiler.map((k) => k.id)}
                    secim={secim}
                    onSecim={onSecim}
                    etiket="Bütün kişileri seç"
                  />
                </th>
                <th className={TH}>Ad soyad</th>
                <th className={TH}>Üye türü</th>
                <th className={TH}>Havuza giriş</th>
                <th className={TH}>Aktarım</th>
                <th className={TH}>Olası aynı kişi</th>
              </tr>
            </thead>
            <tbody>
              {kisiler.map((k) => (
                <tr key={k.id} className="border-t border-outline-variant/50">
                  <td className={TD}>
                    <input
                      type="checkbox"
                      aria-label={`${k.full_name} seç`}
                      checked={secim.has(k.id)}
                      onChange={(e) => onSecim(degistir(secim, k.id, e.target.checked))}
                      className="size-5 accent-primary"
                    />
                  </td>
                  <td className={TD}>{k.full_name}</td>
                  <td className={TD}>{MEMBER_KIND_TR[k.member_kind]}</td>
                  <td className={TD}>{formatDate(k.leave_candidate_since)}</td>
                  <td className={TD}>{aktarimAdi(k.run)}</td>
                  <td className={TD}>
                    {k.similar.length === 0 ? (
                      "—"
                    ) : (
                      <ul className="space-y-1">
                        {k.similar.map((aday) => (
                          <li key={aday.id} className="flex flex-wrap items-center gap-2">
                            <span>{aday.full_name}</span>
                            <Button
                              variant="text"
                              icon="merge"
                              disabled={mesgul}
                              onClick={() => onBirlestir(k, aday)}
                              aria-label={`${k.full_name} kaydını ${aday.full_name} kaydıyla birleştir`}
                            >
                              Birleştir
                            </Button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </section>
  );
}
