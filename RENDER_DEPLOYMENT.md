# Render Deployment & Troubleshooting

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
