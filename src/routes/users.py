from fastapi import APIRouter
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["users"])

class User(BaseModel):
    id: str
    name: str
    email: str
    role: str

users_db = [
    {"id": "1", "name": "misha", "email": "misha@prodpal.com", "role": "backend"},
    {"id": "2", "name": "baha", "email": "baha@prodpal.com", "role": "backend"},
    {"id": "3", "name": "masha", "email": "masha@prodpal.com", "role": "frontend"},
    {"id": "4", "name": "liza", "email": "liza@prodpal.com", "role": "frontend"},
    {"id": "5", "name": "test_user", "email": "test@prodpal.com", "role": "tester"}
]

@router.get("/users", response_model=List[User])
async def get_all_users():
    return users_db