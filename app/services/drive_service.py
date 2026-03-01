"""Google Drive service for PDF uploads."""
import logging
import os
import re
import time
import unicodedata
from io import BytesIO
from typing import Dict, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from app.config import settings
from app.models import parse_iso_datetime

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
ALLOWED_ROOT_FOLDER_ID = "1n8njw20WyC-uylqiMOZULj5tnDZjRjjA"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class DriveApiError(Exception):
    """Base class for Drive API errors."""


class DriveFileNotFoundError(DriveApiError):
    """Raised when an expected file/folder does not exist."""


class DriveInvalidFolderError(DriveApiError):
    """Raised when the provided folder ID is not a folder."""


class DrivePermissionError(DriveApiError):
    """Raised when credentials do not have access to Drive resources."""


class DriveUploadError(DriveApiError):
    """Raised when upload operation fails."""


class DriveService:
    """Service for Google Drive interactions."""

    def __init__(self):
        self.client_secret_file = settings.GOOGLE_CLIENT_SECRET_FILE
        self.token_file = settings.GOOGLE_TOKEN_FILE
        self.service = None

    def get_service(self):
        """Return an authenticated Drive API client."""
        if self.service is not None:
            return self.service

        creds = None

        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.token_file, "w", encoding="utf-8") as token:
                token.write(creds.to_json())

        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self.service

    def _execute_with_retry(self, request, max_retries: int = 5):
        """Execute request with backoff on transient errors."""
        for attempt in range(max_retries):
            try:
                return request.execute()
            except HttpError as error:
                status = getattr(error.resp, "status", None)
                if status in [429, 500, 503, 504] and attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Drive transient error status=%s. Retry in %ss (%s/%s)",
                        status,
                        wait_time,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(wait_time)
                    continue
                raise

    def _handle_http_error(self, error: HttpError, not_found_message: str):
        """Map HttpError to domain exceptions."""
        status = getattr(error.resp, "status", None)

        if status == 404:
            raise DriveFileNotFoundError(not_found_message) from error
        if status in [401, 403]:
            raise DrivePermissionError("Sin permisos para acceder al recurso de Drive") from error

        raise DriveApiError(f"Error de Drive API (status={status})") from error

    def get_file_metadata(self, file_id: str) -> Dict:
        """Return metadata for a Drive resource."""
        service = self.get_service()
        try:
            return self._execute_with_retry(
                service.files().get(
                    fileId=file_id,
                    fields=(
                        "id,name,mimeType,parents,size,webViewLink,webContentLink,"
                        "createdTime,driveId"
                    ),
                    supportsAllDrives=True,
                )
            )
        except HttpError as error:
            self._handle_http_error(error, f"No existe el recurso en Drive: {file_id}")

    def is_descendant_of_root(self, folder_id: str, root_id: str) -> bool:
        """Check whether folder_id is within the allowed root folder tree."""
        metadata = self.get_file_metadata(folder_id)

        if metadata.get("mimeType") != FOLDER_MIME_TYPE:
            raise DriveInvalidFolderError("folder_id debe corresponder a una carpeta")

        to_visit: List[str] = [folder_id]
        visited = set()

        while to_visit:
            current_id = to_visit.pop()
            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id == root_id:
                return True

            current_meta = metadata if current_id == folder_id else self.get_file_metadata(current_id)
            parents = current_meta.get("parents") or []
            to_visit.extend(parents)

        return False

    def build_final_filename(self, fecha_inicio: str, nombre_documento: str) -> str:
        """Build final filename in format YYYYMMDD_documento.pdf."""
        dt = parse_iso_datetime(fecha_inicio)
        date_prefix = dt.strftime("%Y%m%d")

        clean_name = nombre_documento.strip()
        if clean_name.lower().endswith(".pdf"):
            clean_name = clean_name[:-4]

        # Remove accents and normalize to a slug-like safe format.
        clean_name = unicodedata.normalize("NFKD", clean_name)
        clean_name = clean_name.encode("ascii", "ignore").decode("ascii")
        clean_name = clean_name.lower()
        clean_name = re.sub(r"\s+", "_", clean_name)
        clean_name = re.sub(r"[^a-z0-9_-]", "", clean_name)
        clean_name = re.sub(r"_+", "_", clean_name)
        clean_name = clean_name.strip("_")

        if not clean_name:
            clean_name = "documento"

        return f"{date_prefix}_{clean_name}.pdf"

    def _file_exists_in_folder(self, folder_id: str, file_name: str) -> bool:
        """Return True if a non-trashed file with file_name exists in folder_id."""
        service = self.get_service()
        escaped = file_name.replace("'", "\\'")
        query = f"name = '{escaped}' and '{folder_id}' in parents and trashed = false"

        try:
            response = self._execute_with_retry(
                service.files().list(
                    q=query,
                    spaces="drive",
                    fields="files(id)",
                    pageSize=1,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
            )
            return bool(response.get("files"))
        except HttpError as error:
            self._handle_http_error(error, f"No se pudo verificar la carpeta: {folder_id}")

    def resolve_non_colliding_name(self, folder_id: str, candidate_name: str) -> str:
        """Resolve a unique file name by appending numeric suffix if needed."""
        if not self._file_exists_in_folder(folder_id, candidate_name):
            return candidate_name

        base_name = candidate_name[:-4] if candidate_name.lower().endswith(".pdf") else candidate_name
        extension = ".pdf"

        for index in range(1, 1000):
            variant = f"{base_name}_{index}{extension}"
            if not self._file_exists_in_folder(folder_id, variant):
                return variant

        raise DriveUploadError("No fue posible resolver un nombre unico de archivo")

    def upload_pdf_bytes(self, folder_id: str, final_name: str, file_bytes: bytes) -> Dict:
        """Upload PDF bytes to Drive and return uploaded metadata."""
        service = self.get_service()
        media = MediaIoBaseUpload(
            fd=BytesIO(file_bytes),
            mimetype="application/pdf",
            resumable=False,
        )
        metadata = {"name": final_name, "parents": [folder_id]}

        try:
            return self._execute_with_retry(
                service.files().create(
                    body=metadata,
                    media_body=media,
                    fields="id,name,size,webViewLink,webContentLink,createdTime,parents",
                    supportsAllDrives=True,
                )
            )
        except HttpError as error:
            status = getattr(error.resp, "status", None)
            if status == 404:
                raise DriveFileNotFoundError(f"No existe la carpeta de destino: {folder_id}") from error
            if status in [401, 403]:
                raise DrivePermissionError("Sin permisos para subir archivo en la carpeta destino") from error
            raise DriveUploadError(f"Fallo la subida a Drive (status={status})") from error


drive_service = DriveService()
