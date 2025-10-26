from fastapi import FastAPI
from src.routes.health import router as health_router

app = FastAPI()

app.include_router(health_router)

@app.get("/")
async def root():
    return {"message": "Welcome to ProductivityPal API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )