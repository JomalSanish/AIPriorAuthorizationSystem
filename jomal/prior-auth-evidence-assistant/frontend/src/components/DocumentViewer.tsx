/**
 * DocumentViewer component — T065
 * List sidebar + inline viewer for case documents.
 * PDF: browser native <object> embed. Text/other: pre-formatted text.
 */
import React, { useState, useEffect } from 'react';
import api from '../services/api';

interface DocRecord {
  id: string;
  original_filename: string;
  file_type: string;
  ocr_status: string;
  extracted_text_length: number;
}

interface Props {
  caseId: string;
  documents: DocRecord[];
}

const OcrBadge: React.FC<{ status: string }> = ({ status }) => {
  const config: Record<string, { label: string; bg: string; color: string }> = {
    completed: { label: 'Extracted', bg: 'var(--success-soft)', color: 'var(--success)' },
    failed: { label: 'Extraction Failed', bg: 'var(--danger-soft)', color: 'var(--danger)' },
    not_needed: { label: 'Text', bg: 'var(--surface-alt)', color: 'var(--text-secondary)' },
  };
  const c = config[status] ?? config.not_needed;
  return (
    <span
      style={{
        padding: '2px 8px',
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
};

const DocumentViewer: React.FC<Props> = ({ caseId, documents }) => {
  const [selectedId, setSelectedId] = useState<string | null>(
    documents.length > 0 ? documents[0].id : null
  );
  const [docUrl, setDocUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const selectedDoc = documents.find(d => d.id === selectedId);

  useEffect(() => {
    if (!selectedId) return;

    let objectUrl: string | null = null;
    setLoading(true);
    setDocUrl(null);

    api
      .get(`/api/cases/${caseId}/documents/${selectedId}/download`, {
        responseType: 'blob',
      })
      .then(res => {
        objectUrl = URL.createObjectURL(res.data);
        setDocUrl(objectUrl);
      })
      .catch(() => setDocUrl(null))
      .finally(() => setLoading(false));

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [caseId, selectedId]);

  if (documents.length === 0) {
    return (
      <div
        style={{
          padding: 32,
          textAlign: 'center',
          color: 'var(--text-muted)',
          fontSize: 14,
        }}
      >
        No documents attached to this case.
      </div>
    );
  }

  const isPdf = selectedDoc?.file_type?.includes('pdf');

  return (
    <div style={{ display: 'flex', gap: 16, height: 600 }}>
      {/* Sidebar */}
      <div
        style={{
          width: 220,
          flexShrink: 0,
          background: 'var(--surface-alt)',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
          overflowY: 'auto',
          padding: 8,
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
        }}
      >
        {documents.map(doc => (
          <button
            key={doc.id}
            onClick={() => setSelectedId(doc.id)}
            style={{
              background: selectedId === doc.id ? 'var(--primary-soft)' : 'transparent',
              border: selectedId === doc.id
                ? '1px solid var(--primary-soft-border)'
                : '1px solid transparent',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 10px',
              textAlign: 'left',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              transition: 'background 0.15s',
            }}
          >
            <span
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: selectedId === doc.id ? 'var(--primary)' : 'var(--text)',
                wordBreak: 'break-word',
              }}
            >
              {doc.original_filename}
            </span>
            <OcrBadge status={doc.ocr_status} />
          </button>
        ))}
      </div>

      {/* Viewer */}
      <div
        style={{
          flex: 1,
          background: 'var(--surface)',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {loading && (
          <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Loading document…</div>
        )}
        {!loading && !docUrl && (
          <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>
            Document preview unavailable.
          </div>
        )}
        {!loading && docUrl && isPdf && (
          <object
            data={docUrl}
            type="application/pdf"
            width="100%"
            height="100%"
            style={{ border: 'none' }}
          >
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
              PDF viewer not supported.{' '}
              <a href={docUrl} download={selectedDoc?.original_filename}>
                Download instead
              </a>
            </div>
          </object>
        )}
        {!loading && docUrl && !isPdf && (
          <iframe
            src={docUrl}
            title={selectedDoc?.original_filename}
            width="100%"
            height="100%"
            style={{ border: 'none' }}
          />
        )}
      </div>
    </div>
  );
};

export default DocumentViewer;
