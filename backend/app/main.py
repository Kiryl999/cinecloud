from fastapi import FastAPI
from app.api.cinemas import router as cinemas_router

app = FastAPI(title="CineCloud API")

app.include_router(cinemas_router)

@app.get("/")
async def root():
    return {"message": "Hello World!"}

@app.get("/health")
def health_check():
    return {"status:" "ok"}