import uvicorn
from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    if user_id != 1:
        raise HTTPException(
            status_code=404,
            detail=f"用户 ID {user_id} 不存在"
        )
    return {"id": user_id, "name": "张三", "code": 200, "message": "操作成功", "data": []}


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8000)
