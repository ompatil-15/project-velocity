"""
Minimal SQLite-based job persistence for async workflow tracking.
Includes action items for merchant notifications.
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
                result TEXT,
                action_items TEXT DEFAULT '[]'
            )
        """)
        await db.commit()
        
        # Add action_items column if it doesn't exist (for existing DBs)
        try:
            await db.execute("ALTER TABLE jobs ADD COLUMN action_items TEXT DEFAULT '[]'")
            await db.commit()
        except:
            pass  # Column already exists


async def create_job(thread_id: str, merchant_id: str) -> None:
    """Create a new job entry."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO jobs (thread_id, merchant_id, status, stage, created_at, updated_at, action_items)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (thread_id, merchant_id, JobStatus.QUEUED.value, "INPUT", now, now, "[]")
        )
        await db.commit()


async def update_job(
    thread_id: str,
    status: Optional[JobStatus] = None,
    stage: Optional[str] = None,
    error_message: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    action_items: Optional[List[Dict[str, Any]]] = None,
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
        params.append(json.dumps(serializable_result, default=str))
    
    if action_items is not None:
        updates.append("action_items = ?")
        params.append(json.dumps(action_items, default=str))
    
    params.append(thread_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE thread_id = ?",
            params
        )
        await db.commit()


async def append_action_items(thread_id: str, new_items: List[Dict[str, Any]]) -> None:
    """Append new action items to existing ones (immutable append-only)."""
    job = await get_job(thread_id)
    if not job:
        return
    
    existing_items = job.get("action_items", [])
    if isinstance(existing_items, str):
        existing_items = json.loads(existing_items)
    
    # Append new items (immutable - never modify existing)
    all_items = existing_items + new_items
    
    await update_job(thread_id, action_items=all_items)


async def mark_items_resolved(thread_id: str, item_ids: List[str]) -> None:
    """Mark specific action items as resolved by their IDs."""
    job = await get_job(thread_id)
    if not job:
        return
    
    action_items = job.get("action_items", [])
    if isinstance(action_items, str):
        action_items = json.loads(action_items)
    
    now = datetime.now().isoformat()
    
    # Create new list with resolved items (immutable pattern)
    updated_items = []
    for item in action_items:
        if item.get("id") in item_ids and not item.get("resolved"):
            # Create a new dict with resolved status
            updated_item = {**item, "resolved": True, "resolved_at": now}
            updated_items.append(updated_item)
        else:
            updated_items.append(item)
    
    await update_job(thread_id, action_items=updated_items)


async def get_action_items(
    thread_id: str, 
    include_resolved: bool = False
) -> List[Dict[str, Any]]:
    """Get action items for a job, optionally filtering out resolved ones."""
    job = await get_job(thread_id)
    if not job:
        return []
    
    action_items = job.get("action_items", [])
    if isinstance(action_items, str):
        action_items = json.loads(action_items)
    
    if include_resolved:
        return action_items
    
    # Filter to only pending (unresolved) items
    return [item for item in action_items if not item.get("resolved")]


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
        # Parse action_items JSON if present
        if job.get("action_items"):
            job["action_items"] = json.loads(job["action_items"])
        
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
