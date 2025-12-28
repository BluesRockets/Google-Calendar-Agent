from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Optional

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

@dataclass
class CalendarDeps:
    page: Optional[Page] = None
    browser_context: Optional[BrowserContext] = None
    playwright: Optional[Playwright] = None
    timezone: str = "America/Toronto"
    user_id: str = "default"
    user_data_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent / ".calendar_profile")

# define Agent
calendar_agent = Agent(
    'openai:gpt-4o',
    deps_type=CalendarDeps,
    system_prompt=(
        "你是一个Google日历助手。"
        "只能使用提供的工具操作日历，不要试图猜测结果。"
        "如果用户提到的时间不明确，请通过语音询问。"
    )
)

# define agent parameters
class EventDetails(BaseModel):
    title: str = Field(description="日程的标题")
    date_str: str = Field(description="日期，格式必须为 YYYY-MM-DD")
    start_time: str = Field(description="开始时间，格式 HH:mm (24小时制)")
    end_time: str = Field(description="结束时间，格式 HH:mm (24小时制)")


