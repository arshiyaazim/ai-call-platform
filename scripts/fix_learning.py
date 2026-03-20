#!/usr/bin/env python3
"""Fix learning/page.tsx type mismatches on VPS."""
import sys

f = '/home/azim/ai-call-platform/frontend/fazle-dashboard/src/app/dashboard/fazle/learning/page.tsx'
with open(f, 'r') as fh:
    c = fh.read()

# 1. Replace improvements_generated card title and field
c = c.replace('font-medium">Improvements</CardTitle>', 'font-medium">Applied Insights</CardTitle>')
c = c.replace('stats.improvements_generated', 'stats.applied_insights')

# 2. Replace insight_types card with patterns_detected
old_card = '''<CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Insight Types</CardTitle></CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1">
                {Object.entries(stats.insight_types || {}).map(([type, count]) => (
                  <Badge key={type} variant="outline" className="text-xs">{type}: {count}</Badge>
                ))}
              </div>
            </CardContent>'''
new_card = '''<CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Patterns Detected</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{stats.patterns_detected}</div></CardContent>'''
c = c.replace(old_card, new_card)

with open(f, 'w') as fh:
    fh.write(c)

# Verify
with open(f, 'r') as fh:
    content = fh.read()

errors = []
if 'improvements_generated' in content:
    errors.append('improvements_generated still present')
if 'insight_types' in content:
    errors.append('insight_types still present')
if 'applied_insights' not in content:
    errors.append('applied_insights not added')
if 'patterns_detected' not in content:
    errors.append('patterns_detected not added')

if errors:
    print(f"ERRORS: {', '.join(errors)}")
    sys.exit(1)
else:
    print("All fixes applied successfully")
