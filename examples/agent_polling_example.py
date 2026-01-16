#!/usr/bin/env python3
"""
Example: External Agent Polling Script

This demonstrates how an external agent (like Claude Code) would:
1. Poll the SQLite database for pending tasks
2. Process the task
3. Submit results back

This is a simple example - in practice, Claude Code would integrate
this directly into its workflow.
"""
import time
from promaia.external_agent import TaskManager, TaskStatus, TaskResult


def process_task(task):
    """
    Simulate processing a task.

    In reality, this is where Claude Code would:
    - Read the task instructions
    - Access the context
    - Execute code changes, edit drafts, etc.
    - Generate results
    """
    print(f"\n🤖 Processing task: {task.task_id[:8]}...")
    print(f"   Type: {task.task_type.value}")
    print(f"   Instructions: {task.instructions}")
    print(f"   Context: {task.context}")

    # Simulate work
    time.sleep(1)

    # Generate result based on task type
    if task.task_type.value == "email_draft":
        return {
            "status": "completed",
            "changes_made": [
                "Changed 'Hey' to 'Hi [Name]'",
                "Expanded 'wanted to follow up on our chat' to specific details",
                "Added clear call-to-action",
                "Improved closing"
            ],
            "revised_draft": """Hi [Name],

I wanted to follow up on our conversation from yesterday regarding the project timeline.

Based on our discussion, I believe we can move forward with the approach we outlined. Could you please review the attached proposal and let me know your thoughts by Friday?

Looking forward to your feedback.

Best regards"""
        }
    else:
        return {
            "status": "completed",
            "message": f"Processed {task.task_type.value} task successfully"
        }


def poll_and_process():
    """
    Main polling loop.

    In production, Claude Code would:
    - Run this periodically (cron, systemd timer, or continuous loop)
    - Handle multiple workspaces
    - Process tasks in parallel
    - Handle errors gracefully
    """
    task_manager = TaskManager()

    print("🔍 Polling for pending tasks...")

    # Get pending tasks
    tasks = task_manager.get_pending_tasks()

    if not tasks:
        print("✅ No pending tasks found")
        return

    print(f"📋 Found {len(tasks)} pending task(s)\n")

    for task in tasks:
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"Task ID: {task.task_id}")
        print(f"Workspace: {task.workspace}")
        print(f"Type: {task.task_type.value}")

        # Mark as started
        print(f"\n⏳ Marking task as started...")
        task_manager.update_task_status(
            task.task_id,
            TaskStatus.IN_PROGRESS,
            "Started by external agent"
        )

        try:
            # Process the task
            result_data = process_task(task)

            # Submit success result
            result = TaskResult.create_success(
                task_id=task.task_id,
                result_data=result_data,
                agent_name="Example Agent",
                execution_time=1.0
            )

            task_manager.save_result(result)

            print(f"\n✅ Task completed successfully!")
            print(f"   Result: {result_data.get('status', 'completed')}")

        except Exception as e:
            # Submit failure result
            print(f"\n❌ Task failed: {e}")

            result = TaskResult.create_failure(
                task_id=task.task_id,
                error_message=str(e),
                agent_name="Example Agent"
            )

            task_manager.save_result(result)

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"✨ Finished processing all tasks")


if __name__ == "__main__":
    print("External Agent Polling Example")
    print("=" * 45)
    print()

    poll_and_process()

    print("\n💡 Tip: In production, you would:")
    print("   - Run this in a loop with sleep intervals")
    print("   - Use a systemd timer or cron job")
    print("   - Process multiple workspaces")
    print("   - Handle tasks in parallel")
