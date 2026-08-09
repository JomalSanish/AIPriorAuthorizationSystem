import type { FC } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute, { landingPathForRole } from './components/ProtectedRoute';
import Login from './pages/Login';
import PolicyManagement from './pages/PolicyManagement';
import CaseManagement from './pages/CaseManagement';
import NewCase from './pages/NewCase';
import PlaceholderPage from './pages/PlaceholderPage';

/** Sends an already-authenticated visitor away from /login and / to their landing page. */
const RootRedirect: FC = () => {
    const { user, initializing } = useAuth();
    if (initializing) return null;
    return <Navigate to={user ? landingPathForRole(user.role) : '/login'} replace />;
};

function App() {
    return (
        <Router>
            <AuthProvider>
                <Routes>
                    <Route path="/login" element={<Login />} />

                    <Route
                        path="/cases"
                        element={
                            <ProtectedRoute roles={['intake', 'admin']}>
                                <CaseManagement />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/cases/new"
                        element={
                            <ProtectedRoute roles={['intake']}>
                                <NewCase />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/nurse-review"
                        element={
                            <ProtectedRoute roles={['nurse', 'admin']}>
                                <PlaceholderPage
                                    eyebrow="Nurse Review"
                                    title="Review Queue"
                                    description="Metadata-only queue with case locking. Evidence and documents unlock only after a case is claimed."
                                    phase="Phase 6"
                                />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/admin"
                        element={
                            <ProtectedRoute roles={['admin']}>
                                <PlaceholderPage
                                    eyebrow="Administration"
                                    title="Admin Dashboard"
                                    description="Nurse workload, case throughput, and the chronological audit log across the system."
                                    phase="Phase 7"
                                />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/admin/policies"
                        element={
                            <ProtectedRoute roles={['admin']}>
                                <PolicyManagement />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/admin/users"
                        element={
                            <ProtectedRoute roles={['admin']}>
                                <PlaceholderPage
                                    eyebrow="Administration"
                                    title="User Management"
                                    description="Create, deactivate, and reassign roles for Intake, Nurse, and Admin accounts."
                                    phase="Phase 7"
                                />
                            </ProtectedRoute>
                        }
                    />

                    <Route path="/" element={<RootRedirect />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </AuthProvider>
        </Router>
    );
}

export default App;
