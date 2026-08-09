import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { IconAlert, IconUpload } from '../components/icons';
import { CaseCard } from '../components/CaseCard';
import SearchBar, { type CaseSearchResult } from '../components/SearchBar';

interface CaseItem {
    id: string;
    policy_name: string;
    service_type?: string;
    status: string;
    sla_start_at?: string;
    created_at: string;
}

const CaseManagement: React.FC = () => {
    const [cases, setCases] = useState<CaseItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [highlightId, setHighlightId] = useState<string | null>(null);
    const navigate = useNavigate();

    useEffect(() => {
        fetchCases();
    }, []);

    const fetchCases = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.get('/api/cases');
            setCases(res.data);
        } catch (e: any) {
            console.error('Failed to fetch cases', e);
            setError(e.response?.data?.detail || 'Could not load cases. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleSearchSelect = (result: CaseSearchResult) => {
        // Highlight the matching case in the list so the user can find it
        setHighlightId(result.case_id);
        // Scroll to the card if it's rendered
        setTimeout(() => {
            const el = document.getElementById(`case-card-${result.case_id}`);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    };

    return (
        <>
            <div className="page-header">
                <div>
                    <p className="page-eyebrow">Case Management</p>
                    <h1 className="page-title">Prior Auth Cases</h1>
                    <p className="page-subtitle">Manage and track prior authorization requests.</p>
                </div>
                <button className="btn btn-primary" onClick={() => navigate('/cases/new')}>
                    New Case
                </button>
            </div>

            <div className="card card-pad">
                <div className="card-header" style={{ flexWrap: 'wrap', gap: 12 }}>
                    <div>
                        <div className="card-title">All cases</div>
                        <p className="card-desc">History of all cases submitted in the system.</p>
                    </div>
                    {/* T049 — NLP Case Search SearchBar */}
                    <SearchBar
                        placeholder="Search cases by type, code, or member…"
                        onSelect={handleSearchSelect}
                    />
                </div>

                {error && (
                    <div className="banner banner-error" style={{ marginBottom: 16 }}>
                        <IconAlert width={16} height={16} />
                        <span>{error}</span>
                    </div>
                )}

                {loading ? (
                    <div style={{ padding: 40, textAlign: 'center' }}>
                        <span className="spinner spinner-dark" />
                    </div>
                ) : cases.length === 0 ? (
                    !error && (
                        <div className="empty-state">
                            <div className="empty-state-icon">
                                <IconUpload width={20} height={20} color="var(--text-muted)" />
                            </div>
                            <div className="empty-state-title">No cases yet</div>
                            <p>Click "New Case" to submit your first prior authorization request.</p>
                        </div>
                    )
                ) : (
                    <div className="case-grid">
                        {cases.map((c) => (
                            <div
                                key={c.id}
                                id={`case-card-${c.id}`}
                                style={{
                                    outline: highlightId === c.id ? '2px solid var(--primary)' : 'none',
                                    borderRadius: 'var(--radius)',
                                    transition: 'outline 0.3s',
                                }}
                            >
                                <CaseCard
                                    caseId={c.id}
                                    serviceType={c.service_type || c.policy_name}
                                    status={c.status}
                                    slaStartAt={c.sla_start_at}
                                    createdAt={c.created_at}
                                />
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </>
    );
};

export default CaseManagement;
