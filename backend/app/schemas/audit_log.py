"""Schema Pydantic cho Nhật ký kiểm toán (Audit Log)."""
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict


class AuditLogBase(BaseModel):
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    http_method: str
    endpoint: str
    status_code: int
    status: str = "SUCCESS"
    description: Optional[str] = None
    error_message: Optional[str] = None


class AuditLogResponse(AuditLogBase):
    id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_payload: Optional[Any] = None
    response_summary: Optional[str] = None
    execution_time_ms: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogPaginationResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    size: int
    pages: int
