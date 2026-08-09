import React from 'react';
import { IconInbox } from '../components/icons';

interface PlaceholderPageProps {
    eyebrow: string;
    title: string;
    description: string;
    phase: string;
}

const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ eyebrow, title, description, phase }) => {
    return (
        <>
            <div className="page-header">
                <div>
                    <p className="page-eyebrow">{eyebrow}</p>
                    <h1 className="page-title">{title}</h1>
                    <p className="page-subtitle">{description}</p>
                </div>
            </div>

            <div className="card">
                <div className="empty-state">
                    <div className="empty-state-icon">
                        <IconInbox width={20} height={20} color="var(--text-muted)" />
                    </div>
                    <div className="empty-state-title">Coming in {phase}</div>
                    <p style={{ maxWidth: '38ch', margin: '0 auto' }}>
                        This screen ships in a later phase of the spec. Policy Management, on the
                        left, is fully wired up for this build.
                    </p>
                </div>
            </div>
        </>
    );
};

export default PlaceholderPage;
