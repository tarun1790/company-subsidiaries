import sys
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings
from app.core.logging import logger

# SQLAlchemy declarations
Base = declarative_base()

# Create async engine with fallback support
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10
)

# Session maker
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

def fallback_to_sqlite():
    global engine, AsyncSessionLocal
    logger.warning("PostgreSQL is unavailable. Falling back to local SQLite database.")
    sqlite_url = "sqlite+aiosqlite:///./subsidiary.db"
    engine = create_async_engine(
        sqlite_url,
        echo=False,
        future=True
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to retrieve database session."""
    # Always check out session from the active AsyncSessionLocal reference
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database transaction error: {str(e)}")
            raise
        finally:
            await session.close()

async def init_db() -> None:
    """Initialize database schemas (create tables) with pg-to-sqlite fallback retry."""
    # Import models here to register them with Base metadata
    from app.models.company import Company
    from app.models.subsidiary import Subsidiary, Evidence
    from app.models.report import Report

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Failed to connect to PostgreSQL: {str(e)}")
        # Trigger SQLite fallback
        fallback_to_sqlite()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database initialized successfully with SQLite fallback.")
        except Exception as sqlite_err:
            logger.critical(f"SQLite initialization failed: {str(sqlite_err)}")

