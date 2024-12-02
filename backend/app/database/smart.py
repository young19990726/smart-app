# from sqlalchemy import create_engine, URL
# from sqlalchemy.orm import sessionmaker

# from app.configs.config import dbSettings


# SQLALCHEMY_DATABASE_URL = URL.create(
#   f"postgresql",
#     username=dbSettings.DB_USER,
#     password=dbSettings.DB_PASSWORD,
#     host=dbSettings.DB_HOSTNAME,
#     port=dbSettings.DB_PORT,
#     database=dbSettings.DB_NAME
# )

# Engine = create_engine(
#     SQLALCHEMY_DATABASE_URL,
#     # connect_args={"client_encoding": "utf8"} # Set the database encoding to UTF-8
# )

# Session = sessionmaker(
#     autocommit=False, # Disable autocommit so that transaction commits can be managed manually
#     autoflush=False,  # Disable auto-refresh to avoid automatically refreshing the session before executing the query
#     bind=Engine       # Bind the session to the database engine created earlier
# )

# def get_conn():

#     db = Session()
    
#     try:
#         yield db
    
#     except Exception:
#         db.rollback()
#         raise
    
#     finally:
#         db.close()