from fastapi import FastAPI
from app.routes import router as api_router

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Python backend!"}

app.include_router(api_router)