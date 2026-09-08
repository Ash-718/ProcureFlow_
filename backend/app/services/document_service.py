"""
Document upload, listing and automated verification.

Port of Java's `DocumentService`.

**Access control lives here and nowhere else.** `documents.owner_id` is
polymorphic — it points at either `startups.id` or `proposals.id` — so it
carries no foreign key and the database cannot enforce anything. Every rule
below is the only thing standing between one startup and another's compliance
paperwork.

Upload (`assert_can_manage`)
    ADMIN, or the startup that owns the profile, or the startup that owns the
    proposal. Nobody else, including the government department running the
    challenge.

Read (`assert_can_view`)
    ADMIN and EXPERT may read any document (an expert reviews supporting
    material). A startup reads its own. A government user reads documents for a
    proposal on their *own* department's challenge, and a startup's documents
    only where that startup has actually proposed to their department.

**Verification** is a small set of deterministic rules — file type, emptiness,
size — not an ML model. The Java comment is explicit that this was a considered
choice: a rule that states plainly *why* a document was flagged is more
appropriate for a compliance workflow than an opaque classifier, and it is
honestly labelled as automated checks rather than "AI".
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import (
    Document,
    DocumentOwnerType,
    DocumentType,
    NotificationType,
    RoleName,
    User,
    VerificationStatus,
)
from app.repositories import (
    DocumentRepository,
    ProposalRepository,
    StartupRepository,
    UserRepository,
)
from app.schemas.proposal import DocumentResponse
from app.services.audit_service import Action, AuditService
from app.services.file_storage import FileStorageService
from app.services.notification_service import NotificationService

ALLOWED_EXTENSIONS = frozenset({"pdf", "doc", "docx", "jpg", "jpeg", "png"})
MAX_REASONABLE_SIZE_BYTES = 15 * 1024 * 1024


class DocumentService:
    def __init__(self, db: Session, storage: FileStorageService | None = None):
        self.db = db
        self.documents = DocumentRepository(db)
        self.startups = StartupRepository(db)
        self.proposals = ProposalRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)
        self.storage = storage or FileStorageService()

    # --------------------------------------------------------------- write

    def upload(self, actor: User, owner_type: DocumentOwnerType, owner_id: uuid.UUID,
               document_type: DocumentType, stream: BinaryIO,
               original_filename: str | None) -> DocumentResponse:
        self._assert_can_manage(actor, owner_type, owner_id)

        # Storage rejects an empty upload with a 400 before any row is written,
        # so a failed upload leaves neither a file nor a record.
        stored_name = self.storage.store(stream, original_filename)
        size = self.storage.resolve(stored_name).stat().st_size

        document = Document(
            owner_type=owner_type,
            owner_id=owner_id,
            document_type=document_type,
            file_path=stored_name,
            original_filename=original_filename,
        )
        self._apply_verification_rules(document, original_filename, size)

        try:
            self.documents.add(document)
            self.audit.log(actor, Action.UPLOAD, "Document", document.id,
                           {"verificationStatus": document.verification_status.value})
            if document.verification_status is VerificationStatus.FLAGGED:
                self.notifications.notify(
                    actor, NotificationType.DOCUMENT_FLAGGED,
                    f'Your uploaded document "{original_filename}" was flagged: '
                    f"{document.verification_notes}",
                )
            self.db.commit()
        except Exception:
            # Never leave an orphaned file behind if the row could not be saved.
            self.db.rollback()
            self.storage.delete(stored_name)
            raise

        return DocumentResponse.model_validate(document)

    # ---------------------------------------------------------------- read

    def list_for_owner(self, actor: User, owner_type: DocumentOwnerType,
                       owner_id: uuid.UUID) -> list[DocumentResponse]:
        self._assert_can_view(actor, owner_type, owner_id)
        return [DocumentResponse.model_validate(d)
                for d in self.documents.list_for_owner(owner_type, owner_id)]

    # -------------------------------------------------------- verification

    @staticmethod
    def _apply_verification_rules(document: Document, filename: str | None,
                                  size: int) -> None:
        """
        Deterministic checks, in the same order as the Java implementation.

        The empty-file branch is unreachable through the HTTP path — storage
        rejects a zero-byte upload with a 400 first — but it is kept so the
        rules read completely and so a direct caller is covered.
        """
        name = (filename or "").lower()
        extension = name.rsplit(".", 1)[-1] if "." in name else ""

        if size == 0:
            _flag(document, "The uploaded file is empty.")
        elif size > MAX_REASONABLE_SIZE_BYTES:
            _flag(document,
                  "File exceeds the expected size for this document type (>15MB) "
                  "— please confirm it is correct.")
        elif not extension or extension not in ALLOWED_EXTENSIONS:
            _flag(document,
                  f"Unsupported file type '{extension}'. Expected one of: "
                  f"{ALLOWED_EXTENSIONS}")
        else:
            document.verification_status = VerificationStatus.VERIFIED
            document.verification_notes = (
                "Passed automated checks: valid file type, non-empty, "
                "within size limits.")

    # ------------------------------------------------------ access control

    def _assert_can_manage(self, actor: User, owner_type: DocumentOwnerType,
                           owner_id: uuid.UUID) -> None:
        """Who may *upload* against this owner."""
        if actor.role.name is RoleName.ADMIN:
            return

        startup = self.startups.find_by_user(actor.id)
        if owner_type is DocumentOwnerType.STARTUP:
            if startup is not None and startup.id == owner_id:
                return
        else:
            proposal = self.proposals.get(owner_id)
            if proposal is not None and startup is not None \
                    and proposal.startup_id == startup.id:
                return

        raise ApiException.forbidden("You cannot upload documents for this resource")

    def _assert_can_view(self, actor: User, owner_type: DocumentOwnerType,
                         owner_id: uuid.UUID) -> None:
        """Who may *read* documents for this owner."""
        role = actor.role.name
        if role in (RoleName.ADMIN, RoleName.EXPERT):
            return  # any expert may review supporting documents

        startup = self.startups.find_by_user(actor.id)

        if owner_type is DocumentOwnerType.STARTUP:
            if startup is not None and startup.id == owner_id:
                return
            if role is RoleName.GOVERNMENT and \
                    self._startup_has_proposal_to_own_department(actor, owner_id):
                return
        else:
            proposal = self.proposals.get(owner_id)
            if proposal is not None:
                if startup is not None and proposal.startup_id == startup.id:
                    return
                if role is RoleName.GOVERNMENT:
                    department = self.users.find_department_by_user(actor.id)
                    if department is not None and \
                            department.id == proposal.challenge.department_id:
                        return

        raise ApiException.forbidden("You do not have access to these documents")

    def _startup_has_proposal_to_own_department(self, actor: User,
                                                startup_id: uuid.UUID) -> bool:
        """
        A department may read a startup's documents only once that startup has
        proposed to it — not merely because the startup exists.
        """
        department = self.users.find_department_by_user(actor.id)
        if department is None:
            return False
        return any(p.challenge.department_id == department.id
                   for p in self.proposals.list_by_startup(startup_id))


def _flag(document: Document, note: str) -> None:
    document.verification_status = VerificationStatus.FLAGGED
    document.verification_notes = note
