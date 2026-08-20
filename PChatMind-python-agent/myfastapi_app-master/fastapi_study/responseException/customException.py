import uvicorn
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


class CustomException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=exc.code,
        content={"error": exc.message, "code": exc.code}
    )


@app.get("/error")
async def trigger_error():
    raise CustomException(code=400, message="自定义错误")


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8000)
