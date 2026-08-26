import asyncio
import base64
import datetime
import json
import logging
import os
import shutil
from dataclasses import dataclass
from io import BytesIO
from time import time
from typing import Optional

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobSasPermissions, UserDelegationKey, generate_blob_sas
from azure.storage.blob.aio import BlobServiceClient
from semantic_kernel.contents.chat_history import ChatHistory

from data_models.chat_artifact import ChatArtifact, ChatArtifactIdentifier
from data_models.chat_artifact_accessor import ChatArtifactAccessor
from data_models.chat_context import ChatContext
from data_models.chat_context_accessor import ChatContextAccessor
from data_models.clinical_note_accessor import ClinicalNoteAccessor
from data_models.fabric.fabric_clinical_note_accessor import FabricClinicalNoteAccessor
from data_models.fhir.fhir_clinical_note_accessor import FhirClinicalNoteAccessor
from data_models.image_accessor import ImageAccessor

logger = logging.getLogger(__name__)


def _get_repo_root() -> str:
    # src/data_models -> src -> repo_root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LocalBlobSasDelegate:
    """Local SAS delegate that returns URLs as-is for local development."""
    async def get_blob_sas_url(
        self,
        url: str,
        permission: Optional[BlobSasPermissions] = None,
        expiry_delta: Optional[datetime.timedelta] = None,
    ) -> str:
        return url


class LocalClinicalNoteAccessor:
    """Local disk accessor for clinical notes from infra/patient_data."""
    def __init__(self, base_dir: Optional[str] = None):
        repo_root = _get_repo_root()
        self.patient_data_dir = base_dir or os.path.join(repo_root, "infra", "patient_data")
        self.folder_name = "clinical_notes"

    async def get_patients(self) -> list[str]:
        if not os.path.exists(self.patient_data_dir):
            return ["patient_4"]
        patients = [
            d for d in os.listdir(self.patient_data_dir)
            if os.path.isdir(os.path.join(self.patient_data_dir, d))
        ]
        return patients or ["patient_4"]

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        notes_dir = os.path.join(self.patient_data_dir, patient_id, self.folder_name)
        if not os.path.exists(notes_dir):
            return []
        files = [f for f in os.listdir(notes_dir) if f.endswith(".json")]
        return [
            {
                "id": os.path.splitext(f)[0],
                "type": "clinical note",
            }
            for f in sorted(files)
        ]

    async def read(self, patient_id: str, note_id: str) -> str:
        file_path = os.path.join(self.patient_data_dir, patient_id, self.folder_name, f"{note_id}.json")
        if not os.path.exists(file_path):
            raise ResourceNotFoundError(f"Note not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    async def read_all(self, patient_id: str) -> list[str]:
        notes_dir = os.path.join(self.patient_data_dir, patient_id, self.folder_name)
        if not os.path.exists(notes_dir):
            return []
        files = [f for f in os.listdir(notes_dir) if f.endswith(".json")]
        notes = []
        for f in sorted(files):
            file_path = os.path.join(notes_dir, f)
            with open(file_path, "r", encoding="utf-8") as fp:
                notes.append(fp.read())
        return notes


class LocalImageAccessor:
    """Local disk accessor for patient images from infra/patient_data."""
    def __init__(self, base_dir: Optional[str] = None):
        repo_root = _get_repo_root()
        self.patient_data_dir = base_dir or os.path.join(repo_root, "infra", "patient_data")
        self.folder_name = "images"

    def get_url(self, patient_id: str, filename: str) -> str:
        hostname = os.getenv("BACKEND_APP_HOSTNAME", "localhost:8000")
        protocol = "http" if "localhost" in hostname or "127.0.0.1" in hostname else "https"
        return f"{protocol}://{hostname}/patient_data/{patient_id}/{self.folder_name}/{filename}"

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        meta_path = os.path.join(self.patient_data_dir, patient_id, self.folder_name, "metadata.json")
        if not os.path.exists(meta_path):
            return []
        with open(meta_path, "r", encoding="utf-8") as f:
            metadatas = json.load(f)
        for metadata in metadatas:
            filename = metadata.get("filename", "")
            metadata["url"] = self.get_url(patient_id, filename)
        return metadatas

    async def read(self, patient_id: str, filename: str) -> BytesIO:
        file_path = os.path.join(self.patient_data_dir, patient_id, self.folder_name, filename)
        if not os.path.exists(file_path):
            raise ResourceNotFoundError(f"Image not found: {file_path}")
        with open(file_path, "rb") as f:
            return BytesIO(f.read())


class LocalChatContextAccessor:
    """Local disk accessor for chat context sessions."""
    def __init__(self, base_dir: Optional[str] = None):
        repo_root = _get_repo_root()
        self.sessions_dir = base_dir or os.path.join(repo_root, ".local_data", "chat-sessions")
        self.container_client = None
        os.makedirs(self.sessions_dir, exist_ok=True)

    def _get_context_path(self, conversation_id: str) -> str:
        conv_dir = os.path.join(self.sessions_dir, conversation_id)
        os.makedirs(conv_dir, exist_ok=True)
        return os.path.join(conv_dir, "chat_context.json")

    async def read(self, conversation_id: str) -> ChatContext:
        context_path = self._get_context_path(conversation_id)
        if os.path.exists(context_path):
            try:
                with open(context_path, "r", encoding="utf-8") as f:
                    return ChatContextAccessor.deserialize(f.read())
            except Exception as e:
                logger.warning(f"Failed to read local chat context for {conversation_id}: {e}")
        return ChatContext(conversation_id)

    async def write(self, chat_ctx: ChatContext) -> None:
        context_path = self._get_context_path(chat_ctx.conversation_id)
        with open(context_path, "w", encoding="utf-8") as f:
            f.write(ChatContextAccessor.serialize(chat_ctx))

    async def archive(self, chat_ctx: ChatContext) -> None:
        conv_dir = os.path.join(self.sessions_dir, chat_ctx.conversation_id)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
        archive_path = os.path.join(conv_dir, f"{timestamp}_chat_context.json")
        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(ChatContextAccessor.serialize(chat_ctx))
        orig_path = os.path.join(conv_dir, "chat_context.json")
        if os.path.exists(orig_path):
            try:
                os.remove(orig_path)
            except Exception:
                pass


class LocalChatArtifactAccessor:
    """Local disk accessor for generated tumor board documents and artifacts."""
    def __init__(self, base_dir: Optional[str] = None):
        repo_root = _get_repo_root()
        self.artifacts_dir = base_dir or os.path.join(repo_root, ".local_data", "chat-artifacts")
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def get_blob_path(self, artifact_id: ChatArtifactIdentifier) -> str:
        base64_conv_id = base64.urlsafe_b64encode(artifact_id.conversation_id.encode("utf-8")).decode("utf-8")
        return f"{base64_conv_id}/{artifact_id.patient_id}/{artifact_id.filename}"

    def get_url(self, artifact_id: ChatArtifactIdentifier) -> str:
        hostname = os.getenv("BACKEND_APP_HOSTNAME", "localhost:8000")
        protocol = "http" if "localhost" in hostname or "127.0.0.1" in hostname else "https"
        blob_path = self.get_blob_path(artifact_id)
        return f"{protocol}://{hostname}/chat_artifacts/{blob_path}"

    async def read(self, artifact_id: ChatArtifactIdentifier) -> ChatArtifact:
        blob_path = self.get_blob_path(artifact_id)
        file_path = os.path.join(self.artifacts_dir, blob_path.replace("/", os.sep))
        if not os.path.exists(file_path):
            raise ResourceNotFoundError(f"Artifact not found: {file_path}")
        with open(file_path, "rb") as f:
            return ChatArtifact(artifact_id=artifact_id, data=f.read())

    async def write(self, artifact: ChatArtifact) -> None:
        blob_path = self.get_blob_path(artifact.artifact_id)
        file_path = os.path.join(self.artifacts_dir, blob_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(artifact.data)

    async def archive(self, conversation_id: str) -> None:
        pass


class UserDelegationKeyDelegate:
    def __init__(self, blob_service_client: BlobServiceClient):
        self.blob_service_client = blob_service_client
        self.user_delegation_key = None

    async def get_user_delegation_key(self) -> UserDelegationKey:
        if self.is_expired():
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            key_start_time = now_utc - datetime.timedelta(minutes=3)
            key_expiry_time = key_start_time + datetime.timedelta(hours=1)

            self.user_delegation_key = await self.blob_service_client.get_user_delegation_key(
                key_start_time=key_start_time,
                key_expiry_time=key_expiry_time
            )

        return self.user_delegation_key

    def is_expired(self) -> bool:
        if self.user_delegation_key is None:
            return True
        expiry_utc = datetime.datetime.strptime(self.user_delegation_key.signed_expiry, "%Y-%m-%dT%H:%M:%SZ")
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        return now_utc.timestamp() >= expiry_utc.timestamp()


class BlobSasDelegate(UserDelegationKeyDelegate):
    def __init__(self, blob_service_client: BlobServiceClient):
        super().__init__(blob_service_client)

    async def get_blob_sas_url(
        self,
        url: str,
        permission: BlobSasPermissions = BlobSasPermissions(read=True),
        expiry_delta: datetime.timedelta = datetime.timedelta(hours=0.5),
    ) -> str:
        if "?" in url:
            raise ValueError("URL already contains a query string.")

        container_name = url.split('/')[3]
        user_delegation_key = await self.get_user_delegation_key()
        account_name = self.blob_service_client.account_name
        blob_name = url[len(f"https://{account_name}.blob.core.windows.net/{container_name}/"):]
        expiry_time = datetime.datetime.now(datetime.timezone.utc) + expiry_delta

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            user_delegation_key=user_delegation_key,
            permission=permission,
            expiry=expiry_time
        )

        return f"{url}?{sas_token}"


@dataclass(frozen=True)
class DataAccess:
    """ Data access layer for the application. """
    blob_sas_delegate: any
    chat_artifact_accessor: any
    chat_context_accessor: any
    clinical_note_accessor: any
    image_accessor: any


def create_data_access(
    blob_service_client: Optional[BlobServiceClient] = None,
    credential: Optional[AsyncTokenCredential] = None
) -> DataAccess:
    """ Factory function to create a DataAccess object. """
    blob_endpoint = os.getenv("APP_BLOB_STORAGE_ENDPOINT")
    
    # If no Azure blob endpoint is configured or if set to local, use local storage fallback
    if not blob_endpoint or blob_endpoint.lower() in ("local", "none", "") or blob_service_client is None:
        logger.info("Initializing Local DataAccess layer (offline/filesystem mode).")
        return DataAccess(
            blob_sas_delegate=LocalBlobSasDelegate(),
            chat_artifact_accessor=LocalChatArtifactAccessor(),
            chat_context_accessor=LocalChatContextAccessor(),
            clinical_note_accessor=LocalClinicalNoteAccessor(),
            image_accessor=LocalImageAccessor(),
        )

    clinical_notes_source = os.getenv("CLINICAL_NOTES_SOURCE")
    if clinical_notes_source == "fhir" and credential:
        clinical_note_accessor = FhirClinicalNoteAccessor.from_credential(
            fhir_url=os.getenv("FHIR_SERVICE_ENDPOINT"),
            credential=credential,
        )
    elif clinical_notes_source == "fabric" and credential:
        clinical_note_accessor = FabricClinicalNoteAccessor.from_credential(
            fabric_user_data_function_endpoint=os.getenv("FABRIC_USER_DATA_FUNCTION_ENDPOINT"),
            credential=credential,
        )
    else:
        clinical_note_accessor = ClinicalNoteAccessor(blob_service_client)

    return DataAccess(
        blob_sas_delegate=BlobSasDelegate(blob_service_client),
        chat_artifact_accessor=ChatArtifactAccessor(blob_service_client),
        chat_context_accessor=ChatContextAccessor(blob_service_client),
        clinical_note_accessor=clinical_note_accessor,
        image_accessor=ImageAccessor(blob_service_client),
    )
