from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import (
    DateTime, select, String, or_, and_, not_,
    func, desc, distinct, between
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

# 1. 数据库配置
ASYNC_DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/fastapi_test?charset=utf8mb4"
engine = create_async_engine(ASYNC_DATABASE_URL, echo=True)

# 2. 模型定义
class Base(DeclarativeBase):
    created_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class Animals(Base):
    __tablename__ = "animals"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    age: Mapped[int] = mapped_column(nullable=False)
    species: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    owner: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

# 3. 生命周期
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

# 4. 依赖项
asyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession)
async def get_db():
    async with asyncSessionLocal() as session:
        yield session

# ========================= 5. 路由部分 (查询全集) =========================

# --- 基础分页查询 ---
# 访问地址示例: /animals?skip=0&limit=5
@app.get("/animals", summary="分页获取列表")
async def read_animals(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    stmt = select(Animals).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 主键详情查询 ---
# 访问地址示例: /animals/1
@app.get("/animals/{animal_id}", summary="按ID查询详情")
async def read_animal_by_id(animal_id: int, db: AsyncSession = Depends(get_db)):
    animal = await db.get(Animals, animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="动物不存在")
    return animal

# --- 模糊搜索 ---
# 访问地址示例: /animals/search/name?name=小
@app.get("/animals/search/name", summary="按名字模糊搜索")
async def search_by_name(name: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Animals).where(Animals.name.like(f"%{name}%"))
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 多字段关键词搜索 (OR) ---
# 访问地址示例: /animals/search/keyword?q=猫
@app.get("/animals/search/keyword", summary="名字或品种包含关键词")
async def search_by_keyword(q: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Animals).where(or_(Animals.name.contains(q), Animals.species.contains(q)))
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 范围查询 (BETWEEN) ---
# 访问地址示例: /animals/filter/age?min_age=1&max_age=5
@app.get("/animals/filter/age", summary="按年龄区间查询")
async def filter_by_age(min_age: int = 0, max_age: int = 100, db: AsyncSession = Depends(get_db)):
    stmt = select(Animals).where(between(Animals.age, min_age, max_age))
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 改进后的集合查询 (支持模糊匹配) ---
# 访问地址示例: /animals/filter/species?species_list=猫,狗
@app.get("/animals/filter/species", summary="多品种模糊筛选")
async def filter_by_multi_species(species_list: str, db: AsyncSession = Depends(get_db)):
    s_list = [s.strip() for s in species_list.split(",") if s.strip()]
    if not s_list:
        return []
    conditions = [Animals.species.like(f"%{s}%") for s in s_list]
    stmt = select(Animals).where(or_(*conditions))
    result = await db.execute(stmt)
    return result.scalars().all()

# ========================= 新增：比较判断类接口 =========================

# --- 大于/小于判断 ---
# 访问地址示例: /animals/compare/age?gt_age=5
@app.get("/animals/compare/age", summary="年龄大小比较查询")
async def compare_age(gt_age: Optional[int] = None, lt_age: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Animals)
    if gt_age is not None:
        stmt = stmt.where(Animals.age > gt_age)  # 大于
    if lt_age is not None:
        stmt = stmt.where(Animals.age < lt_age)  # 小于
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 不等于判断 ---
# 访问地址示例: /animals/compare/not-species?exclude=萨摩耶
@app.get("/animals/compare/not-species", summary="排除特定品种查询")
async def exclude_species(exclude: str, db: AsyncSession = Depends(get_db)):
    # SQL: WHERE species <> 'exclude'
    stmt = select(Animals).where(Animals.species != exclude)
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 空值判断 (IS NULL / IS NOT NULL) ---
# 访问地址示例: /animals/compare/description-status?is_null=true
@app.get("/animals/compare/description-status", summary="空值检查查询")
async def check_null_desc(is_null: bool = True, db: AsyncSession = Depends(get_db)):
    if is_null:
        # 查找描述为空的
        stmt = select(Animals).where(Animals.description.is_(None))
    else:
        # 查找描述不为空的
        stmt = select(Animals).where(Animals.description.is_not(None))
    result = await db.execute(stmt)
    return result.scalars().all()

# =====================================================================

# --- 排序查询 ---
# 访问地址示例: /animals/sort/age?reverse=true
@app.get("/animals/sort/age", summary="按年龄排序")
async def sort_animals(reverse: bool = False, db: AsyncSession = Depends(get_db)):
    stmt = select(Animals).order_by(desc(Animals.age) if reverse else Animals.age)
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 统计总数 (COUNT) ---
# 访问地址示例: /animals/stats/count
@app.get("/animals/stats/count", summary="统计总数")
async def get_total_count(db: AsyncSession = Depends(get_db)):
    stmt = select(func.count(Animals.id))
    result = await db.execute(stmt)
    return {"total": result.scalar()}

# --- 分组统计 (GROUP BY) ---
# 访问地址示例: /animals/stats/group-by-species
@app.get("/animals/stats/group-by-species", summary="按品种统计数量")
async def get_group_stats(db: AsyncSession = Depends(get_db)):
    stmt = select(Animals.species, func.count(Animals.id)).group_by(Animals.species)
    result = await db.execute(stmt)
    return [{"species": row[0], "count": row[1]} for row in result.all()]

# --- 聚合运算 (AVG/MAX) ---
# 访问地址示例: /animals/stats/age-info
@app.get("/animals/stats/age-info", summary="年龄统计信息")
async def get_age_info(db: AsyncSession = Depends(get_db)):
    stmt = select(func.avg(Animals.age), func.max(Animals.age))
    result = await db.execute(stmt)
    row = result.first()
    return {"avg_age": row[0], "max_age": row[1]}

# --- 去重查询 (DISTINCT) ---
# 访问地址示例: /animals/unique/owners
@app.get("/animals/unique/owners", summary="获取所有主人(去重)")
async def get_unique_owners(db: AsyncSession = Depends(get_db)):
    stmt = select(distinct(Animals.owner))
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 复杂逻辑组合 (AND/NOT) ---
# 访问地址示例: /animals/logic/active-older-cats
@app.get("/animals/logic/active-older-cats", summary="查询活跃且大于2岁的猫")
async def get_specific_cats(db: AsyncSession = Depends(get_db)):
    stmt = select(Animals).where(
        and_(Animals.species == "猫", Animals.age > 2, Animals.is_active == True)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

# --- 添加测试数据接口 ---
# 访问地址示例: POST -> /animals/add?name=旺财&species=狗&age=3&owner=张三
@app.post("/animals/add", summary="新增动物")
async def add_animal(name: str, species: str, age: int, owner: str, db: AsyncSession = Depends(get_db)):
    new_animal = Animals(name=name, species=species, age=age, owner=owner, description="测试数据")
    db.add(new_animal)
    await db.commit()
    await db.refresh(new_animal)
    return new_animal


# ... existing code ...

# --- 添加测试数据接口 ---
# 访问地址示例: POST -> /animals/add?name=旺财&species=狗&age=3&owner=张三
@app.post("/animals/add", summary="新增动物")
async def add_animal(name: str, species: str, age: int, owner: str, db: AsyncSession = Depends(get_db)):
    new_animal = Animals(name=name, species=species, age=age, owner=owner, description="测试数据")
    db.add(new_animal)
    await db.commit()
    await db.refresh(new_animal)
    return new_animal


# ========================= 6. 更新和删除接口 =========================

# --- 完整更新 (PUT) ---
# 访问地址示例: PUT -> /animals/update/1?name=咪咪&species=猫&age=2&owner=李四&description=可爱的猫咪&is_active=true
@app.put("/animals/update/{animal_id}", summary="完整更新动物信息")
async def update_animal(
        animal_id: int,
        name: str,
        species: str,
        age: int,
        owner: str,
        description: Optional[str] = None,
        is_active: bool = True,
        db: AsyncSession = Depends(get_db)
):
    animal = await db.get(Animals, animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="动物不存在")

    animal.name = name
    animal.species = species
    animal.age = age
    animal.owner = owner
    animal.description = description
    animal.is_active = is_active

    await db.commit()
    await db.refresh(animal)
    return animal


# --- 部分更新 (PATCH) ---
# 访问地址示例: PATCH -> /animals/partial-update/1?name=小花&age=3
@app.patch("/animals/partial-update/{animal_id}", summary="部分更新动物信息")
async def partial_update_animal(
        animal_id: int,
        name: Optional[str] = None,
        species: Optional[str] = None,
        age: Optional[int] = None,
        owner: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        db: AsyncSession = Depends(get_db)
):
    animal = await db.get(Animals, animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="动物不存在")

    if name is not None:
        animal.name = name
    if species is not None:
        animal.species = species
    if age is not None:
        animal.age = age
    if owner is not None:
        animal.owner = owner
    if description is not None:
        animal.description = description
    if is_active is not None:
        animal.is_active = is_active

    await db.commit()
    await db.refresh(animal)
    return animal


# --- 批量更新状态 ---
# 访问地址示例: PATCH -> /animals/batch-update-status?species=猫&is_active=false
@app.patch("/animals/batch-update-status", summary="批量更新动物状态")
async def batch_update_status(
        species: str,
        is_active: bool,
        db: AsyncSession = Depends(get_db)
):
    stmt = select(Animals).where(Animals.species == species)
    result = await db.execute(stmt)
    animals = result.scalars().all()

    if not animals:
        raise HTTPException(status_code=404, detail=f"未找到物种为 '{species}' 的动物")

    for animal in animals:
        animal.is_active = is_active

    await db.commit()
    return {"message": f"成功更新 {len(animals)} 条记录", "updated_count": len(animals)}


# --- 软删除 (标记为非活跃) ---
# 访问地址示例: DELETE -> /animals/soft-delete/1
@app.delete("/animals/soft-delete/{animal_id}", summary="软删除动物(标记为非活跃)")
async def soft_delete_animal(animal_id: int, db: AsyncSession = Depends(get_db)):
    animal = await db.get(Animals, animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="动物不存在")

    animal.is_active = False
    await db.commit()
    return {"message": "动物已标记为删除状态", "animal_id": animal_id}


# --- 物理删除 (从数据库彻底删除) ---
# 访问地址示例: DELETE -> /animals/hard-delete/1
@app.delete("/animals/hard-delete/{animal_id}", summary="物理删除动物(永久删除)")
async def hard_delete_animal(animal_id: int, db: AsyncSession = Depends(get_db)):
    animal = await db.get(Animals, animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="动物不存在")

    await db.delete(animal)
    await db.commit()
    return {"message": "动物已永久删除", "animal_id": animal_id}


# --- 批量删除 ---
# 访问地址示例: DELETE -> /animals/batch-delete?species=鸟
@app.delete("/animals/batch-delete", summary="批量删除动物")
async def batch_delete_animals(species: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Animals).where(Animals.species == species)
    result = await db.execute(stmt)
    animals = result.scalars().all()

    if not animals:
        raise HTTPException(status_code=404, detail=f"未找到物种为 '{species}' 的动物")

    deleted_count = len(animals)
    for animal in animals:
        await db.delete(animal)

    await db.commit()
    return {"message": f"成功删除 {deleted_count} 条记录", "deleted_count": deleted_count}


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8000)
