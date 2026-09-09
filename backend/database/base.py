# Single Declarative Base (Prevents circular imports)

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass