-- =====================================================================
-- ReviewBot VKU SE Platform — MySQL Database Schema & Initial Records
-- Target Database: reviewbot
-- Compatible with: MySQL Workbench 8.0+ / MariaDB 10.4+
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `reviewbot` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `reviewbot`;

-- 1. Users Table (Authentication & Access Control)
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `email` VARCHAR(255) NOT NULL UNIQUE,
    `hashed_password` VARCHAR(255) NOT NULL,
    `full_name` VARCHAR(100) DEFAULT '',
    `avatar_url` VARCHAR(500) NULL,
    `is_active` TINYINT(1) DEFAULT 1,
    `is_superuser` TINYINT(1) DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_username` (`username`),
    INDEX `idx_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Repositories Table
CREATE TABLE IF NOT EXISTS `repositories` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `github_repo_id` BIGINT NOT NULL UNIQUE,
    `full_name` VARCHAR(255) NOT NULL UNIQUE,
    `installation_id` BIGINT NULL,
    `config_json` JSON NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_repos_full_name` (`full_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Pull Requests Table
CREATE TABLE IF NOT EXISTS `pull_requests` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `repo_id` INT NOT NULL,
    `number` INT NOT NULL,
    `title` VARCHAR(500) DEFAULT '',
    `author` VARCHAR(100) DEFAULT '',
    `head_sha` VARCHAR(40) NOT NULL,
    `base_sha` VARCHAR(40) DEFAULT '',
    `state` VARCHAR(20) DEFAULT 'open',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_prs_repo` FOREIGN KEY (`repo_id`) REFERENCES `repositories` (`id`) ON DELETE CASCADE,
    UNIQUE KEY `uq_repo_pr_number` (`repo_id`, `number`),
    INDEX `idx_prs_number` (`number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Reviews Table
CREATE TABLE IF NOT EXISTS `reviews` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `pr_id` INT NOT NULL,
    `head_sha` VARCHAR(40) NOT NULL,
    `status` VARCHAR(20) DEFAULT 'queued',
    `model` VARCHAR(100) DEFAULT '',
    `prompt_version` VARCHAR(50) DEFAULT 'v1',
    `input_tokens` INT DEFAULT 0,
    `output_tokens` INT DEFAULT 0,
    `cost_usd` FLOAT DEFAULT 0.0,
    `duration_ms` INT DEFAULT 0,
    `error` TEXT NULL,
    `github_review_id` BIGINT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_reviews_pr` FOREIGN KEY (`pr_id`) REFERENCES `pull_requests` (`id`) ON DELETE CASCADE,
    INDEX `idx_reviews_pr_sha` (`pr_id`, `head_sha`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Findings Table
CREATE TABLE IF NOT EXISTS `findings` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `review_id` INT NOT NULL,
    `file_path` VARCHAR(500) NOT NULL,
    `line_start` INT NOT NULL,
    `line_end` INT NULL,
    `severity` VARCHAR(20) NOT NULL,
    `category` VARCHAR(30) NOT NULL,
    `message` TEXT NOT NULL,
    `suggestion` TEXT NULL,
    `confidence` FLOAT DEFAULT 1.0,
    `rule_id` VARCHAR(100) DEFAULT '',
    `raw_finding` JSON NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_findings_review` FOREIGN KEY (`review_id`) REFERENCES `reviews` (`id`) ON DELETE CASCADE,
    INDEX `idx_findings_severity` (`severity`),
    INDEX `idx_findings_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. PR Summaries Table
CREATE TABLE IF NOT EXISTS `pr_summaries` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `pr_id` INT NOT NULL UNIQUE,
    `head_sha` VARCHAR(40) NOT NULL,
    `title_suggestion` VARCHAR(500) DEFAULT '',
    `summary` TEXT NOT NULL,
    `changed_components` JSON NULL,
    `risk_assessment` VARCHAR(50) DEFAULT 'low',
    `confidence_score` FLOAT DEFAULT 1.0,
    `github_comment_id` BIGINT NULL,
    `raw_summary` JSON NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_summaries_pr` FOREIGN KEY (`pr_id`) REFERENCES `pull_requests` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Developer Feedbacks Table
CREATE TABLE IF NOT EXISTS `feedbacks` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `finding_id` INT NOT NULL,
    `user_id` INT NULL,
    `reaction` VARCHAR(20) NOT NULL,
    `feedback_text` TEXT NULL,
    `source` VARCHAR(50) DEFAULT 'web',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_feedbacks_finding` FOREIGN KEY (`finding_id`) REFERENCES `findings` (`id`) ON DELETE CASCADE,
    INDEX `idx_feedbacks_finding` (`finding_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Webhook Deliveries Table
CREATE TABLE IF NOT EXISTS `webhook_deliveries` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `delivery_id` VARCHAR(100) NOT NULL UNIQUE,
    `event` VARCHAR(50) NOT NULL,
    `action` VARCHAR(50) NULL,
    `repo_name` VARCHAR(255) NULL,
    `status` VARCHAR(50) DEFAULT 'accepted',
    `status_code` INT DEFAULT 202,
    `duration_ms` INT DEFAULT 0,
    `payload_summary` TEXT NULL,
    `error` TEXT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_webhooks_delivery_id` (`delivery_id`),
    INDEX `idx_webhooks_repo_name` (`repo_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Rule Configurations Table
CREATE TABLE IF NOT EXISTS `rule_configs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `config_key` VARCHAR(100) NOT NULL UNIQUE,
    `language` VARCHAR(20) DEFAULT 'vi',
    `min_confidence` FLOAT DEFAULT 0.8,
    `post_summary` TINYINT(1) DEFAULT 1,
    `review_drafts` TINYINT(1) DEFAULT 0,
    `severity_threshold` VARCHAR(20) DEFAULT 'minor',
    `raw_yaml` TEXT NULL,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Seed Default Admin User if not exists
INSERT IGNORE INTO `users` (`id`, `username`, `email`, `hashed_password`, `full_name`, `is_active`, `is_superuser`, `created_at`)
VALUES (
    1,
    'vu_admin',
    'admin@vku.udn.vn',
    'pbkdf2_sha256$100000$8c3f4e2a1b9d7e5f3c1a8b6d4e2f0a8c$e5b8d9c2a1f4e7b0c3d6a9f2e5b8d1c4a7f0e3b6d9c2a5f8e1b4d7c0a3f6e9b2',
    'Vũ Nguyễn',
    1,
    1,
    NOW()
);
