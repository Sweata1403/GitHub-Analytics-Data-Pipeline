-- ============================================================
-- GitHub Analytics Data Pipeline — Star Schema (Gold Layer)
-- Database: PostgreSQL 15+
-- ============================================================
-- This schema follows a star schema design with:
--   • 3 Dimension Tables: dim_repository, dim_user, dim_date
--   • 3 Fact Tables: fact_commits, fact_pull_requests, fact_issues
-- ============================================================

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

-- dim_date: Calendar dimension (pre-populated 2020–2030)
CREATE TABLE IF NOT EXISTS dim_date (
    date_id         INTEGER PRIMARY KEY,           -- YYYYMMDD format
    full_date       DATE NOT NULL UNIQUE,
    year            SMALLINT NOT NULL,
    quarter         SMALLINT NOT NULL,
    month           SMALLINT NOT NULL,
    month_name      VARCHAR(10) NOT NULL,
    week            SMALLINT NOT NULL,
    day_of_month    SMALLINT NOT NULL,
    day_of_week     SMALLINT NOT NULL,             -- 0=Monday, 6=Sunday
    day_name        VARCHAR(10) NOT NULL,
    is_weekend      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_dim_date_year ON dim_date(year);
CREATE INDEX IF NOT EXISTS idx_dim_date_year_month ON dim_date(year, month);


-- dim_repository: GitHub repository dimension
CREATE TABLE IF NOT EXISTS dim_repository (
    repository_id       SERIAL PRIMARY KEY,
    github_repo_id      BIGINT UNIQUE NOT NULL,
    full_name           VARCHAR(255) NOT NULL,
    owner               VARCHAR(100) NOT NULL,
    name                VARCHAR(200) NOT NULL,
    description         TEXT,
    language            VARCHAR(50),
    default_branch      VARCHAR(100) DEFAULT 'main',
    is_private          BOOLEAN DEFAULT FALSE,
    is_fork             BOOLEAN DEFAULT FALSE,
    stars_count         INTEGER DEFAULT 0,
    forks_count         INTEGER DEFAULT 0,
    watchers_count      INTEGER DEFAULT 0,
    open_issues_count   INTEGER DEFAULT 0,
    size_kb             INTEGER DEFAULT 0,
    license_name        VARCHAR(50),
    html_url            VARCHAR(500),
    created_at          TIMESTAMP WITH TIME ZONE,
    updated_at          TIMESTAMP WITH TIME ZONE,
    -- SCD Type 1: overwrite on update
    etl_loaded_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_repo_owner ON dim_repository(owner);
CREATE INDEX IF NOT EXISTS idx_dim_repo_language ON dim_repository(language);
CREATE INDEX IF NOT EXISTS idx_dim_repo_github_id ON dim_repository(github_repo_id);


-- dim_user: GitHub user dimension
CREATE TABLE IF NOT EXISTS dim_user (
    user_id             SERIAL PRIMARY KEY,
    github_user_id      BIGINT UNIQUE,
    login               VARCHAR(100) NOT NULL,
    avatar_url          VARCHAR(500),
    user_type           VARCHAR(20) DEFAULT 'User',  -- User, Bot, Organization
    html_url            VARCHAR(500),
    -- SCD Type 1
    etl_loaded_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_user_login ON dim_user(login);


-- ============================================================
-- FACT TABLES
-- ============================================================

-- fact_commits: Individual commit records
CREATE TABLE IF NOT EXISTS fact_commits (
    commit_id               SERIAL PRIMARY KEY,
    sha                     VARCHAR(40) NOT NULL,
    repository_id           INTEGER NOT NULL REFERENCES dim_repository(repository_id),
    author_id               INTEGER REFERENCES dim_user(user_id),
    committer_id            INTEGER REFERENCES dim_user(user_id),
    date_id                 INTEGER REFERENCES dim_date(date_id),
    message                 TEXT,
    additions               INTEGER DEFAULT 0,
    deletions               INTEGER DEFAULT 0,
    files_changed           INTEGER DEFAULT 0,
    net_lines               INTEGER GENERATED ALWAYS AS (additions - deletions) STORED,
    authored_at             TIMESTAMP WITH TIME ZONE,
    -- Deduplication
    UNIQUE(sha, repository_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_commits_repo ON fact_commits(repository_id);
CREATE INDEX IF NOT EXISTS idx_fact_commits_author ON fact_commits(author_id);
CREATE INDEX IF NOT EXISTS idx_fact_commits_date ON fact_commits(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_commits_authored ON fact_commits(authored_at);


-- fact_pull_requests: Pull request lifecycle records
CREATE TABLE IF NOT EXISTS fact_pull_requests (
    pr_id                   SERIAL PRIMARY KEY,
    github_pr_id            BIGINT NOT NULL,
    number                  INTEGER NOT NULL,
    repository_id           INTEGER NOT NULL REFERENCES dim_repository(repository_id),
    author_id               INTEGER REFERENCES dim_user(user_id),
    created_date_id         INTEGER REFERENCES dim_date(date_id),
    merged_date_id          INTEGER REFERENCES dim_date(date_id),
    closed_date_id          INTEGER REFERENCES dim_date(date_id),
    title                   TEXT,
    state                   VARCHAR(20) NOT NULL,           -- open, closed
    is_merged               BOOLEAN DEFAULT FALSE,
    is_draft                BOOLEAN DEFAULT FALSE,
    comments_count          INTEGER DEFAULT 0,
    review_comments_count   INTEGER DEFAULT 0,
    commits_count           INTEGER DEFAULT 0,
    additions               INTEGER DEFAULT 0,
    deletions               INTEGER DEFAULT 0,
    changed_files           INTEGER DEFAULT 0,
    created_at              TIMESTAMP WITH TIME ZONE,
    merged_at               TIMESTAMP WITH TIME ZONE,
    closed_at               TIMESTAMP WITH TIME ZONE,
    -- Derived: time to merge in hours
    time_to_merge_hours     DOUBLE PRECISION,
    -- Deduplication
    UNIQUE(github_pr_id, repository_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_prs_repo ON fact_pull_requests(repository_id);
CREATE INDEX IF NOT EXISTS idx_fact_prs_author ON fact_pull_requests(author_id);
CREATE INDEX IF NOT EXISTS idx_fact_prs_created_date ON fact_pull_requests(created_date_id);
CREATE INDEX IF NOT EXISTS idx_fact_prs_state ON fact_pull_requests(state);


-- fact_issues: Issue lifecycle records
CREATE TABLE IF NOT EXISTS fact_issues (
    issue_id                SERIAL PRIMARY KEY,
    github_issue_id         BIGINT NOT NULL,
    number                  INTEGER NOT NULL,
    repository_id           INTEGER NOT NULL REFERENCES dim_repository(repository_id),
    author_id               INTEGER REFERENCES dim_user(user_id),
    created_date_id         INTEGER REFERENCES dim_date(date_id),
    closed_date_id          INTEGER REFERENCES dim_date(date_id),
    title                   TEXT,
    state                   VARCHAR(20) NOT NULL,           -- open, closed
    comments_count          INTEGER DEFAULT 0,
    labels                  TEXT[],                          -- PostgreSQL array
    assignees               TEXT[],
    milestone               VARCHAR(200),
    created_at              TIMESTAMP WITH TIME ZONE,
    closed_at               TIMESTAMP WITH TIME ZONE,
    -- Derived: time to close in hours
    time_to_close_hours     DOUBLE PRECISION,
    -- Deduplication
    UNIQUE(github_issue_id, repository_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_issues_repo ON fact_issues(repository_id);
CREATE INDEX IF NOT EXISTS idx_fact_issues_author ON fact_issues(author_id);
CREATE INDEX IF NOT EXISTS idx_fact_issues_created_date ON fact_issues(created_date_id);
CREATE INDEX IF NOT EXISTS idx_fact_issues_state ON fact_issues(state);


-- ============================================================
-- SUPPLEMENTARY TABLES
-- ============================================================

-- repo_languages: Language breakdown per repository
CREATE TABLE IF NOT EXISTS repo_languages (
    id                  SERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES dim_repository(repository_id),
    language            VARCHAR(50) NOT NULL,
    bytes               BIGINT NOT NULL DEFAULT 0,
    percentage          DOUBLE PRECISION DEFAULT 0,
    UNIQUE(repository_id, language)
);

CREATE INDEX IF NOT EXISTS idx_repo_languages_repo ON repo_languages(repository_id);


-- ============================================================
-- INGESTION TRACKING
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              VARCHAR(50) PRIMARY KEY,
    started_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at        TIMESTAMP WITH TIME ZONE,
    status              VARCHAR(30) NOT NULL DEFAULT 'running',
    repos_processed     INTEGER DEFAULT 0,
    total_commits       INTEGER DEFAULT 0,
    total_prs           INTEGER DEFAULT 0,
    total_issues        INTEGER DEFAULT 0,
    errors              TEXT[],
    CONSTRAINT chk_status CHECK (status IN ('running', 'completed', 'failed', 'completed_with_errors'))
);


-- ============================================================
-- USEFUL VIEWS (for the FastAPI backend)
-- ============================================================

-- Repository overview with aggregated stats
CREATE OR REPLACE VIEW v_repository_overview AS
SELECT
    r.repository_id,
    r.full_name,
    r.owner,
    r.name,
    r.description,
    r.language,
    r.stars_count,
    r.forks_count,
    r.is_fork,
    r.created_at,
    r.html_url,
    COUNT(DISTINCT fc.commit_id)    AS total_commits,
    COUNT(DISTINCT fp.pr_id)        AS total_prs,
    COUNT(DISTINCT fi.issue_id)     AS total_issues,
    COALESCE(SUM(fc.additions), 0)  AS total_additions,
    COALESCE(SUM(fc.deletions), 0)  AS total_deletions
FROM dim_repository r
LEFT JOIN fact_commits fc ON r.repository_id = fc.repository_id
LEFT JOIN fact_pull_requests fp ON r.repository_id = fp.repository_id
LEFT JOIN fact_issues fi ON r.repository_id = fi.repository_id
GROUP BY r.repository_id;


-- Daily commit activity
CREATE OR REPLACE VIEW v_daily_commit_activity AS
SELECT
    d.full_date,
    d.year,
    d.month,
    d.day_name,
    d.is_weekend,
    r.full_name AS repository,
    COUNT(fc.commit_id) AS commit_count,
    COUNT(DISTINCT fc.author_id) AS unique_authors,
    COALESCE(SUM(fc.additions), 0) AS additions,
    COALESCE(SUM(fc.deletions), 0) AS deletions
FROM fact_commits fc
JOIN dim_date d ON fc.date_id = d.date_id
JOIN dim_repository r ON fc.repository_id = r.repository_id
GROUP BY d.full_date, d.year, d.month, d.day_name, d.is_weekend, r.full_name
ORDER BY d.full_date;


-- PR merge metrics by repository
CREATE OR REPLACE VIEW v_pr_metrics AS
SELECT
    r.full_name AS repository,
    r.repository_id,
    COUNT(*) AS total_prs,
    COUNT(*) FILTER (WHERE fp.state = 'open') AS open_prs,
    COUNT(*) FILTER (WHERE fp.is_merged = TRUE) AS merged_prs,
    COUNT(*) FILTER (WHERE fp.state = 'closed' AND fp.is_merged = FALSE) AS closed_unmerged,
    ROUND(AVG(fp.time_to_merge_hours)::NUMERIC, 1) AS avg_merge_time_hours,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fp.time_to_merge_hours)::NUMERIC, 1) AS median_merge_time_hours
FROM fact_pull_requests fp
JOIN dim_repository r ON fp.repository_id = r.repository_id
GROUP BY r.full_name, r.repository_id;


-- Top contributors across all repos
CREATE OR REPLACE VIEW v_top_contributors AS
SELECT
    u.login,
    u.avatar_url,
    COUNT(DISTINCT fc.commit_id) AS total_commits,
    COUNT(DISTINCT fc.repository_id) AS repos_contributed_to,
    COALESCE(SUM(fc.additions), 0) AS total_additions,
    COALESCE(SUM(fc.deletions), 0) AS total_deletions,
    MIN(fc.authored_at) AS first_commit,
    MAX(fc.authored_at) AS last_commit
FROM dim_user u
JOIN fact_commits fc ON u.user_id = fc.author_id
GROUP BY u.user_id, u.login, u.avatar_url
ORDER BY total_commits DESC;
