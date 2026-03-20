#!/usr/bin/env python3
"""Fix interval_seconds -> interval_minutes in autonomous-tasks page."""
path = '/home/azim/ai-call-platform/frontend/fazle-dashboard/src/app/dashboard/fazle/autonomous-tasks/page.tsx'

with open(path) as f:
    content = f.read()

# Also fix the label
content = content.replace('Interval (seconds)', 'Interval (minutes)')
content = content.replace("const [interval, setInterval_] = React.useState('3600')", "const [interval, setInterval_] = React.useState('60')")

# Fix the formatInterval function
old_fn = """  const formatInterval = (minutes: number | null) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
    return `${Math.round(seconds / 86400)}d`;
  };"""

new_fn = """  const formatInterval = (minutes: number | null) => {
    if (!minutes) return 'N/A';
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 1440) return `${Math.round(minutes / 60)}h`;
    return `${Math.round(minutes / 1440)}d`;
  };"""

content = content.replace(old_fn, new_fn)

with open(path, 'w') as f:
    f.write(content)
print('autonomous-tasks page fixed')
