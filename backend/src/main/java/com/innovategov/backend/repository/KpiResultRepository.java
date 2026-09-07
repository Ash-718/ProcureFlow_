package com.innovategov.backend.repository;

import com.innovategov.backend.entity.KpiResult;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface KpiResultRepository extends JpaRepository<KpiResult, UUID> {
    List<KpiResult> findByKpiIdOrderByRecordedAtDesc(UUID kpiId);
}
