import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import api, { clearTokens, hasAccessToken, setTokens } from '../services/api';

export type Role = 'admin' | 'nurse' | 'intake';

interface CurrentUser {
    id: string;
    username: string;
    role: Role;
}

interface AuthContextValue {
    user: CurrentUser | null;
    /** True while the initial session bootstrap (silent refresh + /me) is in flight. */
    initializing: boolean;
    login: (username: string, password: string) => Promise<CurrentUser>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<CurrentUser | null>(null);
    const [initializing, setInitializing] = useState(true);

    const fetchProfile = useCallback(async (): Promise<CurrentUser> => {
        const res = await api.get('/api/auth/me');
        const profile: CurrentUser = {
            id: res.data.id,
            username: res.data.username,
            role: res.data.role,
        };
        setUser(profile);
        return profile;
    }, []);

    useEffect(() => {
        // On hard refresh, tokens (memory-only per FR-043c) are gone, so there is
        // nothing to silently restore. We simply mark initialization complete;
        // ProtectedRoute will redirect to /login as needed.
        if (!hasAccessToken()) {
            setInitializing(false);
            return;
        }
        fetchProfile()
            .catch(() => {
                clearTokens();
                setUser(null);
            })
            .finally(() => setInitializing(false));
    }, [fetchProfile]);

    const login = useCallback(
        async (username: string, password: string) => {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const res = await api.post('/api/auth/login', formData, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            });

            setTokens(res.data.access_token, res.data.refresh_token);
            return fetchProfile();
        },
        [fetchProfile]
    );

    const logout = useCallback(() => {
        clearTokens();
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider value={{ user, initializing, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = (): AuthContextValue => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
    return ctx;
};
