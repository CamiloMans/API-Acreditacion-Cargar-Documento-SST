"""Pydantic models for upload API."""
from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def parse_iso_datetime(raw_value: str) -> datetime:
    """Parse ISO date/datetime strings, including trailing Z timezone."""
    value = raw_value.strip()
    if not value:
        raise ValueError("fecha_inicio no puede ser vacia")

    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
            return datetime.combine(parsed_date, time.min)
        except ValueError as exc:
            raise ValueError("fecha_inicio debe ser una fecha ISO 8601 valida") from exc


class SubirDocumentoRequest(BaseModel):
    """Payload for uploading a PDF document to Google Drive."""

    documento_base64: str = Field(..., description="Documento PDF en base64")
    nombre_documento: str = Field(..., description="Nombre del documento PDF")
    fecha_inicio: str = Field(..., description="Fecha ISO para construir YYYYMMDD")
    folder_id: str = Field(..., description="ID de carpeta de destino en Drive")

    @field_validator("documento_base64")
    @classmethod
    def validate_documento_base64(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("documento_base64 no puede ser vacio")
        return trimmed

    @field_validator("nombre_documento")
    @classmethod
    def validate_nombre_documento(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("nombre_documento no puede ser vacio")
        if not trimmed.lower().endswith(".pdf"):
            raise ValueError("nombre_documento debe terminar en .pdf")
        return trimmed

    @field_validator("fecha_inicio")
    @classmethod
    def validate_fecha_inicio(cls, value: str) -> str:
        parse_iso_datetime(value)
        return value.strip()

    @field_validator("folder_id")
    @classmethod
    def validate_folder_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("folder_id no puede ser vacio")
        return trimmed


class SubirDocumentoResponse(BaseModel):
    """Response returned after uploading a PDF document."""

    ok: bool = True
    file_id: str
    file_name: str
    folder_id: str
    web_view_link: Optional[str] = None
    web_content_link: Optional[str] = None
    size_bytes: Optional[int] = None
    created_time: Optional[str] = None
