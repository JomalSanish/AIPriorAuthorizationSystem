import React from 'react';
import { IconAlert } from './icons';

interface CaseCardProps {
    caseId: string;
    serviceType?: string;
    status: string;
    slaStartAt?: string;
    createdAt: string;
}

const getStatusBadge = (status: string) => {
    switch (status) {
        case 'draft':
            return (
                <span className="badge badge-neutral">
                    <span className="badge-dot" /> Draft
                </span>
            );
        case 'processing':
            return (
                <span className="badge badge-primary">
                    <span className="badge-dot" /> Processing
                </span>
            );
        case 'pending_nurse_review':
            return (
                <span className="badge badge-warning">
                    <span className="badge-dot" /> Pending review
                </span>
            );
        case 'accepted':
            return (
                <span className="badge badge-success">
                    <span className="badge-dot" /> Accepted
                </span>
            );
        case 'rejected':
            return (
                <span className="badge badge-danger">
                    <span className="badge-dot" /> Rejected
                </span>
            );
        case 'error':
            return (
                <span className="badge badge-danger">
                    <span className="badge-dot" /> Error
                </span>
            );
        // Set on cases the Admin has edited after a Nurse decision — routed
        // straight back to the Nurse Review queue with this flag (FR-032).
        case 're_verification_required':
            return (
                <span className="badge badge-warning">
                    <span className="badge-dot" /> Re-verification
                </span>
            );
        default:
            return (
                <span className="badge badge-neutral">
                    <span className="badge-dot" /> {status}
                </span>
            );
    }
};

const formatTime = (iso?: string) => {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return '—';
    }
};

export const CaseCard: React.FC<CaseCardProps> = ({ caseId, serviceType, status, slaStartAt, createdAt }) => {
    return (
        <div className="card card-pad case-card">
            <div className="case-card-header">
                <div>
                    <div className="case-field-label">Case ID</div>
                    <div className="case-id">{caseId.split('-')[0]}…</div>
                </div>
                {getStatusBadge(status)}
            </div>

            <div className="grid-2">
                <div>
                    <div className="case-field-label">Service type</div>
                    <div className="case-field-value">{serviceType || 'Not specified'}</div>
                </div>
                <div>
                    <div className="case-field-label">Submitted</div>
                    <div className="case-field-value">{formatTime(createdAt)}</div>
                </div>
            </div>

            {slaStartAt && (
                <div className="sla-banner">
                    <IconAlert width={15} height={15} />
                    <span>SLA started {formatTime(slaStartAt)}</span>
                </div>
            )}
        </div>
    );
};
