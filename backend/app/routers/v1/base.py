from fastapi import APIRouter, Depends

from app.routers.v1.endpoints import (
    smart_ecg
)


router_v1 = APIRouter() 


## [GET] : Test
@router_v1.get("", tags=["Test"])
async def test():
    return JSONResponse(status_code=200, content="Here goes the apis")

router_v1.include_router(smart_ecg.router, prefix="/SMART-ECG", tags=["SMART-ECG"])
