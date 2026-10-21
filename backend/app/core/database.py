from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    # A pooled connection can die unnoticed - a database failover, or an idle
    # connection dropped by a network hop. Pinging on checkout replaces it
    # before a request runs into it.
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


def get_session_factory() -> async_sessionmaker:
    """For work that outlives the request, such as a server-sent event stream.

    A request-scoped session from get_db is closed once the endpoint returns,
    while a stream keeps reading for as long as the client stays connected.
    """
    return SessionLocal
