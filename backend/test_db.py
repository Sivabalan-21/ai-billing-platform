from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    print(conn.execute(text("select 1")).scalar())