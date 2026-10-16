import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { landingPathForRole } from '../components/ProtectedRoute';
import { IconAlert } from '../components/icons';

const Login: React.FC = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const profile = await login(username, password);
            const from = (location.state as { from?: { pathname?: string } })?.from?.pathname;
            navigate(from || landingPathForRole(profile.role), { replace: true });
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Incorrect username or password.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-shell">
            <section className="auth-panel">
                <div className="auth-panel-brand">
                    <div className="auth-panel-brand-mark">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                            <path
                                d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"
                                stroke="#fff"
                                strokeWidth="1.7"
                                strokeLinejoin="round"
                            />
                            <path d="m9 12.5 2.2 2.2L16 10" stroke="#8fe3d3" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </div>
                    PA Evidence Assistant
                </div>

                <div className="auth-panel-quote">
                    <h2>Evidence review, kept on‑prem and on schedule.</h2>
                    <p>
                        Intake, nurse review, and audit — one workspace for prior authorization
                        decisions, with every inference running locally and every decision traced.
                    </p>
                </div>

                <div className="auth-panel-meta">
                    <div>
                        <strong>Local</strong>
                        inference only
                    </div>
                    <div>
                        <strong>Full</strong>
                        audit trail
                    </div>
                    <div>
                        <strong>Role</strong>
                        gated access
                    </div>
                </div>
            </section>

            <section className="auth-form-side">
                <div className="auth-form-card">
                    <h1 className="auth-form-title">Sign in</h1>
                    <p className="auth-form-subtitle">Use your organization credentials to continue.</p>

                    <form onSubmit={handleLogin} className="stack">
                        <div className="field">
                            <label className="label" htmlFor="username">
                                Username
                            </label>
                            <input
                                id="username"
                                type="text"
                                className="input"
                                autoComplete="username"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                autoFocus
                            />
                        </div>
                        <div className="field">
                            <label className="label" htmlFor="password">
                                Password
                            </label>
                            <input
                                id="password"
                                type="password"
                                className="input"
                                autoComplete="current-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>

                        {error && (
                            <div className="banner banner-error" role="alert">
                                <IconAlert width={16} height={16} />
                                <span>{error}</span>
                            </div>
                        )}

                        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
                            {loading && <span className="spinner" />}
                            {loading ? 'Signing in…' : 'Sign in'}
                        </button>
                    </form>
                </div>
            </section>
        </div>
    );
};

export default Login;
