-- ============================================================
-- Lex Tabularum – Test Case Management Platform
-- Schema + Seed Data  v1
-- ============================================================

CREATE DATABASE IF NOT EXISTS lex_tabularum
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

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
-- Test Suites
-- ------------------------------------------------------------
CREATE TABLE test_suites (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    description     TEXT,
    created_by      INT UNSIGNED NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Test Cases
-- ------------------------------------------------------------
CREATE TABLE test_cases (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    suite_id        INT UNSIGNED NULL,
    external_id     VARCHAR(100) NULL,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    preconditions   TEXT,
    steps           TEXT NOT NULL,
    expected_result TEXT NOT NULL,
    priority        ENUM('critical','high','medium','low') NOT NULL DEFAULT 'medium',
    tags            VARCHAR(500) NULL,
    is_active       TINYINT(1) NOT NULL DEFAULT 1,
    created_by      INT UNSIGNED NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (suite_id)   REFERENCES test_suites(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_external_id (external_id),
    INDEX idx_priority (priority),
    INDEX idx_active (is_active)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Test Executions
-- ------------------------------------------------------------
CREATE TABLE test_executions (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    test_case_id        INT UNSIGNED NOT NULL,
    assigned_to         INT UNSIGNED NULL,
    executed_by         INT UNSIGNED NULL,
    status              ENUM('pending','pass','fail','blocked','skipped') NOT NULL DEFAULT 'pending',
    notes               TEXT,
    failure_description TEXT,
    screenshot_path     VARCHAR(500) NULL,
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
    gitlab_issue_iid    INT UNSIGNED NOT NULL,
    gitlab_issue_url    VARCHAR(500) NOT NULL,
    title               VARCHAR(500) NOT NULL,   -- includes username of the tester
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (execution_id) REFERENCES test_executions(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- SEED DATA
-- ============================================================

-- Password for all users: password123
-- bcrypt hash generated with cost 10
INSERT INTO users (username, email, full_name, password_hash, role) VALUES
('alice',  'alice@example.com',  'Alice Tester',   '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'tester'),
('bob',    'bob@example.com',    'Bob Lead',       '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'lead'),
('carol',  'carol@example.com',  'Carol Admin',    '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'admin');

-- Suites
INSERT INTO test_suites (name, description, created_by) VALUES
('Access, shell, and dashboard', 'Entitlements, launch, and dashboard behaviour', 3),
('PeerOps and ProgramReady',     'Team creation, membership, designations, qualifications', 3),
('Coverage and available services', 'Receiving agencies and coverage offers', 3),
('Intake and one-to-one peer support', 'Authenticated and public support requests', 3),
('Multi-member CISM operations', 'CISM activations, staffing, and lifecycle', 3),
('Mutual-aid personnel',         'External personnel and staffing invitations', 3),
('FollowThrough',                'Peer connection, follow-up tasks, and outcomes', 3),
('Privacy and resilience',       'Prohibited content, outages, and presentation', 3);

-- Sample test cases (subset of ResponderCare style for immediate use)
INSERT INTO test_cases
    (suite_id, external_id, title, description, preconditions, steps, expected_result, priority, tags, created_by)
VALUES
(1, 'RC-001', 'Entitlement and application launch',
 'Validate ResponderCare entitlement and application launch behaviour',
 'Platform initial setup complete',
 '1. Enable ResponderCare and assign a ResponderCare role to a member.\n2. Sign in and launch it from the applications landing page.\n3. Repeat after disabling the entitlement or membership.',
 'The authorized application appears and opens under the DutyArc origin; disabled access disappears and direct routes fail.',
 'critical', 'P0,smoke', 3),

(1, 'RC-002', 'Platform administrator non-bypass',
 'Ensure platform admins without operational roles cannot access ResponderCare data',
 'Platform admin account exists with no ResponderCare role',
 '1. Sign in as platform_admin with no ResponderCare operational role.\n2. Attempt team, request, roster, qualification, and activation URLs.',
 'Platform authority does not expose ResponderCare operational data or actions.',
 'critical', 'P0,security', 3),

(1, 'RC-003', 'Dashboard operational counts',
 'Verify dashboard cards reflect accurate operational state',
 'Known requests, offers, and activations exist',
 '1. Create requests, peer offers, and CISM activations in known states.\n2. Compare dashboard cards with queue and activation records.',
 'Available services, open/unverified requests, peer offers, active activations, staffing gaps, and the current user''s CISM offers are accurate and capability-filtered.',
 'high', 'P1,dashboard', 3),

(1, 'RC-004', 'Cross-tenant and cross-team denial',
 'Confirm strict isolation between organizations and teams',
 'Multiple organizations and teams exist',
 '1. Use Organization A and Team A UUIDs with a user authorized only for Organization B or another team.\n2. Test roster, evidence, request, activation, candidate, and staffing endpoints through browser routes.',
 'Access fails without revealing identities, contact hints, request references, or staffing state.',
 'critical', 'P0,security', 3),

(2, 'RC-010', 'Create internal and independent teams',
 'Create different types of peer and CISM teams',
 'Organization exists',
 '1. Create an internal peer team, countywide independent peer team, regional CISM team, and combined team.\n2. Verify name uniqueness, timezone, service area, governance, and status.',
 'Each team is organization-scoped and retains its declared purpose; invalid duplicates and stale updates fail.',
 'critical', 'P0,teams', 3),

(2, 'RC-011', 'Membership and coordinator bootstrap',
 'Bootstrap coordinators correctly and prevent self-appointment abuse',
 'Organization members exist',
 '1. Add organization members to a team.\n2. Appoint the first primary or backup coordinator as a different qualified person.\n3. Attempt self-appointment and repeat bootstrap after an eligible coordinator exists.',
 'Organization membership alone grants no designation; self-bootstrap is denied; the bootstrap closes after valid governance exists.',
 'critical', 'P0,governance', 3),

(4, 'RC-030', 'Authenticated support request',
 'Submit a support request while signed in',
 'Entitled responder and available peer service exist',
 '1. Sign in as an entitled responder and select an available peer service.\n2. Submit without narrative text.',
 'A provider-owned request is created in the correct team queue with authenticated verification and operational fields only.',
 'critical', 'P0,intake', 3),

(4, 'RC-031', 'Code-gated public request',
 'Public intake via scoped access code',
 'Active public access code exists for an external agency',
 '1. Issue a scoped, active public access code for an external agency.\n2. Open /?page=rc-request without signing in and submit approved contact information.\n3. Test invalid, expired, revoked, wrong-service, and exhausted codes plus rate limiting.',
 'Valid intake returns a reference and pending verification; invalid paths expose no team or agency data; raw codes/contact values do not enter logs or plaintext database fields.',
 'critical', 'P0,public,privacy', 3),

(5, 'RC-040', 'Create CISM activation',
 'Create a multi-member CISM activation from a triaged request',
 'CISM/CISD request exists',
 '1. Triage a CISM/CISD request and create an activation with intervention type, schedule, participant estimate, timezone, and affected disciplines.',
 'The request enters activation planning; the system creates lead facilitator, mental-health professional, and one peer position per selected discipline; no participant disclosures are stored.',
 'critical', 'P0,cism', 3),

(5, 'RC-041', 'Qualified internal staffing',
 'Offer and accept/decline positions with qualification checks',
 'Activation with open positions exists',
 '1. Inspect candidates for each required position.\n2. Offer positions to qualified internal members and accept/decline as those members.\n3. Change a qualification or attempt to staff one person into conflicting active positions.',
 'Only active, correctly designated, discipline-matched personnel appear; position and readiness states update correctly; decline reopens the slot.',
 'critical', 'P0,staffing', 3);

-- Assign some executions to Alice (user id 1) so the dashboard has content
INSERT INTO test_executions (test_case_id, assigned_to, status)
SELECT id, 1, 'pending'
FROM test_cases
WHERE external_id IN ('RC-001','RC-002','RC-003','RC-010','RC-030','RC-040');

-- Give Bob a couple as well
INSERT INTO test_executions (test_case_id, assigned_to, status)
SELECT id, 2, 'pending'
FROM test_cases
WHERE external_id IN ('RC-004','RC-011','RC-031');

-- One already completed example
INSERT INTO test_executions (test_case_id, assigned_to, executed_by, status, notes, executed_at)
SELECT id, 1, 1, 'pass', 'Worked as expected on first attempt', NOW()
FROM test_cases WHERE external_id = 'RC-003' LIMIT 1;
