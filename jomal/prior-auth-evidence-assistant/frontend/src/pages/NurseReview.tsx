/**
 * NurseReview page — T061, T066
 * Tab layout: Queue | History
 * Queue: metadata-only, lock/unlock per case, 15-second polling (T067).
 * History: decided cases per nurse (FR-029a).
 */
import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import SearchBar, { type CaseSearchResult } from '../components/SearchBar';
import { useAuth } from '../context/AuthContext';
import { usePolling } from '../hooks/usePolling';
import api from '../services/api';

interface QueueItem {
  case_id: string;
  policy_name: string;
  member_id: string;
  provider_id: string;
  service_type: string | null;
  cpt_code: string | null;
  status: string;
  sla_start_at: string | null;
  is_locked_by_me: boolean;
  is_locked_by_other: boolean;
  lock_expires_at: string | null;
}

interface HistoryItem {
  decision_id: string;
  case_id: string;
  policy_name: string;
  service_type: string | null;
  member_id: string;
  decision: 'accepted' | 'rejected';
  comment: string;
  decided_at: string;
  case_status: string;
}

function SlaTimer({ slaStart }: { slaStart: string | null }) {
  const [display, setDisplay] = React.useState('—');

  React.useEffect(() => {
    if (!slaStart) { setDisplay('—'); return; }
    const update = () => {
      const elapsed = Date.now() - new Date(slaStart).getTime();
      const h = Math.floor(elapsed / 3600000);
      const m = Math.floor((elapsed % 3600000) / 60000);
      setDisplay(`${h}h ${m}m`);
    };
    update();
    const id = setInterval(update, 30000);
    return () => clearInterval(id);
  }, [slaStart]);

  return <span>{display}</span>;
}

const NurseReview: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'queue' | 'history'>('queue');
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lockingId, setLockingId] = useState<string | null>(null);
  const [highlightId, setHighlightId] = useState<string | null>(null);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/api/nurse-review/queue');
      setQueue(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load queue');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await api.get('/api/nurse-review/history');
      setHistory(res.data);
    } catch { /* silently */ }
  }, []);

  // Poll queue every 15s (T067)
  usePolling(fetchQueue, { enabled: activeTab === 'queue', interval: 15000 });

  // Load history when switching tabs
  React.useEffect(() => {
    if (activeTab === 'history') fetchHistory();
  }, [activeTab, fetchHistory]);

  const handleLock = async (caseId: string) => {
    setLockingId(caseId);
    try {
      await api.post(`/api/nurse-review/${caseId}/lock`);
      await fetchQueue();
      navigate(`/nurse-review/${caseId}`);
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Failed to lock case');
    } finally {
      setLockingId(null);
    }
  };

  const handleUnlock = async (caseId: string) => {
    setLockingId(caseId);
    try {
      await api.delete(`/api/nurse-review/${caseId}/lock`);
      await fetchQueue();
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Failed to release lock');
    } finally {
      setLockingId(null);
    }
  };

  const handleSearchSelect = (result: CaseSearchResult) => {
    // If it's already in the visible queue, jump the user to it.
    const inQueue = queue.some(q => q.case_id === result.case_id);
    if (inQueue) {
      if (activeTab !== 'queue') setActiveTab('queue');
      setHighlightId(result.case_id);
      setTimeout(() => {
        document.getElementById(`queue-row-${result.case_id}`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
      return;
    }
    // Otherwise it's outside this nurse's current queue (already decided,
    // locked by someone else and not yet expired, etc.) — nothing to jump to.
    alert('This case is not currently in your review queue.');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Nurse Review</h1>
            <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 14 }}>
              Prior authorization cases awaiting clinical decision
            </p>
          </div>
          <div style={{ width: 320 }}>
            <SearchBar onSelect={handleSearchSelect} />
          </div>
        </div>

        {/* Tab strip */}
        <div style={{ display: 'flex', gap: 0, borderBottom: '2px solid var(--border)' }}>
          {(['queue', 'history'] as const).map(tab => (
            <button
              key={tab}
              id={`nurse-tab-${tab}`}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '10px 24px',
                background: 'none',
                border: 'none',
                borderBottom: activeTab === tab ? '2px solid var(--primary)' : '2px solid transparent',
                marginBottom: -2,
                cursor: 'pointer',
                fontWeight: activeTab === tab ? 700 : 400,
                color: activeTab === tab ? 'var(--primary)' : 'var(--text-secondary)',
                fontSize: 14,
                transition: 'all 0.15s',
                textTransform: 'capitalize',
              }}
            >
              {tab === 'queue' ? 'Review Queue' : 'My History'}
            </button>
          ))}
        </div>

        {/* === QUEUE TAB === */}
        {activeTab === 'queue' && (
          <div>
            {error && (
              <div
                style={{
                  background: 'var(--danger-soft)',
                  border: '1px solid var(--danger-soft-border)',
                  borderRadius: 'var(--radius)',
                  padding: '12px 16px',
                  color: 'var(--danger)',
                  marginBottom: 16,
                  fontSize: 14,
                }}
              >
                {error}
              </div>
            )}

            {loading && queue.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
                Loading review queue…
              </div>
            ) : queue.length === 0 ? (
              <div
                className="card"
                style={{
                  padding: 48,
                  textAlign: 'center',
                  color: 'var(--text-muted)',
                  fontSize: 15,
                }}
              >
                <div style={{ fontSize: 32, marginBottom: 12 }}>✓</div>
                No cases awaiting review
              </div>
            ) : (
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', minWidth: 820, borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-alt)' }}>
                      {['Case ID', 'Policy', 'Service', 'Member', 'Status', 'SLA', 'Lock', 'Actions'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {queue.map((item, i) => (
                      <tr
                        key={item.case_id}
                        id={`queue-row-${item.case_id}`}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          background: highlightId === item.case_id
                            ? 'var(--primary-soft)'
                            : (i % 2 === 0 ? 'var(--surface)' : 'var(--surface-sunken)'),
                          transition: 'background 0.3s',
                        }}
                      >
                        <td style={tdStyle}>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                            {item.case_id.slice(0, 8)}…
                          </span>
                        </td>
                        <td style={tdStyle}>{item.policy_name}</td>
                        <td style={tdStyle}>{item.service_type || '—'}</td>
                        <td style={tdStyle}>{item.member_id || '—'}</td>
                        <td style={tdStyle}>
                          <StatusBadge status={item.status} />
                        </td>
                        <td style={tdStyle}>
                          <SlaTimer slaStart={item.sla_start_at} />
                        </td>
                        <td style={tdStyle}>
                          {item.is_locked_by_me ? (
                            <span style={{ color: 'var(--primary)', fontWeight: 600, fontSize: 12 }}>
                              🔒 Locked by you
                            </span>
                          ) : item.is_locked_by_other ? (
                            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                              🔒 Locked by another
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                              Unlocked
                            </span>
                          )}
                        </td>
                        <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                          {item.is_locked_by_me ? (
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button
                                id={`btn-review-${item.case_id}`}
                                className="btn btn-primary btn-sm"
                                onClick={() => navigate(`/nurse-review/${item.case_id}`)}
                              >
                                Review
                              </button>
                              <button
                                id={`btn-unlock-${item.case_id}`}
                                className="btn btn-ghost btn-sm"
                                onClick={() => handleUnlock(item.case_id)}
                                disabled={lockingId === item.case_id}
                              >
                                Release
                              </button>
                            </div>
                          ) : !item.is_locked_by_other ? (
                            <button
                              id={`btn-lock-${item.case_id}`}
                              className="btn btn-primary btn-sm"
                              onClick={() => handleLock(item.case_id)}
                              disabled={lockingId === item.case_id}
                            >
                              {lockingId === item.case_id ? 'Locking…' : 'Lock & Review'}
                            </button>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* === HISTORY TAB === */}
        {activeTab === 'history' && (
          <div>
            {history.length === 0 ? (
              <div
                className="card"
                style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 15 }}
              >
                No decisions recorded yet
              </div>
            ) : (
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', minWidth: 700, borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-alt)' }}>
                      {['Case ID', 'Policy', 'Service', 'Decision', 'Comment', 'Decided'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((item, i) => (
                      <tr
                        key={item.decision_id}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-sunken)',
                        }}
                      >
                        <td style={tdStyle}>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                            {item.case_id.slice(0, 8)}…
                          </span>
                        </td>
                        <td style={tdStyle}>{item.policy_name}</td>
                        <td style={tdStyle}>{item.service_type || '—'}</td>
                        <td style={tdStyle}>
                          <DecisionBadge decision={item.decision} />
                        </td>
                        <td style={{ ...tdStyle, maxWidth: 240, color: 'var(--text-secondary)' }}>
                          {item.comment
                            ? item.comment.slice(0, 100) + (item.comment.length > 100 ? '…' : '')
                            : '—'}
                        </td>
                        <td style={tdStyle}>
                          {item.decided_at
                            ? new Date(item.decided_at).toLocaleDateString()
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
  );
};

// ---------------------------------------------------------------------------
// Inline helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { label: string; color: string; bg: string }> = {
    pending_nurse_review: { label: 'Pending Review', color: 'var(--info)', bg: 'var(--info-soft)' },
    error: { label: 'Error — Manual Review', color: 'var(--danger)', bg: 'var(--danger-soft)' },
    processing: { label: 'Processing', color: 'var(--amber)', bg: 'var(--amber-soft)' },
  };
  const c = cfg[status] ?? { label: status, color: 'var(--text-secondary)', bg: 'var(--surface-alt)' };
  return (
    <span
      style={{
        padding: '2px 10px',
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        background: c.bg,
        color: c.color,
      }}
    >
      {c.label}
    </span>
  );
}

function DecisionBadge({ decision }: { decision: string }) {
  const isAccepted = decision === 'accepted';
  return (
    <span
      style={{
        padding: '2px 10px',
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        background: isAccepted ? 'var(--success-soft)' : 'var(--danger-soft)',
        color: isAccepted ? 'var(--success)' : 'var(--danger)',
      }}
    >
      {isAccepted ? '✓ Accepted' : '✗ Rejected'}
    </span>
  );
}

const thStyle: React.CSSProperties = {
  padding: '10px 16px',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: 12,
  color: 'var(--text-secondary)',
  borderBottom: '1px solid var(--border)',
  whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
  padding: '12px 16px',
  verticalAlign: 'middle',
};

export default NurseReview;
