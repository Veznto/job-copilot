


from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import timedelta
import asyncio
import fitz  # PyMuPDF
import json
import os
import shutil

from database import engine, get_db, SessionLocal, UPLOAD_DIR
import models, schemas, auth, agents, pipeline_state

# Create all database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Job Application Co-Pilot API")

# Allow the frontend to talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── AUTH ROUTES ────────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pw = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    token = auth.create_access_token(
        data={"sub": new_user.email},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    token = auth.create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer"}

# ─── APPLICATION ROUTES ──────────────────────────────────────────────────────

def _save_resume_pdf(resume: UploadFile, user_id: int) -> tuple[str, str]:
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{resume.filename}")

    with open(file_path, "wb") as f:
        shutil.copyfileobj(resume.file, f)

    return _extract_resume_text(file_path)


def _save_resume_pdf_bytes(content: bytes, filename: str, user_id: int) -> tuple[str, str]:
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{filename}")

    with open(file_path, "wb") as f:
        f.write(content)

    return _extract_resume_text(file_path)


def _extract_resume_text(file_path: str) -> tuple[str, str]:
    try:
        doc = fitz.open(file_path)
        resume_text = ""
        for page in doc:
            resume_text += page.get_text()
        doc.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {str(e)}")

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="PDF appears to be empty or unreadable")

    return file_path, resume_text


def _run_pipeline_background(
    role_id: int,
    resume_text: str,
    jd_text: str,
):
    """Run agents in a background thread and track progress for polling."""
    db = SessionLocal()
    try:
        pipeline_state.set_state(
            role_id,
            status="processing",
            step=0,
            agent="prepare",
            message="Starting AI agents...",
        )

        def on_progress(event: dict):
            pipeline_state.set_state(
                role_id,
                status="processing",
                step=event.get("step", 0),
                agent=event.get("agent", ""),
                agent_status=event.get("status", ""),
                message=event.get("message") or _progress_message(event),
            )

        results = agents.run_pipeline(resume_text, jd_text, on_progress=on_progress)

        draft = models.Draft(
            role_id=role_id,
            fit_analysis=results["fit_analysis"],
            resume_rewrite=results["resume_rewrite"],
            cover_letter=results["cover_letter"],
            interview_qa=results["interview_qa"],
        )
        db.add(draft)
        db.commit()

        pipeline_state.set_state(
            role_id,
            status="complete",
            step=4,
            agent="interview_qa",
            agent_status="completed",
            message="All agents finished!",
        )
    except Exception as e:
        pipeline_state.set_state(
            role_id,
            status="error",
            message=str(e),
        )
    finally:
        db.close()


def _progress_message(event: dict) -> str:
    labels = {
        "prepare": "Reading your resume",
        "fit_analysis": "Fit Analysis Agent",
        "resume_rewrite": "Resume Rewrite Agent",
        "cover_letter": "Cover Letter Agent",
        "interview_qa": "Interview Prep Agent",
    }
    agent = event.get("agent", "")
    label = labels.get(agent, agent)
    if event.get("status") == "started":
        return f"Running {label}..."
    if event.get("status") == "completed":
        return f"{label} complete"
    return "Processing..."


@app.post("/applications/start")
async def start_application(
    job_title: str = Form(...),
    company: str = Form(...),
    jd_text: str = Form(...),
    resume: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Create application and run pipeline in background. Returns immediately for polling."""
    resume_bytes = await resume.read()
    resume_filename = resume.filename

    _, resume_text = _save_resume_pdf_bytes(resume_bytes, resume_filename, current_user.id)

    db = SessionLocal()
    try:
        role = models.Role(
            job_title=job_title,
            company=company,
            jd_text=jd_text,
            original_resume_text=resume_text,
            owner_id=current_user.id,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        role_id = role.id
    finally:
        db.close()

    pipeline_state.set_state(
        role_id,
        status="processing",
        step=0,
        agent="prepare",
        message="Preparing your application...",
    )

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _run_pipeline_background,
        role_id,
        resume_text,
        jd_text,
    )

    return {"role_id": role_id, "status": "processing"}


@app.get("/applications/{role_id}/pipeline-status")
def get_pipeline_status(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    role = db.query(models.Role).filter(
        models.Role.id == role_id,
        models.Role.owner_id == current_user.id,
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Application not found")

    if role.drafts:
        return {
            "role_id": role_id,
            "status": "complete",
            "step": 4,
            "agent": "interview_qa",
            "agent_status": "completed",
            "message": "All agents finished!",
        }

    state = pipeline_state.get_state(role_id)
    if state.get("status") == "unknown":
        return {
            "role_id": role_id,
            "status": "processing",
            "step": 0,
            "message": "Waiting for agents to start...",
        }
    return {"role_id": role_id, **state}


@app.post("/applications/stream")
async def create_application_stream(
    job_title: str = Form(...),
    company: str = Form(...),
    jd_text: str = Form(...),
    resume: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Stream real-time agent progress via Server-Sent Events."""
    resume_bytes = await resume.read()
    resume_filename = resume.filename
    user_id = current_user.id

    async def event_generator():
        progress_queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: dict):
            asyncio.run_coroutine_threadsafe(progress_queue.put(event), loop)

        def run_pipeline_job():
            db = SessionLocal()
            try:
                emit({"type": "progress", "step": 0, "agent": "prepare", "status": "started",
                      "message": "Reading your resume..."})

                _, resume_text = _save_resume_pdf_bytes(resume_bytes, resume_filename, user_id)
                emit({"type": "progress", "step": 0, "agent": "prepare", "status": "completed",
                      "message": "Resume extracted"})

                role = models.Role(
                    job_title=job_title,
                    company=company,
                    jd_text=jd_text,
                    original_resume_text=resume_text,
                    owner_id=user_id,
                )
                db.add(role)
                db.commit()
                db.refresh(role)

                def on_progress(event: dict):
                    emit(event)

                results = agents.run_pipeline(resume_text, jd_text, on_progress=on_progress)

                draft = models.Draft(
                    role_id=role.id,
                    fit_analysis=results["fit_analysis"],
                    resume_rewrite=results["resume_rewrite"],
                    cover_letter=results["cover_letter"],
                    interview_qa=results["interview_qa"],
                )
                db.add(draft)
                db.commit()

                emit({"type": "complete", "role_id": role.id})
            except HTTPException as e:
                emit({"type": "error", "message": e.detail})
            except Exception as e:
                emit({"type": "error", "message": f"AI pipeline error: {str(e)}"})
            finally:
                db.close()
                asyncio.run_coroutine_threadsafe(progress_queue.put(None), loop)

        loop.run_in_executor(None, run_pipeline_job)

        while True:
            event = await progress_queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/applications", response_model=schemas.RoleOut)
async def create_application(
    job_title: str = Form(...),
    company: str = Form(...),
    jd_text: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    _, resume_text = _save_resume_pdf(resume, current_user.id)

    # Create the Role record in DB
    role = models.Role(
        job_title=job_title,
        company=company,
        jd_text=jd_text,
        original_resume_text=resume_text,
        owner_id=current_user.id
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    
    # Run the multi-agent pipeline
    try:
        results = agents.run_pipeline(resume_text, jd_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI pipeline error: {str(e)}")
    
    # Save the Draft
    draft = models.Draft(
        role_id=role.id,
        fit_analysis=results["fit_analysis"],
        resume_rewrite=results["resume_rewrite"],
        cover_letter=results["cover_letter"],
        interview_qa=results["interview_qa"],
    )
    db.add(draft)
    db.commit()
    db.refresh(role)
    
    return role

@app.get("/applications", response_model=list[schemas.RoleOut])
def get_applications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.Role).filter(
        models.Role.owner_id == current_user.id
    ).order_by(models.Role.created_at.desc()).all()

@app.get("/applications/{role_id}", response_model=schemas.RoleOut)
def get_application(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    role = db.query(models.Role).filter(
        models.Role.id == role_id,
        models.Role.owner_id == current_user.id
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Application not found")
    return role

@app.patch("/applications/{role_id}", response_model=schemas.RoleOut)
def update_status(
    role_id: int,
    update: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    role = db.query(models.Role).filter(
        models.Role.id == role_id,
        models.Role.owner_id == current_user.id
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Application not found")
    if update.status:
        role.status = update.status
    db.commit()
    db.refresh(role)
    return role

@app.delete("/applications/{role_id}")
def delete_application(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    role = db.query(models.Role).filter(
        models.Role.id == role_id,
        models.Role.owner_id == current_user.id
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(role)
    db.commit()
    return {"message": "Deleted"}


# Serve frontend from the backend (avoids Live Server reloads when DB/uploads change)
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"message": "Job Application Co-Pilot API is running!"}