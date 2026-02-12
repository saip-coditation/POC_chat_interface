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
        },
        trello: {
            name: 'Trello',
            icon: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.333 1.333H4.667C2.827 1.333 1.333 2.827 1.333 4.667v14.666c0 1.84 1.494 3.334 3.334 3.334h14.666c1.84 0 3.334-1.494 3.334-3.334V4.667c0-1.84-1.494-3.334-3.334-3.334zM10.667 17.333h-4V5.333h4v12zm8.666-4.666h-4V5.333h4v7.334z"/></svg>`,
            helpUrl: 'https://trello.com/power-ups/admin',
            description: 'Enter your API Key and Token separated by a colon (KEY:TOKEN)'
        },
        salesforce: {
            name: 'Salesforce',
            icon: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M10.006 5a4.5 4.5 0 0 1 4.26 3.052A3.75 3.75 0 0 1 17.97 11.6a3.75 3.75 0 0 1-.469 7.4H5.25a4.35 4.35 0 0 1-.81-8.624A4.5 4.5 0 0 1 10.006 5z"/></svg>`,
            helpUrl: 'https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/',
            description: 'Enter ACCESS_TOKEN:INSTANCE_URL'
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
                console.log('[API] 401 Unauthorized, attempting token refresh...');
                const refreshed = await API.refreshAccessToken();
                if (refreshed) {
                    console.log('[API] Token refreshed successfully, retrying request...');
                    // Retry with new token
                    headers['Authorization'] = `Bearer ${API.accessToken}`;
                    response = await fetch(url, { ...options, headers });
                } else {
                    console.error('[API] Token refresh failed, user needs to log in again');
                    // Redirect to login if refresh fails
                    if (window.location.hash !== '#login') {
                        window.location.hash = '#login';
                        // Show error message
                        if (window.App && window.App.showToast) {
                            window.App.showToast('Your session has expired. Please log in again.', 'error');
                        }
                    }
                }
            }

            // 204 No Content = success with no body (e.g. DELETE)
            if (response.status === 204) {
                return null;
            }

            // Check if response is JSON before parsing
            let data;
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                const text = await response.text();
                throw new Error(`Server error: ${response.status} ${response.statusText}`);
            }

            if (!response.ok) {
                // Handle authentication errors specifically
                if (response.status === 401) {
                    const errorMsg = data.detail || data.error || 'Authentication failed';
                    if (errorMsg.includes('token') || errorMsg.includes('Given token')) {
                        API.clearTokens();
                        // Redirect to login if not already there
                        if (window.location.hash !== '#login') {
                            window.location.hash = '#login';
                            if (window.App && window.App.showToast) {
                                window.App.showToast('Your session has expired. Please log in again.', 'error');
                            }
                        }
                        throw new Error('Your session has expired. Please log in again.');
                    }
                }
                throw new Error(data.error || data.detail || `Request failed: ${response.status}`);
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
     * Generate PKCE code verifier and challenge for Salesforce OAuth
     */
    async generatePKCE() {
        // Generate random code verifier
        const array = new Uint8Array(40);
        crypto.getRandomValues(array);
        const codeVerifier = btoa(String.fromCharCode(...array))
            .replace(/\+/g, '-')
            .replace(/\//g, '_')
            .replace(/=/g, '');

        // Generate code challenge (SHA-256 hash of verifier)
        const encoder = new TextEncoder();
        const data = encoder.encode(codeVerifier);
        const digest = await crypto.subtle.digest('SHA-256', data);
        const codeChallenge = btoa(String.fromCharCode(...new Uint8Array(digest)))
            .replace(/\+/g, '-')
            .replace(/\//g, '_')
            .replace(/=/g, '');

        return { codeVerifier, codeChallenge };
    },

    /**
     * Get Salesforce OAuth authorization URL
     */
    getSalesforceAuthUrl(clientId, codeChallenge, redirectUri = 'https://login.salesforce.com/services/oauth2/success') {
        const params = new URLSearchParams({
            response_type: 'code',
            client_id: clientId,
            redirect_uri: redirectUri,
            code_challenge: codeChallenge,
            code_challenge_method: 'S256'
        });
        return `https://login.salesforce.com/services/oauth2/authorize?${params.toString()}`;
    },

    /**
     * Exchange Salesforce authorization code for access token and connect
     */
    async exchangeSalesforceCode(authorizationCode, codeVerifier, clientId, clientSecret, redirectUri = 'https://login.salesforce.com/services/oauth2/success') {
        return await API.request('/platforms/salesforce/exchange-code/', {
            method: 'POST',
            body: JSON.stringify({
                code: authorizationCode,
                code_verifier: codeVerifier,
                client_id: clientId,
                client_secret: clientSecret,
                redirect_uri: redirectUri
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
     * Process a query with streaming response (for real-time logs)
     */
    async processQueryStream(query, platform = '', onChunk) {
        return await API.streamRequest('/queries/process/', {
            method: 'POST',
            body: JSON.stringify({ query, platform })
        }, onChunk);
    },

    /**
     * Make a streaming API request
     */
    async streamRequest(endpoint, options = {}, onChunk) {
        const url = `${API.baseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        if (API.accessToken) {
            headers['Authorization'] = `Bearer ${API.accessToken}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || data.detail || 'Request failed');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.trim()) {
                        try {
                            const data = JSON.parse(line);
                            if (onChunk) onChunk(data);
                        } catch (e) {
                            console.warn("Stream parse error for line:", line);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Stream request error:', error);
            throw error;
        }
    },

    /**
     * Get query history
     */
    async getQueryHistory() {
        return await API.request('/queries/history/');
    },

    /**
     * Get saved queries for the current user
     */
    async getSavedQueries() {
        return await API.request('/queries/saved-queries/');
    },

    /**
     * Save a new query (name, query_text, optional platform)
     */
    async saveQuery(name, queryText, platform = '') {
        return await API.request('/queries/saved-queries/', {
            method: 'POST',
            body: JSON.stringify({ name, query_text: queryText, platform: platform || '' })
        });
    },

    /**
     * Delete a saved query by id
     */
    async deleteSavedQuery(id) {
        return await API.request(`/queries/saved-queries/${id}/`, { method: 'DELETE' });
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
