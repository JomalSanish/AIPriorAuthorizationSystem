import React, { useEffect, useRef, useState } from 'react';
import api from '../services/api';
import { IconAlert, IconCheckCircle, IconPolicy, IconUpload } from '../components/icons';

interface PolicyRequirement {
    id: string;
    text: string;
}

interface PolicyListItem {
    id: string;
    name: string;
    description?: string | null;
    is_active?: boolean;
    created_at?: string;
    document_count?: number;
    requirement_count?: number;
}

const formatDate = (iso?: string) => {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    } catch {
        return '—';
    }
};

const PolicyManagement: React.FC = () => {
    const [policies, setPolicies] = useState<PolicyListItem[]>([]);
    const [policiesLoading, setPoliciesLoading] = useState(true);
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    const [requirements, setRequirements] = useState<PolicyRequirement[]>([]);
    const [deactivatingId, setDeactivatingId] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        fetchPolicies();
    }, []);

    const fetchPolicies = async () => {
        setPoliciesLoading(true);
        try {
            const res = await api.get('/api/policies');
            setPolicies(res.data);
        } catch (e) {
            console.error('Failed to fetch policies', e);
        } finally {
            setPoliciesLoading(false);
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file || !name) {
            setMessage({ type: 'error', text: 'Please provide a policy name and a document.' });
            return;
        }

        setLoading(true);
        setMessage(null);
        setRequirements([]);

        const formData = new FormData();
        formData.append('name', name);
        formData.append('description', description);
        formData.append('file', file);

        try {
            const res = await api.post('/api/policies', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            setMessage({
                type: 'success',
                text: `"${res.data.name}" indexed — ${res.data.chunks_indexed} chunks embedded, ${res.data.requirements.length} requirements extracted.`,
            });
            setRequirements(res.data.requirements || []);
            setName('');
            setDescription('');
            setFile(null);
            if (fileInputRef.current) fileInputRef.current.value = '';
            fetchPolicies();
        } catch (err: any) {
            setMessage({ type: 'error', text: err.response?.data?.detail || err.message || 'Upload failed.' });
        } finally {
            setLoading(false);
        }
    };

    const handleDeactivate = async (id: string, policyName: string) => {
        if (!window.confirm(`Deactivate "${policyName}"? It will be removed from the case-creation dropdown, but existing cases are unaffected.`)) {
            return;
        }
        setDeactivatingId(id);
        try {
            await api.patch(`/api/policies/${id}`);
            fetchPolicies();
        } catch (err) {
            console.error('Failed to deactivate policy', err);
        } finally {
            setDeactivatingId(null);
        }
    };

    return (
        <>
            <div className="page-header">
                <div>
                    <p className="page-eyebrow">Administration</p>
                    <h1 className="page-title">Policy Management</h1>
                    <p className="page-subtitle">
                        Upload payer policy documents to extract evidence requirements and index
                        them for hybrid retrieval during case review.
                    </p>
                </div>
            </div>

            <div className="card card-pad section-gap">
                <div className="card-header">
                    <div>
                        <div className="card-title">Upload new policy</div>
                        <p className="card-desc">PDF, DOCX, TXT, or Markdown. Ingestion runs automatically after upload.</p>
                    </div>
                </div>

                <form onSubmit={handleUpload} className="stack" style={{ maxWidth: 560 }}>
                    <div className="grid-2">
                        <div className="field">
                            <label className="label" htmlFor="policy-name">
                                Policy name
                            </label>
                            <input
                                id="policy-name"
                                type="text"
                                className="input"
                                placeholder="e.g. Lumbar MRI Policy"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                required
                            />
                        </div>
                        <div className="field">
                            <label className="label" htmlFor="policy-description">
                                Description <span className="label-hint">(optional)</span>
                            </label>
                            <input
                                id="policy-description"
                                type="text"
                                className="input"
                                placeholder="Short internal note"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                            />
                        </div>
                    </div>

                    <div className="field">
                        <label className="label" htmlFor="policy-file">
                            Policy document
                        </label>
                        <input
                            id="policy-file"
                            ref={fileInputRef}
                            type="file"
                            className="file-input"
                            onChange={handleFileChange}
                            accept=".pdf,.docx,.txt,.md"
                            required
                        />
                    </div>

                    <button type="submit" className="btn btn-primary" disabled={loading} style={{ alignSelf: 'flex-start' }}>
                        {loading ? <span className="spinner" /> : <IconUpload width={15} height={15} />}
                        {loading ? 'Processing…' : 'Upload & ingest'}
                    </button>
                </form>

                {message && (
                    <div className={`banner ${message.type === 'success' ? 'banner-success' : 'banner-error'}`} style={{ marginTop: 18 }}>
                        {message.type === 'success' ? <IconCheckCircle width={16} height={16} /> : <IconAlert width={16} height={16} />}
                        <span>{message.text}</span>
                    </div>
                )}

                {requirements.length > 0 && (
                    <div style={{ marginTop: 16, padding: 16, background: 'var(--surface-alt)', borderRadius: 'var(--radius)' }}>
                        <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 10 }}>Extracted requirements</div>
                        <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {requirements.map((r) => (
                                <li key={r.id} style={{ fontSize: 13.75, color: 'var(--text-secondary)' }}>
                                    {r.text}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>

            <div className="card card-pad">
                <div className="card-header">
                    <div>
                        <div className="card-title">Policy registry</div>
                        <p className="card-desc">All policies ever uploaded, active and inactive.</p>
                    </div>
                </div>

                <div className="table-wrap">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Status</th>
                                <th>Requirements</th>
                                <th>Documents</th>
                                <th>Uploaded</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {policiesLoading && (
                                <tr>
                                    <td colSpan={6} className="table-empty">
                                        <span className="spinner spinner-dark" style={{ margin: '0 auto' }} />
                                    </td>
                                </tr>
                            )}

                            {!policiesLoading && policies.length === 0 && (
                                <tr>
                                    <td colSpan={6}>
                                        <div className="empty-state">
                                            <div className="empty-state-icon">
                                                <IconPolicy width={20} height={20} color="var(--text-muted)" />
                                            </div>
                                            <div className="empty-state-title">No policies yet</div>
                                            <p>Upload your first policy document above to get started.</p>
                                        </div>
                                    </td>
                                </tr>
                            )}

                            {!policiesLoading &&
                                policies.map((p) => (
                                    <tr key={p.id}>
                                        <td className="table-name">{p.name}</td>
                                        <td>
                                            {p.is_active === false ? (
                                                <span className="badge badge-neutral">
                                                    <span className="badge-dot" /> Inactive
                                                </span>
                                            ) : (
                                                <span className="badge badge-success">
                                                    <span className="badge-dot" /> Active
                                                </span>
                                            )}
                                        </td>
                                        <td className="text-secondary">{p.requirement_count ?? '—'}</td>
                                        <td className="text-secondary">{p.document_count ?? '—'}</td>
                                        <td className="text-secondary">{formatDate(p.created_at)}</td>
                                        <td>
                                            {p.is_active !== false && (
                                                <button
                                                    className="btn btn-danger btn-sm"
                                                    onClick={() => handleDeactivate(p.id, p.name)}
                                                    disabled={deactivatingId === p.id}
                                                >
                                                    {deactivatingId === p.id && <span className="spinner" style={{ borderTopColor: 'var(--danger)', borderColor: 'rgba(174,42,32,0.25)' }} />}
                                                    Deactivate
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </>
    );
};

export default PolicyManagement;
