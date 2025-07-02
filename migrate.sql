CREATE TABLE IF NOT EXISTS history (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    response TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS file (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    indexed BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS files_used (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES file(id) ON DELETE CASCADE,
    history_id INTEGER REFERENCES history(id) ON DELETE CASCADE,
    UNIQUE(file_id, history_id)
);

CREATE INDEX IF NOT EXISTS idx_history_user_id ON history(user_id);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at);
CREATE INDEX IF NOT EXISTS idx_file_indexed ON file(indexed);
CREATE INDEX IF NOT EXISTS idx_file_uploaded_at ON file(uploaded_at);
CREATE INDEX IF NOT EXISTS idx_files_used_file_id ON files_used(file_id);
CREATE INDEX IF NOT EXISTS idx_files_used_history_id ON files_used(history_id);

ALTER TABLE history ENABLE ROW LEVEL SECURITY;
ALTER TABLE file ENABLE ROW LEVEL SECURITY;
ALTER TABLE files_used ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own history" ON history
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view all files" ON file
    FOR SELECT USING (true);

CREATE POLICY "Users can upload files" ON file
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Users can manage files_used through history" ON files_used
    USING (
        EXISTS (
            SELECT 1 FROM history
            WHERE history.id = files_used.history_id
            AND history.user_id = auth.uid()
        )
    );
