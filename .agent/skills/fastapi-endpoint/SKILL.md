---
name: fastapi-endpoint
description: 当用户要求创建新 API 端点、路由或后端接口时使用。自动遵循项目 FastAPI + SQLAlchemy + Pydantic 规范生成端点代码。
---

# FastAPI 端点生成技能

## 目标
按照项目后端架构规范自动生成 FastAPI 端点，确保风格一致。

## 使用场景
- 用户说"创建一个 XX API"
- 用户说"新增一个 XX 接口"
- 需要为新功能添加后端支持

## 生成前置检查
1. 先读取 `docs/BACKEND_STRUCTURE.md` 确认架构约定
2. 确认端点属于哪个模块（core / plugin-baseline / plugin-report / plugin-correction）
3. 如涉及数据库变更，先提出 schema 变更方案并等待批准

## 生成规范

### 端点结构
```python
"""模块说明（中文）"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.xxx import XxxModel
from app.schemas.xxx import XxxCreate, XxxResponse

router = APIRouter(prefix="/api/v1/xxx", tags=["xxx"])


@router.get("/", response_model=list[XxxResponse])
async def list_xxx(
    session: AsyncSession = Depends(get_session),
) -> list[XxxResponse]:
    """获取 xxx 列表（中文 docstring）"""
    ...


@router.get("/{xxx_id}", response_model=XxxResponse)
async def get_xxx(
    xxx_id: int,
    session: AsyncSession = Depends(get_session),
) -> XxxResponse:
    """获取单个 xxx（中文 docstring）"""
    ...


@router.post("/", response_model=XxxResponse, status_code=status.HTTP_201_CREATED)
async def create_xxx(
    data: XxxCreate,
    session: AsyncSession = Depends(get_session),
) -> XxxResponse:
    """创建 xxx（中文 docstring）"""
    ...
```

### 命名规范
- 路由前缀：`/api/v1/{resource}`（RESTful 风格）
- 文件名：`{resource}.py`（放在对应模块的 `routers/` 目录下）
- Pydantic schema：`{Resource}Create`、`{Resource}Update`、`{Resource}Response`

### 数据验证
- 所有请求体必须用 **Pydantic** model 验证
- 所有响应必须用 `response_model` 声明
- 路径参数用类型注解约束

### 异步规范
- 所有数据库操作使用 **async/await**
- 使用 `AsyncSession`
- 使用 SQLAlchemy 2.0 风格的 `select()` 查询

### 错误处理
- 用 `HTTPException` 返回标准错误
- 404 用 `status.HTTP_404_NOT_FOUND`
- 400 用 `status.HTTP_400_BAD_REQUEST`

## 约束
- 禁止使用同步数据库操作
- 禁止使用原生 SQL 字符串拼接
- 禁止在路由中直接写复杂业务逻辑（应拆到 service 层）
- 新增路由后必须在主 app 中注册 router
