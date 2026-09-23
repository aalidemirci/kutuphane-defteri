// Sunucu tarafı sayfalamanın ortak çubuğu: "1–25 / 480 kayıt" + Önceki/Sonraki.
// Backend liste uçları `?limit=&offset=` alır ve `{count, next, previous, results}`
// döndürür (CLAUDE.md §7, tasarım D9); bu çubuk o sözleşmenin tek arayüz karşılığıdır.
// Sayılar Türkçe biçimlenir (binlik nokta — lib/format.ts).

import { formatNumber } from "../lib/format";
import Button from "./Button";

export default function PaginationBar({
  count,
  offset,
  pageSize,
  onOffset,
}: {
  /** Sunucudaki toplam kayıt sayısı (`count`). */
  count: number;
  /** Görüntülenen sayfanın başlangıcı. */
  offset: number;
  /** Sayfa boyutu (`limit`). */
  pageSize: number;
  onOffset: (next: number) => void;
}) {
  const from = count === 0 ? 0 : offset + 1;
  const to = Math.min(offset + pageSize, count);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-body-small text-on-surface-variant">
        {formatNumber(from)}–{formatNumber(to)} / {formatNumber(count)} kayıt
      </p>
      <div className="flex gap-2">
        <Button
          variant="text"
          icon="chevron_left"
          onClick={() => onOffset(Math.max(0, offset - pageSize))}
          disabled={offset === 0}
        >
          Önceki
        </Button>
        <Button
          variant="text"
          icon="chevron_right"
          onClick={() => onOffset(offset + pageSize)}
          disabled={to >= count}
        >
          Sonraki
        </Button>
      </div>
    </div>
  );
}
