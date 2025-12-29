from datetime import datetime
import time
from typing import Optional, Sequence, Tuple
from zoneinfo import ZoneInfo
import utils
from pydantic_ai import RunContext
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from agent_service import calendar_agent, CalendarDeps


# tool 1: get today's date
@calendar_agent.tool
async def get_today_date(ctx: RunContext[CalendarDeps]) -> str:
    """获取今天日期，格式为 YYYY-MM-DD。"""
    now = datetime.now(ZoneInfo(ctx.deps.timezone))
    return now.strftime("%Y-%m-%d")

# ensure calendar page is opened and ready
async def _ensure_calendar_page(ctx: RunContext[CalendarDeps], target_url: Optional[str] = None) -> Page:
    deps = ctx.deps
    # 检查现有页面和浏览器上下文状态
    if deps.page is not None and deps.page.is_closed():
        deps.page = None
    if deps.browser_context is not None:
        try:
            _ = deps.browser_context.pages
        except Exception:
            deps.browser_context = None
    # 页面关闭时重新创建
    if deps.page is None and deps.browser_context is not None:
        deps.page = await deps.browser_context.new_page()
    if deps.page is None:
        # 根据用户id找对应的profile不存在时创建
        profile_dir = deps.user_data_dir / deps.user_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        lock_file = profile_dir / "SingletonLock"
        if lock_file.exists():
            raise RuntimeError(
                "浏览器配置目录正在被占用，请先关闭已打开的 Chrome/Playwright 实例后重试。"
            )
        playwright = await async_playwright().start()
        deps.playwright = playwright
        try:
            # 启动持久化浏览器
            deps.browser_context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
        except Exception as exc:
            raise RuntimeError(
                "启动浏览器失败，可能是配置目录被占用。请关闭已有 Chrome 实例后重试。"
            ) from exc
        if deps.browser_context.pages:
            deps.page = deps.browser_context.pages[0]
        else:
            deps.page = await deps.browser_context.new_page()

    if target_url:
        await deps.page.goto(target_url, wait_until="domcontentloaded")
    else:
        if "calendar.google.com/calendar" not in deps.page.url:
            await deps.page.goto("https://calendar.google.com", wait_until="domcontentloaded")
    await _wait_for_calendar_ready(deps.page)
    return deps.page

# wait for user to complete login
async def _wait_for_calendar_ready(page: Page, timeout_seconds: int = 300) -> None:
    start = time.monotonic()
    while True:
        if "accounts.google.com" in page.url:
            await page.wait_for_timeout(1000)
        else:
            try:
                await page.wait_for_selector('div[role="main"]', timeout=1000)
                return
            except Exception:
                await page.wait_for_timeout(500)

        if time.monotonic() - start > timeout_seconds:
            raise TimeoutError("等待登录超时，请完成登录后重试。")

async def _fill_first(page: Page, selectors: Sequence[str], value: str) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(timeout=1500)
            await locator.fill(value)
            return True
        except Exception:
            continue
    return False

async def _click_first(page: Page, selectors: Sequence[str]) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(timeout=1500)
            await locator.click()
            return True
        except Exception:
            continue
    return False


async def _has_conflict(page: Page, date_str: str, start_time: str, end_time: str) -> Optional[bool]:
    target_url = f"https://calendar.google.com/calendar/u/0/r/day/{date_str.replace('-', '/')}"
    if target_url not in page.url:
        await page.goto(target_url)
    await page.wait_for_selector('div[role="main"]', timeout=15000)

    start_minutes = utils.parse_time_to_minutes(start_time)
    end_minutes = utils.parse_time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None:
        return None
    if end_minutes <= start_minutes:
        return None

    # find existing events
    event_locators = page.locator('[role="gridcell"] [data-eventid], [data-eventid][role="button"], [data-eventid][role="gridcell"]')
    count = await event_locators.count()
    for idx in range(count):
        locator = event_locators.nth(idx)
        # get event detail
        label = await locator.get_attribute("aria-label")
        text = await locator.text_content()
        combined = " ".join(part for part in [label, text] if part)
        if not combined:
            continue
        range_minutes = utils.extract_time_range(combined)
        if not range_minutes:
            continue
        print(f"{start_minutes}, {end_minutes}, text={text}, range={range_minutes}")
        # check conflict
        event_start, event_end = range_minutes
        if start_minutes < event_end and end_minutes > event_start:
            return True
    return False

# tool 2: check schedule conflict 
@calendar_agent.tool
async def check_availability(ctx: RunContext[CalendarDeps], date_str: str, start_time: str, end_time: str) -> str:
    try:
        page = await _ensure_calendar_page(
            ctx,
            target_url=f"https://calendar.google.com/calendar/u/0/r/day/{date_str.replace('-', '/')}",
        )
    except TimeoutError as exc:
        return str(exc)
    
    # check conflict 
    has_conflict = await _has_conflict(page, date_str, start_time, end_time)
    if has_conflict is None:
        return "无法确认该时段是否有冲突，请检查时间格式或日历页面状态。"
    print(f"Checking {date_str} {start_time}-{end_time}")
    return "该时段已有安排" if has_conflict else "该时段空闲"


# creat event parameters
class EventDetails(BaseModel):
    title: str = Field(description="日程的标题")
    date_str: str = Field(description="日期，格式必须为 YYYY-MM-DD")
    start_time: str = Field(description="开始时间，格式 HH:mm (24小时制)")
    end_time: str = Field(description="结束时间，格式 HH:mm (24小时制)")

# tool 3: create a new event
@calendar_agent.tool
async def create_event(ctx: RunContext[CalendarDeps], details: EventDetails) -> str:
    print(f"Creating event: {details}")
    try:
        page = await _ensure_calendar_page(
            ctx,
            target_url=f"https://calendar.google.com/calendar/u/0/r/day/{details.date_str.replace('-', '/')}",
        )
    except TimeoutError as exc:
        return str(exc)
    await page.wait_for_selector('div[role="main"]', timeout=15000)
    await page.wait_for_timeout(800)
    # Use keyboard shortcut to open the quick event dialog.
    await page.keyboard.press("c")


    title_filled = await _fill_first(
        page,
        [
            'input[aria-label="Add title"]',
            'input[aria-label="添加标题"]',
            'input[aria-label="标题"]',
            'input[placeholder="Add title"]',
        ],
        details.title,
    )
    if not title_filled:
        return "未找到标题输入框，请确认日历页面已加载。"

    await _fill_first(
        page,
        [
            'input[aria-label="Start date"]',
            'input[aria-label="开始日期"]',
            'input[aria-label="日期"]',
        ],
        details.date_str,
    )
    await _fill_first(
        page,
        [
            'input[aria-label="Start time"]',
            'input[aria-label="开始时间"]',
            'input[aria-label="时间"]',
        ],
        details.start_time,
    )
    await _fill_first(
        page,
        [
            'input[aria-label="End date"]',
            'input[aria-label="结束日期"]',
        ],
        details.date_str,
    )
    await _fill_first(
        page,
        [
            'input[aria-label="End time"]',
            'input[aria-label="结束时间"]',
        ],
        details.end_time,
    )

    saved = await _click_first(
        page,
        [
            'button:has-text("Save")',
            'button:has-text("保存")',
            'button:has-text("Save event")',
        ],
    )
    if not saved:
        return "未找到保存按钮，请检查是否打开了创建日程弹窗。"

    return f"成功创建日程：{details.title}，时间：{details.date_str} {details.start_time}-{details.end_time}"
