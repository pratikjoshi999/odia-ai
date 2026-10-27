# Configurable AI Agent Framework

An incremental MVP framework for launching configurable conversational agents. The default profile is Odisha AI; a sample Nimble AI counselling profile is included.

## Agent profiles

The active agent is selected with `AGENT_PROFILE`; its reusable configuration is stored in YAML:

- `AGENT_PROFILE` selects a YAML profile under `backend/app/config/agents/`.
- `AGENT_CONFIG_DIR` optionally changes the profile directory.
- YAML profiles define the UI identity, prompt file, domain policy, and knowledge-base folder.
- `BACKEND_PORT`, `FRONTEND_ORIGIN`, `VITE_API_BASE_URL`, and `VITE_DEV_PORT` select ports and connection targets.

Reference profiles are available in `backend/app/config/agents/odisha.yaml` and `backend/app/config/agents/nimble.yaml`. Set `AGENT_PROFILE=odisha` or `AGENT_PROFILE=nimble` in the backend `.env`.

Profile-specific prompts and knowledge are stored in:

```text
backend/app/config/prompts/odisha.txt
backend/app/config/prompts/nimble.txt
backend/app/config/agents/odisha.yaml
backend/app/config/agents/nimble.yaml
data/odisha/
data/nimble/
```

To run Nimble AI alongside the default profile, use backend port `8001`, frontend port `5174`, and `VITE_API_BASE_URL=http://localhost:8001`.

## Phase 3 status

- React + Vite + TypeScript conversational shell
- FastAPI backend with `GET /health` and `POST /api/chat`
- Provider-agnostic LLM service with local, Ollama, OpenAI, Gemini, and Sarvam adapters
- Local deterministic fallback so the project runs without API keys
- Responsive text-chat UI and clear conversation action
- LangGraph conversation workflow with intent classification, Odisha domain guard, conversation history, and response validation
- Curated Odisha text knowledge base with chunking, configurable embeddings, FAISS retrieval, and graph context injection

Sarvam STT/TTS and observability remain available through the existing service configuration.

## Run locally

From this directory:

```bash
cp .env.example .env

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The frontend expects the backend at `http://localhost:8000`; set `VITE_API_BASE_URL` if needed.

To use a hosted model, set `LLM_PROVIDER` and its API key in `backend/.env` (or export the variables before starting Uvicorn). Keep secrets server-side.

For Sarvam chat completions, use `LLM_PROVIDER=sarvam`, set `SARVAM_API_KEY`, and optionally set `LLM_MODEL` (defaults to `sarvam-105b`). Access and model availability depend on the Sarvam API key and account.

## Phase 2 deployment

The production deployment uses Vercel for the Vite frontend and Cloud Run for the FastAPI backend. The backend image is built from the repository root so it includes the agent profiles, prompts, and `data/` knowledge base.

Build and deploy the backend:

```bash
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

export GCP_REGION=asia-south1
export GCP_PROJECT_ID=$(gcloud config get-value project)
export IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/odia-ai/odia-ai-api:latest"

gcloud artifacts repositories create odia-ai \
  --repository-format=docker \
  --location="${GCP_REGION}" \
  --description="Odisha AI container images"

gcloud builds submit . \
  --config=cloudbuild.yaml \
  --substitutions="_IMAGE=${IMAGE}"
gcloud run deploy odia-ai-api \
  --image "${IMAGE}" \
  --region "${GCP_REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars AGENT_PROFILE=odisha,LLM_PROVIDER=local
```

For hosted providers, pass API keys through Secret Manager rather than committing or uploading `.env`:

```bash
printf '%s' "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
gcloud run services update odia-ai-api \
  --region "${GCP_REGION}" \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

After the backend is deployed, set `VITE_API_BASE_URL` in the Vercel project to the Cloud Run URL and deploy the `frontend/` directory with build command `npm run build` and output directory `dist`. Set the backend `FRONTEND_ORIGIN` to the final Vercel URL before testing from a browser.

## API

`GET /health`

`POST /api/chat`

```json
{"message":"ପୁରୀ ବିଷୟରେ କହନ୍ତୁ","history":[]}
```

The response is shaped as:

```json
{"reply":"...","provider":"local","request_id":"..."}
```

## Structure

```text
frontend/     React/Vite client
backend/app/  FastAPI HTTP layer and isolated services
data/odisha/  Future curated knowledge files
scripts/      Future indexing and operational scripts
```
