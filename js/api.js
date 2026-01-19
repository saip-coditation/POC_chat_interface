/**
 * API Client for Django Backend
 * Handles all API communication with the Django REST Framework backend
 */

const API = {
    // Base API URL - pointing to Django backend
    baseUrl: 'http://localhost:8000/api',

    // JWT tokens (stored in memory for security)
    accessToken: null,
    refreshToken: null,

    /**
     * Platform configurations (for UI display)
     */
    platformConfig: {
        stripe: {
            name: 'Stripe',
            icon: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M13.976 9.15c-2.172-.806-3.356-1.426-3.356-2.409 0-.831.683-1.305 1.901-1.305 2.227 0 4.515.858 6.09 1.631l.89-5.494C18.252.975 15.697 0 12.165 0 9.667 0 7.589.654 6.104 1.872 4.56 3.147 3.757 4.992 3.757 7.218c0 4.039 2.467 5.76 6.476 7.219 2.585.92 3.445 1.574 3.445 2.583 0 .98-.84 1.545-2.354 1.545-1.875 0-4.965-.921-6.99-2.109l-.9 5.555C5.175 22.99 8.385 24 11.714 24c2.641 0 4.843-.624 6.328-1.813 1.664-1.305 2.525-3.236 2.525-5.732 0-4.128-2.524-5.851-6.591-7.305z"/></svg>`,
            helpUrl: 'https://stripe.com/docs/keys',
            description: 'Enter your Stripe Secret Key (starts with sk_)'
        },
        zoho: {
            name: 'Zoho CRM',
            icon: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>`,
            helpUrl: 'https://api-console.zoho.com/',
            description: 'Enter your Zoho Refresh Token'
        },
        github: {
            name: 'GitHub',
            icon: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>`,
            helpUrl: 'https://github.com/settings/tokens',
            description: 'Enter your Personal Access Token'
        }
    },

    /**
     * Initialize API - load tokens from storage
     */
    init() {
        const tokens = sessionStorage.getItem('databridge_tokens');
        if (tokens) {
            try {
                const parsed = JSON.parse(tokens);
                API.accessToken = parsed.access;
                API.refreshToken = parsed.refresh;
            } catch (e) {
                console.warn('Failed to parse stored tokens');
            }
        }
    },

    /**
     * Save tokens to session storage
     */
    saveTokens(tokens) {
        API.accessToken = tokens.access;
        API.refreshToken = tokens.refresh;
        sessionStorage.setItem('databridge_tokens', JSON.stringify(tokens));
    },

    /**
     * Clear tokens
     */
    clearTokens() {
        API.accessToken = null;
        API.refreshToken = null;
        sessionStorage.removeItem('databridge_tokens');
    },

    /**
     * Make authenticated API request
     */
    async request(endpoint, options = {}) {
        const url = `${API.baseUrl}${endpoint}`;

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        // Add auth header if we have a token
        if (API.accessToken) {
            headers['Authorization'] = `Bearer ${API.accessToken}`;
        }

        try {
            let response = await fetch(url, {
                ...options,
                headers
            });

            // If 401, try to refresh token
            if (response.status === 401 && API.refreshToken) {
                const refreshed = await API.refreshAccessToken();
                if (refreshed) {
                    // Retry with new token
                    headers['Authorization'] = `Bearer ${API.accessToken}`;
                    response = await fetch(url, { ...options, headers });
                }
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || data.detail || 'Request failed');
            }

            return data;

        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    },

    /**
     * Refresh access token
     */
    async refreshAccessToken() {
        try {
            const response = await fetch(`${API.baseUrl}/auth/refresh/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh: API.refreshToken })
            });

            if (!response.ok) {
                API.clearTokens();
                return false;
            }

            const data = await response.json();
            API.accessToken = data.access;
            if (data.refresh) {
                API.refreshToken = data.refresh;
            }
            API.saveTokens({ access: API.accessToken, refresh: API.refreshToken });
            return true;

        } catch (error) {
            console.error('Token refresh failed:', error);
            API.clearTokens();
            return false;
        }
    },

    /**
     * Login user
     */
    async login(email, password) {
        try {
            const response = await fetch(`${API.baseUrl}/auth/login/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success && data.tokens) {
                API.saveTokens(data.tokens);
                return {
                    success: true,
                    user: data.user
                };
            }

            return {
                success: false,
                error: data.errors?.non_field_errors?.[0] || data.error || 'Login failed'
            };

        } catch (error) {
            console.error('Login error:', error);
            return {
                success: false,
                error: 'Connection failed. Please check if the server is running.'
            };
        }
    },

    /**
     * Register user
     */
    async register(email, password, firstName = '', lastName = '') {
        try {
            const response = await fetch(`${API.baseUrl}/auth/register/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email,
                    password,
                    password_confirm: password,
                    first_name: firstName,
                    last_name: lastName
                })
            });

            const data = await response.json();

            if (data.success && data.tokens) {
                API.saveTokens(data.tokens);
                return {
                    success: true,
                    user: data.user
                };
            }

            return {
                success: false,
                error: data.errors?.email?.[0] || data.error || 'Registration failed'
            };

        } catch (error) {
            console.error('Registration error:', error);
            return {
                success: false,
                error: 'Connection failed. Please check if the server is running.'
            };
        }
    },

    /**
     * Logout user
     */
    async logout() {
        try {
            if (API.refreshToken) {
                await API.request('/auth/logout/', {
                    method: 'POST',
                    body: JSON.stringify({ refresh: API.refreshToken })
                });
            }
        } catch (error) {
            console.warn('Logout request failed:', error);
        } finally {
            API.clearTokens();
        }
    },

    /**
     * Get current user profile
     */
    async getProfile() {
        return await API.request('/auth/me/');
    },

    /**
     * List connected platforms
     */
    async listPlatforms() {
        return await API.request('/platforms/');
    },

    /**
     * Connect a platform
     */
    async connectPlatform(platform, apiKey) {
        return await API.request('/platforms/connect/', {
            method: 'POST',
            body: JSON.stringify({ platform, api_key: apiKey })
        });
    },

    /**
     * Disconnect a platform
     */
    async disconnectPlatform(platformId) {
        return await API.request(`/platforms/${platformId}/`, {
            method: 'DELETE'
        });
    },

    /**
     * Exchange Zoho authorization code for refresh token and connect
     */
    async exchangeZohoCode(authorizationCode, clientId = null, clientSecret = null) {
        return await API.request('/platforms/zoho/exchange-code/', {
            method: 'POST',
            body: JSON.stringify({
                code: authorizationCode,
                client_id: clientId,
                client_secret: clientSecret
            })
        });
    },

    /**
     * Reverify platform credentials
     */
    async reverifyPlatform(platformId, apiKey) {
        return await API.request(`/platforms/${platformId}/reverify/`, {
            method: 'POST',
            body: JSON.stringify({ api_key: apiKey })
        });
    },

    /**
     * Process a natural language query
     */
    async processQuery(query, platform = '') {
        return await API.request('/queries/process/', {
            method: 'POST',
            body: JSON.stringify({ query, platform })
        });
    },

    /**
     * Get query history
     */
    async getQueryHistory() {
        return await API.request('/queries/history/');
    },

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!API.accessToken;
    }
};

// Initialize API on load
API.init();

// Make API globally available
window.API = API;
