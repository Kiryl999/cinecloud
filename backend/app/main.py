from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.cinemas import router as cinemas_router

app = FastAPI(title="CineCloud API")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, PUT, DELETE
    allow_headers=["*"],
)

app.include_router(cinemas_router)

@app.get("/")
async def root():
    return {"message": "Hello World!"}

@app.get("/health")
def health_check():
    return {"status:" "ok"}