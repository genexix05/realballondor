const es = {
  meta: {
    title: "Índex Ballon d'Or",
    description: "Ranking estadístico partido a partido",
  },
  brand: {
    index: "Índex",
    name: "Ballon d'Or",
    season: "25/26",
  },
  nav: {
    index: "Índice",
    ranking: "Ranking",
    trophies: "Títulos",
    method: "Método",
  },
  footer: "82% rendimiento · 18% palmarés · rival UEFA/FIFA al saque",
  lang: {
    label: "Idioma",
    es: "ES",
    en: "EN",
    pt: "PT",
    de: "DE",
    fr: "FR",
  },
  common: {
    years: "años",
    seeList: "Ver lista",
    index: "índice",
    runnerUp: "subcampeón",
    champion: "campeón",
    winner: "campeón",
    dash: "—",
  },
  positions: {
    FWD: "Delanteros",
    MID: "Medios",
    DEF: "Defensas",
    GK: "Porteros",
    U23: "Sub-23",
    MID_long: "Mediocentros",
  },
  home: {
    kicker: "Temporada {season}",
    title: "El Balón de Oro, partido a partido.",
    lede: "{total} jugadores. El índice mezcla lo que hiciste en cada partido con el nivel de esas actuaciones: jugar 55 veces no basta si cada una vale poco.",
    numberOne: "Número uno",
    howTitle: "Cómo se calcula",
    howStrong: "Índice = 82% rendimiento + 18% palmarés.",
    howLead: "El rendimiento mezcla volumen y nivel (media × 40 partidos). Cada partido vale:",
    formula: "actuación × rival × competición × fase",
    how1:
      "La actuación mezcla las estadísticas de la posición —escaladas al percentil 95, no por 90— con el rating de FotMob (35%).",
    how2:
      "El rival sale de coeficientes UEFA y ranking FIFA al saque, sin Elo casero y sin mirar el resultado de ese partido.",
    how3:
      "Un partido de Liga vale 1. Un grupo de Mundial ronda eso: clasificarse y caer no hincha el índice. La final, 2.25 (1.50 de torneo × 1.50 de final).",
    how4:
      "El palmarés se deduce de las finales y las tablas. El crédito se reparte según lo que aportaste (Match Score), no según minutos en el banquillo.",
    howLink: "La ficha completa del método →",
    splitTitle: "Cómo se parte el índice",
    splitLede: "Oro: rendimiento × 0.82. Gris: palmarés × 0.18.",
    rosterTitle: "Plantilla",
  },
  ranking: {
    kicker: "Temporada {season}",
    titles: {
      "": "Los 100 primeros",
      FWD: "Delanteros",
      MID: "Medios",
      DEF: "Defensas",
      GK: "Porteros",
      U23: "Menores de 23",
      fallback: "Ranking",
    },
    lede: "{total} jugadores en esta lista. El puesto de la tabla es el de este recorte; al lado del nombre va el del índice general.",
    tabs: {
      all: "General",
      FWD: "Delanteros",
      MID: "Medios",
      DEF: "Defensas",
      GK: "Porteros",
      U23: "Sub-23",
    },
    th: {
      player: "Jugador",
      pos: "Pos",
      apps: "PJ",
      goals: "G",
      assists: "A",
      rating: "Rating",
      index: "Índice",
    },
  },
  trophies: {
    kicker: "Temporada {season}",
    title: "Quién ganó qué",
    lede: "Copas por la final — incluidas las tandas de penaltis — y ligas por la tabla.",
  },
  player: {
    back: "← Ranking",
    unranked: "Sin ranking",
    individual: "Rendimiento",
    trophies: "Palmarés",
    seasonScore: "Season Score",
    meanMatch: "Match Score medio",
    meanRating: "Rating medio",
    consistency: "Regularidad",
    matches: "Partidos",
    minutes: "Minutos",
    started: "Titular",
    goals: "Goles",
    assists: "Asistencias",
    modelStats: "Estadísticas del modelo · {position}",
    modelLede:
      "Solo entran estas variables, con el peso de su grupo. Totales de la temporada y por 90 minutos. El rating de FotMob aporta el {pct}% de la actuación.",
    thStat: "Estadística",
    thWeight: "Peso",
    thTotal: "Total",
    thPer90: "/90",
    matchScore: "Match Score",
    matchScoreLede: "Cada punto es un partido, en orden cronológico.",
    notEnoughMatches: "No hay suficientes partidos para graficar.",
    noTrophies: "Sin títulos ni subcampeonatos esta temporada.",
    matchesHeading: "{n} partidos",
    thDate: "Fecha",
    thComp: "Competición",
    thMatch: "Partido",
    thMin: "Min",
    thGA: "G/A",
    thRating: "Rating",
    thOpp: "Rival",
    thScore: "Score",
    shareMin: "% min",
  },
  method: {
    kicker: "Documentación",
    title: "Cómo se construye el índice",
    lede: "Todo sale de jugador × partido. No hay Elo casero, no hay votos, no se escriben los campeones a mano. Esta página es el modelo tal como está configurado ahora.",
    formulaTitle: "La fórmula gorda",
    formulaIntro:
      "Un jugador necesita al menos {min} partidos para entrar. El índice de temporada es:",
    formula:
      "índice = {ind}% × rendimiento + {trophy}% × palmarés",
    formulaNote:
      "Rendimiento y palmarés se reescalan a 0–100 entre los elegibles. La regularidad (1 − coeficiente de variación de los Match Scores) mueve un poco el total: dos temporadas con la misma suma no son iguales si una es plana y la otra son tres explosiones.",
    volumeNote:
      "No hay un factor de lesiones aparte. El Season Score mezcla a partes iguales la suma de partidos y el nivel (media × 40 partidos): una campaña corta y grande ya no la entierra un calendario de 55 partidos mediocres.",
    matchTitle: "Match Score",
    matchIntro: "Cada partido produce un número:",
    performanceLabel: "Actuación",
    performance:
      "Las estadísticas del grupo de posición se dividen por el percentil 95 de ese grupo (un 1.0 es una noche grande, el cero sigue siendo cero). No se pasan a por-90: los minutos ya van en los recuentos. Un z-score le daría negativo a cada suplente. Eso se mezcla con el rating de FotMob ({pct}%): un {baseline} es neutro, un {sat} satura. Por debajo de ~10 minutos FotMob no puntúa y manda solo lo que hizo en el campo.",
    opponentLabel: "Rival",
    opponent:
      "Fuerza 0–1 el día del saque: coeficiente UEFA de club (ventana cerrada el año anterior) más puntos por partido domésticos, y ranking FIFA para selecciones. El multiplicador es {floor} + {range} × fuerza, así un partido fácil no vale cero.",
    reliabilityLabel: "Fiabilidad",
    reliability:
      "Hoy el exponente de minutos es 0: la actuación se sostiene sola. Un cameo corto no se hincha ni se borra.",
    stageTitle: "Competición y fase",
    stageIntro:
      "Los dos se multiplican. Un grupo de Mundial vale {wc} × {group} = {wcGroup}: es un partido, no un bono por haber estado ahí. La final, {wc} × {final} = {wcFinal}.",
    thComp: "Competición",
    thStage: "Fase",
    thWeight: "Peso",
    statsTitle: "Qué estadística cuenta, según la posición",
    statsIntro:
      "Los números son importancia relativa, no puntos. Goles y pases entran en la misma escala porque cada uno se divide por su propio p95.",
    penalties: "Penalizaciones (todos)",
    gkNote:
      "En porteros manda goles evitados (PSxG − goles encajados). Las paradas en crudo pesan menos para no premiar al que más le tiran.",
    trophiesTitle: "Palmarés",
    trophiesIntro:
      "Las copas se resuelven por la final — incluidas las tandas de penaltis, contando goles de la tanda, no el marcador que arrastra el evento. Las ligas, por la tabla. El crédito del jugador es el valor del título × Match Score en esa competición / el máximo del compañero de su misma posición. Un suplente con muchos minutos flojos no cobra más que el titular que produjo más.",
    thTitle: "Título",
    thChampion: "Campeón",
    thRunner: "Subcampeón",
    trophiesNote:
      "Las ligas Big 5 se anclan a la Premier (0.80, por debajo de la Champions) y se separan con la raíz del coeficiente UEFA de país. El Mundial campeón vale 1.20.",
    stages: {
      regular_season: "Liga / temporada regular",
      league_phase: "Fase de liga",
      group_stage: "Fase de grupos",
      playoff: "Playoff",
      round_of_32: "Dieciseisavos",
      round_of_16: "Octavos",
      quarter_final: "Cuartos",
      semi_final: "Semifinales",
      third_place: "Tercer puesto",
      final: "Final",
    },
  },
  charts: {
    performance: "Rendimiento",
    trophies: "Palmarés",
  },
} as const;

type DeepStringify<T> = {
  [K in keyof T]: T[K] extends string
    ? string
    : T[K] extends readonly (infer U)[]
      ? DeepStringify<U>[]
      : T[K] extends object
        ? DeepStringify<T[K]>
        : T[K];
};

export default es;
export type Dictionary = DeepStringify<typeof es>;
