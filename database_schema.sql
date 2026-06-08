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
-- Login History Table (Fix Bug 10 / Supabase alignment)
-- ============================================
CREATE TABLE IF NOT EXISTS login_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ip_address VARCHAR(45) NOT NULL,
    user_agent VARCHAR(255) NOT NULL,
    login_time TIMESTAMP DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE
);

-- Create indexes for login history
CREATE INDEX IF NOT EXISTS idx_login_history_user_id ON login_history(user_id);
CREATE INDEX IF NOT EXISTS idx_login_history_time ON login_history(login_time DESC);

-- ============================================
-- Insert Default Site Content (Fix Bug 6)
-- ============================================
INSERT INTO site_content (page_section, content_text) VALUES
('about_description', 'LUNA (Linked Universal Neural Arm) is an advanced AI-powered robotic arm system developed for research and education.'),
('contact_email', 'luna@invicta.io'),
('contact_phone', '+1 555-LUNA'),
('contact_address', 'Grid Sector 7, Neo-Tech District'),
('contact_github', 'https://github.com/sunaypotnuru/Healix'),
('contact_linkedin', 'https://linkedin.com/company/invicta-labs'),
('institution_website', 'https://universalai.in/'),
('tech_specs_hardware', 'Arduino Mega 2560, PCA9685 PWM Driver, VL53L0X Distance Sensor, MPU6050 Accelerometer'),
('tech_specs_brain', 'Google Gemini AI for Natural Language Voice Processing, YOLOv8 for Object Detection & Mimicry')
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
