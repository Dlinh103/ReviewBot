-- ============================================================================
-- ReviewBot — MySQL Workbench Database Schema & Initial Data Dump
-- Target RDBMS: MySQL 8.0+ / 8.4 / 9.0 (MySQL Workbench Compatible)
-- Character Set: utf8mb4 / Collation: utf8mb4_unicode_ci
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `reviewbot` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `reviewbot`;

SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- Table structure for `repositories`
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `repositories`;
CREATE TABLE `repositories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `github_repo_id` bigint NOT NULL,
  `full_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `installation_id` bigint DEFAULT NULL,
  `config_json` json DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_repositories_full_name` (`full_name`),
  UNIQUE KEY `ix_repositories_github_repo_id` (`github_repo_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table `repositories`
INSERT INTO `repositories` (`id`, `github_repo_id`, `full_name`, `installation_id`, `config_json`, `created_at`) VALUES (1, 1001, 'vku-se/student-management-app', NULL, 'null', '2026-11-01 09:35:54');
INSERT INTO `repositories` (`id`, `github_repo_id`, `full_name`, `installation_id`, `config_json`, `created_at`) VALUES (2, 1002, 'vku-se/core-library', NULL, 'null', '2026-11-01 09:35:54');
INSERT INTO `repositories` (`id`, `github_repo_id`, `full_name`, `installation_id`, `config_json`, `created_at`) VALUES (3, 1003, 'vku-se/auth-service', NULL, 'null', '2026-11-01 09:35:54');

-- ------------------------------------------------------------
-- Table structure for `pull_requests`
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `pull_requests`;
CREATE TABLE `pull_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `repo_id` int NOT NULL,
  `number` int NOT NULL,
  `title` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `author` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `head_sha` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `base_sha` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `state` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_repo_pr_number` (`repo_id`,`number`),
  KEY `ix_pull_requests_number` (`number`),
  CONSTRAINT `pull_requests_ibfk_1` FOREIGN KEY (`repo_id`) REFERENCES `repositories` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table `pull_requests`
INSERT INTO `pull_requests` (`id`, `repo_id`, `number`, `title`, `author`, `head_sha`, `base_sha`, `state`, `created_at`, `updated_at`) VALUES (1, 1, 101, 'feat(auth): add database user authentication logic', 'vuminh', 'e8f9a12c4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f', '', 'open', '2026-11-01 09:35:54', '2026-11-01 09:35:54');
INSERT INTO `pull_requests` (`id`, `repo_id`, `number`, `title`, `author`, `head_sha`, `base_sha`, `state`, `created_at`, `updated_at`) VALUES (2, 2, 45, 'fix(payment): resolve potential zero division bug in coupon calculation', 'linhdan', 'a1b2c3d4e5f67890123456789abcdef012345678', '', 'open', '2026-11-01 09:35:54', '2026-11-01 09:35:54');
INSERT INTO `pull_requests` (`id`, `repo_id`, `number`, `title`, `author`, `head_sha`, `base_sha`, `state`, `created_at`, `updated_at`) VALUES (3, 3, 12, 'refactor(core): migrate legacy threadpool to async event loop', 'hoangnam', 'f7e6d5c4b3a2109876543210fedcba9876543210', '', 'open', '2026-11-01 09:35:54', '2026-11-01 09:35:54');

-- ------------------------------------------------------------
-- Table structure for `reviews`
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `reviews`;
CREATE TABLE `reviews` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pr_id` int NOT NULL,
  `head_sha` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(7) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `prompt_version` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `input_tokens` int NOT NULL,
  `output_tokens` int NOT NULL,
  `cost_usd` float NOT NULL,
  `duration_ms` int NOT NULL,
  `error` text COLLATE utf8mb4_unicode_ci,
  `github_review_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pr_head_sha` (`pr_id`,`head_sha`),
  KEY `ix_reviews_head_sha` (`head_sha`),
  CONSTRAINT `reviews_ibfk_1` FOREIGN KEY (`pr_id`) REFERENCES `pull_requests` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table `reviews`
INSERT INTO `reviews` (`id`, `pr_id`, `head_sha`, `status`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `cost_usd`, `duration_ms`, `error`, `github_review_id`, `created_at`) VALUES (1, 1, 'e8f9a12c4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f', 'DONE', 'claude-sonnet-4-6', 'v1', 850, 320, 0.0074, 620, NULL, 100101, '2026-11-01 09:35:54');
INSERT INTO `reviews` (`id`, `pr_id`, `head_sha`, `status`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `cost_usd`, `duration_ms`, `error`, `github_review_id`, `created_at`) VALUES (2, 2, 'a1b2c3d4e5f67890123456789abcdef012345678', 'DONE', 'claude-sonnet-4-6', 'v1', 620, 180, 0.0045, 450, NULL, 100102, '2026-11-01 09:35:54');
INSERT INTO `reviews` (`id`, `pr_id`, `head_sha`, `status`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `cost_usd`, `duration_ms`, `error`, `github_review_id`, `created_at`) VALUES (3, 3, 'f7e6d5c4b3a2109876543210fedcba9876543210', 'DONE', 'claude-sonnet-4-6', 'v1', 710, 210, 0.0052, 510, NULL, 100103, '2026-11-01 09:35:54');

-- ------------------------------------------------------------
-- Table structure for `findings`
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `findings`;
CREATE TABLE `findings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `review_id` int NOT NULL,
  `file_path` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `line_start` int NOT NULL,
  `line_end` int DEFAULT NULL,
  `severity` varchar(8) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(15) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `suggestion` text COLLATE utf8mb4_unicode_ci,
  `confidence` float NOT NULL,
  `evidence` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `posted` tinyint(1) NOT NULL,
  `github_comment_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `review_id` (`review_id`),
  CONSTRAINT `findings_ibfk_1` FOREIGN KEY (`review_id`) REFERENCES `reviews` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table `findings`
INSERT INTO `findings` (`id`, `review_id`, `file_path`, `line_start`, `line_end`, `severity`, `category`, `message`, `suggestion`, `confidence`, `evidence`, `posted`, `github_comment_id`, `created_at`) VALUES (1, 1, 'src/auth/database.py', 18, 19, 'CRITICAL', 'SECURITY', 'Phát hiện lỗ hổng SQL Injection nghiêm trọng do nối chuỗi trực tiếp tham số username và password vào câu lệnh SQL.', 'query = "SELECT * FROM users WHERE username = %s AND password = %s"
    cursor.execute(query, (username, password))', 0.98, 'query = f"SELECT * FROM users WHERE username = ''{username}'' AND password = ''{password}''"', 1, NULL, '2026-11-01 09:35:54');
INSERT INTO `findings` (`id`, `review_id`, `file_path`, `line_start`, `line_end`, `severity`, `category`, `message`, `suggestion`, `confidence`, `evidence`, `posted`, `github_comment_id`, `created_at`) VALUES (2, 1, 'src/auth/database.py', 15, NULL, 'CRITICAL', 'SECURITY', 'Không được lưu cứng khóa truy cập AWS trong mã nguồn. Cần chuyển sang sử dụng biến môi trường.', 'import os
    AWS_ACCESS_KEY_ID = os.environ.get(''AWS_ACCESS_KEY_ID'')', 0.95, 'AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"', 1, NULL, '2026-11-01 09:35:54');
INSERT INTO `findings` (`id`, `review_id`, `file_path`, `line_start`, `line_end`, `severity`, `category`, `message`, `suggestion`, `confidence`, `evidence`, `posted`, `github_comment_id`, `created_at`) VALUES (3, 2, 'src/payment/processor.py', 23, NULL, 'MAJOR', 'BUG', 'Nguy cơ lỗi ZeroDivisionError nếu tham số coupon_count bằng 0, có thể gây crash ứng dụng thanh toán.', 'if not coupon_count:
        return 0.0
    discount_ratio = total_amount / coupon_count', 0.92, 'discount_ratio = total_amount / coupon_count', 1, NULL, '2026-11-01 09:35:54');
INSERT INTO `findings` (`id`, `review_id`, `file_path`, `line_start`, `line_end`, `severity`, `category`, `message`, `suggestion`, `confidence`, `evidence`, `posted`, `github_comment_id`, `created_at`) VALUES (4, 3, 'src/auth/service.py', 48, 50, 'MINOR', 'PERFORMANCE', 'Có thể tối ưu hóa kết nối Redis bằng ConnectionPool thay vì khởi tạo socket mới mỗi request.', 'client = redis.Redis(connection_pool=pool)', 0.88, 'client = redis.Redis(host=''localhost'')', 1, NULL, '2026-11-01 09:35:54');

-- ------------------------------------------------------------
-- Table structure for `feedback`
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `feedback`;
CREATE TABLE `feedback` (
  `id` int NOT NULL AUTO_INCREMENT,
  `finding_id` int NOT NULL,
  `reaction` varchar(8) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `finding_id` (`finding_id`),
  CONSTRAINT `feedback_ibfk_1` FOREIGN KEY (`finding_id`) REFERENCES `findings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table structure for `pr_summaries`
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `pr_summaries`;
CREATE TABLE `pr_summaries` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pr_id` int NOT NULL,
  `head_sha` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `summary_md` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `risks_md` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `test_suggestions_md` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `github_comment_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `pr_id` (`pr_id`),
  CONSTRAINT `pr_summaries_ibfk_1` FOREIGN KEY (`pr_id`) REFERENCES `pull_requests` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table `pr_summaries`
INSERT INTO `pr_summaries` (`id`, `pr_id`, `head_sha`, `summary_md`, `risks_md`, `test_suggestions_md`, `github_comment_id`, `created_at`) VALUES (1, 1, 'e8f9a12c4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f', 'Pull Request bổ sung logic xác thực người dùng trong database và kết nối AWS.

Changes:
- Bổ sung hàm authenticate_user truy vấn bảng users
- Thêm khóa kết nối AWS credentials', '- Nguy cơ SQL Injection khi nối chuỗi trực tiếp
- Hardcoded AWS Access Key lộ lọt thông tin nhạy cảm', '- Kiểm thử bảo mật SQLi với username: '' OR ''1''=''1
- Chuyển AWS credentials sang .env', 900101, '2026-11-01 09:35:54');

-- ------------------------------------------------------------
-- Table structure for `webhook_deliveries`
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `webhook_deliveries`;
CREATE TABLE `webhook_deliveries` (
  `id` int NOT NULL AUTO_INCREMENT,
  `delivery_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `event` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `repo_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status_code` int NOT NULL,
  `duration_ms` int NOT NULL,
  `payload_summary` text COLLATE utf8mb4_unicode_ci,
  `error` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_webhook_deliveries_delivery_id` (`delivery_id`),
  KEY `ix_webhook_deliveries_event` (`event`),
  KEY `ix_webhook_deliveries_repo_name` (`repo_name`),
  KEY `ix_webhook_deliveries_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table `webhook_deliveries`
INSERT INTO `webhook_deliveries` (`id`, `delivery_id`, `event`, `action`, `repo_name`, `status`, `status_code`, `duration_ms`, `payload_summary`, `error`, `created_at`) VALUES (1, 'del_7f9a12c4-8e3b-41d2-9a3c', 'pull_request', 'opened', 'vku-se/student-management-app', 'accepted', 202, 85, 'PR #101 opened by vuminh', NULL, '2026-11-01 09:35:54');
INSERT INTO `webhook_deliveries` (`id`, `delivery_id`, `event`, `action`, `repo_name`, `status`, `status_code`, `duration_ms`, `payload_summary`, `error`, `created_at`) VALUES (2, 'del_8e3b41d2-9a3c-4e8f-7f9a', 'pull_request', 'synchronize', 'vku-se/core-library', 'accepted', 202, 110, 'PR #45 head sha updated to a1b2c3d4', NULL, '2026-11-01 09:35:54');
INSERT INTO `webhook_deliveries` (`id`, `delivery_id`, `event`, `action`, `repo_name`, `status`, `status_code`, `duration_ms`, `payload_summary`, `error`, `created_at`) VALUES (3, 'del_1a9c33e8-5d2e-4b6a-9f8e', 'ping', NULL, 'vku-se/auth-service', 'accepted', 200, 18, 'GitHub webhook ping handshake', NULL, '2026-11-01 09:35:54');

-- ------------------------------------------------------------
-- Table structure for `rule_configs`
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `rule_configs`;
CREATE TABLE `rule_configs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `config_key` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `language` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `min_confidence` float NOT NULL,
  `post_summary` tinyint(1) NOT NULL,
  `review_drafts` tinyint(1) NOT NULL,
  `severity_threshold` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `raw_yaml` text COLLATE utf8mb4_unicode_ci,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_rule_configs_config_key` (`config_key`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table `rule_configs`
INSERT INTO `rule_configs` (`id`, `config_key`, `language`, `min_confidence`, `post_summary`, `review_drafts`, `severity_threshold`, `raw_yaml`, `updated_at`) VALUES (1, 'default', 'vi', 0.8, 1, 0, 'minor', 'version: 1\\nlanguage: vi\\nrules:\\n  min_confidence: 0.80\\n  post_summary: true\\n  review_drafts: false\\n  severity_threshold: minor\\n', '2026-11-01 09:35:54');

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- Verification queries:
-- SELECT * FROM repositories;
-- SELECT * FROM pull_requests;
-- SELECT * FROM reviews;
-- SELECT * FROM findings;
-- SELECT * FROM webhook_deliveries;
-- ============================================================================