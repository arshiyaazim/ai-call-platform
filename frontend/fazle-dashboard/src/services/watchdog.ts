import { apiGet, apiPost } from './api';

export interface SystemStatus {
  containers: { name: string; status: string; cpu: number; memory: number }[];
  ai_activity: {
    running_agents: number;
    active_workflows: number;
    queued_tasks: number;
    tools_active: number;
    recent_actions: { action: string; time: string }[];
  };
  safety: {
    guardrail_status: string;
    blocked_actions_24h: number;
    pending_approvals: number;
  };
}

export const watchdogService = {
  getStatus: () => apiGet<SystemStatus>('/system/status'),
  restartContainer: (name: string) => apiPost<{ status: string; command: string }>('/system/container/restart', { container_name: name }),
  pauseAI: () => apiPost<{ status: string }>('/system/ai/pause'),
  resumeAI: () => apiPost<{ status: string }>('/system/ai/resume'),
};
