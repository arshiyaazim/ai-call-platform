export interface DashboardStats {
  active_agents: number;
  total_memories: number;
  scheduled_tasks: number;
  average_latency: number;
  active_conversations: number;
}

export interface Memory {
  id: string;
  content: string;
  type: string;
  created: string;
  status: string;
  locked: boolean;
}

export interface Agent {
  id: string;
  name: string;
  model: string;
  priority: number;
  status: 'active' | 'inactive' | 'error';
  enabled: boolean;
}

export interface Plugin {
  id: string;
  name: string;
  description: string;
  version: string;
  status: 'active' | 'inactive' | 'error';
  enabled: boolean;
}

export interface Task {
  id: string;
  name: string;
  schedule: string;
  status: 'running' | 'paused' | 'completed' | 'failed';
  last_run: string | null;
  next_run: string | null;
}

export interface Persona {
  name: string;
  tone: string;
  language: string;
  speaking_style: string;
  knowledge_notes: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  user_query: string;
  agent_route: string;
  tools_used: string[];
  latency: number;
}

export interface ApiError {
  detail: string;
  status: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

// ── Phase-5 Autonomy Types ─────────────────────────────────

export interface PlanStep {
  id: string;
  action: string;
  description: string;
  tool: string | null;
  depends_on: string[];
  status: string;
  result: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface AutonomyPlan {
  id: string;
  goal: string;
  context: string | null;
  steps: PlanStep[];
  status: 'pending' | 'planning' | 'executing' | 'reflecting' | 'completed' | 'failed' | 'paused';
  reflection: string | null;
  created_at: string;
  updated_at: string | null;
  completed_at: string | null;
  retry_count: number;
  user_id: string | null;
}

// ── Phase-5 Knowledge Graph Types ──────────────────────────

export interface GraphNode {
  id: string;
  name: string;
  node_type: 'person' | 'project' | 'company' | 'conversation' | 'task' | 'topic' | 'location' | 'concept';
  properties: Record<string, unknown>;
  created_at: string;
  mention_count: number;
}

export interface GraphRelationship {
  id: string;
  source_id: string;
  target_id: string;
  relationship_type: string;
  weight: number;
}

export interface GraphStats {
  total_nodes: number;
  total_relationships: number;
  node_types: Record<string, number>;
  relationship_types: Record<string, number>;
  top_entities: Array<{ name: string; type: string; mentions: number }>;
}

// ── Phase-5 Autonomous Task Types ──────────────────────────

export interface AutonomousTask {
  id: string;
  name: string;
  task_type: 'research' | 'monitor' | 'reminder' | 'digest' | 'learning' | 'custom';
  description: string;
  trigger: string;
  interval_minutes: number | null;
  status: 'active' | 'paused' | 'completed' | 'failed' | 'cancelled';
  last_run: string | null;
  next_run: string | null;
  run_count: number;
  last_result: string | null;
  last_error: string | null;
  created_at: string;
}

// ── Phase-5 Self-Learning Types ────────────────────────────

export interface LearningInsight {
  id: string;
  insight_type: 'pattern' | 'preference' | 'improvement' | 'routing_optimization' | 'knowledge_gap' | 'behavioral';
  title: string;
  description: string;
  confidence: number;
  evidence_count: number;
  action_suggested: string | null;
  applied: boolean;
  created_at: string;
}

export interface LearningStats {
  total_insights: number;
  applied_insights: number;
  patterns_detected: number;
  routing_optimizations: number;
  analysis_runs: number;
  last_analysis: string | null;
}

// ── Phase-5 Tool Engine Types ──────────────────────────────

export interface ToolDefinition {
  id: string;
  name: string;
  category: string;
  description: string;
  enabled: boolean;
  requires_approval: boolean;
  status: 'available' | 'disabled' | 'error';
  usage_count: number;
  last_used: string | null;
}

// ── AI Safety Guardrail Types ──────────────────────────────

export interface GuardrailPolicy {
  id: string;
  name: string;
  description: string;
  category: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  rule_type: 'keyword' | 'pattern' | 'rate_limit' | 'approval_required';
  rule_config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
}

export interface GuardrailActionLog {
  id: string;
  action_type: string;
  input_text: string;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  policies_triggered: string[];
  decision: 'allowed' | 'blocked' | 'pending_approval';
  review_status: 'pending' | 'approved' | 'rejected';
  reviewed_by: string | null;
  review_notes: string | null;
  created_at: string;
}

export interface GuardrailStats {
  total_checks: number;
  blocked: number;
  allowed: number;
  pending_review: number;
  risk_distribution: Record<string, number>;
  top_triggered_policies: Array<{ policy: string; count: number }>;
}

// ── Observability Types ────────────────────────────────────

export interface ObservabilityMetrics {
  api_request_rate: number;
  api_latency_p95: number;
  container_count: number;
  healthy_services: number;
}

export interface ServiceHealth {
  service: string;
  instance: string;
  up: boolean;
}

export interface ContainerStats {
  name: string;
  cpu_percent: number;
  memory_mb: number;
}

// ── Workflow Orchestration Types ────────────────────────────

export interface WorkflowStep {
  name: string;
  type: 'llm_call' | 'tool_call' | 'condition' | 'delay' | 'webhook';
  config: Record<string, unknown>;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  status: 'draft' | 'running' | 'completed' | 'failed' | 'stopped';
  trigger_type: 'manual' | 'schedule' | 'event';
  current_step: number;
  result: Record<string, unknown>;
  error: string;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface WorkflowLog {
  id: string;
  workflow_id: string;
  step_index: number;
  level: string;
  message: string;
  data: Record<string, unknown>;
  created_at: string | null;
}

// ── Tool Marketplace Types ─────────────────────────────────

export interface MarketplaceTool {
  id: string;
  name: string;
  category: string;
  description: string;
  version: string;
  enabled: boolean;
  installed: boolean;
  requires_approval: boolean;
  status: 'available' | 'disabled' | 'error';
  usage_count: number;
  last_used: string | null;
}
