"""
Task Manager - Storage and lifecycle management for external agent tasks.

Now uses PostgreSQL for centralized storage.
"""
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

from promaia.storage.postgres_db import get_postgres_db, pg_connect
import psycopg2.extras
from .models import AgentTask, TaskResult, TaskStatus, TaskType

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Manages external agent tasks in PostgreSQL database.

    Handles task submission, status tracking, result storage,
    and querying of tasks and results.
    """

    def __init__(self, db_path: str = "data/hybrid_metadata.db", timeout: float = 30.0):
        """
        Initialize task manager.
        
        Args:
            db_path: Deprecated - kept for backward compatibility.
            timeout: Not used with PostgreSQL pooling.
        """
        self.db_path = db_path
        self.timeout = timeout
        self.db = get_postgres_db()
        self._ensure_tables()

    @contextmanager
    def _get_connection(self):
        """Get a PostgreSQL connection from the pool."""
        conn = None
        try:
            conn = self.db._pool.getconn()
            conn.autocommit = False
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.db._pool.putconn(conn)

    def _ensure_tables(self):
        """Verify agent_tasks and agent_results tables exist."""
        try:
            if not self.db.table_exists('agent_tasks'):
                logger.warning("agent_tasks table not found. Run: python -m promaia db init")

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tasks_draft
                    ON agent_tasks(related_draft_id)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_results_task
                    ON agent_results(task_id)
                """)

                conn.commit()
                logger.info("✅ Agent tasks tables initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize agent_tasks tables: {e}")
            raise

    def submit_task(self, task: AgentTask) -> str:
        """
        Submit a new task for an external agent.

        Args:
            task: AgentTask to submit

        Returns:
            task_id of the submitted task
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO agent_tasks (
                        task_id, task_type, workspace, instructions, context, metadata,
                        status, created_at, expires_at, started_at, completed_at,
                        related_draft_id, related_thread_id, progress_notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    task.task_id,
                    task.task_type.value,
                    task.workspace,
                    task.instructions,
                    json.dumps(task.context),
                    json.dumps(task.metadata),
                    task.status.value,
                    task.created_at.isoformat(),
                    task.expires_at.isoformat() if task.expires_at else None,
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.related_draft_id,
                    task.related_thread_id,
                    json.dumps(task.progress_notes)
                ))

                conn.commit()
                logger.info(f"✅ Submitted task {task.task_id} ({task.task_type.value})")
                return task.task_id

        except Exception as e:
            logger.error(f"❌ Failed to submit task: {e}")
            raise

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a specific task by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                cursor.execute("SELECT * FROM agent_tasks WHERE task_id = %s", (task_id,))
                row = cursor.fetchone()

                if row:
                    return self._row_to_task(dict(row))
                return None

        except Exception as e:
            logger.error(f"❌ Failed to get task {task_id}: {e}")
            return None

    def list_tasks(
        self,
        workspace: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        limit: Optional[int] = None
    ) -> List[AgentTask]:
        """
        List tasks with optional filtering.

        Args:
            workspace: Filter by workspace
            status: Filter by status
            task_type: Filter by task type
            limit: Maximum number of tasks to return

        Returns:
            List of matching tasks
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                query = "SELECT * FROM agent_tasks WHERE 1=1"
                params = []

                if workspace:
                    query += " AND workspace = %s"
                    params.append(workspace)

                if status:
                    query += " AND status = %s"
                    params.append(status.value)

                if task_type:
                    query += " AND task_type = %s"
                    params.append(task_type.value)

                query += " ORDER BY created_at DESC"

                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_task(dict(row)) for row in rows]

        except Exception as e:
            logger.error(f"❌ Failed to list tasks: {e}")
            return []

    def get_pending_tasks(self, workspace: Optional[str] = None) -> List[AgentTask]:
        """Get all pending tasks."""
        return self.list_tasks(workspace=workspace, status=TaskStatus.PENDING)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress_note: Optional[str] = None
    ):
        """
        Update task status and optionally add progress note.

        Args:
            task_id: Task ID to update
            status: New status
            progress_note: Optional progress note to add
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                now = datetime.now(timezone.utc).isoformat()

                # Get current task to update timestamps and notes
                cursor.execute("SELECT started_at, completed_at, progress_notes FROM agent_tasks WHERE task_id = %s", (task_id,))
                row = cursor.fetchone()

                if not row:
                    logger.error(f"❌ Task {task_id} not found")
                    return

                started_at, completed_at, progress_notes = row
                notes = json.loads(progress_notes) if progress_notes else []

                # Update timestamps based on status
                if status == TaskStatus.IN_PROGRESS and not started_at:
                    started_at = now

                if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    completed_at = now

                # Add progress note if provided
                if progress_note:
                    notes.append(f"{now}: {progress_note}")

                cursor.execute("""
                    UPDATE agent_tasks
                    SET status = %s, started_at = %s, completed_at = %s, progress_notes = %s
                    WHERE task_id = %s
                """, (status.value, started_at, completed_at, json.dumps(notes), task_id))

                conn.commit()
                logger.info(f"✅ Updated task {task_id} status to {status.value}")

        except Exception as e:
            logger.error(f"❌ Failed to update task status: {e}")
            raise

    def save_result(self, result: TaskResult):
        """
        Save a task result.

        Args:
            result: TaskResult to save
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO agent_results (
                        task_id, status, result_data, metadata,
                        error_message, created_at,
                        agent_name, agent_version, execution_time_seconds
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    result.task_id,
                    result.status.value,
                    json.dumps(result.result_data),
                    json.dumps(result.metadata),
                    result.error_message,
                    result.created_at.isoformat(),
                    result.agent_name,
                    result.agent_version,
                    result.execution_time_seconds
                ))

                # Update task status to match result (in same transaction)
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute("""
                    UPDATE agent_tasks
                    SET status = %s, completed_at = %s
                    WHERE task_id = %s
                """, (result.status.value, now, result.task_id))

                conn.commit()
                logger.info(f"✅ Saved result for task {result.task_id}")

        except Exception as e:
            logger.error(f"❌ Failed to save result: {e}")
            raise

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the latest result for a task."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                cursor.execute("""
                    SELECT * FROM agent_results
                    WHERE task_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (task_id,))

                row = cursor.fetchone()

                if row:
                    return self._row_to_result(dict(row))
                return None

        except Exception as e:
            logger.error(f"❌ Failed to get result for task {task_id}: {e}")
            return None

    def get_tasks_by_draft(self, draft_id: str) -> List[AgentTask]:
        """Get all tasks related to a specific draft."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                cursor.execute("""
                    SELECT * FROM agent_tasks
                    WHERE related_draft_id = %s
                    ORDER BY created_at DESC
                """, (draft_id,))

                rows = cursor.fetchall()
                return [self._row_to_task(dict(row)) for row in rows]

        except Exception as e:
            logger.error(f"❌ Failed to get tasks for draft {draft_id}: {e}")
            return []

    def cleanup_expired_tasks(self) -> int:
        """
        Mark expired tasks as EXPIRED.

        Returns:
            Number of tasks marked as expired
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc).isoformat()

                cursor.execute("""
                    UPDATE agent_tasks
                    SET status = %s
                    WHERE status IN (%s, %s)
                    AND expires_at IS NOT NULL
                    AND expires_at < %s
                """, (
                    TaskStatus.EXPIRED.value,
                    TaskStatus.PENDING.value,
                    TaskStatus.IN_PROGRESS.value,
                    now
                ))

                count = cursor.rowcount
                conn.commit()

                if count > 0:
                    logger.info(f"✅ Marked {count} tasks as expired")

                return count

        except Exception as e:
            logger.error(f"❌ Failed to cleanup expired tasks: {e}")
            return 0

    @staticmethod
    def _row_to_task(row: Dict[str, Any]) -> AgentTask:
        """Convert database row to AgentTask."""
        return AgentTask(
            task_id=row['task_id'],
            task_type=TaskType(row['task_type']),
            workspace=row['workspace'],
            instructions=row['instructions'],
            context=json.loads(row['context']),
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            status=TaskStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            related_draft_id=row['related_draft_id'],
            related_thread_id=row['related_thread_id'],
            progress_notes=json.loads(row['progress_notes']) if row['progress_notes'] else []
        )

    @staticmethod
    def _row_to_result(row: Dict[str, Any]) -> TaskResult:
        """Convert database row to TaskResult."""
        return TaskResult(
            task_id=row['task_id'],
            status=TaskStatus(row['status']),
            result_data=json.loads(row['result_data']),
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            error_message=row['error_message'],
            created_at=datetime.fromisoformat(row['created_at']),
            agent_name=row['agent_name'],
            agent_version=row['agent_version'],
            execution_time_seconds=row['execution_time_seconds']
        )
