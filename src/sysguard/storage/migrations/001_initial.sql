CREATE TABLE collection_sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration REAL NOT NULL CHECK(duration > 0),
    interval REAL NOT NULL CHECK(interval > 0),
    status TEXT NOT NULL CHECK(status IN ('running','completed','interrupted','failed'))
);
CREATE TABLE system_samples (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES collection_sessions(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    cpu_percent REAL,
    memory_total INTEGER,
    memory_available INTEGER,
    memory_percent REAL,
    disk_read_bytes INTEGER,
    disk_write_bytes INTEGER,
    network_bytes_sent INTEGER,
    network_bytes_recv INTEGER,
    process_count INTEGER
);
CREATE TABLE process_samples (
    id INTEGER PRIMARY KEY,
    sample_id INTEGER NOT NULL REFERENCES system_samples(id) ON DELETE CASCADE,
    pid INTEGER NOT NULL,
    create_time REAL,
    name TEXT,
    exe TEXT,
    ppid INTEGER,
    status TEXT,
    cpu_percent REAL,
    rss INTEGER,
    vms INTEGER,
    num_threads INTEGER,
    disk_read_bytes INTEGER,
    disk_write_bytes INTEGER,
    username TEXT,
    UNIQUE(sample_id, pid)
);
CREATE INDEX idx_system_timestamp ON system_samples(timestamp);
CREATE INDEX idx_system_session_time ON system_samples(session_id, timestamp);
CREATE INDEX idx_process_identity ON process_samples(pid, create_time);
CREATE INDEX idx_process_sample ON process_samples(sample_id);
