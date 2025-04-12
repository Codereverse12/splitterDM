CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT,
    register_date NUMERIC NOT NULL,
    ig_id INTEGER UNIQUE,
    ig_username TEXT UNIQUE,
    default_config_id TEXT
);

CREATE TABLE IF NOT EXISTS gameplays (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    length_seconds INTEGER NOT NULL,
    size_kb INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS video_configurations (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    config_name TEXT NOT NULL,
    split_type TEXT CHECK (split_type IN ('horizontal', 'vertical')),
    video_position TEXT CHECK (video_position IN ('left', 'right', 'top', 'bottom')),
    edit_type TEXT CHECK (edit_type IN ('crop', 'fit')),
    original_video_percentage INTEGER CHECK(original_video_percentage BETWEEN 0 AND 100),
    created_at NUMERIC NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS config_gameplays (
    config_id TEXT NOT NULL,
    gameplay_id TEXT NOT NULL,
    PRIMARY KEY (config_id, gameplay_id),
    FOREIGN KEY (config_id) REFERENCES video_configurations(id) ON DELETE CASCADE,
    FOREIGN KEY (gameplay_id) REFERENCES gameplays(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS video_jobs (
    id TEXT PRIMARY KEY,
    config_id TEXT, 
    gameplay_id TEXT,
    user_id INTEGER NOT NULL,
    caption TEXT,
    video_url TEXT,
    video_type TEXT CHECK (video_type IN ('tiktok', 'youtube', 'instagram')),
    status TEXT CHECK (status IN ('pending', 'downloaded', 'processing', 'completed', 'failed')) DEFAULT 'pending',
    processing_errors TEXT,
    created_at NUMERIC NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    FOREIGN KEY (config_id) REFERENCES video_configurations(id) ON DELETE SET NULL,
    FOREIGN KEY (gameplay_id) REFERENCES gameplays(id) ON DELETE SET NULL
);

