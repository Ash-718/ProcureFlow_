package com.innovategov.backend.repository;

import com.innovategov.backend.entity.Document;
import com.innovategov.backend.entity.enums.DocumentOwnerType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface DocumentRepository extends JpaRepository<Document, UUID> {
    List<Document> findByOwnerTypeAndOwnerId(DocumentOwnerType ownerType, UUID ownerId);
}
