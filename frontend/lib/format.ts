const LANGS: Record<string, string> = {
  en: "English", de: "German", es: "Spanish", fr: "French", pt: "Portuguese", it: "Italian", nl: "Dutch",
  pl: "Polish", sv: "Swedish", da: "Danish", no: "Norwegian", fi: "Finnish", tr: "Turkish", ru: "Russian",
  uk: "Ukrainian", ar: "Arabic", hi: "Hindi", ur: "Urdu", ja: "Japanese", ko: "Korean", "zh-cn": "Chinese",
  zh: "Chinese", id: "Indonesian", ms: "Malay", vi: "Vietnamese", th: "Thai", cs: "Czech", ro: "Romanian",
  el: "Greek", he: "Hebrew", und: "Unknown",
};

export const languageName = (code: string) => LANGS[code?.toLowerCase()] ?? (code ? code.toUpperCase() : "Unknown");

export const CATEGORY_LABEL: Record<string, string> = {
  bug: "Bug", feature_request: "Feature request", usability: "Usability", performance: "Performance",
  pricing: "Pricing & billing", support: "Support", praise: "Praise", question: "Question", other: "Other",
};

export const STATUS_LABEL: Record<string, string> = {
  under_review: "Under review", planned: "Planned", in_progress: "In progress", shipped: "Shipped", declined: "Declined",
};

export const RECOMMENDATION_LABEL: Record<string, string> = {
  build_now: "Build now", build_later: "Build later", investigate: "Investigate first", decline: "Decline",
};

export const COMPONENT_LABEL: Record<string, string> = {
  demand: "Demand", revenue: "Revenue at stake", pain: "Customer pain", momentum: "Momentum", reach: "Global reach", rice: "RICE",
};

export const money = (v: number | null | undefined) =>
  v == null ? "–" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v);

export const num = (v: number | null | undefined, digits = 0) =>
  v == null ? "–" : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(v);

export const pct = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);

export function sentimentTone(s: number | null | undefined): "positive" | "neutral" | "negative" | "none" {
  if (s == null) return "none";
  if (s < -0.2) return "negative";
  if (s > 0.2) return "positive";
  return "neutral";
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "";
  let value = Math.abs(Date.now() - new Date(iso).getTime()) / 1000;
  if (value < 60) return "just now";
  const steps: [number, string][] = [[60, "m"], [60, "h"], [24, "d"], [7, "w"], [4.35, "mo"], [12, "y"]];
  let label = "s";
  for (const [div, unit] of steps) {
    if (value < div) break;
    value /= div;
    label = unit;
  }
  return `${Math.floor(value)}${label} ago`;
}

export const shortDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "";

export function providerLabel(by: string): string {
  if (!by) return "";
  const [name, ...rest] = by.split(":");
  const nice: Record<string, string> = { anthropic: "Claude", openai: "OpenAI", ollama: "Ollama", heuristic: "Offline engine" };
  const model = rest.join(":").split(" ")[0];
  const suffix = by.includes("fallback") ? " (fallback)" : "";
  return `${nice[name] ?? name}${model && name !== "heuristic" ? ` · ${model}` : ""}${suffix}`;
}
