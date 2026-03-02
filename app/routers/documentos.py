"""Router for PDF document uploads to Google Drive."""
import base64
import binascii
import logging

from fastapi import APIRouter, HTTPException, status

from app.models import SubirDocumentoRequest, SubirDocumentoResponse
from app.services.drive_service import (
    ALLOWED_ROOT_FOLDER_ID,
    DriveApiError,
    DriveFileNotFoundError,
    DriveInvalidFolderError,
    DrivePermissionError,
    DriveUploadError,
    drive_service,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024

router = APIRouter(prefix="/documentos", tags=["documentos"])


def _decode_base64_document(documento_base64: str) -> bytes:
    """Decode base64 content, supporting optional data URI prefix."""
    data = documento_base64.strip()
    if "," in data and data.lower().startswith("data:"):
        data = data.split(",", 1)[1]

    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="documento_base64 no es valido",
        ) from exc


@router.post("/subir", response_model=SubirDocumentoResponse)
async def subir_documento(request: SubirDocumentoRequest):
    """Upload a PDF document to Google Drive."""
    file_bytes = _decode_base64_document(request.documento_base64)

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El documento excede el tamano maximo de {MAX_FILE_SIZE_BYTES} bytes",
        )

    try:
        if not drive_service.is_descendant_of_root(request.folder_id, ALLOWED_ROOT_FOLDER_ID):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="folder_id fuera de la carpeta permitida",
            )

        candidate_name = drive_service.build_final_filename(
            request.fecha_inicio,
            request.nombre_documento,
        )
        final_name = drive_service.resolve_non_colliding_name(request.folder_id, candidate_name)

        uploaded = drive_service.upload_pdf_bytes(
            folder_id=request.folder_id,
            final_name=final_name,
            file_bytes=file_bytes,
        )

        return SubirDocumentoResponse(
            ok=True,
            file_id=uploaded["id"],
            file_name=uploaded["name"],
            folder_id=request.folder_id,
            web_view_link=uploaded.get("webViewLink"),
            web_content_link=uploaded.get("webContentLink"),
            size_bytes=int(uploaded["size"]) if uploaded.get("size") is not None else None,
            created_time=uploaded.get("createdTime"),
        )
    except DriveFileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DriveInvalidFolderError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DrivePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except DriveUploadError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except DriveApiError as exc:
        logger.exception("Drive API error while uploading document")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
