from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  -- registers all models with the SQLModel mapper
from app.api.auth import router as auth_router
from app.api.cinemas import router as cinemas_router
from app.core.config import settings

app = FastAPI(title="CineCloud API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(cinemas_router)

@app.get("/")
async def root():
    return {"message": "Hello World!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
