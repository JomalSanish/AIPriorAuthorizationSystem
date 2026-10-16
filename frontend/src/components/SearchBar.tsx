/**
 * SearchBar — T049 (US6 NLP Case Search)
 *
 * Free-text input with debounced search (300 ms) that calls
 * POST /api/cases/search and displays case-level results in a dropdown.
 *
 * Used on Case Management, Nurse Review, and Admin Dashboard pages.
 * Never shows raw document chunks (FR-038).
 */

import { useState, useEffect, useRef, useCallback, type KeyboardEvent } from 'react';
import api from '../services/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CaseSearchResult {
  case_id: string;
  service_type: string | null;
  status: string;
  policy_name: string | null;
  member_id: string | null;
  provider_id: string | null;
  cpt_code: string | null;
  icd_code: string | null;
  score: number;
  summary: string | null;
}

interface SearchBarProps {
  /** Called when the user clicks a result row. */
  onSelect?: (result: CaseSearchResult) => void;
  /** Placeholder text for the input. */
  placeholder?: string;
  /** Extra CSS class for the wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Status badge helpers (mirrors backend CaseStatus enum)
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<string, string> = {
  draft:                    'Draft',
  processing:               'Processing',
  pending_nurse_review:     'Pending Review',
  accepted:                 'Accepted',
  rejected:                 'Rejected',
  error:                    'Error',
  re_verification_required: 'Re-Verification',
};

const STATUS_COLORS: Record<string, string> = {
  draft:                    'var(--text-muted)',
  processing:               'var(--info)',
  pending_nurse_review:     'var(--amber)',
  accepted:                 'var(--success)',
  rejected:                 'var(--danger)',
  error:                    'var(--danger)',
  re_verification_required: 'var(--amber)',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SearchBar({ onSelect, placeholder = 'Search cases…', className = '' }: SearchBarProps) {
  const [query, setQuery]           = useState('');
  const [results, setResults]       = useState<CaseSearchResult[]>([]);
  const [isLoading, setIsLoading]   = useState(false);
  const [isOpen, setIsOpen]         = useState(false);
  const [activeIdx, setActiveIdx]   = useState(-1);
  const [error, setError]           = useState<string | null>(null);

  const inputRef    = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------------------------------------------------------------------------
  // Search execution
  // ---------------------------------------------------------------------------

  const runSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const resp = await api.post<CaseSearchResult[]>('/api/cases/search', { query: q });
      setResults(resp.data);
      setIsOpen(true);
      setActiveIdx(-1);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Search failed';
      setError(message);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Debounce: 300 ms after user stops typing
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runSearch(query);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, runSearch]);

  // ---------------------------------------------------------------------------
  // Close on outside click
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        dropdownRef.current && !dropdownRef.current.contains(target) &&
        inputRef.current   && !inputRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // ---------------------------------------------------------------------------
  // Keyboard navigation
  // ---------------------------------------------------------------------------

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx(i => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault();
      handleSelect(results[activeIdx]);
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  const handleSelect = (result: CaseSearchResult) => {
    setIsOpen(false);
    setQuery('');
    onSelect?.(result);
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div
      className={`search-bar-wrapper ${className}`}
      style={{ position: 'relative', width: '100%', maxWidth: 480 }}
    >
      {/* Input */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        {/* Search icon */}
        <span
          style={{
            position: 'absolute',
            left: 12,
            color: 'var(--text-muted)',
            pointerEvents: 'none',
            display: 'flex',
          }}
          aria-hidden="true"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </span>

        <input
          id="search-bar-input"
          ref={inputRef}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (results.length > 0) setIsOpen(true); }}
          placeholder={placeholder}
          autoComplete="off"
          aria-label="Search cases"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-controls="search-bar-dropdown"
          style={{
            width: '100%',
            padding: '10px 36px 10px 40px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            background: 'var(--surface)',
            color: 'var(--text)',
            fontSize: '0.875rem',
            outline: 'none',
            transition: 'border-color 0.15s, box-shadow 0.15s',
          }}
          onFocusCapture={e => { (e.target as HTMLInputElement).style.boxShadow = 'var(--focus-ring)'; (e.target as HTMLInputElement).style.borderColor = 'var(--primary)'; }}
          onBlurCapture={e => { (e.target as HTMLInputElement).style.boxShadow = 'none'; (e.target as HTMLInputElement).style.borderColor = 'var(--border)'; }}
        />

        {/* Loading spinner */}
        {isLoading && (
          <span
            style={{
              position: 'absolute',
              right: 12,
              display: 'flex',
              animation: 'spin 0.8s linear infinite',
            }}
            aria-label="Loading…"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          </span>
        )}

        {/* Clear button */}
        {query && !isLoading && (
          <button
            id="search-bar-clear"
            onClick={() => { setQuery(''); setResults([]); setIsOpen(false); inputRef.current?.focus(); }}
            style={{
              position: 'absolute',
              right: 10,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-muted)',
              padding: 2,
              display: 'flex',
              borderRadius: 4,
            }}
            aria-label="Clear search"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        )}
      </div>

      {/* Error message */}
      {error && !isLoading && (
        <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: 'var(--danger)' }}>
          {error}
        </p>
      )}

      {/* Dropdown results */}
      {isOpen && results.length > 0 && (
        <div
          id="search-bar-dropdown"
          ref={dropdownRef}
          role="listbox"
          aria-label="Case search results"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            right: 0,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 1000,
            overflow: 'hidden',
            maxHeight: 380,
            overflowY: 'auto',
          }}
        >
          {/* Header row */}
          <div style={{
            padding: '6px 14px',
            fontSize: '0.7rem',
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
            borderBottom: '1px solid var(--border)',
            background: 'var(--surface-sunken)',
          }}>
            {results.length} result{results.length !== 1 ? 's' : ''}
          </div>

          {results.map((r, idx) => (
            <button
              key={r.case_id}
              role="option"
              aria-selected={idx === activeIdx}
              id={`search-result-${idx}`}
              onClick={() => handleSelect(r)}
              onMouseEnter={() => setActiveIdx(idx)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                border: 'none',
                borderBottom: idx < results.length - 1 ? '1px solid var(--border)' : 'none',
                cursor: 'pointer',
                padding: '10px 14px',
                background: idx === activeIdx ? 'var(--primary-soft)' : 'transparent',
                transition: 'background 0.1s',
              }}
            >
              {/* Top row: case id + status */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  #{r.case_id.slice(-8).toUpperCase()}
                </span>
                <span style={{
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  padding: '2px 7px',
                  borderRadius: 99,
                  background: STATUS_COLORS[r.status] ? `${STATUS_COLORS[r.status]}22` : 'var(--surface-alt)',
                  color: STATUS_COLORS[r.status] ?? 'var(--text-muted)',
                }}>
                  {STATUS_LABELS[r.status] ?? r.status}
                </span>
              </div>

              {/* Middle row: service type + policy */}
              <div style={{ display: 'flex', gap: 12, marginTop: 4 }}>
                {r.service_type && (
                  <span style={{ fontSize: '0.82rem', color: 'var(--text)', fontWeight: 500 }}>
                    {r.service_type}
                  </span>
                )}
                {r.policy_name && (
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {r.policy_name}
                  </span>
                )}
              </div>

              {/* Bottom row: codes / member / score */}
              <div style={{ display: 'flex', gap: 10, marginTop: 3, flexWrap: 'wrap', alignItems: 'center' }}>
                {r.cpt_code && (
                  <Code label="CPT" value={r.cpt_code} />
                )}
                {r.icd_code && (
                  <Code label="ICD" value={r.icd_code} />
                )}
                {r.member_id && (
                  <Code label="MBR" value={r.member_id} />
                )}
                <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                  score {r.score.toFixed(3)}
                </span>
              </div>

              {/* Summary (only visible to admin) */}
              {r.summary && (
                <p style={{
                  margin: '5px 0 0',
                  fontSize: '0.78rem',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.45,
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}>
                  {r.summary}
                </p>
              )}
            </button>
          ))}
        </div>
      )}

      {/* No results state */}
      {isOpen && results.length === 0 && !isLoading && query.trim() && (
        <div
          ref={dropdownRef}
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            right: 0,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 1000,
            padding: '18px 14px',
            textAlign: 'center',
            fontSize: '0.85rem',
            color: 'var(--text-muted)',
          }}
        >
          No cases found for &ldquo;{query}&rdquo;
        </div>
      )}

      {/* Keyframe for spinner (injected once) */}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline helper: small code/label pill
// ---------------------------------------------------------------------------

function Code({ label, value }: { label: string; value: string }) {
  return (
    <span style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
      <span style={{
        fontSize: '0.65rem',
        fontWeight: 700,
        letterSpacing: '0.04em',
        color: 'var(--primary-tint-text)',
        textTransform: 'uppercase',
      }}>
        {label}
      </span>
      <span style={{
        fontSize: '0.75rem',
        fontFamily: 'var(--font-mono)',
        color: 'var(--text)',
      }}>
        {value}
      </span>
    </span>
  );
}
