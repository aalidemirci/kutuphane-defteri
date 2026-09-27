// Elle şifreli yedek kartı (Güvenlik sekmesi). Metin kullanıcı dilindedir:
// şifreleme algoritmalarının adı (teknik ayrıntı) burada geçmez — yalnız
// Hakkında sayfası ve kurulum belgesi anar (docs/sozluk.md §1). Dosya adındaki
// tarih YEREL tarihtir (`todayIso`): `toISOString()` UTC verir, gece yarısına
// yakın alınan yedeğe bir önceki günün tarihini yazardı (CLAUDE.md §2).

import { useCallback, useEffect, useState } from "react";

import { api } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { todayIso } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { guvenlikApi } from "./api";
import type { DisYedekDurumu } from "./api";
import { disYedekCumlesi, disYedekHatirlatmaCumlesi } from "./DisYedekKarti";

function hataMesaji(error: unknown): string {
  return error instanceof Error ? error.message : "Şifreli yedek oluşturulamadı.";
}

/** `kutuphane-defteri-yedek-2026-09-18.kdbak` — ad sıralanınca tarih sırası çıkar. */
function yedekDosyaAdi(): string {
  return `kutuphane-defteri-yedek-${todayIso()}.kdbak`;
}

/** Hatırlatma süresi seçenekleri (gün; sunucu 7-90 aralığını ayrıca denetler). */
const SURE_SECENEKLERI = [7, 14, 30, 60, 90].map((gun) => ({
  value: String(gun),
  label: `${gun} gün`,
}));

export default function SifreliYedekleme({ parolaKurulu }: { parolaKurulu: boolean }) {
  const snackbar = useSnackbar();
  const [calisiyor, setCalisiyor] = useState(false);
  // F11 dış yedek hatırlatması: son indirme tarihi (sunucu, indirmeyle yazar) + süre.
  const [disYedek, setDisYedek] = useState<DisYedekDurumu | null>(null);

  const disYedegiOku = useCallback(() => {
    guvenlikApi
      .disYedek()
      .then(setDisYedek)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (parolaKurulu) disYedegiOku();
  }, [parolaKurulu, disYedegiOku]);

  async function indir() {
    setCalisiyor(true);
    try {
      const yedek = await api.postBlob("/backups/encrypted/");
      saveBlob(yedek, yedekDosyaAdi());
      snackbar.success("Şifreli veritabanı yedeği indirildi. Dosyayı USB belleğe kopyalayın.");
      disYedegiOku();
    } catch (error) {
      snackbar.error(hataMesaji(error));
    } finally {
      setCalisiyor(false);
    }
  }

  const hatirlatma = disYedek ? disYedekHatirlatmaCumlesi(disYedek) : null;

  async function sureDegisti(deger: string) {
    try {
      setDisYedek(await guvenlikApi.disYedekSuresi(Number(deger)));
      snackbar.success("Hatırlatma süresi kaydedildi.");
    } catch (error) {
      snackbar.error(error instanceof Error ? error.message : "Hatırlatma süresi kaydedilemedi.");
    }
  }

  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <Icon name="backup" className="mt-0.5 text-primary" />
        <div className="min-w-0 flex-1">
          <h2 className="text-title-large text-on-surface">Şifreli Veritabanı Yedeği</h2>
          <p className="mt-2 text-body-medium text-on-surface-variant">
            Kayıtlarınızın tutarlı bir kopyası bu bilgisayarda hazırlanır ve güçlü şifrelemeyle
            korunur, ardından yedek dosyası olarak indirilir. Şifresiz kopya üretilmez; dosya hiçbir
            yere kendiliğinden gönderilmez.
          </p>
          <p className="mt-2 text-body-small text-on-surface-variant">
            İndirdiğiniz dosyayı USB belleğe ya da okulun ağ diskine kendiniz kopyalayın; bulut
            depolama hizmetine yüklemeyin (Bilgi ve Sistem Güvenliği Yönergesi 11/23). Yedeği açmak
            için yönetici parolanız ya da kurtarma anahtarınız gerekir; ikisini de güvenli biçimde
            saklayın.
          </p>
          {!parolaKurulu && (
            <p className="mt-3 rounded-shape-md bg-error-container p-3 text-body-small text-on-error-container">
              Şifreli yedek oluşturabilmek için önce yönetici parolası kurmalısınız.
            </p>
          )}
          <div className="mt-5">
            <Button icon="download" onClick={indir} disabled={calisiyor || !parolaKurulu}>
              {calisiyor ? "Şifreli yedek hazırlanıyor…" : "Şifreli yedeği indir"}
            </Button>
          </div>
          {parolaKurulu && disYedek && (
            <div className="mt-5 flex flex-wrap items-end gap-4">
              <div className="min-w-48 flex-1 space-y-1">
                <p className="text-body-medium text-on-surface">{disYedekCumlesi(disYedek)}</p>
                {hatirlatma &&
                  (disYedek.remind ? (
                    <p
                      role="status"
                      className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container"
                    >
                      <Icon name="notification_important" size="sm" />
                      <span>{hatirlatma}</span>
                    </p>
                  ) : (
                    <p className="text-body-small text-on-surface-variant">{hatirlatma}</p>
                  ))}
              </div>
              <Select
                label="Hatırlatma süresi"
                className="w-40"
                options={SURE_SECENEKLERI}
                value={String(disYedek.reminder_days)}
                onChange={(e) => void sureDegisti(e.target.value)}
                helperText="Genel Bakış bu süre dolunca hatırlatır."
              />
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
