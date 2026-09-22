// Genel Bakış'ta "Ayrılış Havuzu" kartı (F1 eki 7; tasarım §8.3). e-Okul aktarımı
// kimseyi ayırmaz: listede bulunmayan kişiler Kişiler → Ayrılış Havuzu'nda karar
// bekler. Havuz boş değilse kart "N kişi ayrılış kararı bekliyor" der ve havuza
// bağlanır; boşsa ya da sayı okunamazsa hiçbir şey göstermez.
//
// Yalnız SAYILAR istenir (`GET leave-pool/?summary=true`): kişi adı bu ekrana gelmez.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatNumber } from "../../lib/format";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { HAVUZ_ADRESI } from "../kisiler/ortak";
import { okulApi } from "../okul/api";
import type { LeavePoolSummary } from "../okul/api";

export default function AyrilisHavuzuKarti() {
  const [ozet, setOzet] = useState<LeavePoolSummary | null>(null);

  useEffect(() => {
    let iptal = false;
    okulApi
      .getLeavePoolSummary()
      .then((o) => {
        if (!iptal) setOzet(o);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  if (ozet === null) return null;
  const toplam = ozet.student_count + ozet.personnel_count;
  if (toplam === 0) return null;

  const parcalar: string[] = [];
  if (ozet.student_count > 0) parcalar.push(`${formatNumber(ozet.student_count)} öğrenci`);
  if (ozet.personnel_count > 0) {
    parcalar.push(`${formatNumber(ozet.personnel_count)} öğretmen ve diğer personel`);
  }

  return (
    <section aria-labelledby="ayrilis-havuzu-karti">
      <Card elevation={0} className="p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-tertiary-container text-on-tertiary-container">
            <Icon name="pending_actions" />
          </span>
          <div className="min-w-0 space-y-1">
            <h2
              id="ayrilis-havuzu-karti"
              className="text-title-medium font-semibold text-on-surface"
            >
              Ayrılış Havuzu
            </h2>
            <p className="text-body-medium text-on-surface">
              {formatNumber(toplam)} kişi ayrılış kararı bekliyor ({parcalar.join(", ")}).
            </p>
            <p className="text-body-small text-on-surface-variant">
              e-Okul listesinde bulunmadıkları için havuza eklendiler; durumları aktif. Okuldan
              ayrılanları işaretleyin, kalanları havuzdan çıkarın.
            </p>
            <Link
              to={HAVUZ_ADRESI}
              className="inline-flex pt-1 text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Ayrılış Havuzu&apos;nu aç
            </Link>
          </div>
        </div>
      </Card>
    </section>
  );
}
