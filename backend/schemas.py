

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class RoleCreate(BaseModel):
    job_title: str
    company: str
    jd_text: str

class RoleUpdate(BaseModel):
    status: Optional[str] = None

class DraftOut(BaseModel):
    id: int
    fit_analysis: Optional[str]
    resume_rewrite: Optional[str]
    cover_letter: Optional[str]
    interview_qa: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class RoleOut(BaseModel):
    id: int
    job_title: str
    company: str
    status: str
    original_resume_text: Optional[str] = None
    created_at: datetime
    drafts: list[DraftOut] = []
    
    class Config:
        from_attributes = True