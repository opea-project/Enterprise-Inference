# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Float
from sqlalchemy.sql import func
from app.database import Base

class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    model_name = Column(String, nullable=False)
    input_filename = Column(String, nullable=False)
    hyperparameters = Column(JSON, default=dict)
    
    # Job Status
    status = Column(String, default="PENDING", index=True)  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    error_log = Column(Text, nullable=True)
    
    # Progress Tracking
    progress_percent = Column(Float, default=0.0)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, nullable=True)
    training_loss = Column(Float, nullable=True)
    
    # GPU Metrics
    gpu_memory_used_gb = Column(Float, nullable=True)
    gpu_utilization_percent = Column(Float, nullable=True)
    
    # Output
    output_file_id = Column(String, nullable=True)
    output_path = Column(String, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    elapsed_seconds = Column(Integer, nullable=True)
    
    # Metadata
    dataset_size = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "username": self.username,
            "model_name": self.model_name,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "training_loss": self.training_loss,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": self.elapsed_seconds,
            "output_file_id": self.output_file_id,
            "error_log": self.error_log
        }
