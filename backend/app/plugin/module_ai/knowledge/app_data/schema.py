from typing import Any, Literal

from pydantic import BaseModel, Field

AppDataScope = Literal["TENANT", "USER"]
AppAccessPolicy = Literal["TENANT_SHARED", "OWNER_ONLY", "ACL"]
AppAclSubject = Literal["USER", "ROLE"]
AppAclPermission = Literal["READ", "WRITE", "DELETE", "SHARE"]


class AppResourceAclInput(BaseModel):
    subject_type: AppAclSubject
    subject_id: str = Field(..., min_length=1, max_length=128)
    permission: AppAclPermission


class AppResourceCreateSchema(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    data_scope: AppDataScope = "TENANT"
    access_policy: AppAccessPolicy = "TENANT_SHARED"
    schema_version: str = Field(default="1", min_length=1, max_length=32)
    external_ref: str | None = Field(default=None, max_length=2000)
    acl: list[AppResourceAclInput] = Field(default_factory=list, max_length=100)


class AppResourcePatchSchema(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class AppResourceOutSchema(BaseModel):
    id: str
    app_id: str
    resource_type: str
    data_scope: AppDataScope
    access_policy: AppAccessPolicy
    owner_space_id: str | None = None
    data: dict[str, Any]
    external_ref: str | None = None
    schema_version: str
    version: int
    created_by_subject_id: str
    updated_by_subject_id: str
