/**
 * GapChecklist component — T064
 * Separate Absent (red) and Unclear (amber) sections (FR-022).
 * Unclear items show ambiguous citation inline for nurse evaluation.
 */
import React from 'react';

interface Citation {
  document_name?: string;
  page_number?: number;
  relevant_excerpt?: string;
}

interface GapItem {
  requirement_id: string;
  requirement_text: string;
  classification: 'Absent' | 'Unclear';
  citation?: Citation | null;
  confidence: number;
}

interface Props {
  gapItems: GapItem[];
}

const GapChecklist: React.FC<Props> = ({ gapItems }) => {
  const absentItems = gapItems.filter(g => g.classification === 'Absent');
  const unclearItems = gapItems.filter(g => g.classification === 'Unclear');

  if (gapItems.length === 0) {
    return (
      <div
        style={{
          background: 'var(--success-soft)',
          border: '1px solid var(--success-soft-border)',
          borderRadius: 'var(--radius)',
          padding: '16px 20px',
          color: 'var(--success)',
          fontWeight: 600,
          fontSize: 14,
        }}
      >
        ✓ All requirements satisfied — no gaps found
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Absent section */}
      {absentItems.length > 0 && (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 10,
            }}
          >
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: 'var(--danger)',
                flexShrink: 0,
              }}
            />
            <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--danger)' }}>
              Missing Evidence ({absentItems.length})
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {absentItems.map(item => (
              <div
                key={item.requirement_id}
                style={{
                  background: 'var(--danger-soft)',
                  border: '1px solid var(--danger-soft-border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 16px',
                }}
              >
                <div style={{ fontWeight: 500, fontSize: 13, color: 'var(--text)' }}>
                  {item.requirement_text}
                </div>
                <div
                  style={{
                    marginTop: 4,
                    fontSize: 11,
                    color: 'var(--danger)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}
                >
                  No evidence found
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Unclear section */}
      {unclearItems.length > 0 && (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 10,
            }}
          >
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: 'var(--amber)',
                flexShrink: 0,
              }}
            />
            <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--amber)' }}>
              Needs Nurse Evaluation ({unclearItems.length})
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {unclearItems.map(item => (
              <div
                key={item.requirement_id}
                style={{
                  background: 'var(--amber-soft)',
                  border: '1px solid var(--amber-soft-border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 16px',
                }}
              >
                <div style={{ fontWeight: 500, fontSize: 13, color: 'var(--text)' }}>
                  {item.requirement_text}
                </div>
                <div
                  style={{
                    marginTop: 4,
                    fontSize: 11,
                    color: 'var(--amber)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}
                >
                  Ambiguous — review source
                </div>
                {item.citation && (
                  <div
                    style={{
                      marginTop: 8,
                      padding: '8px 12px',
                      background: 'rgba(255,255,255,0.6)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: 12,
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>
                      {item.citation.document_name}
                      {item.citation.page_number ? ` p.${item.citation.page_number}` : ''}
                    </span>
                    {item.citation.relevant_excerpt && (
                      <div style={{ marginTop: 4, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                        "{item.citation.relevant_excerpt.slice(0, 150)}
                        {item.citation.relevant_excerpt.length > 150 ? '…' : ''}"
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default GapChecklist;
