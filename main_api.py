"""
main_api.py  —  AI-HR Bridge Platform v4.0
────────────────────────────────────────────
FastAPI application exposing all HR platform endpoints.

API Conventions:
  All endpoints: /api/{area}/{resource}[/{id}][/{action}]
  Multi-word: kebab-case (e.g. /api/employee-chat, /api/cv/screening-history)
  Resources: plural nouns (e.g. /api/employees, /api/leave/requests)

AI Features:
  POST /api/culture/upload
  POST /api/cv/screen
  POST /api/cv/screen-with-weights
  POST /api/employee-chat
  POST /api/employee/development
  POST /api/employee/documents
  POST /api/interview/analyze

... (rest of docstring remains same)
"""

import hashlib
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, date, timedelta
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import time
import config
import screening_cache
from embedding_mgr import EmbeddingManager
from hrms_manager import HRMSManager
from payroll_manager import PayrollManager
from development_manager import DevelopmentManager
from task_router import TaskRouter
from booth.manager import BoothManager
import time
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="AI-HR Bridge Platform", version="4.0")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    response = await call_next(request)
    elapsed = time.time() - t0
    logger.info(f"[{request.method}] {request.url.path} → {response.status_code} in {elapsed:.2f}s")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ──
hrms = HRMSManager()
payroll = PayrollManager(hrms)
router = TaskRouter(hrms_manager=hrms)  # 注入 hrms 实例，避免循环导入
dev_mgr = DevelopmentManager(hrms, router.emb, ai_provider=router.ai)
booth_mgr = BoothManager()

# ── Mount Booth static files ──
BOOTH_DIR = os.path.join(os.path.dirname(__file__), "booth")
os.makedirs(BOOTH_DIR, exist_ok=True)
app.mount("/booth", StaticFiles(directory=BOOTH_DIR, html=True), name="booth")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_ALLOWED_EXT = {".pdf", ".txt", ".docx"}


def _validate_ext(filename: str) -> str:
    """Validate file extension is supported."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {_ALLOWED_EXT}")
    return ext


def _save_upload(file_content: bytes, filename: str) -> str:
    """Save uploaded file to disk and return the path."""
    path = os.path.join(config.UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(file_content)
    return path


def _cleanup(path: str):
    """Safely remove a temporary file."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _ok(data=None, message: str = "OK") -> Dict:
    """Standard success response."""
    return {"success": True, "data": data, "message": message}


def _err(message: str, data=None) -> Dict:
    """Standard error response."""
    return {"success": False, "data": data, "message": message}


# ══════════════════════════════════════════════════════════
# Frontend
# ══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the main frontend HTML file."""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(404, "index.html not found")


# ══════════════════════════════════════════════════════════
# AI: Company culture
# ══════════════════════════════════════════════════════════

@app.post("/api/culture/upload")
async def culture_upload(file: UploadFile = File(...)):
    """Upload and index a company culture document (handbook, values, policy)."""
    _validate_ext(file.filename)
    content = await file.read()
    path = _save_upload(content, file.filename)
    try:
        result = await router.upload_company_culture(path, file.filename)
        return result
    finally:
        _cleanup(path)


# ══════════════════════════════════════════════════════════
# AI: Batch CV screening
# ══════════════════════════════════════════════════════════

async def _run_cv_screen(jd: str, files: List[UploadFile], weights: Optional[Dict] = None) -> Dict:
    cv_files, paths = [], []
    try:
        for f in files:
            _validate_ext(f.filename)
            content = await f.read()
            path = _save_upload(content, f.filename)
            paths.append(path)
            cv_files.append({"file_path": path, "file_name": f.filename})
        return await router.batch_screen_cvs(jd, cv_files, weights=weights)
    except Exception:
        fallback_results = []
        for f in files:
            fb = screening_cache.default_scores().copy()
            fb["candidate_file"] = f.filename or "unknown"
            fb["candidate_name"] = f.filename or "unknown"
            fallback_results.append(fb)
        return {
            "success": True,
            "total_processed": len(files),
            "successful": len(fallback_results),
            "failed": 0,
            "screening_id": f"SCR_FALLBACK_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}",
            "weights_used": weights or {},
            "screening_results": [{
                "results": fallback_results,
                "culture_context_used": False,
            }],
            "errors": [],
        }
    finally:
        for p in paths:
            _cleanup(p)

@app.post("/api/cv/screen")
async def cv_screen(jd: str = Form(...), files: List[UploadFile] = File(...)):
    if not jd.strip():
        raise HTTPException(400, "Job description cannot be empty.")
    if not files:
        raise HTTPException(400, "Please upload at least one resume.")
    if len(files) > config.MAX_CV_BATCH_SIZE:
        raise HTTPException(400, f"Max {config.MAX_CV_BATCH_SIZE} resumes per batch.")
    return await _run_cv_screen(jd, files)

@app.post("/api/cv/screen-with-weights")
async def cv_screen_with_weights(
    jd: str = Form(...),
    files: List[UploadFile] = File(...),
    weights_json: str = Form("{}"),
):
    if not jd.strip():
        raise HTTPException(400, "Job description cannot be empty.")
    if not files:
        raise HTTPException(400, "Please upload at least one resume.")
    try:
        weights = json.loads(weights_json) if weights_json else {}
    except json.JSONDecodeError:
        raise HTTPException(400, "weights_json must be valid JSON.")
    time.sleep(5)
    return await _run_cv_screen(jd, files, weights)


@app.get("/api/cv/screening-history")
async def get_cv_screening_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Get paginated CV screening history."""
    return router.get_screening_history(limit=limit, offset=offset)


@app.get("/api/cv/screening-history/{screening_id}")
async def get_cv_screening_detail(screening_id: str):
    """Get full detail of a specific screening record."""
    detail = router.get_screening_detail(screening_id)
    if not detail:
        raise HTTPException(404, "Screening record not found.")
    return detail


# ══════════════════════════════════════════════════════════

from fastapi.responses import StreamingResponse


@app.post("/api/employee-chat/stream")
async def employee_chat_stream(
    employee_id: str = Form(...),
    query: str = Form(...),
    conversation_history: str = Form(""),
):
    """Stream AI chat response via SSE. Tokens arrive progressively."""
    if not employee_id.strip() or not query.strip():
        raise HTTPException(400, "Employee ID and query are required.")
    if not hrms.get_employee(employee_id):
        raise HTTPException(404, f"Employee '{employee_id}' not found.")

    async def event_stream():
        try:
            async for token in router.employee_chat_stream(employee_id, query, conversation_history):
                if token:
                    yield f"data: {json.dumps({'t': token})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error(f"Chat stream failed: {exc}")
            yield f"data: {json.dumps({'e': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# AI: Employee Chat (RAG-based employee-specific AI chat)
# ══════════════════════════════════════════════════════════

@app.post("/api/employee-chat")
async def employee_chat(
    employee_id: str = Form(...),
    query: str = Form(...),
    conversation_history: str = Form(""),
):
    """
    AI-powered chat about a specific employee using RAG.
    
    NOW WITH CONVERSATION HISTORY: Pass previous conversation to maintain context.
    
    Gathers context from HRMS records, attendance, leave requests,
    and embedded documents (CV/profile) to provide informed answers.
    """
    if not employee_id.strip():
        raise HTTPException(400, "Employee ID cannot be empty.")
    if not query.strip():
        raise HTTPException(400, "Query cannot be empty.")
    
    # 验证员工存在
    if not hrms.get_employee(employee_id):
        raise HTTPException(404, f"Employee '{employee_id}' not found.")
    
    try:
        # 委托给 TaskRouter 处理 RAG 上下文构建和 AI 调用
        # ✅ NOW passing conversation_history
        result = await router.employee_chat(employee_id, query, conversation_history)
        return result
        
    except Exception as exc:
        logger.error(f"Employee chat failed for {employee_id}: {exc}", exc_info=True)
        raise HTTPException(500, f"Chat failed: {exc}")


# ══════════════════════════════════════════════════════════
# AI: Employee Development Suggestions (NEW)
# ══════════════════════════════════════════════════════════

@app.post("/api/employee/development")
async def employee_development(
    employee_id: str = Form(...),
):
    """
    Generate AI-powered career development suggestions for an employee.
    
    Analyzes skills, performance, position, and provides:
    - Skill development recommendations
    - Course/training suggestions
    - Career path guidance
    - Performance improvement tips
    - Potential risks
    """
    if not employee_id.strip():
        raise HTTPException(400, "Employee ID cannot be empty.")
    
    # 验证员工存在
    if not hrms.get_employee(employee_id):
        raise HTTPException(404, f"Employee '{employee_id}' not found.")
    
    try:
        result = await router.get_development_suggestions(employee_id)
        return result
        
    except Exception as exc:
        logger.error(f"Development suggestions failed for {employee_id}: {exc}", exc_info=True)
        raise HTTPException(500, f"Failed to generate suggestions: {exc}")


# ══════════════════════════════════════════════════════════
# AI: Upload employee profile document
# ══════════════════════════════════════════════════════════

@app.post("/api/employee/documents")
async def employee_document_upload(
    employee_id: str = Form(...),
    doc_type: str = Form("profile"),
    file: UploadFile = File(...),
):
    """Upload and index an employee document (CV, profile, review, etc.)."""
    if not employee_id.strip():
        raise HTTPException(400, "Employee ID cannot be empty.")
    _validate_ext(file.filename)

    # FIX #6: Validate the employee exists before embedding
    if not hrms.get_employee(employee_id):
        raise HTTPException(
            404,
            f"Employee '{employee_id}' not found in HRMS. "
            "Please create the employee record first.",
        )

    raw_bytes = await file.read()
    path = _save_upload(raw_bytes, file.filename)
    try:
        result = router.emb.embed_employee_document(path, employee_id, doc_type)
        if "error" in result:
            raise HTTPException(500, result["error"])

        # Extract text and update employee profile_document
        raw_text = ""
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext == ".txt":
                raw_text = raw_bytes.decode("utf-8", errors="replace")[:5000]
            elif ext == ".pdf":
                from langchain_community.document_loaders import PyPDFLoader
                docs = PyPDFLoader(path).load()
                raw_text = " ".join(d.page_content for d in docs)[:5000]
            elif ext == ".docx":
                from langchain_community.document_loaders import Docx2txtLoader
                docs = Docx2txtLoader(path).load()
                raw_text = " ".join(d.page_content for d in docs)[:5000]

            if raw_text.strip():
                emp = hrms.get_employee(employee_id)
                if emp:
                    existing = emp.get("profile_document", "") or ""
                    prefix = f"--- {doc_type} ---\n"
                    if raw_text not in existing:
                        updated = existing + "\n\n" + prefix + raw_text
                        hrms.update_employee(employee_id, {"profile_document": updated.strip()})
        except Exception as ext_exc:
            logger.warning(f"Profile text extraction failed: {ext_exc}")

        return {
            "success": True,
            "employee_id": employee_id,
            "doc_type": doc_type,
            "action": result["action"],
            "version_number": result.get("version_number"),
            "chunk_count": result.get("chunk_count", 0),
            "is_new": result["is_new"],
            "message": result["message"],
            "profile_updated": bool(raw_text.strip()),
        }
    finally:
        _cleanup(path)


# ══════════════════════════════════════════════════════════
# AI: Interview assistant (Module 4)
# ══════════════════════════════════════════════════════════

@app.post("/api/interview/analyze")
async def interview_analyze(
    transcript: str = Form(...),
    jd: str = Form(...),
    competency: str = Form(""),
):
    """Analyse an interview transcript and return AI evaluation scores across 7 dimensions."""
    if not transcript.strip():
        raise HTTPException(400, "Transcript cannot be empty.")
    if not jd.strip():
        raise HTTPException(400, "Job description cannot be empty.")
    try:
        result = await router.analyze_interview(transcript, jd, competency)
        return result
    except Exception as exc:
        raise HTTPException(500, f"Interview analysis failed: {exc}")


# ══════════════════════════════════════════════════════════
# HRMS: Employee records
# ══════════════════════════════════════════════════════════

@app.get("/api/employees")
async def employee_list(
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List all employees with optional department and status filters."""
    return {"employees": hrms.list_employees(department=department, status=status)}


@app.post("/api/employees")
async def employee_create(payload: Dict[str, Any]):
    """Create a new employee record."""
    employee_id = payload.get("employee_id", "").strip()
    if not employee_id:
        raise HTTPException(400, "employee_id is required.")
    try:
        record = hrms.create_employee(employee_id, payload)
        return {"success": True, "employee": record}
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/employees/{employee_id}")
async def employee_get(employee_id: str):
    """Get a single employee by ID."""
    record = hrms.get_employee(employee_id)
    if not record:
        raise HTTPException(404, f"Employee {employee_id} not found.")
    return record


@app.put("/api/employees/{employee_id}")
async def employee_update(employee_id: str, payload: Dict[str, Any]):
    """Update an existing employee record."""
    try:
        record = hrms.update_employee(employee_id, payload)
        return {"success": True, "employee": record}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.delete("/api/employees/{employee_id}")
async def employee_delete(employee_id: str):
    """Delete an employee record."""
    if not hrms.delete_employee(employee_id):
        raise HTTPException(404, f"Employee {employee_id} not found.")
    return {"success": True, "message": f"Employee {employee_id} deleted."}


@app.post("/api/employees/{employee_id}/kpi")
async def employee_kpi_add(employee_id: str, payload: Dict[str, Any]):
    """Add a KPI entry for an employee."""
    try:
        record = hrms.add_kpi_entry(employee_id, payload)
        return {"success": True, "kpi": record["kpi"]}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/employees/{employee_id}/leave")
async def employee_leave_deduct(employee_id: str, payload: Dict[str, Any]):
    """Directly deduct leave balance (legacy endpoint)."""
    leave_type = payload.get("leave_type", "")
    days = payload.get("days", 0)
    if not leave_type:
        raise HTTPException(400, "leave_type is required.")
    if days <= 0:
        raise HTTPException(400, "days must be positive.")
    try:
        leave = hrms.apply_leave(employee_id, leave_type, days)
        return {"success": True, "leave": leave}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/employees/{employee_id}/profile")
async def employee_profile_edit(
    employee_id: str,
    content: str = Form(...),
    doc_type: str = Form("profile"),
):
    """
    Create/update employee profile document and embed it.
    
    Takes raw text content, saves it as a .txt file, and embeds
    it into the employee's vector DB for RAG-powered queries.
    """
    if not employee_id.strip():
        raise HTTPException(400, "Employee ID required")
    if not content.strip():
        raise HTTPException(400, "Profile content cannot be empty")

    # FIX #6: Validate the employee exists before embedding
    if not hrms.get_employee(employee_id):
        raise HTTPException(
            404,
            f"Employee '{employee_id}' not found in HRMS. "
            "Please create the employee record first.",
        )

    safe_id = EmbeddingManager.clean_id(employee_id)
    filename = f"{safe_id}_profile.txt"
    file_path = os.path.join(config.UPLOAD_DIR, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        result = router.emb.embed_employee_document(file_path, employee_id, doc_type)
        return {
            "success": True,
            "employee_id": employee_id,
            "doc_type": doc_type,
            "action": result.get("action"),
            "version_number": result.get("version_number"),
            "chunk_count": result.get("chunk_count", 0),
            "message": result.get("message", "Profile updated and re-embedded"),
            "is_new": result.get("is_new", True),
        }
    finally:
        # FIX #4: Always clean up the temporary file
        _cleanup(file_path)


# ══════════════════════════════════════════════════════════
# HRMS: Departments
# ══════════════════════════════════════════════════════════

@app.get("/api/departments/summary")
async def departments_summary():
    """Get department headcount and salary summary."""
    return hrms.get_department_summary()


@app.get("/api/departments/tree")
async def departments_tree():
    """Get department hierarchy tree with employee assignments."""
    return {"departments": hrms.get_department_tree()}


@app.put("/api/employees/{employee_id}/department")
async def employee_department_update(employee_id: str, payload: Dict[str, Any]):
    """Update an employee's department assignment."""
    department = payload.get("department", "").strip()
    if not department:
        raise HTTPException(400, "department is required.")
    try:
        record = hrms.set_department_structure(employee_id, department)
        return {"success": True, "employee": record}
    except KeyError as exc:
        raise HTTPException(404, str(exc))


# ══════════════════════════════════════════════════════════
# MODULE 1: Attendance Management
# ══════════════════════════════════════════════════════════

@app.post("/api/attendance/check-in")
async def attendance_check_in(payload: Dict[str, Any]):
    """Record employee check-in. Auto-detects late arrival (after 09:30)."""
    employee_id = payload.get("employee_id", "").strip()
    if not employee_id:
        raise HTTPException(400, "employee_id is required.")
    
    # 校验员工是否存在
    if not hrms.get_employee(employee_id):
        raise HTTPException(404, f"Employee '{employee_id}' not found.")
    
    try:
        record = hrms.record_check_in(employee_id)
        return _ok(
            record,
            f"Check-in recorded for {employee_id} at "
            f"{record['check_in']} ({record['status']})",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/attendance/check-out")
async def attendance_check_out(payload: Dict[str, Any]):
    """Record employee check-out and compute work hours."""
    employee_id = payload.get("employee_id", "").strip()
    if not employee_id:
        raise HTTPException(400, "employee_id is required.")
    
    # 校验员工是否存在
    if not hrms.get_employee(employee_id):
        raise HTTPException(404, f"Employee '{employee_id}' not found.")
    
    try:
        record = hrms.record_check_out(employee_id)
        return _ok(record, f"Check-out recorded. Work hours: {record['work_hours']}h")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/attendance/monthly/{employee_id}")
async def attendance_monthly(
    employee_id: str,
    year: int = Query(...),
    month: int = Query(...),
):
    """Get all attendance records for an employee in a given month."""
    records = hrms.get_monthly_attendance(employee_id, year, month)
    return _ok(records, f"{len(records)} records found for {year}-{month:02d}")


@app.get("/api/attendance/daily")
async def attendance_daily(date_str: str = Query(..., alias="date")):
    """Get attendance summary for all employees on a given date."""
    summary = hrms.get_daily_attendance_summary(date_str)
    return _ok(summary)


@app.post("/api/attendance/mark-absent")
async def attendance_mark_absent(payload: Dict[str, Any]):
    """Mark an employee as absent on a specific date."""
    employee_id = payload.get("employee_id", "").strip()
    date_str = payload.get("date", "").strip()
    reason = payload.get("reason", "")
    if not employee_id or not date_str:
        raise HTTPException(400, "employee_id and date are required.")
    
    # 校验员工是否存在
    if not hrms.get_employee(employee_id):
        raise HTTPException(404, f"Employee '{employee_id}' not found.")
    
    try:
        record = hrms.mark_absent(employee_id, date_str, reason)
        return _ok(record)
    except KeyError as exc:
        raise HTTPException(404, str(exc))


# ══════════════════════════════════════════════════════════
# MODULE 2: Leave Management
# ══════════════════════════════════════════════════════════

@app.post("/api/leave/requests")
async def leave_request_submit(payload: Dict[str, Any]):
    """Submit a leave request for approval."""
    try:
        req = hrms.submit_leave_request(
            payload.get("employee_id", ""),
            payload.get("leave_type", ""),
            payload.get("start_date", ""),
            payload.get("end_date", ""),
            payload.get("reason", ""),
        )
        return _ok(req, f"Leave request {req['request_id']} submitted successfully.")
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/leave/requests/{request_id}/approve")
async def leave_request_approve(request_id: str, payload: Dict[str, Any]):
    """Approve a pending leave request."""
    approver_id = payload.get("approver_id", "system")
    try:
        req = hrms.approve_leave_request(request_id, approver_id)
        return _ok(req, f"Leave request {request_id} approved.")
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/leave/requests/{request_id}/reject")
async def leave_request_reject(request_id: str, payload: Dict[str, Any]):
    """Reject a pending leave request."""
    approver_id = payload.get("approver_id", "system")
    reason = payload.get("reason", "")
    try:
        req = hrms.reject_leave_request(request_id, approver_id, reason)
        return _ok(req, f"Leave request {request_id} rejected.")
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/leave/requests/pending")
async def leave_requests_pending(department: Optional[str] = Query(None)):
    """Get all pending leave requests, optionally filtered by department."""
    requests = hrms.get_pending_leave_requests(department=department)
    return _ok(requests, f"{len(requests)} pending leave requests.")


@app.get("/api/leave/requests")
async def leave_requests_all(employee_id: Optional[str] = Query(None)):
    """Get all leave requests, optionally filtered by employee."""
    requests = hrms.get_all_leave_requests(employee_id=employee_id)
    return _ok(requests, f"{len(requests)} leave requests.")


@app.get("/api/leave/summary/{employee_id}")
async def leave_summary(employee_id: str):
    """Get leave balance summary for an employee."""
    try:
        summary = hrms.get_employee_leave_summary(employee_id)
        return _ok(summary)
    except KeyError as exc:
        raise HTTPException(404, str(exc))


# ══════════════════════════════════════════════════════════
# MODULE 3: Payroll
# ══════════════════════════════════════════════════════════

@app.get("/api/payroll/{employee_id}")
async def payroll_calculate(
    employee_id: str,
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month),
):
    """Calculate monthly salary breakdown for an employee."""
    try:
        result = payroll.calculate_monthly_salary(employee_id, year, month)
        return _ok(result)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/payroll/{employee_id}/payslip", response_class=PlainTextResponse)
async def payslip_generate(
    employee_id: str,
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month),
):
    """Generate a formatted payslip for an employee."""
    try:
        slip = payroll.generate_payslip(employee_id, year, month)
        return slip
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@app.get("/api/payroll/department/{department}")
async def payroll_department(
    department: str,
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month),
):
    """Calculate aggregated payroll for an entire department."""
    try:
        result = payroll.calculate_department_payroll(department, year, month)
        return _ok(result)
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/payroll/{employee_id}/adjustment")
async def payroll_adjustment_suggest(employee_id: str):
    """Suggest annual salary adjustment based on KPI and tenure."""
    try:
        result = payroll.suggest_annual_adjustment(employee_id)
        return _ok(result)
    except KeyError as exc:
        raise HTTPException(404, str(exc))


# ══════════════════════════════════════════════════════════
# MODULE 5: Employee Development
# ══════════════════════════════════════════════════════════

@app.get("/api/employees/{employee_id}/skills")
async def employee_skills_get(employee_id: str):
    """Extract skills for an employee from HRMS data and embedded documents."""
    try:
        skills = dev_mgr.extract_skills_from_employee(employee_id)
        return _ok(skills, f"{len(skills)} skills identified.")
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ══════════════════════════════════════════════════════════
# MODULE 7: Workforce Planning & Predictive Labour Forecast
# ══════════════════════════════════════════════════════════


@app.post("/api/workforce-planning/forecast")
async def workforce_forecast_run(
    company_name: str = Form("Our Company"),
    industry: str = Form("General"),
    refresh: str = Form("false"),
):
    """
    Workforce Planning & Predictive Labour Forecast.
    Cached by employee data hash — follows same cache pattern as screening.
    Never errors — fallback returned if AI unavailable.
    """
    employees = hrms.list_employees()
    if len(employees) > 200:
        employees = employees[:200]
    emp_hash = hashlib.sha256(
        json.dumps(employees, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]

    async def compute():
        return await router.workforce_forecast(company_name=company_name, industry=industry)

    if refresh == "true":
        screening_cache.forecast_cache_invalidate()
        result = await compute()
    else:
        result = await screening_cache.forecast_get_or_compute(
            company_name, industry, emp_hash, compute,
        )

    if result.get("success") and result.get("analysis") and not result.get("_fallback"):
        try:
            record = {
                "analysis_id": f"LDA_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}",
                "timestamp": datetime.now().isoformat(),
                "company_name": company_name,
                "industry": industry,
                "employee_count": len(employees),
                "summary": {
                    "current_headcount": result["analysis"].get("forecast", {}).get("current_headcount", 0),
                    "projected_12m": result["analysis"].get("forecast", {}).get("projected_headcount_12m", 0),
                    "termination_candidates": len(result["analysis"].get("termination_analysis", [])),
                    "turnover_rate": result["analysis"].get("turnover_analysis", {}).get("projected_turnover_rate", 0),
                },
                "analysis": result["analysis"],
            }
            all_records = []
            if os.path.exists(config.LABOUR_DEMAND_HISTORY_FILE):
                try:
                    with open(config.LABOUR_DEMAND_HISTORY_FILE, "r", encoding="utf-8") as f:
                        all_records = json.load(f)
                except Exception:
                    all_records = []
            all_records.insert(0, record)
            all_records = all_records[:50]
            os.makedirs(os.path.dirname(config.LABOUR_DEMAND_HISTORY_FILE), exist_ok=True)
            with open(config.LABOUR_DEMAND_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(all_records, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return result


@app.get("/api/workforce-planning/forecasts")
async def workforce_forecasts_list(
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """Get history of workforce planning forecast analyses."""
    history = []
    if os.path.exists(config.LABOUR_DEMAND_HISTORY_FILE):
        try:
            with open(config.LABOUR_DEMAND_HISTORY_FILE, "r", encoding="utf-8") as f:
                all_records = json.load(f)
            total = len(all_records)
            page = all_records[offset:offset + limit]
            history = [{
                "analysis_id": r.get("analysis_id"),
                "timestamp": r.get("timestamp"),
                "company_name": r.get("company_name", ""),
                "industry": r.get("industry", ""),
                "employee_count": r.get("employee_count", 0),
                "summary": r.get("summary", {}),
            } for r in page]
            return _ok({"total": total, "offset": offset, "limit": limit, "analyses": history})
        except Exception:
            return _ok({"total": 0, "offset": offset, "limit": limit, "analyses": []})
    return _ok({"total": 0, "offset": offset, "limit": limit, "analyses": []})


# ══════════════════════════════════════════════════════════
# MODULE 8: Enhanced Dashboard
# ══════════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def dashboard_get():
    """
    Enhanced dashboard with KPIs:
    - Employee stats (total, active, on leave, terminated)
    - Attendance today
    - Pending approvals
    - Payroll estimate for current month
    - Recent CV screening history
    """
    employees = hrms.list_employees()
    dept_summary = hrms.get_department_summary()
    recent_screenings = router.get_screening_history(limit=5, offset=0)

    now = datetime.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = [
        e for e in employees
        if e.get("created_at", "") >= this_month_start.isoformat()
    ]

    status_counts = {"Active": 0, "On Leave": 0, "Terminated": 0}
    for e in employees:
        s = e.get("status", "Active")
        if s in status_counts:
            status_counts[s] += 1

    recent_terminated = [
        e for e in employees
        if e.get("status") == "Terminated"
        and e.get("updated_at", "") >= (now.replace(day=1) - timedelta(days=30)).isoformat()
    ]

    # Attendance today
    today_str = date.today().isoformat()
    attendance_today = hrms.get_daily_attendance_summary(today_str)

    # Pending approvals
    pending_leave = len(hrms.get_pending_leave_requests())

    # Payroll this month (quick estimate from base salaries)
    total_base = sum(
        e.get("salary", {}).get("base", 0)
        for e in employees
        if e.get("status") == "Active"
    )
    active_count = status_counts["Active"]

    return {
        "employee_stats": {
            "total": len(employees),
            "active": status_counts["Active"],
            "on_leave": status_counts["On Leave"],
            "terminated": status_counts["Terminated"],
            "new_this_month": len(new_this_month),
            "terminated_this_month": len(recent_terminated),
        },
        "department_count": len(dept_summary),
        "departments": dept_summary,
        "recent_screenings": recent_screenings,
        "turnover_rate_this_month": round(
            len(recent_terminated) / max(len(employees), 1) * 100, 1
        ),
        "attendance_today": attendance_today,
        "pending_approvals": {
            "leave_requests": pending_leave
        },
        "payroll_this_month": {
            "total": total_base,
            "average": int(total_base / active_count) if active_count > 0 else 0,
        }
    }


# ══════════════════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════════════════

_start_time = datetime.now()

@app.get("/api/health")
async def health_check():
    """Health check endpoint with system status."""
    uptime = datetime.now() - _start_time
    try:
        all_emps = hrms.list_employees() if hrms else []
        emp_count = len(all_emps)
        active = sum(1 for e in all_emps if e.get("status") == "Active")
    except Exception:
        emp_count = -1
        active = -1
    return {
        "status": "healthy",
        "service": "AI-HR Bridge Platform v4.0",
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime": str(uptime).split(".")[0],
        "employees": {
            "total": emp_count,
            "active": active,
        },
        "version": "4.0",
        "timestamp": datetime.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════
# Booth Game endpoints
# ══════════════════════════════════════════════════════════

class BoothScreenRequest(BaseModel):
    category: str = "sales"
    candidate_file: str = ""
    jd: Optional[str] = None
    weights: Optional[Dict[str, int]] = None
    cv_content: Optional[str] = None  # Add this line for CV content

@app.get("/api/booth/options")
async def booth_options_get():
    """Return job categories and match criteria options."""
    return booth_mgr.get_options()

@app.get("/api/booth/candidate")
async def booth_candidate_get(
    category: str = Query("sales"),
    file: str = Query(...),
):
    """Return full CV text of a matched candidate."""
    content = booth_mgr.get_candidate_content(category, file)
    return {"category": category, "candidate_file": file, "content": content}

@app.get("/api/booth/match")
async def booth_candidate_match(
    category: str = Query("sales"),
    edu: Optional[str] = Query(None),
    exp: Optional[str] = Query(None, alias="experience"),
    skill: Optional[str] = Query(None),
    avail: Optional[str] = Query(None),
    random: Optional[bool] = Query(False),
):
    """Match audience selections to best candidate in a job category."""
    if random:
        return booth_mgr.random_match(category)
    selections = {k: v for k, v in [("edu", edu), ("exp", exp), ("skill", skill), ("avail", avail)] if v}
    if not selections:
        return booth_mgr.random_match(category)
    return booth_mgr.match(category, selections)

@app.post("/api/booth/screen")
async def booth_screen_run(req: BoothScreenRequest):
    """
    Run AI CV screening on a matched candidate.
    - If cv_content is provided and modified, use it
    - If cv_content is empty or unchanged, use the file
    - Never 500 - always returns a structured response
    """
    category = req.category or "sales"
    candidate_file = req.candidate_file
    jd = req.jd or booth_mgr.get_default_jd(category)
    
    # Check if CV content has been provided and modified
    use_cv_content = False
    cv_text_to_use = None
    
    if req.cv_content and req.cv_content.strip():
        # Check if this is a modified version
        try:
            # Get original CV content from the booth manager
            original_content = booth_mgr.get_candidate_content(category, candidate_file)
            
            # Clean both for comparison
            original_cleaned = ' '.join(original_content.split()) if original_content else ''
            provided_cleaned = ' '.join(req.cv_content.split())
            
            # If different, use provided content
            if original_cleaned != provided_cleaned:
                use_cv_content = True
                cv_text_to_use = req.cv_content
                logger.info(f"Using modified CV content for {candidate_file}")
            else:
                logger.info(f"CV content unchanged, using file {candidate_file}")
                
        except Exception as e:
            # If we can't get original, use provided content
            logger.warning(f"Could not get original content, using provided: {e}")
            use_cv_content = True
            cv_text_to_use = req.cv_content
    
    try:
        if use_cv_content and cv_text_to_use:
            # Use the modified CV content - create a temporary file
            import tempfile
            import os
            
            suffix = os.path.splitext(candidate_file)[1] or '.txt'
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
                f.write(cv_text_to_use)
                temp_path = f.name
            
            try:
                # Use batch_screen_cvs directly with the temp file
                cv_files = [{"file_path": temp_path, "file_name": candidate_file or "modified_cv.txt"}]
                result = await router.batch_screen_cvs(jd, cv_files, weights=req.weights)
                
                # Ensure proper format
                if isinstance(result, dict):
                    if "screening_results" not in result:
                        # Wrap in standard format
                        result = {
                            "success": True,
                            "screening_id": f"SCR_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}",
                            "total_processed": 1,
                            "successful": 1,
                            "failed": 0,
                            "weights_used": req.weights or {},
                            "screening_results": [{
                                "results": [result],
                                "culture_context_used": False,
                            }],
                            "errors": [],
                            "cv_modified": True
                        }
                    else:
                        # Already in the right format, add metadata
                        result["cv_modified"] = True
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temp file: {cleanup_error}")
        else:
            # Use the original file via booth_mgr
            result = await booth_mgr.screen_candidate(
                category, candidate_file, jd, router, weights=req.weights
            )
        
        # Add metadata about what was used
        if isinstance(result, dict):
            result["cv_source"] = "modified_text" if use_cv_content else "original_file"
            result["candidate_file"] = candidate_file
        
        return result
        
    except Exception as e:
        logger.error(f"Booth screening failed: {e}", exc_info=True)
        # Fallback response - never 500
        from screening_cache import default_scores
        fallback = default_scores("mid", "mid", "mid").copy()
        fallback["candidate_file"] = candidate_file or "unknown"
        fallback["candidate_name"] = candidate_file or "unknown"
        return {
            "screening_id": f"BOOTH_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}",
            "total_processed": 1,
            "successful": 1,
            "failed": 0,
            "weights_used": req.weights or {},
            "screening_results": [{
                "results": [fallback],
                "culture_context_used": False,
            }],
            "errors": [str(e)],
            "_fallback": True,
            "cv_source": "fallback",
            "candidate_file": candidate_file
        }
@app.get("/api/booth/history")
async def booth_history_get(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Get booth screening history."""
    return router.get_screening_history(limit=limit, offset=offset)

@app.get("/api/booth/default-jd")
async def booth_default_jd_get(category: str = Query("sales")):
    """Get the default job description for a category."""
    return {"category": category, "jd": booth_mgr.get_default_jd(category)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

