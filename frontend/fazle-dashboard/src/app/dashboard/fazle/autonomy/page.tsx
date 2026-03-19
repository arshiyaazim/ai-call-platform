'use client';

import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { apiGet, apiPost } from '@/services/api';
import type { AutonomyPlan } from '@/types';
import { Zap, Play, Eye, Loader2, Plus, RefreshCw } from 'lucide-react';

export default function AutonomyPage() {
  const [plans, setPlans] = React.useState<AutonomyPlan[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [creating, setCreating] = React.useState(false);
  const [goalInput, setGoalInput] = React.useState('');
  const [contextInput, setContextInput] = React.useState('');
  const [selectedPlan, setSelectedPlan] = React.useState<AutonomyPlan | null>(null);

  const fetchPlans = React.useCallback(async () => {
    try {
      const data = await apiGet<{ plans: AutonomyPlan[] }>('/autonomy/plans?limit=50');
      setPlans(data.plans || []);
    } catch {
      setPlans([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchPlans(); }, [fetchPlans]);

  const createPlan = async (autoExecute: boolean) => {
    if (!goalInput.trim()) return;
    setCreating(true);
    try {
      const data = await apiPost<{ plan: AutonomyPlan }>('/autonomy/plan', {
        goal: goalInput,
        context: contextInput || undefined,
        auto_execute: autoExecute,
      });
      if (data.plan) {
        setPlans((prev) => [data.plan, ...prev]);
        setGoalInput('');
        setContextInput('');
      }
    } catch (err) {
      console.error('Failed to create plan:', err);
    } finally {
      setCreating(false);
    }
  };

  const executePlan = async (planId: string) => {
    try {
      await apiPost('/autonomy/execute', { plan_id: planId });
      fetchPlans();
    } catch (err) {
      console.error('Failed to execute plan:', err);
    }
  };

  const viewPlan = async (planId: string) => {
    try {
      const data = await apiGet<{ plan: AutonomyPlan }>(`/autonomy/plan/${planId}`);
      setSelectedPlan(data.plan);
    } catch (err) {
      console.error('Failed to fetch plan:', err);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'default';
      case 'executing': return 'secondary';
      case 'failed': return 'destructive';
      case 'paused': return 'outline';
      default: return 'secondary';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Autonomy Engine</h1>
          <p className="text-muted-foreground">Create and manage autonomous execution plans</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchPlans}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Create Plan */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5" /> New Autonomy Plan
          </CardTitle>
          <CardDescription>Define a goal and Fazle will decompose it into actionable steps</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="goal">Goal</Label>
            <Input
              id="goal"
              placeholder="e.g., Research the latest AI frameworks and summarize findings"
              value={goalInput}
              onChange={(e) => setGoalInput(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="context">Context (optional)</Label>
            <Input
              id="context"
              placeholder="Additional context or constraints..."
              value={contextInput}
              onChange={(e) => setContextInput(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={() => createPlan(false)} disabled={creating || !goalInput.trim()}>
              {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
              Generate Plan
            </Button>
            <Button variant="secondary" onClick={() => createPlan(true)} disabled={creating || !goalInput.trim()}>
              <Play className="mr-2 h-4 w-4" /> Generate & Execute
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Plan List */}
      <Card>
        <CardHeader>
          <CardTitle>Plans ({plans.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : plans.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No plans yet. Create your first autonomy plan above.</p>
          ) : (
            <div className="space-y-3">
              {plans.map((plan) => (
                <div
                  key={plan.id}
                  className="flex items-center justify-between rounded-lg border p-4 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{plan.goal}</p>
                    <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                      <Badge variant={statusColor(plan.status)}>{plan.status}</Badge>
                      <span>{plan.steps.length} steps</span>
                      <span>·</span>
                      <span>{new Date(plan.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <Button variant="ghost" size="sm" onClick={() => viewPlan(plan.id)}>
                      <Eye className="h-4 w-4" />
                    </Button>
                    {plan.status === 'pending' && (
                      <Button variant="outline" size="sm" onClick={() => executePlan(plan.id)}>
                        <Play className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Plan Detail Modal */}
      {selectedPlan && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Plan: {selectedPlan.goal}</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setSelectedPlan(null)}>✕</Button>
            </div>
            <CardDescription>
              Status: <Badge variant={statusColor(selectedPlan.status)}>{selectedPlan.status}</Badge>
              {selectedPlan.reflection && ' · Has reflection'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {selectedPlan.steps.map((step, i) => (
              <div key={step.id} className="rounded border p-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono bg-muted px-2 py-0.5 rounded">{i + 1}</span>
                  <span className="font-medium">{step.action}</span>
                  <Badge variant={step.status === 'completed' ? 'default' : step.status === 'failed' ? 'destructive' : 'outline'}>
                    {step.status}
                  </Badge>
                  {step.tool && <span className="text-xs text-muted-foreground">tool: {step.tool}</span>}
                </div>
                <p className="text-sm text-muted-foreground mt-1">{step.description}</p>
                {step.result && <p className="text-sm mt-1 text-green-600 dark:text-green-400">{step.result}</p>}
                {step.error && <p className="text-sm mt-1 text-red-600 dark:text-red-400">{step.error}</p>}
              </div>
            ))}
            {selectedPlan.reflection && (
              <div className="rounded border border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-800 p-3 mt-4">
                <p className="font-medium text-sm mb-1">Reflection</p>
                <p className="text-sm text-muted-foreground">{selectedPlan.reflection}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
