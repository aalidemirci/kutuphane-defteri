// OYS `lib/gradeLevels.ts`'ten uyarlandı (F4-D3/D5); yalnız kullanılan yüzey
// taşındı — OYS'nin sınıf çipi renk eşlemesi (`gradeColor`) burada çağıran
// bulamadığı için alınmadı.

// Öğrenim seviyeleri — UI seçicileri (sınıf düzeyi süzgeci, şube ekleme).
// `GET /api/v1/grade-levels/` okul içi sabit kümeyi döner: 1-12, okul
// künyesinde hazırlık sınıfı açıksa başta Hazırlık (0) ve `prep_enabled=true`.
// Aynı küme öğrenci/şube yazma kapılarında ve içe aktarmada denetlenir.

import { api } from "./api";

export interface GradeLevelOption {
  value: number;
  label: string;
}

export interface GradeLevelsResponse {
  levels: GradeLevelOption[];
  prep_enabled: boolean;
}

export const getGradeLevels = () => api.get<GradeLevelsResponse>("/grade-levels/");

// Sınıf düzeyi etiketi: 0 → "Hazırlık", n → "n. Sınıf", null/undefined → "—".
// Tek yazım "n. Sınıf"tır: eskiden ekranda "9. sınıf" ile "9. Sınıf" yan yana
// çıkıyordu.
export function gradeLevelLabel(level: number | null | undefined): string {
  if (level == null) return "—";
  return level === 0 ? "Hazırlık" : `${level}. Sınıf`;
}
