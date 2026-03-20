'use client';

import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/store/auth';
import { apiPost, apiGet } from '@/services/api';
import { Settings, KeyRound, Shield, Users, Eye, EyeOff } from 'lucide-react';

interface UserInfo {
  id: string;
  email: string;
  name: string;
  role: string;
  relationship_to_azim: string;
}

interface FamilyMember {
  id: string;
  email: string;
  name: string;
  role: string;
}

export default function SettingsPage() {
  const { token } = useAuthStore();

  // Change password state
  const [currentPassword, setCurrentPassword] = React.useState('');
  const [newPassword, setNewPassword] = React.useState('');
  const [confirmPassword, setConfirmPassword] = React.useState('');
  const [showCurrent, setShowCurrent] = React.useState(false);
  const [showNew, setShowNew] = React.useState(false);
  const [changeStatus, setChangeStatus] = React.useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [changePending, setChangePending] = React.useState(false);

  // Admin reset state
  const [familyMembers, setFamilyMembers] = React.useState<FamilyMember[]>([]);
  const [selectedUser, setSelectedUser] = React.useState('');
  const [resetPassword, setResetPassword] = React.useState('');
  const [resetStatus, setResetStatus] = React.useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [resetPending, setResetPending] = React.useState(false);

  // User info
  const [userInfo, setUserInfo] = React.useState<UserInfo | null>(null);

  React.useEffect(() => {
    const loadData = async () => {
      try {
        const me = await apiGet<UserInfo>('/../auth/me');
        setUserInfo(me);

        if (me.role === 'admin') {
          const res = await fetch('/api/auth/family', {
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });
          if (res.ok) {
            const members: FamilyMember[] = await res.json();
            setFamilyMembers(members.filter((m) => m.id !== me.id));
          }
        }
      } catch {
        // silent
      }
    };
    loadData();
  }, [token]);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setChangeStatus(null);

    if (newPassword !== confirmPassword) {
      setChangeStatus({ type: 'error', message: 'New passwords do not match.' });
      return;
    }

    setChangePending(true);
    try {
      await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      }).then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: 'Failed' }));
          throw new Error(body.detail || 'Failed to change password');
        }
      });

      setChangeStatus({ type: 'success', message: 'Password changed successfully.' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to change password';
      setChangeStatus({ type: 'error', message });
    } finally {
      setChangePending(false);
    }
  };

  const handleAdminReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetStatus(null);

    if (!selectedUser || !resetPassword) {
      setResetStatus({ type: 'error', message: 'Select a user and enter a new password.' });
      return;
    }

    setResetPending(true);
    try {
      await fetch('/api/auth/admin/reset-password', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: selectedUser,
          new_password: resetPassword,
        }),
      }).then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: 'Failed' }));
          throw new Error(body.detail || 'Failed to reset password');
        }
      });

      const user = familyMembers.find((m) => m.id === selectedUser);
      setResetStatus({ type: 'success', message: `Password reset for ${user?.name || 'user'}.` });
      setResetPassword('');
      setSelectedUser('');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to reset password';
      setResetStatus({ type: 'error', message });
    } finally {
      setResetPending(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">Account and password management.</p>
      </div>

      {/* Account Info */}
      {userInfo && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Shield className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle>Account Information</CardTitle>
                <CardDescription>{userInfo.email}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <Label className="text-muted-foreground">Name</Label>
                <p className="font-medium">{userInfo.name}</p>
              </div>
              <div>
                <Label className="text-muted-foreground">Role</Label>
                <div className="mt-1">
                  <Badge variant={userInfo.role === 'admin' ? 'default' : 'secondary'}>
                    {userInfo.role}
                  </Badge>
                </div>
              </div>
              <div>
                <Label className="text-muted-foreground">Relationship</Label>
                <p className="font-medium capitalize">{userInfo.relationship_to_azim}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Change Own Password */}
      <Card className="max-w-xl">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <KeyRound className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>Update your account password.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-password">Current Password</Label>
              <div className="relative">
                <Input
                  id="current-password"
                  type={showCurrent ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowCurrent((v) => !v)}
                >
                  {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">New Password</Label>
              <div className="relative">
                <Input
                  id="new-password"
                  type={showNew ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowNew((v) => !v)}
                >
                  {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                Min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special character.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm New Password</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>

            {changeStatus && (
              <div
                className={`rounded-md border p-3 text-sm ${
                  changeStatus.type === 'success'
                    ? 'border-green-500/50 bg-green-500/10 text-green-700 dark:text-green-400'
                    : 'border-destructive/50 bg-destructive/10 text-destructive'
                }`}
              >
                {changeStatus.message}
              </div>
            )}

            <Button type="submit" disabled={changePending}>
              {changePending ? 'Changing...' : 'Change Password'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Admin: Reset Another User's Password */}
      {userInfo?.role === 'admin' && familyMembers.length > 0 && (
        <Card className="max-w-xl">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-100 dark:bg-orange-900/30">
                <Users className="h-5 w-5 text-orange-600 dark:text-orange-400" />
              </div>
              <div>
                <CardTitle>Reset User Password</CardTitle>
                <CardDescription>Admin: reset another family member&apos;s password.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAdminReset} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="reset-user">Select User</Label>
                <select
                  id="reset-user"
                  value={selectedUser}
                  onChange={(e) => setSelectedUser(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  required
                >
                  <option value="">— Select a user —</option>
                  {familyMembers.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.email})
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="reset-new-password">New Password</Label>
                <Input
                  id="reset-new-password"
                  type="password"
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>

              {resetStatus && (
                <div
                  className={`rounded-md border p-3 text-sm ${
                    resetStatus.type === 'success'
                      ? 'border-green-500/50 bg-green-500/10 text-green-700 dark:text-green-400'
                      : 'border-destructive/50 bg-destructive/10 text-destructive'
                  }`}
                >
                  {resetStatus.message}
                </div>
              )}

              <Button type="submit" variant="outline" disabled={resetPending}>
                {resetPending ? 'Resetting...' : 'Reset Password'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
