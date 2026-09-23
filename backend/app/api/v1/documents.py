"""
`/api/v1/documents` — upload and listing.

No role guard on either route. Access is decided entirely by ownership inside
`DocumentService`, because `documents.owner_id` is polymorphic and a role alone
cannot say whether *this* caller owns *that* resource.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import DocumentOwnerType, DocumentType
from app.schemas.proposal import DocumentResponse
from app.security.deps import CurrentUserEntity
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/{owner_type}/{owner_id}", response_model=DocumentResponse,
             status_code=status.HTTP_201_CREATED)
def upload_document(
    owner_type: DocumentOwnerType,
    owner_id: uuid.UUID,
    db: DbSession,
    actor: CurrentUserEntity,
    document_type: Annotated[DocumentType, Query(alias="documentType")],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    """
    Upload a supporting document. Returns **201**.

    `documentType` is a query parameter and `file` a multipart part, matching
    the Java controller and what `DocumentApi.upload` already sends.

    The response reports an automated verification outcome — VERIFIED, or
    FLAGGED with the reason. Those are deterministic file checks, not a content
    classifier, and are labelled as such.
    """
    return DocumentService(db).upload(
        actor, owner_type, owner_id, document_type, file.file, file.filename)


@router.get("/{owner_type}/{owner_id}", response_model=list[DocumentResponse])
def list_documents(owner_type: DocumentOwnerType, owner_id: uuid.UUID,
                   db: DbSession, actor: CurrentUserEntity) -> list[DocumentResponse]:
    """Documents for one owner, subject to the ownership rules in the service."""
    return DocumentService(db).list_for_owner(actor, owner_type, owner_id)
