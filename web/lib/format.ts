export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(digits);
}

export const POSITIONS = [
  { id: "", label: "Todos" },
  { id: "FWD", label: "Delanteros" },
  { id: "MID", label: "Medios" },
  { id: "DEF", label: "Defensas" },
  { id: "GK", label: "Porteros" },
] as const;
