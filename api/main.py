# coding: utf-8
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import health, runs, platforms, organisms, quality
from simulator.src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="GenomicFlow Clinical Data Platform API",
    description="Real-time clinical genomics sequencing metadata API backed by BigQuery",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(runs.router)
app.include_router(platforms.router)
app.include_router(organisms.router)
app.include_router(quality.router)


@app.get("/")
async def root():
    return {
        "service":     "GenomicFlow Clinical Data Platform API",
        "version":     settings.app_version,
        "docs":        "/docs",
        "data_source": "Google BigQuery",
        "project":     settings.gcp_project_id,
    }