# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import os

from typing import Optional
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob.aio import BlobServiceClient
from fastapi import APIRouter, Response

from data_models import mime_type

logger = logging.getLogger(__name__)


def _get_repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def patient_data_routes(blob_service_client: Optional[BlobServiceClient] = None):
    router = APIRouter()
    repo_root = _get_repo_root()

    async def get_blob(blob_path: str, container_name: str) -> Response:
        ''' Get a file generated from an Azure AI Agent or local storage '''

        filename = os.path.basename(blob_path)
        logger.info(f"get_blob: {container_name}/{blob_path}")

        # Try Azure Blob Storage if client is provided
        if blob_service_client:
            try:
                container_client = blob_service_client.get_container_client(container_name)
                blob_client = container_client.get_blob_client(blob_path)

                blob = await blob_client.download_blob()
                blob_data = await blob.readall()

                headers = {
                    'Content-Type': mime_type(filename)
                }
                return Response(media_type=mime_type(filename), content=blob_data, headers=headers)
            except ResourceNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Error fetching from blob storage: {e}")

        # Fall back to local file system
        local_file_path = None
        if container_name == "chat-artifacts":
            local_file_path = os.path.join(repo_root, ".local_data", "chat-artifacts", blob_path.replace("/", os.sep))
        elif container_name == "patient-data":
            local_file_path = os.path.join(repo_root, "infra", "patient_data", blob_path.replace("/", os.sep))

        if local_file_path and os.path.exists(local_file_path):
            try:
                with open(local_file_path, "rb") as f:
                    blob_data = f.read()
                headers = {
                    'Content-Type': mime_type(filename)
                }
                return Response(media_type=mime_type(filename), content=blob_data, headers=headers)
            except Exception as e:
                logger.error(f"Error reading local file {local_file_path}: {e}")

        return Response(status_code=404, content=f"Blob not found: {blob_path}")

    @router.get("/chat_artifacts/{blob_path:path}")
    async def get_chat_artifact(blob_path: str):
        return await get_blob(blob_path, container_name="chat-artifacts")

    @router.get("/patient_data/{blob_path:path}")
    async def get_patient_data(blob_path: str):
        return await get_blob(blob_path, container_name="patient-data")

    return router


def get_chat_artifacts_url(blob_path: str) -> str:
    """Get the URL for a given blob path in chat artifacts."""
    hostname = os.getenv("BACKEND_APP_HOSTNAME", "localhost:8000")
    protocol = "http" if "localhost" in hostname or "127.0.0.1" in hostname else "https"
    return f"{protocol}://{hostname}/chat_artifacts/{blob_path}"


def get_patient_data_url(blob_path: str) -> str:
    """Get the URL for a given blob path."""
    hostname = os.getenv("BACKEND_APP_HOSTNAME", "localhost:8000")
    protocol = "http" if "localhost" in hostname or "127.0.0.1" in hostname else "https"
    return f"{protocol}://{hostname}/patient_data/{blob_path}"
