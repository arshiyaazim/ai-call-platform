#!/usr/bin/env python3
"""Fix all LearningInsight field mismatches in learning/page.tsx."""
import sys

f = '/home/azim/ai-call-platform/frontend/fazle-dashboard/src/app/dashboard/fazle/learning/page.tsx'
with open(f, 'r') as fh:
    c = fh.read()

# 1. insight.type -> insight.insight_type
c = c.replace('insight.type)', 'insight.insight_type)')
c = c.replace('insight.type}', 'insight.insight_type}')
c = c.replace('insight.type,', 'insight.insight_type,')

# 2. insight.content -> insight.description
c = c.replace('insight.content', 'insight.description')

# 3. insight.source -> insight.action_suggested (closest available field)
c = c.replace('insight.source', 'insight.action_suggested')
c = c.replace('Source:', 'Suggested Action:')

with open(f, 'w') as fh:
    fh.write(c)

# Verify
with open(f, 'r') as fh:
    content = fh.read()

errors = []
if 'insight.type}' in content or 'insight.type)' in content:
    errors.append('insight.type still present')
if 'insight.content' in content:
    errors.append('insight.content still present')
if 'insight.source' in content:
    errors.append('insight.source still present')

if errors:
    print(f"ERRORS: {', '.join(errors)}")
    sys.exit(1)
else:
    print("All insight field fixes applied successfully")
