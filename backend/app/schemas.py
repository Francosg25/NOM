from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicationInput(Input):
    review_status: Literal["pendiente", "en_revision", "resuelta"] | None = None
    kind: (
        Literal[
            "proyecto",
            "norma_definitiva",
            "modificacion",
            "cancelacion",
            "acuerdo",
            "aviso",
            "clasificacion_pendiente",
        ]
        | None
    ) = None
    effective_on: date | None = None
    effective_verified: bool | None = None
    effective_evidence: str | None = Field(None, max_length=20000)


class ProductSearchInput(Input):
    mode: Literal["fraccion", "descripcion"]
    value: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_value(self):
        if not self.value.strip():
            raise ValueError("El valor de búsqueda no puede estar vacío")
        return self
