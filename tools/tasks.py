from googleapiclient.discovery import build

from auth import get_credentials


def _service(account: str):
    return build("tasks", "v1", credentials=get_credentials(account))


def list_tasklists(account: str) -> list[dict]:
    svc = _service(account)
    result = svc.tasklists().list(maxResults=100).execute()
    return [{"id": t["id"], "title": t["title"]} for t in result.get("items", [])]


def list_tasks(account: str, tasklist_id: str = "@default", show_completed: bool = False) -> list[dict]:
    svc = _service(account)
    result = svc.tasks().list(
        tasklist=tasklist_id, showCompleted=show_completed, maxResults=100
    ).execute()
    tasks = []
    for t in result.get("items", []):
        tasks.append({
            "id": t["id"],
            "title": t.get("title", ""),
            "status": t.get("status", ""),
            "due": t.get("due", ""),
            "notes": t.get("notes", ""),
        })
    return tasks


def create_task(account: str, title: str, tasklist_id: str = "@default",
                notes: str = "", due: str = "") -> dict:
    svc = _service(account)
    body = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = due
    task = svc.tasks().insert(tasklist=tasklist_id, body=body).execute()
    return {"id": task["id"], "title": task["title"], "status": task.get("status", "")}


def update_task(account: str, task_id: str, tasklist_id: str = "@default",
                title: str | None = None, notes: str | None = None, due: str | None = None) -> dict:
    svc = _service(account)
    task = svc.tasks().get(tasklist=tasklist_id, task=task_id).execute()
    if title is not None:
        task["title"] = title
    if notes is not None:
        task["notes"] = notes
    if due is not None:
        task["due"] = due
    updated = svc.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
    return {"id": updated["id"], "title": updated["title"], "status": updated.get("status", "")}


def complete_task(account: str, task_id: str, tasklist_id: str = "@default") -> dict:
    svc = _service(account)
    task = svc.tasks().get(tasklist=tasklist_id, task=task_id).execute()
    task["status"] = "completed"
    updated = svc.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
    return {"id": updated["id"], "title": updated["title"], "status": "completed"}
