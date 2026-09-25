// Ayıklama teklifinin ayrıntısı (F8; Md. 12/1, D15, tasarım §10 E7).
//
// Adım rayı: Taslak → Komisyona sunuldu → Komisyon kararı → Harcama yetkilisi onayı →
// Uygulandı. Her adımın eylemi yalnız o adımda görünür; kural (hangi geçişin hangi
// durumda yapılabildiği, E7 tablosu, engeller) SUNUCUDADIR ve ret iletisi olduğu gibi
// gösterilir.
//
// Geri dönüşü olmayan iki işlem onay diyaloğundan geçer: "Uygula" (nüshalar kayıttan
// düşülür ya da devredilir — ayrıca ikinci doğrulama kutusu) ve "İptal et" (teklif
// kapanır). Teklifi geri çekmek taslağa döndürür ve sonraki adımların kayıtlarını siler;
// onu da onay sorar.
//
// Belgeler kartı sunucunun `…/documents/` yanıtından kurulur: basılamayan belgenin
// gerekçesi yazılır (ör. "Komisyon kararı bağlandıktan sonra basılır.").

import { useCallback, useEffect, useState } from "react";

import { formatDate, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Stepper from "../../ui/Stepper";
import type { StepperItem, StepperStatus } from "../../ui/Stepper";
import { ayiklamaApi, GEREKCE_BENDI, teklifAdi } from "./api";
import type { AyiklamaBelgesi, Kalem, TeklifAyrintisi as TeklifVerisi, TeklifDurumu } from "./api";
import { BelgeSatiri, Bilgi, Rozet, useKurallar } from "./ortak";
import {
  IptalDiyalogu,
  KalemDuzenleDiyalogu,
  KalemEkleDiyalogu,
  KararBaglaDiyalogu,
  OnayDiyalogu,
} from "./TeklifDiyaloglari";

const ADIMLAR: Array<{ key: TeklifDurumu; label: string; icon: string }> = [
  { key: "DRAFT", label: "Taslak", icon: "edit_note" },
  { key: "SUBMITTED", label: "Komisyona sunuldu", icon: "send" },
  { key: "DECIDED", label: "Komisyon kararı", icon: "gavel" },
  { key: "APPROVED", label: "Harcama yetkilisi onayı", icon: "approval" },
  { key: "APPLIED", label: "Uygulandı", icon: "task_alt" },
];

/** Süren teklifin durumları — geri çekme ve iptal yalnız bunlarda. */
const SUREN: TeklifDurumu[] = ["DRAFT", "SUBMITTED", "DECIDED", "APPROVED"];

type Diyalog = "ekle" | "karar" | "onay" | "iptal" | null;

export default function TeklifAyrintisi({ id, onGeri }: { id: number; onGeri: () => void }) {
  const kurallar = useKurallar();
  const [teklif, setTeklif] = useState<TeklifVerisi | null>(null);
  const [belgeler, setBelgeler] = useState<AyiklamaBelgesi[]>([]);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const [diyalog, setDiyalog] = useState<Diyalog>(null);
  const [duzenlenen, setDuzenlenen] = useState<Kalem | null>(null);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const yukle = useCallback(async () => {
    const [t, b] = await Promise.all([ayiklamaApi.teklif(id), ayiklamaApi.belgeler(id)]);
    setTeklif(t);
    setBelgeler(b);
  }, [id]);

  useEffect(() => {
    let iptal = false;
    Promise.all([ayiklamaApi.teklif(id), ayiklamaApi.belgeler(id)])
      .then(([t, b]) => {
        if (iptal) return;
        setTeklif(t);
        setBelgeler(b);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Ayıklama teklifi yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [id]);

  /** Bir geçişi çalıştırır; sonra teklifi ve belgeleri yeniden okur. */
  const calistir = async (is: () => Promise<unknown>, ileti: string, yedek: string) => {
    setBusy(true);
    setHata(null);
    try {
      await is();
      snackbar.success(ileti);
      await yukle();
    } catch (e) {
      setHata(hataOku(e, yedek));
    } finally {
      setBusy(false);
    }
  };

  if (teklif === null) {
    return (
      <div className="space-y-3">
        <Button variant="text" icon="arrow_back" onClick={onGeri}>
          Tekliflere dön
        </Button>
        {hata ? <ErrorBand hata={hata} /> : <SkeletonList rows={4} />}
      </div>
    );
  }

  const durum = teklif.status;
  const sira = ADIMLAR.findIndex((a) => a.key === durum);
  const adimlar: StepperItem[] = ADIMLAR.map((a, i) => {
    let st: StepperStatus = "upcoming";
    if (durum === "CANCELLED") st = "skipped";
    else if (i < sira || durum === "APPLIED") st = "done";
    else if (i === sira) st = "current";
    return { key: a.key, label: a.label, icon: a.icon, status: st };
  });
  const teklifte = teklif.items.filter((k) => k.state === "PROPOSED");
  const dusulecek = teklif.items.filter((k) => k.state === "PROPOSED" && !k.is_transfer).length;
  const devredilecek = teklif.items.filter((k) => k.state === "PROPOSED" && k.is_transfer).length;

  const sun = async () => {
    const onay = await confirm({
      title: "Teklif komisyona sunulsun mu?",
      message:
        "Kalem listesi kilitlenir; değişiklik için teklifi geri çekmek gerekir. Kitaplar komisyon kararına ve harcama yetkilisinin onayına kadar rafta kalır ve ödünç verilebilir.",
      confirmLabel: "Komisyona sun",
    });
    if (onay) {
      await calistir(
        () => ayiklamaApi.sun(teklif.id),
        "Teklif komisyona sunuldu.",
        "Teklif komisyona sunulamadı.",
      );
    }
  };

  const geriCek = async () => {
    const onay = await confirm({
      title: "Teklif geri çekilsin mi?",
      message:
        "Teklif taslağa döner. Bağlanan komisyon kararı, harcama yetkilisinin onayı ve dışarıda bırakılan kalemlerin işaretleri silinir; kalemler kalır.",
      confirmLabel: "Geri çek",
    });
    if (onay) {
      await calistir(
        () => ayiklamaApi.geriCek(teklif.id),
        "Teklif geri çekildi; taslağa döndü.",
        "Teklif geri çekilemedi.",
      );
    }
  };

  const uygula = async () => {
    const onay = await confirm({
      title: "Teklif uygulansın mı?",
      message: `${formatNumber(dusulecek)} nüsha “Ayıklandı (kayıttan düşüldü)”, ${formatNumber(
        devredilecek,
      )} nüsha “Devredildi” olur. Nüshalar katalogdan ve Ağ Kataloğundan çıkar, kayıt defterinde kalır. İşlem geri alınamaz.`,
      confirmLabel: "Uygula",
      acknowledgeLabel: "Harcama yetkilisinin onayını ve belgelerin imzalandığını denetledim.",
    });
    if (!onay) return;
    setBusy(true);
    setHata(null);
    try {
      const sonuc = await ayiklamaApi.uygula(teklif.id);
      snackbar.success(
        `Teklif uygulandı: ${formatNumber(sonuc.withdrawn)} nüsha kayıttan düşüldü, ${formatNumber(
          sonuc.transferred,
        )} nüsha devredildi.`,
      );
      await yukle();
    } catch (e) {
      setHata(hataOku(e, "Teklif uygulanamadı."));
    } finally {
      setBusy(false);
    }
  };

  const sil = async () => {
    const onay = await confirm({
      title: "Taslak teklif silinsin mi?",
      message: "Teklif ve kalemleri kaldırılır; nüshalara dokunulmaz.",
      confirmLabel: "Sil",
    });
    if (!onay) return;
    setBusy(true);
    try {
      await ayiklamaApi.teklifSil(teklif.id);
      snackbar.success("Taslak teklif silindi.");
      onGeri();
    } catch (e) {
      setHata(hataOku(e, "Teklif silinemedi."));
      setBusy(false);
    }
  };

  const cikar = async (kalem: Kalem) => {
    await calistir(
      () => ayiklamaApi.kalemCikar(teklif.id, kalem.id),
      "Kalem tekliften çıkarıldı.",
      "Kalem çıkarılamadı.",
    );
  };

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="text" icon="arrow_back" onClick={onGeri}>
          Tekliflere dön
        </Button>
      </div>

      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="text-title-large font-semibold text-on-surface">{teklifAdi(teklif)}</h2>
          <Rozet ton={durum === "APPLIED" ? "ikincil" : "notr"}>{teklif.status_display}</Rozet>
        </div>
        <Stepper items={adimlar} ariaLabel="Teklif adımları" />
        {durum === "CANCELLED" && (
          <p className="rounded-shape-sm bg-surface-container px-3 py-2 text-body-medium text-on-surface">
            Teklif {formatDate(teklif.cancelled_at)} tarihinde iptal edildi
            {teklif.cancel_reason ? `: ${teklif.cancel_reason}` : "."} Nüshalara dokunulmadı.
          </p>
        )}
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Bilgi etiket="Ders yılı">{teklif.school_year_name}</Bilgi>
          <Bilgi etiket="Kalem">
            {`${formatNumber(teklif.counts.items)} (kayıttan düşme ${formatNumber(
              teklif.counts.write_off,
            )}, devir ${formatNumber(teklif.counts.transfer)})`}
          </Bilgi>
          <Bilgi etiket="Komisyon kararı">
            {teklif.decision
              ? `${formatDate(teklif.decision.decision_date)}${
                  teklif.decision.decision_no ? ` · ${teklif.decision.decision_no}` : ""
                }`
              : "—"}
          </Bilgi>
          <Bilgi etiket="Harcama yetkilisinin onayı">
            {teklif.approved_on
              ? `${teklif.approved_by_name} · ${formatDate(teklif.approved_on)}`
              : "—"}
          </Bilgi>
          {teklif.tmy_commission_members && (
            <Bilgi etiket="Komisyon üyeleri">
              {teklif.tmy_commission_members.split("\n").filter(Boolean).join(" · ")}
            </Bilgi>
          )}
          {teklif.destruction_decided && <Bilgi etiket="İmha kararı">Var (TMY 28/5)</Bilgi>}
          {teklif.applied_at && <Bilgi etiket="Uygulanma">{formatDate(teklif.applied_at)}</Bilgi>}
        </dl>

        {hata && <ErrorBand hata={hata} />}

        <div className="flex flex-wrap gap-2">
          {durum === "DRAFT" && (
            <>
              <Button icon="add" onClick={() => setDiyalog("ekle")} disabled={busy}>
                Kalem ekle
              </Button>
              <Button
                variant="tonal"
                icon="send"
                onClick={() => void sun()}
                disabled={busy || teklif.items.length === 0}
              >
                Komisyona sun
              </Button>
              <Button variant="text" icon="delete" onClick={() => void sil()} disabled={busy}>
                Teklifi sil
              </Button>
            </>
          )}
          {durum === "SUBMITTED" && (
            <Button icon="gavel" onClick={() => setDiyalog("karar")} disabled={busy}>
              Komisyon kararını bağla
            </Button>
          )}
          {durum === "DECIDED" && (
            <Button icon="approval" onClick={() => setDiyalog("onay")} disabled={busy}>
              Harcama yetkilisinin onayını işle
            </Button>
          )}
          {durum === "APPROVED" && (
            <Button icon="task_alt" onClick={() => void uygula()} disabled={busy}>
              Uygula
            </Button>
          )}
          {(durum === "SUBMITTED" || durum === "DECIDED" || durum === "APPROVED") && (
            <Button variant="outlined" icon="undo" onClick={() => void geriCek()} disabled={busy}>
              Teklifi geri çek
            </Button>
          )}
          {SUREN.includes(durum) && (
            <Button
              variant="text"
              icon="cancel"
              onClick={() => setDiyalog("iptal")}
              disabled={busy}
            >
              İptal et
            </Button>
          )}
        </div>
      </Card>

      <section aria-labelledby="kalemler-baslik" className="space-y-3">
        <h2 id="kalemler-baslik" className="text-title-medium font-semibold text-on-surface">
          Kalemler
        </h2>
        {teklif.items.length === 0 ? (
          <EmptyState
            compact
            icon="list_alt"
            title="Teklifte kalem yok."
            description="“Kalem ekle” ile aday nüshaları seçin ya da kütüphane etiketlerini okutun."
          />
        ) : (
          <KalemTablosu
            kalemler={teklif.items}
            durum={durum}
            busy={busy}
            onDuzenle={setDuzenlenen}
            onCikar={(k) => void cikar(k)}
          />
        )}
      </section>

      <Card elevation={0} className="shadow-elevation-1">
        <div className="border-b border-outline-variant/60 px-4 py-3">
          <h2 className="text-title-medium font-semibold text-on-surface">Ayıklama Belgeleri</h2>
          <p className="text-body-small text-on-surface-variant">
            Belgeler Taşınır Mal Yönetmeliği yoluna göre basılır. Kayıttan Düşme Teklif ve Onay
            Tutanağı ve Varlık İşlem Fişi Taşınır Kayıt ve Yönetim Sistemi&apos;nde (TKYS)
            düzenlenir; buradaki çıktılar onların hazırlığıdır.
          </p>
        </div>
        <ul className="divide-y divide-outline-variant/50">
          {belgeler.map((b) => (
            <BelgeSatiri
              key={b.kind}
              ad={b.title}
              basilabilir={b.available}
              gerekce={b.reason}
              pdfAl={() => ayiklamaApi.belge(teklif.id, b.kind)}
              excelAl={
                b.formats.includes("xlsx")
                  ? () => ayiklamaApi.belge(teklif.id, b.kind, "xlsx")
                  : undefined
              }
            />
          ))}
        </ul>
      </Card>

      {diyalog === "ekle" && (
        <KalemEkleDiyalogu
          teklifId={teklif.id}
          kurallar={kurallar}
          onClose={() => setDiyalog(null)}
          onEklendi={(adet) => {
            setDiyalog(null);
            snackbar.success(`${formatNumber(adet)} kalem eklendi.`);
            void yukle();
          }}
        />
      )}
      {diyalog === "karar" && (
        <KararBaglaDiyalogu
          teklifId={teklif.id}
          kalemler={teklifte}
          onClose={() => setDiyalog(null)}
          onBaglandi={() => {
            setDiyalog(null);
            snackbar.success("Komisyon kararı bağlandı.");
            void yukle();
          }}
        />
      )}
      {diyalog === "onay" && (
        <OnayDiyalogu
          teklif={teklif}
          kalemler={teklifte}
          onClose={() => setDiyalog(null)}
          onOnaylandi={() => {
            setDiyalog(null);
            snackbar.success("Harcama yetkilisinin onayı işlendi.");
            void yukle();
          }}
        />
      )}
      {diyalog === "iptal" && (
        <IptalDiyalogu
          teklifId={teklif.id}
          onClose={() => setDiyalog(null)}
          onIptal={() => {
            setDiyalog(null);
            snackbar.success("Teklif iptal edildi.");
            void yukle();
          }}
        />
      )}
      {duzenlenen !== null && (
        <KalemDuzenleDiyalogu
          teklifId={teklif.id}
          kalem={duzenlenen}
          taslak={durum === "DRAFT"}
          kurallar={kurallar}
          onClose={() => setDuzenlenen(null)}
          onKaydedildi={() => {
            setDuzenlenen(null);
            snackbar.success("Kalem güncellendi.");
            void yukle();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Kalem tablosu
// ---------------------------------------------------------------------------

function KalemTablosu({
  kalemler,
  durum,
  busy,
  onDuzenle,
  onCikar,
}: {
  kalemler: Kalem[];
  durum: TeklifDurumu;
  busy: boolean;
  onDuzenle: (kalem: Kalem) => void;
  onCikar: (kalem: Kalem) => void;
}) {
  const taslak = durum === "DRAFT";
  const kurumDuzeltilir = durum === "SUBMITTED" || durum === "DECIDED";
  return (
    <Card elevation={0} className="overflow-x-auto p-0 shadow-elevation-1 scrollbar-thin">
      <table className="w-full min-w-table border-collapse text-body-small">
        <thead className="bg-surface-container-low">
          <tr className="border-b border-outline-variant text-left text-label-medium text-on-surface-variant">
            <th className="px-4 py-3 font-semibold">Barkod</th>
            <th className="px-4 py-3 font-semibold">Kaynak adı</th>
            <th className="px-4 py-3 font-semibold">Gerekçe</th>
            <th className="px-4 py-3 font-semibold">TMY yolu</th>
            <th className="px-4 py-3 font-semibold">Kalem durumu</th>
            <th className="px-4 py-3 font-semibold">
              <span className="sr-only">Eylemler</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {kalemler.map((k) => (
            <tr key={k.id} className="border-t border-outline-variant/50 align-top">
              <td className="whitespace-nowrap px-4 py-3 font-mono">{k.barcode_display}</td>
              <td className="px-4 py-3">
                <p className="text-on-surface">{k.work_title}</p>
                {k.work_authors && <p className="text-on-surface-variant">{k.work_authors}</p>}
                {k.copy_is_rare && k.state === "PROPOSED" && (
                  <p className="mt-1">
                    <Rozet ton="hata" icon="warning">
                      Nadir eser — ayıklanamaz
                    </Rozet>
                  </p>
                )}
              </td>
              <td className="px-4 py-3">
                <p>
                  {k.reason_display}{" "}
                  <span className="text-on-surface-variant">({GEREKCE_BENDI[k.reason]})</span>
                </p>
                {k.criterion_display && (
                  <p className="text-on-surface-variant">{k.criterion_display}</p>
                )}
              </td>
              <td className="px-4 py-3">
                <p>{k.tmy_path_display}</p>
                {k.is_transfer && (
                  <p className="text-on-surface-variant">
                    {k.transfer_target ? (
                      `Devralacak: ${k.transfer_target}`
                    ) : (
                      <span className="inline-flex items-center gap-1 text-error">
                        <Icon name="warning" size="sm" />
                        Devralacak kurum yazılmadı
                      </span>
                    )}
                  </p>
                )}
              </td>
              <td className="px-4 py-3">
                <p>{k.state_display}</p>
                {k.exclusion_reason && (
                  <p className="text-on-surface-variant">{k.exclusion_reason}</p>
                )}
                {k.destruction_decided && (
                  <p className="text-on-surface-variant">İmha kararı (TMY 28/5)</p>
                )}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-right">
                {(taslak || (kurumDuzeltilir && k.is_transfer && k.state === "PROPOSED")) && (
                  <Button
                    variant="text"
                    icon="edit"
                    onClick={() => onDuzenle(k)}
                    disabled={busy}
                    aria-label={`${k.work_title} kalemini düzenle`}
                  >
                    {taslak ? "Düzenle" : "Devralacak kurum"}
                  </Button>
                )}
                {taslak && (
                  <Button
                    variant="text"
                    icon="close"
                    onClick={() => onCikar(k)}
                    disabled={busy}
                    aria-label={`${k.work_title} kalemini çıkar`}
                  >
                    Çıkar
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
