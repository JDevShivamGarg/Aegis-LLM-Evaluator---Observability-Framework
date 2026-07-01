import uuid
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, func, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.core.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    suites = relationship("TestSuite", back_populates="project", cascade="all, delete-orphan")

class TestSuite(Base):
    __tablename__ = "test_suites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    custom_evaluators = Column(JSONB, nullable=False, server_default="[]")
    judge_config = Column(JSONB, nullable=False, server_default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="suites")
    cases = relationship("TestCase", back_populates="suite", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="suite", cascade="all, delete-orphan")

class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite_id = Column(UUID(as_uuid=True), ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False)
    input_prompt = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=True)
    assertion_rules = Column(JSONB, nullable=False, server_default="[]")
    context_documents = Column(ARRAY(Text), nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    suite = relationship("TestSuite", back_populates="cases")
    results = relationship("TestResult", back_populates="test_case", cascade="all, delete-orphan")

class Run(Base):
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite_id = Column(UUID(as_uuid=True), ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")
    triggered_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    suite = relationship("TestSuite", back_populates="runs")
    results = relationship("TestResult", back_populates="run", cascade="all, delete-orphan")

class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    actual_output = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run = relationship("Run", back_populates="results")
    test_case = relationship("TestCase", back_populates="results")
    scores = relationship("MetricScore", back_populates="test_result", cascade="all, delete-orphan")

class MetricScore(Base):
    __tablename__ = "metric_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_result_id = Column(UUID(as_uuid=True), ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_type = Column(String(50), nullable=False)  # 'LLM_JUDGE', 'EMBEDDING_SIMILARITY', 'RULE_ASSERTION'
    score = Column(Float, nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    test_result = relationship("TestResult", back_populates="scores")
