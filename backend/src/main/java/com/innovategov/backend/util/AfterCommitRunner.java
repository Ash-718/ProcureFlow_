package com.innovategov.backend.util;

import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/**
 * Runs a callback only after the current transaction has committed — needed
 * whenever we fire a "best-effort" call to the AI service to recompute an
 * embedding for a row we just saved. Without this, the HTTP call reaches the AI
 * service (a separate process/connection) *before* our transaction commits, so
 * it queries the row under READ COMMITTED isolation and gets a 404 even though
 * the save "succeeded" from the caller's point of view.
 */
@Component
public class AfterCommitRunner {

    public void run(Runnable action) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    action.run();
                }
            });
        } else {
            action.run();
        }
    }
}
