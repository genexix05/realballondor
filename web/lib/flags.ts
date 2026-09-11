/** FIFA / FotMob 3-letter codes → flagcdn ISO 3166-1 alpha-2 (or gb-*). */
export const FIFA_TO_ISO: Record<string, string> = {
  AFG: "af", ALB: "al", ALG: "dz", AND: "ad", ANG: "ao", ARG: "ar", ARM: "am",
  ARU: "aw", ASA: "as", AUS: "au", AUT: "at", AZE: "az", BAH: "bs", BAN: "bd",
  BAR: "bb", BDI: "bi", BEL: "be", BEN: "bj", BER: "bm", BHR: "bh", BHU: "bt",
  BIH: "ba", BIZ: "bz", BLR: "by", BOL: "bo", BOT: "bw", BRA: "br", BRB: "bb",
  BRN: "bn", BRU: "bn", BUL: "bg", BUR: "bf", BFA: "bf", CAF: "cf", CAM: "kh",
  CAN: "ca", CAY: "ky", CGO: "cg", CHA: "td", CHI: "cl", CHN: "cn", CIV: "ci",
  CMR: "cm", COD: "cd", COK: "ck", COL: "co", COM: "km", CPV: "cv", CRC: "cr",
  CRO: "hr", CTA: "cf", CUB: "cu", CUW: "cw", CYP: "cy", CZE: "cz", DEN: "dk",
  DJI: "dj", DMA: "dm", DOM: "do", ECU: "ec", EGY: "eg", ENG: "gb-eng",
  EQG: "gq", ERI: "er", ESP: "es", EST: "ee", ETH: "et", FIJ: "fj", FIN: "fi",
  FRA: "fr", FRO: "fo", GAB: "ga", GAM: "gm", GEO: "ge", GER: "de", GHA: "gh",
  GIB: "gi", GNB: "gw", GRE: "gr", GRN: "gd", GUA: "gt", GUI: "gn", GUM: "gu",
  GUY: "gy", HAI: "ht", HKG: "hk", HON: "hn", HUN: "hu", IDN: "id", IND: "in",
  IRI: "ir", IRN: "ir", IRL: "ie", IRQ: "iq", ISL: "is", ISR: "il", ITA: "it",
  JAM: "jm", JOR: "jo", JPN: "jp", KAZ: "kz", KEN: "ke", KGZ: "kg", KIR: "ki",
  KOR: "kr", KOS: "xk", KSA: "sa", KUW: "kw", LAO: "la", LAT: "lv", LBN: "lb",
  LBY: "ly", LCA: "lc", LES: "ls", LBR: "lr", LIE: "li", LTU: "lt", LUX: "lu",
  MAC: "mo", MAD: "mg", MAR: "ma", MAS: "my", MDA: "md", MDV: "mv", MEX: "mx",
  MGL: "mn", MKD: "mk", MLI: "ml", MLT: "mt", MNE: "me", MOZ: "mz", MRI: "mu",
  MSR: "ms", MTN: "mr", MWI: "mw", MYA: "mm", NAM: "na", NCA: "ni", NED: "nl",
  NEP: "np", NGA: "ng", NIG: "ne", NIR: "gb-nir", NOR: "no", NZL: "nz",
  OMA: "om", PAK: "pk", PAN: "pa", PAR: "py", PER: "pe", PHI: "ph", PLE: "ps",
  PNG: "pg", POL: "pl", POR: "pt", PRK: "kp", PUR: "pr", QAT: "qa", ROU: "ro",
  RSA: "za", RUS: "ru", RWA: "rw", SAM: "ws", SCO: "gb-sct", SEN: "sn",
  SEY: "sc", SIN: "sg", SKN: "kn", SLE: "sl", SLV: "sv", SMR: "sm", SOL: "sb",
  SOM: "so", SRB: "rs", SRI: "lk", SSD: "ss", STP: "st", SUD: "sd", SUI: "ch",
  SUR: "sr", SVK: "sk", SVN: "si", SWE: "se", SWZ: "sz", SYR: "sy", TAH: "pf",
  TAN: "tz", TCA: "tc", TGA: "to", THA: "th", TJK: "tj", TKM: "tm", TLS: "tl",
  TOG: "tg", TPE: "tw", TRI: "tt", TUN: "tn", TUR: "tr", UAE: "ae", UGA: "ug",
  UKR: "ua", URU: "uy", USA: "us", UZB: "uz", VAN: "vu", VEN: "ve", VIE: "vn",
  VIN: "vc", WAL: "gb-wls", YEM: "ye", ZAM: "zm", ZIM: "zw",
};

export function flagUrl(fifa: string | null | undefined): string | null {
  if (!fifa) return null;
  const iso = FIFA_TO_ISO[fifa.toUpperCase()];
  return iso ? `https://flagcdn.com/w80/${iso}.png` : null;
}

export function playerPhotoUrl(fotmobId: string | number | null | undefined): string | null {
  if (fotmobId === null || fotmobId === undefined || fotmobId === "") return null;
  return `https://images.fotmob.com/image_resources/playerimages/${fotmobId}.png`;
}
