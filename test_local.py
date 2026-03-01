"""Local tests for API Documentos Drive."""
import base64

from fastapi.testclient import TestClient

from app.main import app
from app.routers import documentos as documentos_router
from app.services.drive_service import (
    DriveFileNotFoundError,
    DriveInvalidFolderError,
    DriveUploadError,
    drive_service,
)

client = TestClient(app)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"


def test_root_endpoint() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["nombre"] == "API Documentos Drive"
    assert body["endpoints"]["subir_documento"] == "/documentos/subir"


def test_subir_documento_ok(monkeypatch) -> None:
    monkeypatch.setattr(drive_service, "is_descendant_of_root", lambda folder_id, root_id: True)
    monkeypatch.setattr(
        drive_service,
        "build_final_filename",
        lambda fecha_inicio, nombre_documento: "20260301_documento.pdf",
    )
    monkeypatch.setattr(
        drive_service,
        "resolve_non_colliding_name",
        lambda folder_id, candidate_name: "20260301_documento_1.pdf",
    )
    monkeypatch.setattr(
        drive_service,
        "upload_pdf_bytes",
        lambda folder_id, final_name, file_bytes: {
            "id": "file-123",
            "name": final_name,
            "size": str(len(file_bytes)),
            "webViewLink": "https://drive.google.com/file/d/file-123/view",
            "webContentLink": "https://drive.google.com/uc?id=file-123&export=download",
            "createdTime": "2026-03-01T12:00:00.000Z",
        },
    )

    payload = {
        "documento_base64": _b64(b"%PDF-1.4 fake"),
        "nombre_documento": "Contrato SST.pdf",
        "fecha_inicio": "2026-03-01",
        "folder_id": "folder-allowed",
    }

    response = client.post("/documentos/subir", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert body["file_id"] == "file-123"
    assert body["file_name"] == "20260301_documento_1.pdf"
    assert body["folder_id"] == "folder-allowed"
    assert body["size_bytes"] == len(b"%PDF-1.4 fake")


def test_subir_documento_base64_invalido() -> None:
    payload = {
        "documento_base64": "no-es-base64",
        "nombre_documento": "Contrato SST.pdf",
        "fecha_inicio": "2026-03-01",
        "folder_id": "folder-allowed",
    }

    response = client.post("/documentos/subir", json=payload)
    assert response.status_code == 422


def test_subir_documento_nombre_no_pdf() -> None:
    payload = {
        "documento_base64": _b64(b"hola"),
        "nombre_documento": "Contrato SST.txt",
        "fecha_inicio": "2026-03-01",
        "folder_id": "folder-allowed",
    }

    response = client.post("/documentos/subir", json=payload)
    assert response.status_code == 422


def test_subir_documento_folder_no_encontrado(monkeypatch) -> None:
    def _raise_not_found(folder_id: str, root_id: str) -> bool:
        raise DriveFileNotFoundError("No existe el recurso en Drive: folder-x")

    monkeypatch.setattr(drive_service, "is_descendant_of_root", _raise_not_found)

    payload = {
        "documento_base64": _b64(b"%PDF-1.4 fake"),
        "nombre_documento": "Contrato SST.pdf",
        "fecha_inicio": "2026-03-01",
        "folder_id": "folder-x",
    }

    response = client.post("/documentos/subir", json=payload)
    assert response.status_code == 404


def test_subir_documento_folder_fuera_de_root(monkeypatch) -> None:
    monkeypatch.setattr(drive_service, "is_descendant_of_root", lambda folder_id, root_id: False)

    payload = {
        "documento_base64": _b64(b"%PDF-1.4 fake"),
        "nombre_documento": "Contrato SST.pdf",
        "fecha_inicio": "2026-03-01",
        "folder_id": "folder-outside",
    }

    response = client.post("/documentos/subir", json=payload)
    assert response.status_code == 403


def test_subir_documento_folder_no_es_carpeta(monkeypatch) -> None:
    def _raise_invalid(folder_id: str, root_id: str) -> bool:
        raise DriveInvalidFolderError("folder_id debe corresponder a una carpeta")

    monkeypatch.setattr(drive_service, "is_descendant_of_root", _raise_invalid)

    payload = {
        "documento_base64": _b64(b"%PDF-1.4 fake"),
        "nombre_documento": "Contrato SST.pdf",
        "fecha_inicio": "2026-03-01",
        "folder_id": "not-folder",
    }

    response = client.post("/documentos/subir", json=payload)
    assert response.status_code == 422


def test_subir_documento_tamano_supera_limite(monkeypatch) -> None:
    monkeypatch.setattr(documentos_router, "MAX_FILE_SIZE_BYTES", 10)

    payload = {
        "documento_base64": _b64(b"12345678901"),
        "nombre_documento": "Contrato SST.pdf",
        "fecha_inicio": "2026-03-01",
        "folder_id": "folder-allowed",
    }

    response = client.post("/documentos/subir", json=payload)
    assert response.status_code == 413


def test_subir_documento_upload_error(monkeypatch) -> None:
    monkeypatch.setattr(drive_service, "is_descendant_of_root", lambda folder_id, root_id: True)
    monkeypatch.setattr(
        drive_service,
        "build_final_filename",
        lambda fecha_inicio, nombre_documento: "20260301_documento.pdf",
    )
    monkeypatch.setattr(
        drive_service,
        "resolve_non_colliding_name",
        lambda folder_id, candidate_name: candidate_name,
    )

    def _raise_upload(folder_id: str, final_name: str, file_bytes: bytes):
        raise DriveUploadError("Fallo la subida")

    monkeypatch.setattr(drive_service, "upload_pdf_bytes", _raise_upload)

    payload = {
        "documento_base64": _b64(b"%PDF-1.4 fake"),
        "nombre_documento": "Contrato SST.pdf",
        "fecha_inicio": "2026-03-01",
        "folder_id": "folder-allowed",
    }

    response = client.post("/documentos/subir", json=payload)
    assert response.status_code == 502


def test_build_final_filename_from_date() -> None:
    file_name = drive_service.build_final_filename("2026-03-01", "Contrato SST.pdf")
    assert file_name == "20260301_contrato_sst.pdf"


def test_build_final_filename_from_datetime() -> None:
    file_name = drive_service.build_final_filename("2026-03-01T14:30:00-03:00", "Informe Final.PDF")
    assert file_name == "20260301_informe_final.pdf"


def test_resolve_non_colliding_name_adds_suffix(monkeypatch) -> None:
    calls = {"count": 0}

    def _exists(folder_id: str, file_name: str) -> bool:
        calls["count"] += 1
        return calls["count"] == 1

    monkeypatch.setattr(drive_service, "_file_exists_in_folder", _exists)

    final_name = drive_service.resolve_non_colliding_name("folder-allowed", "20260301_doc.pdf")
    assert final_name == "20260301_doc_1.pdf"
