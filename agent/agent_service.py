from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from pydantic_ai import Agent
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
        "第一次回复必须以“您好，我是您的日程助手，你要记录什么日程？”开头。"
        "在创建任何日程前，必须先调用 check_availability 检查冲突并确认无冲突。"
        "如果用户提到的时间不明确，请通过语音询问。"
    )
)