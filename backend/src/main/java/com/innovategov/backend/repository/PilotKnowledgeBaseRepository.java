package com.innovategov.backend.repository;

import com.innovategov.backend.entity.PilotKnowledgeBase;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface PilotKnowledgeBaseRepository extends JpaRepository<PilotKnowledgeBase, UUID> {
}
