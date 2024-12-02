import logging
import os
import requests
import sys
import time
import uvicorn

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse


sys.path.append("./")


from app.configs.config import basicSettings
# from app.database.smart import Engine
from app.routers.v1.base import router_v1
from app.middleware.exception import exception_message


def init_app():

    app = FastAPI(
        version=basicSettings.VERSION,
        titie="Smart app"
    )
    
    app.include_router(router_v1, prefix=basicSettings.BASE_PREFIX)
    
    # Setting local Static files directory (offline)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(BASE_DIR, 'static')
    app.mount('/static', StaticFiles(directory=static_dir), name="static")
    
    origins = ["http://localhost"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*']
    )
    
    return app


APP = init_app()


uvicorn_logger = logging.getLogger('uvicorn.error')
system_logger = logging.getLogger('custom.error')


@APP.middleware("http")
async def log_middleware(request:Request, call_next):
    
    # print(request.url.path)
    # print(request.client.host)
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
    
    except Exception as e:
        system_logger.error(exception_message(e))
        response = JSONResponse(
            status_code=500,
            content={"message":"internal server error"}
        )
        
    finally:
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

# Define Exception Handler
@APP.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request:Request, 
    exc:StarletteHTTPException
    ):
  
    '''Define the response format while raising HTTPException'''
    if exc.status_code == 404:
        return JSONResponse(
        status_code=exc.status_code,
        content={"message":exc.detail})
    elif exc.status_code == 500:
        return JSONResponse(
        status_code=exc.status_code,
        content={"message":"internal server error"})
    else:
        return JSONResponse(
        status_code=exc.status_code,
        content={"message":exc.detail})

if __name__ == "__main__":

    uvicorn.run(
        "main:APP",        # 指定檔案名稱和 APP 實例
        host="127.0.0.1",  # 預設運行在本機
        port=8000,         # 預設端口為 8000
        workers=5,
        reload=True        # 開發模式下使用自動重載
    )
    
    # expose_port = os.environ['FASTAPI_PORT']
    # worker_count = os.environ['WORKER_COUNT']
    # debug = os.getenv('DEBUG', False) == 'True'
    # debug = True
    # uvicorn.run(
    #   "main:APP", 
    #   host="0.0.0.0", 
    #   port=basicSettings.SERVICE_PORT,
    #   workers=basicSettings.WORKER_COUNT,
    #   reload=basicSettings.SERVICE_DEBUG,
    #   root_path=basicSettings.BASE_PATH,
    #   log_level="info",
    #   log_config='log_conf.yml'
    # )