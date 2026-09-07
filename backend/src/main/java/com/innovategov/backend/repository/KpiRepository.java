package com.innovategov.backend.repository;

import com.innovategov.backend.entity.Kpi;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface KpiRepository extends JpaRepository<Kpi, UUID> {
    List<Kpi> findByPilotId(UUID pilotId);
}
