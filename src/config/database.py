"""
Database Configuration for TimescaleDB
Handles SQLAlchemy engine, sessions, and connection pooling
"""

from sqlalchemy import create_engine, text, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import logging

from src.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# SQLAlchemy Engine Configuration
# ============================================================================

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,  # Verify connections before using them
    echo=settings.DB_ECHO,  # Log SQL queries if enabled
)

# ============================================================================
# Session Factory
# ============================================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ============================================================================
# Declarative Base
# ============================================================================

Base = declarative_base()

# ============================================================================
# Database Event Listeners
# ============================================================================

@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """
    Event listener triggered on each database connection
    Logs successful connections
    """
    logger.debug("Database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """
    Event listener triggered when a connection is checked out from the pool
    """
    logger.debug("Connection checked out from pool")


# ============================================================================
# Slow Query Logging
# ============================================================================

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Record query start time for slow query detection"""
    import time
    conn.info.setdefault('query_start_time', []).append(time.time())


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log slow queries (>2 seconds)"""
    import time
    total = time.time() - conn.info['query_start_time'].pop(-1)
    if total > 2.0:  # Log queries taking more than 2 seconds
        logger.warning(
            f"Slow query detected ({total:.2f}s): {statement[:200]}",
            extra={
                "query_time": total,
                "query": statement[:500]
            }
        )


# ============================================================================
# Database Session Dependency
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions
    Automatically handles session lifecycle and rollback on errors

    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db here
            pass
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions (for non-FastAPI code)

    Usage:
        with get_db_context() as db:
            # Use db here
            pass
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database context error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


# ============================================================================
# Database Health Check
# ============================================================================

def check_database_connection() -> bool:
    """
    Check if database connection is healthy

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False


# ============================================================================
# Database Initialization
# ============================================================================

async def init_database():
    """
    Initialize database connection and verify TimescaleDB extension
    Called during application startup
    """
    try:
        # Test database connection
        if not check_database_connection():
            raise Exception("Database connection failed")

        logger.info("✅ Database connection established")

        # Verify TimescaleDB extension
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'")
            )
            if result.scalar() == 0:
                logger.warning("⚠️  TimescaleDB extension not found")
            else:
                logger.info("✅ TimescaleDB extension verified")

        # Log connection pool info
        logger.info(
            f"Database pool configured: size={settings.DB_POOL_SIZE}, "
            f"max_overflow={settings.DB_MAX_OVERFLOW}"
        )

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        raise


async def close_database():
    """
    Close all database connections
    Called during application shutdown
    """
    try:
        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {str(e)}")


# ============================================================================
# Query Helper Functions
# ============================================================================

def execute_raw_sql(query: str, params: dict = None):
    """
    Execute raw SQL query (for migrations, admin tasks)

    Args:
        query: SQL query string
        params: Optional query parameters

    Returns:
        Query result
    """
    with get_db_context() as db:
        if params:
            result = db.execute(query, params)
        else:
            result = db.execute(query)
        return result


def get_table_row_count(table_name: str) -> int:
    """
    Get row count for a table

    Args:
        table_name: Name of the table

    Returns:
        Number of rows in the table
    """
    with engine.connect() as conn:
        result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        return result.scalar()
