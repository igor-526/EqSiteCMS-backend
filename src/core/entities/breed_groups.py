from uuid import UUID

from pydantic import Field

from .base import Entity, SlugMixin, TimeStampMixin


class BreedGroup(Entity, TimeStampMixin, SlugMixin):
    equestrian_id: UUID = Field(...)
    name: str = Field(...)
    page_data: str = Field(default="<div></div>")


class BreedGroupIdentity(Entity):
    name: str
    slug: str
