from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.endpoints import auth, chats, messages
from src.database.connection import engine, Base
from src.models.user import User
from src.models.chat import Chat, ChatParticipant
from src.models.message import Message
import uvicorn

app = FastAPI(
    title="ProdPal API",
    description="AI-помощник для умного общения и управления задачами",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(chats.router, prefix="/api", tags=["chats"])
app.include_router(messages.router, prefix="/api", tags=["messages"])

@app.get("/")
def read_root():
    return {"message": "Welcome to ProdPal API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)