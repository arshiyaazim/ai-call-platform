'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { apiGet, apiPost, apiDelete } from '@/services/api';
import {
  Store, Search, Download, Loader2, RefreshCw, Power, PowerOff, Trash2,
  Package, CheckCircle2, XCircle, AlertTriangle,
} from 'lucide-react';

interface MarketplaceTool {
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

export default function ToolMarketplacePage() {
  const [tools, setTools] = React.useState<MarketplaceTool[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [search, setSearch] = React.useState('');
  const [category, setCategory] = React.useState('all');
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

  const fetchTools = React.useCallback(async () => {
    try {
      const data = await apiGet<{ tools: MarketplaceTool[] }>('/marketplace/tools');
      setTools(data.tools || []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchTools(); }, [fetchTools]);

  const installTool = async (name: string) => {
    setActionLoading(name);
    try {
      await apiPost('/marketplace/tools/install', { tool_name: name });
      fetchTools();
    } finally {
      setActionLoading(null);
    }
  };

  const enableTool = async (name: string) => {
    setActionLoading(name);
    try {
      await apiPost(`/marketplace/tools/${name}/enable`);
      fetchTools();
    } finally {
      setActionLoading(null);
    }
  };

  const disableTool = async (name: string) => {
    setActionLoading(name);
    try {
      await apiPost(`/marketplace/tools/${name}/disable`);
      fetchTools();
    } finally {
      setActionLoading(null);
    }
  };

  const removeTool = async (name: string) => {
    setActionLoading(name);
    try {
      await apiDelete(`/marketplace/tools/${name}`);
      fetchTools();
    } finally {
      setActionLoading(null);
    }
  };

  const categories = React.useMemo(() => {
    const cats = new Set(tools.map((t) => t.category));
    return ['all', ...Array.from(cats).sort()];
  }, [tools]);

  const filtered = React.useMemo(() => {
    return tools.filter((t) => {
      if (category !== 'all' && t.category !== category) return false;
      if (search) {
        const q = search.toLowerCase();
        return t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q);
      }
      return true;
    });
  }, [tools, search, category]);

  const installedCount = tools.filter((t) => t.installed !== false).length;
  const enabledCount = tools.filter((t) => t.enabled).length;

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
          <h1 className="text-3xl font-bold tracking-tight">Tool Marketplace</h1>
          <p className="text-muted-foreground">Install, enable, and manage AI tool plugins</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchTools}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{tools.length}</p>
              <p className="text-sm text-muted-foreground">Total Tools</p>
            </div>
            <Package className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{installedCount}</p>
              <p className="text-sm text-muted-foreground">Installed</p>
            </div>
            <Download className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{enabledCount}</p>
              <p className="text-sm text-muted-foreground">Active</p>
            </div>
            <Power className="h-5 w-5 text-green-500" />
          </CardContent>
        </Card>
      </div>

      {/* Search + Category Filter */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tools..." className="pl-9" />
        </div>
        <div className="flex gap-1 flex-wrap">
          {categories.map((cat) => (
            <Button key={cat} variant={category === cat ? 'default' : 'outline'} size="sm"
              onClick={() => setCategory(cat)} className="capitalize">
              {cat}
            </Button>
          ))}
        </div>
      </div>

      {/* Tool Grid */}
      {filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Store className="h-12 w-12 mx-auto mb-4 opacity-40" />
            <p>No tools found matching your criteria.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((tool) => {
            const isLoading = actionLoading === tool.name;
            return (
              <Card key={tool.id || tool.name} className="flex flex-col">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="min-w-0">
                      <CardTitle className="text-base truncate">{tool.name}</CardTitle>
                      <div className="flex gap-2 mt-1">
                        <Badge variant="outline" className="text-xs capitalize">{tool.category}</Badge>
                        {tool.version && <Badge variant="secondary" className="text-xs">v{tool.version}</Badge>}
                      </div>
                    </div>
                    <div className="flex-shrink-0">
                      {tool.enabled ? (
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                      ) : tool.status === 'error' ? (
                        <AlertTriangle className="h-5 w-5 text-yellow-500" />
                      ) : (
                        <XCircle className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col">
                  <p className="text-sm text-muted-foreground mb-3 flex-1 line-clamp-2">{tool.description}</p>
                  <div className="flex items-center justify-between text-xs text-muted-foreground mb-3">
                    <span>{tool.usage_count} uses</span>
                    {tool.requires_approval && (
                      <Badge variant="outline" className="text-xs">Requires Approval</Badge>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {tool.installed === false ? (
                      <Button size="sm" className="w-full" onClick={() => installTool(tool.name)} disabled={isLoading}>
                        {isLoading ? <Loader2 className="mr-2 h-3 w-3 animate-spin" /> : <Download className="mr-2 h-3 w-3" />}
                        Install
                      </Button>
                    ) : (
                      <>
                        {tool.enabled ? (
                          <Button variant="outline" size="sm" className="flex-1"
                            onClick={() => disableTool(tool.name)} disabled={isLoading}>
                            {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <PowerOff className="mr-1 h-3 w-3" />}
                            Disable
                          </Button>
                        ) : (
                          <Button size="sm" className="flex-1" onClick={() => enableTool(tool.name)} disabled={isLoading}>
                            {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Power className="mr-1 h-3 w-3" />}
                            Enable
                          </Button>
                        )}
                        <Button variant="ghost" size="icon" onClick={() => removeTool(tool.name)} disabled={isLoading}>
                          <Trash2 className="h-3 w-3 text-red-500" />
                        </Button>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
