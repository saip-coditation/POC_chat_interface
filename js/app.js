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
   * Initialize theme - always dark mode
   */
  initTheme() {
    // Always set dark mode
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem('databridge_theme', 'dark');
  },

  /**
   * Bind all event listeners
   */
  bindEvents() {
    // Navigation
    window.addEventListener('hashchange', App.handleRouteChange);

    // Theme toggle removed - dark mode only

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

    // Query input with autocomplete
    const queryInput = Utils.$('#query-input');
    if (queryInput) {
      queryInput.addEventListener('input', () => {
        const submitBtn = Utils.$('#query-submit');
        submitBtn.disabled = !queryInput.value.trim();
        // Trigger autocomplete only if not selecting from dropdown
        if (!App.autocompleteState.isSelecting) {
          App.handleAutocomplete(queryInput.value);
        } else {
          // Reset flag after a short delay
          setTimeout(() => {
            App.autocompleteState.isSelecting = false;
          }, 100);
        }
      });
      
      // Handle keyboard navigation
      queryInput.addEventListener('keydown', (e) => {
        App.handleAutocompleteKeydown(e);
      });
      
      // Hide autocomplete on blur (with delay to allow clicks)
      queryInput.addEventListener('blur', () => {
        setTimeout(() => {
          App.hideAutocomplete();
        }, 200);
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

    // Saved queries: run (click label or Run) or delete (delegated)
    const savedList = Utils.$('#saved-queries-list');
    if (savedList) {
      savedList.addEventListener('click', (e) => {
        const deleteBtn = e.target.closest('.saved-query-item__delete');
        const item = e.target.closest('.saved-query-item');
        if (!item) return;
        const query = item.dataset.query;
        const platform = item.dataset.platform || '';
        const id = item.dataset.id;
        if (deleteBtn && id) {
          e.preventDefault();
          e.stopPropagation();
          App.handleSavedQueryDelete(id);
        } else if (query) {
          e.preventDefault();
          Utils.$('#query-input').value = query;
          Utils.$('#query-submit').disabled = false;
          App.handleQuery(new Event('submit'));
        }
      });
    }

    // Save current query
    const saveQueryBtn = Utils.$('#save-query-btn');
    if (saveQueryBtn) {
      saveQueryBtn.addEventListener('click', (e) => {
        e.preventDefault();
        App.handleSaveQuery();
      });
    }

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
        App.updateUI();
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
    App.updateUI();
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
    Utils.hide('#trello-instructions');
    Utils.hide('#salesforce-instructions');

    // Reset API key input state
    Utils.$('#api-key').style.display = 'block';
    Utils.$('#api-key').required = true;

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
      Utils.$('#api-key').placeholder = 'ghp_xxxxxxxxxxxxxxxxxxxx';
      Utils.$('#api-key-help').textContent = 'Generate a token with "repo" scope at GitHub Settings.';
    } else if (platform === 'trello') {
      Utils.show('#trello-instructions');
      Utils.$('#api-key-label').textContent = 'Trello Credentials';
      Utils.$('#api-key').placeholder = 'Your_API_Key:Your_Token';
      Utils.$('#api-key-help').textContent = 'Enter API Key and Token separated by a colon.';
    } else if (platform === 'salesforce') {
      Utils.show('#salesforce-instructions');
      Utils.$('#api-key-label').textContent = 'Salesforce Credentials';
      // Hide standard API key input for Salesforce (using OAuth popup instead)
      Utils.$('#api-key').style.display = 'none';
      Utils.$('#api-key').required = false;
      Utils.$('#api-key-help').textContent = 'Enter your Consumer Key and Secret above, then click Connect.';
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
      } else if (platform === 'salesforce') {
        // Salesforce requires OAuth popup flow
        const clientId = Utils.$('#sf-client-id')?.value?.trim();
        const clientSecret = Utils.$('#sf-client-secret')?.value?.trim();

        if (!clientId || !clientSecret) {
          throw new Error('Please enter Consumer Key (Client ID) and Consumer Secret');
        }

        // Generate PKCE
        const { codeVerifier, codeChallenge } = await API.generatePKCE();

        // Store code verifier for later use
        State.sfCodeVerifier = codeVerifier;
        State.sfClientId = clientId;
        State.sfClientSecret = clientSecret;

        // Open Salesforce authorization popup
        const authUrl = API.getSalesforceAuthUrl(clientId, codeChallenge);
        const popup = window.open(authUrl, 'salesforce_oauth', 'width=600,height=700');

        if (!popup) {
          throw new Error('Popup blocked. Please allow popups for this site.');
        }

        // Wait for user to authorize and return
        App.showToast('Complete authorization in the popup window...', 'info');

        // Check if popup closes
        const checkClosed = setInterval(async () => {
          if (popup.closed) {
            clearInterval(checkClosed);

            // Show custom modal for code input
            const modal = Utils.$('#sf-code-modal');
            const codeInput = Utils.$('#sf-auth-code');
            const submitBtn2 = Utils.$('#sf-code-submit');
            const cancelBtn = Utils.$('#sf-code-cancel');

            Utils.show('#sf-code-modal');
            codeInput.value = '';
            codeInput.focus();

            // Handle submit
            const handleSubmit = async () => {
              const code = codeInput.value.trim();
              if (!code) {
                App.showToast('Please enter the authorization code', 'error');
                return;
              }

              submitBtn2.classList.add('btn--loading');
              submitBtn2.disabled = true;

              try {
                // URL decode the code if needed
                let decodedCode = code;
                if (decodedCode.includes('%')) {
                  decodedCode = decodeURIComponent(decodedCode);
                }

                const result = await API.exchangeSalesforceCode(
                  decodedCode,
                  State.sfCodeVerifier,
                  State.sfClientId,
                  State.sfClientSecret
                );

                Utils.hide('#sf-code-modal');

                if (result.success) {
                  await State.fetchPlatforms();
                  Utils.show('#connect-success');
                  App.showToast('Salesforce connected successfully!', 'success');
                  setTimeout(() => App.navigate('query'), 1500);
                } else {
                  Utils.show('#connect-error');
                  Utils.$('#connect-error-message').textContent = result.error || 'Connection failed';
                }
              } catch (err) {
                Utils.hide('#sf-code-modal');
                Utils.show('#connect-error');
                Utils.$('#connect-error-message').textContent = err.message || 'Connection failed';
              } finally {
                submitBtn2.classList.remove('btn--loading');
                submitBtn2.disabled = false;
              }
            };

            // Handle cancel
            const handleCancel = () => {
              Utils.hide('#sf-code-modal');
            };

            // Event listeners (remove old ones first)
            submitBtn2.onclick = handleSubmit;
            cancelBtn.onclick = handleCancel;
            Utils.$('#sf-code-modal .modal__backdrop').onclick = handleCancel;

            // Enter key to submit
            codeInput.onkeydown = (e) => {
              if (e.key === 'Enter') handleSubmit();
              if (e.key === 'Escape') handleCancel();
            };

            submitBtn.classList.remove('btn--loading');
            submitBtn.disabled = false;
          }
        }, 1000);

        return; // Exit early for Salesforce popup flow
      } else {
        // Standard connection (Stripe, GitHub, Trello, or Zoho Refresh Token)
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
      // Load saved queries for one-click run
      App.loadSavedQueries();
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
    console.log('[DEBUG appendMessageToUI] msg:', msg);
    console.log('[DEBUG appendMessageToUI] msg.content:', msg.content);
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
      console.log('[DEBUG] Rendering chart:', msg.rawData.chart);
      const chartId = `chart-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      const chartContainer = document.createElement('div');
      chartContainer.className = 'chat-chart-container';
      chartContainer.innerHTML = `<canvas id="${chartId}"></canvas>`;

      // Append to the message content
      const contentEl = messageEl.querySelector('.chat-message__content');
      if (contentEl) {
        // Find the result-card__body and insert chart after the details element
        const resultCardBody = contentEl.querySelector('.result-card__body');
        if (resultCardBody) {
          const detailsInBody = resultCardBody.querySelector('details.view-details');
          if (detailsInBody && detailsInBody.parentNode === resultCardBody) {
            // Insert chart after the details element (below the table)
            try {
              // Use insertBefore with nextSibling, or appendChild if no next sibling
              if (detailsInBody.nextSibling) {
                resultCardBody.insertBefore(chartContainer, detailsInBody.nextSibling);
              } else {
                resultCardBody.appendChild(chartContainer);
              }
            } catch (e) {
              console.warn('[DEBUG] Failed to insertAfter, appending instead:', e);
              resultCardBody.appendChild(chartContainer);
            }
          } else {
            // No details element, append to end
            resultCardBody.appendChild(chartContainer);
          }
        } else {
          // Fallback: try to find details element in contentEl and insert after it
          const detailsEl = contentEl.querySelector('details.view-details');
          if (detailsEl && detailsEl.parentNode === contentEl) {
            try {
              if (detailsEl.nextSibling) {
                contentEl.insertBefore(chartContainer, detailsEl.nextSibling);
              } else {
                contentEl.appendChild(chartContainer);
              }
            } catch (e) {
              console.warn('[DEBUG] Failed to insertAfter in content, appending instead:', e);
              contentEl.appendChild(chartContainer);
            }
          } else {
            // Fallback: append to content element
            contentEl.appendChild(chartContainer);
          }
        }

        // Render the chart with a slight delay to ensure DOM is ready
        setTimeout(() => {
          const canvas = document.getElementById(chartId);
          if (canvas) {
            App.renderChart(chartId, msg.rawData.chart);
          } else {
            console.error('[DEBUG] Canvas element not found for chart:', chartId);
          }
        }, 150);
      } else {
        console.error('[DEBUG] Content element not found for chart insertion');
      }
    } else {
      console.log('[DEBUG] No chart data found. rawData:', msg.rawData);
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
   * Load and render saved queries
   */
  async loadSavedQueries() {
    const listEl = Utils.$('#saved-queries-list');
    if (!listEl || !State.isLoggedIn()) return;
    try {
      const saved = await API.getSavedQueries();
      App.renderSavedQueries(saved);
    } catch (err) {
      console.warn('Failed to load saved queries', err);
      listEl.innerHTML = '';
    }
  },

  /**
   * Render saved queries list into #saved-queries-list
   */
  renderSavedQueries(list) {
    const listEl = Utils.$('#saved-queries-list');
    const container = Utils.$('#saved-queries-container');
    if (!listEl || !container) return;
    if (!list || list.length === 0) {
      listEl.innerHTML = '';
      container.classList.add('hidden');
      return;
    }
    container.classList.remove('hidden');
    listEl.innerHTML = list.map((s) => {
      const name = Utils.escapeHtml(s.name);
      const queryAttr = Utils.escapeHtml(s.query_text);
      const platformAttr = Utils.escapeHtml(s.platform || '');
      return `
        <div class="saved-query-item" data-id="${s.id}" data-query="${queryAttr}" data-platform="${platformAttr}">
          <span class="saved-query-item__label">${name}</span>
          <button type="button" class="saved-query-item__run" title="Run">Run</button>
          <button type="button" class="saved-query-item__delete" title="Remove" aria-label="Remove">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      `;
    }).join('');
  },

  /**
   * Save current query as favorite (prompt for name)
   */
  async handleSaveQuery() {
    const input = Utils.$('#query-input');
    const query = input && input.value.trim();
    if (!query) {
      App.showToast('Enter a query first, then click save.', 'info');
      return;
    }
    // Use query text as name (truncated); save directly, no prompt
    const name = query.length > 120 ? query.slice(0, 117) + '...' : query;
    try {
      await API.saveQuery(name, query, State.activeSession === 'all' ? '' : State.activeSession);
      App.showToast('Added to saved queries.', 'success');
      App.loadSavedQueries();
    } catch (err) {
      const msg = err.message || '';
      // Check for duplicate query error messages
      if (msg.toLowerCase().includes('already have') || 
          msg.toLowerCase().includes('already exists') ||
          msg.toLowerCase().includes('unique') || 
          msg.includes('already') || 
          msg.includes('400')) {
        App.showToast('You already have a saved query with this name.', 'info');
      } else {
        App.showToast(msg || 'Failed to save query', 'error');
      }
    }
  },

  /**
   * Delete a saved query and refresh list
   */
  async handleSavedQueryDelete(id) {
    try {
      await API.deleteSavedQuery(id);
      App.showToast('Saved query removed.', 'success');
      App.loadSavedQueries();
    } catch (err) {
      App.showToast(err.message || 'Failed to delete', 'error');
    }
  },

  /**
   * Handle query submission
   */
  async handleQuery(e) {
    e.preventDefault();

    const input = Utils.$('#query-input');
    const query = input.value.trim();

    if (!query || State.isProcessing) return;

    // Hide autocomplete dropdown
    App.hideAutocomplete();

    // Add user message
    App.addChatMessage(query, 'user');

    // Clear input
    input.value = '';
    Utils.$('#query-submit').disabled = true;

    State.isProcessing = true;
    // Show typing indicator, but capture the ID/Element to update it
    App.showTypingIndicator();
    // Use ID selector according to showTypingIndicator implementation
    const typingTextElement = Utils.$('#typing-indicator .processing-step__text');

    try {
      // Determine platform context if in specific session
      let platform = null;
      if (State.activeSession !== 'all') {
        platform = State.activeSession;
      }

      let finalResponse = null;

      await API.processQueryStream(query, platform, (chunk) => {
        if (chunk.type === 'log') {
          // Find the processing loader container
          const typingContainer = Utils.$('#typing-indicator .processing-loader');

          if (typingContainer) {
            // Mark previous step as completed
            const lastStep = typingContainer.lastElementChild;
            if (lastStep) {
              lastStep.classList.remove('active');
              lastStep.classList.add('completed');

              // Replace spinner with checkmark
              const iconContainer = lastStep.querySelector('.processing-step__icon');
              if (iconContainer) {
                iconContainer.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-green-500"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
              }
            }

            // Create new active step
            const newStep = document.createElement('div');
            newStep.className = 'processing-step active';
            newStep.innerHTML = `
                    <div class="processing-step__icon"><div class="spinner spinner--sm"></div></div>
                    <span class="processing-step__text">${chunk.message}</span>
                `;
            typingContainer.appendChild(newStep);

            // Auto-scroll to bottom of chat if needed (optional but good UX)
            // Utils.scrollToBottom(); 
          }
        } else if (chunk.type === 'result') {
          finalResponse = chunk.payload;
        }
      });

      App.removeTypingIndicator();

      if (finalResponse && finalResponse.success) {
        // Debug: Log the full response to see chart data
        console.log('[DEBUG handleQuery] Full response:', finalResponse);
        console.log('[DEBUG handleQuery] Chart in response:', finalResponse.chart);

        if (finalResponse.logs) {
          App.renderLogs(finalResponse.logs);
        }
        App.addChatMessage(finalResponse, 'ai');
      } else {
        const errorMsg = finalResponse ? (finalResponse.error || 'Failed to process query') : 'No response received';
        App.addChatMessage({
          summary: errorMsg,
          data: null
        }, 'ai');
      }
    } catch (error) {
      console.error('Query error:', error);
      App.removeTypingIndicator();
      
      // Handle authentication errors
      if (error.message && (error.message.includes('session has expired') || error.message.includes('token'))) {
        // Don't show error message in chat, user will be redirected to login
        if (window.location.hash !== '#login') {
          window.location.hash = '#login';
        }
        return;
      }
      
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
    console.log('[DEBUG addChatMessage] Called with type:', type, 'content:', content);
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
          const renderer = new marked.Renderer();
          const linkRenderer = renderer.link;
          renderer.link = (href, title, text) => {
            const html = linkRenderer.call(renderer, href, title, text);
            return html.replace(/^<a /, '<a target="_blank" rel="noopener noreferrer" ');
          };
          parsedSummary = marked.parse(parsedSummary, { renderer: renderer });
        } catch (e) {
          console.error('Markdown parse error:', e);
        }
      }

      // Re-creating the result card HTML:
      messageContent = '';

      if (response.type === 'bulk_response' && Array.isArray(response.data)) {
        // Bulk Rendering
        const overallSummary = parsedSummary || 'Executed multiple actions.';
        messageContent += `<div style="margin-bottom:12px;">${overallSummary}</div>`;

        response.data.forEach(subResult => {
          // Use the platform from subResult, fallback to 'salesforce' for backward compatibility
          const subPlatform = subResult.platform || 'salesforce';
          const subConfig = API.platformConfig[subPlatform] || {};

          // Sub-summary
          let subSummaryRaw = subResult.summary || (subResult.success ? 'Action executed.' : 'Action failed.');
          let subParsed = typeof marked !== 'undefined' ? marked.parse(subSummaryRaw) : subSummaryRaw;

          let subTable = '';
          if (subResult.data && Array.isArray(subResult.data) && subResult.data.length > 0) {
            const h = Object.keys(subResult.data[0]).slice(0, 4);
            const ths = h.map(c => `<th>${Utils.capitalize(c)}</th>`).join('');
            const trs = subResult.data.map(item => {
              const tds = h.map(k => {
                let value = item[k];

                // Skip formatting if value is an object (shouldn't happen, but safety check)
                if (typeof value === 'object' && value !== null && !(value instanceof Date)) {
                  value = JSON.stringify(value);
                }

                // Format currency values
                if ((k === 'amount' || k === 'total_spend' || k === 'balance' || k === 'available' || k === 'pending' || k === 'total') && typeof value === 'number') {
                  value = new Intl.NumberFormat('en-US', { style: 'currency', currency: item.currency || 'USD' }).format(value);
                }
                // Format dates - only if value is a valid date string/number
                if ((k === 'date' || k === 'created') && value && typeof value !== 'object') {
                  try {
                    const date = new Date(value);
                    if (!isNaN(date.getTime())) {  // Check if date is valid
                      value = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                    }
                  } catch (e) {
                    // Keep original value if parsing fails
                  }
                }
                return `<td>${Utils.escapeHtml(String(value || '-'))}</td>`;
              }).join('');
              return `<tr>${tds}</tr>`;
            }).join('');

            subTable = `
                   <details class="view-details">
                     <summary class="view-details__header">
                       <span class="view-details__icon">📋</span>
                       View Details (${subResult.data.length})
                       <span class="view-details__chevron">▼</span>
                     </summary>
                     <div class="view-details__content"><div class="table-container"><table class="result-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table></div></div>
                   </details>
                 `;
          } else if (subResult.error) {
            subParsed = `<span style="color:var(--color-error)">❌ ${subResult.error}</span>`;
          } else if (subResult.success && subResult.data && Array.isArray(subResult.data) && subResult.data.length === 0) {
            // Success but no data (e.g., customer found but no invoices)
            subParsed += `<div style="margin-top: 8px; color: var(--color-text-secondary); font-size: 0.9em;">No additional data available.</div>`;
          }

          messageContent += `
               <div class="result-card" style="margin-bottom: 12px; border-left: 3px solid ${subConfig.color || '#ccc'};">
                 <div class="result-card__header">
                   <span class="result-card__platform">
                     <span style="width: 16px; height: 16px; display: inline-flex;">${subConfig.icon || ''}</span>
                     ${subConfig.name || subPlatform}
                   </span>
                 </div>
                 <div class="result-card__body ai-response">
                   ${subParsed}
                   ${subTable}
                 </div>
               </div>
             `;
        });

      } else {
        // Check if this is a knowledge query answer
        if (response.data && Array.isArray(response.data) && response.data.length > 0 && response.data[0].type === 'knowledge') {
          const knowledgeData = response.data[0];
          const answer = knowledgeData.answer || parsedSummary;
          const topic = knowledgeData.topic || 'Information';
          
          // Format knowledge answer with markdown support
          let formattedAnswer = answer;
          if (typeof marked !== 'undefined') {
            try {
              formattedAnswer = marked.parse(answer);
            } catch (e) {
              console.error('Markdown parse error for knowledge answer:', e);
            }
          }
          
          messageContent = `
             <div class="result-card">
             <div class="result-card__header">
               <span class="result-card__platform">
                 <span style="width: 16px; height: 16px; display: inline-flex;">${config.icon || '📚'}</span>
                 ${topic}
               </span>
             </div>
             <div class="result-card__body ai-response">
               ${formattedAnswer}
             </div>
           </div>
         `;
        } else {
          // Standard Single Response (Existing Logic)
          messageContent = `
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
        }
      }

      // Determine table content with collapsible View Details
      let tableContent = '';
      // Support both nested (response.data.data) and direct (response.data as array) formats
      let items = null;
      if (response.data && Array.isArray(response.data) && response.data.length > 0) {
        items = response.data;
      } else if (response.data && response.data.data && Array.isArray(response.data.data) && response.data.data.length > 0) {
        items = response.data.data;
      }

      if (items && items.length > 0) {
        const itemCount = items.length;
        const type = App.detectResultType(items, platform);

        // Define columns based on type
        let cols = [];
        const item0 = items[0];
        if (platform === 'github') {
          if (item0.sha) cols = ['Commit', 'Message', 'Author', 'Date'];
          else if (item0.merged !== undefined) cols = ['PR #', 'Title', 'State', 'Author'];
          else if (item0.number) cols = ['Issue #', 'Title', 'State', 'Labels'];
          else cols = ['Name', 'Description', 'Stars', 'Updated'];
        } else if (platform === 'stripe') {
          if (item0.available !== undefined || item0.pending !== undefined) {
            // Balance data
            cols = ['Available', 'Pending', 'Total', 'Currency'];
          } else if (item0.amount) cols = ['Amount', 'Status', 'Customer', 'Date'];
          else if (item0.email && (item0.balance !== undefined || item0.total_spend !== undefined)) {
            // Show total_spend if available (more useful than account balance)
            cols = item0.total_spend !== undefined ? ['Name', 'Email', 'Total Spend'] : ['Name', 'Email', 'Balance'];
          } else if (item0.email) cols = ['Name', 'Email', 'Created'];
          else cols = ['ID', 'Name', 'Status'];
        } else if (platform === 'zendesk') {
          if (item0.subject) cols = ['ID', 'Subject', 'Status', 'Priority'];
          else cols = ['Name', 'Email', 'Role'];

        } else if (platform === 'trello') {
          if (type === 'cards') cols = ['Name', 'List', 'Due', 'URL'];
          else if (type === 'boards') cols = ['Name', 'Description', 'URL'];
          else if (type === 'lists') cols = ['Name', 'Board ID', 'List ID'];
        } else if (platform === 'salesforce') {
          if (type === 'leads') cols = ['Name', 'Email', 'Company', 'Status'];
          else if (type === 'contacts') cols = ['Name', 'Email', 'Account', 'Title'];
          else if (type === 'accounts') cols = ['Name', 'Industry', 'City', 'Phone'];
          else if (type === 'opportunities') cols = ['Name', 'Amount', 'Stage', 'Close Date'];
        } else if (platform === 'zoho') {
          if (type === 'deals') cols = ['Name', 'Amount', 'Stage', 'Closing Date'];
          else if (type === 'contacts') cols = ['Name', 'Email', 'Account', 'Created'];
          else if (type === 'leads') cols = ['Name', 'Email', 'Company', 'Status'];
          else if (type === 'accounts') cols = ['Name', 'Industry', 'Website', 'Created'];
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

      // Standard response: append table and close divs
      // Skip table for knowledge queries (they're informational, not data tables)
      if (response.type !== 'bulk_response') {
        const isKnowledgeQuery = response.data && Array.isArray(response.data) && response.data.length > 0 && response.data[0].type === 'knowledge';
        if (!isKnowledgeQuery) {
          messageContent += tableContent + `</div></div>`;
        } else {
          // Knowledge query already has complete HTML, just close if needed
          if (!messageContent.includes('</div></div>')) {
            messageContent += `</div></div>`;
          }
        }
      }
    }

    const message = {
      type,
      content: messageContent,
      // Store raw data too for potential future re-rendering
      rawData: type === 'ai' ? content : null
    };

    // Debug: Log chart data if present
    if (type === 'ai') {
      console.log('[DEBUG addChatMessage] Full content object:', content);
      console.log('[DEBUG addChatMessage] Chart in content:', content?.chart);
      console.log('[DEBUG addChatMessage] rawData will be:', content);
      console.log('[DEBUG addChatMessage] rawData.chart will be:', content?.chart);
    }

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
      console.log('[DEBUG addChatMessage] About to append, message:', message);
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
      if (item.available !== undefined || item.pending !== undefined) return 'balance';
      if (item.amount) return 'transactions'; // or invoices/charges
      if (item.email && (item.balance !== undefined || item.total_spend !== undefined || item.name)) return 'customers';
      return 'customers';
    }
    if (platform === 'zendesk') {
      if (item.subject) return 'tickets';
      return 'users';
    }
    if (platform === 'trello') {
      if (item.idList || (item.url && item.url.includes('/c/'))) return 'cards';
      if (item.prefs || (item.url && item.url.includes('/b/'))) return 'boards';
      if (item.idBoard && item.name) return 'lists';
    }
    if (platform === 'salesforce') {
      if (item.Status && item.Company) return 'leads';
      if (item.Account && item.Title) return 'contacts';
      if (item.Industry || item.BillingCity) return 'accounts';
      if (item.StageName || item.Amount) return 'opportunities';
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
  renderTableRow(item, type, platform) {
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

    if (type === 'balance') {
      return `
        <td>${Utils.formatCurrency(item.available, item.currency || 'USD')}</td>
        <td>${Utils.formatCurrency(item.pending, item.currency || 'USD')}</td>
        <td>${Utils.formatCurrency(item.total, item.currency || 'USD')}</td>
        <td>${item.currency || 'USD'}</td>
      `;
    }

    if (type === 'customers') {
      // Prefer total_spend over balance (more useful metric)
      if (item.total_spend !== undefined) {
        return `
          <td>${item.name || '-'}</td>
          <td>${item.email || '-'}</td>
          <td>${Utils.formatCurrency(item.total_spend, item.currency || 'USD')}</td>
        `;
      } else if (item.balance !== undefined) {
        return `
          <td>${item.name || '-'}</td>
          <td>${item.email || '-'}</td>
          <td>${Utils.formatCurrency(item.balance, item.currency || 'USD')}</td>
        `;
      } else {
        return `
          <td>${item.id}</td>
          <td>${item.name || '-'}</td>
          <td>${item.email || '-'}</td>
          <td>${item.created ? Utils.formatDate(item.created) : '-'}</td>
        `;
      }
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
        <td><strong><a href="${item.html_url || item.url}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: none;">${Utils.escapeHtml(item.name || '-')}</a></strong></td>
        <td>${Utils.escapeHtml((item.description || '-').substring(0, 50))}</td>
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



    if (type === 'cards') {
      const url = item.url || item.shortUrl;
      return `
            <td>${Utils.escapeHtml(item.name || '-')}</td>
            <td>${Utils.escapeHtml(item.list_name || '-')}</td>
            <td>${item.due ? Utils.formatDate(item.due) : '-'}</td>
            <td><a href="${url}" target="_blank" rel="noopener noreferrer" class="link-external">View Card ↗</a></td>
        `;
    }

    if (type === 'boards') {
      return `
            <td><strong>${Utils.escapeHtml(item.name || '-')}</strong></td>
            <td>${Utils.escapeHtml((item.desc || '-').substring(0, 50))}</td>
            <td><a href="${item.url}" target="_blank" rel="noopener noreferrer" style="color: var(--color-primary); text-decoration: none;">View Board ↗</a></td>
        `;
    }

    if (type === 'lists') {
      return `
            <td><strong>${Utils.escapeHtml(item.name || '-')}</strong></td>
            <td>${Utils.escapeHtml(item.idBoard || '-')}</td>
            <td><code>${item.id}</code></td>
        `;
    }

    // Salesforce types
    if (type === 'leads') {
      return `
        <td><strong>${Utils.escapeHtml(item.Name || '-')}</strong></td>
        <td>${Utils.escapeHtml(item.Email || '-')}</td>
        <td>${Utils.escapeHtml(item.Company || '-')}</td>
        <td><span class="badge badge--info">${Utils.escapeHtml(item.Status || '-')}</span></td>
      `;
    }

    if (type === 'contacts') {
      const accountName = item.Account ? item.Account.Name : '-';
      return `
        <td><strong>${Utils.escapeHtml(item.Name || '-')}</strong></td>
        <td>${Utils.escapeHtml(item.Email || '-')}</td>
        <td>${Utils.escapeHtml(accountName)}</td>
        <td>${Utils.escapeHtml(item.Title || '-')}</td>
      `;
    }

    if (type === 'accounts') {
      return `
        <td><strong>${Utils.escapeHtml(item.Name || '-')}</strong></td>
        <td>${Utils.escapeHtml(item.Industry || '-')}</td>
        <td>${Utils.escapeHtml(item.BillingCity || '-')}</td>
        <td>${Utils.escapeHtml(item.Phone || '-')}</td>
      `;
    }

    if (type === 'opportunities') {
      const accountName = item.Account ? item.Account.Name : '-';
      return `
        <td><strong>${Utils.escapeHtml(item.Name || '-')}</strong></td>
        <td>$${(item.Amount || 0).toLocaleString()}</td>
        <td><span class="badge badge--info">${Utils.escapeHtml(item.StageName || '-')}</span></td>
        <td>${item.CloseDate || '-'}</td>
      `;
    }

    if (type === 'deals') {
      // Format amount - handle both numeric and string values
      let amountValue = item.amount || item.Amount || 0;
      if (typeof amountValue === 'string') {
        // Remove currency symbols, commas, spaces
        amountValue = amountValue.replace(/[$,\s]/g, '').trim();
        amountValue = parseFloat(amountValue) || 0;
      }
      const formattedAmount = typeof amountValue === 'number' ? amountValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : amountValue;

      return `
        <td><strong>${Utils.escapeHtml(item.name || item.Deal_Name || '-')}</strong></td>
        <td>$${formattedAmount}</td>
        <td><span class="badge badge--info">${Utils.escapeHtml(item.stage || item.Stage || '-')}</span></td>
        <td>${item.closing_date || item.Closing_Date || '-'}</td>
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

    // Generic Fallback
    const keys = Object.keys(item).slice(0, 4);
    return keys.map(k => {
      let val = item[k];
      if (typeof val === 'object' && val !== null) val = JSON.stringify(val);
      return `<td>${Utils.escapeHtml(String(val || '-'))}</td>`;
    }).join('');
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
   * Autocomplete state
   */
  autocompleteState: {
    suggestions: [],
    selectedIndex: -1,
    debounceTimer: null,
    isSelecting: false, // Flag to prevent autocomplete when selecting
  },

  /**
   * Handle autocomplete input
   */
  async handleAutocomplete(queryText) {
    // Clear previous timer
    if (App.autocompleteState.debounceTimer) {
      clearTimeout(App.autocompleteState.debounceTimer);
    }

    // Hide if query is too short
    if (!queryText || queryText.trim().length < 2) {
      App.hideAutocomplete();
      return;
    }

    // Debounce API call
    App.autocompleteState.debounceTimer = setTimeout(async () => {
      try {
        const result = await API.getQuerySuggestions(queryText.trim(), 10);
        App.autocompleteState.suggestions = result.suggestions || [];
        App.autocompleteState.selectedIndex = -1;
        
        if (App.autocompleteState.suggestions.length > 0) {
          App.renderAutocomplete(App.autocompleteState.suggestions);
        } else {
          App.hideAutocomplete();
        }
      } catch (err) {
        console.warn('Autocomplete error:', err);
        App.hideAutocomplete();
      }
    }, 300); // 300ms debounce
  },

  /**
   * Render autocomplete dropdown
   */
  renderAutocomplete(suggestions) {
    const dropdown = Utils.$('#autocomplete-dropdown');
    if (!dropdown) return;

    if (!suggestions || suggestions.length === 0) {
      App.hideAutocomplete();
      return;
    }

    // Store suggestions - use index to look up from array to avoid attribute encoding issues
    dropdown.innerHTML = suggestions.map((suggestion, index) => {
      const typeIcon = suggestion.type === 'saved' ? '💾' : 
                       suggestion.type === 'history' ? '🕒' : '💡';
      const platformBadge = suggestion.platform && suggestion.platform !== 'all' 
        ? `<span class="autocomplete-item__platform">${suggestion.platform}</span>` 
        : '';
      
      return `
        <div class="autocomplete-item ${index === App.autocompleteState.selectedIndex ? 'selected' : ''}" 
             data-index="${index}">
          <span class="autocomplete-item__icon">${typeIcon}</span>
          <span class="autocomplete-item__text">
            <span class="autocomplete-item__label">${Utils.escapeHtml(suggestion.label)}</span>
            ${platformBadge}
          </span>
        </div>
      `;
    }).join('');

    // Store suggestions array on the dropdown element for lookup
    dropdown._suggestions = suggestions;

    // Add click handlers
    dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
      item.addEventListener('click', () => {
        // Get the index and look up the full text from the stored suggestions array
        const index = parseInt(item.getAttribute('data-index'), 10);
        const suggestion = dropdown._suggestions[index];
        const text = suggestion ? suggestion.text : '';
        App.selectAutocompleteSuggestion(text);
      });
    });

    dropdown.classList.remove('hidden');
  },

  /**
   * Hide autocomplete dropdown
   */
  hideAutocomplete() {
    const dropdown = Utils.$('#autocomplete-dropdown');
    if (dropdown) {
      dropdown.classList.add('hidden');
    }
    App.autocompleteState.selectedIndex = -1;
  },

  /**
   * Handle keyboard navigation in autocomplete
   */
  handleAutocompleteKeydown(e) {
    const dropdown = Utils.$('#autocomplete-dropdown');
    if (!dropdown || dropdown.classList.contains('hidden')) {
      return;
    }

    const suggestions = App.autocompleteState.suggestions;
    if (suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        App.autocompleteState.selectedIndex = Math.min(
          App.autocompleteState.selectedIndex + 1,
          suggestions.length - 1
        );
        App.renderAutocomplete(suggestions);
        App.scrollAutocompleteToSelected();
        break;

      case 'ArrowUp':
        e.preventDefault();
        App.autocompleteState.selectedIndex = Math.max(
          App.autocompleteState.selectedIndex - 1,
          -1
        );
        App.renderAutocomplete(suggestions);
        App.scrollAutocompleteToSelected();
        break;

      case 'Enter':
        if (App.autocompleteState.selectedIndex >= 0 && App.autocompleteState.selectedIndex < suggestions.length) {
          e.preventDefault();
          const selected = suggestions[App.autocompleteState.selectedIndex];
          if (selected && selected.text) {
            App.selectAutocompleteSuggestion(selected.text);
          }
          // Don't submit form when selecting from autocomplete
          return;
        }
        break;

      case 'Escape':
        e.preventDefault();
        App.hideAutocomplete();
        break;
    }
  },

  /**
   * Select an autocomplete suggestion
   */
  selectAutocompleteSuggestion(text) {
    const input = Utils.$('#query-input');
    if (input) {
      // Set flag to prevent autocomplete from showing again
      App.autocompleteState.isSelecting = true;
      
      // Hide dropdown first
      App.hideAutocomplete();
      
      // Set the value
      input.value = text;
      
      // Enable submit button
      const submitBtn = Utils.$('#query-submit');
      if (submitBtn) {
        submitBtn.disabled = !text.trim();
      }
      
      // Focus input
      input.focus();
      
      // Reset flag after a short delay
      setTimeout(() => {
        App.autocompleteState.isSelecting = false;
      }, 100);
    }
  },

  /**
   * Scroll autocomplete to selected item
   */
  scrollAutocompleteToSelected() {
    const dropdown = Utils.$('#autocomplete-dropdown');
    if (!dropdown) return;

    const selectedItem = dropdown.querySelector('.autocomplete-item.selected');
    if (selectedItem) {
      selectedItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
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
  /**
   * Render Chart.js Chart with Modern UI
   */
  renderChart(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Global Aesthetics
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';

    // Enhance Datasets with Gradients and Styling
    if (config.data && config.data.datasets) {
      config.data.datasets.forEach((ds, i) => {
        // Generate a color based on index if not set
        const colors = [
          ['#6366f1', '#8b5cf6'], // Indigo -> Purple
          ['#10b981', '#3b82f6'], // Emerald -> Blue
          ['#f59e0b', '#ef4444'], // Amber -> Red
        ];
        const colorPair = colors[i % colors.length];

        if (config.type === 'bar' || config.type === 'line') {
          // Create Gradient
          const gradient = ctx.createLinearGradient(0, 0, 0, 400);
          gradient.addColorStop(0, colorPair[0]);
          gradient.addColorStop(1, 'rgba(99, 102, 241, 0.05)'); // Fade to transparent

          ds.backgroundColor = gradient;
          ds.borderColor = colorPair[0];
          ds.borderWidth = config.type === 'line' ? 3 : 0;
          ds.borderRadius = 8; // Rounded top corners
          ds.barPercentage = 0.6;

          // Shadow for Lines
          if (config.type === 'line') {
            ds.tension = 0.4; // Smooth curve
            ds.fill = true;
            ds.pointBackgroundColor = '#1f2937';
            ds.pointBorderColor = colorPair[0];
            ds.pointBorderWidth = 2;
            ds.pointRadius = 4;
            ds.pointHoverRadius = 6;
          }
        } else if (config.type === 'doughnut' || config.type === 'pie') {
          ds.borderWidth = 0;
          ds.hoverOffset = 20;
          ds.borderRadius = 5;
          // Use palette for doughnut segments
          ds.backgroundColor = [
            '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6'
          ];
        }
      });
    }

    // Custom Glassmorphism Tooltip
    const externalTooltipHandler = (context) => {
      // Tooltip Element
      let tooltipEl = document.getElementById('chartjs-tooltip');

      // Create element on first render
      if (!tooltipEl) {
        tooltipEl = document.createElement('div');
        tooltipEl.id = 'chartjs-tooltip';
        tooltipEl.style.opacity = 1;
        tooltipEl.style.position = 'absolute';
        tooltipEl.style.pointerEvents = 'none';
        tooltipEl.style.background = 'rgba(17, 24, 39, 0.8)'; // Dark semi-transparent
        tooltipEl.style.backdropFilter = 'blur(12px)';
        tooltipEl.style.webkitBackdropFilter = 'blur(12px)';
        tooltipEl.style.borderRadius = '12px';
        tooltipEl.style.border = '1px solid rgba(255, 255, 255, 0.1)';
        tooltipEl.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.5)';
        tooltipEl.style.color = '#fff';
        tooltipEl.style.padding = '12px';
        tooltipEl.style.transition = 'all 0.1s ease';
        tooltipEl.style.zIndex = '100';
        tooltipEl.style.fontFamily = "'Inter', sans-serif";
        tooltipEl.style.transform = 'translate(-50%, 0)'; // Center horizontally
        document.body.appendChild(tooltipEl);
      }

      const tooltipModel = context.tooltip;

      // Hide if no tooltip
      if (tooltipModel.opacity === 0) {
        tooltipEl.style.opacity = 0;
        return;
      }

      // Set content
      if (tooltipModel.body) {
        const titleLines = tooltipModel.title || [];
        const bodyLines = tooltipModel.body.map(b => b.lines);

        let innerHtml = '<div style="margin-bottom: 8px; font-weight: 600; font-size: 13px; color: #a5b4fc;">';
        titleLines.forEach(title => {
          innerHtml += `<span>${title}</span>`;
        });
        innerHtml += '</div>';

        innerHtml += '<div style="display: flex; flex-direction: column; gap: 4px;">';
        bodyLines.forEach((body, i) => {
          const colors = tooltipModel.labelColors[i];
          const span = `<span style="display:inline-block; width: 8px; height: 8px; border-radius: 50%; background:${colors.backgroundColor}; margin-right: 8px;"></span>`;
          // Clean up value (remove "Subject: " prefix if present)
          let text = body[0];
          if (text.includes(':')) {
            const parts = text.split(':');
            if (parts.length > 1) {
              text = `<span style="color: #94a3b8;">${parts[0]}:</span> <span style="font-weight: 500; color: #fff;">${parts.slice(1).join(':')}</span>`;
            }
          }
          innerHtml += `<div style="font-size: 13px; display: flex; align-items: center;">${span}${text}</div>`;
        });
        innerHtml += '</div>';

        tooltipEl.innerHTML = innerHtml;
      }

      const position = context.chart.canvas.getBoundingClientRect();
      const bodyFont = Chart.defaults.font; // Just to get size estimate if needed

      // Position
      tooltipEl.style.opacity = 1;
      tooltipEl.style.left = position.left + window.pageXOffset + tooltipModel.caretX + 'px';
      tooltipEl.style.top = position.top + window.pageYOffset + tooltipModel.caretY - 10 + 'px'; // Slight offset up
    };

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
              display: config.type === 'doughnut' || config.type === 'pie',
              position: 'bottom',
              labels: {
                usePointStyle: true,
                padding: 20,
                boxWidth: 8,
                color: '#9ca3af',
                font: { size: 12 }
              }
            },
            tooltip: {
              enabled: false, // Disable default
              external: externalTooltipHandler
            }
          },
          scales: (config.type === 'doughnut' || config.type === 'pie') ? {} : {
            y: {
              beginAtZero: true,
              grid: {
                color: 'rgba(255, 255, 255, 0.05)',
                drawBorder: false,
                borderDash: [5, 5] // Dashed grid lines
              },
              ticks: {
                padding: 10,
                color: '#9ca3af',
                font: { size: 11 }
              },
              border: { display: false } // Remove axis line
            },
            x: {
              grid: { display: false },
              ticks: {
                padding: 10,
                color: '#9ca3af',
                font: { size: 11 }
              },
              border: { display: false }
            }
          },
          layout: {
            padding: 20
          },
          interaction: {
            mode: 'index',
            intersect: false,
          },
          animation: {
            duration: 1000,
            easing: 'easeOutQuart'
          }
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
