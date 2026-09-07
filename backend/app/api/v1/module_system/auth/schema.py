from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schema import JWTOutSchema


class CaptchaOutSchema(BaseModel):
    """验证码响应模型"""

    model_config = ConfigDict(from_attributes=True)

    enable: bool = Field(default=True, description="是否启用验证码")
    key: str = Field(..., min_length=1, description="验证码唯一标识")
    img_base: str = Field(..., min_length=1, description="Base64编码的验证码图片")


class AutoLoginUserSchema(BaseModel):
    """免登录用户信息模型"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    name: str = Field(..., description="用户姓名")
    avatar: str | None = Field(default=None, description="头像")


class AutoLoginTokenSchema(BaseModel):
    """免登录Token响应模型"""

    model_config = ConfigDict(from_attributes=True)

    token: str = Field(..., description="免登录Token")
    user: AutoLoginUserSchema = Field(..., description="用户信息")


class LoginSchema(JWTOutSchema):
    """登录响应。"""

    user_info: dict = Field(default_factory=dict, description="用户信息")


class CloudIdentityLoginSchema(BaseModel):
    """客户知识库员工使用云端账号登录。"""

    identity: str = Field(..., min_length=1, max_length=200, description="云端员工账号或邮箱")
    password: str = Field(..., min_length=1, max_length=128, description="云端员工密码")


class CloudIdentityExchangeSchema(BaseModel):
    """客户知识库交换云面板签发的员工身份凭证。"""

    identity_token: str = Field(..., min_length=20, max_length=256, description="云面板员工身份凭证")
    refresh_token: str = Field(..., min_length=20, max_length=256, description="云面板员工身份刷新凭证")


class CloudControlPlaneBindSchema(BaseModel):
    """首次绑定使用本地管理员，换绑使用目标实例的企业超管。"""

    admin_username: str = Field(..., min_length=1, max_length=32, description="首次绑定的本地管理员账号；换绑时为企业超管账号")
    admin_password: str = Field(..., min_length=1, max_length=128, description="首次绑定的本地管理员密码；换绑时为企业超管密码")
    instance_id: int = Field(..., gt=0, description="客户知识库实例ID")
    service_credential: str = Field(..., min_length=1, max_length=256, description="云面板服务凭证")


class OAuthTicketSchema(BaseModel):
    """One-time OAuth browser callback ticket."""

    ticket: str = Field(..., min_length=20, max_length=256)

