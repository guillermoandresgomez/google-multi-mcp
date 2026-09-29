import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

from auth import get_account_names, get_account_email
from tools import gmail, calendar, drive, tasks

mcp = FastMCP("google-multi", instructions="""
MCP Server para gestionar múltiples cuentas Google simultáneamente.
Cada herramienta requiere un parámetro 'account' que identifica la cuenta.
Usa 'list_accounts' para ver las cuentas disponibles.
""")


# ── Account management ──

@mcp.tool()
def list_accounts() -> list[dict]:
    """List all configured Google accounts."""
    return [{"name": name, "email": get_account_email(name)} for name in get_account_names()]


# ── Gmail tools ──

@mcp.tool()
def gmail_search(account: str, query: str, max_results: int = 10) -> list[dict]:
    """Search emails in a Google account. Uses Gmail search syntax (e.g. 'from:user@example.com', 'is:unread', 'subject:hello')."""
    return gmail.search_emails(account, query, max_results)


@mcp.tool()
def gmail_read(account: str, message_id: str) -> dict:
    """Read the full content of an email by its message ID."""
    return gmail.read_email(account, message_id)


@mcp.tool()
def gmail_read_thread(account: str, thread_id: str) -> dict:
    """Read all messages in an email thread."""
    return gmail.read_thread(account, thread_id)


@mcp.tool()
def gmail_send(account: str, to: str, subject: str, body: str,
               attachments: list[str] | None = None) -> dict:
    """Send an email from the specified account. Optionally attach local files by providing their full Windows paths (e.g. 'C:\\Users\\ag87r\\Documents\\report.pdf')."""
    return gmail.send_email(account, to, subject, body, attachments)


@mcp.tool()
def gmail_create_draft(account: str, to: str, subject: str, body: str,
                       attachments: list[str] | None = None) -> dict:
    """Create an email draft in the specified account. Optionally attach local files by providing their full Windows paths (e.g. 'C:\\Users\\ag87r\\Documents\\report.pdf')."""
    return gmail.create_draft(account, to, subject, body, attachments)


@mcp.tool()
def gmail_list_drafts(account: str, max_results: int = 20) -> list[dict]:
    """List drafts in the specified account (id, message_id, subject, to, date, snippet)."""
    return gmail.list_drafts(account, max_results)


@mcp.tool()
def gmail_delete_draft(account: str, draft_id: str, confirm: bool = False) -> dict:
    """Permanently delete a draft (irreversible). Use ONLY after the user has explicitly approved deleting
    that specific draft. Requires confirm=true; get draft_id from gmail_list_drafts (the draft 'id', not message_id)."""
    if not confirm:
        return {"status": "not_deleted", "reason": "confirm=true required; ask the user for explicit approval first."}
    return gmail.delete_draft(account, draft_id)


@mcp.tool()
def gmail_list_labels(account: str) -> list[dict]:
    """List all labels/folders in a Gmail account."""
    return gmail.list_labels(account)


@mcp.tool()
def gmail_archive(account: str, message_id: str) -> dict:
    """Archive an email (remove from inbox)."""
    return gmail.archive_email(account, message_id)


@mcp.tool()
def gmail_mark_read(account: str, message_id: str, read: bool = True) -> dict:
    """Mark an email as read or unread."""
    return gmail.mark_read(account, message_id, read)


# ── Calendar tools ──

@mcp.tool()
def calendar_list_events(account: str, days_ahead: int = 7, max_results: int = 20,
                          start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    """List calendar events. By default returns events for the next N days from today.
    To list events in a past or specific range, pass start_date and end_date as 'YYYY-MM-DD'."""
    return calendar.list_events(account, days_ahead, max_results, start_date, end_date)

@mcp.tool()
def calendar_create_event(account: str, summary: str, start: str, end: str,
                          description: str = "", location: str = "",
                          attendees: list[str] | None = None,
                          add_meet: bool = False) -> dict:
    """Create a calendar event. Start/end must be ISO 8601 datetime strings (e.g. '2026-05-15T10:00:00-05:00'). Set add_meet=true to generate a Google Meet link automatically."""
    return calendar.create_event(account, summary, start, end, description, location, attendees, add_meet)


@mcp.tool()
def calendar_update_event(account: str, event_id: str, summary: str | None = None,
                          start: str | None = None, end: str | None = None,
                          description: str | None = None, location: str | None = None) -> dict:
    """Update an existing calendar event. Only provided fields will be changed."""
    return calendar.update_event(account, event_id, summary, start, end, description, location)


@mcp.tool()
def calendar_delete_event(account: str, event_id: str) -> dict:
    """Delete a calendar event."""
    return calendar.delete_event(account, event_id)


# ── Drive tools ──

@mcp.tool()
def drive_search(account: str, query: str, max_results: int = 10, parent_id: str | None = None) -> list[dict]:
    """Search files in Google Drive by name. Optionally scope the search to inside a folder with parent_id."""
    return drive.search_files(account, query, max_results, parent_id)


@mcp.tool()
def drive_read(account: str, file_id: str) -> dict:
    """Read the content of a file from Google Drive. Supports Google Docs, Sheets (as CSV), and text files."""
    return drive.read_file_content(account, file_id)


@mcp.tool()
def drive_list_recent(account: str, max_results: int = 10) -> list[dict]:
    """List recently modified files in Google Drive."""
    return drive.list_recent_files(account, max_results)


@mcp.tool()
def drive_create_file(account: str, name: str, content: str = "",
                      target_mime_type: str = "text/plain", parent_id: str | None = None) -> dict:
    """Create a file in Google Drive.
    Use target_mime_type='application/vnd.google-apps.document' to create an editable Google Doc
    from plain-text content (Drive converts it automatically).
    Use target_mime_type='text/markdown' or 'text/plain' to create a raw text/markdown file with
    no conversion (use this for cache/context files meant to be read back programmatically).
    Optionally place it inside parent_id (a folder id from drive_find_or_create_folder)."""
    return drive.create_file(account, name, content, target_mime_type, parent_id)


@mcp.tool()
def drive_update_file_content(account: str, file_id: str, content: str) -> dict:
    """Replace the content of an existing Drive file (Google Doc or plain text/markdown file) with new content, keeping its current type."""
    return drive.update_file_content(account, file_id, content)


@mcp.tool()
def drive_create_folder(account: str, name: str, parent_id: str | None = None) -> dict:
    """Create a folder in Google Drive. Optionally nested inside parent_id."""
    return drive.create_folder(account, name, parent_id)


@mcp.tool()
def drive_find_or_create_folder(account: str, name: str, parent_id: str | None = None) -> dict:
    """Find a folder by exact name (optionally scoped inside parent_id), or create it if it doesn't exist. Returns its id — reuse this id across runs so files always land in the same folder."""
    return drive.find_or_create_folder(account, name, parent_id)


@mcp.tool()
def drive_trash_file(account: str, file_id: str, confirm: bool = False) -> dict:
    """Move a Drive file or folder to the trash (recoverable, not permanent). Use ONLY after the
    user has explicitly approved deleting that specific file. Requires confirm=true."""
    if not confirm:
        return {"status": "not_deleted", "reason": "confirm=true required; ask the user for explicit approval first."}
    return drive.trash_file(account, file_id)


# ── Tasks tools ──

@mcp.tool()
def tasks_list_tasklists(account: str) -> list[dict]:
    """List all task lists in Google Tasks."""
    return tasks.list_tasklists(account)


@mcp.tool()
def tasks_list(account: str, tasklist_id: str = "@default", show_completed: bool = False) -> list[dict]:
    """List tasks in a task list."""
    return tasks.list_tasks(account, tasklist_id, show_completed)


@mcp.tool()
def tasks_create(account: str, title: str, tasklist_id: str = "@default",
                 notes: str = "", due: str = "") -> dict:
    """Create a new task. Due date format: RFC 3339 (e.g. '2026-05-20T00:00:00.000Z')."""
    return tasks.create_task(account, title, tasklist_id, notes, due)


@mcp.tool()
def tasks_update(account: str, task_id: str, tasklist_id: str = "@default",
                 title: str | None = None, notes: str | None = None, due: str | None = None) -> dict:
    """Update an existing task. Only provided fields will be changed."""
    return tasks.update_task(account, task_id, tasklist_id, title, notes, due)


@mcp.tool()
def tasks_complete(account: str, task_id: str, tasklist_id: str = "@default") -> dict:
    """Mark a task as completed."""
    return tasks.complete_task(account, task_id, tasklist_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
