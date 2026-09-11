"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const GOLD = "#c4a35a";
const GOLD_DIM = "#8a7428";
const BLUE = "#7a8490";
const GRID = "rgba(239,230,212,0.08)";

const tooltipStyle = {
  background: "#1a1916",
  border: "1px solid rgba(239,230,212,0.14)",
  borderRadius: 2,
  fontSize: 12,
  color: "#efe6d4",
};

export function TopIndexChart({
  data,
}: {
  data: { name: string; index: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 12, top: 8, bottom: 0 }}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="name"
          width={92}
          tick={{ fill: "rgba(255,255,255,0.55)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
        <Bar dataKey="index" fill={GOLD} radius={[0, 8, 8, 0]} barSize={14} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SplitChart({
  data,
  performanceLabel = "Rendimiento",
  trophiesLabel = "Palmarés",
}: {
  data: { name: string; rendimiento: number; palmares: number }[];
  performanceLabel?: string;
  trophiesLabel?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 32 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          interval={0}
          angle={-25}
          textAnchor="end"
        />
        <YAxis hide />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
        <Bar
          dataKey="rendimiento"
          stackId="a"
          fill={GOLD}
          radius={[0, 0, 0, 0]}
          name={performanceLabel}
        />
        <Bar
          dataKey="palmares"
          stackId="a"
          fill={BLUE}
          radius={[6, 6, 0, 0]}
          name={trophiesLabel}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

const POS_COLORS: Record<string, string> = {
  FWD: GOLD,
  MID: BLUE,
  DEF: "#6e8b74",
  GK: "#9c2b2b",
};

export function PositionChart({
  data,
}: {
  data: { position_group: string; n: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          dataKey="n"
          nameKey="position_group"
          innerRadius={58}
          outerRadius={84}
          paddingAngle={3}
          stroke="none"
        >
          {data.map((entry) => (
            <Cell key={entry.position_group} fill={POS_COLORS[entry.position_group] ?? "#888"} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function MatchScoreChart({
  data,
}: {
  data: { label: string; score: number; rating: number | null }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={GOLD} stopOpacity={0.35} />
            <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="label" hide />
        <YAxis
          tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={32}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.label ?? ""}
        />
        <Area
          type="monotone"
          dataKey="score"
          stroke={GOLD}
          fill="url(#scoreFill)"
          strokeWidth={2}
          name="Match Score"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function TrophyBars({
  data,
}: {
  data: { name: string; points: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 36)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 0, bottom: 0 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="name"
          width={140}
          tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="points" fill={GOLD_DIM} radius={[0, 8, 8, 0]} barSize={12} />
      </BarChart>
    </ResponsiveContainer>
  );
}
