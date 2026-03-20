# ============================================================
# Pydantic schemas for Fazle API Gateway
# Strict input validation for all endpoints
# ============================================================
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import re

# ── Max length constants ────────────────────────────────────
MAX_MESSAGE_LEN = 10_000
MAX_SHORT_TEXT = 500
MAX_TITLE_LEN = 200
MAX_QUERY_LEN = 1_000
MAX_TRANSCRIPT_LEN = 50_000
MAX_USER_LEN = 100

# Safe text pattern — reject control chars except newlines/tabs
_SAFE_TEXT_RE = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f]*$")


def _validate_safe_text(v: str, field_name: str) -> str:
    if not _SAFE_TEXT_RE.match(v):
        raise ValueError(f"{field_name} contains invalid control characters")
    return v.strip()


# ── Chat ────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LEN, description="User message")
    conversation_id: Optional[str] = Field(None, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")
    user: str = Field("Azim", max_length=MAX_USER_LEN)

    @field_validator("message")
    @classmethod
    def message_safe(cls, v: str) -> str:
        return _validate_safe_text(v, "message")


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    memory_updates: list = Field(default_factory=list)


# ── Decision (Dograh integration) ──────────────────────────
class DecisionRequest(BaseModel):
    caller: str = Field(..., min_length=1, max_length=MAX_SHORT_TEXT, description="Caller identifier")
    intent: str = Field(..., min_length=1, max_length=MAX_SHORT_TEXT, description="Detected intent")
    conversation_context: str = Field("", max_length=MAX_TRANSCRIPT_LEN, description="Conversation transcript")
    metadata: dict = Field(default_factory=dict)

    @field_validator("caller", "intent")
    @classmethod
    def fields_safe(cls, v: str) -> str:
        return _validate_safe_text(v, "field")


class DecisionResponse(BaseModel):
    response: str
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    actions: list = Field(default_factory=list)
    memory_updates: list = Field(default_factory=list)


# ── Memory ──────────────────────────────────────────────────
VALID_MEMORY_TYPES = {"preference", "contact", "knowledge", "personal", "conversation"}


class MemoryStoreRequest(BaseModel):
    type: str = Field(..., description="Memory type")
    user: str = Field("Azim", max_length=MAX_USER_LEN)
    content: dict = Field(default_factory=dict)
    text: str = Field("", max_length=MAX_MESSAGE_LEN)

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        if v not in VALID_MEMORY_TYPES:
            raise ValueError(f"type must be one of: {', '.join(sorted(VALID_MEMORY_TYPES))}")
        return v


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LEN)
    memory_type: Optional[str] = None
    limit: int = Field(5, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def query_safe(cls, v: str) -> str:
        return _validate_safe_text(v, "query")

    @field_validator("memory_type")
    @classmethod
    def memory_type_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of: {', '.join(sorted(VALID_MEMORY_TYPES))}")
        return v


# ── Password Management ────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class AdminResetPasswordRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-fA-F0-9\-]+$")
    new_password: str = Field(..., min_length=8, max_length=128)


class RequestPasswordResetRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v


class ResetPasswordConfirmRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=128)


# ── Knowledge ingestion ────────────────────────────────────
class KnowledgeIngestRequest(BaseModel):
    text: str = Field("", max_length=MAX_TRANSCRIPT_LEN)
    source: str = Field("manual", max_length=MAX_SHORT_TEXT, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    title: str = Field("", max_length=MAX_TITLE_LEN)


# ── Tasks ───────────────────────────────────────────────────
VALID_TASK_TYPES = {"reminder", "scheduled", "recurring", "one-time"}


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    description: str = Field("", max_length=MAX_MESSAGE_LEN)
    scheduled_at: Optional[str] = Field(None, max_length=30, pattern=r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$")
    task_type: str = Field("reminder")
    payload: dict = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def title_safe(cls, v: str) -> str:
        return _validate_safe_text(v, "title")

    @field_validator("task_type")
    @classmethod
    def task_type_valid(cls, v: str) -> str:
        if v not in VALID_TASK_TYPES:
            raise ValueError(f"task_type must be one of: {', '.join(sorted(VALID_TASK_TYPES))}")
        return v


# ── Web Search ──────────────────────────────────────────────
class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LEN)
    max_results: int = Field(5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def query_safe(cls, v: str) -> str:
        return _validate_safe_text(v, "query")


# ── Training ───────────────────────────────────────────────
class TrainRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=MAX_TRANSCRIPT_LEN)
    user: str = Field("Azim", max_length=MAX_USER_LEN)
    session_type: str = Field("conversation", max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$")


# ── Authentication ─────────────────────────────────────────
VALID_RELATIONSHIPS = {"self", "wife", "daughter", "son", "parent", "sibling"}
VALID_ROLES = {"admin", "member"}


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    relationship_to_azim: str = Field("self", max_length=50)
    role: str = Field("member", max_length=20)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("relationship_to_azim")
    @classmethod
    def relationship_valid(cls, v: str) -> str:
        if v not in VALID_RELATIONSHIPS:
            raise ValueError(f"relationship must be one of: {', '.join(sorted(VALID_RELATIONSHIPS))}")
        return v

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def email_clean(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    relationship_to_azim: str
    role: str

    @model_validator(mode="before")
    @classmethod
    def stringify_id(cls, values):
        if isinstance(values, dict) and "id" in values:
            values["id"] = str(values["id"])
        return values


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    relationship_to_azim: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None

    @field_validator("relationship_to_azim")
    @classmethod
    def relationship_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_RELATIONSHIPS:
            raise ValueError(f"relationship must be one of: {', '.join(sorted(VALID_RELATIONSHIPS))}")
        return v

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v


# ── User Management ────────────────────────────────────────
class UserManagementCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("member", max_length=20)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("username")
    @classmethod
    def username_safe(cls, v: str) -> str:
        return _validate_safe_text(v, "username")

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v


class UserManagementUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, min_length=5, max_length=255)
    role: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().lower()
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
                raise ValueError("Invalid email format")
        return v

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v
