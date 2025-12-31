import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import registry, sessionmaker

# ← Use registry ao invés de declarative_base
table_registry = registry()

engine = create_engine('sqlite:///database.db')
SessionLocal = sessionmaker(bind=engine)


def create_tables():

    if os.path.exists('database.db'):
        os.remove('database.db')

    table_registry.metadata.create_all(bind=engine)


@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
