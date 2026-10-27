# Odisha AI backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run tests with `python -m pytest -q`. API keys are read only by the backend from environment variables.

