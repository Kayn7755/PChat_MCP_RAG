from __future__ import annotations

from enum import Enum

# agent的功能
class AgentState(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"
    # AgentState(str, Enum) 定义了Agent运行生命周期：
    # IDLE：初始/空闲状态，尚未开始执行
    # PLANNING：规划阶段（当前这版里预留，基本没实际切换）
    # THINKING：思考阶段（同样偏预留）
    # EXECUTING：执行工具阶段（偏预留）
    # FINISHED：任务完成，主循环退出
    # ERROR：执行异常，进入错误终态


# 给工具的类型
class ToolType(str, Enum):
    FIXED = "FIXED" # 固定工具，必须执行
    OPTIONAL = "OPTIONAL" # 可选工具，可执行可不执行
