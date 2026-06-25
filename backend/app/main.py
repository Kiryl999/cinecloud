from fastapi import FastAPI

app = FastAPI(title="CineCloud API")

@app.get("/")
async def root():
    return {"message": "Hello World!"}

@app.get("/health")
def health_check():
    return {"status:" "ok"}