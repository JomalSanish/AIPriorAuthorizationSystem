import React from 'react';
import { NavLink } from 'react-router-dom';
import type { Role } from '../context/AuthContext';
import { IconAdmin, IconCases, IconNurse, IconPolicy } from './icons';

interface SidebarProps {
    role: Role | null;
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
    `sidebar-link${isActive ? ' active' : ''}`;

const Sidebar: React.FC<SidebarProps> = ({ role }) => {
    if (!role) return null;

    return (
        <aside className="sidebar">
            <div className="sidebar-brand">
                <div className="sidebar-brand-mark">
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
                        <path
                            d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"
                            stroke="#fff"
                            strokeWidth="1.7"
                            strokeLinejoin="round"
                        />
                        <path d="m9 12.5 2.2 2.2L16 10" stroke="#7fd9c9" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </div>
                <div className="sidebar-brand-text">
                    PA Evidence
                    <span>Assistant</span>
                </div>
            </div>

            <nav className="sidebar-nav">
                {(role === 'admin' || role === 'intake') && (
                    <div className="sidebar-section">
                        <div className="sidebar-section-label">Case Management</div>
                        <NavLink to="/cases" className={linkClass}>
                            <IconCases width={17} height={17} />
                            Case Management
                        </NavLink>
                    </div>
                )}

                {(role === 'admin' || role === 'nurse') && (
                    <div className="sidebar-section">
                        <div className="sidebar-section-label">Nurse Review</div>
                        <NavLink to="/nurse-review" className={linkClass}>
                            <IconNurse width={17} height={17} />
                            Review Queue
                        </NavLink>
                    </div>
                )}

                {role === 'admin' && (
                    <div className="sidebar-section">
                        <div className="sidebar-section-label">Administration</div>
                        <NavLink to="/admin" end className={linkClass}>
                            <IconAdmin width={17} height={17} />
                            Admin Dashboard
                        </NavLink>
                        <NavLink to="/admin/policies" className={linkClass}>
                            <IconPolicy width={17} height={17} />
                            Policy Management
                        </NavLink>
                    </div>
                )}
            </nav>

            <div className="sidebar-footer">
                <span className="sidebar-role-pill">
                    <span className="badge-dot" />
                    {role}
                </span>
            </div>
        </aside>
    );
};

export default Sidebar;
