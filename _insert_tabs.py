#!/usr/bin/env python3
"""Insert SalaryTab, AttendanceTab, AdminTab into page.tsx"""

f = r'e:\Programs\vps-deploy\frontend\fazle-dashboard\src\app\dashboard\fazle\wbom\page.tsx'
content = open(f, 'r', encoding='utf-8').read()
lines = content.split('\n')

# Find the Date formatting helpers line
didx = next(i for i, l in enumerate(lines) if 'Date formatting' in l)
print(f'Date formatting at line {didx+1}')

NEW_CODE = r'''
// ══════════════════════════════════════════════════════════════
// SALARY TAB
// ══════════════════════════════════════════════════════════════
function SalaryTab({ showMsg }: { showMsg: (t: string, tp?: 'success' | 'error') => void }) {
  const now = new Date();
  const [month, setMonth] = React.useState(now.getMonth() + 1);
  const [year, setYear] = React.useState(now.getFullYear());
  const [records, setRecords] = React.useState<WbomSalaryRecord[]>([]);
  const [totalPayable, setTotalPayable] = React.useState(0);
  const [loading, setLoading] = React.useState(false);
  const [drafts, setDrafts] = React.useState<{ employee_name: string; net_salary: number; draft_message: string }[]>([]);

  const fetchSummary = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await wbomService.getSalarySummary(month, year);
      setRecords(res.records || []);
      setTotalPayable(res.total_payable || 0);
    } catch { showMsg('Failed to load salary summary', 'error'); }
    setLoading(false);
  }, [month, year, showMsg]);

  React.useEffect(() => { fetchSummary(); }, [fetchSummary]);

  const markPaid = async (id: number) => {
    try {
      await wbomService.markSalaryPaid(id);
      showMsg('Marked as paid');
      fetchSummary();
    } catch { showMsg('Failed to mark paid', 'error'); }
  };

  const loadDrafts = async () => {
    try {
      const res = await wbomService.getSalaryDrafts(month, year);
      setDrafts(res);
      showMsg(`${res.length} drafts generated`);
    } catch { showMsg('Failed to load drafts', 'error'); }
  };

  return (
    <div className="space-y-4 mt-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Label>Month</Label>
          <Input type="number" min={1} max={12} value={month} onChange={e => setMonth(+e.target.value)} className="w-20" />
        </div>
        <div className="flex items-center gap-2">
          <Label>Year</Label>
          <Input type="number" min={2020} value={year} onChange={e => setYear(+e.target.value)} className="w-24" />
        </div>
        <Button onClick={fetchSummary} disabled={loading} size="sm">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />} Load
        </Button>
        <Button onClick={loadDrafts} variant="outline" size="sm">
          <DollarSign className="h-4 w-4 mr-1" /> Generate Drafts
        </Button>
      </div>

      {totalPayable > 0 && (
        <Card><CardContent className="py-3 flex items-center gap-4">
          <Badge variant="secondary" className="text-base px-4 py-1">Total Payable: ৳{totalPayable.toLocaleString()}</Badge>
          <span className="text-muted-foreground text-sm">{records.length} records</span>
        </CardContent></Card>
      )}

      <div className="rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50"><tr>
            <th className="px-3 py-2 text-left">Employee</th>
            <th className="px-3 py-2 text-right">Basic</th>
            <th className="px-3 py-2 text-right">Programs</th>
            <th className="px-3 py-2 text-right">Allowance</th>
            <th className="px-3 py-2 text-right">Advances</th>
            <th className="px-3 py-2 text-right">Net Salary</th>
            <th className="px-3 py-2 text-center">Status</th>
            <th className="px-3 py-2 text-center">Action</th>
          </tr></thead>
          <tbody>
            {records.map(r => (
              <tr key={r.salary_id} className="border-t hover:bg-muted/30">
                <td className="px-3 py-2">{r.employee_name || `#${r.employee_id}`}<br/><span className="text-xs text-muted-foreground">{r.designation}</span></td>
                <td className="px-3 py-2 text-right">৳{(r.basic_salary || 0).toLocaleString()}</td>
                <td className="px-3 py-2 text-right">{r.total_programs}</td>
                <td className="px-3 py-2 text-right">৳{(r.program_allowance || 0).toLocaleString()}</td>
                <td className="px-3 py-2 text-right text-red-600">৳{(r.total_advances || 0).toLocaleString()}</td>
                <td className="px-3 py-2 text-right font-semibold">৳{(r.net_salary || 0).toLocaleString()}</td>
                <td className="px-3 py-2 text-center"><Badge variant={r.status === 'Paid' ? 'default' : 'secondary'}>{r.status}</Badge></td>
                <td className="px-3 py-2 text-center">
                  {r.status !== 'Paid' && <Button size="sm" variant="outline" onClick={() => markPaid(r.salary_id)}>Mark Paid</Button>}
                </td>
              </tr>
            ))}
            {records.length === 0 && <tr><td colSpan={8} className="px-3 py-8 text-center text-muted-foreground">No salary records for this period</td></tr>}
          </tbody>
        </table>
      </div>

      {drafts.length > 0 && (
        <Card><CardHeader><CardTitle className="text-base">Payment Drafts</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {drafts.map((d, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-md bg-muted/40">
                <span className="font-medium">{d.employee_name}</span>
                <code className="text-xs bg-background px-2 py-1 rounded">{d.draft_message}</code>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// ATTENDANCE TAB
// ══════════════════════════════════════════════════════════════
function AttendanceTab({ showMsg }: { showMsg: (t: string, tp?: 'success' | 'error') => void }) {
  const today = new Date().toISOString().split('T')[0];
  const [date, setDate] = React.useState(today);
  const [records, setRecords] = React.useState<WbomAttendance[]>([]);
  const [loading, setLoading] = React.useState(false);

  const fetchReport = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await wbomService.getAttendanceReport({ attendance_date: date });
      setRecords(Array.isArray(res) ? res : []);
    } catch { showMsg('Failed to load attendance', 'error'); }
    setLoading(false);
  }, [date, showMsg]);

  React.useEffect(() => { fetchReport(); }, [fetchReport]);

  const bulkMark = async (status: string) => {
    try {
      const res = await wbomService.bulkAttendance(status, date, 'admin');
      showMsg(`Marked ${res.marked} employees as ${status}`);
      fetchReport();
    } catch { showMsg('Bulk mark failed', 'error'); }
  };

  return (
    <div className="space-y-4 mt-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Label>Date</Label>
          <Input type="date" value={date} onChange={e => setDate(e.target.value)} className="w-44" />
        </div>
        <Button onClick={fetchReport} disabled={loading} size="sm">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />} Load
        </Button>
        <Button onClick={() => bulkMark('Present')} variant="outline" size="sm">
          <CheckCircle2 className="h-4 w-4 mr-1" /> Bulk Present
        </Button>
        <Button onClick={() => bulkMark('Absent')} variant="outline" size="sm">
          <XCircle className="h-4 w-4 mr-1" /> Bulk Absent
        </Button>
      </div>

      <div className="flex gap-3">
        <Badge variant="secondary">{records.length} records</Badge>
        <Badge variant="default">{records.filter(r => r.status === 'Present').length} Present</Badge>
        <Badge variant="destructive">{records.filter(r => r.status === 'Absent').length} Absent</Badge>
      </div>

      <div className="rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50"><tr>
            <th className="px-3 py-2 text-left">Employee</th>
            <th className="px-3 py-2 text-left">Mobile</th>
            <th className="px-3 py-2 text-center">Status</th>
            <th className="px-3 py-2 text-left">Location</th>
            <th className="px-3 py-2 text-left">Remarks</th>
          </tr></thead>
          <tbody>
            {records.map(r => (
              <tr key={r.attendance_id} className="border-t hover:bg-muted/30">
                <td className="px-3 py-2">{r.employee_name || `#${r.employee_id}`}<br/><span className="text-xs text-muted-foreground">{r.designation}</span></td>
                <td className="px-3 py-2 text-muted-foreground">{r.employee_mobile}</td>
                <td className="px-3 py-2 text-center">
                  <Badge variant={r.status === 'Present' ? 'default' : r.status === 'Absent' ? 'destructive' : 'secondary'}>{r.status}</Badge>
                </td>
                <td className="px-3 py-2">{r.location || '\u2014'}</td>
                <td className="px-3 py-2">{r.remarks || '\u2014'}</td>
              </tr>
            ))}
            {records.length === 0 && <tr><td colSpan={5} className="px-3 py-8 text-center text-muted-foreground">No attendance records for this date</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// ADMIN TAB
// ══════════════════════════════════════════════════════════════
function AdminTab({ showMsg }: { showMsg: (t: string, tp?: 'success' | 'error') => void }) {
  const [cmdInput, setCmdInput] = React.useState('');
  const [cmdResult, setCmdResult] = React.useState<AdminCommandResult | null>(null);
  const [cmdLoading, setCmdLoading] = React.useState(false);
  const [requests, setRequests] = React.useState<WbomEmployeeRequest[]>([]);
  const [summaryDate, setSummaryDate] = React.useState(new Date().toISOString().split('T')[0]);
  const [dailySummary, setDailySummary] = React.useState<{ date: string; total: number; by_type: Record<string, number> } | null>(null);

  const sendCommand = async () => {
    if (!cmdInput.trim()) return;
    setCmdLoading(true);
    try {
      const res = await wbomService.sendAdminCommand('admin', cmdInput);
      setCmdResult(res);
      showMsg(res.message || 'Command executed');
    } catch { showMsg('Command failed', 'error'); }
    setCmdLoading(false);
  };

  const loadRequests = async () => {
    try {
      const res = await wbomService.getPendingRequests();
      setRequests(res);
    } catch { showMsg('Failed to load requests', 'error'); }
  };

  const respondReq = async (id: number) => {
    const text = prompt('Enter response:');
    if (!text) return;
    try {
      await wbomService.respondToRequest(id, text);
      showMsg('Response sent');
      loadRequests();
    } catch { showMsg('Failed to respond', 'error'); }
  };

  const loadDailySummary = async () => {
    try {
      const res = await wbomService.getDailyPaymentSummary(summaryDate);
      setDailySummary(res);
    } catch { showMsg('Failed to load daily summary', 'error'); }
  };

  React.useEffect(() => { loadRequests(); }, []);

  return (
    <div className="space-y-6 mt-4">
      <Card>
        <CardHeader><CardTitle className="text-base">Admin Command</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="e.g. khoj Rahim, beton 01XXXXXXXXX 5000, hajira today..."
              value={cmdInput}
              onChange={e => setCmdInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendCommand()}
              className="flex-1"
            />
            <Button onClick={sendCommand} disabled={cmdLoading}>
              {cmdLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Execute'}
            </Button>
          </div>
          {cmdResult && (
            <div className="rounded-md bg-muted p-3 text-sm">
              <div className="font-medium mb-1">{cmdResult.command_type}: {cmdResult.message}</div>
              <pre className="text-xs overflow-x-auto whitespace-pre-wrap">{JSON.stringify(cmdResult.result, null, 2)}</pre>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Daily Payment Summary</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 mb-3">
            <Input type="date" value={summaryDate} onChange={e => setSummaryDate(e.target.value)} className="w-44" />
            <Button onClick={loadDailySummary} size="sm" variant="outline">Load</Button>
          </div>
          {dailySummary && (
            <div className="space-y-2">
              <Badge variant="secondary" className="text-base px-4 py-1">Total: ৳{dailySummary.total.toLocaleString()}</Badge>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(dailySummary.by_type).map(([k, v]) => (
                  <Badge key={k} variant="outline">{k}: ৳{v.toLocaleString()}</Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Employee Requests</CardTitle>
          <Button onClick={loadRequests} size="sm" variant="outline"><RefreshCw className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent>
          {requests.length === 0 && <p className="text-muted-foreground text-sm">No pending requests</p>}
          <div className="space-y-2">
            {requests.map(r => (
              <div key={r.request_id} className="flex items-start justify-between p-3 rounded-md border">
                <div>
                  <div className="font-medium text-sm">{r.employee_name || `#${r.employee_id}`} {'\u2014'} <Badge variant="outline">{r.request_type}</Badge></div>
                  <div className="text-xs text-muted-foreground mt-1">{r.message_body}</div>
                  <div className="text-xs text-muted-foreground">{fmtDate(r.created_at)} {'\u00B7'} {r.sender_number}</div>
                </div>
                {r.status === 'Pending' && (
                  <Button size="sm" variant="outline" onClick={() => respondReq(r.request_id)}>Respond</Button>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
'''

lines.insert(didx, NEW_CODE)
open(f, 'w', encoding='utf-8').write('\n'.join(lines))
print(f'Done - 3 tab components inserted before line {didx+1}')
