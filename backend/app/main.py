import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config.settings import get_settings
from app.utils.observability import LangfuseTracer, RequestMetrics, log_request, request_metrics

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
tracer = LangfuseTracer(settings)
app = FastAPI(title="Odisha AI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"}),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    incoming_id = request.headers.get("x-request-id", "")
    metrics = RequestMetrics(request_id=incoming_id[:100] if incoming_id else RequestMetrics().request_id)
    with request_metrics(metrics), tracer.request(metrics):
        response = await call_next(request)
    response.headers["X-Request-ID"] = metrics.request_id
    log_request(metrics, request.method, request.url.path, response.status_code)
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "odia-ai-api"}
