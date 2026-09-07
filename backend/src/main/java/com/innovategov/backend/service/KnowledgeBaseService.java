package com.innovategov.backend.service;

import com.innovategov.backend.dto.ai.AiKnowledgeBaseSimilarResponse;
import com.innovategov.backend.dto.knowledgebase.KnowledgeBaseEntryDto;
import com.innovategov.backend.entity.PilotKnowledgeBase;
import com.innovategov.backend.repository.PilotKnowledgeBaseRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Locale;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class KnowledgeBaseService {

    private final PilotKnowledgeBaseRepository knowledgeBaseRepository;
    private final AiServiceClient aiServiceClient;

    /** Small dataset by design (a few dozen closed pilots at most) — an in-memory filter is simpler and
     * just as correct as a dynamic query builder here; revisit with Specifications if this grows. */
    public List<KnowledgeBaseEntryDto> search(String domain, String technology, Boolean success, String q) {
        return knowledgeBaseRepository.findAll().stream()
                .filter(kb -> domain == null || kb.getDomain().equalsIgnoreCase(domain))
                .filter(kb -> technology == null || List.of(kb.getTechnologyTags()).stream()
                        .anyMatch(t -> t.toLowerCase(Locale.ROOT).contains(technology.toLowerCase(Locale.ROOT))))
                .filter(kb -> success == null || success.equals(kb.getSuccess()))
                .filter(kb -> !StringUtils.hasText(q) || matchesFreeText(kb, q))
                .map(KnowledgeBaseEntryDto::new)
                .toList();
    }

    private boolean matchesFreeText(PilotKnowledgeBase kb, String q) {
        return kb.getSearchableText().toLowerCase(Locale.ROOT).contains(q.toLowerCase(Locale.ROOT));
    }

    public AiKnowledgeBaseSimilarResponse findSimilarForDraft(
            String title, String problemStatement, String desiredTechnology, String domain, String outcomesExpected
    ) {
        return aiServiceClient.findSimilarPilots(title, problemStatement, desiredTechnology, domain, outcomesExpected);
    }
}
