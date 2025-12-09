"""
Minimal SQLite-based job persistence for async workflow tracking.
"""
import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.schema import JobStatus

DB_PATH = "db/checkpoints.sqlite"


async def init_job_table():
    """Create the jobs table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                thread_id TEXT PRIMARY KEY,
                merchant_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'QUEUED',
                stage TEXT DEFAULT 'INPUT',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_message TEXT,
                result TEXT
            )
        """)
        await db.commit()


async def create_job(thread_id: str, merchant_id: str) -> None:
    """Create a new job entry."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO jobs (thread_id, merchant_id, status, stage, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (thread_id, merchant_id, JobStatus.QUEUED.value, "INPUT", now, now)
        )
        await db.commit()


async def update_job(
    thread_id: str,
    status: Optional[JobStatus] = None,
    stage: Optional[str] = None,
    error_message: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> None:
    """Update an existing job."""
    updates = ["updated_at = ?"]
    params = [datetime.now().isoformat()]
    
    if status is not None:
        updates.append("status = ?")
        params.append(status.value)
    
    if stage is not None:
        updates.append("stage = ?")
        params.append(stage)
    
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    
    if result is not None:
        # Serialize result, excluding non-serializable message objects
        serializable_result = {
            k: v for k, v in result.items() 
            if k != "messages"  # Skip LangChain message objects
        }
        updates.append("result = ?")
        params.append(json.dumps(serializable_result))
    
    params.append(thread_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE thread_id = ?",
            params
        )
        await db.commit()


async def get_job(thread_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by thread_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM jobs WHERE thread_id = ?",
            (thread_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        job = dict(row)
        # Parse result JSON if present
        if job.get("result"):
            job["result"] = json.loads(job["result"])
        
        return job


async def list_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent jobs."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT thread_id, merchant_id, status, stage, created_at, updated_at, error_message FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

