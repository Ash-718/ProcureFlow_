package com.innovategov.backend.service;

import com.innovategov.backend.exception.ApiException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

@Service
public class FileStorageService {

    private final Path root;

    public FileStorageService(@Value("${app.file-storage.path}") String storagePath) {
        this.root = Path.of(storagePath).toAbsolutePath().normalize();
        try {
            Files.createDirectories(root);
        } catch (IOException e) {
            throw new IllegalStateException("Could not create file storage directory: " + root, e);
        }
    }

    /** Stores the file under a random-UUID-prefixed name and returns the relative path to persist in the DB. */
    public String store(MultipartFile file) {
        if (file.isEmpty()) {
            throw ApiException.badRequest("Uploaded file is empty");
        }
        String original = StringUtils.cleanPath(file.getOriginalFilename() == null ? "file" : file.getOriginalFilename());
        String safeName = UUID.randomUUID() + "_" + original.replaceAll("[^a-zA-Z0-9._-]", "_");
        try {
            Files.copy(file.getInputStream(), root.resolve(safeName));
        } catch (IOException e) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "Failed to store uploaded file");
        }
        return safeName;
    }

    public Path resolve(String relativePath) {
        return root.resolve(relativePath).normalize();
    }
}
