"""CORS configuration settings."""

from pydantic import BaseModel, Field, field_validator, model_validator


class CORSSettings(BaseModel):
    """CORS-specific configuration settings.

    Security Note: When origins contains "*" (wildcard), credentials is automatically
    set to False to prevent CSRF vulnerabilities. Browsers block credentials with
    wildcard origins anyway, but we enforce this at the config level for safety.
    """

    origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allowed origins",
    )

    credentials: bool = Field(
        default=False,
        description="CORS allow credentials (automatically disabled for wildcard origins)",
    )

    methods: list[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allowed methods",
    )

    headers: list[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allowed headers",
    )

    origin_regex: str | None = Field(
        default=None,
        description="CORS origin regex pattern",
    )

    expose_headers: list[str] = Field(
        default_factory=list,
        description="CORS exposed headers",
    )

    max_age: int = Field(
        default=600,
        description="CORS preflight max age in seconds",
        ge=0,
    )

    @field_validator("origins", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Split comma-separated string
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("methods", mode="before")
    @classmethod
    def validate_cors_methods(cls, v: str | list[str]) -> list[str]:
        """Parse CORS methods from string or list."""
        if isinstance(v, str):
            # Split comma-separated string
            return [method.strip().upper() for method in v.split(",") if method.strip()]
        return [method.upper() for method in v]

    @field_validator("headers", mode="before")
    @classmethod
    def validate_cors_headers(cls, v: str | list[str]) -> list[str]:
        """Parse CORS headers from string or list."""
        if isinstance(v, str):
            # Split comma-separated string
            return [header.strip() for header in v.split(",") if header.strip()]
        return v

    @field_validator("expose_headers", mode="before")
    @classmethod
    def validate_cors_expose_headers(cls, v: str | list[str]) -> list[str]:
        """Parse CORS expose headers from string or list."""
        if isinstance(v, str):
            # Split comma-separated string
            return [header.strip() for header in v.split(",") if header.strip()]
        return v

    @model_validator(mode="after")
    def validate_wildcard_credentials(self) -> "CORSSettings":
        """Ensure credentials are disabled when using wildcard origins.

        This is a security measure to prevent CSRF attacks. Browsers already
        block credentials with wildcard origins, but we enforce it at config
        level to make the security posture explicit.
        """
        if "*" in self.origins and self.credentials:
            # Automatically disable credentials for wildcard origins
            object.__setattr__(self, "credentials", False)
        return self
