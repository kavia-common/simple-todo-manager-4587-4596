from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from typing import List, Optional
import sqlite3
import os

# ===== Theme Colors (for API docs and reference, not used in code logic) =====
THEME_COLORS = {
    "primary": "#3b82f6",
    "secondary": "#64748b",
    "success": "#06b6d4",
    "error": "#EF4444",
    "background": "#f9fafb",
    "surface": "#ffffff",
    "text": "#111827"
}

DB_NAME = "todo.db"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)

def get_db_connection():
    """Creates and returns a SQLite database connection with row_factory as dict."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates the tasks table if it does not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()
    conn.close()

init_db()

app = FastAPI(
    title="Todo API",
    description="A simple Todo backend with FastAPI, SQLite, and CORS for frontend integration.",
    version="1.0.0"
)

# Allow CORS from localhost:3000 only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskBase(BaseModel):
    title: str = Field(..., description="Title of the task", min_length=1, max_length=255)

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Updated title of the task", min_length=1, max_length=255)
    completed: Optional[bool] = Field(None, description="Completion state of the task")

class Task(TaskBase):
    id: int = Field(..., description="Unique ID of the task")
    completed: bool = Field(..., description="Whether the task is completed or not")

    class Config:
        orm_mode = True

# PUBLIC_INTERFACE
@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}

# PUBLIC_INTERFACE
@app.get("/tasks", response_model=List[Task], tags=["Tasks"], summary="Get all tasks")
def list_tasks():
    """Get all todo tasks."""
    conn = get_db_connection()
    cursor = conn.cursor()
    tasks = cursor.execute("SELECT id, title, completed FROM tasks").fetchall()
    conn.close()
    task_list = [
        Task(id=row["id"], title=row["title"], completed=bool(row["completed"])) for row in tasks
    ]
    return task_list

# PUBLIC_INTERFACE
@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["Tasks"], summary="Create a new task")
def create_task(task: TaskCreate):
    """Create a new todo task."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (title, completed) VALUES (?, ?)",
        (task.title, 0)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return Task(id=task_id, title=task.title, completed=False)

# PUBLIC_INTERFACE
@app.put("/tasks/{task_id}", response_model=Task, tags=["Tasks"], summary="Update a task")
def update_task(task_id: int, task: TaskUpdate):
    """Update title or completion of a task."""
    conn = get_db_connection()
    cursor = conn.cursor()
    existing = cursor.execute("SELECT id, title, completed FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found.")
    # Determine new values
    new_title = task.title if task.title is not None else existing["title"]
    new_completed = int(task.completed) if task.completed is not None else existing["completed"]
    cursor.execute(
        "UPDATE tasks SET title=?, completed=? WHERE id=?",
        (new_title, new_completed, task_id)
    )
    conn.commit()
    updated = cursor.execute("SELECT id, title, completed FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return Task(id=updated["id"], title=updated["title"], completed=bool(updated["completed"]))

# PUBLIC_INTERFACE
@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tasks"], summary="Delete a task")
def delete_task(task_id: int):
    """Delete a task by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})

# PUBLIC_INTERFACE
@app.patch("/tasks/{task_id}/toggle", response_model=Task, tags=["Tasks"], summary="Toggle completion")
def toggle_task_complete(task_id: int):
    """Toggle the completed status of a task."""
    conn = get_db_connection()
    cursor = conn.cursor()
    existing = cursor.execute("SELECT id, title, completed FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found.")
    toggled_completed = 0 if existing["completed"] else 1
    cursor.execute(
        "UPDATE tasks SET completed=? WHERE id=?",
        (toggled_completed, task_id)
    )
    conn.commit()
    updated = cursor.execute("SELECT id, title, completed FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return Task(id=updated["id"], title=updated["title"], completed=bool(updated["completed"]))
