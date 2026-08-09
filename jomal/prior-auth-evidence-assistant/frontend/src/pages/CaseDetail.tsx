/**
 * CaseDetail page — T062
 * Only accessible after locking; redirects to queue if not locked.
 * Tabs: Evidence Summary | Documents
 * Decision panel: Accept/Reject + mandatory comment (FR-028).
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import EvidenceSummary from '../components/EvidenceSummary';
import GapChecklist from '../components/GapChecklist';
import DocumentViewer from '../components/DocumentViewer';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

interface SummaryData {
  case_id: string;
  status: string;
  summary_available: boolean;
  summary_text: string | null;
  summary_metadata: {
    gap_count?: number;
    flags?: string[];
  } | null;
  verdict_summary: string | null;
  documents: DocRecord[];
}

interface DocRecord {
  id: string;
  original_filename: string;
  file_type: string;
  ocr_status: string;
  extracted_text_length: number;
}

const CaseDetail: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<'summary' | 'documents'>('summary');
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Decision form state
  const [decision, setDecision] = useState<'accepted' | 'rejected' | null>(null);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const fetchSummary = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/cases/${caseId}/summary`);
      setSummaryData(res.data);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || 'Failed to load case details';
      if (e?.response?.status === 403) {
        // Not locked — redirect back
        navigate('/nurse-review');
        return;
      }
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [caseId, navigate]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const handleDecision = async () => {
    if (!decision) return;
    if (!comment.trim()) {
      setSubmitError('A comment is required (FR-028)');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.post(`/api/nurse-review/${caseId}/decide`, {
        decision,
        comment: comment.trim(),
      });
      setSubmitSuccess(true);
      setTimeout(() => navigate('/nurse-review'), 2000);
    } catch (e: any) {
      setSubmitError(e?.response?.data?.detail || 'Decision submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div style={{ padding: 64, textAlign: 'center', color: 'var(--text-muted)' }}>
          Loading case details…
        </div>
      </AppLayout>
    );
  }

  if (error) {
    return (
      <AppLayout>
        <div
          style={{
            background: 'var(--danger-soft)',
            border: '1px solid var(--danger-soft-border)',
            borderRadius: 'var(--radius)',
            padding: '16px 20px',
            color: 'var(--danger)',
            margin: 32,
          }}
        >
          <strong>Error:</strong> {error}
          <br />
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginTop: 12 }}
            onClick={() => navigate('/nurse-review')}
          >
            ← Back to Queue
          </button>
        </div>
      </AppLayout>
    );
  }

  // Success banner
  if (submitSuccess) {
    return (
      <AppLayout>
        <div
          style={{
            background: 'var(--success-soft)',
            border: '1px solid var(--success-soft-border)',
            borderRadius: 'var(--radius)',
            padding: '32px',
            textAlign: 'center',
            margin: 64,
            color: 'var(--success)',
          }}
        >
          <div style={{ fontSize: 32, marginBottom: 12 }}>✓</div>
          <strong>Decision submitted successfully!</strong>
          <p style={{ margin: '8px 0 0' }}>Returning to queue…</p>
        </div>
      </AppLayout>
    );
  }

  const gapItems = summaryData?.summary_metadata
    ? []
    : [];

  return (
    <AppLayout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <button
              className="btn btn-ghost btn-sm"
              style={{ marginBottom: 8 }}
              onClick={() => navigate('/nurse-review')}
            >
              ← Back to Queue
            </button>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>
              Case Review
            </h1>
            <p style={{ margin: '4px 0 0', color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
              {caseId}
            </p>
          </div>
          <div>
            {summaryData?.status && (
              <span
                style={{
                  padding: '4px 14px',
                  borderRadius: 999,
                  fontSize: 12,
                  fontWeight: 600,
                  background: 'var(--info-soft)',
                  color: 'var(--info)',
                }}
              >
                {summaryData.status.replace(/_/g, ' ')}
              </span>
            )}
          </div>
        </div>

        {/* Main content + decision panel */}
        <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
          {/* Content area */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Tabs */}
            <div style={{ display: 'flex', borderBottom: '2px solid var(--border)', marginBottom: 20 }}>
              {(['summary', 'documents'] as const).map(tab => (
                <button
                  key={tab}
                  id={`detail-tab-${tab}`}
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
                  {tab === 'summary' ? 'Evidence Summary' : 'Documents'}
                </button>
              ))}
            </div>

            {/* Tab content */}
            {activeTab === 'summary' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {!summaryData?.summary_available ? (
                  <div
                    style={{
                      background: 'var(--amber-soft)',
                      border: '1px solid var(--amber-soft-border)',
                      borderRadius: 'var(--radius)',
                      padding: '16px 20px',
                      color: 'var(--amber)',
                      fontSize: 14,
                    }}
                  >
                    AI summary not yet available for this case. Review documents manually.
                  </div>
                ) : (
                  <>
                    <EvidenceSummary
                      summary={{
                        summary_text: summaryData.summary_text || '',
                        flags: summaryData.summary_metadata?.flags,
                      }}
                    />
                    {summaryData.summary_metadata?.gap_count != null &&
                      summaryData.summary_metadata.gap_count > 0 && (
                        <div className="card" style={{ padding: 20 }}>
                          <div
                            style={{
                              fontSize: 12,
                              fontWeight: 700,
                              letterSpacing: 1,
                              textTransform: 'uppercase',
                              color: 'var(--text-muted)',
                              marginBottom: 16,
                            }}
                          >
                            Gap Checklist ({summaryData.summary_metadata.gap_count} item{summaryData.summary_metadata.gap_count !== 1 ? 's' : ''})
                          </div>
                          <GapChecklist gapItems={[]} />
                        </div>
                      )}
                  </>
                )}
              </div>
            )}

            {activeTab === 'documents' && summaryData && (
              <DocumentViewer
                caseId={summaryData.case_id}
                documents={summaryData.documents}
              />
            )}
          </div>

          {/* Decision panel */}
          <div
            className="card"
            style={{
              width: 300,
              flexShrink: 0,
              padding: 24,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
              position: 'sticky',
              top: 80,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 15 }}>Clinical Decision</div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(['accepted', 'rejected'] as const).map(d => (
                <label
                  key={d}
                  id={`decision-option-${d}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-sm)',
                    border: `2px solid ${decision === d
                      ? d === 'accepted' ? 'var(--success)' : 'var(--danger)'
                      : 'var(--border)'}`,
                    background: decision === d
                      ? d === 'accepted' ? 'var(--success-soft)' : 'var(--danger-soft)'
                      : 'transparent',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  <input
                    type="radio"
                    name="decision"
                    value={d}
                    checked={decision === d}
                    onChange={() => setDecision(d)}
                    style={{ accentColor: d === 'accepted' ? 'var(--success)' : 'var(--danger)' }}
                  />
                  <span
                    style={{
                      fontWeight: 600,
                      fontSize: 13,
                      color: d === 'accepted' ? 'var(--success)' : 'var(--danger)',
                      textTransform: 'capitalize',
                    }}
                  >
                    {d === 'accepted' ? '✓ Accept' : '✗ Reject'}
                  </span>
                </label>
              ))}
            </div>

            <div>
              <label
                htmlFor="decision-comment"
                style={{ display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6 }}
              >
                Clinical Rationale <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <textarea
                id="decision-comment"
                value={comment}
                onChange={e => setComment(e.target.value)}
                placeholder="Required — describe your clinical reasoning…"
                rows={5}
                style={{
                  width: '100%',
                  resize: 'vertical',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px',
                  fontSize: 13,
                  fontFamily: 'var(--font-sans)',
                  background: 'var(--surface)',
                  color: 'var(--text)',
                  outline: 'none',
                }}
              />
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                Mandatory per FR-028
              </div>
            </div>

            {submitError && (
              <div
                style={{
                  background: 'var(--danger-soft)',
                  border: '1px solid var(--danger-soft-border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px',
                  color: 'var(--danger)',
                  fontSize: 12,
                }}
              >
                {submitError}
              </div>
            )}

            <button
              id="btn-submit-decision"
              className="btn btn-primary"
              onClick={handleDecision}
              disabled={!decision || !comment.trim() || submitting}
              style={{ width: '100%' }}
            >
              {submitting ? 'Submitting…' : 'Submit Decision'}
            </button>

            <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
              This decision is final and will be recorded in the audit trail.
              The AI summary is advisory only — the decision is yours.
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default CaseDetail;
