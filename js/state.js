/**
 * Application State Management
 */

const State = {
    // Current user session
    user: null,

    // Connected platforms (fetched from backend)
    platforms: [],

    // Current page
    currentPage: 'landing',

    // Platform being connected
    connectingPlatform: null,

    // Chat sessions history
    sessions: {
        all: [],
        stripe: [],
        zendesk: [],
        github: []
    },

    // Currently active session tab
    activeSession: 'all',

    // Processing state
    isProcessing: false,

    /**
     * Initialize state
     */
    async init() {
        // Check if we have valid tokens and fetch user data
        if (API.isAuthenticated()) {
            try {
                const response = await API.getProfile();
                if (response.success) {
                    State.user = response.user;
                    await State.fetchPlatforms();
                }
            } catch (e) {
                console.warn('Failed to restore session:', e);
                State.user = null;
            }
        }
    },

    /**
     * Fetch platforms from backend
     */
    async fetchPlatforms() {
        try {
            const response = await API.listPlatforms();
            if (response.success) {
                State.platforms = response.platforms || [];
            }
        } catch (e) {
            console.error('Failed to fetch platforms:', e);
            State.platforms = [];
        }
    },

    /**
     * Set user session
     */
    setUser(user) {
        State.user = user;
    },

    /**
     * Clear user session
     */
    clearUser() {
        State.user = null;
        State.platforms = [];
        State.sessions = {
            all: [],
            stripe: [],
            zendesk: [],
            github: []
        };
        State.activeSession = 'all';
    },

    /**
     * Check if any platform is connected
     */
    hasConnectedPlatforms() {
        return State.platforms.length > 0;
    },

    /**
     * Get list of connected platforms
     */
    getConnectedPlatforms() {
        return State.platforms.filter(p => p.is_valid);
    },

    /**
     * Get platform by name
     */
    getPlatformByName(name) {
        return State.platforms.find(p => p.platform === name);
    },

    /**
     * Set active session
     */
    setActiveSession(session) {
        if (State.sessions[session]) {
            State.activeSession = session;
            return true;
        }
        return false;
    },

    /**
     * Get messages for current session
     */
    getMessages() {
        return State.sessions[State.activeSession] || [];
    },

    /**
     * Add a chat message
     */
    addMessage(message, platform = null) {
        const msgObj = {
            id: Utils.generateId(),
            timestamp: new Date().toISOString(),
            ...message
        };

        // Always add to 'all'
        State.sessions.all.push(msgObj);

        // Add to specific platform session if applicable
        if (platform && State.sessions[platform]) {
            State.sessions[platform].push(msgObj);
        } else if (State.activeSession !== 'all' && State.sessions[State.activeSession]) {
            // If explicit platform not provided, infer from active session
            State.sessions[State.activeSession].push(msgObj);
        }
    },

    /**
     * Clear all messages
     */
    clearMessages() {
        State.sessions = {
            all: [],
            stripe: [],
            zendesk: [],
            github: []
        };
    },

    /**
     * Set current page
     */
    setCurrentPage(page) {
        State.currentPage = page;
    },

    /**
     * Check if logged in
     */
    isLoggedIn() {
        return !!State.user && API.isAuthenticated();
    }
};

// Make State globally available
window.State = State;
