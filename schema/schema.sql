-- ============================================================
-- Lex Tabularum – Test Case Management Platform
-- Schema v1
-- ============================================================

CREATE DATABASE IF NOT EXISTS lex_tabularum
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lex_tabularum;

-- ------------------------------------------------------------
-- Users
-- ------------------------------------------------------------
CREATE TABLE users (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50)  NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(150) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            ENUM('tester', 'lead', 'admin') NOT NULL DEFAULT 'tester',
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Test Suites (optional grouping)
-- ------------------------------------------------------------
CREATE TABLE test_suites (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    description     TEXT,
    created_by      INT UNSIGNED,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Test Cases
-- ------------------------------------------------------------
CREATE TABLE test_cases (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    suite_id        INT UNSIGNED NULL,
    external_id     VARCHAR(100) NULL,          -- e.g. TC-001 from your old system
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    preconditions   TEXT,
    steps           TEXT NOT NULL,              -- numbered steps, can be markdown
    expected_result TEXT NOT NULL,
    priority        ENUM('critical','high','medium','low') NOT NULL DEFAULT 'medium',
    tags            VARCHAR(500) NULL,          -- comma-separated for simplicity
    is_active       TINYINT(1) NOT NULL DEFAULT 1,
    created_by      INT UNSIGNED,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (suite_id)   REFERENCES test_suites(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_external_id (external_id),
    INDEX idx_priority (priority),
    INDEX idx_active (is_active)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Test Executions / Runs
-- ------------------------------------------------------------
CREATE TABLE test_executions (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    test_case_id        INT UNSIGNED NOT NULL,
    assigned_to         INT UNSIGNED NULL,       -- who should run it
    executed_by         INT UNSIGNED NULL,       -- who actually ran it
    status              ENUM('pending','pass','fail','blocked','skipped') NOT NULL DEFAULT 'pending',
    notes               TEXT,                    -- free text from the tester
    failure_description TEXT,                    -- required when status = fail
    screenshot_path     VARCHAR(500) NULL,       -- relative path to uploaded screenshot
    executed_at         DATETIME NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to)  REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (executed_by)  REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_assigned (assigned_to),
    INDEX idx_executed_by (executed_by)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- GitLab Issues (created from failed executions)
-- ------------------------------------------------------------
CREATE TABLE gitlab_issues (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    execution_id        INT UNSIGNED NOT NULL UNIQUE,
    gitlab_project_id   INT UNSIGNED NOT NULL,
    gitlab_issue_iid    INT UNSIGNED NOT NULL,   -- the # number in GitLab
    gitlab_issue_url    VARCHAR(500) NOT NULL,
    title               VARCHAR(500) NOT NULL,   -- will include username
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (execution_id) REFERENCES test_executions(id) ON DELETE CASCADE
) ENGINE=InnoDB;
