// Ağ Kataloğu testlerinin uydurma verileri (gerçek okul ağı bilgisi DEĞİLDİR —
// docs/sozluk.md §2.1: gerçek IP blokları yazılmaz).

import type {
  AgDurumu,
  GuvenlikDuvari,
  IpAdaylari,
  KatalogAyari,
  KatalogDurumu,
} from "../modules/agkatalogu/api";

export const ORNEK_IP = "10.20.30.40";
export const ORNEK_IP_2 = "10.99.0.7";

export function ayarVerisi(fazlasi: Partial<KatalogAyari> = {}): KatalogAyari {
  return {
    acik: false,
    port: 8765,
    dinleme_kipi: "ALL",
    secili_ip: "",
    son_afis_ip: "",
    uyku_engelleme: true,
    vitrin_acik: true,
    konular_acik: true,
    tahta_cidrleri: [],
    kutuphane_saatleri: "",
    ...fazlasi,
  };
}

export function duvarVerisi(fazlasi: Partial<GuvenlikDuvari> = {}): GuvenlikDuvari {
  return {
    platform: "windows",
    dinlemeye_izin: true,
    maddeler: [
      { kod: "etkin", baslik: "Kural var ve etkin", durum: "gecti", aciklama: "Kural etkin." },
      {
        kod: "program",
        baslik: "Kuraldaki program bu program",
        durum: "gecti",
        aciklama: "Kural bu programa yazılmış.",
      },
      {
        kod: "port",
        baslik: "Kuraldaki port ayardaki portla aynı",
        durum: "kaldi",
        aciklama: "Kural başka bir portu kapsıyor.",
      },
      {
        kod: "kapsam",
        baslik: "Kural bu ağ profilini kapsıyor",
        durum: "uyari",
        aciklama: "Uzak adres her yer.",
      },
      {
        kod: "engelleme",
        baslik: "Bu program için engelleme kuralı yok",
        durum: "bilinmiyor",
        aciklama: "Denetlenemedi.",
      },
    ],
    kural: {
      ad: "Kutuphane Defteri Katalog",
      program: "kutuphane-defteri.exe",
      yerel_port: ["8765"],
      uzak_adres: ["LocalSubnet", "10.60.0.0/22"],
      profil: "Domain, Private, Public",
      etkin: true,
    },
    ag_profilleri: ["Public"],
    hata: null,
    linux: {},
    ...fazlasi,
  };
}

export function katalogVerisi(fazlasi: Partial<KatalogDurumu> = {}): KatalogDurumu {
  return {
    durum: "kapali",
    ayar_acik: false,
    dinleme_kipi: "ALL",
    tum_arayuzler: false,
    dinleme_ip: null,
    port: 8765,
    adres: null,
    guncel_ip: ORNEK_IP,
    son_afis_ip: null,
    ip_degisti: false,
    son_hata: null,
    uyarilar: [],
    guvenlik_duvari: null,
    reddedilen_baglanti: 0,
    uyku_engelli: false,
    ...fazlasi,
  };
}

export function acikKatalog(fazlasi: Partial<KatalogDurumu> = {}): KatalogDurumu {
  return katalogVerisi({
    durum: "acik",
    ayar_acik: true,
    tum_arayuzler: true,
    adres: `http://${ORNEK_IP}:8765/`,
    uyku_engelli: true,
    ...fazlasi,
  });
}

export function durumVerisi(fazlasi: Partial<AgDurumu> = {}): AgDurumu {
  return {
    masaustu: true,
    platform: "windows",
    katalog: katalogVerisi(),
    qr: null,
    sayaclar: {
      bugun: { sayfa: 12, arama: 5, hiz_siniri: 0 },
      son_hata: null,
    },
    ...fazlasi,
  };
}

/** 21×21 örnek QR matrisi (içeriği önemsiz; çizim sınanır). */
export const ORNEK_QR = Array.from({ length: 21 }, (_, y) =>
  Array.from({ length: 21 }, (_, x) => ((x + y) % 3 === 0 ? "1" : "0")).join(""),
);

export function adaylarVerisi(fazlasi: Partial<IpAdaylari> = {}): IpAdaylari {
  return {
    arayuzler: [
      {
        ad: "Ethernet",
        ip: ORNEK_IP,
        onek: 24,
        varsayilan_rota: true,
        ag_profili: "Public",
        yonlendirme: false,
      },
      {
        ad: "Ethernet 2",
        ip: ORNEK_IP_2,
        onek: 24,
        varsayilan_rota: false,
        ag_profili: "Private",
        yonlendirme: true,
      },
    ],
    varsayilan_ip: ORNEK_IP,
    yonlendirme_acik: true,
    uyarilar: ["Ağ Kataloğu bu ağda da erişilebilir: Ethernet 2."],
    kaynak: "sahte",
    ...fazlasi,
  };
}
