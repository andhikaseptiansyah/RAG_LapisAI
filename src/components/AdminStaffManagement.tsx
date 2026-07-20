import React, { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { AdminHeader } from './AdminHeader';
import { AdminSidebar } from './AdminSidebar';
import { ApiError, getFriendlyApiErrorMessage } from '../services/api';
import {
  createStaffAccount,
  deleteManagedUser,
  getManagedUsers,
  updateManagedUserPassword,
  type ManagedUser,
} from '../services/staffService';
import { useAuth } from '../hooks/useAuth';

const getStaffErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError && error.data && typeof error.data === 'object') {
    const detail = (error.data as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
  }
  return getFriendlyApiErrorMessage(error);
};

const formatAccountDate = (value: string): string => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('en-US', {
    timeZone: 'Asia/Jakarta',
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  });
};

const roleClassName = (role: string): string => {
  if (role === 'admin' || role === 'superadmin' || role === 'owner') {
    return 'border-violet-400/20 bg-violet-500/10 text-violet-300';
  }
  return 'border-cyan-400/20 bg-cyan-500/10 text-cyan-300';
};

interface ModalShellProps {
  title: string;
  description: string;
  icon: string;
  onClose: () => void;
  children: React.ReactNode;
}

const ModalShell: React.FC<ModalShellProps> = ({
  title,
  description,
  icon,
  onClose,
  children,
}) => (
  <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 px-4 backdrop-blur-sm">
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="staff-modal-title"
      className="w-full max-w-md overflow-hidden rounded-3xl border border-white/10 bg-[#0b1020] shadow-[0_30px_100px_rgba(0,0,0,0.65)]"
    >
      <div className="flex items-start gap-4 border-b border-white/5 px-6 py-5">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-500/10 text-cyan-300">
          <span className="material-symbols-outlined">{icon}</span>
        </div>
        <div className="min-w-0 flex-1">
          <h2 id="staff-modal-title" className="text-lg font-bold text-white">
            {title}
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">{description}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-xl p-2 text-slate-500 transition hover:bg-white/5 hover:text-white"
          aria-label="Close modal"
        >
          <span className="material-symbols-outlined text-[20px]">close</span>
        </button>
      </div>
      {children}
    </div>
  </div>
);

export const AdminStaffManagement: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createUsername, setCreateUsername] = useState('');
  const [createPassword, setCreatePassword] = useState('');
  const [showCreatePassword, setShowCreatePassword] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const [passwordTarget, setPasswordTarget] = useState<ManagedUser | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<ManagedUser | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadUsers = useCallback(async (showRefreshState = false) => {
    if (showRefreshState) setIsRefreshing(true);
    else setIsLoading(true);

    setErrorMessage('');
    try {
      const response = await getManagedUsers();
      setUsers(response.users ?? []);
    } catch (error) {
      setErrorMessage(getStaffErrorMessage(error));
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const summary = useMemo(() => {
    const staff = users.filter((item) => item.role === 'staff' || item.role === 'user').length;
    const admins = users.filter((item) => item.role === 'admin' || item.role === 'superadmin' || item.role === 'owner').length;
    const totalChats = users.reduce((total, item) => total + Number(item.totalChats || 0), 0);
    return { total: users.length, staff, admins, totalChats };
  }, [users]);

  const resetCreateForm = (): void => {
    setCreateName('');
    setCreateUsername('');
    setCreatePassword('');
    setShowCreatePassword(false);
  };

  const handleCreateStaff = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');
    setIsCreating(true);

    try {
      await createStaffAccount({
        name: createName.trim(),
        username: createUsername.trim().toLowerCase(),
        password: createPassword,
      });
      setSuccessMessage(`Staff account "${createUsername.trim().toLowerCase()}" was created successfully.`);
      setIsCreateOpen(false);
      resetCreateForm();
      await loadUsers(true);
    } catch (error) {
      setErrorMessage(getStaffErrorMessage(error));
    } finally {
      setIsCreating(false);
    }
  };

  const handleUpdatePassword = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!passwordTarget) return;

    setErrorMessage('');
    setSuccessMessage('');
    setIsUpdatingPassword(true);

    try {
      await updateManagedUserPassword(passwordTarget.id, newPassword);
      setSuccessMessage(`Password for "${passwordTarget.username}" was updated successfully.`);
      setPasswordTarget(null);
      setNewPassword('');
      setShowNewPassword(false);
      await loadUsers(true);
    } catch (error) {
      setErrorMessage(getStaffErrorMessage(error));
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  const handleDeleteUser = async (): Promise<void> => {
    if (!deleteTarget) return;

    setErrorMessage('');
    setSuccessMessage('');
    setIsDeleting(true);

    try {
      await deleteManagedUser(deleteTarget.id);
      setSuccessMessage(`Account "${deleteTarget.username}" was deleted successfully.`);
      setDeleteTarget(null);
      await loadUsers(true);
    } catch (error) {
      setErrorMessage(getStaffErrorMessage(error));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex h-screen h-[100dvh] min-h-0 w-full overflow-hidden bg-[#030611] text-slate-100">
      <AdminSidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <AdminHeader onToggleSidebar={() => setIsSidebarOpen(true)} />

        <main className="custom-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-6 pb-[calc(1.5rem+env(safe-area-inset-bottom))] md:px-8 md:py-8 md:pb-[calc(2rem+env(safe-area-inset-bottom))]">
          <div className="mx-auto max-w-[1500px]">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.24em] text-cyan-400">
                  Admin Tools
                </p>
                <h1 className="mt-2 text-2xl font-black tracking-tight text-white md:text-3xl">
                  Staff Management
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                  Create staff accounts, reset passwords, remove access, and review each user&apos;s total chat activity.
                </p>
              </div>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => void loadUsers(true)}
                  disabled={isRefreshing}
                  className="inline-flex h-11 items-center gap-2 rounded-xl border border-white/10 bg-[#10182b] px-4 text-sm font-semibold text-slate-300 transition hover:border-cyan-400/30 hover:text-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <span className={`material-symbols-outlined text-[20px] ${isRefreshing ? 'animate-spin' : ''}`}>
                    refresh
                  </span>
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setErrorMessage('');
                    setSuccessMessage('');
                    setIsCreateOpen(true);
                  }}
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-cyan-400 px-4 text-sm font-black text-slate-950 shadow-[0_0_25px_rgba(34,211,238,0.2)] transition hover:bg-cyan-300"
                >
                  <span className="material-symbols-outlined text-[20px]">person_add</span>
                  Add Staff
                </button>
              </div>
            </div>

            {errorMessage && (
              <div className="mt-6 flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                <span className="material-symbols-outlined text-[20px]">error</span>
                <span>{errorMessage}</span>
              </div>
            )}

            {successMessage && (
              <div className="mt-6 flex items-start gap-3 rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                <span className="material-symbols-outlined text-[20px]">check_circle</span>
                <span>{successMessage}</span>
              </div>
            )}

            <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {[
                { label: 'Total Accounts', value: summary.total, icon: 'group', tone: 'text-cyan-300 bg-cyan-500/10 border-cyan-400/20' },
                { label: 'Staff Accounts', value: summary.staff, icon: 'badge', tone: 'text-emerald-300 bg-emerald-500/10 border-emerald-400/20' },
                { label: 'Admin Accounts', value: summary.admins, icon: 'admin_panel_settings', tone: 'text-violet-300 bg-violet-500/10 border-violet-400/20' },
                { label: 'Total Chats', value: summary.totalChats, icon: 'forum', tone: 'text-amber-300 bg-amber-500/10 border-amber-400/20' },
              ].map((item) => (
                <article key={item.label} className="rounded-2xl border border-white/10 bg-[#0d1425] p-5 shadow-xl">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-xl border ${item.tone}`}>
                    <span className="material-symbols-outlined">{item.icon}</span>
                  </div>
                  <p className="mt-5 text-sm font-semibold text-slate-400">{item.label}</p>
                  <p className="mt-1 text-3xl font-black text-white">{item.value.toLocaleString('en-US')}</p>
                </article>
              ))}
            </section>

            <section className="mt-7 overflow-hidden rounded-2xl border border-white/10 bg-[#0d1425] shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/5 px-5 py-4 md:px-6">
                <div>
                  <h2 className="font-bold text-white">User and Staff List</h2>
                  <p className="mt-1 text-xs text-slate-500">Chat totals are calculated from saved query logs.</p>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-slate-400">
                  {users.length} accounts
                </span>
              </div>

              {isLoading ? (
                <div className="flex min-h-[280px] items-center justify-center gap-3 text-slate-400">
                  <span className="material-symbols-outlined animate-spin text-cyan-300">progress_activity</span>
                  Loading accounts...
                </div>
              ) : users.length === 0 ? (
                <div className="flex min-h-[280px] flex-col items-center justify-center px-6 text-center">
                  <span className="material-symbols-outlined text-5xl text-slate-700">group_off</span>
                  <p className="mt-3 font-semibold text-slate-300">No accounts found</p>
                  <p className="mt-1 text-sm text-slate-500">Create the first staff account using Add Staff.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[880px] text-left">
                    <thead className="bg-[#090f1e] font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">
                      <tr>
                        <th className="px-6 py-4 font-medium">Account</th>
                        <th className="px-6 py-4 font-medium">Username</th>
                        <th className="px-6 py-4 font-medium">Role</th>
                        <th className="px-6 py-4 font-medium">Total Chat</th>
                        <th className="px-6 py-4 font-medium">Created</th>
                        <th className="px-6 py-4 text-right font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {users.map((managedUser) => {
                        const isAdminAccount = ['admin', 'superadmin', 'owner'].includes(managedUser.role);
                        const isCurrentAccount = managedUser.id === currentUser?.id;
                        const canDelete = !isAdminAccount && !isCurrentAccount;

                        return (
                          <tr key={managedUser.id} className="transition hover:bg-white/[0.025]">
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-3">
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-gradient-to-br from-cyan-500/20 to-violet-500/20 font-black text-cyan-200">
                                  {(managedUser.name || managedUser.username).slice(0, 1).toUpperCase()}
                                </div>
                                <div>
                                  <p className="font-semibold text-white">
                                    {managedUser.name}
                                    {isCurrentAccount && (
                                      <span className="ml-2 text-[10px] font-mono uppercase tracking-wider text-cyan-400">You</span>
                                    )}
                                  </p>
                                  <p className="mt-0.5 font-mono text-[11px] text-slate-600">{managedUser.id}</p>
                                </div>
                              </div>
                            </td>
                            <td className="px-6 py-4 font-mono text-sm text-slate-300">@{managedUser.username}</td>
                            <td className="px-6 py-4">
                              <span className={`inline-flex rounded-full border px-3 py-1 font-mono text-[11px] font-bold uppercase tracking-wider ${roleClassName(managedUser.role)}`}>
                                {managedUser.role}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <span className="text-lg font-black text-white">{managedUser.totalChats.toLocaleString('en-US')}</span>
                              <span className="ml-2 text-xs text-slate-500">chats</span>
                            </td>
                            <td className="px-6 py-4 text-sm text-slate-400">{formatAccountDate(managedUser.createdAt)}</td>
                            <td className="px-6 py-4">
                              <div className="flex justify-end gap-2">
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (isAdminAccount) return;
                                    setErrorMessage('');
                                    setSuccessMessage('');
                                    setPasswordTarget(managedUser);
                                    setNewPassword('');
                                  }}
                                  disabled={isAdminAccount}
                                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-amber-400/20 bg-amber-500/10 px-3 text-xs font-bold text-amber-300 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-30"
                                  title={isAdminAccount ? 'Administrator passwords are managed separately' : 'Update password'}
                                >
                                  <span className="material-symbols-outlined text-[18px]">key</span>
                                  Password
                                </button>
                                <button
                                  type="button"
                                  onClick={() => canDelete && setDeleteTarget(managedUser)}
                                  disabled={!canDelete}
                                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-rose-400/20 bg-rose-500/10 px-3 text-xs font-bold text-rose-300 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-30"
                                  title={canDelete ? 'Delete account' : 'Administrator accounts cannot be deleted'}
                                >
                                  <span className="material-symbols-outlined text-[18px]">delete</span>
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        </main>
      </div>

      {isCreateOpen && (
        <ModalShell
          title="Create staff account"
          description="The new staff member can sign in immediately after the account is created."
          icon="person_add"
          onClose={() => {
            if (isCreating) return;
            setIsCreateOpen(false);
            resetCreateForm();
          }}
        >
          <form onSubmit={handleCreateStaff} className="space-y-4 px-6 py-5">
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Full name</span>
              <input
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                required
                minLength={2}
                maxLength={80}
                placeholder="Example: Budi Santoso"
                className="mt-2 w-full rounded-xl border border-white/10 bg-[#050918] px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-700 focus:border-cyan-400/50"
              />
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Username</span>
              <input
                value={createUsername}
                onChange={(event) => setCreateUsername(event.target.value.toLowerCase())}
                required
                minLength={3}
                maxLength={32}
                pattern="[a-z0-9._-]+"
                placeholder="budi.staff"
                className="mt-2 w-full rounded-xl border border-white/10 bg-[#050918] px-4 py-3 font-mono text-sm text-white outline-none transition placeholder:text-slate-700 focus:border-cyan-400/50"
              />
              <span className="mt-1 block text-xs text-slate-600">Lowercase letters, numbers, dots, underscores, or hyphens.</span>
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Temporary password</span>
              <div className="relative mt-2">
                <input
                  type={showCreatePassword ? 'text' : 'password'}
                  value={createPassword}
                  onChange={(event) => setCreatePassword(event.target.value)}
                  required
                  minLength={6}
                  maxLength={128}
                  placeholder="Minimum 6 characters"
                  className="w-full rounded-xl border border-white/10 bg-[#050918] px-4 py-3 pr-12 text-sm text-white outline-none transition placeholder:text-slate-700 focus:border-cyan-400/50"
                />
                <button
                  type="button"
                  onClick={() => setShowCreatePassword((value) => !value)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                  aria-label={showCreatePassword ? 'Hide password' : 'Show password'}
                >
                  <span className="material-symbols-outlined text-[20px]">{showCreatePassword ? 'visibility_off' : 'visibility'}</span>
                </button>
              </div>
            </label>
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setIsCreateOpen(false);
                  resetCreateForm();
                }}
                disabled={isCreating}
                className="rounded-xl border border-white/10 px-4 py-2.5 text-sm font-bold text-slate-300 transition hover:bg-white/5 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isCreating}
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-400 px-4 py-2.5 text-sm font-black text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isCreating && <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>}
                {isCreating ? 'Creating...' : 'Create Account'}
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {passwordTarget && (
        <ModalShell
          title="Update password"
          description={`Set a new password for ${passwordTarget.name} (@${passwordTarget.username}).`}
          icon="key"
          onClose={() => {
            if (isUpdatingPassword) return;
            setPasswordTarget(null);
            setNewPassword('');
          }}
        >
          <form onSubmit={handleUpdatePassword} className="space-y-4 px-6 py-5">
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">New password</span>
              <div className="relative mt-2">
                <input
                  autoFocus
                  type={showNewPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  required
                  minLength={6}
                  maxLength={128}
                  placeholder="Minimum 6 characters"
                  className="w-full rounded-xl border border-white/10 bg-[#050918] px-4 py-3 pr-12 text-sm text-white outline-none transition placeholder:text-slate-700 focus:border-amber-400/50"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword((value) => !value)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                  aria-label={showNewPassword ? 'Hide password' : 'Show password'}
                >
                  <span className="material-symbols-outlined text-[20px]">{showNewPassword ? 'visibility_off' : 'visibility'}</span>
                </button>
              </div>
            </label>
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setPasswordTarget(null);
                  setNewPassword('');
                }}
                disabled={isUpdatingPassword}
                className="rounded-xl border border-white/10 px-4 py-2.5 text-sm font-bold text-slate-300 transition hover:bg-white/5 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isUpdatingPassword}
                className="inline-flex items-center gap-2 rounded-xl bg-amber-400 px-4 py-2.5 text-sm font-black text-slate-950 transition hover:bg-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isUpdatingPassword && <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>}
                {isUpdatingPassword ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {deleteTarget && (
        <ModalShell
          title="Delete staff account?"
          description={`Are you sure you want to delete ${deleteTarget.name} (@${deleteTarget.username})? The account will no longer be able to sign in.`}
          icon="person_remove"
          onClose={() => !isDeleting && setDeleteTarget(null)}
        >
          <div className="px-6 py-5">
            <div className="rounded-2xl border border-rose-400/15 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-200">
              Existing query logs will remain available for reporting, but this user account will be permanently removed.
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={isDeleting}
                className="rounded-xl border border-white/10 px-4 py-2.5 text-sm font-bold text-slate-300 transition hover:bg-white/5 disabled:opacity-50"
              >
                No, Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleDeleteUser()}
                disabled={isDeleting}
                className="inline-flex items-center gap-2 rounded-xl bg-rose-500 px-4 py-2.5 text-sm font-black text-white transition hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isDeleting && <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>}
                {isDeleting ? 'Deleting...' : 'Yes, Delete'}
              </button>
            </div>
          </div>
        </ModalShell>
      )}
    </div>
  );
};
