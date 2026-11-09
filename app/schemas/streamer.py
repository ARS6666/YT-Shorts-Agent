from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal


Platform = Literal["kick", "twitch", "youtube"]


class StreamerAccountCreate(BaseModel):
    platform: Platform
    username: str = Field(min_length=1, max_length=150)
    external_id: Optional[str] = None
    profile_url: Optional[str] = None


class StreamerAccountOut(StreamerAccountCreate):
    id: int
    streamer_id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class StreamerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    slug: str = Field(min_length=1, max_length=150)
    priority: int = Field(default=5, ge=1, le=10)
    notes: Optional[str] = None


class StreamerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    priority: Optional[int] = Field(default=None, ge=1, le=10)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class StreamerOut(BaseModel):
    id: int
    name: str
    slug: str
    priority: int
    is_active: bool
    notes: Optional[str] = None
    accounts: list[StreamerAccountOut] = []

    model_config = ConfigDict(from_attributes=True)