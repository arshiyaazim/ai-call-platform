'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { usersService, type ManagedUser } from '@/services/users';
import {
  Users, Plus, Loader2, RefreshCw, Pencil, Trash2, KeyRound,
  ChevronLeft, ChevronRight, CheckCircle2, XCircle, Copy,
} from 'lucide-react';

export default function UserManagementPage() {
  const [users, setUsers] = React.useState<ManagedUser[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [totalPages, setTotalPages] = React.useState(1);
  const [total, setTotal] = React.useState(0);

  // Create modal
  const [showCreate, setShowCreate] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [newUser, setNewUser] = React.useState({ username: '', email: '', password: '', role: 'viewer' });

  // Edit modal
  const [editUser, setEditUser] = React.useState<ManagedUser | null>(null);
  const [editData, setEditData] = React.useState({ username: '', email: '', role: '', is_active: true });
  const [saving, setSaving] = React.useState(false);

  // Feedback
  const [message, setMessage] = React.useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [tempPassword, setTempPassword] = React.useState<string | null>(null);

  const fetchUsers = React.useCallback(async () => {
    try {
      const data = await usersService.list(page);
      setUsers(data.users || []);
      setTotalPages(data.total_pages);
      setTotal(data.total);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [page]);

  React.useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleCreate = async () => {
    if (!newUser.username.trim() || !newUser.email.trim() || !newUser.password.trim()) return;
    setCreating(true);
    try {
      await usersService.create(newUser);
      setMessage({ text: 'User created successfully', type: 'success' });
      setNewUser({ username: '', email: '', password: '', role: 'viewer' });
      setShowCreate(false);
      fetchUsers();
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail || 'Failed to create user';
      setMessage({ text: detail, type: 'error' });
    } finally {
      setCreating(false);
    }
  };

  const openEdit = (user: ManagedUser) => {
    setEditUser(user);
    setEditData({ username: user.username, email: user.email, role: user.role, is_active: user.is_active });
  };

  const handleUpdate = async () => {
    if (!editUser) return;
    setSaving(true);
    try {
      await usersService.update({ user_id: editUser.id, ...editData });
      setMessage({ text: 'User updated', type: 'success' });
      setEditUser(null);
      fetchUsers();
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail || 'Update failed';
      setMessage({ text: detail, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (userId: string) => {
    if (!confirm('Are you sure you want to delete this user?')) return;
    try {
      await usersService.remove(userId);
      setMessage({ text: 'User deleted', type: 'success' });
      fetchUsers();
    } catch {
      setMessage({ text: 'Delete failed', type: 'error' });
    }
  };

  const handleResetPassword = async (userId: string) => {
    try {
      const res = await usersService.resetPassword(userId);
      setTempPassword(res.temporary_password);
      setMessage({ text: 'Password reset successful', type: 'success' });
    } catch {
      setMessage({ text: 'Password reset failed', type: 'error' });
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setMessage({ text: 'Copied to clipboard', type: 'success' });
  };

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
          <h1 className="text-3xl font-bold tracking-tight">User Management</h1>
          <p className="text-muted-foreground">{total} total user{total !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchUsers(); }}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" /> Add User
          </Button>
        </div>
      </div>

      {/* Feedback */}
      {message && (
        <div className={`rounded-lg border p-3 flex items-center gap-2 ${message.type === 'success' ? 'border-green-500/40 bg-green-500/10 text-green-700 dark:text-green-400' : 'border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-400'}`}>
          {message.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          <span className="text-sm">{message.text}</span>
          <Button variant="ghost" size="sm" className="ml-auto h-6 px-2" onClick={() => setMessage(null)}>×</Button>
        </div>
      )}

      {/* Temp Password Display */}
      {tempPassword && (
        <div className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-3 flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-yellow-600" />
          <span className="text-sm">Temporary password: <code className="bg-muted px-2 py-0.5 rounded font-mono">{tempPassword}</code></span>
          <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => copyToClipboard(tempPassword)}>
            <Copy className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="ml-auto h-6 px-2" onClick={() => setTempPassword(null)}>×</Button>
        </div>
      )}

      {/* Create User Panel */}
      {showCreate && (
        <Card>
          <CardHeader><CardTitle>Create New User</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Username</Label>
                <Input value={newUser.username} onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} placeholder="Username" />
              </div>
              <div>
                <Label>Email</Label>
                <Input type="email" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} placeholder="user@example.com" />
              </div>
              <div>
                <Label>Password</Label>
                <Input type="password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} placeholder="Min 8 characters" />
              </div>
              <div>
                <Label>Role</Label>
                <select
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  className="w-full border rounded px-3 py-2 text-sm bg-background"
                >
                  <option value="viewer">Viewer</option>
                  <option value="editor">Editor</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={creating || !newUser.username.trim() || !newUser.email.trim() || !newUser.password.trim()}>
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create User
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Edit User Panel */}
      {editUser && (
        <Card>
          <CardHeader><CardTitle>Edit User: {editUser.email}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Username</Label>
                <Input value={editData.username} onChange={(e) => setEditData({ ...editData, username: e.target.value })} />
              </div>
              <div>
                <Label>Email</Label>
                <Input type="email" value={editData.email} onChange={(e) => setEditData({ ...editData, email: e.target.value })} />
              </div>
              <div>
                <Label>Role</Label>
                <select
                  value={editData.role}
                  onChange={(e) => setEditData({ ...editData, role: e.target.value })}
                  className="w-full border rounded px-3 py-2 text-sm bg-background"
                >
                  <option value="viewer">Viewer</option>
                  <option value="editor">Editor</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="flex items-end gap-3">
                <Label>Active</Label>
                <button
                  className={`w-12 h-6 rounded-full transition-colors ${editData.is_active ? 'bg-primary' : 'bg-muted'}`}
                  onClick={() => setEditData({ ...editData, is_active: !editData.is_active })}
                >
                  <div className={`w-5 h-5 rounded-full bg-white shadow transition-transform ${editData.is_active ? 'translate-x-6' : 'translate-x-0.5'}`} />
                </button>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEditUser(null)}>Cancel</Button>
              <Button onClick={handleUpdate} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Changes
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" /> Users
          </CardTitle>
        </CardHeader>
        <CardContent>
          {users.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">No users found</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-medium w-10">#</th>
                    <th className="pb-2 font-medium">Username</th>
                    <th className="pb-2 font-medium">Email</th>
                    <th className="pb-2 font-medium">Role</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {users.map((user, idx) => (
                    <tr key={user.id} className="hover:bg-muted/50">
                      <td className="py-2 text-muted-foreground">{(page - 1) * 20 + idx + 1}</td>
                      <td className="py-2 font-medium">{user.username || '—'}</td>
                      <td className="py-2 font-mono text-xs">{user.email}</td>
                      <td className="py-2">
                        <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>{user.role}</Badge>
                      </td>
                      <td className="py-2">
                        <Badge variant={user.is_active ? 'default' : 'destructive'}>
                          {user.is_active ? 'Active' : 'Disabled'}
                        </Badge>
                      </td>
                      <td className="py-2 text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" title="Reset Password" onClick={() => handleResetPassword(user.id)}>
                            <KeyRound className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Edit" onClick={() => openEdit(user)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Delete" onClick={() => handleDelete(user.id)}>
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t mt-4">
              <p className="text-sm text-muted-foreground">
                Page {page} of {totalPages} ({total} users)
              </p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => { setPage(page - 1); setLoading(true); }}>
                  <ChevronLeft className="h-4 w-4 mr-1" /> Previous
                </Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => { setPage(page + 1); setLoading(true); }}>
                  Next <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
