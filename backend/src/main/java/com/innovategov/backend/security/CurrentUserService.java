package com.innovategov.backend.security;

import com.innovategov.backend.entity.User;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class CurrentUserService {

    private final UserRepository userRepository;

    public AuthenticatedUser principal() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        if (!(principal instanceof AuthenticatedUser authenticatedUser)) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "Not authenticated");
        }
        return authenticatedUser;
    }

    /** Loads the full, currently-managed User entity — use when a service needs to persist a reference to the actor. */
    public User currentUser() {
        return userRepository.findById(principal().getId())
                .orElseThrow(() -> ApiException.notFound("Authenticated user no longer exists"));
    }
}
