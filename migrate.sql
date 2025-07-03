CREATE TABLE IF NOT EXISTS history (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat (
    id SERIAL PRIMARY KEY,
    history_id INTEGER REFERENCES history(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    response TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS file (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
);

CREATE INDEX IF NOT EXISTS idx_history_user_id ON history(user_id);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at);
CREATE INDEX IF NOT EXISTS idx_file_uploaded_at ON file(uploaded_at);

ALTER TABLE history ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat ENABLE ROW LEVEL SECURITY;
ALTER TABLE file ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own history" ON history
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view all files" ON file
    FOR SELECT USING (true);

CREATE POLICY "Users can upload files" ON file
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Users can view their own chats" ON chat
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM history
            WHERE history.id = chat.history_id
              AND history.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert chats for their history" ON chat
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM history
            WHERE history.id = chat.history_id
              AND history.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update their own chats" ON chat
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM history
            WHERE history.id = chat.history_id
              AND history.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete their own chats" ON chat
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM history
            WHERE history.id = chat.history_id
              AND history.user_id = auth.uid()
        )
    );

