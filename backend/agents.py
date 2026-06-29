import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Helper function to call the Groq API."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=2000,
    )
    return response.choices[0].message.content

# ─── AGENT 1: Fit Analyst ───────────────────────────────────────────────────

def agent_fit_analysis(resume_text: str, jd_text: str) -> str:
    system = """You are a senior recruiter with 15 years of experience. 
    Analyze the match between a candidate's resume and a job description.
    Be specific, honest, and actionable. Structure your response clearly."""
    
    user = f"""Analyze how well this candidate fits this job.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Provide:
1. MATCH SCORE: X/10 with one sentence explanation
2. STRONG MATCHES (3-5 bullet points): Requirements the candidate clearly meets
3. GAPS TO ADDRESS (2-4 bullet points): Requirements missing or weak in the resume
4. KEYWORDS TO ADD: 5-8 keywords from the JD missing from the resume
5. WHAT TO EMPHASISE: 2-3 specific things to highlight for this role

Keep it concise and actionable."""
    
    return call_llm(system, user)

# ─── AGENT 2: Resume Rewriter ────────────────────────────────────────────────

def agent_resume_rewrite(resume_text: str, jd_text: str, fit_analysis: str) -> str:
    system = """You are an expert resume writer who transforms mediocre resumes into 
    interview-winning ones. You keep the same jobs and timeline but sharpen every bullet 
    point. You never fabricate experience. You use strong action verbs and quantify impact."""
    
    user = f"""Rewrite this resume to be highly tailored for the job description below.

ORIGINAL RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

FIT ANALYSIS (use this to know what to emphasise):
{fit_analysis}

Rules:
- Keep the same work history and education (don't invent experience)
- Rewrite bullet points to start with strong action verbs
- Weave in relevant keywords from the JD naturally
- Quantify achievements where possible (use estimates if needed, marked with ~)
- Emphasise the skills and experiences most relevant to this role
- Keep it to 1 page worth of content

Output the full rewritten resume in clean plain text format."""
    
    return call_llm(system, user)

# ─── AGENT 3: Cover Letter Writer ───────────────────────────────────────────

def agent_cover_letter(resume_text: str, jd_text: str, fit_analysis: str) -> str:
    system = """You are a professional cover letter writer who crafts compelling, 
    human-sounding letters. You avoid clichés like 'I am writing to express my interest' 
    and 'I am a passionate team player'. Every letter sounds like the candidate wrote it themselves."""
    
    user = f"""Write a cover letter for this candidate applying to this job.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

FIT ANALYSIS:
{fit_analysis}

Requirements:
- Exactly 3 paragraphs, 1 page max
- Opening: Hook with a specific achievement or insight, not a generic opener
- Middle: Connect 2-3 specific resume experiences to the role's needs
- Closing: Confident call to action
- Tone: Professional but warm, not robotic
- No bullet points — flowing prose only
- Do not use: "passionate", "team player", "hard worker", "I am writing to"

Output only the letter text (no subject line needed)."""
    
    return call_llm(system, user)

# ─── AGENT 4: Interview Coach ───────────────────────────────────────────────

def agent_interview_qa(resume_text: str, jd_text: str) -> str:
    system = """You are an expert interview coach who prepares candidates for job interviews. 
    You know the STAR method and how interviewers think. You ground every answer in the 
    candidate's actual experience from their resume."""
    
    user = f"""Create a mock interview preparation pack for this candidate.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Generate exactly 10 interview questions this company is likely to ask, with sample answers.

For each question:
- Write the question
- Write a strong sample answer (3-5 sentences) grounded in this candidate's actual resume
- Use the STAR method (Situation, Task, Action, Result) for behavioral questions

Mix of question types:
- 3 behavioral ("Tell me about a time...")  
- 3 role-specific technical questions
- 2 motivation questions ("Why this company/role?")
- 2 situational ("What would you do if...")

Format each as:
Q[N]: [Question]
A[N]: [Answer]
"""
    
    return call_llm(system, user)

# ─── ORCHESTRATOR: Run All Agents ───────────────────────────────────────────

def run_pipeline(resume_text: str, jd_text: str, on_progress=None) -> dict:
    """Run all 4 agents sequentially, emitting progress events if a callback is provided."""

    def run_step(step_num: int, agent_name: str, fn):
        if on_progress:
            on_progress({"type": "progress", "step": step_num, "agent": agent_name, "status": "started"})
        print(f"Agent {step_num}: Running {agent_name}...")
        result = fn()
        if on_progress:
            on_progress({"type": "progress", "step": step_num, "agent": agent_name, "status": "completed"})
        return result

    fit_analysis = run_step(1, "fit_analysis", lambda: agent_fit_analysis(resume_text, jd_text))
    resume_rewrite = run_step(2, "resume_rewrite", lambda: agent_resume_rewrite(resume_text, jd_text, fit_analysis))
    cover_letter = run_step(3, "cover_letter", lambda: agent_cover_letter(resume_text, jd_text, fit_analysis))
    interview_qa = run_step(4, "interview_qa", lambda: agent_interview_qa(resume_text, jd_text))

    print("Pipeline complete!")
    return {
        "fit_analysis": fit_analysis,
        "resume_rewrite": resume_rewrite,
        "cover_letter": cover_letter,
        "interview_qa": interview_qa,
    }