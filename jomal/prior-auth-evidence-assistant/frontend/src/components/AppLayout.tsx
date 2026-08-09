import React from 'react';
import { useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuth } from '../context/AuthContext';

const TITLES: Record<string, string> = {
    '/cases': 'Case Management',
    '/cases/new': 'New Case',
    '/nurse-review': 'Nurse Review Queue',
    '/admin': 'Admin Dashboard',
    '/admin/policies': 'Policy Management',
    '/admin/users': 'User Management',
};

const pageTitleFor = (pathname: string): string => TITLES[pathname] || 'PA Evidence Assistant';

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { user, logout } = useAuth();
    const location = useLocation();

    const initials = user?.username ? user.username.slice(0, 2).toUpperCase() : '—';

    return (
        <div className="app-shell">
            <Sidebar role={user?.role ?? null} />
            <div className="app-main">
                <header className="topbar">
                    <div className="topbar-crumb">
                        <span>PA Evidence Assistant</span>
                        <span aria-hidden="true">/</span>
                        <strong>{pageTitleFor(location.pathname)}</strong>
                    </div>
                    <div className="topbar-user">
                        <span className="text-secondary" style={{ fontSize: 13.5 }}>
                            {user?.username}
                        </span>
                        <div className="avatar" title={user?.username}>
                            {initials}
                        </div>
                        <button className="btn btn-ghost btn-sm" onClick={logout}>
                            Sign out
                        </button>
                    </div>
                </header>
                <main className="page">{children}</main>
            </div>
        </div>
    );
};

export default AppLayout;
