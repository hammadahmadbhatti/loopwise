export type Sentiment = "positive" | "neutral" | "negative" | "";
export type OppStatus = "under_review" | "planned" | "in_progress" | "shipped" | "declined";

export interface WorkspaceRef {
  id: number;
  name: string;
  slug: string;
  role: "owner" | "admin" | "member";
}

export interface User {
  id: number;
  email: string;
  name: string;
  workspaces: WorkspaceRef[];
}

export interface Customer {
  id: number;
  email: string | null;
  name: string;
  company: string;
  country: string;
  plan: string;
  mrr: number;
  language: string;
  feedback_count?: number;
  avg_sentiment?: number | null;
  churn_signals?: number;
}

export interface Feedback {
  id: number;
  text: string;
  source: string;
  rating: number | null;
  country: string;
  page_url: string;
  status: "new" | "reviewed" | "archived";
  created_at: string;
  analysis_status: "pending" | "processing" | "done" | "failed";
  analyzed_by: string;
  analysis_error: string;
  language: string;
  translated_text: string;
  summary: string;
  sentiment: number | null;
  sentiment_label: Sentiment;
  category: string;
  urgency: string;
  churn_risk: boolean;
  keywords: string[];
  theme: { id: number; name: string } | null;
  theme_locked: boolean;
  duplicate_of_id: number | null;
  customer: Customer | null;
  linked?: boolean;
}

export interface FeedbackDetail extends Feedback {
  opportunities: { id: number; title: string; status: OppStatus }[];
  similar: { id: number; summary: string; similarity: number; language: string }[];
}

export interface Theme {
  id: number;
  name: string;
  description: string;
  keywords: string[];
  archived: boolean;
  name_locked: boolean;
  labeled_by: string;
  count: number;
  customers: number;
  mrr: number;
  avg_sentiment: number | null;
  negative_pct: number;
  churn_risk: number;
  categories: [string, number][];
  languages: string[];
  countries: string[];
  weekly: number[];
  emerging: boolean;
  opportunities: { id: number; title: string; status: OppStatus }[];
}

export interface BreakdownItem {
  component: string;
  value: number;
  weight: number;
  contribution: number;
}

export interface Metrics {
  mentions: number;
  duplicates: number;
  customers: number;
  known_customers: number;
  votes: number;
  mrr: number;
  avg_sentiment: number | null;
  negative_share: number;
  urgency_score: number;
  urgency_mix: Record<string, number>;
  churn_risk: number;
  countries: string[];
  languages: string[];
  plans: Record<string, number>;
  categories: Record<string, number>;
  recent_30: number;
  prior_30: number;
  growth_pct: number | null;
  rice_score: number | null;
  first_seen: string | null;
  last_seen: string | null;
}

export interface Opportunity {
  id: number;
  title: string;
  description: string;
  status: OppStatus;
  is_public: boolean;
  theme: { id: number; name: string } | null;
  reach: number | null;
  impact: number | null;
  confidence: number | null;
  effort: number | null;
  priority_score: number;
  breakdown: BreakdownItem[];
  metrics: Metrics;
  has_brief: boolean;
  created_at: string;
  shipped_at: string | null;
}

export interface Brief {
  summary: string;
  problem: string;
  affected_segments: string[];
  evidence: { feedback_id: number; quote: string; why_it_matters: string }[];
  risks: string[];
  options: { title: string; pros: string[]; cons: string[] }[];
  recommendation: "build_now" | "build_later" | "investigate" | "decline";
  rationale: string;
  confidence: number;
  suggested_impact: number;
  suggested_confidence: number;
}

export interface Decision {
  id: number;
  opportunity_id: number;
  opportunity_title: string | null;
  outcome: "build" | "defer" | "investigate" | "decline";
  rationale: string;
  decided_by: string | null;
  evidence_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface OpportunityDetail extends Opportunity {
  rank: number | null;
  open_count: number;
  brief: Brief | null;
  brief_by: string;
  brief_at: string | null;
  evidence: Feedback[];
  decisions: Decision[];
  notifications: { draft: number; sent: number; failed: number };
  close_the_loop?: { changelog_entry_id: number; notifications_created: number; languages: string[] } | null;
}

export interface Overview {
  days: number;
  kpis: {
    feedback: number;
    feedback_prev: number;
    avg_sentiment: number | null;
    avg_sentiment_prev: number | null;
    negative_pct: number;
    avg_rating: number | null;
    languages: number;
    countries: number;
    churn_signals: number;
    customers: number;
    pending_analysis: number;
  };
  series: { date: string; positive: number; neutral: number; negative: number; pending: number }[];
  categories: [string, number][];
  sources: [string, number][];
  languages: [string, number][];
  countries: { country: string; count: number; avg_sentiment: number | null }[];
  top_themes: { id: number; name: string; count: number; avg_sentiment: number | null; weekly: number[]; emerging: boolean }[];
  emerging: { id: number; name: string; weekly: number[]; this_week: number; baseline: number }[];
  at_risk: {
    id: number; summary: string; customer: string; company: string; mrr: number; urgency: string;
    churn_risk: boolean; language: string; created_at: string;
  }[];
}

export interface WorkspaceSettings {
  ai_provider: string;
  working_language: string;
  portal_enabled: boolean;
  portal_title: string;
  brand_color: string;
  priority_weights: Record<string, number>;
}

export interface Workspace {
  id: number;
  name: string;
  slug: string;
  role: string;
  public_key: string;
  api_key_prefix: string | null;
  settings: WorkspaceSettings;
  portal_url: string;
}

export interface AIStatus {
  preference: string;
  server_default: string;
  active: { name: string; model: string; note: string };
  providers: { name: string; title: string; model: string; available: boolean; detail: string }[];
  embeddings: { name: string; model: string };
}

export interface ChangelogEntry {
  id: number;
  opportunity_id: number | null;
  title: string;
  body: string;
  published: boolean;
  published_at: string | null;
  written_by: string;
  created_at: string;
}

export interface Notification {
  id: number;
  opportunity_id: number | null;
  opportunity_title?: string | null;
  customer_id: number | null;
  email: string;
  language: string;
  subject: string;
  body: string;
  status: "draft" | "sent" | "failed";
  channel: string;
  error: string;
  localized_by: string;
  created_at: string;
  sent_at: string | null;
}

export interface AskResult {
  answer: string;
  citations: { id: number; text: string; translated_text: string; language: string; sentiment_label: Sentiment }[];
  follow_up_questions: string[];
  answered_by: string;
  retrieved: number;
}
