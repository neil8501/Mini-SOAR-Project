import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.api.routes.actions import router as actions_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.cases import router as cases_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.stats import router as stats_router
from app.api.routes.tickets import router as tickets_router
from app.db.session import engine
from app.metrics.prometheus import api_request_latency_seconds

app = FastAPI(
    title="Mini-SOAR API",
    version="1.1.0",
    description="Local SOAR-style incident automation platform (UI enabled)",
)

# UI runs on localhost:3001. Allow local dev + docker dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response: Response
    try:
        response = await call_next(request)
        return response
    finally:
        dt = time.perf_counter() - start
        route = request.url.path
        method = request.method
        status = "unknown"
        try:
            status = str(getattr(response, "status_code", "unknown"))
        except Exception:
            status = "unknown"
        api_request_latency_seconds.labels(route=route, method=method, status=status).observe(dt)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(ingest_router)
app.include_router(alerts_router)
app.include_router(cases_router)
app.include_router(actions_router)
app.include_router(tickets_router)
app.include_router(metrics_router)
app.include_router(stats_router)