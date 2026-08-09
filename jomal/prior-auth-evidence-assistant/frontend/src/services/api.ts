import axios, { type InternalAxiosRequestConfig } from 'axios';

// Memory store for tokens per FR-043c — never persisted to
// localStorage/sessionStorage, so a hard refresh always requires re-login.
let accessToken: string | null = null;
let refreshToken: string | null = null;

export const setTokens = (access: string, refresh: string) => {
    accessToken = access;
    refreshToken = refresh;
};

export const clearTokens = () => {
    accessToken = null;
    refreshToken = null;
};

export const hasAccessToken = () => accessToken !== null;

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
const api = axios.create({
    baseURL: BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor to attach access token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    if (accessToken && config.headers) {
        config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
});

// Response interceptor for silent refresh
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // Never attempt a silent refresh for the login endpoint itself —
        // a 401 there means bad credentials, not an expired session.
        const isLoginRequest = originalRequest?.url?.includes('/api/auth/login');

        if (error.response?.status === 401 && !originalRequest._retry && !isLoginRequest) {
            originalRequest._retry = true;

            if (refreshToken) {
                try {
                    const response = await axios.post(`${BASE_URL}/api/auth/refresh`, {
                        refresh_token: refreshToken,
                    });

                    if (response.data?.access_token) {
                        accessToken = response.data.access_token;
                        if (response.data.refresh_token) {
                            refreshToken = response.data.refresh_token;
                        }

                        originalRequest.headers.Authorization = `Bearer ${accessToken}`;
                        return api(originalRequest);
                    }
                } catch (refreshError) {
                    // Refresh failed, clear tokens and redirect to login
                    clearTokens();
                    if (!window.location.pathname.startsWith('/login')) {
                        window.location.href = '/login';
                    }
                    return Promise.reject(refreshError);
                }
            } else if (!window.location.pathname.startsWith('/login')) {
                // No refresh token available and we're not already on /login
                clearTokens();
                window.location.href = '/login';
            }
        }

        return Promise.reject(error);
    }
);

export default api;
