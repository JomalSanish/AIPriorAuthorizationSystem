import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { IconAlert, IconCheckCircle } from '../components/icons';

interface Policy {
    id: string;
    name: string;
}

interface Metadata {
    member_id: string;
    provider_id: string;
    cpt_code: string;
    icd_code: string;
    service_type: string;
}

const NewCase: React.FC = () => {
    const navigate = useNavigate();
    const [policies, setPolicies] = useState<Policy[]>([]);
    const [selectedPolicy, setSelectedPolicy] = useState('');
    const [caseId, setCaseId] = useState<string | null>(null);

    const [files, setFiles] = useState<File[]>([]);
    // Tracks whether the currently-selected files have already been uploaded
    // for this case draft, so retrying "Extract Metadata" after a transient
    // failure re-runs extraction instead of re-uploading (and duplicating)
    // the same documents.
    const [documentsUploaded, setDocumentsUploaded] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [extracting, setExtracting] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const [metadata, setMetadata] = useState<Metadata>({
        member_id: '',
        provider_id: '',
        cpt_code: '',
        icd_code: '',
        service_type: '',
    });
    const [hasMetadata, setHasMetadata] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Set to true only after the backend reports every document failed
    // OCR/extraction (409 response). Controls whether the confirmation
    // checkbox is shown at all.
    const [needsFailureConfirmation, setNeedsFailureConfirmation] = useState(false);
    // The checkbox's own value — always starts unchecked, so the intake
    // user has to take a deliberate action to proceed (FR-013a). This must
    // never be set to true programmatically.
    const [confirmed, setConfirmed] = useState(false);

    useEffect(() => {
        api.get('/api/policies/').then((res) => setPolicies(res.data)).catch(console.error);
    }, []);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            setFiles(Array.from(e.target.files));
            setDocumentsUploaded(false);
        }
    };

    const handleProcess = async () => {
        if (!selectedPolicy || files.length === 0) {
            setError('Please select a policy and attach at least one document.');
            return;
        }

        setError(null);
        let currentCaseId = caseId;

        try {
            // 1. Create draft if not exists
            if (!currentCaseId) {
                const caseRes = await api.post('/api/cases/', { policy_id: selectedPolicy });
                currentCaseId = caseRes.data.id;
                setCaseId(currentCaseId);
            }

            // 2. Upload documents — only once per selected file set. Retrying
            // this step after an extraction failure must not re-upload (and
            // duplicate) documents that already made it to the case.
            if (!documentsUploaded) {
                setUploading(true);
                const formData = new FormData();
                files.forEach((f) => formData.append('files', f));
                await api.post(`/api/cases/${currentCaseId}/documents`, formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });
                setDocumentsUploaded(true);
                setUploading(false);
            }

            setExtracting(true);

            // 3. Extract metadata
            const metaRes = await api.post(`/api/cases/${currentCaseId}/extract-metadata`);
            setMetadata({
                member_id: metaRes.data.member_id || '',
                provider_id: metaRes.data.provider_id || '',
                cpt_code: metaRes.data.cpt_code || '',
                icd_code: metaRes.data.icd_code || '',
                service_type: metaRes.data.service_type || '',
            });
            setHasMetadata(true);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'An error occurred during processing.');
        } finally {
            setUploading(false);
            setExtracting(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!caseId) return;

        setSubmitting(true);
        setError(null);
        try {
            await api.post(`/api/cases/${caseId}/submit`, {
                member_id: metadata.member_id,
                provider_id: metadata.provider_id,
                cpt_code: metadata.cpt_code || undefined,
                icd_code: metadata.icd_code || undefined,
                service_type: metadata.service_type || undefined,
                confirmed_all_failed: confirmed,
            });
            navigate('/cases');
        } catch (err: any) {
            if (err.response?.status === 409) {
                setError(err.response.data.detail);
                // Reveal the confirmation checkbox — but leave it unchecked.
                // The user must explicitly opt in before resubmitting.
                setNeedsFailureConfirmation(true);
                setConfirmed(false);
            } else {
                setError(err.response?.data?.detail || err.message || 'Submit failed.');
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <>
            <div className="page-header">
                <div>
                    <p className="page-eyebrow">Intake</p>
                    <h1 className="page-title">New Case</h1>
                    <p className="page-subtitle">
                        Upload case documents to extract details and submit for prior authorization.
                    </p>
                </div>
            </div>

            <div className="card card-pad section-gap">
                <div className="card-header">
                    <div>
                        <div className="card-title">1. Document upload</div>
                    </div>
                </div>

                <div className="stack" style={{ maxWidth: 560 }}>
                    <div className="field">
                        <label className="label">Applicable policy</label>
                        <select
                            className="input"
                            value={selectedPolicy}
                            onChange={(e) => setSelectedPolicy(e.target.value)}
                            disabled={!!caseId}
                        >
                            <option value="">Select a policy…</option>
                            {policies.map((p) => (
                                <option key={p.id} value={p.id}>
                                    {p.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="field">
                        <label className="label">Case documents</label>
                        <input
                            type="file"
                            className="file-input"
                            multiple
                            onChange={handleFileChange}
                            accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png,.tiff"
                        />
                        <div className="text-muted" style={{ marginTop: 8, fontSize: 13 }}>
                            Selected {files.length} file(s)
                            {documentsUploaded && ' — already uploaded to this case'}
                        </div>
                    </div>

                    {!hasMetadata && (
                        <button
                            className="btn btn-primary"
                            onClick={handleProcess}
                            disabled={uploading || extracting || files.length === 0 || !selectedPolicy}
                            style={{ alignSelf: 'flex-start' }}
                        >
                            {(uploading || extracting) && <span className="spinner" />}
                            {uploading ? 'Uploading…' : extracting ? 'Extracting metadata…' : 'Extract metadata'}
                        </button>
                    )}
                </div>

                {error && (
                    <div className="banner banner-error" style={{ marginTop: 18, maxWidth: 560 }}>
                        <IconAlert width={16} height={16} />
                        <span>{error}</span>
                    </div>
                )}
            </div>

            {hasMetadata && (
                <div className="card card-pad">
                    <div className="card-header">
                        <div>
                            <div className="card-title">2. Review metadata</div>
                            <p className="card-desc">Review and correct auto-extracted identifiers before submission.</p>
                        </div>
                    </div>

                    <form onSubmit={handleSubmit} className="stack" style={{ maxWidth: 560 }}>
                        <div className="grid-2">
                            <div className="field">
                                <label className="label">Member ID</label>
                                <input
                                    className="input"
                                    value={metadata.member_id}
                                    onChange={(e) => setMetadata({ ...metadata, member_id: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="field">
                                <label className="label">Provider ID</label>
                                <input
                                    className="input"
                                    value={metadata.provider_id}
                                    onChange={(e) => setMetadata({ ...metadata, provider_id: e.target.value })}
                                    required
                                />
                            </div>
                        </div>

                        <div className="grid-2">
                            <div className="field">
                                <label className="label">CPT code</label>
                                <input
                                    className="input"
                                    value={metadata.cpt_code}
                                    onChange={(e) => setMetadata({ ...metadata, cpt_code: e.target.value })}
                                />
                            </div>
                            <div className="field">
                                <label className="label">ICD-10 code</label>
                                <input
                                    className="input"
                                    value={metadata.icd_code}
                                    onChange={(e) => setMetadata({ ...metadata, icd_code: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="field">
                            <label className="label">Service type</label>
                            <input
                                className="input"
                                value={metadata.service_type}
                                onChange={(e) => setMetadata({ ...metadata, service_type: e.target.value })}
                            />
                        </div>

                        {needsFailureConfirmation && (
                            <div className="banner banner-error" style={{ alignItems: 'center' }}>
                                <input
                                    type="checkbox"
                                    id="confirm-failed"
                                    checked={confirmed}
                                    onChange={(e) => setConfirmed(e.target.checked)}
                                    required
                                    style={{ marginTop: 1 }}
                                />
                                <label htmlFor="confirm-failed">
                                    I confirm that I want to submit this case despite every document failing
                                    extraction.
                                </label>
                            </div>
                        )}

                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={submitting || (needsFailureConfirmation && !confirmed)}
                            style={{ alignSelf: 'flex-start', marginTop: 16 }}
                        >
                            {submitting ? <span className="spinner" /> : <IconCheckCircle width={15} height={15} />}
                            {submitting ? 'Submitting…' : 'Submit case'}
                        </button>
                    </form>
                </div>
            )}
        </>
    );
};

export default NewCase;
