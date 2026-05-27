SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    target_paths_json TEXT NOT NULL,
    total_files INTEGER NOT NULL DEFAULT 0,
    scanned_files INTEGER NOT NULL DEFAULT 0,
    cache_used_count INTEGER NOT NULL DEFAULT 0,
    detection_group_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_session_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    normalized_path TEXT NOT NULL,
    storage_type TEXT NOT NULL,
    media_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    sha256 TEXT,
    perceptual_hash TEXT,
    blur_score REAL,
    cache_status TEXT NOT NULL,
    scan_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (scan_session_id) REFERENCES scan_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_media_files_path ON media_files(normalized_path);
CREATE INDEX IF NOT EXISTS idx_media_files_sha256 ON media_files(sha256);
CREATE INDEX IF NOT EXISTS idx_media_files_size ON media_files(size_bytes);

CREATE TABLE IF NOT EXISTS analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    normalized_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    media_type TEXT NOT NULL,
    sha256 TEXT,
    perceptual_hash TEXT,
    blur_score REAL,
    last_scanned_at TEXT NOT NULL,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_analysis_cache_key
ON analysis_cache(normalized_path, size_bytes, modified_at);

CREATE TABLE IF NOT EXISTS detection_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_session_id INTEGER NOT NULL,
    group_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (scan_session_id) REFERENCES scan_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_detection_groups_session
ON detection_groups(scan_session_id, group_type);

CREATE TABLE IF NOT EXISTS detection_group_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_group_id INTEGER NOT NULL,
    media_file_id INTEGER NOT NULL,
    recommended_action TEXT NOT NULL,
    selected_by_default INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (detection_group_id) REFERENCES detection_groups(id),
    FOREIGN KEY (media_file_id) REFERENCES media_files(id)
);

CREATE INDEX IF NOT EXISTS idx_detection_group_items_group
ON detection_group_items(detection_group_id);

CREATE TABLE IF NOT EXISTS quarantine_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_file_id INTEGER,
    original_path TEXT NOT NULL,
    original_normalized_path TEXT NOT NULL,
    quarantined_path TEXT NOT NULL,
    original_size_bytes INTEGER NOT NULL,
    original_modified_at TEXT NOT NULL,
    source_storage_type TEXT NOT NULL,
    status TEXT NOT NULL,
    quarantined_at TEXT NOT NULL,
    error_message TEXT,
    FOREIGN KEY (media_file_id) REFERENCES media_files(id)
);

CREATE INDEX IF NOT EXISTS idx_quarantine_original_path
ON quarantine_records(original_normalized_path);

CREATE TABLE IF NOT EXISTS app_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    level TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    path TEXT,
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_app_events_created_at ON app_events(created_at);
CREATE INDEX IF NOT EXISTS idx_app_events_level ON app_events(level);
"""
