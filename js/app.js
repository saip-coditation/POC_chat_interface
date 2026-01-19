/**
 * Main Application Controller
 */

const App = {
  /**
   * Initialize the application
   */
  async init() {
    // Initialize theme
    App.initTheme();

    // Initialize state (checks for existing session)
    await State.init();

    App.bindEvents();
    App.handleInitialRoute();
    App.updateUI();
  },

  /**
   * Initialize theme from localStorage or system preference
   */
  initTheme() {
    const savedTheme = localStorage.getItem('databridge_theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme) {
      document.documentElement.setAttribute('data-theme', savedTheme);
    } else if (prefersDark) {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
    // Light theme is default, no attribute needed
  },

  /**
   * Toggle theme between light and dark
   */
  toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    if (newTheme === 'light') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
    }

    localStorage.setItem('databridge_theme', newTheme);

    // Show toast notification
    const themeName = newTheme === 'dark' ? 'Dark' : 'Light';
    App.showToast(`${themeName} mode enabled`, 'info');
  },

  /**
   * Bind all event listeners
   */
  bindEvents() {
    // Navigation
    window.addEventListener('hashchange', App.handleRouteChange);

    // Theme toggle
    const themeToggle = Utils.$('#theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', App.toggleTheme);
    }

    // Login form
    const loginForm = Utils.$('#login-form');
    if (loginForm) {
      loginForm.addEventListener('submit', App.handleLogin);
    }

    // Password toggle
    const pwdToggle = Utils.$('.input-password-toggle');
    if (pwdToggle) {
      pwdToggle.addEventListener('click', App.togglePasswordVisibility);
    }

    // Platform cards on landing
    Utils.$$('.platform-card').forEach(card => {
      card.addEventListener('click', () => {
        const platform = card.dataset.platform;
        if (platform) App.startConnect(platform);
      });
    });

    // Connect form
    const connectForm = Utils.$('#connect-form');
    if (connectForm) {
      connectForm.addEventListener('submit', App.handleConnect);
    }

    const connectCancel = Utils.$('#connect-cancel');
    if (connectCancel) {
      connectCancel.addEventListener('click', () => App.navigate('dashboard'));
    }

    // Query form
    const queryForm = Utils.$('#query-form');
    if (queryForm) {
      queryForm.addEventListener('submit', App.handleQuery);
    }

    // Query input
    const queryInput = Utils.$('#query-input');
    if (queryInput) {
      queryInput.addEventListener('input', () => {
        const submitBtn = Utils.$('#query-submit');
        submitBtn.disabled = !queryInput.value.trim();
      });
    }

    // Example queries
    Utils.$$('.example-query').forEach(btn => {
      btn.addEventListener('click', () => {
        const query = btn.dataset.query;
        if (query) {
          Utils.$('#query-input').value = query;
          Utils.$('#query-submit').disabled = false;
          App.handleQuery(new Event('submit'));
        }
      });
    });

    // Register form
    const registerForm = Utils.$('#register-form');
    if (registerForm) {
      registerForm.addEventListener('submit', App.handleRegister);
    }

    // Logout
    const logoutBtn = Utils.$('#logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', App.handleLogout);
    }
  },

  /**
   * Handle initial route on page load
   */
  handleInitialRoute() {
    const hash = window.location.hash.slice(1) || 'landing';
    App.navigate(hash, false);
  },

  /**
   * Handle route changes
   */
  handleRouteChange() {
    const hash = window.location.hash.slice(1) || 'landing';
    App.navigate(hash, false);
  },

  /**
   * Navigate to a page
   */
  async navigate(page, updateHash = true) {
    // Check authentication for protected pages
    const protectedPages = ['dashboard', 'query', 'connect'];
    if (protectedPages.includes(page) && !State.isLoggedIn()) {
      page = 'login';
    }

    // Hide all pages
    Utils.$$('.page').forEach(p => {
      p.classList.remove('active');
    });

    // Show target page
    const targetPage = Utils.$(`#page-${page}`);
    if (targetPage) {
      targetPage.classList.add('active');
      State.setCurrentPage(page);

      // Update navigation visibility
      const nav = Utils.$('#main-nav');
      const footer = Utils.$('#security-footer');

      // Keep navbar and footer visible on all pages as requested
      Utils.show(nav);
      if (footer) Utils.show(footer);

      // Update active nav link
      Utils.$$('.nav__link').forEach(link => {
        link.classList.toggle('active', link.dataset.nav === page);
      });

      // Page-specific setup
      if (page === 'dashboard') {
        await App.renderDashboard();
      } else if (page === 'query') {
        await App.renderQueryPage();
      }
    }

    if (updateHash) {
      window.location.hash = page;
    }
  },

  /**
   * Update UI based on current state
   */
  updateUI() {
    const isLoggedIn = State.isLoggedIn();

    // Toggle navigation menus
    const navMenu = Utils.$('#nav-menu');
    const authLinks = Utils.$('#auth-links');
    const logoutBtn = Utils.$('#logout-btn');

    if (isLoggedIn) {
      if (navMenu) Utils.show(navMenu);
      if (authLinks) Utils.hide(authLinks);
      if (logoutBtn) Utils.show(logoutBtn);
    } else {
      if (navMenu) Utils.hide(navMenu);
      if (authLinks) Utils.show(authLinks);
      if (logoutBtn) Utils.hide(logoutBtn);
    }

    App.renderQueryPlatformBadges();
  },

  /**
   * Handle login form submission
   */
  async handleLogin(e) {
    e.preventDefault();

    const email = Utils.$('#login-email').value;
    const password = Utils.$('#login-password').value;
    const submitBtn = e.target.querySelector('button[type="submit"]');

    // Show loading state
    submitBtn.classList.add('btn--loading');
    submitBtn.disabled = true;

    try {
      const result = await API.login(email, password);

      if (result.success) {
        State.setUser(result.user);
        await State.fetchPlatforms();

        App.showToast('Successfully signed in!', 'success');

        // Navigate based on platform connections
        if (State.hasConnectedPlatforms()) {
          App.navigate('query');
        } else {
          App.navigate('dashboard');
        }
      } else {
        App.showToast(result.error || 'Login failed', 'error');
      }
    } catch (err) {
      App.showToast('An error occurred. Please try again.', 'error');
    } finally {
      submitBtn.classList.remove('btn--loading');
      submitBtn.disabled = false;
    }
  },

  /**
   * Handle logout
   */
  async handleLogout() {
    await API.logout();
    State.clearUser();
    App.showToast('Signed out successfully', 'info');
    App.navigate('landing');
  },

  /**
   * Toggle password visibility
   */
  togglePasswordVisibility(e) {
    const btn = e.currentTarget;
    const input = btn.previousElementSibling;
    const isPassword = input.type === 'password';

    input.type = isPassword ? 'text' : 'password';
    btn.innerHTML = isPassword
      ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
      : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
  },

  /**
   * Start platform connection flow
   */
  startConnect(platform) {
    State.connectingPlatform = platform;
    const config = API.platformConfig[platform];

    // Update connect page UI
    const iconContainer = Utils.$('#connect-platform-icon');
    iconContainer.innerHTML = config.icon;
    iconContainer.className = `connect-card__platform-icon connect-card__platform-icon--${platform}`;

    Utils.$('#connect-title').textContent = `Connect ${config.name}`;
    Utils.$('#connect-subtitle').textContent = config.description;

    // Show platform-specific instructions
    Utils.hide('#stripe-instructions');
    Utils.hide('#zoho-instructions');
    Utils.hide('#github-instructions');

    if (platform === 'stripe') {
      Utils.show('#stripe-instructions');
      Utils.$('#api-key-label').textContent = 'Stripe Secret Key (Authentication Token)';
      Utils.$('#api-key').placeholder = 'sk_test_... or sk_live_...';
      Utils.$('#api-key-help').textContent = 'Your Secret Key acts as your Access Token and is encrypted at rest.';
    } else if (platform === 'zoho') {
      Utils.show('#zoho-instructions');
      // Default to "Code" mode
      App.switchZohoTab('code');
    } else if (platform === 'github') {
      Utils.show('#github-instructions');
      Utils.$('#api-key-label').textContent = 'GitHub Personal Access Token';
      Utils.$('#api-key').placeholder = 'ghp_xxxxxxxxxxxxxxxxxxxx';
      Utils.$('#api-key-help').textContent = 'Generate a token with "repo" scope at GitHub Settings.';
    }

    // Reset form state
    Utils.$('#api-key').value = '';
    Utils.$('#api-key').disabled = false;
    Utils.hide('#connect-success');
    Utils.hide('#connect-error');
    Utils.hide('#masked-key-display');
    Utils.$('#connect-submit').disabled = false;
    Utils.$('#connect-submit').classList.remove('btn--loading');

    // Check if user is logged in
    if (!State.isLoggedIn()) {
      App.navigate('login');
      App.showToast('Please sign in to connect platforms', 'info');
    } else {
      App.navigate('connect');
    }
  },

  /**
   * Handle platform connection
   */
  /**
   * Switch between Zoho connect tabs
   */
  switchZohoTab(tab) {
    const codeBtn = Utils.$('#zoho-tab-code');
    const tokenBtn = Utils.$('#zoho-tab-token');
    const codeInstr = Utils.$('#zoho-code-instructions');
    const tokenInstr = Utils.$('#zoho-token-instructions');
    const inputLabel = Utils.$('#api-key-label');
    const inputHelp = Utils.$('#api-key-help');
    const input = Utils.$('#api-key');

    // Reset button styles
    codeBtn.className = tab === 'code' ? 'btn btn--sm btn--primary' : 'btn btn--sm btn--secondary';
    tokenBtn.className = tab === 'token' ? 'btn btn--sm btn--primary' : 'btn btn--sm btn--secondary';

    if (tab === 'code') {
      Utils.show(codeInstr);
      Utils.hide(tokenInstr);
      inputLabel.textContent = 'Zoho Authorization Code';
      input.placeholder = '1000.xxxxxxx.xxxxxxx';
      inputHelp.textContent = 'We will automatically exchange this code for a refresh token.';
      State.zohoConnectMode = 'code';
    } else {
      Utils.hide(codeInstr);
      Utils.show(tokenInstr);
      inputLabel.textContent = 'Zoho Refresh Token';
      input.placeholder = '1000.xxxxxxx.xxxxxxx';
      inputHelp.textContent = 'Paste your existing refresh token here.';
      State.zohoConnectMode = 'token';
    }
  },

  /**
   * Handle platform connection
   */
  async handleConnect(e) {
    e.preventDefault();

    const apiKey = Utils.$('#api-key').value;
    const platform = State.connectingPlatform;
    const submitBtn = Utils.$('#connect-submit');

    // Reset status
    Utils.hide('#connect-success');
    Utils.hide('#connect-error');

    // Show loading
    submitBtn.classList.add('btn--loading');
    submitBtn.disabled = true;

    try {
      let result;

      // Special handling for Zoho Code Exchange
      if (platform === 'zoho' && (State.zohoConnectMode === 'code' || !State.zohoConnectMode)) {
        const clientId = Utils.$('#zoho-client-id')?.value?.trim();
        const clientSecret = Utils.$('#zoho-client-secret')?.value?.trim();

        if (!clientId || !clientSecret) {
          throw new Error('Please enter Client ID and Client Secret');
        }

        result = await API.exchangeZohoCode(apiKey, clientId, clientSecret);
      } else {
        // Standard connection (Stripe, GitHub, or Zoho Refresh Token)
        result = await API.connectPlatform(platform, apiKey);
      }

      if (result.success) {
        // Refresh platforms list
        await State.fetchPlatforms();

        // Show success
        Utils.show('#connect-success');

        // Show masked key
        const displayKey = result.refresh_token || apiKey;
        Utils.$('#masked-key-value').textContent = result.platform?.masked_key || Utils.maskApiKey(displayKey);
        Utils.show('#masked-key-display');

        // Clear the actual key from input (security)
        Utils.$('#api-key').value = '';
        Utils.$('#api-key').type = 'text';
        Utils.$('#api-key').value = result.platform?.masked_key || Utils.maskApiKey(displayKey);
        Utils.$('#api-key').disabled = true;

        App.showToast(`${API.platformConfig[platform].name} connected successfully!`, 'success');

        // Navigate to query after delay
        setTimeout(() => {
          App.navigate('query');
        }, 1500);
      } else {
        Utils.show('#connect-error');
        Utils.$('#connect-error-message').textContent = result.error || 'Connection failed';
        submitBtn.disabled = false;
      }
    } catch (err) {
      Utils.show('#connect-error');
      Utils.$('#connect-error-message').textContent = err.message || 'Connection failed. Please try again.';
      submitBtn.disabled = false;
    } finally {
      submitBtn.classList.remove('btn--loading');
    }
  },

  /**
   * Render dashboard page
   */
  async renderDashboard() {
    // Refresh platforms from backend
    await State.fetchPlatforms();

    const grid = Utils.$('#dashboard-grid');
    const emptyState = Utils.$('#dashboard-empty');
    const connected = State.getConnectedPlatforms();

    if (connected.length === 0) {
      Utils.hide(grid);
      Utils.show(emptyState);
      return;
    }

    Utils.show(grid);
    Utils.hide(emptyState);

    grid.innerHTML = connected.map(platform => {
      const config = API.platformConfig[platform.platform];
      return `
        <div class="dashboard-card">
          <div class="dashboard-card__header">
            <div class="dashboard-card__platform">
              <div class="dashboard-card__icon dashboard-card__icon--${platform.platform}">
                ${config.icon}
              </div>
              <div>
                <div class="dashboard-card__name">${config.name}</div>
                <div class="dashboard-card__key">${platform.masked_key}</div>
              </div>
            </div>
            <span class="badge badge--success">
              <span class="badge__dot"></span>
              Connected
            </span>
          </div>
          <p class="dashboard-card__info">
            Connected ${Utils.formatRelativeTime(platform.connected_at)}
          </p>
          <div class="dashboard-card__actions">
            <button class="btn btn--secondary btn--sm" onclick="App.reverifyPlatform(${platform.id}, '${platform.platform}')">
              Re-verify
            </button>
            <button class="btn btn--ghost btn--sm" onclick="App.disconnectPlatform(${platform.id}, '${platform.platform}')">
              Disconnect
            </button>
          </div>
        </div>
      `;
    }).join('');
  },

  /**
   * Disconnect a platform
   */
  async disconnectPlatform(platformId, platformName) {
    const config = API.platformConfig[platformName];

    if (confirm(`Are you sure you want to disconnect ${config.name}?`)) {
      try {
        const result = await API.disconnectPlatform(platformId);
        if (result.success) {
          await State.fetchPlatforms();
          App.renderDashboard();
          App.showToast(`${config.name} disconnected`, 'info');
        } else {
          App.showToast(result.error || 'Failed to disconnect', 'error');
        }
      } catch (err) {
        App.showToast('Failed to disconnect platform', 'error');
      }
    }
  },

  /**
   * Handle user registration
   */
  async handleRegister(e) {
    if (e) e.preventDefault();

    const firstName = Utils.$('#register-first-name').value;
    const lastName = Utils.$('#register-last-name').value;
    const email = Utils.$('#register-email').value;
    const password = Utils.$('#register-password').value;

    const submitBtn = Utils.$('#register-form button[type="submit"]');
    if (!submitBtn) return;

    submitBtn.disabled = true;
    submitBtn.classList.add('btn--loading');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Creating account...';

    try {
      const response = await API.register(email, password, firstName, lastName);

      if (response.success) {
        App.showToast('Account created successfully!', 'success');
        // Initial state update to catch the new user
        await State.init();
        App.navigate('dashboard');
        App.updateUI();
      } else {
        App.showToast(response.error || 'Registration failed', 'error');
      }
    } catch (error) {
      console.error('Registration error:', error);
      App.showToast('Network error. Please try again.', 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.classList.remove('btn--loading');
      submitBtn.textContent = originalText;
    }
  },

  /**
   * Re-verify platform credentials
   */
  reverifyPlatform(platformId, platformName) {
    State.connectingPlatform = platformName;
    // Store ID for reverify
    State.reverifyPlatformId = platformId;
    App.startConnect(platformName);
  },

  /**
   * Render query page
   */
  async renderQueryPage() {
    // Refresh platforms
    await State.fetchPlatforms();

    App.renderQueryPlatformBadges();
    App.initSessionTabs();

    // Check if any platforms are connected
    if (!State.hasConnectedPlatforms()) {
      Utils.$('#chat-welcome').innerHTML = `
        <div class="empty-state">
          <div class="empty-state__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <h3 class="empty-state__title">No platforms connected</h3>
          <p class="empty-state__text">Connect Stripe or Zoho CRM to start querying your data</p>
          <a href="#landing" class="btn btn--primary">Connect a Platform</a>
        </div>
      `;
      Utils.$('#query-input').disabled = true;
      Utils.$('#query-submit').disabled = true;
    } else {
      Utils.$('#query-input').disabled = false;
      // Re-render messages for current session if returning to page
      App.renderMessages();
    }
  },

  /**
   * Initialize session tabs
   */
  initSessionTabs() {
    const tabs = document.querySelectorAll('.session-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const session = tab.getAttribute('data-session');
        App.switchSession(session);
      });
    });
  },

  /**
   * Switch active chat session
   */
  switchSession(session) {
    if (State.setActiveSession(session)) {
      // Update tab UI
      document.querySelectorAll('.session-tab').forEach(tab => {
        if (tab.getAttribute('data-session') === session) {
          tab.classList.add('session-tab--active');
        } else {
          tab.classList.remove('session-tab--active');
        }
      });

      // Show/Hide welcome message based on session content
      const messages = State.getMessages();
      if (messages.length > 0) {
        Utils.hide('#chat-welcome');
      } else {
        Utils.show('#chat-welcome');
      }

      // Re-render messages
      App.renderMessages();
    }
  },

  /**
   * Render all messages for current session
   */
  renderMessages() {
    const container = Utils.$('#chat-messages');
    container.innerHTML = '';

    const messages = State.getMessages();
    messages.forEach(msg => {
      // Re-use logic to append message
      App.appendMessageToUI(msg);
    });

    // Scroll to bottom
    const chatContainer = Utils.$('#chat-container');
    chatContainer.scrollTop = chatContainer.scrollHeight;
  },

  /**
   * Append a single message object to UI
   */
  appendMessageToUI(msg) {
    const container = Utils.$('#chat-messages');
    const messageEl = document.createElement('div');
    messageEl.className = `chat-message ${msg.type === 'user' ? 'chat-message--user' : 'chat-message--ai'} animate-fadeInUp`;

    if (msg.type === 'user') {
      messageEl.innerHTML = `
        <div class="chat-message__avatar">
          <div class="avatar">${State.user?.first_name?.[0] || 'U'}</div>
        </div>
        <div class="chat-message__content">
          <p class="chat-message__text">${Utils.escapeHtml(msg.content)}</p>
        </div>
      `;
    } else {
      // AI message with rich content
      let htmlContent = msg.content;

      // Only parse markdown if content doesn't already contain HTML tags
      // (result cards are already HTML, don't parse them)
      const containsHtml = /<[a-z][\s\S]*>/i.test(msg.content);

      if (!containsHtml && typeof marked !== 'undefined') {
        try {
          htmlContent = marked.parse(msg.content);
        } catch (e) {
          console.error('Markdown parse error:', e);
        }
      }

      messageEl.innerHTML = `
        <div class="chat-message__avatar">
          <div class="avatar" style="background: linear-gradient(135deg, var(--color-stripe), var(--color-zoho-accent));">AI</div>
        </div>
        <div class="chat-message__content ai-response" style="max-width: 700px;">
          <div style="font-size: 10px; text-transform: uppercase; color: #818cf8; margin-bottom: 8px; font-weight: 700; letter-spacing: 0.05em; display: flex; align-items: center; gap: 4px;">
            <span style="width: 6px; height: 6px; background: #818cf8; border-radius: 50%;"></span>
            Summarizer Agent
          </div>
          ${htmlContent} 
        </div>
      `;
    }
    container.appendChild(messageEl);

    // Render Chart if available
    if (msg.rawData && msg.rawData.chart) {
      const chartId = `chart-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      const chartContainer = document.createElement('div');
      chartContainer.className = 'chat-chart-container';
      chartContainer.innerHTML = `<canvas id="${chartId}"></canvas>`;

      // Append to the message content
      const contentEl = messageEl.querySelector('.chat-message__content');
      if (contentEl) {
        contentEl.appendChild(chartContainer);
        // Render the chart
        setTimeout(() => {
          App.renderChart(chartId, msg.rawData.chart);
        }, 100);
      }
    }
  },

  /**
   * Render platform badges in query header
   */
  renderQueryPlatformBadges() {
    const container = Utils.$('#query-platforms');
    if (!container) return;

    const connected = State.getConnectedPlatforms();

    container.innerHTML = connected.map(platform => {
      const config = API.platformConfig[platform.platform];
      return `
        <span class="badge badge--success">
          <span class="badge__dot"></span>
          ${config.name}
        </span>
      `;
    }).join('');
  },

  /**
   * Handle query submission
   */
  async handleQuery(e) {
    e.preventDefault();

    const input = Utils.$('#query-input');
    const query = input.value.trim();

    if (!query || State.isProcessing) return;

    // Add user message
    App.addChatMessage(query, 'user');

    // Clear input
    input.value = '';
    Utils.$('#query-submit').disabled = true;

    State.isProcessing = true;
    App.showTypingIndicator();

    try {
      // Determine platform context if in specific session
      let platform = null;
      if (State.activeSession !== 'all') {
        platform = State.activeSession;
      }

      const response = await API.processQuery(query, platform);

      App.removeTypingIndicator();

      if (response.success) {
        if (response.logs) {
          App.renderLogs(response.logs);
        }
        App.addChatMessage(response, 'ai');
      } else {
        App.addChatMessage({
          summary: response.error || 'Failed to process query',
          data: null
        }, 'ai');
      }
    } catch (error) {
      console.error('Query error:', error);
      App.removeTypingIndicator();
      App.addChatMessage({
        summary: error.message || 'An error occurred while processing your request.',
        data: null
      }, 'ai');
    } finally {
      State.isProcessing = false;
    }
  },

  /**
   * Add chat message to state and UI
   */
  addChatMessage(content, type) {
    // Construct message object
    let messageContent = '';

    if (type === 'user') {
      messageContent = content;
    } else {
      // Format AI response (reuse existing logic in appendMessageToUI)
      // For state storage, we store the raw response object for AI, string for user
      // But for display we need the rendered HTML. 
      // Simplified: Store the "summary" and "metrics/table" structure for AI

      const response = content;
      const platform = response.platform || 'unknown';
      const config = API.platformConfig[platform] || {};

      let metricsHtml = '';
      if (response.data && response.data.count !== undefined) {
        metricsHtml = `<div class="result-metrics">
            <div class="metric">
              <span class="metric__label">Count</span>
              <span class="metric__value">${response.data.count}</span>
            </div>
         </div>`;
      }

      let tableHtml = '';
      if (response.data && response.data.data && Array.isArray(response.data.data) && response.data.data.length > 0) {
        const headers = Object.keys(response.data.data[0]).slice(0, 4); // Show first 4 cols
        const rows = response.data.data.slice(0, 5); // Show first 5 rows

        const ths = headers.map(h => `<th>${Utils.capitalize(h.replace(/_/g, ' '))}</th>`).join('');
        const trs = rows.map(row => {
          // Use renderTableRow logic if available, else generic
          // For now generic:
          const tds = headers.map(h => {
            let val = row[h];
            // Basic format handling
            if (typeof val === 'object' && val !== null) val = JSON.stringify(val);
            return `<td>${Utils.escapeHtml(String(val || '-'))}</td>`;
          }).join('');
          // Better: use App.renderTableRow if we refactor it to return string
          // But existing renderTableRow is tied to specific fields. 
          // We'll rely on our updated App.addChatMessage logic to capture the FULL HTML
          return `<tr>${tds}</tr>`;
        }).join('');

        // Use the improved renderTableRow logic (accessing it via App.renderTableRow would be cleaner if it was pure)
        // Let's defer "rich" rendering to the appendMessageToUI by storing the raw data
        // BUT wait, renderMessages() needs to re-construct the HTML. 
        // Strategy: Store raw data in State, and re-render HTML in appendMessageToUI.
      }

      // Actually, let's keep it simple: Render the HTML NOW and store it as "content" string.
      // This is easiest for "all" session view which mixes types.

      // Parse markdown in summary if marked is available
      let parsedSummary = response.summary || '';
      if (typeof marked !== 'undefined' && parsedSummary) {
        try {
          parsedSummary = marked.parse(parsedSummary);
        } catch (e) {
          console.error('Markdown parse error:', e);
        }
      }

      // Re-creating the result card HTML:
      const resultCardHeader = `
          <div class="result-card">
          <div class="result-card__header">
            <span class="result-card__platform">
              <span style="width: 16px; height: 16px; display: inline-flex;">${config.icon || ''}</span>
              ${config.name || platform}
            </span>
          </div>
          <div class="result-card__body ai-response">
            ${parsedSummary}
      `;

      // Determine table content with collapsible View Details
      let tableContent = '';
      if (response.data && response.data.data && Array.isArray(response.data.data) && response.data.data.length > 0) {
        const items = response.data.data;
        const itemCount = items.length;
        const type = App.detectResultType(items, platform);

        // Define columns based on type
        let cols = [];
        const item0 = items[0];
        if (platform === 'github') {
          if (item0.sha) cols = ['Commit', 'Message', 'Author', 'Date'];
          else if (item0.merged !== undefined) cols = ['PR #', 'Title', 'State', 'Author'];
          else if (item0.number) cols = ['Issue #', 'Title', 'State', 'Labels'];
          else cols = ['Name', 'Description', 'Language'];
        } else if (platform === 'stripe') {
          if (item0.amount) cols = ['Amount', 'Status', 'Customer', 'Date'];
          else if (item0.email) cols = ['Name', 'Email', 'Balance'];
          else cols = ['ID', 'Name', 'Status'];
        } else if (platform === 'zendesk') {
          if (item0.subject) cols = ['ID', 'Subject', 'Status', 'Priority'];
          else cols = ['Name', 'Email', 'Role'];
        } else {
          cols = Object.keys(item0).slice(0, 4).map(k => Utils.capitalize(k));
        }

        // Build collapsible details section
        const tableHeader = cols.map(c => `<th>${c}</th>`).join('');
        const rowsHtml = items.map(item => {
          return `<tr>` + App.renderTableRow(item, type, platform) + `</tr>`;
        }).join('');

        tableContent = `
          <details class="view-details">
            <summary class="view-details__header">
              <span class="view-details__icon">📋</span>
              View Details (${itemCount} items)
              <span class="view-details__chevron">▼</span>
            </summary>
            <div class="view-details__content">
              <div class="table-container">
                <table class="result-table">
                  <thead><tr>${tableHeader}</tr></thead>
                  <tbody>${rowsHtml}</tbody>
                </table>
              </div>
            </div>
          </details>
        `;
      }

      messageContent = resultCardHeader + tableContent + `</div></div>`;
    }

    const message = {
      type,
      content: messageContent,
      // Store raw data too for potential future re-rendering
      rawData: type === 'ai' ? content : null
    };

    // Store in state
    let platform = null;
    if (type === 'ai' && content.platform) {
      platform = content.platform;
    }
    State.addMessage(message, platform);

    // Add to UI if visible (active session matches message context)
    // If active session is 'all', always show
    // If active session matches platform, show
    const currentSession = State.activeSession;
    if (currentSession === 'all' || (platform && currentSession === platform) || (type === 'user' && currentSession !== 'all')) {
      // Note: showing user messages in specific tabs is tricky if they are cross-cutting.
      // But addMessage stores them in the current session too.
      // So we just check if the message was added to the *current active session*

      // Simpler: Just re-render messages to be safe and consistent order, 
      // OR just append. appending is smoother.
      App.appendMessageToUI(message);

      const chatContainer = Utils.$('#chat-container');
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  },

  /**
   * Helper to detect result type for table rendering
   */
  detectResultType(items, platform) {
    if (!items || !items.length) return 'unknown';
    const item = items[0];
    if (platform === 'github') {
      if (item.sha) return 'commits';
      if (item.merged !== undefined) return 'pull_requests';
      if (item.number) return 'issues';
      return 'repositories';
    }
    if (platform === 'stripe') {
      if (item.amount) return 'transactions'; // or invoices/charges
      return 'customers';
    }
    if (platform === 'zendesk') {
      if (item.subject) return 'tickets';
      return 'users';
    }
    return 'generic';
  },

  /**
   * Show typing indicator
   */
  showTypingIndicator() {
    const container = Utils.$('#chat-messages');
    const id = 'typing-indicator';
    if (Utils.$(`#${id}`)) return;

    const messageEl = document.createElement('div');
    messageEl.className = 'chat-message message-enter';
    messageEl.id = id;

    messageEl.innerHTML = `
      <div class="chat-message__avatar">
        <div class="avatar" style="background: linear-gradient(135deg, var(--color-stripe), var(--color-zendesk-accent));">AI</div>
      </div>
      <div class="chat-message__content">
        <div class="processing-loader">
          <div class="processing-step active">
            <div class="processing-step__icon"><div class="spinner spinner--sm"></div></div>
            <span class="processing-step__text">Thinking...</span>
          </div>
        </div>
      </div>
    `;

    container.appendChild(messageEl);
    App.scrollToBottom();
  },

  /**
   * Remove typing indicator
   */
  removeTypingIndicator() {
    const el = Utils.$('#typing-indicator');
    if (el) el.remove();
  },

  /**
   * Render table row based on data type
   */
  renderTableRow(item, type) {
    if (type === 'invoices') {
      const statusClass = item.status === 'paid' ? 'paid' : (item.status === 'overdue' ? 'overdue' : 'unpaid');
      return `
        <td>${item.id || item.number || '-'}</td>
        <td>${item.customer_name || item.customer_email || '-'}</td>
        <td>${Utils.formatCurrency(item.amount, item.currency)}</td>
        <td><span class="status-pill status-pill--${statusClass}">${item.status}</span></td>
        <td>${Utils.formatDate(item.created)}</td>
      `;
    }

    if (type === 'tickets') {
      const statusClass = item.status === 'closed' || item.status === 'solved' ? 'closed' : 'open';
      return `
        <td>${item.id}</td>
        <td>${Utils.escapeHtml(item.subject || '-')}</td>
        <td><span class="status-pill status-pill--${statusClass}">${item.status}</span></td>
        <td>${item.priority || 'normal'}</td>
        <td>${Utils.formatRelativeTime(item.created_at)}</td>
      `;
    }

    if (type === 'subscriptions') {
      return `
        <td>${item.id}</td>
        <td>${item.customer || '-'}</td>
        <td><span class="status-pill status-pill--${item.status === 'active' ? 'paid' : 'unpaid'}">${item.status}</span></td>
        <td>${Utils.formatCurrency(item.amount)}</td>
        <td>${item.interval}</td>
      `;
    }

    if (type === 'customers') {
      return `
        <td>${item.id}</td>
        <td>${item.name || '-'}</td>
        <td>${item.email || '-'}</td>
        <td>${Utils.formatDate(item.created)}</td>
      `;
    }

    if (type === 'products') {
      const activeClass = item.active ? 'paid' : 'unpaid';
      return `
        <td>${item.id}</td>
        <td>${Utils.escapeHtml(item.name || '-')}</td>
        <td><span class="status-pill status-pill--${activeClass}">${item.active ? 'Active' : 'Inactive'}</span></td>
        <td>${Utils.escapeHtml(item.description || '-')}</td>
        <td>${Utils.formatDate(item.created)}</td>
      `;
    }

    if (type === 'payouts') {
      return `
        <td>${item.id}</td>
        <td>${Utils.formatCurrency(item.amount, item.currency)}</td>
        <td>${item.currency}</td>
        <td><span class="status-pill">${item.status}</span></td>
        <td>${Utils.formatDate(item.arrival_date)}</td>
      `;
    }

    // GitHub types
    if (type === 'repositories') {
      return `
        <td><strong>${Utils.escapeHtml(item.name || '-')}</strong></td>
        <td>${Utils.escapeHtml((item.description || '-').substring(0, 50))}</td>
        <td><span class="badge badge--info">${item.language || 'N/A'}</span></td>
        <td>⭐ ${item.stars || 0}</td>
        <td>${Utils.formatRelativeTime(item.updated_at)}</td>
      `;
    }

    if (type === 'commits') {
      return `
        <td><code>${item.sha || '-'}</code></td>
        <td>${Utils.escapeHtml((item.message || '-').substring(0, 60))}</td>
        <td>${Utils.escapeHtml(item.author || '-')}</td>
        <td>${Utils.formatRelativeTime(item.date)}</td>
      `;
    }

    if (type === 'pull_requests') {
      const stateClass = item.merged ? 'paid' : (item.state === 'open' ? 'open' : 'closed');
      const stateText = item.merged ? 'Merged' : item.state;
      return `
        <td>#${item.number}</td>
        <td>${Utils.escapeHtml((item.title || '-').substring(0, 50))}</td>
        <td><span class="status-pill status-pill--${stateClass}">${stateText}</span></td>
        <td>${Utils.escapeHtml(item.author || '-')}</td>
        <td>${Utils.formatRelativeTime(item.created_at)}</td>
      `;
    }

    if (type === 'issues') {
      const stateClass = item.state === 'open' ? 'open' : 'closed';
      return `
        <td>#${item.number}</td>
        <td>${Utils.escapeHtml((item.title || '-').substring(0, 50))}</td>
        <td><span class="status-pill status-pill--${stateClass}">${item.state}</span></td>
        <td>${Utils.escapeHtml(item.author || '-')}</td>
        <td>${Utils.formatRelativeTime(item.created_at)}</td>
      `;
    }

    return Object.values(item).map(v => `<td>${v}</td>`).join('');
  },

  /**
   * Scroll chat to bottom
   */
  scrollToBottom() {
    const container = Utils.$('#chat-container');
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  },

  /**
   * Render Agent Logs
   */
  renderLogs(logs) {
    const panel = Utils.$('#agent-logs-panel');
    const content = Utils.$('#agent-logs-content');

    if (!panel || !content) return;

    content.innerHTML = '';
    logs.forEach(log => {
      const entry = document.createElement('div');
      entry.className = `log-entry ${log.status || 'info'}`;
      entry.innerHTML = `
            <span class="log-entry__agent">${log.agent}:</span>
            <span class="log-entry__message">${Utils.escapeHtml(log.message)}</span>
          `;
      content.appendChild(entry);
    });

    panel.classList.remove('hidden');
    App.scrollToBottom();
  },

  /**
   * Render Chart.js Chart
   */
  renderChart(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Global Aesthetics
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';

    // Modern Gradient for Bars/Lines
    if (config.data && config.data.datasets && config.data.datasets[0]) {
      const ds = config.data.datasets[0];

      if (config.type === 'bar' || config.type === 'line') {
        const gradient = ctx.createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, '#6366f1'); // Indigo-500
        gradient.addColorStop(1, 'rgba(99, 102, 241, 0.1)');

        ds.backgroundColor = gradient;
        ds.borderColor = '#6366f1';
        ds.borderWidth = config.type === 'line' ? 2 : 0;
        ds.borderRadius = 6;
        ds.barPercentage = 0.6;

        if (config.type === 'line') {
          ds.tension = 0.4; // Smooth curve
          ds.fill = true;
        }
      } else if (config.type === 'doughnut') {
        ds.borderWidth = 0;
        ds.hoverOffset = 15;
        // Use custom palette if array
        if (Array.isArray(ds.backgroundColor)) {
          // Keep original colors but maybe adjust opacity? 
          // Let's rely on backend colors for categorical data
        }
      }
    }

    try {
      new Chart(ctx, {
        type: config.type,
        data: config.data,
        options: {
          ...config.options,
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: config.type === 'doughnut', // Hide legend for single-series bar/line
              position: 'bottom',
              labels: {
                usePointStyle: true,
                padding: 20,
                boxWidth: 8
              }
            },
            tooltip: {
              backgroundColor: 'rgba(17, 24, 39, 0.95)',
              titleColor: '#fff',
              bodyColor: '#e5e7eb',
              borderColor: 'rgba(255,255,255,0.1)',
              borderWidth: 1,
              padding: 12,
              cornerRadius: 8,
              displayColors: true,
              boxPadding: 4
            }
          },
          scales: config.type === 'doughnut' ? {} : {
            y: {
              beginAtZero: true,
              grid: {
                color: 'rgba(255, 255, 255, 0.05)',
                drawBorder: false
              },
              ticks: { padding: 10 }
            },
            x: {
              grid: { display: false },
              ticks: { padding: 10 }
            }
          },
          layout: {
            padding: 10
          },
          interaction: {
            mode: 'index',
            intersect: false,
          },
        }
      });
    } catch (e) {
      console.error("Chart render error:", e);
    }
  },

  /**
   * Show toast notification
   */
  showToast(message, type = 'info') {
    const container = Utils.$('#toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;

    const icons = {
      success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
      error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
      warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };

    toast.innerHTML = `
      <span class="toast__icon">${icons[type] || icons.info}</span>
      <span class="toast__message">${message}</span>
      <button class="toast__close" onclick="this.parentElement.remove()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    `;

    container.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
      toast.remove();
    }, 5000);
  }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', App.init);

// Make App globally available
window.App = App;
