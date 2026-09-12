# 统一异常处理：未捕获异常 -> 统一 JSON 错误体，不把堆栈甩给前端
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("yinku.error")


class AppError(Exception):
    """业务异常基类，可带状态码"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code,
                            content={"code": exc.status_code, "message": exc.message})

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("未捕获的异常: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"code": 500, "message": "服务器内部错误"})
