-- LUNA Robotic Arm - Database Schema
-- Run this SQL script in your Supabase SQL Editor to create all required tables

-- ============================================
-- Users Table
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'operator',
    created_at TIMESTAMP DEFAULT NOW(),
    full_name VARCHAR(100),
    bio TEXT,
    photo_url VARCHAR(200),
    linkedin_url VARCHAR(200),
    github_url VARCHAR(200)
);

-- Create index on username for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ============================================
-- Team Members Table
-- ============================================
CREATE TABLE IF NOT EXISTS team_members (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(100) NOT NULL,
    bio TEXT,
    photo_url VARCHAR(200),
    linkedin_url VARCHAR(200),
    github_url VARCHAR(200),
    display_order INTEGER DEFAULT 0
);

-- Create index on display_order for sorting
CREATE INDEX IF NOT EXISTS idx_team_display_order ON team_members(display_order);

-- ============================================
-- Site Content Table
-- ============================================
CREATE TABLE IF NOT EXISTS site_content (
    id SERIAL PRIMARY KEY,
    page_section VARCHAR(100) UNIQUE NOT NULL,
    content_text TEXT NOT NULL
);

-- Create index on page_section for faster lookups
CREATE INDEX IF NOT EXISTS idx_site_content_section ON site_content(page_section);

-- ============================================
-- Mission Logs Table
-- ============================================
CREATE TABLE IF NOT EXISTS mission_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT NOW(),
    command VARCHAR(50) NOT NULL,
    robot_state JSONB NOT NULL
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_mission_logs_user_id ON mission_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_mission_logs_timestamp ON mission_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_mission_logs_command ON mission_logs(command);

-- ============================================
-- Insert Default Site Content
-- ============================================
INSERT INTO site_content (page_section, content_text) VALUES
('about_intro', 'LUNA (Linked Universal Neural Arm) is an advanced AI-powered robotic arm system developed for research and education.'),
('about_mission', 'Our mission is to make advanced robotics accessible through intuitive control interfaces and cutting-edge AI integration.'),
('features_intro', 'LUNA combines multiple control methods, real-time computer vision, and natural language processing to create an intuitive robotic control experience.'),
('contact_info', 'For inquiries about LUNA, please reach out through our contact form or email.')
ON CONFLICT (page_section) DO NOTHING;

-- ============================================
-- Verification Queries
-- ============================================
-- Run these to verify tables were created successfully:

-- Check all tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('users', 'team_members', 'site_content', 'mission_logs');

-- Check users table structure
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users';

-- Check mission_logs table structure
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'mission_logs';

-- ============================================
-- Optional: Sample Data for Testing
-- ============================================
-- Uncomment to insert sample team member
-- INSERT INTO team_members (name, role, bio, display_order) VALUES
-- ('Potnuru Sunay', 'Team Lead & AI Engineer', 'Lead developer specializing in computer vision and AI integration.', 1);
