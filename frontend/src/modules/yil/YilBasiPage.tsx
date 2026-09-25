// Yıl Başı (F7; tasarım §8.3). Adım adım ekran: ders yılı → yeni e-Okul listeleri →
// mutabakat (Ayrılış Havuzu) → kapalı günler. Her adım durumunu gösterir ve işin
// yapıldığı ekrana bağlanır; bu ekran KAYIT YAZMAZ. Genel Bakış'ta yıl başı
// penceresinde kart çıkar; İlişik Listesi sayfasının sağ üstündeki bağlantıyla her
// zaman açılır. YALNIZ yönetici kipinde.
//
// "Yıl devri" işlemi YOKTUR (tasarım §8.3 — `year_rollover` alınmadı): sınıf atlama
// ve mezunların ayrılışı e-Okul aktarımı ve Ayrılış Havuzu kararıyla olur. Aktarım
// kimseyi ayırmaz ve kimsenin kaydını silmez (F1 eki 7).

import { useState } from "react";
import type { ReactNode } from "react";

import { formatDate, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import Stepper from "../../ui/Stepper";
import type { StepperItem } from "../../ui/Stepper";
import { HAVUZ_ADRESI } from "../kisiler/ortak";
import { ILISIK_LISTESI_ADRESI, YIL_BASI_BASLIGI, YIL_SONU_ADRESI } from "./api";
import type { YilBasiAdimi, YilBasiOzeti } from "./api";
import { AdimBasligi, MetinBaglantisi, useYilAkislari, YanEkranBaglantilari } from "./ortak";

const ADIMLAR: Array<{ key: YilBasiAdimi; label: string; icon: string }> = [
  { key: "school_year", label: "Ders Yılı", icon: "calendar_month" },
  { key: "import", label: "e-Okul Listeleri", icon: "upload_file" },
  { key: "leave_pool", label: "Ayrılış Havuzu", icon: "pending_actions" },
  { key: "closed_days", label: "Kapalı Günler", icon: "event_busy" },
];

function Not({ children, ikon = "info" }: { children: ReactNode; ikon?: string }) {
  return (
    <p className="flex items-start gap-2 rounded-shape-sm bg-surface-container-high px-3 py-2 text-body-small text-on-surface">
      <Icon name={ikon} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

function Uyari({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container">
      <Icon name="warning" className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

export default function YilBasiPage() {
  const { akislar, hata } = useYilAkislari();
  const [adim, setAdim] = useState(0);
  const ozet = akislar?.year_start ?? null;

  const items: StepperItem[] = ADIMLAR.map((a, i) => ({
    key: a.key,
    label: a.label,
    icon: a.icon,
    status: i === adim ? "current" : ozet?.steps[a.key] ? "done" : "upcoming",
  }));

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">{YIL_BASI_BASLIGI}</h1>
          <p className="kd-page-description max-w-4xl">
            Yeni ders yılına hazırlık, adım adım: ders yılı, yeni e-Okul listeleri, Ayrılış Havuzu
            kararları ve kapalı günler. Her adım işin yapıldığı ekrana götürür.
          </p>
        </div>
        <YanEkranBaglantilari
          baglantilar={[
            { to: ILISIK_LISTESI_ADRESI, label: "İlişik Listesi", icon: "fact_check" },
            { to: YIL_SONU_ADRESI, label: "Yıl Sonu", icon: "event_upcoming" },
          ]}
        />
      </div>

      <Card elevation={0} className="p-[var(--kd-panel-padding)] shadow-elevation-1">
        <Stepper items={items} ariaLabel="Yıl başı adımları" onSelect={(_, i) => setAdim(i)} />
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {ozet === null ? (
        !hata && <SkeletonList rows={4} />
      ) : (
        <>
          <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
            {adim === 0 && <DersYiliAdimi ozet={ozet} />}
            {adim === 1 && <ListelerAdimi ozet={ozet} />}
            {adim === 2 && <HavuzAdimi ozet={ozet} />}
            {adim === 3 && <KapaliGunlerAdimi ozet={ozet} />}
          </Card>
          {ozet.stale_last_loan_dates && (
            <Uyari>
              Geçen ders yılının yıl sonu son ödünç tarihi kayıtlı; bu yıl uygulanmaz. İsterseniz
              Ayarlar → Kütüphane Politikası'ndan silebilirsiniz.{" "}
              <MetinBaglantisi to="/ayarlar?tab=politika">
                Kütüphane Politikası'nı aç
              </MetinBaglantisi>
            </Uyari>
          )}
          <div className="flex flex-wrap justify-between gap-2">
            <Button
              variant="outlined"
              icon="arrow_back"
              disabled={adim === 0}
              onClick={() => setAdim((a) => Math.max(0, a - 1))}
            >
              Geri
            </Button>
            {adim < ADIMLAR.length - 1 && (
              <Button icon="arrow_forward" onClick={() => setAdim((a) => a + 1)}>
                Devam
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function DersYiliAdimi({ ozet }: { ozet: YilBasiOzeti }) {
  const yil = ozet.school_year;
  return (
    <>
      <AdimBasligi
        sira={1}
        baslik="Ders Yılı"
        tamam={ozet.steps.school_year}
        durum={
          yil
            ? `Etkin ders yılı: ${yil.name} (${formatDate(yil.start_date)} – ${formatDate(yil.end_date)})`
            : "Etkin ders yılı yok."
        }
      />
      {!ozet.school_year_ready && (
        <Uyari>
          Bu yılın ders yılı açılmamış. Şubeler, teslimler ve iade tarihi uyarıları etkin ders
          yılına bağlıdır. Ayarlar → Ders Yılları'ndan yeni ders yılını ekleyip etkinleştirin.
        </Uyari>
      )}
      {ozet.kademe_missing && (
        <Uyari>
          Okulun kademesi seçilmemiş; son sınıflar belirlenemiyor. Ayarlar → Okul Bilgileri'nden
          seçin.
        </Uyari>
      )}
      <MetinBaglantisi to="/ayarlar?tab=ders-yillari">Ders Yılları'nı aç</MetinBaglantisi>
    </>
  );
}

function ListelerAdimi({ ozet }: { ozet: YilBasiOzeti }) {
  return (
    <>
      <AdimBasligi
        sira={2}
        baslik="e-Okul Listeleri"
        tamam={ozet.steps.import}
        durum={
          ozet.last_student_import
            ? `Son öğrenci listesi aktarımı: ${formatDate(ozet.last_student_import)}`
            : "Öğrenci listesi hiç aktarılmadı."
        }
      />
      <ul className="list-disc space-y-1 pl-5 text-body-medium text-on-surface">
        <li>
          Öğrenci listesi:{" "}
          {ozet.student_import_fresh
            ? "bu ders yılı için aktarıldı."
            : "bu ders yılı için henüz aktarılmadı."}
        </li>
        <li>
          Personel listesi:{" "}
          {ozet.last_personnel_import
            ? ozet.personnel_import_fresh
              ? `bu ders yılı için aktarıldı (${formatDate(ozet.last_personnel_import)}).`
              : `son aktarım ${formatDate(ozet.last_personnel_import)}; bu yıl için yenileyin.`
            : "hiç aktarılmadı."}
        </li>
      </ul>
      <Not>
        Aktarım kimseyi ayırmaz ve kimsenin kaydını silmez: yeni listede bulunmayan kişi Ayrılış
        Havuzu'na düşer, kararı siz verirsiniz. Sınıf atlama ve mezunların ayrılışı da bu yolla
        olur; programda ayrıca bir yıl devri işlemi yoktur.
      </Not>
      <div className="flex flex-wrap gap-4">
        <MetinBaglantisi to="/kisiler?tab=ogrenciler">Öğrencileri aç</MetinBaglantisi>
        <MetinBaglantisi to="/kisiler?tab=personel">
          Öğretmenler ve Diğer Personel'i aç
        </MetinBaglantisi>
      </div>
    </>
  );
}

function HavuzAdimi({ ozet }: { ozet: YilBasiOzeti }) {
  const toplam = ozet.leave_pool_students + ozet.leave_pool_personnel;
  return (
    <>
      <AdimBasligi
        sira={3}
        baslik="Ayrılış Havuzu"
        tamam={ozet.steps.leave_pool}
        durum={
          toplam > 0
            ? `${formatNumber(toplam)} kişi ayrılış kararı bekliyor (${formatNumber(
                ozet.leave_pool_students,
              )} öğrenci, ${formatNumber(ozet.leave_pool_personnel)} öğretmen ve diğer personel).`
            : "Ayrılış kararı bekleyen kişi yok."
        }
      />
      <Not>
        Okuldan ayrılanları “Ayrıldı olarak işaretle”yin, okulda kalanları “Aktif kalsın” ile
        havuzdan çıkarın. Ayrılanların üyeliği sonlanır; iade etmedikleri kaynaklar ve teslimler
        İlişik Listesi'ne düşer, kayıtları silinmez.
      </Not>
      <div className="flex flex-wrap gap-4">
        <MetinBaglantisi to={HAVUZ_ADRESI}>Ayrılış Havuzu'nu aç</MetinBaglantisi>
        <MetinBaglantisi to={ILISIK_LISTESI_ADRESI}>İlişik Listesi'ni aç</MetinBaglantisi>
      </div>
    </>
  );
}

function KapaliGunlerAdimi({ ozet }: { ozet: YilBasiOzeti }) {
  return (
    <>
      <AdimBasligi
        sira={4}
        baslik="Kapalı Günler"
        tamam={ozet.steps.closed_days}
        durum={`Bu ders yılında ${formatNumber(ozet.school_break_count)} öğrenciye kapalı gün kaydı var.`}
      />
      {ozet.holidays_missing_years.length > 0 && (
        <Uyari>
          {ozet.holidays_missing_years.join(" ve ")} yılının resmî tatil ya da dini bayram günleri
          Kapalı Günler'de eksik; iade tarihi bir tatile rastlarsa kaydırılamaz. “Resmî ve dini
          tatilleri ekle” düğmesiyle ekleyin.
        </Uyari>
      )}
      <Not>
        Ara tatil ve yarıyıl “öğrenciye kapalı gün” olarak girilir; iade tarihi bu günlere rastlarsa
        Kütüphane Politikası'ndaki ayara göre dersin başladığı ilk güne kayar.
      </Not>
      <MetinBaglantisi to="/ayarlar?tab=kapali-gunler">Kapalı Günler'i aç</MetinBaglantisi>
    </>
  );
}
