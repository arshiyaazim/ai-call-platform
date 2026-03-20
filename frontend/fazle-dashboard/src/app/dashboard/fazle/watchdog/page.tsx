'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { watchdogService, type SystemStatus } from '@/services/watchdog';
import {
  Shield, RefreshCw, Loader2, Cpu, MemoryStick, Activity,
  Play, Pause, Server, AlertTriangle, CheckCircle2, XCircle,
  Bot, GitBranch, Wrench, CalendarClock,
} from 'lucide-react';

export default function WatchdogPage() {
  const [status, setStatus] = React.useState<SystemStatus | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);
  const [restartName, setRestartName] = React.useState('');
  const [message, setMessage] = React.useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchStatus = React.useCallback(async () => {
    try {
      const data = await watchdogService.getStatus();
      setStatus(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchStatus(); }, [fetchStatus]);

  // Auto-refresh every 30 seconds
  React.useEffect(() => {
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleRestart = async () => {
    if (!restartName.trim()) return;
    setActionLoading('restart');
    try {
      const res = await watchdogService.restartContainer(restartName.trim());
      setMessage({ text: `Restart initiated: ${res.command}`, type: 'success' });
      setRestartName('');
    } catch {
      setMessage({ text: 'Restart failed', type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  const handlePause = async () => {
    setActionLoading('pause');
    try {
      await watchdogService.pauseAI();
      setMessage({ text: 'AI systems paused', type: 'success' });
      fetchStatus();
    } catch {
      setMessage({ text: 'Pause failed', type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleResume = async () => {
    setActionLoading('resume');
    try {
      await watchdogService.resumeAI();
      setMessage({ text: 'AI systems resumed', type: 'success' });
      fetchStatus();
    } catch {
      setMessage({ text: 'Resume failed', type: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const containers = status?.containers || [];
  const ai = status?.ai_activity;
  const safety = status?.safety;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Watchdog Control Panel</h1>
          <p className="text-muted-foreground">Monitor and control all AI systems in real-time</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchStatus(); }}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Alert Message */}
      {message && (
        <div className={`rounded-lg border p-3 flex items-center gap-2 ${message.type === 'success' ? 'border-green-500/40 bg-green-500/10 text-green-700 dark:text-green-400' : 'border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-400'}`}>
          {message.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          <span className="text-sm">{message.text}</span>
          <Button variant="ghost" size="sm" className="ml-auto h-6 px-2" onClick={() => setMessage(null)}>×</Button>
        </div>
      )}

      {/* AI Activity Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{ai?.running_agents ?? 0}</p>
              <p className="text-sm text-muted-foreground">Active Agents</p>
            </div>
            <Bot className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{ai?.active_workflows ?? 0}</p>
              <p className="text-sm text-muted-foreground">Running Workflows</p>
            </div>
            <GitBranch className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{ai?.queued_tasks ?? 0}</p>
              <p className="text-sm text-muted-foreground">Queued Tasks</p>
            </div>
            <CalendarClock className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{ai?.tools_active ?? 0}</p>
              <p className="text-sm text-muted-foreground">Active Tools</p>
            </div>
            <Wrench className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
      </div>

      {/* Safety + Controls */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Guardrail Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" /> Safety Monitoring
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">Guardrail Status</span>
              <Badge variant={safety?.guardrail_status === 'active' ? 'default' : 'destructive'}>
                {safety?.guardrail_status ?? 'unknown'}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Blocked Actions (24h)</span>
              <span className="text-sm font-mono font-medium">{safety?.blocked_actions_24h ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Pending Approvals</span>
              <span className="text-sm font-mono font-medium">{safety?.pending_approvals ?? 0}</span>
            </div>
          </CardContent>
        </Card>

        {/* Controls */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" /> System Controls
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={handlePause} disabled={actionLoading === 'pause'}>
                {actionLoading === 'pause' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Pause className="mr-2 h-4 w-4" />}
                Pause All AI
              </Button>
              <Button variant="outline" className="flex-1" onClick={handleResume} disabled={actionLoading === 'resume'}>
                {actionLoading === 'resume' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                Resume All AI
              </Button>
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="Container name to restart"
                value={restartName}
                onChange={(e) => setRestartName(e.target.value)}
                className="flex-1"
              />
              <Button variant="destructive" size="sm" onClick={handleRestart} disabled={!restartName.trim() || actionLoading === 'restart'}>
                {actionLoading === 'restart' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                Restart
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Container Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" /> Container Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {containers.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">No container data available</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-medium">Container</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">CPU %</th>
                    <th className="pb-2 font-medium">Memory %</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {containers.map((c) => (
                    <tr key={c.name} className="hover:bg-muted/50">
                      <td className="py-2 font-mono text-xs">{c.name}</td>
                      <td className="py-2">
                        <Badge variant={c.status === 'running' ? 'default' : c.status === 'stopped' ? 'destructive' : 'secondary'}>
                          {c.status}
                        </Badge>
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          <Cpu className="h-3 w-3 text-muted-foreground" />
                          <div className="w-20 bg-muted rounded-full h-1.5">
                            <div className="bg-primary h-1.5 rounded-full" style={{ width: `${Math.min(c.cpu, 100)}%` }} />
                          </div>
                          <span className="text-xs font-mono">{c.cpu.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          <MemoryStick className="h-3 w-3 text-muted-foreground" />
                          <div className="w-20 bg-muted rounded-full h-1.5">
                            <div className={`h-1.5 rounded-full ${c.memory > 80 ? 'bg-red-500' : 'bg-primary'}`} style={{ width: `${Math.min(c.memory, 100)}%` }} />
                          </div>
                          <span className="text-xs font-mono">{c.memory.toFixed(1)}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Activity */}
      {ai?.recent_actions && ai.recent_actions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" /> Recent AI Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {ai.recent_actions.map((action, i) => (
                <div key={i} className="flex items-center gap-3 text-sm">
                  <span className="text-xs text-muted-foreground font-mono w-20 flex-shrink-0">{action.time}</span>
                  <span>{action.action}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
