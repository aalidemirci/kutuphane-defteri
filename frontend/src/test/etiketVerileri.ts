// Etiket testlerinin ortak kalıpları (F4) — backend serializer alan kümeleriyle
// birebir (`labels/serializers.py`, `serializers_kuyruk.py`). Testler yalnız
// farkı yazar.
//
// KVKK: bütün adlar UYDURMADIR; etiket yanıtları zaten kişisel veri taşımaz.

import type {
  AyrilmisNumara,
  BasimPartisi,
  BasimPartisiAyrintisi,
  BosBarkodAraligi,
  BosBarkodAraligiAyrintisi,
  DogrulamaSonucu,
  EtiketDenetimi,
  EtiketOzeti,
  EtiketSablonu,
  KuyrukNushasi,
  YaziciKalibrasyonu,
} from "../modules/kutuphane/etiketApi";

/** Varsayılan 65'li barkod tabakası (38,1 × 21,2 mm, 5 × 13). */
export function etiketSablonu(ozel: Partial<EtiketSablonu> = {}): EtiketSablonu {
  return {
    id: 1,
    name: "Barkod etiketi — 38,1 × 21,2 mm, 65'li",
    kind: "BARCODE",
    kind_display: "Barkod etiketi",
    page_margin_top: 10.7,
    page_margin_left: 4.75,
    label_width: 38.1,
    label_height: 21.2,
    rows: 13,
    cols: 5,
    gutter_x: 2.5,
    gutter_y: 0,
    corner_radius: 0,
    is_default: true,
    labels_per_sheet: 65,
    supports_qr: false,
    supports_barcode: true,
    updated_at: "2026-09-24T09:00:00+03:00",
    ...ozel,
  };
}

/** Hazır dört şablonun ekrana yeten üçü: 65'li barkod, 44'lü QR'lı, 65'li sırt. */
export function hazirSablonlar(): EtiketSablonu[] {
  return [
    etiketSablonu(),
    etiketSablonu({
      id: 2,
      name: "Barkod etiketi (QR'a uygun) — 48,5 × 25,4 mm, 44'lü",
      label_width: 48.5,
      label_height: 25.4,
      page_margin_top: 8.8,
      page_margin_left: 8,
      gutter_x: 0,
      rows: 11,
      cols: 4,
      labels_per_sheet: 44,
      is_default: false,
      supports_qr: true,
    }),
    etiketSablonu({
      id: 4,
      name: "Sırt etiketi — 38,1 × 21,2 mm, 65'li",
      kind: "SPINE",
      kind_display: "Sırt etiketi",
    }),
  ];
}

export function kalibrasyon(ozel: Partial<YaziciKalibrasyonu> = {}): YaziciKalibrasyonu {
  return {
    id: 8,
    template: 1,
    template_name: "Barkod etiketi — 38,1 × 21,2 mm, 65'li",
    printer_name: "Masa yazıcısı",
    offset_x: 1.5,
    offset_y: -0.5,
    updated_at: "2026-09-24T09:30:00+03:00",
    ...ozel,
  };
}

export function kuyrukNushasi(ozel: Partial<KuyrukNushasi> = {}): KuyrukNushasi {
  return {
    id: 21,
    work: 7,
    work_title: "Şiir Defteri",
    work_authors: "Ayşe Yılmaz",
    call_number: "811 YIL",
    acquisition: 3,
    accession_no: 2026000123,
    barcode: "2026000123",
    barcode_display: "2026-000123",
    section: 1,
    section_name: "Edebiyat",
    label_printed_at: null,
    label_verified_at: null,
    spine_label_printed_at: null,
    pending_batch: null,
    created_at: "2026-09-24T10:00:00+03:00",
    ...ozel,
  };
}

export function basimPartisi(ozel: Partial<BasimPartisi> = {}): BasimPartisi {
  return {
    id: 12,
    kind: "BOTH",
    kind_display: "Sırt ve barkod etiketi",
    template: 1,
    template_name: "Barkod etiketi — 38,1 × 21,2 mm, 65'li",
    calibration: null,
    printer_name: null,
    spine_template: null,
    spine_calibration: null,
    include_qr: false,
    order: "CALL_NUMBER",
    order_display: "Yer numarası",
    start_cell: 1,
    copy_count: 2,
    status: "PENDING",
    status_display: "Basım onayı bekliyor",
    created_at: "2026-09-24T11:00:00+03:00",
    confirmed_at: null,
    reverted_at: null,
    discarded_at: null,
    reprint_of: null,
    ...ozel,
  };
}

export function basimPartisiAyrintisi(
  ozel: Partial<BasimPartisiAyrintisi> = {},
): BasimPartisiAyrintisi {
  return {
    ...basimPartisi(),
    items: [
      { position: 1, ...kuyrukNushasi(), printable: true },
      {
        position: 2,
        ...kuyrukNushasi({ id: 22, barcode_display: "2026-000124" }),
        printable: true,
      },
    ],
    ...ozel,
  };
}

export function etiketOzeti(ozel: Partial<EtiketOzeti> = {}): EtiketOzeti {
  return {
    queue: { SPINE: 4, BARCODE: 3, BOTH: 3 },
    unverified: 2,
    pending_batches: 0,
    reservations: { reserved: 65, bound: 12, cancelled: 1, open: 52 },
    ...ozel,
  };
}

export function bosBarkodAraligi(ozel: Partial<BosBarkodAraligi> = {}): BosBarkodAraligi {
  return {
    id: 5,
    year: 2026,
    first_barcode: "2026000101",
    first_barcode_display: "2026-000101",
    last_barcode: "2026000103",
    last_barcode_display: "2026-000103",
    count: 3,
    note: "Hikâye rafı",
    printed_at: null,
    open_count: 2,
    bound_count: 1,
    cancelled_count: 0,
    created_at: "2026-09-24T08:00:00+03:00",
    ...ozel,
  };
}

export function ayrilmisNumara(ozel: Partial<AyrilmisNumara> = {}): AyrilmisNumara {
  return {
    barcode: "2026000101",
    barcode_display: "2026-000101",
    state: "OPEN",
    state_display: "Bağlanmadı",
    copy: null,
    work_title: "",
    bound_at: null,
    cancelled_at: null,
    cancel_reason: "",
    ...ozel,
  };
}

export function bosBarkodAraligiAyrintisi(
  ozel: Partial<BosBarkodAraligiAyrintisi> = {},
): BosBarkodAraligiAyrintisi {
  return {
    ...bosBarkodAraligi(),
    numbers: [
      ayrilmisNumara(),
      ayrilmisNumara({ barcode: "2026000102", barcode_display: "2026-000102" }),
      ayrilmisNumara({
        barcode: "2026000103",
        barcode_display: "2026-000103",
        state: "BOUND",
        state_display: "Nüshaya bağlandı",
        copy: 41,
        work_title: "Gökyüzü Masalları",
        bound_at: "2026-09-24T09:00:00+03:00",
      }),
    ],
    ...ozel,
  };
}

export function dogrulamaSonucu(ozel: Partial<DogrulamaSonucu> = {}): DogrulamaSonucu {
  return {
    result: "verified",
    kind: "COPY",
    message: "Etiket doğrulandı.",
    copy: {
      id: 21,
      barcode: "2026000123",
      barcode_display: "2026-000123",
      work_title: "Şiir Defteri",
      call_number: "811 YIL",
      label_printed_at: "2026-09-24T11:30:00+03:00",
      label_verified_at: "2026-09-24T12:00:00+03:00",
    },
    ...ozel,
  };
}

export function etiketDenetimi(ozel: Partial<EtiketDenetimi> = {}): EtiketDenetimi {
  return {
    bindable: true,
    kind: "RESERVED",
    barcode: "2026000101",
    barcode_display: "2026-000101",
    reservation: 5,
    copy: null,
    work_title: "",
    message: "Etiket boş; kayıtta nüsha bu numarayla açılacak.",
    hint: "",
    ...ozel,
  };
}
