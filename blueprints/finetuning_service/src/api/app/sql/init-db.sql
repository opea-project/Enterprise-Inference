-- Database initialization for Fine-Tuning Middleware Service
-- This middleware orchestrates fine-tuning jobs across different backends (Nvidia, Xeon, Azure)
-- Actual training happens on backend systems
-- Authentication is handled by Keycloak - no local user storage

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Fine-tuning jobs table (tracks jobs across all backends)
CREATE TABLE IF NOT EXISTS fine_tuning_jobs (
    id VARCHAR(255) PRIMARY KEY,
    model VARCHAR(255) NOT NULL,
    training_file VARCHAR(255) NOT NULL,
    validation_file VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    user_id VARCHAR(255) NOT NULL,  -- Keycloak user ID (sub claim)
    hyperparameters JSONB,
    suffix VARCHAR(255),
    created_at INTEGER NOT NULL,
    updated_at INTEGER,
    finished_at INTEGER,
    fine_tuned_model VARCHAR(500),
    error_message TEXT,
    error_code VARCHAR(255),      -- OpenAI error code (e.g. 'server_error')
    error_param VARCHAR(255),     -- OpenAI error param if applicable
    result_files JSONB,
    trained_tokens INTEGER,
    -- Tracking fields
    organization_id VARCHAR(255),
    seed INTEGER,
    estimated_finish INTEGER,
    -- Backend routing
    resource_type VARCHAR(50) DEFAULT 'nvidia',
    resource_job_id VARCHAR(255),
    -- Constraints
    CONSTRAINT chk_status CHECK (status IN ('queued', 'validating_files', 'running', 'succeeded', 'failed', 'cancelled')),
    CONSTRAINT chk_resource_type CHECK (resource_type IN ('nvidia', 'xeon', 'azure', 'gaudi')),
    CONSTRAINT chk_created_at_positive CHECK (created_at > 0),
    CONSTRAINT chk_trained_tokens_positive CHECK (trained_tokens IS NULL OR trained_tokens >= 0)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON fine_tuning_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON fine_tuning_jobs(status) WHERE status != 'succeeded';  -- Partial index for active jobs
CREATE INDEX IF NOT EXISTS idx_jobs_resource_type ON fine_tuning_jobs(resource_type);
CREATE INDEX IF NOT EXISTS idx_jobs_resource_job_id ON fine_tuning_jobs(resource_job_id) WHERE resource_job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON fine_tuning_jobs(created_at DESC);  -- For sorting by recent
CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON fine_tuning_jobs(user_id, status);  -- Composite for user queries

-- Job events table (for detailed logging and audit trail)
CREATE TABLE IF NOT EXISTS job_events (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) NOT NULL REFERENCES fine_tuning_jobs(id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    level VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(100),
    data JSONB,
    -- Constraints
    CONSTRAINT chk_level CHECK (level IN ('info', 'warning', 'error', 'debug')),
    CONSTRAINT chk_created_at_positive CHECK (created_at > 0)
);

-- Performance indexes for events
CREATE INDEX IF NOT EXISTS idx_events_job_id ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON job_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_level ON job_events(level) WHERE level IN ('error', 'warning');  -- Focus on issues

-- Base Models table (stores available models for fine-tuning)
CREATE TABLE IF NOT EXISTS base_models (
    id VARCHAR(255) PRIMARY KEY,  -- e.g., 'meta-llama/Llama-3.2-3B-Instruct'
    object VARCHAR(50) NOT NULL DEFAULT 'model',
    created INTEGER NOT NULL,
    owned_by VARCHAR(255) NOT NULL,
    description TEXT,
    resource_type VARCHAR(50),  -- Which backend supports this model (NULL = all backends)
    is_active BOOLEAN NOT NULL DEFAULT true,
    -- Performance metadata
    context_length INTEGER,
    parameters_count BIGINT,  -- Number of parameters (e.g., 3000000000 for 3B)
    -- Constraints
    CONSTRAINT chk_created_positive CHECK (created > 0),
    CONSTRAINT chk_resource_type_models CHECK (resource_type IS NULL OR resource_type IN ('nvidia', 'xeon', 'azure', 'gaudi')),
    CONSTRAINT chk_context_length CHECK (context_length IS NULL OR context_length > 0),
    CONSTRAINT chk_parameters_count CHECK (parameters_count IS NULL OR parameters_count > 0)
);

-- Performance indexes for base models
CREATE INDEX IF NOT EXISTS idx_base_models_resource_type ON base_models(resource_type) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_base_models_is_active ON base_models(is_active);

-- Insert default base models for fine-tuning
INSERT INTO base_models (id, object, created, owned_by, description, resource_type, is_active, context_length, parameters_count)
VALUES
    ('meta-llama/Llama-3.2-3B-Instruct', 'model', 1699046400, 'meta',
     'Llama 3.2 3B Instruct - Optimized for instruction following',
     NULL, true, 8192, 3000000000),
    ('meta-llama/Llama-3.1-8B-Instruct', 'model', 1699046400, 'meta',
     'Llama 3.1 8B Instruct - Larger model with better performance',
     NULL, true, 8192, 8000000000)
ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    context_length = EXCLUDED.context_length,
    parameters_count = EXCLUDED.parameters_count;

-- Create view for active jobs (commonly queried)
CREATE OR REPLACE VIEW active_jobs AS
SELECT
    id,
    model,
    status,
    user_id,
    resource_type,
    created_at,
    estimated_finish
FROM fine_tuning_jobs
WHERE status NOT IN ('succeeded', 'failed', 'cancelled')
ORDER BY created_at DESC;

-- Grant permissions (if using role-based access)
-- GRANT SELECT, INSERT, UPDATE ON fine_tuning_jobs TO finetuning_app;
-- GRANT SELECT, INSERT ON job_events TO finetuning_app;
-- GRANT SELECT ON base_models TO finetuning_app;

-- Add table comments for documentation
COMMENT ON TABLE fine_tuning_jobs IS 'Tracks fine-tuning jobs across all backend resources (Nvidia, Xeon, Azure, Gaudi)';
COMMENT ON TABLE job_events IS 'Audit trail and logging for fine-tuning job lifecycle events';
COMMENT ON TABLE base_models IS 'Available base models for fine-tuning with metadata';
COMMENT ON COLUMN fine_tuning_jobs.resource_type IS 'Backend resource type (nvidia/xeon/azure/gaudi)';
COMMENT ON COLUMN fine_tuning_jobs.resource_job_id IS 'Job ID from the backend system';
COMMENT ON COLUMN base_models.resource_type IS 'NULL means available on all backends, otherwise specific to one backend';
