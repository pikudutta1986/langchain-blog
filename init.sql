CREATE DATABASE IF NOT EXISTS blog_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE blog_db;

CREATE TABLE IF NOT EXISTS blog_posts (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(500)     NOT NULL,
    slug        VARCHAR(500)     NOT NULL UNIQUE,
    topic       VARCHAR(255)     NOT NULL,
    content     LONGTEXT         NOT NULL,
    summary     TEXT,
    image_path  VARCHAR(500),
    image_b64   LONGTEXT,
    status      ENUM('draft', 'published', 'failed') DEFAULT 'draft',
    created_at  DATETIME         DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME         DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    topic       VARCHAR(255)     NOT NULL,
    raw_data    LONGTEXT,
    insights    LONGTEXT,
    created_at  DATETIME         DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    run_id      VARCHAR(64)      NOT NULL UNIQUE,
    status      ENUM('running', 'completed', 'failed') DEFAULT 'running',
    blog_post_id INT,
    error_message TEXT,
    started_at  DATETIME         DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    FOREIGN KEY (blog_post_id) REFERENCES blog_posts(id) ON DELETE SET NULL
);
