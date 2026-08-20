import uvicorn
from fastapi import FastAPI,Query,Depends


app = FastAPI()

# 创建专门的依赖函数
def common_pagination(
    pageNum: int = Query(0, description="页码", ge=0, le=10),
    pageSize: int = Query(10, description="每页数量", ge=1, le=20)
):
    return {"pageNum": pageNum, "pageSize": pageSize}

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.get("/user/")
async def read_user(pagination = Depends(common_pagination)):
    return {"pageNum": pagination["pageNum"], "pageSize": pagination["pageSize"]}


@app.get("/items/")
async def read_items(comon = Depends(common_pagination)):
    return {"comon": comon}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

