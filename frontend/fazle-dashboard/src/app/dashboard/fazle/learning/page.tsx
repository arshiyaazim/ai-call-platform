'use client';

import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { apiGet, apiPost } from '@/services/api';
import type { LearningInsight, LearningStats } from '@/types';
import { Lightbulb, Brain, TrendingUp, Loader2, RefreshCw, Sparkles } from 'lucide-react';

export default function LearningPage() {
  const [stats, setStats] = React.useState<LearningStats | null>(null);
  const [insights, setInsights] = React.useState<LearningInsight[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [analyzeText, setAnalyzeText] = React.useState('');
  const [analyzing, setAnalyzing] = React.useState(false);
  const [improving, setImproving] = React.useState(false);
  const [improvements, setImprovements] = React.useState<string[]>([]);

  const fetchData = React.useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, insightsData] = await Promise.all([
        apiGet<LearningStats>('/self-learning/stats'),
        apiGet<{ insights: LearningInsight[] }>('/self-learning/insights?limit=50'),
      ]);
      setStats(statsData);
      setInsights(insightsData.insights || []);
    } catch {
      setStats(null);
      setInsights([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  const handleAnalyze = async () => {
    if (!analyzeText.trim()) return;
    setAnalyzing(true);
    try {
      const data = await apiPost<{ insights: LearningInsight[] }>('/self-learning/analyze', {
        conversation: analyzeText,
      });
      if (data.insights) {
        setInsights((prev) => [...data.insights, ...prev]);
      }
      setAnalyzeText('');
      fetchData();
    } catch (err) {
      console.error('Failed to analyze:', err);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleImprove = async () => {
    setImproving(true);
    try {
      const data = await apiPost<{ improvements: string[] }>('/self-learning/improve', {});
      setImprovements(data.improvements || []);
    } catch (err) {
      console.error('Failed to generate improvements:', err);
    } finally {
      setImproving(false);
    }
  };

  const insightTypeIcon = (type: string) => {
    switch (type) {
      case 'pattern': return '🔄';
      case 'preference': return '⭐';
      case 'improvement': return '📈';
      case 'routing_optimization': return '🔀';
      case 'knowledge_gap': return '❓';
      case 'behavioral': return '🧠';
      default: return '💡';
    }
  };

  const confidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 dark:text-green-400';
    if (confidence >= 0.5) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Self-Learning</h1>
          <p className="text-muted-foreground">Insights, patterns, and continuous improvement</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Total Insights</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{stats.total_insights}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Analyses Run</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{stats.analyses_run}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Improvements</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{stats.improvements_generated}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Insight Types</CardTitle></CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1">
                {Object.entries(stats.insight_types || {}).map(([type, count]) => (
                  <Badge key={type} variant="outline" className="text-xs">{type}: {count}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Analyze Conversation */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Brain className="h-5 w-5" /> Analyze Conversation</CardTitle>
          <CardDescription>Feed a conversation to extract learning insights</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="analyze-text">Conversation Text</Label>
            <Input
              id="analyze-text"
              placeholder="Paste a conversation or interaction text to analyze..."
              value={analyzeText}
              onChange={(e) => setAnalyzeText(e.target.value)}
            />
          </div>
          <Button onClick={handleAnalyze} disabled={analyzing || !analyzeText.trim()}>
            {analyzing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Lightbulb className="mr-2 h-4 w-4" />}
            Extract Insights
          </Button>
        </CardContent>
      </Card>

      {/* Generate Improvements */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><TrendingUp className="h-5 w-5" /> Improvement Suggestions</CardTitle>
          <CardDescription>Generate actionable improvements based on learned patterns</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button onClick={handleImprove} disabled={improving}>
            {improving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            Generate Improvements
          </Button>
          {improvements.length > 0 && (
            <div className="space-y-2 mt-3">
              {improvements.map((imp, i) => (
                <div key={i} className="rounded border border-green-200 bg-green-50 dark:bg-green-950 dark:border-green-800 p-3">
                  <p className="text-sm">{imp}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Insights List */}
      <Card>
        <CardHeader>
          <CardTitle>Insights ({insights.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : insights.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No insights yet. Analyze a conversation to start learning.</p>
          ) : (
            <div className="space-y-3">
              {insights.map((insight) => (
                <div
                  key={insight.id}
                  className="rounded-lg border p-4 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">{insightTypeIcon(insight.type)}</span>
                    <Badge variant="outline">{insight.type}</Badge>
                    <span className={`text-xs font-medium ${confidenceColor(insight.confidence)}`}>
                      {Math.round(insight.confidence * 100)}% confidence
                    </span>
                    <span className="text-xs text-muted-foreground ml-auto">
                      {new Date(insight.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm">{insight.content}</p>
                  {insight.source && (
                    <p className="text-xs text-muted-foreground mt-1">Source: {insight.source}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
