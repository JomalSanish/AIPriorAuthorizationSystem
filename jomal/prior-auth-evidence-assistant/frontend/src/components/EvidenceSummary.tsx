/**
 * EvidenceSummary component — T063
 * Renders the structured AI evidence summary with classification badges,
 * confidence bars, citations, and gap checklist (FR-022).
 */
import React from 'react';

interface Citation {
  document_name?: string;
  page_number?: number;
  relevant_excerpt?: string;
}

interface VerdictRow {
  requirement_id: string;
  requirement_text: string;
  classification: 'Present' | 'Absent' | 'Unclear';
  composite_confidence: number;
  retrieval_score: number;
  llm_confidence: number;
  citation?: Citation | null;
  reasoning_text?: string;
}

interface GapItem {
  requirement_id: string;
  requirement_text: string;
  classification: 'Absent' | 'Unclear';
  citation?: Citation | null;
  confidence: number;
}

interface SummaryData {
  summary_text: string;
  verdicts?: VerdictRow[];
  gap_checklist?: GapItem[];
  flags?: string[];
}

interface Props {
  summary: SummaryData;
}

const ClassificationBadge: React.FC<{ classification: string }> = ({ classification }) => {
  const styles: Record<string, React.CSSProperties> = {
    Present: {
      background: 'var(--success-soft)',
      color: 'var(--success)',
      border: '1px solid var(--success-soft-border)',
    },
    Absent: {
      background: 'var(--danger-soft)',
      color: 'var(--danger)',
      border: '1px solid var(--danger-soft-border)',
    },
    Unclear: {
      background: 'var(--amber-soft)',
      color: 'var(--amber)',
      border: '1px solid var(--amber-soft-border)',
    },
  };

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: 0.3,
        ...styles[classification],
      }}
    >
      {classification}
    </span>
  );
};

const ConfidenceBar: React.FC<{ value: number; label?: string }> = ({ value, label }) => {
  const pct = Math.round(value * 100);
  const color =
    pct >= 75 ? 'var(--success)' : pct >= 50 ? 'var(--amber)' : 'var(--danger)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div
        style={{
          flex: 1,
          height: 6,
          background: 'var(--surface-alt)',
          borderRadius: 999,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: color,
            borderRadius: 999,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
      <span style={{ fontSize: 12, color: 'var(--text-secondary)', minWidth: 36 }}>
        {label ?? `${pct}%`}
      </span>
    </div>
  );
};

const EvidenceSummary: React.FC<Props> = ({ summary }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Warning flags */}
      {summary.flags && summary.flags.length > 0 && (
        <div
          style={{
            background: 'var(--amber-soft)',
            border: '1px solid var(--amber-soft-border)',
            borderRadius: 'var(--radius)',
            padding: '12px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <div style={{ fontWeight: 600, color: 'var(--amber)', fontSize: 13 }}>
            ⚠ Pipeline warnings
          </div>
          {summary.flags.map((f, i) => (
            <div key={i} style={{ fontSize: 13, color: 'var(--amber)' }}>
              {f}
            </div>
          ))}
        </div>
      )}

      {/* Prose summary */}
      <div
        className="card"
        style={{ padding: 20 }}
      >
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: 1,
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
            marginBottom: 10,
          }}
        >
          AI Evidence Summary
        </div>
        <p style={{ margin: 0, lineHeight: 1.7, color: 'var(--text)', fontSize: 14 }}>
          {summary.summary_text}
        </p>
      </div>

      {/* Per-requirement verdicts table */}
      {summary.verdicts && summary.verdicts.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div
            style={{
              padding: '14px 20px',
              borderBottom: '1px solid var(--border)',
              fontWeight: 600,
              fontSize: 13,
            }}
          >
            Requirement Verdicts
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--surface-alt)' }}>
                  <th style={thStyle}>Requirement</th>
                  <th style={{ ...thStyle, width: 100 }}>Status</th>
                  <th style={{ ...thStyle, width: 140 }}>Confidence</th>
                  <th style={{ ...thStyle, width: 180 }}>Citation</th>
                </tr>
              </thead>
              <tbody>
                {summary.verdicts.map((v, i) => (
                  <tr
                    key={v.requirement_id}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-sunken)',
                    }}
                  >
                    <td style={{ ...tdStyle, lineHeight: 1.5 }}>
                      <div>{v.requirement_text}</div>
                      {v.reasoning_text && v.reasoning_text !== 'No reasoning provided by LLM.' && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                          {v.reasoning_text.slice(0, 120)}
                          {v.reasoning_text.length > 120 ? '…' : ''}
                        </div>
                      )}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'center' }}>
                      <ClassificationBadge classification={v.classification} />
                    </td>
                    <td style={tdStyle}>
                      <ConfidenceBar value={v.composite_confidence} />
                    </td>
                    <td style={{ ...tdStyle, fontSize: 12 }}>
                      {v.citation ? (
                        <div>
                          <div style={{ fontWeight: 500 }}>
                            {v.citation.document_name}
                            {v.citation.page_number ? ` p.${v.citation.page_number}` : ''}
                          </div>
                          {v.citation.relevant_excerpt && (
                            <div
                              style={{
                                color: 'var(--text-muted)',
                                fontStyle: 'italic',
                                marginTop: 2,
                              }}
                            >
                              "{v.citation.relevant_excerpt.slice(0, 80)}
                              {v.citation.relevant_excerpt.length > 80 ? '…' : ''}"
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
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
  );
};

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
  verticalAlign: 'top',
};

export default EvidenceSummary;
