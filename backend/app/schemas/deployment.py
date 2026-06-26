import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    scan_id: uuid.UUID
    container_id: str | None
    container_name: str | None
    image_tag: str | None
    status: str
    internal_port: int | None
    external_port: int | None
    public_url: str | None
    allowed_egress_urls: list | None
    env_vars_injected: dict | None
    started_at: datetime | None
    stopped_at: datetime | None
    created_at: datetime
    app_visibility: str | None = None
    app_public_flagged_at: datetime | None = None
    k8s_namespace: str | None = None
    k8s_deployment_name: str | None = None
