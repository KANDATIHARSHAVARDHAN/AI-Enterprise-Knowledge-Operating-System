-- ============================================
-- EKOS - Enterprise Knowledge Operating System
-- MySQL Database Schema
-- ============================================

CREATE DATABASE IF NOT EXISTS ekos_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ekos_db;

-- ============================================
-- Users & Authentication
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) DEFAULT '',
    role ENUM('admin', 'analyst', 'viewer') NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_email (email),
    INDEX idx_users_role (role)
) ENGINE=InnoDB;

-- ============================================
-- Documents
-- ============================================
CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size_bytes BIGINT NOT NULL DEFAULT 0,
    file_path VARCHAR(1000) NOT NULL,
    status ENUM('pending', 'processing', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    error_message TEXT,
    chunk_count INT DEFAULT 0,
    uploaded_by INT,
    metadata_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_documents_status (status),
    INDEX idx_documents_file_type (file_type),
    INDEX idx_documents_uploaded_by (uploaded_by)
) ENGINE=InnoDB;

-- ============================================
-- Document Chunks
-- ============================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    metadata_json JSON,
    embedding_id VARCHAR(100),
    token_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    INDEX idx_chunks_document_id (document_id),
    INDEX idx_chunks_embedding_id (embedding_id),
    UNIQUE INDEX idx_chunks_doc_index (document_id, chunk_index)
) ENGINE=InnoDB;

-- ============================================
-- Conversations
-- ============================================
CREATE TABLE IF NOT EXISTS conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(500) DEFAULT 'New Conversation',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_conversations_user_id (user_id)
) ENGINE=InnoDB;

-- ============================================
-- Messages
-- ============================================
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    content TEXT NOT NULL,
    agent_trace_json JSON,
    citations_json JSON,
    confidence_score FLOAT DEFAULT NULL,
    latency_ms INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_messages_conversation_id (conversation_id)
) ENGINE=InnoDB;

-- ============================================
-- Query Logs (for evaluation)
-- ============================================
CREATE TABLE IF NOT EXISTS query_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    conversation_id INT,
    query TEXT NOT NULL,
    response_summary TEXT,
    retrieved_chunks_json JSON,
    agent_path_json JSON,
    latency_ms INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    model_used VARCHAR(100),
    status ENUM('success', 'failed', 'partial') DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    INDEX idx_query_logs_user_id (user_id),
    INDEX idx_query_logs_created_at (created_at)
) ENGINE=InnoDB;

-- ============================================
-- Evaluation Results
-- ============================================
CREATE TABLE IF NOT EXISTS evaluation_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_log_id INT NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    score FLOAT NOT NULL,
    details_json JSON,
    evaluator VARCHAR(50) DEFAULT 'ragas',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (query_log_id) REFERENCES query_logs(id) ON DELETE CASCADE,
    INDEX idx_eval_query_log_id (query_log_id),
    INDEX idx_eval_metric_name (metric_name)
) ENGINE=InnoDB;

-- ============================================
-- Enterprise Data: Machine Events
-- ============================================
CREATE TABLE IF NOT EXISTS machine_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id VARCHAR(50) NOT NULL,
    machine_name VARCHAR(200) NOT NULL,
    event_type ENUM('failure', 'warning', 'maintenance', 'inspection', 'repair') NOT NULL,
    description TEXT NOT NULL,
    severity ENUM('critical', 'high', 'medium', 'low') NOT NULL DEFAULT 'medium',
    root_cause TEXT,
    reported_by VARCHAR(200),
    department VARCHAR(100),
    production_line VARCHAR(100),
    downtime_hours FLOAT DEFAULT 0,
    cost_usd DECIMAL(10, 2) DEFAULT 0,
    event_date TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_machine_events_machine_id (machine_id),
    INDEX idx_machine_events_type (event_type),
    INDEX idx_machine_events_date (event_date),
    INDEX idx_machine_events_severity (severity)
) ENGINE=InnoDB;

-- ============================================
-- Enterprise Data: Maintenance Logs
-- ============================================
CREATE TABLE IF NOT EXISTS maintenance_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id VARCHAR(50) NOT NULL,
    machine_name VARCHAR(200) NOT NULL,
    action_type ENUM('preventive', 'corrective', 'emergency', 'inspection') NOT NULL,
    description TEXT NOT NULL,
    technician VARCHAR(200) NOT NULL,
    parts_replaced TEXT,
    parts_cost_usd DECIMAL(10, 2) DEFAULT 0,
    labor_cost_usd DECIMAL(10, 2) DEFAULT 0,
    total_cost_usd DECIMAL(10, 2) DEFAULT 0,
    duration_hours FLOAT DEFAULT 0,
    status ENUM('completed', 'in_progress', 'scheduled', 'cancelled') DEFAULT 'completed',
    notes TEXT,
    log_date TIMESTAMP NOT NULL,
    next_maintenance_date TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_maintenance_machine_id (machine_id),
    INDEX idx_maintenance_date (log_date),
    INDEX idx_maintenance_technician (technician(100))
) ENGINE=InnoDB;

-- ============================================
-- Audit Logs
-- ============================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(100),
    details_json JSON,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_audit_user_id (user_id),
    INDEX idx_audit_action (action),
    INDEX idx_audit_created_at (created_at)
) ENGINE=InnoDB;

-- ============================================
-- Conversation Memory (Long-term)
-- ============================================
CREATE TABLE IF NOT EXISTS memory_store (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    memory_type ENUM('fact', 'preference', 'summary', 'entity') NOT NULL,
    content TEXT NOT NULL,
    metadata_json JSON,
    importance_score FLOAT DEFAULT 0.5,
    access_count INT DEFAULT 0,
    last_accessed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_memory_user_id (user_id),
    INDEX idx_memory_type (memory_type)
) ENGINE=InnoDB;
