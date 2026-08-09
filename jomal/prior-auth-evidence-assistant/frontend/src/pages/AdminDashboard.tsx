/**
 * AdminDashboard page — T070, T071, T072
 * Tabs: All Cases | Nurse Workload | User Management | Audit Log
 */
import React, { useState, useCallback, useEffect } from 'react';
import AppLayout from '../components/AppLayout';
import api from '../services/api';

// ============================================================================
// Types
// ============================================================================

interface CaseRow {
  case_id: string;
  policy_name: string;
  member_id: string;
  provider_id: string;
  service_type: string | null;
  cpt_code: string | null;
  icd_code: string | null;
  status: string;
  sla_start_at: string | null;
  decided_at: string | null;
  created_at: string;
  lock_holder: string | null;
  lock_expires_at: string | null;
}

interface NurseWorkload {
  nurse_id: string;
  username: string;
  is_active: boolean;
  active_locks: number;
  decided_cases: number;
}

interface UserRow {
  id: string;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface AuditEntry {
  id: string;
  trace_id: string;
  case_id: string | null;
  timestamp: string;
  actor_type: string;
  actor_id: string;
  action: string;
  model_name: string | null;
  confidence_score: number | null;
  input_summary: string | null;
  output_summary: string | null;
}

// ============================================================================
// Status Badge
// ============================================================================

const STATUS_CFG: Record<string, { label: string; bg: string; color: string }> = {
  draft:                   { label: 'Draft',            bg: 'var(--surface-alt)',  color: 'var(--text-secondary)' },
  processing:              { label: 'Processing',       bg: 'var(--amber-soft)',   color: 'var(--amber)' },
  pending_nurse_review:    { label: 'Pending Review',   bg: 'var(--info-soft)',    color: 'var(--info)' },
  accepted:                { label: 'Accepted',         bg: 'var(--success-soft)', color: 'var(--success)' },
  rejected:                { label: 'Rejected',         bg: 'var(--danger-soft)',  color: 'var(--danger)' },
  error:                   { label: 'Error',            bg: 'var(--danger-soft)',  color: 'var(--danger)' },
  re_verification_required:{ label: 'Re-verification',  bg: 'var(--amber-soft)',   color: 'var(--amber)' },
};

function StatusBadge({ status }: { status: string }) {
  const c = STATUS_CFG[status] ?? { label: status, bg: 'var(--surface-alt)', color: 'var(--text-secondary)' };
  return (
    <span style={{ padding: '2px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: c.bg, color: c.color }}>
      {c.label}
    </span>
  );
}

const thStyle: React.CSSProperties = {
  padding: '10px 14px', textAlign: 'left', fontWeight: 600, fontSize: 12,
  color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
};
const tdStyle: React.CSSProperties = {
  padding: '11px 14px', verticalAlign: 'middle', fontSize: 13,
};

// ============================================================================
// Edit Case Modal
// ============================================================================

interface EditModalProps {
  caseRow: CaseRow;
  onClose: () => void;
  onSaved: () => void;
}

function EditCaseModal({ caseRow, onClose, onSaved }: EditModalProps) {
  const [fields, setFields] = useState({
    member_id: caseRow.member_id || '',
    provider_id: caseRow.provider_id || '',
    cpt_code: caseRow.cpt_code || '',
    icd_code: caseRow.icd_code || '',
    service_type: caseRow.service_type || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const isDecided = ['accepted', 'rejected'].includes(caseRow.status);

  const handleSave = async () => {
    if (isDecided && !confirmed) {
      setError('Please confirm that you want to re-queue this decided case.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/api/admin/cases/${caseRow.case_id}`, fields);
      onSaved();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(10,16,22,0.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div className="card" style={{ width: 480, padding: 28, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>Edit Case</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {caseRow.case_id}
        </div>

        {isDecided && (
          <div style={{
            background: 'var(--amber-soft)', border: '1px solid var(--amber-soft-border)',
            borderRadius: 'var(--radius-sm)', padding: '10px 14px', fontSize: 13, color: 'var(--amber)',
          }}>
            ⚠ This case has been <strong>{caseRow.status}</strong>. Saving will invalidate the existing decision and
            return it to the nurse review queue with "Re-verification Required" status.
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, cursor: 'pointer' }}>
              <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
              <span style={{ fontWeight: 600 }}>I understand, proceed with edit</span>
            </label>
          </div>
        )}

        {(['member_id', 'provider_id', 'cpt_code', 'icd_code', 'service_type'] as const).map(f => (
          <div key={f}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: 12, marginBottom: 4, textTransform: 'capitalize' }}>
              {f.replace('_', ' ')}
            </label>
            <input
              id={`edit-${f}`}
              value={fields[f]}
              onChange={e => setFields(prev => ({ ...prev, [f]: e.target.value }))}
              style={{
                width: '100%', padding: '7px 10px', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)', fontSize: 13, fontFamily: 'var(--font-sans)',
                background: 'var(--surface)', color: 'var(--text)', outline: 'none',
              }}
            />
          </div>
        ))}

        {error && (
          <div style={{ background: 'var(--danger-soft)', border: '1px solid var(--danger-soft-border)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', color: 'var(--danger)', fontSize: 12 }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button id="btn-save-edit" className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// All Cases Tab — T070
// ============================================================================

function AllCasesTab() {
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [editCase, setEditCase] = useState<CaseRow | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/api/admin/cases');
      setCases(res.data);
    } catch { /* silently */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ padding: 32, color: 'var(--text-muted)' }}>Loading cases…</div>;

  return (
    <div>
      {editCase && (
        <EditCaseModal
          caseRow={editCase}
          onClose={() => setEditCase(null)}
          onSaved={async () => { setEditCase(null); await load(); }}
        />
      )}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--surface-alt)' }}>
                {['Case ID', 'Policy', 'Service', 'Status', 'Lock Holder', 'SLA', 'Decided', 'Created', ''].map(h => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cases.length === 0 ? (
                <tr><td colSpan={9} style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>No cases found</td></tr>
              ) : cases.map((c, i) => (
                <tr key={c.case_id} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-sunken)' }}>
                  <td style={tdStyle}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{c.case_id.slice(0, 8)}…</span>
                  </td>
                  <td style={tdStyle}>{c.policy_name}</td>
                  <td style={tdStyle}>{c.service_type || '—'}</td>
                  <td style={tdStyle}><StatusBadge status={c.status} /></td>
                  <td style={{ ...tdStyle, color: c.lock_holder ? 'var(--primary)' : 'var(--text-muted)' }}>
                    {c.lock_holder ? `🔒 ${c.lock_holder}` : '—'}
                  </td>
                  <td style={tdStyle}>
                    {c.sla_start_at ? `${Math.floor((Date.now() - new Date(c.sla_start_at).getTime()) / 3600000)}h` : '—'}
                  </td>
                  <td style={tdStyle}>
                    {c.decided_at ? new Date(c.decided_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={tdStyle}>{new Date(c.created_at).toLocaleDateString()}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    <button
                      id={`btn-edit-case-${c.case_id.slice(0, 8)}`}
                      className="btn btn-ghost btn-sm"
                      onClick={() => setEditCase(c)}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Nurse Workload Tab — T072
// ============================================================================

function NurseWorkloadTab() {
  const [workload, setWorkload] = useState<NurseWorkload[]>([]);
  const [loading, setLoading] = useState(true);
  const [historyNurse, setHistoryNurse] = useState<NurseWorkload | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    api.get('/api/admin/nurses/workload')
      .then(res => setWorkload(res.data))
      .finally(() => setLoading(false));
  }, []);

  const viewHistory = async (nurse: NurseWorkload) => {
    setHistoryNurse(nurse);
    setHistoryLoading(true);
    try {
      const res = await api.get(`/api/admin/nurses/${nurse.nurse_id}/history`);
      setHistory(res.data);
    } catch { setHistory([]); }
    finally { setHistoryLoading(false); }
  };

  if (loading) return <div style={{ padding: 32, color: 'var(--text-muted)' }}>Loading workload…</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 700, fontSize: 14 }}>
          Nurse Workload (FR-033)
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: 'var(--surface-alt)' }}>
              {['Nurse', 'Status', 'Active Locks', 'Total Decisions', ''].map(h => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {workload.map((n, i) => (
              <tr key={n.nurse_id} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-sunken)' }}>
                <td style={tdStyle}>{n.username}</td>
                <td style={tdStyle}>
                  <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600,
                    background: n.is_active ? 'var(--success-soft)' : 'var(--danger-soft)',
                    color: n.is_active ? 'var(--success)' : 'var(--danger)' }}>
                    {n.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td style={tdStyle}>{n.active_locks}</td>
                <td style={tdStyle}>{n.decided_cases}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => viewHistory(n)}>
                    View History
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {historyNurse && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>History — {historyNurse.username}</span>
            <button className="btn btn-ghost btn-sm" onClick={() => setHistoryNurse(null)}>Close</button>
          </div>
          {historyLoading ? (
            <div style={{ padding: 24, color: 'var(--text-muted)' }}>Loading…</div>
          ) : history.length === 0 ? (
            <div style={{ padding: 24, color: 'var(--text-muted)' }}>No decisions recorded.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--surface-alt)' }}>
                  {['Case ID', 'Policy', 'Decision', 'Comment', 'Decided'].map(h => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((d, i) => (
                  <tr key={d.decision_id} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-sunken)' }}>
                    <td style={tdStyle}><span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{d.case_id.slice(0, 8)}…</span></td>
                    <td style={tdStyle}>{d.policy_name}</td>
                    <td style={tdStyle}>
                      <span style={{ padding: '2px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600,
                        background: d.decision === 'accepted' ? 'var(--success-soft)' : 'var(--danger-soft)',
                        color: d.decision === 'accepted' ? 'var(--success)' : 'var(--danger)' }}>
                        {d.decision === 'accepted' ? '✓ Accepted' : '✗ Rejected'}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, color: 'var(--text-secondary)', maxWidth: 200 }}>
                      {d.comment ? d.comment.slice(0, 80) + (d.comment.length > 80 ? '…' : '') : '—'}
                    </td>
                    <td style={tdStyle}>{d.decided_at ? new Date(d.decided_at).toLocaleDateString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// User Management Tab — T072
// ============================================================================

function UserManagementTab() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'nurse' });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/api/admin/users');
      setUsers(res.data);
    } catch { /* silently */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    if (!newUser.username.trim() || !newUser.password.trim()) {
      setCreateError('Username and password are required'); return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      await api.post('/api/admin/users', newUser);
      setNewUser({ username: '', password: '', role: 'nurse' });
      setShowCreate(false);
      await load();
    } catch (e: any) {
      setCreateError(e?.response?.data?.detail || 'Create failed');
    } finally {
      setCreating(false);
    }
  };

  const toggleActive = async (user: UserRow) => {
    try {
      await api.patch(`/api/admin/users/${user.id}`, { is_active: !user.is_active });
      await load();
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Update failed');
    }
  };

  if (loading) return <div style={{ padding: 32, color: 'var(--text-muted)' }}>Loading users…</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Create User Form */}
      <div className="card" style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: showCreate ? 16 : 0 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>Create User</span>
          <button id="btn-toggle-create-user" className="btn btn-primary btn-sm" onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? 'Cancel' : '+ New User'}
          </button>
        </div>

        {showCreate && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            {[['username', 'Username'], ['password', 'Password']].map(([f, label]) => (
              <div key={f} style={{ flex: '1 0 160px' }}>
                <label style={{ display: 'block', fontWeight: 600, fontSize: 12, marginBottom: 4 }}>{label}</label>
                <input
                  id={`new-user-${f}`}
                  type={f === 'password' ? 'password' : 'text'}
                  value={(newUser as any)[f]}
                  onChange={e => setNewUser(prev => ({ ...prev, [f]: e.target.value }))}
                  style={{ width: '100%', padding: '7px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontFamily: 'var(--font-sans)', background: 'var(--surface)', color: 'var(--text)', outline: 'none' }}
                />
              </div>
            ))}
            <div style={{ flex: '1 0 120px' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Role</label>
              <select
                id="new-user-role"
                value={newUser.role}
                onChange={e => setNewUser(prev => ({ ...prev, role: e.target.value }))}
                style={{ width: '100%', padding: '7px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, background: 'var(--surface)', color: 'var(--text)', outline: 'none' }}
              >
                <option value="intake">Intake</option>
                <option value="nurse">Nurse</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <button id="btn-create-user" className="btn btn-primary" onClick={handleCreate} disabled={creating} style={{ height: 36 }}>
              {creating ? 'Creating…' : 'Create'}
            </button>
          </div>
        )}

        {createError && (
          <div style={{ marginTop: 10, color: 'var(--danger)', fontSize: 12 }}>{createError}</div>
        )}
      </div>

      {/* User List */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: 'var(--surface-alt)' }}>
              {['Username', 'Role', 'Status', 'Created', ''].map(h => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u, i) => (
              <tr key={u.id} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-sunken)' }}>
                <td style={tdStyle}>{u.username}</td>
                <td style={tdStyle}>
                  <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600,
                    background: u.role === 'admin' ? 'var(--primary-soft)' : 'var(--surface-alt)',
                    color: u.role === 'admin' ? 'var(--primary)' : 'var(--text-secondary)' }}>
                    {u.role}
                  </span>
                </td>
                <td style={tdStyle}>
                  <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600,
                    background: u.is_active ? 'var(--success-soft)' : 'var(--danger-soft)',
                    color: u.is_active ? 'var(--success)' : 'var(--danger)' }}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td style={tdStyle}>{new Date(u.created_at).toLocaleDateString()}</td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  <button
                    id={`btn-toggle-user-${u.id.slice(0, 8)}`}
                    className="btn btn-ghost btn-sm"
                    onClick={() => toggleActive(u)}
                    style={{ color: u.is_active ? 'var(--danger)' : 'var(--success)' }}
                  >
                    {u.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================================
// Audit Log Tab — T071
// ============================================================================

function AuditLogTab() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('');
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 30 };
      if (filterAction.trim()) params.action = filterAction.trim();
      const res = await api.get('/api/admin/audit', { params });
      setEntries(res.data.entries);
    } catch { setEntries([]); }
    finally { setLoading(false); }
  }, [page, filterAction]);

  useEffect(() => { load(); }, [load]);

  const actorColor = (type: string) => {
    if (type === 'agent') return 'var(--primary)';
    if (type === 'user') return 'var(--info)';
    return 'var(--text-muted)';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <input
          id="audit-filter-action"
          placeholder="Filter by action…"
          value={filterAction}
          onChange={e => { setFilterAction(e.target.value); setPage(1); }}
          style={{ padding: '7px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, background: 'var(--surface)', color: 'var(--text)', outline: 'none', width: 240 }}
        />
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Latest 30 entries</span>
      </div>

      {loading ? (
        <div style={{ padding: 32, color: 'var(--text-muted)' }}>Loading audit log…</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {entries.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>No audit entries found</div>
          ) : entries.map((e, i) => (
            <div
              key={e.id}
              style={{
                borderBottom: '1px solid var(--border)',
                padding: '12px 16px',
                background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-sunken)',
                cursor: 'pointer',
              }}
              onClick={() => setExpanded(expanded === e.id ? null : e.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 160 }}>
                  {new Date(e.timestamp).toLocaleString()}
                </span>
                <span style={{ padding: '1px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600,
                  background: 'var(--surface-alt)', color: actorColor(e.actor_type) }}>
                  {e.actor_type}
                </span>
                <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--text)' }}>{e.action}</span>
                {e.model_name && (
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{e.model_name}</span>
                )}
                {e.confidence_score != null && (
                  <span style={{ fontSize: 11, color: 'var(--primary)' }}>
                    conf={Math.round(e.confidence_score * 100)}%
                  </span>
                )}
              </div>

              {expanded === e.id && (
                <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    <strong>Actor ID:</strong> {e.actor_id}
                  </div>
                  {e.case_id && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      <strong>Case:</strong> {e.case_id}
                    </div>
                  )}
                  {e.input_summary && (
                    <div style={{ background: 'var(--surface-alt)', borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontSize: 12 }}>
                      <strong>In:</strong> {e.input_summary}
                    </div>
                  )}
                  {e.output_summary && (
                    <div style={{ background: 'var(--surface-alt)', borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontSize: 12 }}>
                      <strong>Out:</strong> {e.output_summary}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
          ← Prev
        </button>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Page {page}</span>
        <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => p + 1)} disabled={entries.length < 30}>
          Next →
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// AdminDashboard root
// ============================================================================

const TABS = ['All Cases', 'Nurse Workload', 'User Management', 'Audit Log'] as const;
type Tab = typeof TABS[number];

const AdminDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('All Cases');

  return (
    <AppLayout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Header */}
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Admin Dashboard</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 14 }}>
            Full operational oversight — cases, nurses, users, and audit trail
          </p>
        </div>

        {/* Tab strip */}
        <div style={{ display: 'flex', borderBottom: '2px solid var(--border)' }}>
          {TABS.map(tab => (
            <button
              key={tab}
              id={`admin-tab-${tab.toLowerCase().replace(' ', '-')}`}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '10px 20px', background: 'none', border: 'none',
                borderBottom: activeTab === tab ? '2px solid var(--primary)' : '2px solid transparent',
                marginBottom: -2, cursor: 'pointer',
                fontWeight: activeTab === tab ? 700 : 400,
                color: activeTab === tab ? 'var(--primary)' : 'var(--text-secondary)',
                fontSize: 13, transition: 'all 0.15s', whiteSpace: 'nowrap',
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'All Cases'       && <AllCasesTab />}
        {activeTab === 'Nurse Workload'  && <NurseWorkloadTab />}
        {activeTab === 'User Management' && <UserManagementTab />}
        {activeTab === 'Audit Log'       && <AuditLogTab />}
      </div>
    </AppLayout>
  );
};

export default AdminDashboard;
