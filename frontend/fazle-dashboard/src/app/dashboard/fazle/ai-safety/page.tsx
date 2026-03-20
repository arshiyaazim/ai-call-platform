'use client';

import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { apiGet, apiPost, apiPut, apiDelete } from '@/services/api';
import type { GuardrailPolicy, GuardrailActionLog, GuardrailStats } from '@/types';
import { useAuthStore } from '@/store/auth';
import {
  ShieldAlert, ShieldCheck, ShieldX, RefreshCw, Plus, Loader2,
  AlertTriangle, CheckCircle2, XCircle, Eye, Trash2, ToggleLeft, ToggleRight
} from 'lucide-react';

type TabId = 'overview' | 'policies' | 'logs';

const severityColor: Record<string, string> = {
  low: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  high: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
  critical: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

const decisionIcon: Record<string, React.ReactNode> = {
  allowed: <CheckCircle2 className="h-4 w-4 text-green-500" />,
  blocked: <XCircle className="h-4 w-4 text-red-500" />,
  pending_approval: <AlertTriangle className="h-4 w-4 text-yellow-500" />,
};

export default function AISafetyPage() {
  const { role } = useAuthStore();
  const isAdmin = role === 'admin';

  const [tab, setTab] = React.useState<TabId>('overview');
  const [stats, setStats] = React.useState<GuardrailStats | null>(null);
  const [policies, setPolicies] = React.useState<GuardrailPolicy[]>([]);
  const [logs, setLogs] = React.useState<GuardrailActionLog[]>([]);
  const [loading, setLoading] = React.useState(true);

  // Create policy form
  const [showCreate, setShowCreate] = React.useState(false);
  const [newPolicy, setNewPolicy] = React.useState({
    name: '', description: '', category: 'content', severity: 'medium' as const,
    rule_type: 'keyword' as const, rule_config: '{}',
  });
  const [creating, setCreating] = React.useState(false);

  // Log filters
  const [filterRisk, setFilterRisk] = React.useState('');
  const [filterDecision, setFilterDecision] = React.useState('');

  // Review dialog
  const [reviewingLog, setReviewingLog] = React.useState<GuardrailActionLog | null>(null);
  const [reviewDecision, setReviewDecision] = React.useState('approved');
  const [reviewNotes, setReviewNotes] = React.useState('');
  const [submittingReview, setSubmittingReview] = React.useState(false);

  const fetchStats = React.useCallback(async () => {
    try {
      const data = await apiGet<GuardrailStats>('/guardrail/stats');
      setStats(data);
    } catch { setStats(null); }
  }, []);

  const fetchPolicies = React.useCallback(async () => {
    try {
      const data = await apiGet<{ policies: GuardrailPolicy[] }>('/guardrail/policies');
      setPolicies(data.policies || []);
    } catch { setPolicies([]); }
  }, []);

  const fetchLogs = React.useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (filterRisk) params.set('risk_level', filterRisk);
      if (filterDecision) params.set('decision', filterDecision);
      const data = await apiGet<{ logs: GuardrailActionLog[] }>(`/guardrail/logs?${params}`);
      setLogs(data.logs || []);
    } catch { setLogs([]); }
  }, [filterRisk, filterDecision]);

  const fetchAll = React.useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchStats(), fetchPolicies(), fetchLogs()]);
    setLoading(false);
  }, [fetchStats, fetchPolicies, fetchLogs]);

  React.useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleTogglePolicy = async (id: string) => {
    try {
      await apiPut(`/guardrail/policies/${id}/toggle`, {});
      fetchPolicies();
    } catch (err) { console.error('Toggle failed:', err); }
  };

  const handleDeletePolicy = async (id: string) => {
    if (!confirm('Delete this policy?')) return;
    try {
      await apiDelete(`/guardrail/policies/${id}`);
      fetchPolicies();
      fetchStats();
    } catch (err) { console.error('Delete failed:', err); }
  };

  const handleCreatePolicy = async () => {
    setCreating(true);
    try {
      let ruleConfig: Record<string, unknown>;
      try { ruleConfig = JSON.parse(newPolicy.rule_config); }
      catch { ruleConfig = {}; }

      await apiPost('/guardrail/policies', {
        name: newPolicy.name,
        description: newPolicy.description,
        category: newPolicy.category,
        severity: newPolicy.severity,
        rule_type: newPolicy.rule_type,
        rule_config: ruleConfig,
      });
      setShowCreate(false);
      setNewPolicy({ name: '', description: '', category: 'content', severity: 'medium', rule_type: 'keyword', rule_config: '{}' });
      fetchPolicies();
      fetchStats();
    } catch (err) { console.error('Create failed:', err); }
    finally { setCreating(false); }
  };

  const handleSubmitReview = async () => {
    if (!reviewingLog) return;
    setSubmittingReview(true);
    try {
      await apiPost(`/guardrail/logs/${reviewingLog.id}/review`, {
        decision: reviewDecision,
        notes: reviewNotes,
      });
      setReviewingLog(null);
      setReviewNotes('');
      fetchLogs();
      fetchStats();
    } catch (err) { console.error('Review failed:', err); }
    finally { setSubmittingReview(false); }
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
          <h1 className="text-3xl font-bold tracking-tight">AI Safety</h1>
          <p className="text-muted-foreground">Guardrail policies, risk monitoring, and action review</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAll}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        {(['overview', 'policies', 'logs'] as TabId[]).map((t) => (
          <Button key={t} variant={tab === t ? 'default' : 'ghost'} size="sm"
            onClick={() => { setTab(t); if (t === 'logs') fetchLogs(); }}>
            {t === 'overview' ? 'Overview' : t === 'policies' ? 'Policies' : 'Action Logs'}
          </Button>
        ))}
      </div>

      {/* ── Overview Tab ─────────────────────── */}
      {tab === 'overview' && stats && (
        <div className="space-y-6">
          {/* Stat Cards */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Checks</CardTitle>
                <ShieldAlert className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent><div className="text-2xl font-bold">{stats.total_checks}</div></CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Allowed</CardTitle>
                <ShieldCheck className="h-4 w-4 text-green-500" />
              </CardHeader>
              <CardContent><div className="text-2xl font-bold text-green-600">{stats.allowed}</div></CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Blocked</CardTitle>
                <ShieldX className="h-4 w-4 text-red-500" />
              </CardHeader>
              <CardContent><div className="text-2xl font-bold text-red-600">{stats.blocked}</div></CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
                <AlertTriangle className="h-4 w-4 text-yellow-500" />
              </CardHeader>
              <CardContent><div className="text-2xl font-bold text-yellow-600">{stats.pending_review}</div></CardContent>
            </Card>
          </div>

          {/* Risk Distribution */}
          {stats.risk_distribution && Object.keys(stats.risk_distribution).length > 0 && (
            <Card>
              <CardHeader><CardTitle>Risk Distribution</CardTitle></CardHeader>
              <CardContent>
                <div className="flex gap-4 flex-wrap">
                  {Object.entries(stats.risk_distribution).map(([level, count]) => (
                    <div key={level} className="flex items-center gap-2">
                      <Badge className={severityColor[level] || 'bg-gray-100 text-gray-800'}>{level}</Badge>
                      <span className="text-lg font-semibold">{count as number}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Top Triggered Policies */}
          {stats.top_triggered_policies && stats.top_triggered_policies.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Top Triggered Policies</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {stats.top_triggered_policies.map((tp, idx) => (
                    <div key={idx} className="flex items-center justify-between py-1 border-b last:border-0">
                      <span className="font-medium">{tp.policy}</span>
                      <Badge variant="outline">{tp.count} triggers</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* ── Policies Tab ─────────────────────── */}
      {tab === 'policies' && (
        <div className="space-y-4">
          {isAdmin && (
            <div className="flex justify-end">
              <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
                <Plus className="mr-2 h-4 w-4" /> {showCreate ? 'Cancel' : 'New Policy'}
              </Button>
            </div>
          )}

          {/* Create Policy Form */}
          {showCreate && isAdmin && (
            <Card>
              <CardHeader>
                <CardTitle>Create Policy</CardTitle>
                <CardDescription>Define a new guardrail policy rule</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input value={newPolicy.name} onChange={(e) => setNewPolicy({ ...newPolicy, name: e.target.value })}
                      placeholder="e.g. Block SQL injection" />
                  </div>
                  <div className="space-y-2">
                    <Label>Category</Label>
                    <select className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                      value={newPolicy.category} onChange={(e) => setNewPolicy({ ...newPolicy, category: e.target.value })}>
                      <option value="content">Content</option>
                      <option value="security">Security</option>
                      <option value="privacy">Privacy</option>
                      <option value="rate_limit">Rate Limit</option>
                      <option value="compliance">Compliance</option>
                    </select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input value={newPolicy.description} onChange={(e) => setNewPolicy({ ...newPolicy, description: e.target.value })}
                    placeholder="What does this policy do?" />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Severity</Label>
                    <select className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                      value={newPolicy.severity} onChange={(e) => setNewPolicy({ ...newPolicy, severity: e.target.value as 'low' | 'medium' | 'high' | 'critical' })}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Rule Type</Label>
                    <select className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                      value={newPolicy.rule_type} onChange={(e) => setNewPolicy({ ...newPolicy, rule_type: e.target.value as 'keyword' | 'pattern' | 'rate_limit' | 'approval_required' })}>
                      <option value="keyword">Keyword</option>
                      <option value="pattern">Pattern (Regex)</option>
                      <option value="rate_limit">Rate Limit</option>
                      <option value="approval_required">Approval Required</option>
                    </select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Rule Config (JSON)</Label>
                  <Input value={newPolicy.rule_config} onChange={(e) => setNewPolicy({ ...newPolicy, rule_config: e.target.value })}
                    placeholder='{"keywords": ["drop table", "rm -rf"]}' className="font-mono text-xs" />
                </div>
                <Button onClick={handleCreatePolicy} disabled={creating || !newPolicy.name}>
                  {creating ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Creating...</> : 'Create Policy'}
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Policies List */}
          {policies.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-muted-foreground">No policies configured</CardContent></Card>
          ) : (
            <div className="grid gap-3">
              {policies.map((policy) => (
                <Card key={policy.id} className={!policy.enabled ? 'opacity-60' : ''}>
                  <CardContent className="flex items-center justify-between py-4">
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{policy.name}</span>
                        <Badge className={severityColor[policy.severity]}>{policy.severity}</Badge>
                        <Badge variant="outline">{policy.rule_type}</Badge>
                        <Badge variant="outline">{policy.category}</Badge>
                        {!policy.enabled && <Badge variant="secondary">Disabled</Badge>}
                      </div>
                      <p className="text-sm text-muted-foreground">{policy.description}</p>
                    </div>
                    {isAdmin && (
                      <div className="flex items-center gap-2 ml-4">
                        <Button variant="ghost" size="sm" onClick={() => handleTogglePolicy(policy.id)}
                          title={policy.enabled ? 'Disable' : 'Enable'}>
                          {policy.enabled
                            ? <ToggleRight className="h-5 w-5 text-green-500" />
                            : <ToggleLeft className="h-5 w-5 text-gray-400" />}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDeletePolicy(policy.id)}>
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Action Logs Tab ─────────────────────── */}
      {tab === 'logs' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex gap-4 flex-wrap items-end">
            <div className="space-y-1">
              <Label className="text-xs">Risk Level</Label>
              <select className="rounded-md border px-3 py-2 text-sm bg-background"
                value={filterRisk} onChange={(e) => setFilterRisk(e.target.value)}>
                <option value="">All</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Decision</Label>
              <select className="rounded-md border px-3 py-2 text-sm bg-background"
                value={filterDecision} onChange={(e) => setFilterDecision(e.target.value)}>
                <option value="">All</option>
                <option value="allowed">Allowed</option>
                <option value="blocked">Blocked</option>
                <option value="pending_approval">Pending</option>
              </select>
            </div>
            <Button variant="outline" size="sm" onClick={fetchLogs}>
              <RefreshCw className="mr-2 h-4 w-4" /> Filter
            </Button>
          </div>

          {/* Logs List */}
          {logs.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-muted-foreground">No action logs found</CardContent></Card>
          ) : (
            <div className="space-y-2">
              {logs.map((log) => (
                <Card key={log.id}>
                  <CardContent className="py-3">
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {decisionIcon[log.decision]}
                          <span className="font-medium text-sm">{log.action_type}</span>
                          <Badge className={severityColor[log.risk_level]}>{log.risk_level}</Badge>
                          <Badge variant="outline">{log.decision.replace('_', ' ')}</Badge>
                          <span className="text-xs text-muted-foreground">
                            Score: {(log.risk_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground truncate">{log.input_text}</p>
                        {log.policies_triggered.length > 0 && (
                          <div className="flex gap-1 flex-wrap">
                            {log.policies_triggered.map((p, i) => (
                              <Badge key={i} variant="secondary" className="text-xs">{p}</Badge>
                            ))}
                          </div>
                        )}
                        {log.review_status !== 'pending' && (
                          <p className="text-xs text-muted-foreground">
                            Reviewed: {log.review_status} {log.reviewed_by ? `by ${log.reviewed_by}` : ''}
                            {log.review_notes ? ` — ${log.review_notes}` : ''}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground">{new Date(log.created_at).toLocaleString()}</p>
                      </div>
                      {isAdmin && log.review_status === 'pending' && (
                        <Button variant="outline" size="sm" onClick={() => {
                          setReviewingLog(log);
                          setReviewDecision('approved');
                          setReviewNotes('');
                        }}>
                          <Eye className="mr-1 h-4 w-4" /> Review
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Review Dialog */}
          {reviewingLog && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
              <Card className="w-full max-w-md mx-4">
                <CardHeader>
                  <CardTitle>Review Action</CardTitle>
                  <CardDescription>Action: {reviewingLog.action_type} | Risk: {reviewingLog.risk_level}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-3 bg-muted rounded-md text-sm">{reviewingLog.input_text}</div>
                  <div className="space-y-2">
                    <Label>Decision</Label>
                    <select className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                      value={reviewDecision} onChange={(e) => setReviewDecision(e.target.value)}>
                      <option value="approved">Approve</option>
                      <option value="rejected">Reject</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Notes</Label>
                    <Input value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)}
                      placeholder="Optional review notes" />
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button variant="ghost" onClick={() => setReviewingLog(null)}>Cancel</Button>
                    <Button onClick={handleSubmitReview} disabled={submittingReview}>
                      {submittingReview ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                      Submit Review
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
