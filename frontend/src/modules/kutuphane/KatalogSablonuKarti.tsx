// Genel Bakış'taki "Katalog Excel Şablonu" kartı (tasarım §8.1). Okul kitap
// listesini katalog ekranlarını beklemeden bu şablonla Excel'de hazırlar; şablonun
// sütunları ve kuralları backend'deki tek sözlükten gelir, doldurma kılavuzu
// docs/katalog-excel-sablonu.md'dedir. Kart gezinme kartı değildir (bir sayfaya
// gitmez), bu yüzden HubFeatureCard değil düz Card + düğmedir. İndirme işlevi
// `useKatalogSablonuIndirme` kancasındadır; "Başlangıç Yol Haritası" da onu kullanır
// ve `onIndirildi` ile şablon maddesini işaretler.

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { KATALOG_SABLONU_BELGE_ADI } from "./api";
import { useKatalogSablonuIndirme } from "./useKatalogSablonu";

interface KatalogSablonuKartiProps {
  /** Şablon başarıyla indirilince çağrılır (yol haritasının şablon maddesi). */
  onIndirildi?: () => void;
}

export default function KatalogSablonuKarti({ onIndirildi }: KatalogSablonuKartiProps) {
  const { indir, indiriliyor } = useKatalogSablonuIndirme(onIndirildi);

  return (
    <Card elevation={0} className="p-5">
      <div className="flex items-start gap-4">
        <span
          aria-hidden="true"
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-primary-container text-primary"
        >
          <Icon name="table_view" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-title-medium font-semibold text-on-surface">
            {KATALOG_SABLONU_BELGE_ADI}
          </h2>
          <p className="mt-1 text-body-medium text-on-surface-variant">
            Kitap listenizi bu şablonla Excel'de hazırlamaya şimdiden başlayabilirsiniz;
            hazırladığınız dosya katalog içe aktarımında olduğu gibi kullanılır. Şablondaki
            “Sütunlar” sayfası her sütuna ne yazılacağını anlatır. Listeye kişisel veri yazılmaz.
          </p>
          <Button
            variant="tonal"
            icon="download"
            className="mt-3"
            onClick={() => void indir()}
            disabled={indiriliyor}
          >
            Şablonu indir
          </Button>
        </div>
      </div>
    </Card>
  );
}
