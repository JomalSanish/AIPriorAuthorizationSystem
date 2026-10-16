import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth, type Role } from '../context/AuthContext';
import AppLayout from './AppLayout';

interface ProtectedRouteProps {
    roles?: Role[];
    children: React.ReactNode;
}

const FullScreenLoader: React.FC = () => (
    <div className="full-screen-loader">
        <div className="spinner spinner-dark" style={{ width: 24, height: 24 }} />
    </div>
);

/**
 * Wraps a page element. Redirects unauthenticated users to /login
 * (preserving the intended destination), and unauthorized-but-authenticated
 * users to their own role-appropriate landing page.
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ roles, children }) => {
    const { user, initializing } = useAuth();
    const location = useLocation();

    if (initializing) {
        return <FullScreenLoader />;
    }

    if (!user) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    if (roles && !roles.includes(user.role)) {
        return <Navigate to={landingPathForRole(user.role)} replace />;
    }

    return <AppLayout>{children}</AppLayout>;
};

export const landingPathForRole = (role: Role): string => {
    switch (role) {
        case 'admin':
            return '/admin';
        case 'nurse':
            return '/nurse-review';
        case 'intake':
            return '/cases';
        default:
            return '/login';
    }
};

export default ProtectedRoute;
