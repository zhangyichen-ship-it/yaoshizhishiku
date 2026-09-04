import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.base_params import BaseQueryParam
from app.core.base_schema import BaseSchema, UserBySchema


class KnowledgeBaseCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    is_enabled: bool = True


class KnowledgeBaseUpdateSchema(KnowledgeBaseCreateSchema):
    pass


class KnowledgeBaseQueryParam(BaseQueryParam):
    name: str | None = None
    is_enabled: bool | None = None


class KnowledgeBaseOutSchema(KnowledgeBaseCreateSchema, BaseSchema, UserBySchema):
    document_count: int = 0
    indexed_document_count: int = 0
    indexing_document_count: int = 0
    failed_document_count: int = 0


class KnowledgeDocumentQueryParam(BaseQueryParam):
    knowledge_base_id: int | None = None
    file_name: str | None = None
    parse_status: str | None = None
    index_status: str | None = None


class KnowledgeDocumentOutSchema(BaseSchema, UserBySchema):
    knowledge_base_id: int
    file_name: str
    file_path: str | None = None
    file_type: str
    file_size: int = 0
    parse_status: str
    index_status: str
    error_message: str | None = None
    chunk_count: int = 0


class RetrievalTestSchema(BaseModel):
    query: str = Field(min_length=1, max_length=8_000)
    knowledge_base_ids: list[int] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchSchema(BaseModel):
    """Search the employee's locally authorized knowledge bases."""

    query: str = Field(min_length=1, max_length=8_000)
    knowledge_base_ids: list[int] | None = Field(default=None, max_length=20)
    limit: int = Field(default=8, ge=1, le=8)


class KbMemberCreateSchema(BaseModel):
    """Create a cloud employee through the customer KB service boundary."""

    username: str = Field(..., min_length=2, max_length=32, description="云端员工账号")
    password: str = Field(..., min_length=6, max_length=128, description="初始密码，仅转发到云面板，不落本地库")
    name: str = Field(..., min_length=1, max_length=32, description="员工名称")
    email: EmailStr | None = Field(default=None, description="员工邮箱")
    status: int = Field(default=0, ge=0, le=1, description="云端账号状态")
    desktop_enabled: bool = Field(default=True, description="是否允许使用桌面端")
    knowledge_enabled: bool = Field(default=True, description="是否允许访问知识库")
    model_enabled: bool = Field(default=True, description="是否允许调用模型服务")

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", value):
            raise ValueError("员工账号需以字母开头，2-32位，仅允许小写字母、数字、_、-")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("员工名称不能为空")
        return value


class KbMemberUpdateSchema(BaseModel):
    """Update cloud employee profile and product grants."""

    name: str | None = Field(default=None, min_length=1, max_length=32, description="员工名称")
    email: EmailStr | None = Field(default=None, description="员工邮箱")
    status: int | None = Field(default=None, ge=0, le=1, description="云端账号状态")
    desktop_enabled: bool | None = Field(default=None, description="是否允许使用桌面端")
    knowledge_enabled: bool | None = Field(default=None, description="是否允许访问知识库")
    model_enabled: bool | None = Field(default=None, description="是否允许调用模型服务")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("员工名称不能为空")
        return value


class KbMemberOutSchema(BaseSchema):
    """Safe local projection of a cloud employee; never contains a password."""

    user_id: int = Field(..., description="云端用户ID")
    username: str
    name: str
    email: str | None = None
    status: int
    knowledge_enabled: bool
    local_role: str
    knowledge_base_ids: list[int] = Field(default_factory=list)


class KnowledgeBaseAccessUpdateSchema(BaseModel):
    """Replace one employee's local knowledge-base ACL set."""

    knowledge_base_ids: list[int] = Field(default_factory=list, max_length=100, description="允许访问的知识库ID")


class KnowledgeBaseAccessOutSchema(BaseModel):
    user_id: int
    knowledge_base_ids: list[int] = Field(default_factory=list)
