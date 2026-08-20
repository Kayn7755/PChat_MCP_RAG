"""
FastAPI 文件响应示例

演示多种返回文件的方式：
1. FileResponse - 返回静态文件（图片、PDF、HTML等）
2. 流式文件下载
3. 动态生成文件内容
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse
import os
import uvicorn

app = FastAPI()

# 文件路径
file_dir = os.path.join(os.path.dirname(__file__), '../..', 'file')
photo_path = os.path.join(file_dir, 'photo.png')


@app.get("/")
async def read_root():
    """根路径 - 返回欢迎信息"""
    return {
        "message": "FastAPI 文件响应示例",
        "endpoints": {
            "/photo": "查看图片文件",
            "/download": "下载图片文件",
            "/html": "返回 HTML 文件",
            "/info": "查看文件信息"
        }
    }


@app.get("/photo")
async def get_photo():
    """
    返回图片文件 - 浏览器直接显示
    
    使用 FileResponse 返回静态文件
    FastAPI 会自动设置正确的 Content-Type（如 image/png）
    """
    if not os.path.exists(photo_path):
        return {"error": "文件不存在", "path": photo_path}

    return FileResponse(
        path=photo_path,
        media_type="image/png",
        filename="photo.png"
    )


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
