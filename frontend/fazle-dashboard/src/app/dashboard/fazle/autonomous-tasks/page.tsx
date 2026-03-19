'use client';

import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { apiGet, apiPost, apiDelete } from '@/services/api';
import type { AutonomousTask } from '@/types';
import { PlayCircle, Pause, Trash2, Loader2, Plus, RefreshCw, History } from 'lucide-react';

export default function AutonomousTasksPage() {
  const [tasks, setTasks] = React.useState<AutonomousTask[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [creating, setCreating] = React.useState(false);
  const [showHistory, setShowHistory] = React.useState(false);
  const [history, setHistory] = React.useState<Array<{ task_id: string; executed_at: string; result: string }>>([]);

  const [name, setName] = React.useState('');
  const [taskType, setTaskType] = React.useState('research');
  const [config, setConfig] = React.useState('');
  const [interval, setInterval_] = React.useState('3600');

  const taskTypes = ['research', 'monitor', 'reminder', 'digest', 'learning', 'custom'];

  const fetchTasks = React.useCallback(async () => {
    try {
      const data = await apiGet<{ tasks: AutonomousTask[] }>('/autonomous-tasks/list');
      setTasks(data.tasks || []);
    } catch {
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchTasks(); }, [fetchTasks]);

  const createTask = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      let parsedConfig = {};
      if (config.trim()) {
        try { parsedConfig = JSON.parse(config); } catch { parsedConfig = { raw: config }; }
      }
      await apiPost('/autonomous-tasks/create', {
        name,
        task_type: taskType,
        config: parsedConfig,
        interval_seconds: parseInt(interval) || 3600,
      });
      setName('');
      setConfig('');
      fetchTasks();
    } catch (err) {
      console.error('Failed to create task:', err);
    } finally {
      setCreating(false);
    }
  };

  const runTask = async (taskId: string) => {
    try {
      await apiPost(`/autonomous-tasks/${taskId}/run`, {});
      fetchTasks();
    } catch (err) {
      console.error('Failed to run task:', err);
    }
  };

  const pauseTask = async (taskId: string) => {
    try {
      await apiPost(`/autonomous-tasks/${taskId}/pause`, {});
      fetchTasks();
    } catch (err) {
      console.error('Failed to pause task:', err);
    }
  };

  const deleteTask = async (taskId: string) => {
    try {
      await apiDelete(`/autonomous-tasks/${taskId}`);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (err) {
      console.error('Failed to delete task:', err);
    }
  };

  const fetchHistory = async () => {
    try {
      const data = await apiGet<{ history: Array<{ task_id: string; executed_at: string; result: string }> }>('/autonomous-tasks/history?limit=50');
      setHistory(data.history || []);
      setShowHistory(true);
    } catch {
      setHistory([]);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'active': return 'default';
      case 'running': return 'secondary';
      case 'paused': return 'outline';
      case 'completed': return 'default';
      case 'failed': return 'destructive';
      default: return 'secondary';
    }
  };

  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
    return `${Math.round(seconds / 86400)}d`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Autonomous Tasks</h1>
          <p className="text-muted-foreground">Schedule and manage background autonomous tasks</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchHistory}>
            <History className="mr-2 h-4 w-4" /> History
          </Button>
          <Button variant="outline" size="sm" onClick={fetchTasks}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
        </div>
      </div>

      {/* Create Task */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" /> New Autonomous Task</CardTitle>
          <CardDescription>Create a background task that runs on a schedule</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="task-name">Task Name</Label>
              <Input
                id="task-name"
                placeholder="e.g., Daily news digest"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Task Type</Label>
              <Select value={taskType} onValueChange={setTaskType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {taskTypes.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="config">Config (JSON or text)</Label>
              <Input
                id="config"
                placeholder='{"topic": "AI news", "sources": ["arxiv"]}'
                value={config}
                onChange={(e) => setConfig(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="interval">Interval (seconds)</Label>
              <Input
                id="interval"
                type="number"
                min="60"
                placeholder="3600"
                value={interval}
                onChange={(e) => setInterval_(e.target.value)}
              />
            </div>
          </div>
          <Button onClick={createTask} disabled={creating || !name.trim()}>
            {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
            Create Task
          </Button>
        </CardContent>
      </Card>

      {/* Task List */}
      <Card>
        <CardHeader>
          <CardTitle>Tasks ({tasks.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : tasks.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No autonomous tasks yet.</p>
          ) : (
            <div className="space-y-3">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-center justify-between rounded-lg border p-4 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{task.name}</p>
                      <Badge variant={statusColor(task.status)}>{task.status}</Badge>
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                      <span className="capitalize">{task.task_type}</span>
                      <span>·</span>
                      <span>Every {formatInterval(task.interval_seconds)}</span>
                      {task.last_run && (
                        <>
                          <span>·</span>
                          <span>Last run: {new Date(task.last_run).toLocaleString()}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1 ml-4">
                    {(task.status === 'active' || task.status === 'paused') && (
                      <Button variant="ghost" size="sm" onClick={() => runTask(task.id)} title="Run now">
                        <PlayCircle className="h-4 w-4" />
                      </Button>
                    )}
                    {task.status === 'active' && (
                      <Button variant="ghost" size="sm" onClick={() => pauseTask(task.id)} title="Pause">
                        <Pause className="h-4 w-4" />
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => deleteTask(task.id)} title="Delete" className="text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* History */}
      {showHistory && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2"><History className="h-5 w-5" /> Execution History</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setShowHistory(false)}>✕</Button>
            </div>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-center text-muted-foreground py-4">No execution history yet.</p>
            ) : (
              <div className="space-y-2">
                {history.map((entry, i) => (
                  <div key={i} className="rounded border p-3 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs">{entry.task_id.slice(0, 8)}</span>
                      <span className="text-muted-foreground">{new Date(entry.executed_at).toLocaleString()}</span>
                    </div>
                    <p className="mt-1 text-muted-foreground">{entry.result}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
