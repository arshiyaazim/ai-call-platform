'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { apiGet } from '@/services/api';
import {
  Activity, Cpu, MemoryStick, RefreshCw, Loader2, CheckCircle2, XCircle,
  Gauge, Server, Zap
} from 'lucide-react';

interface ServiceStatus {
  service: string;
  instance: string;
  up: boolean;
}

interface ContainerStat {
  name: string;
  cpu_percent: number;
  memory_mb: number;
}

interface ObservabilityMetrics {
  api_request_rate: number;
  api_latency_p95: number;
  container_count: number;
  healthy_services: number;
}

export default function ObservabilityPage() {
  const [metrics, setMetrics] = React.useState<ObservabilityMetrics | null>(null);
  const [services, setServices] = React.useState<ServiceStatus[]>([]);
  const [containers, setContainers] = React.useState<ContainerStat[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [autoRefresh, setAutoRefresh] = React.useState(false);

  const fetchData = React.useCallback(async () => {
    try {
      const [m, s, c] = await Promise.all([
        apiGet<ObservabilityMetrics>('/observability/metrics').catch(() => null),
        apiGet<{ services: ServiceStatus[] }>('/observability/services').catch(() => ({ services: [] })),
        apiGet<{ containers: ContainerStat[] }>('/observability/container-stats').catch(() => ({ containers: [] })),
      ]);
      setMetrics(m);
      setServices(s.services || []);
      setContainers(c.containers || []);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  React.useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const healthyCount = services.filter((s) => s.up).length;
  const totalCount = services.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Observability</h1>
          <p className="text-muted-foreground">System metrics, service health, and container performance</p>
        </div>
        <div className="flex gap-2">
          <Button variant={autoRefresh ? 'default' : 'outline'} size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}>
            <Activity className="mr-2 h-4 w-4" />
            {autoRefresh ? 'Live' : 'Auto-refresh'}
          </Button>
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
        </div>
      </div>

      {/* Top Metrics */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Request Rate</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics ? `${metrics.api_request_rate.toFixed(1)}/s` : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">Across all Fazle services</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">API Latency (p95)</CardTitle>
            <Gauge className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics ? `${(metrics.api_latency_p95 * 1000).toFixed(0)}ms` : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">95th percentile</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Containers</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics ? metrics.container_count : 0}</div>
            <p className="text-xs text-muted-foreground">Monitored Fazle containers</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Service Health</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              <span className={healthyCount === totalCount ? 'text-green-600' : 'text-yellow-600'}>
                {healthyCount}
              </span>
              <span className="text-muted-foreground text-lg">/{totalCount}</span>
            </div>
            <p className="text-xs text-muted-foreground">Healthy services</p>
          </CardContent>
        </Card>
      </div>

      {/* Service Health Grid */}
      <Card>
        <CardHeader><CardTitle>Service Health Status</CardTitle></CardHeader>
        <CardContent>
          {services.length === 0 ? (
            <p className="text-center text-muted-foreground py-4">No services reporting to Prometheus</p>
          ) : (
            <div className="grid gap-2 md:grid-cols-3 lg:grid-cols-4">
              {services.map((svc) => (
                <div key={svc.service + svc.instance}
                  className="flex items-center gap-2 p-3 rounded-lg border">
                  {svc.up
                    ? <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                    : <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />}
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{svc.service}</p>
                    <p className="text-xs text-muted-foreground truncate">{svc.instance}</p>
                  </div>
                  <Badge variant={svc.up ? 'default' : 'destructive'} className="ml-auto flex-shrink-0">
                    {svc.up ? 'UP' : 'DOWN'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Container Resources */}
      <Card>
        <CardHeader><CardTitle>Container Resources</CardTitle></CardHeader>
        <CardContent>
          {containers.length === 0 ? (
            <p className="text-center text-muted-foreground py-4">No container metrics available</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-3 font-medium">Container</th>
                    <th className="text-right py-2 px-3 font-medium">CPU %</th>
                    <th className="text-right py-2 px-3 font-medium">Memory (MB)</th>
                    <th className="text-right py-2 px-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {containers.map((c) => (
                    <tr key={c.name} className="border-b last:border-0 hover:bg-muted/50">
                      <td className="py-2 px-3 flex items-center gap-2">
                        <Cpu className="h-3 w-3 text-muted-foreground" />
                        {c.name}
                      </td>
                      <td className="text-right py-2 px-3">
                        <span className={c.cpu_percent > 80 ? 'text-red-500 font-semibold' :
                          c.cpu_percent > 50 ? 'text-yellow-500' : ''}>
                          {c.cpu_percent.toFixed(1)}%
                        </span>
                      </td>
                      <td className="text-right py-2 px-3 flex items-center justify-end gap-1">
                        <MemoryStick className="h-3 w-3 text-muted-foreground" />
                        {c.memory_mb.toFixed(0)}
                      </td>
                      <td className="text-right py-2 px-3">
                        <Badge variant="outline" className="text-green-600">running</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Grafana Link */}
      <Card>
        <CardContent className="py-4 flex items-center justify-between">
          <div>
            <p className="font-medium">Full Grafana Dashboards</p>
            <p className="text-sm text-muted-foreground">Access advanced monitoring, alerting, and historical metrics</p>
          </div>
          <Button variant="outline" asChild>
            <a href="https://iamazim.com/grafana/" target="_blank" rel="noopener noreferrer">
              Open Grafana
            </a>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
