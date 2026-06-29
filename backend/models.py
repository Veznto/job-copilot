

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    roles = relationship("Role", back_populates="owner")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    job_title = Column(String)
    company = Column(String)
    jd_text = Column(Text)
    original_resume_text = Column(Text)
    status = Column(String, default="applied")  # applied / interviewing / rejected / offer
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="roles")
    drafts = relationship("Draft", back_populates="role")

class Draft(Base):
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"))
    fit_analysis = Column(Text)
    resume_rewrite = Column(Text)
    cover_letter = Column(Text)
    interview_qa = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    role = relationship("Role", back_populates="drafts")