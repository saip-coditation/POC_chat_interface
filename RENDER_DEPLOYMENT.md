# Render Deployment & Troubleshooting

## Fast deploys (~2–3 min)

- **sentence-transformers is not installed** on Render so the build stays fast.
- **Knowledge answers on Render** use **direct answers from render_knowledge (same topics as seed_platform_knowledge)** (no RAG, no embeddings): e.g. “How do I clone a repository?” returns a fixed answer. Other knowledge questions get: *“I can only answer a few questions here. Try: How do I clone a repository?”*
- Full RAG + embeddings still runs when **not** on Render (local or other hosts).

## "No response received" Error

If queries like "Show me trello boards" return **"No response received"**:

1. **Render timeout (~30s on free tier)** – The request exceeds Render's limit. On cold start, the app can take 50+ seconds to wake; first requests may time out.
2. **Trello/OpenAI unreachable** – Render may block outbound calls to `api.trello.com` or `api.openai.com`. Check Render logs for `APIConnectionError` or `Connection error`.
3. **Platform not connected** – Ensure Trello (or the relevant platform) is connected in the app and credentials are valid.

**What we do:**
- Trello requests use a 25s timeout to fail fast instead of hanging.
- Local embeddings (sentence-transformers) are preloaded on Render so the first knowledge query is faster.

---

## "Embedding generation failed" Error

If you see **"Error processing knowledge query: Embedding generation failed"** on Render, it usually means:

1. **`OPENAI_API_KEY` is missing or invalid** – The RAG/knowledge feature needs embeddings via the OpenAI API.
2. **Network or API limits** – Render can reach OpenAI, but rate limits or billing issues may apply.

### Fix: Set Environment Variables on Render

1. In the **Render Dashboard**, open your **Web Service**.
2. Go to **Environment** (sidebar).
3. Add these variables (mark sensitive ones as **Secret**):
   - `OPENAI_API_KEY` – Your OpenAI API key from https://platform.openai.com/api-keys
   - `SECRET_KEY` – A strong Django secret (generate with `openssl rand -hex 32`)
   - `ENCRYPTION_KEY` – Generate with:  
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `ALLOWED_HOSTS` – Your Render URL, e.g. `yourapp.onrender.com`
   - `DATABASE_URL` – If using PostgreSQL (Render provides this automatically)
4. **Save changes** and **trigger a redeploy**.

### Fallback Without OpenAI

For common questions like **"How do I clone a repository?"**, a keyword-based fallback runs when embeddings fail. You’ll still get an answer, but RAG search and other knowledge queries will only work once `OPENAI_API_KEY` is set.

### Required Variables for Full Functionality

| Variable          | Required for                  |
|------------------|-------------------------------|
| `OPENAI_API_KEY` | RAG, embeddings, AI answers   |
| `SECRET_KEY`     | Django security               |
| `ENCRYPTION_KEY` | Encrypted platform credentials|
| `ALLOWED_HOSTS`  | CSRF / host validation        |
| `CORS_ALLOWED_ORIGINS` | Frontend domain (if different) |

### Using OpenRouter Instead of OpenAI

If you use OpenRouter (key starts with `sk-or-`), `OPENAI_API_KEY` should be set to that key. The embedding code will use OpenRouter’s embedding endpoint.
