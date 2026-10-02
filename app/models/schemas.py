from typing import Optional

from pydantic import BaseModel, Field, field_validator


class HomePlannerInput(BaseModel):

    budget: float = Field(
        gt=0,
        description="Budget must be greater than zero.",
    )

    room_type: str = Field(
        min_length=1,
        max_length=100,
    )

    quantity: int = Field(
        default=1,
        ge=1,
        le=100,
    )

    style: str = Field(
        min_length=1,
        max_length=100,
    )

    needs: str = Field(
        default="",
        max_length=500,
    )

    @field_validator("room_type", "style")
    @classmethod
    def validate_required_text(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        return value

    @field_validator("needs")
    @classmethod
    def validate_needs(cls, value):
        return value.strip()


class PartyPlannerInput(BaseModel):

    budget: float = Field(
        gt=0,
        description="Budget must be greater than zero.",
    )

    guest_count: int = Field(
        ge=1,
        le=10000,
        description="Guest count must be between 1 and 10,000.",
    )

    event_type: str = Field(
        min_length=1,
        max_length=100,
    )

    venue: str = Field(
        default="",
        max_length=200,
    )

    preferences: str = Field(
        default="",
        max_length=500,
    )

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Event type cannot be empty.")

        return value

    @field_validator("venue", "preferences")
    @classmethod
    def clean_optional_text(cls, value):
        return value.strip()


class JewelryPlannerInput(BaseModel):

    budget: float = Field(
        gt=0,
        description="Budget must be greater than zero.",
    )

    occasion: str = Field(
        min_length=1,
        max_length=100,
    )

    style: str = Field(
        min_length=1,
        max_length=100,
    )

    outfit_notes: str = Field(
        default="",
        max_length=500,
    )

    image_path: Optional[str] = None

    @field_validator("occasion", "style")
    @classmethod
    def validate_required_text(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        return value

    @field_validator("outfit_notes")
    @classmethod
    def clean_outfit_notes(cls, value):
        return value.strip()