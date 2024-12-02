# from datetime import datetime
# from pydantic import BaseModel, Field


# """
# Smart ECG Pydantic Schema
# """


# class SmartECGBase(BaseModel):
    
#     uid: int | None = Field(None, description="Id")
#     file_path: str | None = Field(None, max_length=200, description="File path")
#     create_time: datetime | None = Field(None, description="Create time of data")
#     is_analyzed: bool | None = Field(None, description="Is analyzed?")
#     result: dict | None = Field(None, description="Analysis result in JSON format")

#     class Config:
      
#         from_attributes = True  # Enable direct conversion from ORM models
#         json_encoders = {datetime: lambda v: v.isoformat()}  # Convert datetime to ISO 8601 string