'use client';

import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { apiGet, apiPost } from '@/services/api';
import type { GraphNode, GraphStats } from '@/types';
import { Network, Search, BarChart3, Loader2, RefreshCw, Plus } from 'lucide-react';

export default function KnowledgeGraphPage() {
  const [stats, setStats] = React.useState<GraphStats | null>(null);
  const [nodes, setNodes] = React.useState<GraphNode[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [querying, setQuerying] = React.useState(false);
  const [queryInput, setQueryInput] = React.useState('');
  const [queryResults, setQueryResults] = React.useState<GraphNode[]>([]);
  const [filterType, setFilterType] = React.useState<string>('all');
  const [updateText, setUpdateText] = React.useState('');
  const [updating, setUpdating] = React.useState(false);

  const nodeTypes = ['person', 'project', 'company', 'conversation', 'task', 'topic', 'location', 'concept'];

  const fetchData = React.useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, nodesData] = await Promise.all([
        apiGet<GraphStats>('/knowledge-graph/stats'),
        apiGet<{ nodes: GraphNode[] }>('/knowledge-graph/nodes?limit=100'),
      ]);
      setStats(statsData);
      setNodes(nodesData.nodes || []);
    } catch {
      setStats(null);
      setNodes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  const handleQuery = async () => {
    if (!queryInput.trim()) return;
    setQuerying(true);
    try {
      const data = await apiPost<{ nodes: GraphNode[] }>('/knowledge-graph/query', {
        query: queryInput,
        node_type: filterType !== 'all' ? filterType : undefined,
      });
      setQueryResults(data.nodes || []);
    } catch {
      setQueryResults([]);
    } finally {
      setQuerying(false);
    }
  };

  const handleUpdate = async () => {
    if (!updateText.trim()) return;
    setUpdating(true);
    try {
      await apiPost('/knowledge-graph/update', { text: updateText });
      setUpdateText('');
      fetchData();
    } catch (err) {
      console.error('Failed to update graph:', err);
    } finally {
      setUpdating(false);
    }
  };

  const typeColor = (type: string) => {
    const colors: Record<string, string> = {
      person: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
      project: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
      company: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
      topic: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
      concept: 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-300',
      task: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
      conversation: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300',
      location: 'bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-300',
    };
    return colors[type] || 'bg-gray-100 text-gray-800';
  };

  const filteredNodes = filterType === 'all' ? nodes : nodes.filter((n) => n.node_type === filterType);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Knowledge Graph</h1>
          <p className="text-muted-foreground">Explore entities, relationships, and context</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Total Nodes</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{stats.total_nodes}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Relationships</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{stats.total_relationships}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Node Types</CardTitle></CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1">
                {Object.entries(stats.node_types || {}).map(([type, count]) => (
                  <Badge key={type} variant="outline" className="text-xs">{type}: {count}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Update Graph from Text */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" /> Update Graph</CardTitle>
          <CardDescription>Extract entities and relationships from text</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="update-text">Text</Label>
            <Input
              id="update-text"
              placeholder="e.g., John works at Google on the AI research project..."
              value={updateText}
              onChange={(e) => setUpdateText(e.target.value)}
            />
          </div>
          <Button onClick={handleUpdate} disabled={updating || !updateText.trim()}>
            {updating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Network className="mr-2 h-4 w-4" />}
            Extract & Store
          </Button>
        </CardContent>
      </Card>

      {/* Query */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Search className="h-5 w-5" /> Query Graph</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Search for entities..."
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
              className="flex-1"
            />
            <Button onClick={handleQuery} disabled={querying || !queryInput.trim()}>
              {querying ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            </Button>
          </div>
          {queryResults.length > 0 && (
            <div className="space-y-2 mt-3">
              <p className="text-sm font-medium">{queryResults.length} result(s)</p>
              {queryResults.map((node) => (
                <div key={node.id} className="rounded border p-3">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${typeColor(node.node_type)}`}>{node.node_type}</span>
                    <span className="font-medium">{node.name}</span>
                  </div>
                  {node.properties && Object.keys(node.properties).length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {Object.entries(node.properties).map(([k, v]) => (
                        <span key={k} className="text-xs text-muted-foreground">{k}: {String(v)}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Node List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" /> Nodes ({filteredNodes.length})
            </CardTitle>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {nodeTypes.map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredNodes.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No nodes found. Update the graph to add entities.</p>
          ) : (
            <div className="space-y-2">
              {filteredNodes.map((node) => (
                <div key={node.id} className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors">
                  <div className="flex items-center gap-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${typeColor(node.node_type)}`}>{node.node_type}</span>
                    <span className="font-medium">{node.name}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">{new Date(node.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
