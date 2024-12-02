# from sqlalchemy import Boolean, Column, DateTime, func, Integer, JSON, String
# from sqlalchemy.orm import declarative_base

# from app.database.smart import Engine


# Base = declarative_base()


# class SmartECG(Base):
#     __tablename__ = "smart_ecg"

#     uid = Column(Integer, primary_key=True, autoincrement=True)
#     file_path = Column(String(100), index=True)
#     create_time = Column(DateTime, default=func.now())
#     is_analyzed = Column(Boolean, default=False)
#     result = Column(JSON, nullable=True)

# # Create all defined tables in the DB
# Base.metadata.create_all(bind=Engine)