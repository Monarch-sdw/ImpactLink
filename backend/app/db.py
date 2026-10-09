import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()
URL = os.getenv('DATABASE_URL', 'sqlite:///./impactlink.db')
engine = create_engine(URL, connect_args={'check_same_thread': False, 'timeout': 30} if URL.startswith('sqlite') else {}, pool_pre_ping=True)
if URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_setup(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as session:
        yield session
