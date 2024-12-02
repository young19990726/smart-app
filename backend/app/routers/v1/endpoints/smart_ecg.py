import json
import logging
import os
import sys

from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, Query, status, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from io import BytesIO
from jose import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response
from typing import Annotated, List, Optional , Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

# from app.database.smart import get_conn
from app.middleware.exception import exception_message
from app.misc.utils.aiecg_api import ecg_ai_model
from app.misc.utils.parse_ecg_from_fhir import convert_to_matrix, extract_ecg_data, plot_ecg_from_matrix, resample_ecg_matrix 
from app.misc.utils.validate_fhir_format import validate_fhir_format
# from app.models.smart import SmartECG
# from app.schemas.v1.smart_ecg import SmartECGBase


router = APIRouter()


uvicorn_logger = logging.getLogger('uvicorn.error')
system_logger = logging.getLogger('custom.error')


UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..', 'file', 'json'))
os.makedirs(UPLOAD_DIR, exist_ok=True)


env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'configs', '.env'))
load_dotenv(dotenv_path=env_path)

SECRET_KEY = os.getenv("SECRET_KEY")                           
ALGORITHM = os.getenv("ALGORITHM")  
ACCESS_TOKEN_EXPIRE_MINUTES = 30  
USERNAME = os.getenv("USERNAME")      
HASHED_PASSWORD = os.getenv("HASHED_PASSWORD")  
USER_DB = {USERNAME: {"username": USERNAME, "hashed_password": HASHED_PASSWORD, "disabled": False}}


class Token(BaseModel):
    access_token: str                 
    token_type: str                   

class TokenData(BaseModel):
    username: Union[str, None] = None 

class User(BaseModel):
    username: str                     
    disabled: Union[bool, None] = None

class UserInDB(User):
    hashed_password: str       


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://127.0.0.1:8000/api/v1/SMART-ECG/token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire}) 
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM) 

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    
    user = get_user(USER_DB, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@router.post("/token")
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    
    user = authenticate_user(USER_DB, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    
    return Token(access_token=access_token, token_type="bearer")

@router.get("/users/me/", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user

@router.get("/users/me/items/")
async def read_own_items(current_user: Annotated[User, Depends(get_current_active_user)]):
    return [{"item_id": "Foo", "owner": current_user.username}]

@router.post("", name="Post FHIR data", description="Post FHIR data", include_in_schema=True)
async def upload_fhir_file_get_value(
    current_user: Annotated[User, Depends(get_current_active_user)],
    file: UploadFile = File(...),
    # db: Session = Depends(get_conn)
):
    try:
        if not file.content_type == "application/json":
            raise HTTPException(status_code=400, detail="Invalid file type. Only JSON files are supported.")

        file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                file_data = json.load(f)

                # validate FHIR format using FHIR server (maybe)
                # if not validate_fhir_format(file_data):
                #     raise HTTPException(status_code=400, detail="Invalid FHIR format.")
                
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail="Invalid JSON file format.")

        leads_data, metadata = extract_ecg_data(file_data)
        uid = metadata.get('subject')[9:16]
        ecg_matrix = convert_to_matrix(leads_data)
        resampled_matrix = resample_ecg_matrix(ecg_matrix)
        # fig = plot_ecg_from_matrix(resampled_matrix, sample_rate=500, uid=file_name.split(".json")[0])
        fig_path = plot_ecg_from_matrix(resampled_matrix, sample_rate=500, uid=file_name.split(".json")[0])

        matrix_data = resampled_matrix.T
        # processed_result = ecg_ai_model(matrix_data)

        # new_record = SmartECG(file_path=file_name, is_analyzed=True, result=processed_result)
        # db.add(new_record)
        # db.commit()

        uvicorn_logger.info(f"Uploaded and processed file: {file_name}")

        return {
            "message": "File uploaded and processed successfully",
            "file_name": file_name,
            "file_path": file_path,
            "fig_path": fig_path,
            # "result": processed_result,
        }

    # except SQLAlchemyError as e:
    #     db.rollback()
    #     system_logger.error(f"Database error: {str(e)}")
    #     raise HTTPException(status_code=500, detail="Failed to save file information to the database.")

    except Exception as e:
        system_logger.error(f"Error processing file: {exception_message(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the file.")

# ## [GET]：Root
# @router.get("")
# async def root(request:Request):
#     return {"Root":request.scope.get("root_path")}

## [POST] : 
# @router.post("", name="Post FHIR data", description="Post FHIR data", include_in_schema=True)
# async def upload_fhir_file_get_value(
#     file: UploadFile = File(...),
#     # db: Session = Depends(get_conn)
# ):
#     try:
#         if not file.content_type == "application/json":
#             raise HTTPException(status_code=400, detail="Invalid file type. Only JSON files are supported.")

#         file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
#         file_path = os.path.join(UPLOAD_DIR, file_name)
#         with open(file_path, "wb") as f:
#             f.write(await file.read())

#         with open(file_path, "r", encoding="utf-8") as f:
#             try:
#                 file_data = json.load(f)

#                 # validate FHIR format using FHIR server (maybe)
#                 # if not validate_fhir_format(file_data):
#                 #     raise HTTPException(status_code=400, detail="Invalid FHIR format.")
                
#             except json.JSONDecodeError as e:
#                 raise HTTPException(status_code=400, detail="Invalid JSON file format.")

#         leads_data, metadata = extract_ecg_data(file_data)
#         uid = metadata.get('subject')[9:16]
#         ecg_matrix = convert_to_matrix(leads_data)
#         resampled_matrix = resample_ecg_matrix(ecg_matrix)
#         # fig = plot_ecg_from_matrix(resampled_matrix, sample_rate=500, uid=file_name.split(".json")[0])
#         fig_path = plot_ecg_from_matrix(resampled_matrix, sample_rate=500, uid=file_name.split(".json")[0])

#         matrix_data = resampled_matrix.T
#         # processed_result = ecg_ai_model(matrix_data)

#         # new_record = SmartECG(file_path=file_name, is_analyzed=True, result=processed_result)
#         # db.add(new_record)
#         # db.commit()

#         uvicorn_logger.info(f"Uploaded and processed file: {file_name}")

#         return {
#             "message": "File uploaded and processed successfully",
#             "file_name": file_name,
#             "file_path": file_path,
#             "fig_path": fig_path,
#             # "result": processed_result,
#         }

#     # except SQLAlchemyError as e:
#     #     db.rollback()
#     #     system_logger.error(f"Database error: {str(e)}")
#     #     raise HTTPException(status_code=500, detail="Failed to save file information to the database.")

#     except Exception as e:
#         system_logger.error(f"Error processing file: {exception_message(e)}")
#         raise HTTPException(status_code=500, detail="An error occurred while processing the file.")

# @router.post("/image", name="Post ECG wave", description="Post ECG wave", include_in_schema=True)
# async def upload_fhir_file_get_image(
#     file: UploadFile = File(...),
#     db: Session = Depends(get_conn)
# ):
#     try:
#         if not file.content_type == "application/json":
#             raise HTTPException(status_code=400, detail="Invalid file type. Only JSON files are supported.")
        
#         file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
#         file_path = os.path.join(UPLOAD_DIR, file_name)
#         with open(file_path, "wb") as f:
#             f.write(await file.read())
        
#         with open(file_path, "r", encoding="utf-8") as f:
#             try:
#                 file_data = json.load(f)
#             except json.JSONDecodeError as e:
#                 raise HTTPException(status_code=400, detail="Invalid JSON file format.") from e
        
#         leads_data, metadata = extract_ecg_data(file_data)
#         uid = metadata.get('subject')[9:16]
#         ecg_matrix = convert_to_matrix(leads_data)
#         resampled_matrix = resample_ecg_matrix(ecg_matrix)
#         fig = plot_ecg_from_matrix(resampled_matrix, sample_rate=500, uid=file_name.split(".json")[0])

#         img_buffer = BytesIO()
#         fig.savefig(img_buffer, format='png', bbox_inches='tight', dpi=300)
#         img_buffer.seek(0)

#         uvicorn_logger.info(f"Uploaded and display image: {file_name}")

#         return Response(img_buffer.getvalue(), media_type="image/png")
        
        
#     except SQLAlchemyError as e:
#         db.rollback()
#         system_logger.error(f"Database error: {str(e)}")
#         raise HTTPException(status_code=500, detail="Failed to save file information to the database.")

#     except Exception as e:
#         system_logger.error(f"Error processing file: {str(e)}")
#         raise HTTPException(status_code=500, detail="An error occurred while processing the file.")

# ## [POST] : 
# @router.post("", name="Post FHIR data", description="Post FHIR data", include_in_schema=True)
# async def upload_fhir_file(
#     file: UploadFile = File(...),
#     db: Session = Depends(get_conn)
# ):
#     """接收 FHIR 文件，保存到伺服器，並將文件資訊記錄到資料庫"""
#     try:
#         if not file.content_type == "application/json":
#             raise HTTPException(status_code=400, detail="Invalid file type. Only JSON files are supported.")

#         file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
#         file_path = os.path.join(UPLOAD_DIR, file_name)
#         with open(file_path, "wb") as f:
#             f.write(await file.read())

#         new_record = SmartECG(file_path=file_name)
#         db.add(new_record)
#         db.commit()

#         uvicorn_logger.info(f"Uploaded file: {file_name}")

#         return {
#             "message": "File uploaded successfully",
#             "file_name": file_name,
#             "file_path": file_path,
#         }

#     except SQLAlchemyError as e:
#         db.rollback()
#         system_logger.error(f"Database error: {str(e)}")
#         raise HTTPException(status_code=500, detail="Failed to save file information to the database.")

#     except Exception as e:
#         system_logger.error(f"Error processing file: {str(e)}")
#         raise HTTPException(status_code=500, detail="An error occurred while processing the file.")

# ## [GET]：
# @router.get("", response_model=List[SmartECGBase], name="Get FHIR path", description="Get FHIR path", include_in_schema=True)
# async def get_fhir_path(
#     db: Session=Depends(get_conn)
# ):
#     """取得尚未經過 AI 預測的資料"""
#     try:
#         data = db.query(SmartECG).filter(SmartECG.is_analyzed == False).all()
    
#     except Exception as e:
#         system_logger.error(exception_message(e))
#         raise HTTPException(status_code=500, detail="Error get smart ECG")
    
#     if len(data) == 0:
#         raise HTTPException(status_code=404, detail=f"SmartECG not exists")
    
#     return data

# ## [PUT]: 
# @router.put("/fhir-processed", name="Process FHIR data", description="Process FHIR data and update result")
# async def process_fhir_data(
#     result: dict,
#     uid: Optional[int] = Query(None, description="Update uid"),
#     db: Session = Depends(get_conn)
# ):
#     """將 AI 預測結果存進資料庫，並標示為已分析"""
#     try:
#         fhir_data = db.query(SmartECG).filter(SmartECG.uid == uid).first()
#         if not fhir_data:
#             raise HTTPException(status_code=400, detail="The uid is not found")

#         fhir_data.result = result
#         fhir_data.is_analyzed = True

#         db.commit()

#         uvicorn_logger.info(f"Processed UID: {uid} and updated result.")

#         return {
#             "message": "Data processed successfully.",
#             "record_id": uid,
#             "result": fhir_data.result
#         }

#     except SQLAlchemyError as e:
#         db.rollback()
#         system_logger.error(f"Database error: {exception_message(e)}")
#         raise HTTPException(status_code=500, detail="Failed to update record in the database.")

#     except Exception as e:
#         system_logger.error(f"Error processing data: {exception_message(e)}")
#         raise HTTPException(status_code=500, detail="An error occurred while processing the data.")
    
if __name__ == "__main__":
    pass