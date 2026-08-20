from fastapi import FastAPI, Query
import uvicorn

app = FastAPI()


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/count/")
async def read_root(pageNum: int = Query(0, title="跳过数量", description="要跳过的项目数量", ge=0, le=100),
                    pageSize: int = Query(10, title="项目数量", description="要获取的项目数量", ge=1, le=100)):
    """
    分页查询项目信息
    :param skip: 跳过数量，必须大于等于0，小于等于100
    :param limit: 项目数量，必须大于等于1，小于等于100
    :return: 包含跳过数量和项目数量的字典对象
    """
    return {"skip": pageNum, "limit": pageSize}


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
