import uvicorn
from fastapi import FastAPI, Path

app = FastAPI()


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/items/id/{item_id}")
async def read_item_by_id(
        item_id: int = Path(..., ge=1, le=10, title="这是个路径参数", description="要获取的项目 ID，必须在 1-10 之间",
                            examples=[5])):
    """
    根据项目 ID 获取项目信息
    :param ...: 路径参数不能为空
    :param ge:大于等于1
    :param le:小于等于10
    :return: 包含项目 ID 的字典对象
    """
    return {"item_id": item_id, "description": "项目 ID", "summary": "根据项目 ID 获取项目信息", "tags": ["items"],
            "deprecated": False, "extra": "这是个额外的字段"}


@app.get("/items/name/{name}")
async def read_item_by_name(
        name: str = Path(..., max_length=10, min_length=1, title="这是个路径参数", description="要获取的项目名称",
                         examples=["fastapi"])):
    """
    根据项目名称获取项目信息
    :param ...: 路径参数不能为空
    :param title:这是个路径参数
    :param description:要获取的项目名称
    :param max_length: 项目名称最大长度为10
    :param min_length: 项目名称最小长度为1
    :return: 包含项目名称的字典对象
    """

    return {"name": name, "description": "项目名称", "summary": "根据项目名称获取项目信息", "tags": ["items"],
            "deprecated": False, "extra": "这是个额外的字段"}


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
