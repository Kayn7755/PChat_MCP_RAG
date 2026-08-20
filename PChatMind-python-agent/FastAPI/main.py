"""
FastAPI基础代码

可通过uvicorn main:app --reload运行
main是名称 app是FastAPI实例   reload是修改代码后自动重启服务器
"""
from fastapi import FastAPI, Path, Query, Depends, File, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse, FileResponse
import models # 将models中的模块与main产生关联

# 创建FastAPI实例
app = FastAPI()

# 这是一个装饰器，表示定义一个 GET 请求接口，路径是根路径 /
@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/hello/{name}")
async def hello(name: str):
    return {"message": f"Hello, {name}!"}

# 路由
@app.get("/hello")
async def hello(name: str):
    return {"message": "Hello!"}

# path注解
@app.get("/book/{id}")
def getbook(id:int = Path(...,gt=0,lt=101,description="书籍id, 范围是0-101")):
    return {f"{id}"}

# 查询参数Query
# 查询新闻+分页 skip跳过的记录数 limit返回的记录数
@app.get("/news/news_list")
async def get_news_list(skip:int = Query(0,description="跳过的记录数", lt=101),
                        limit:int = Query(10,description="返回的记录数")):
    return {"skip": skip, "limit": limit}

# 请求体参数
# 实现注册功能 继承BaseModel把Python类变成数据校验模型, 根据pydantic的BaseModel判断接受请求体参数
class User(BaseModel):
    username: str = Field(default="未命名123456", min_length=3, max_length=10)
    password: str = Field(default="123456", min_length=6, max_length=20)

@app.post("/register")
async def register(user: User):
    return user

@app.get("/html", response_class=HTMLResponse)
async def get_html():
    return "<h1>Hello</h1>"

@app.get("/file")
async def get_file():
    path = "./file/1.jpg"
    return FileResponse(path) # FileResponse是处理文件响应, 用于后端把磁盘上的文件发回浏览器

# 客户端->服务器文件上传
@app.post("/upload")
async def upload(file: UploadFile = File(...)): #  UploadFile将用来接收上传的文件; UploadFile 本身不限类型，PDF、JPG 都能作为二进制传上来
    data = await file.read()   # 读上传内容读到的是文件的二进制内容（bytes） 请注意，read会消耗内存，因此对于大文件，你可能需要分块读取或使用其他策略
    # 保存到磁盘 / 交给业务处理
    with open(file.filename, "wb") as f:
        f.write(data) # 把二进制内容写到磁盘
    return {"filename": file.filename}

# 自定义响应数据格式
class News(BaseModel):
    id:int
    title:str
    content:str

@app.get("/news", response_model=News) # response_model约定了响应的数据格式, 返回值不是该类型会报错
async def get_news(id:int):
    return {
        "id": id,
        "title": id,
        "content": "111"
    }

# 异常响应
from fastapi import HTTPException
@app.get("/news/{id}")
async def get_news(id:int):
    id_list = {1,2,3,4,5,6}
    if(id not in id_list):
        raise HTTPException(status_code=404,
                            detail="没找到")

    return {"id": id}

# 中间件
@app.middleware("http")
                    # 传入中间件的参数, 中间件的回调函数
async def middleware(request, call_next):
    print("中间件1开始")
    response = await call_next(request) # await 等待整个请求处理链完成, 异步, 暂停的是当前这个函数，而不是整个程序。
    print("中间件1结束")
    return response # 返回中间件执行结果

# 依赖注入
# 实现一个通用的功能common_params
async def common_params(
        skip:int = Query(0,ge=0),
        limit:int = Query(10,le=60)
):
    return {skip,limit}

# 通过commons和Depends将这个功能加入到其它函数的形参中
@app.get("/news", response_model=News) # response_model约定了响应的数据格式, 返回值不是该类型会报错
async def get_ccc(id:int,commons=Depends(common_params)):
    # 请求进来先执行common_params, 返回值给commons, 再执行本函数内容
    # doing(commons)
    return commons
# FastAPI 的 Depends 做不到「先跑接口再跑依赖」。
# 依赖一定在路由函数之前执行；这是设计如此。

# 如果想先跑接口再跑依赖, 可以使用yield
async def common_params(skip: int = Query(0), limit: int = Query(10)):
    # —— 这里在 get_ccc 之前 ——
    params = {"skip": skip, "limit": limit} # 执行原common_params功能
    yield params # yield用来暂停函数并交出一个值，之后还可以从暂停处继续跑。这种函数叫生成器
    # —— return 之后才会走到这里（做清理、收尾）——
    print("接口已结束，做收尾")

@app.get("/news")
async def get_ccc(id: int, commons=Depends(common_params)):
    return commons # 返回暂停处的值
    # 执行完后再执行print("接口已结束，做收尾") # 因为 return 结束的是 get_ccc，不是 common_params。这是两个函数。

from models.user import AsyncSessionFactory
# CRUD-注册Session, 相当于创建了一个用于操作数据库的类
async def get_session():
    session = AsyncSessionFactory() #  1. 创建一个新的异步数据库会话
    try: #  # 路由正常用 session，或中途抛异常
        yield session # 2. 将 session 传递给需要的路由函数
    finally: # finally 里的代码不管前面成功还是出错都会执行。请求结束或接口报错时，都把数据库 session 关掉，避免连接泄漏。
        await session.close() # 3. 请求处理完毕后，确保关闭连接
        # await异步方法，表示：等关闭完成后再继续; 没有 await 的话，关闭可能还没真正做完函数就往下走了（在 async 里也不对）


# 通过依赖注入方式获取session并实现数据库增加操作
from typing import List
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
@app.post('/article/add', response_model=User) # response_model约定了响应的数据格式, 返回值不是该类型会报错
async def add_article(req: User, session: AsyncSession = Depends(get_session)):
    async with session.begin(): # 1. 开启显式数据库事务上下文
        # 利用session执行数据库CRUD操作
        user = User(username=req.username, email=req.email, password=req.password) # 通过模型创建对象
        session.add(user)       # 2. 将新用户对象添加到会话中, 以事务形式
    return user                 # 3. 事务已自动提交，返回用户对象

# 删除, 通过delete方法删除传入的数据
from sqlalchemy import delete
@app.post('/article/add', response_model=User) # response_model约定了响应的数据格式, 返回值不是该类型会报错
async def delete_article(req: User, session: AsyncSessionFactory = Depends(get_session)):
    async with session.begin():
        await session.execute(delete(User).where(User.username == req.username))
    return "111"

# 查找
from sqlalchemy import select
## 查找一条数据
@app.get('/select/{user_id}', response_model=UserRespSchema)
async def select_user_by_id(user_id: int, session: AsyncSession = Depends(get_session)):
    async with session.begin():
        # 要查找User.id, User.email, User.username, 条件是User.id == user_id
        query = await session.execute(select(User.id, User.email, User.username).where(User.id == user_id))
        result = query.scalar() # 返回一条数据
        return result

## 查找多条数据
@app.get('/select', response_model=List[UserRespSchema])
async def select_user(session: AsyncSession = Depends(get_session), q: str | None = None):
    async with session.begin():
        stmt = select(User.id, User.username, User.email)\
            .where(or_(User.email.contains(q), User.username.contains(q)))\
            .limit(2).offset(0).order_by(User.id.desc())
        query = await session.execute(stmt)
        result = query.scalars() # 返回多条数据(加s表示复数形式)
        return result

# 修改数据
## 方式一, 先select再修改
## 方式二, 直接修改
from sqlalchemy import update
@app.put('/user/update/{user_id}')
async def update_user(request: Request, user_id: int, user_data: UserCreateReq):
    session = request.state.session
    async with session.begin():
        # 方式一
        # user = await session.execute(select(User.id, User.email, User.username).where(User.id == user_id))
        # user.id = 123

        # 方式二
        # 将username和email改为传入值
        await session.execute(update(User).where(User.id == user_id).values(username=user_data.username, email=user_data.email))
    return {"message": "数据修改成功！"}

# 处理cookie

# 是服务器通过响应告诉客户端「请保存这个 Cookie」
@app.get("/cookie/")
async def set_cookie(response: Response):
    response.set_cookie(key="my_cookie", value="the_value")

# 从请求中获取 Cookies：FastAPI 会自动将请求头中的 “Cookie” 字段解析为字典，并将其作为 Request 对象的 .cookies 属性提供。你可以在路径操作函数中访问此属性来读取请求中的 Cookies。
@app.get("/read-cookie/")
async def read_cookie(request: Request):
    my_cookie = request.cookies.get("my_cookie")
    # doing()...


"""
yield 
用来暂停函数并交出一个值，之后还可以从暂停处继续跑。这种函数叫生成器。
def gen():
    print("1. 开始")
    yield 10          # 把 10 交出去，函数在这里暂停
    print("2. 继续")  # 下次再驱动生成器时才会执行

g = gen()
print(next(g))  # 打印「1. 开始」，得到 10
print(next(g))  # 打印「2. 继续」，然后结束
'''