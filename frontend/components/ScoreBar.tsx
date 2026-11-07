"use client";

import { COMPONENT_LABEL } from "@/lib/format";
import type { Opportunity } from "@/lib/types";

export const COMPONENT_COLORS: Record<string, string> = {
  demand: "#6366f1", revenue: "#10b981", pain: "#f43f5e", momentum: "#f59e0b", reach: "#0ea5e9", rice: "#8b5cf6",
};

export function ScoreBar({ breakdown, score }: { breakdown: Opportunity["breakdown"]; score: number }) {
  return (
    <div className="w-full">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100">
        {breakdown.filter((b) => b.contribution > 0).map((b) => (
          <div key={b.component} title={`${COMPONENT_LABEL[b.component]}: +${b.contribution}`} style={{ width: `${b.contribution}%`, background: COMPONENT_COLORS[b.component] }} />
        ))}
      </div>
      <span className="sr-only">Score {score}</span>
    </div>
  );
}

