-- Migration: Add Google OAuth fields to users and admins tables
-- Date: 2025-12-06

-- Add google_id and profile_picture to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE,
ADD COLUMN IF NOT EXISTS profile_picture TEXT;

-- Add google_id and profile_picture to admins table
ALTER TABLE admins
ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE,
ADD COLUMN IF NOT EXISTS profile_picture TEXT;

-- Create indexes for Google IDs
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_admins_google_id ON admins(google_id);

-- Make password_hash nullable since OAuth users don't need passwords
-- (Already nullable in the schema, this is just documentation)
