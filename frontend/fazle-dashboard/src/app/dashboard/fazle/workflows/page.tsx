'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { apiGet, apiPost } from '@/services/api';
import {
  GitBranch, Play, Square, Loader2, RefreshCw, Plus, Trash2,
  ChevronDown, ChevronUp, Clock, CheckCircle2, XCircle, AlertTriangle,
} from 'lucide-react';

interface WorkflowStep {
  name: string;
  type: 'llm_call' | 'tool_call' | 'condition' | 'delay' | 'webhook';
  config: Record<string, unknown>;
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  status: string;
  trigger_type: string;
  current_step: number;
  error: string;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface WorkflowLog {
  id: string;
  workflow_id: string;
  step_index: number;
  level: string;
  message: string;
  created_at: string | null;
}

const STATUS_STYLES: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: React.ElementType }> = {
  draft: { variant: 'secondary', icon: Clock },
  running: { variant: 'default', icon: Loader2 },
  completed: { variant: 'outline', icon: CheckCircle2 },
  failed: { variant: 'destructive', icon: XCircle },
  stopped: { variant: 'secondary', icon: Square },
};

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = React.useState<Workflow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [expandedId, setExpandedId] = React.useState<string | null>(null);
  const [logs, setLogs] = React.useState<WorkflowLog[]>([]);
  const [logsLoading, setLogsLoading] = React.useState(false);
  const [showCreate, setShowCreate] = React.useState(false);
  const [creating, setCreating] = React.useState(false);

  // Create form state
  const [newName, setNewName] = React.useState('');
  const [newDesc, setNewDesc] = React.useState('');
  const [newSteps, setNewSteps] = React.useState<WorkflowStep[]>([
    { name: 'Step 1', type: 'llm_call', config: { prompt: '' } },
  ]);

  const fetchWorkflows = React.useCallback(async () => {
    try {
      const data = await apiGet<{ workflows: Workflow[] }>('/workflows');
      setWorkflows(data.workflows || []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchWorkflows(); }, [fetchWorkflows]);

  const toggleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    setLogsLoading(true);
    try {
      const data = await apiGet<{ logs: WorkflowLog[] }>(`/workflows/${id}/logs`);
      setLogs(data.logs || []);
    } catch {
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  const startWorkflow = async (id: string) => {
    await apiPost(`/workflows/${id}/start`);
    fetchWorkflows();
  };

  const stopWorkflow = async (id: string) => {
    await apiPost(`/workflows/${id}/stop`);
    fetchWorkflows();
  };

  const addStep = () => {
    setNewSteps((s) => [...s, { name: `Step ${s.length + 1}`, type: 'llm_call', config: { prompt: '' } }]);
  };

  const removeStep = (idx: number) => {
    setNewSteps((s) => s.filter((_, i) => i !== idx));
  };

  const updateStep = (idx: number, field: string, value: string) => {
    setNewSteps((s) =>
      s.map((step, i) => {
        if (i !== idx) return step;
        if (field === 'name') return { ...step, name: value };
        if (field === 'type') return { ...step, type: value as WorkflowStep['type'] };
        if (field === 'prompt') return { ...step, config: { ...step.config, prompt: value } };
        return step;
      })
    );
  };

  const createWorkflow = async () => {
    if (!newName.trim() || newSteps.length === 0) return;
    setCreating(true);
    try {
      await apiPost('/workflows/create', {
        name: newName.trim(),
        description: newDesc.trim(),
        steps: newSteps,
        trigger_type: 'manual',
      });
      setNewName('');
      setNewDesc('');
      setNewSteps([{ name: 'Step 1', type: 'llm_call', config: { prompt: '' } }]);
      setShowCreate(false);
      fetchWorkflows();
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workflows</h1>
          <p className="text-muted-foreground">Create and orchestrate multi-step AI workflows</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchWorkflows}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
            <Plus className="mr-2 h-4 w-4" /> New Workflow
          </Button>
        </div>
      </div>

      {/* Create Workflow Panel */}
      {showCreate && (
        <Card>
          <CardHeader><CardTitle>Create Workflow</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Workflow Name</Label>
                <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Daily Research Report" />
              </div>
              <div>
                <Label>Description</Label>
                <Input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="What this workflow does" />
              </div>
            </div>

            <div className="space-y-3">
              <Label>Steps</Label>
              {newSteps.map((step, idx) => (
                <div key={idx} className="flex gap-2 items-start p-3 rounded-lg border">
                  <span className="text-sm font-mono text-muted-foreground mt-2 w-6">{idx + 1}.</span>
                  <div className="flex-1 space-y-2">
                    <div className="flex gap-2">
                      <Input value={step.name} onChange={(e) => updateStep(idx, 'name', e.target.value)}
                        placeholder="Step name" className="flex-1" />
                      <select value={step.type} onChange={(e) => updateStep(idx, 'type', e.target.value)}
                        className="border rounded px-2 text-sm bg-background">
                        <option value="llm_call">LLM Call</option>
                        <option value="tool_call">Tool Call</option>
                        <option value="condition">Condition</option>
                        <option value="delay">Delay</option>
                        <option value="webhook">Webhook</option>
                      </select>
                    </div>
                    {step.type === 'llm_call' && (
                      <Textarea value={String(step.config.prompt || '')}
                        onChange={(e) => updateStep(idx, 'prompt', e.target.value)}
                        placeholder="Prompt (use {{step_0_output}} for previous step results)" rows={2} />
                    )}
                  </div>
                  {newSteps.length > 1 && (
                    <Button variant="ghost" size="icon" onClick={() => removeStep(idx)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  )}
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={addStep}>
                <Plus className="mr-2 h-4 w-4" /> Add Step
              </Button>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button onClick={createWorkflow} disabled={creating || !newName.trim()}>
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create Workflow
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        {(['draft', 'running', 'completed', 'failed'] as const).map((st) => {
          const count = workflows.filter((w) => w.status === st).length;
          return (
            <Card key={st}>
              <CardContent className="py-4 flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold">{count}</p>
                  <p className="text-sm text-muted-foreground capitalize">{st}</p>
                </div>
                {React.createElement(STATUS_STYLES[st]?.icon || Clock, {
                  className: `h-5 w-5 ${st === 'running' ? 'animate-spin' : ''} text-muted-foreground`,
                })}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Workflow List */}
      {workflows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <GitBranch className="h-12 w-12 mx-auto mb-4 opacity-40" />
            <p>No workflows yet. Create one to get started.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {workflows.map((wf) => {
            const style = STATUS_STYLES[wf.status] || STATUS_STYLES.draft;
            const isExpanded = expandedId === wf.id;
            return (
              <Card key={wf.id}>
                <CardContent className="py-4">
                  <div className="flex items-center gap-3">
                    <GitBranch className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{wf.name}</p>
                      <p className="text-sm text-muted-foreground truncate">{wf.description || 'No description'}</p>
                    </div>
                    <Badge variant={style.variant} className="flex-shrink-0">
                      {wf.status === 'running' && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                      {wf.status}
                    </Badge>
                    <span className="text-xs text-muted-foreground flex-shrink-0">
                      {wf.steps.length} step{wf.steps.length !== 1 ? 's' : ''}
                    </span>
                    <div className="flex gap-1 flex-shrink-0">
                      {(wf.status === 'draft' || wf.status === 'failed' || wf.status === 'stopped') && (
                        <Button variant="ghost" size="icon" onClick={() => startWorkflow(wf.id)} title="Start">
                          <Play className="h-4 w-4 text-green-600" />
                        </Button>
                      )}
                      {wf.status === 'running' && (
                        <Button variant="ghost" size="icon" onClick={() => stopWorkflow(wf.id)} title="Stop">
                          <Square className="h-4 w-4 text-red-500" />
                        </Button>
                      )}
                      <Button variant="ghost" size="icon" onClick={() => toggleExpand(wf.id)}>
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  {wf.status === 'running' && wf.steps.length > 0 && (
                    <div className="mt-3">
                      <div className="flex justify-between text-xs text-muted-foreground mb-1">
                        <span>Step {wf.current_step + 1} of {wf.steps.length}</span>
                        <span>{Math.round(((wf.current_step + 1) / wf.steps.length) * 100)}%</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${((wf.current_step + 1) / wf.steps.length) * 100}%` }} />
                      </div>
                    </div>
                  )}

                  {wf.error && (
                    <div className="mt-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 dark:bg-red-950/30 p-2 rounded">
                      <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                      <span className="truncate">{wf.error}</span>
                    </div>
                  )}

                  {/* Expanded: Steps + Logs */}
                  {isExpanded && (
                    <div className="mt-4 space-y-4 border-t pt-4">
                      {/* Steps */}
                      <div>
                        <h4 className="text-sm font-medium mb-2">Steps</h4>
                        <div className="space-y-1">
                          {wf.steps.map((step, idx) => (
                            <div key={idx} className="flex items-center gap-2 text-sm py-1">
                              <span className="w-5 text-center text-muted-foreground font-mono">{idx + 1}</span>
                              {idx < wf.current_step && wf.status !== 'draft' ? (
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                              ) : idx === wf.current_step && wf.status === 'running' ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
                              ) : (
                                <div className="h-3.5 w-3.5 rounded-full border" />
                              )}
                              <span>{step.name}</span>
                              <Badge variant="outline" className="text-xs ml-auto">{step.type}</Badge>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Logs */}
                      <div>
                        <h4 className="text-sm font-medium mb-2">Execution Logs</h4>
                        {logsLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : logs.length === 0 ? (
                          <p className="text-sm text-muted-foreground">No logs yet</p>
                        ) : (
                          <div className="max-h-48 overflow-y-auto space-y-1 font-mono text-xs bg-muted/50 rounded p-2">
                            {logs.map((log) => (
                              <div key={log.id} className="flex gap-2">
                                <span className="text-muted-foreground">
                                  {log.created_at ? new Date(log.created_at).toLocaleTimeString() : '--:--'}
                                </span>
                                <Badge variant={log.level === 'error' ? 'destructive' : log.level === 'warn' ? 'secondary' : 'outline'}
                                  className="text-xs h-4">
                                  {log.level}
                                </Badge>
                                <span>{log.message}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
