import uvicorn
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI()

# HTML 文件目录
html_dir = os.path.join(os.path.dirname(__file__), '../..', 'file')


@app.get("/")
async def read_root():
    """
    根路径 - 从文件读取 HTML 页面
    
    使用 HTMLResponse 返回外部 HTML 文件内容
    """
    file_path = os.path.join(html_dir, "index.html")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="HTML 页面文件不存在")

    # 读取 HTML 文件内容
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return HTMLResponse(content=content)


@app.get("/simple")
async def simple_html():
    """
    简单 HTML 页面 - 从文件读取
    
    如果文件不存在，返回简单的 HTML 字符串
    """
    file_path = os.path.join(html_dir, "simple.html")

    if not os.path.exists(file_path):
        # 文件不存在时，返回默认内容
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>简单 HTML 示例</title>
            </head>
            <body>
                <h1>这是一个简单的 HTML 页面</h1>
                <p>文件 simple.html 不存在，显示默认内容。</p>
                <a href="/">返回首页</a>
            </body>
            </html>
            """
        )

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return HTMLResponse(content=content)


@app.get("/dynamic")
async def dynamic_html(name: str = "访客"):
    """
    动态 HTML 页面 - 根据参数生成不同的内容
    
    参数:
        name: 用户名，默认值为"访客"
    """
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>欢迎页面</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f0f2f5;
                padding: 50px;
                text-align: center;
            }}
            .welcome {{
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                display: inline-block;
            }}
            h1 {{
                color: #4CAF50;
            }}
            .time {{
                color: #999;
                margin-top: 20px;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="welcome">
            <h1>👋 你好，{name}！</h1>
            <p>欢迎访问 FastAPI 动态 HTML 页面</p>
            <p class="time">当前时间：动态生成</p>
            <p><a href="/dynamic?name=你的姓名">点击这里修改用户名</a></p>
            <p><a href="/">返回首页</a></p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/info")
async def get_html_info():
    """
    获取 HTML 文件信息
    
    返回 HTML 文件的元数据信息
    """
    file_path = os.path.join(html_dir, "index.html")

    if not os.path.exists(file_path):
        return {"error": "HTML 文件不存在", "path": file_path}

    # 获取文件信息
    stat = os.stat(file_path)

    return {
        "file_name": os.path.basename(file_path),
        "file_path": os.path.abspath(file_path),
        "file_size": stat.st_size,  # 字节
        "file_size_readable": f"{stat.st_size / 1024:.2f} KB",
        "file_type": "text/html",
        "exists": True
    }


# 启动配置
if __name__ == "__main__":
    print(html_dir)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
