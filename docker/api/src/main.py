"""
Task API service for the task management application.

This module provides a FastAPI application for managing tasks with
PostgreSQL database backend. It includes endpoints for creating and listing tasks,
as well as a health check endpoint.
"""

from logging import Logger, LoggerAdapter
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable, Awaitable
from contextlib import asynccontextmanager
from typing import Any

import asyncpg  # type: ignore
from fastapi import FastAPI, HTTPException, Request, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from logger import get_logger

# Configure structured JSON logging
logger = get_logger("task-api")

# Database connection settings
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "taskdb")
DB_USER = os.getenv("DB_USER", "taskuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "taskpass")


# Request ID middleware
class RequestContextMiddleware:
    """Middleware to add request context to each request."""
    
    async def __call__(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = str(uuid.uuid4())
        # Set extra logger context for this request
        logger_adapter = LoggerAdapter(
            logger, 
            {"request_id": request_id}
        )
        
        # Store the logger adapter in request state
        request.state.logger = logger_adapter
        
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifecycle event handler for FastAPI application."""
    # Startup
    try:
        conn = await asyncpg.connect(  # type: ignore
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )

        # Create tasks table if it doesn't exist
        sql = """
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                user_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            -- Create index for filtering by user_id (most common use case)
            CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id);
            -- Create composite index for filtering by user_id and status
            CREATE INDEX IF NOT EXISTS idx_tasks_user_id_status
            ON tasks (user_id, status);
            -- Create index for sorting/filtering by creation time
            CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks (created_at);
            -- Create index for status-based filtering
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
        """
        await conn.execute(sql)  # type: ignore

        await conn.close()  # type: ignore
        
        # Log with structured JSON
        logger.info(
            "Database initialized successfully", 
            extra={
                "database": DB_NAME,
                "host": DB_HOST,
                "component": "database"
            }
        )
    except Exception as e:
        # Log with structured JSON
        logger.error(
            f"Database initialization failed: {e}", 
            extra={
                "database": DB_NAME,
                "host": DB_HOST,
                "component": "database",
                "error_details": str(e)
            },
            exc_info=True
        )

    yield  # Server is running

    # Shutdown
    logger.info("Service shutting down", extra={"component": "application"})


app = FastAPI(title="Task Management API", lifespan=lifespan)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request context middleware
@app.middleware("http")
async def request_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Middleware to add request context and timing to each request.
    
    Args:
        request: The FastAPI request object
        call_next: The next middleware or route handler
        
    Returns:
        The response from the route handler
    """
    # Generate a unique request ID
    request_id = str(uuid.uuid4())
    
    # Extract user ID from headers or query params if available
    user_id = None
    if "X-User-ID" in request.headers:
        user_id = request.headers.get("X-User-ID")
    elif "user_id" in request.query_params:
        user_id = request.query_params.get("user_id")
    
    # Create a request-specific logger with context
    extra_context = {
        "request_id": request_id,
        "path": str(request.url.path),
        "method": request.method
    }
    if user_id:
        extra_context["user_id"] = user_id
        
    request.state.logger = LoggerAdapter(logger, extra_context)
    
    # Record the start time for performance measurement
    start_time = time.time()
    
    # Process the request
    try:
        response = await call_next(request)
        
        # Calculate request duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log the completed request
        request.state.logger.info(
            f"Request completed: {request.method} {request.url.path}",
            extra={
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "content_type": response.headers.get("content-type", ""),
                "user_agent": request.headers.get("user-agent", ""),
                "referer": request.headers.get("referer", ""),
                "component": "http",
                "operation": "request"
            }
        )
        
        # Add request ID to response headers for tracking
        response.headers["X-Request-ID"] = request_id
        
        return response
    except Exception as e:
        # Calculate request duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log the failed request
        request.state.logger.error(
            f"Request failed: {request.method} {request.url.path}",
            extra={
                "duration_ms": duration_ms,
                "error": str(e),
                "component": "http",
                "operation": "request"
            },
            exc_info=True
        )
        raise


class Task(BaseModel):
    """Model representing a task input."""

    title: str
    description: str | None = None
    user_id: str


class TaskResponse(BaseModel):
    """Model representing a task response."""

    id: int
    title: str
    description: str | None
    status: str
    user_id: str


async def get_request_logger_dependency(request: Request) -> Any:
    """Dependency to get the request-specific logger."""
    return getattr(request.state, "logger", logger)


@app.get("/health")
async def health_check(
    request_logger: LoggerAdapter[Logger] = Depends(get_request_logger_dependency)
) -> dict[str, str]:
    """Health check endpoint."""
    request_logger.info("Health check request received", extra={"component": "api"})
    return {"status": "healthy", "service": "task-api"}


@app.post("/tasks", response_model=TaskResponse)
async def create_task(
    task: Task, 
    request_logger: LoggerAdapter[Logger] = Depends(get_request_logger_dependency)
) -> TaskResponse:
    """Create a new task."""
    request_logger.info(
        "Creating task for user", 
        extra={
            "user_id": task.user_id,
            "component": "api",
            "operation": "create_task"
        }
    )
    
    try:
        conn = await asyncpg.connect(  # type: ignore
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )

        query = """
            INSERT INTO tasks (title, description, user_id)
            VALUES ($1, $2, $3)
            RETURNING id, title, description, status, user_id
        """
        result = await conn.fetchrow(query, task.title, task.description, task.user_id)  # type: ignore
        await conn.close()  # type: ignore

        # Log success with structured data
        request_logger.info(
            "Task created successfully", 
            extra={
                "user_id": task.user_id,
                "task_id": result["id"],  # type: ignore
                "component": "api",
                "operation": "create_task"
            }
        )

        return TaskResponse(
            id=result["id"],  # type: ignore
            title=result["title"],  # type: ignore
            description=result["description"],  # type: ignore
            status=result["status"],  # type: ignore
            user_id=result["user_id"],  # type: ignore
        )
    except Exception as e:
        # Log error with structured data
        request_logger.error(
            "Error creating task", 
            extra={
                "user_id": task.user_id,
                "error": str(e),
                "component": "api",
                "operation": "create_task"
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e


@app.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    user_id: str,
    request_logger: LoggerAdapter[Logger] = Depends(get_request_logger_dependency)
) -> list[TaskResponse]:
    """
    List tasks for a specific user.

    Args:
        user_id: The ID of the user whose tasks to retrieve
    """
    request_logger.info(
        "Fetching tasks for user", 
        extra={
            "user_id": user_id,
            "component": "api",
            "operation": "list_tasks"
        }
    )
    
    try:
        conn = await asyncpg.connect(  # type: ignore
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )

        rows = await conn.fetch(  # type: ignore
            """
            SELECT id, title, description, status, user_id FROM tasks
            WHERE user_id = $1 ORDER BY id DESC
            """,
            user_id,
        )
        await conn.close()  # type: ignore

        # Log success with task count
        request_logger.info(
            "Tasks retrieved successfully", 
            extra={
                "user_id": user_id,
                "task_count": len(rows),  # type: ignore
                "component": "api",
                "operation": "list_tasks"
            }
        )

        return [
            TaskResponse(
                id=row["id"],  # type: ignore
                title=row["title"],  # type: ignore
                description=row["description"],  # type: ignore
                status=row["status"],  # type: ignore
                user_id=row["user_id"],  # type: ignore
            )
            for row in rows  # type: ignore
        ]
    except Exception as e:
        # Log error with structured data
        request_logger.error(
            "Error listing tasks for user", 
            extra={
                "user_id": user_id,
                "error": str(e),
                "component": "api",
                "operation": "list_tasks"
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e


if __name__ == "__main__":
    import uvicorn

    # Log application startup
    logger.info(
        "Starting Task API service", 
        extra={
            "component": "application",
            "environment": os.getenv("ENVIRONMENT", "development")
        }
    )
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
