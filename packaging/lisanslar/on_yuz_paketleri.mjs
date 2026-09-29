// =============================================================================
// packaging/lisanslar/on_yuz_paketleri.mjs — ön yüz paketine giren npm paketleri
// =============================================================================
// THIRD_PARTY_LICENSES üreticisinin (packaging/lisanslar/lisanslar.py) ön yüz
// girdisidir. Vite derlemesini YAZMADAN (write: false) koşar ve çıktıya GERÇEKTEN
// giren modülleri toplar:
//
//   * JS parçalarında `renderedLength > 0` olan modüller — ağaç sarsmayla düşen
//     (ör. yalnız geliştirmede çizilen React Query Devtools) listeye girmez;
//   * CSS `@import` zinciri (postcss-import) `getWatchFiles()` ile;
//   * CSS'in çektiği varlıklar (ör. Material Symbols yazı tipi) `originalFileNames`;
//   * Vite'ın kendi çalışma anı yardımcıları (`\0vite/...`, `\0commonjsHelpers`) →
//     vite paketi; Tailwind'in ürettiği CSS (preflight) → tailwindcss paketi.
//
// Çıktı stdout'a JSON'dur; günlük stderr'e yazılır. Kullanım (depo kökünden):
//
//   docker compose run --rm -T frontend node --input-type=module \
//       < packaging/lisanslar/on_yuz_paketleri.mjs > dist/lisans/on-yuz.json
//
// Betik stdin'den okunur; bu yüzden modüller ÇALIŞMA DİZİNİNE (/app) göre çözülür.
// Doğrudan çağıran: packaging/lisanslar/uret.sh.
// =============================================================================
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const kok = process.cwd();
const vitePaketi = JSON.parse(readFileSync(path.join(kok, "node_modules", "vite", "package.json"), "utf8"));
const viteGiris = path.join(kok, "node_modules", "vite", "dist", "node", "index.js");
if (!existsSync(viteGiris)) {
  process.stderr.write(`HATA: vite ${vitePaketi.version} giriş dosyası bulunamadı: ${viteGiris}\n`);
  process.exit(2);
}
const vite = await import(pathToFileURL(viteGiris).href);

const yollar = new Set();
const sanallar = new Set();
let cssMetni = "";

/** Derlemenin çıktıya koyduğu modülleri toplayan eklenti (en son koşar). */
const toplayici = {
  name: "kd-lisans-toplayici",
  enforce: "post",
  generateBundle(_secenekler, paket) {
    for (const oge of Object.values(paket)) {
      if (oge.type === "chunk") {
        for (const [kimlik, bilgi] of Object.entries(oge.modules)) {
          if (bilgi.renderedLength > 0) {
            if (kimlik.startsWith("\0")) sanallar.add(kimlik.slice(1));
            else yollar.add(kimlik);
          }
        }
      } else {
        for (const ad of oge.originalFileNames ?? []) yollar.add(path.resolve(kok, ad));
        if (oge.originalFileName) yollar.add(path.resolve(kok, oge.originalFileName));
        if (oge.fileName.endsWith(".css")) cssMetni += String(oge.source);
      }
    }
    for (const dosya of this.getWatchFiles()) yollar.add(dosya);
  },
};

await vite.build({
  root: kok,
  configFile: path.join(kok, "vite.config.ts"),
  logLevel: "silent",
  plugins: [toplayici],
  build: { write: false, reportCompressedSize: false },
});

const MODULLER = `${path.sep}node_modules${path.sep}`;

/** Yolun ait olduğu paketin kök dizini (node_modules/<ad> ya da @kapsam/<ad>). */
function paketKoku(dosya) {
  const temiz = dosya.split("?")[0];
  const i = temiz.lastIndexOf(MODULLER);
  if (i < 0) return null;
  const kalan = temiz.slice(i + MODULLER.length).split(path.sep);
  const parca = kalan[0].startsWith("@") ? kalan.slice(0, 2) : kalan.slice(0, 1);
  return temiz.slice(0, i + MODULLER.length) + parca.join(path.sep);
}

const kokler = new Map();
function ekle(dizin, neden) {
  if (!dizin || !existsSync(path.join(dizin, "package.json"))) return;
  const onceki = kokler.get(dizin) ?? new Set();
  onceki.add(neden);
  kokler.set(dizin, onceki);
}

for (const dosya of yollar) {
  const neden = /\.(css|scss)$/.test(dosya.split("?")[0])
    ? "css"
    : /\.(js|mjs|cjs|jsx|ts|tsx)$/.test(dosya.split("?")[0])
      ? "js"
      : "varlik";
  ekle(paketKoku(dosya), neden);
}
for (const kimlik of sanallar) {
  const kok2 = paketKoku(kimlik);
  if (kok2) ekle(kok2, "js");
  else if (/^(vite\/|commonjsHelpers)/.test(kimlik)) {
    // Vite'ın çalışma anı yardımcıları (modulepreload, preload-helper) ve paketin
    // içine gömdüğü @rollup/plugin-commonjs yardımcıları: vite'ın LICENSE.md'si
    // gömülü bağımlılıkların lisanslarını da taşır.
    ekle(path.join(kok, "node_modules", "vite"), "vite-yardimcisi");
  }
}
if (/tailwindcss v\d|--tw-[a-z]/.test(cssMetni)) {
  // Tailwind'in ürettiği CSS (preflight ve `--tw-*` değişkenleri) çıktının
  // içindedir; paket bir PostCSS eklentisidir ve modül grafiğinde görünmez.
  // Küçültücü `/*! tailwindcss … */` başlığını siler, bu yüzden değişken
  // önekine de bakılır.
  ekle(path.join(kok, "node_modules", "tailwindcss"), "css-uretimi");
}

const LISANS_DOSYASI = /^(licen[cs]e|copying|notice)(\.|$|-)/i;
const paketler = [];
for (const [dizin, nedenler] of kokler) {
  const bilgi = JSON.parse(readFileSync(path.join(dizin, "package.json"), "utf8"));
  const dosyalar = readdirSync(dizin)
    .filter((ad) => LISANS_DOSYASI.test(ad))
    .sort()
    .map((ad) => ({ ad, metin: readFileSync(path.join(dizin, ad), "utf8") }));
  const lisans =
    typeof bilgi.license === "string"
      ? bilgi.license
      : (bilgi.license?.type ?? (bilgi.licenses ?? []).map((l) => l.type).join(" OR "));
  paketler.push({
    ad: bilgi.name,
    surum: bilgi.version,
    lisans: lisans || "",
    kaynak: typeof bilgi.repository === "string" ? bilgi.repository : (bilgi.repository?.url ?? ""),
    anasayfa: bilgi.homepage ?? "",
    nedenler: [...nedenler].sort(),
    dosyalar,
  });
}
paketler.sort((a, b) => a.ad.localeCompare(b.ad, "en"));
process.stdout.write(JSON.stringify({ vite: vitePaketi.version, paketler }, null, 2) + "\n");
process.stderr.write(`${paketler.length} npm paketi ön yüz çıktısında.\n`);
