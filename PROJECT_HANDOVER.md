# Chat Interface (DataBridge AI)

This document serves as a comprehensive guide for the Chat Interface project (DataBridge AI), including setup instructions, crucial links, and credential management guides.

## 📌 Important Links & Credentials

### **Zoho API Console**
*   **Link**: [https://api-console.zoho.in/client/1000.KIP35Q5XY5NCCSLHDHT1J4PZ9VI2BM](https://api-console.zoho.in/client/1000.KIP35Q5XY5NCCSLHDHT1J4PZ9VI2BM)
*   **Usage**: Manage Zoho OAuth Client ID (`1000.KIP35Q5XY5NCCSLHDHT1J4PZ9VI2BM`) and Client Secret. Ensure redirect URIs are correctly configured for your environment (e.g., `http://localhost:8000/api/platforms/zoho/callback/`).

### **Stripe Dashboard**
*   **Link**: [https://dashboard.stripe.com/acct_1SpQgM2f4RjAwI8m/test/dashboard](https://dashboard.stripe.com/acct_1SpQgM2f4RjAwI8m/test/dashboard)
*   **Usage**: View test data, manage API keys (Publishable/Secret keys), and monitor transactions. This link points to the test mode dashboard for account `acct_1SpQgM2f4RjAwI8m`.

---

## 🔑 GitHub Personal Access Token (PAT) Generation Guide

To interact with GitHub repositories via the application or command line (for fetching data or code), you may need a Personal Access Token. Follow these detailed steps:

1.  **Log in to GitHub**: Go to [https://github.com](https://github.com) and sign in.
2.  **Access Settings**: Click your profile photo in the top-right corner and select **Settings**.
3.  **Developer Settings**: Scroll down to the bottom of the left sidebar and click **Developer settings**.
4.  **Personal Access Tokens**:
    *   Click **Personal access tokens** in the left sidebar.
    *   Select **Tokens (classic)** (recommended for general compatibility).
5.  **Generate New Token**:
    *   Click the **Generate new token** button (select **Generate new token (classic)** if prompted).
    *   **Note**: Give your token a descriptive name, e.g., "Chat Interface Project Token".
    *   **Expiration**: Choose an expiration period (e.g., 30 days, 90 days, or No expiration if appropriate for your security policy).
    *   **Select Scopes**: Check the boxes for the permissions you need. Common scopes include:
        *   `repo` (Full control of private repositories)
        *   `workflow` (Update GitHub Action workflows)
        *   `read:user` (Read user profile data)
6.  **Copy Token**:
    *   Click **Generate token** at the bottom.
    *   **IMPORTANT**: Copy the token immediately. You will **not** be able to see it again once you leave the page.
    *   Store it securely in your `.env` file or password manager.

---

## 🚀 Project Overview & Setup

### **Summary**
DataBridge AI is a SaaS web application allowing natural language queries on business data from Stripe and Zendesk. It features a Django REST Framework backend and a vanilla JS/CSS frontend.

### **Quick Setup**

#### **1. Backend (Django)**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure your keys in .env
python manage.py migrate
python manage.py runserver
```

#### **2. Frontend**
The frontend is a static SPA. Serve it using any static server:
```bash
# From project root
python -m http.server 5500
```
Access at: `http://localhost:5500`

---

## 🔄 Project Architecture & Flow

The application uses a **Multi-Agent Architecture** to process natural language queries:

1.  **Request Handler**: Receives the user's query via the API.
2.  **Agent 1: Classifier (Route)**:
    *   Determines which platform the query is targeting (Stripe, Zoho, or GitHub).
    *   Uses OpenAI with fallback keyword matching.
3.  **Agent 2: Planner (Interpret)**:
    *   Converts the natural language query into specific API parameters (Actions & Filters).
    *   Example: "Show me high value deals" -> `action: list_deals`, `filters: {amount_gt: 10000}`.
4.  **Agent 3: Fetcher (Execute)**:
    *   Executes the determined action against the platform's API using standard clients (`stripe`, `requests`).
    *   Handles pagination and error checking.
5.  **Agent 4: Analyst (Visualize)**:
    *   Analyzes the fetched data to see if a chart is appropriate.
    *   Generates configuration for Line, Bar, or Doughnut charts if trends or breakdowns are detected.
6.  **Agent 5: Summarizer (Narrate)**:
    *   Feeds the raw data and original query back to OpenAI.
    *   Generates a human-readable summary of the findinds.

### **OpenAI Integration**
*   **Model**: Uses `gpt-4o-mini` (via OpenRouter or Native).
*   **System Prompts**: Located in `backend/utils/openai_client.py`. Specialized prompts exist for:
    *   Platform Detection
    *   Query Parameter Generation (Stripe/Zoho/GitHub rules)
    *   Result Summarization

---

## 📂 Deliverables & Resources

### **Output Videos**
> **[Google Drive Link: Project Demos & Output Videos](https://drive.google.com/drive/folders/1_h3QJw6ZSBbwxnYO4mf__wsdwwz0V49a)**

### **GitHub Repository & Push Guide**
To push this project to a new GitHub repository, follow these steps:

1.  **Initialize Git** (if not already done):
    ```bash
    git init
    ```
2.  **Add Files**:
    ```bash
    git add .
    ```
3.  **Commit Changes**:
    ```bash
    git commit -m "Initial commit: Chat Interface with Stripe, Zoho, and GitHub support"
    ```
4.  **Rename Branch** (optional but recommended):
    ```bash
    git branch -M main
    ```
5.  **Add Remote Origin**:
    *   Replace `YOUR_USERNAME` and `REPO_NAME` with your actual details.
    ```bash
    git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git
    ```
6.  **Push to GitHub**:
    *   You will be prompted for a Username and Password.
    *   **Username**: Your GitHub username.
    *   **Password**: Paste the **Personal Access Token (PAT)** you generated earlier (NOT your login password).
    ```bash
    git push -u origin main
    ```

---

## ❓ Example Queries & Results

Here are tested queries you can use to demonstrate the system:

### **Stripe**
*   **Query**: *"Show me unpaid invoices"*
    *   **Result**: Lists invoices with status `open`, showing Customer, Amount, and Due Date.
*   **Query**: *"How much revenue did we make last week?"*
    *   **Result**: Displays total revenue for the previous week with a comparison trend.
*   **Query**: *"List all failed charges"*
    *   **Result**: Shows a list of failed transactions to help identify payment issues.

### **Zoho CRM**
*   **Query**: *"Show me won deals over 10k"*
    *   **Result**: Lists deals with stage `Closed Won` and amount > 10,000.
*   **Query**: *"List contacts from Mumbai"*
    *   **Result**: distinct list of contacts where City is 'Mumbai'.
*   **Query**: *"Breakdown deals by stage"*
    *   **Result**: Generates a **Doughnut Chart** visualizing deal distribution.

### **GitHub**
*   **Query**: *"Summarize the facebook/react repo"*
    *   **Result**: detailed summary including stars, forks, open issues, and description.
*   **Query**: *"Show me open pull requests in this repo"*
    *   **Result**: Lists active PRs with their authors and build status.
*   **Query**: *"List recent commits"*
    *   **Result**: Displays the latest commit history with messages and authors.

