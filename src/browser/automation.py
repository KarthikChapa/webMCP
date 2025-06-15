import asyncio
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
import os
import time

logger = logging.getLogger(__name__)

class BrowserAutomation:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        logger.info("Starting Playwright engine...")
        self.playwright = await async_playwright().start()
        logger.info("Playwright engine started successfully")
        
        logger.info(f"Launching browser with headless={self.headless}...")
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        logger.info("Browser launched successfully")
        
        logger.info("Creating browser context...")
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        logger.info("Browser context created successfully")
        
        logger.info("Creating new page...")
        self.page = await self.context.new_page()
        
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(60000)
        
        logger.info("Browser initialization complete")

    async def handle_consent_popup(self):
        logger.info("Checking for consent popups with quick timeout...")
        
        consent_selectors = [
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
            'button:has-text("I Accept")',
            'button:has-text("OK")',
            'button:has-text("Got it")',
            'button[id*="accept"]',
            'button[class*="accept"]',
            '#L2AGLb', 
            'button:has-text("Reject")',
            'button:has-text("Decline")',
        ]
        
        found_popup = False
        try:
            for selector in consent_selectors:
                try:
                    element = self.page.locator(selector).first
                    await element.wait_for(state="visible", timeout=2000)
                    await element.click()
                    logger.info(f"Clicked consent popup: {selector}")
                    found_popup = True
                    break
                except PlaywrightTimeoutError:
                    continue
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {str(e)}")
                    continue
            
            if not found_popup:
                logger.info("No consent popups detected or none were clickable.")
            
            if found_popup:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.warning(f"Error during consent popup handling: {str(e)}")

    async def close(self):
        logger.info("Closing browser resources...")
        
        try:
            if self.page:
                await self.page.close()
        except Exception as e:
            logger.warning(f"Error closing page (might be already closed): {e}")
        
        try:
            if self.context:
                await self.context.close()
        except Exception as e:
            logger.warning(f"Error closing context (might be already closed or closing): {e}")
        
        try:
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logger.warning(f"Error closing browser (might be already closed): {e}")
        
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error stopping playwright (might be already stopped): {e}")
        
        logger.info("Browser resources closed.")

    async def navigate(self, url: str, wait_until: str = 'domcontentloaded'):
        try:
            logger.info(f"Navigating to {url} (wait_until='{wait_until}')...")
            response = await self.page.goto(url, wait_until=wait_until, timeout=30000)
            
            if response:
                status = response.status
                logger.info(f"Navigation to {url} completed with status: {status}")
            else:
                logger.warning(f"Navigation to {url} completed but no response object")
                status = 200
            
            await self.handle_consent_popup()
            
            try:
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                logger.info("Network became idle after navigation and consent handling.")
            except PlaywrightTimeoutError:
                logger.info("Network didn't become idle within timeout, but continuing...")
            
            return {
                "status": "success",
                "message": "Navigation successful",
                "url": self.page.url,
                "http_status": status
            }
        
        except PlaywrightTimeoutError as e:
            logger.error(f"Navigation timeout to {url}: {str(e)}")
            return {"status": "error", "message": f"Navigation timeout: {str(e)}"}
        except Exception as e:
            logger.error(f"Navigation error to {url}: {str(e)}")
            return {"status": "error", "message": f"Navigation failed: {str(e)}"}

    async def click_element(self, selector: str):
        try:
            logger.info(f"Attempting to click element with selector: {selector}")
            element = self.page.locator(selector).first
            await element.wait_for(state="visible", timeout=10000)
            await element.click()
            logger.info(f"Successfully clicked element: {selector}")
            return {"status": "success", "message": f"Clicked element '{selector}'"}
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for element to be visible: {selector}")
            return {"status": "error", "message": f"Timeout waiting for element '{selector}' to be visible"}
        except Exception as e:
            logger.error(f"Error clicking element {selector}: {str(e)}")
            return {"status": "error", "message": f"Failed to click element '{selector}': {str(e)}"}

    async def type_into_element(self, selector: str, text: str):
        try:
            logger.info(f"Attempting to type '{text}' into element with selector: {selector}")
            element = self.page.locator(selector).first
            await element.wait_for(state="visible", timeout=10000)
            await element.clear()
            await element.fill(text)
            logger.info(f"Typed '{text}' into element: {selector}")
            return {"status": "success", "message": f"Typed '{text}' into element '{selector}'."}
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for element to be visible: {selector}")
            return {"status": "error", "message": f"Timeout waiting for element '{selector}' to be visible"}
        except Exception as e:
            logger.error(f"Error typing into element {selector}: {str(e)}")
            return {"status": "error", "message": f"Failed to type into element '{selector}': {str(e)}"}

    async def press_key(self, key: str, selector: str = None):
        try:
            if selector:
                logger.info(f"Pressing key '{key}' on element with selector: {selector}")
                element = self.page.locator(selector).first
                await element.wait_for(state="visible", timeout=10000)
                await element.press(key)
                logger.info(f"Pressed key '{key}' on element: {selector}")
            else:
                logger.info(f"Pressing key '{key}' on page")
                await self.page.keyboard.press(key)
                logger.info(f"Pressed key '{key}' on page")
            
            return {"status": "success", "message": f"Pressed key '{key}'" + (f" on element '{selector}'" if selector else "")}
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for element: {selector}")
            return {"status": "error", "message": f"Timeout waiting for element '{selector}'"}
        except Exception as e:
            logger.error(f"Error pressing key {key}: {str(e)}")
            return {"status": "error", "message": f"Failed to press key '{key}': {str(e)}"}

    async def wait_for_element(self, selector: str, timeout_ms: int = 10000, state: str = "visible"):
        try:
            logger.info(f"Waiting for element '{selector}' to be {state} (timeout: {timeout_ms}ms)")
            element = self.page.locator(selector).first
            await element.wait_for(state=state, timeout=timeout_ms)
            logger.info(f"Element '{selector}' is now {state}")
            return {"status": "success", "message": f"Element '{selector}' is {state}"}
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for element '{selector}' to be {state}")
            return {"status": "error", "message": f"Timeout waiting for element '{selector}' to be {state}"}
        except Exception as e:
            logger.error(f"Error waiting for element {selector}: {str(e)}")
            return {"status": "error", "message": f"Failed to wait for element '{selector}': {str(e)}"}

    async def get_page_text_content(self, selector: str = None):
        try:
            if selector:
                logger.info(f"Attempting to get text content from selector: {selector}")
                element = self.page.locator(selector).first
                await element.wait_for(state="visible", timeout=10000)
                text_content = await element.text_content()
            else:
                logger.info("Getting text content from entire page")
                text_content = await self.page.text_content('body')
            
            if text_content:
                logger.info(f"Retrieved text content: {len(text_content)} characters")
                return {
                    "status": "success",
                    "result": {"text_content": text_content.strip()}
                }
            else:
                logger.warning("No text content found")
                return {"status": "error", "message": "No text content found"}
                
        except PlaywrightTimeoutError:
            logger.error(f"Timeout getting text content from: {selector if selector else 'page'}")
            return {"status": "error", "message": f"Timeout getting text content from: {selector if selector else 'page'}"}
        except Exception as e:
            logger.error(f"Error getting text content: {str(e)}")
            return {"status": "error", "message": f"Failed to get text content: {str(e)}"}

    async def get_element_attribute(self, selector: str, attribute: str):
        try:
            logger.info(f"Getting attribute '{attribute}' from element: {selector}")
            element = self.page.locator(selector).first
            await element.wait_for(state="visible", timeout=10000)
            
            if attribute.lower() == "innertext":
                value = await element.text_content()
            else:
                value = await element.get_attribute(attribute)
            
            if value is not None:
                logger.info(f"Retrieved attribute '{attribute}': {value[:100]}...")
                return {
                    "status": "success",
                    "result": {attribute: value}
                }
            else:
                logger.warning(f"Attribute '{attribute}' not found on element: {selector}")
                return {"status": "error", "message": f"Attribute '{attribute}' not found"}
                
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for element: {selector}")
            return {"status": "error", "message": f"Timeout waiting for element: {selector}"}
        except Exception as e:
            logger.error(f"Error getting attribute: {str(e)}")
            return {"status": "error", "message": f"Failed to get attribute: {str(e)}"}

    async def take_screenshot(self, filename: str = None, full_page: bool = False):
        try:
            if not filename:
                timestamp = int(time.time())
                filename = f"screenshot_{timestamp}.png"
            else:
                if not filename.lower().endswith('.png'):
                    filename_without_ext = os.path.splitext(filename)[0]
                    filename = f"{filename_without_ext}.png"
            
            screenshots_dir = "screenshots"
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
            
            filepath = os.path.join(screenshots_dir, filename)
            
            logger.info(f"Taking screenshot: {filepath} (full_page={full_page})")
            await self.page.screenshot(path=filepath, full_page=full_page)
            logger.info(f"Screenshot saved: {filepath}")
            
            return {
                "status": "success",
                "message": f"Screenshot saved to {filepath}",
                "filepath": filepath
            }
        except Exception as e:
            logger.error(f"Error taking screenshot: {str(e)}")
            return {"status": "error", "message": f"Failed to take screenshot: {str(e)}"}

    async def scroll_page(self, direction: str, pixels: int = 300):
        try:
            direction_map = {
                "up": (0, -pixels),
                "down": (0, pixels),
                "left": (-pixels, 0),
                "right": (pixels, 0)
            }
            
            if direction not in direction_map:
                return {"status": "error", "message": f"Invalid direction: {direction}"}
            
            dx, dy = direction_map[direction]
            logger.info(f"Scrolling {direction} by {pixels} pixels")
            await self.page.mouse.wheel(dx, dy)
            logger.info(f"Scrolled {direction} by {pixels} pixels")
            
            return {"status": "success", "message": f"Scrolled {direction} by {pixels} pixels"}
        except Exception as e:
            logger.error(f"Error scrolling: {str(e)}")
            return {"status": "error", "message": f"Failed to scroll: {str(e)}"}

    async def select_dropdown_option(self, selector: str, option_value: str):
        try:
            logger.info(f"Selecting option '{option_value}' from dropdown: {selector}")
            element = self.page.locator(selector).first
            await element.wait_for(state="visible", timeout=10000)
            await element.select_option(value=option_value)
            logger.info(f"Selected option '{option_value}' from dropdown: {selector}")
            return {"status": "success", "message": f"Selected option '{option_value}' from dropdown '{selector}'"}
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for dropdown: {selector}")
            return {"status": "error", "message": f"Timeout waiting for dropdown: {selector}"}
        except Exception as e:
            logger.error(f"Error selecting dropdown option: {str(e)}")
            return {"status": "error", "message": f"Failed to select dropdown option: {str(e)}"}

    async def check_checkbox(self, selector: str, checked: bool = True):
        try:
            logger.info(f"Setting checkbox '{selector}' to {checked}")
            element = self.page.locator(selector).first
            await element.wait_for(state="visible", timeout=10000)
            await element.set_checked(checked)
            logger.info(f"Set checkbox '{selector}' to {checked}")
            return {"status": "success", "message": f"Set checkbox '{selector}' to {checked}"}
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for checkbox: {selector}")
            return {"status": "error", "message": f"Timeout waiting for checkbox: {selector}"}
        except Exception as e:
            logger.error(f"Error setting checkbox: {str(e)}")
            return {"status": "error", "message": f"Failed to set checkbox: {str(e)}"}

    async def upload_file(self, selector: str, file_path: str):
        try:
            logger.info(f"Uploading file '{file_path}' to element: {selector}")
            element = self.page.locator(selector).first
            await element.wait_for(state="visible", timeout=10000)
            await element.set_input_files(file_path)
            logger.info(f"Uploaded file '{file_path}' to element: {selector}")
            return {"status": "success", "message": f"Uploaded file '{file_path}' to element '{selector}'"}
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for file input: {selector}")
            return {"status": "error", "message": f"Timeout waiting for file input: {selector}"}
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            return {"status": "error", "message": f"Failed to upload file: {str(e)}"}

    async def hover_element(self, selector: str):
        try:
            logger.info(f"Hovering over element: {selector}")
            element = self.page.locator(selector).first
            await element.wait_for(state="visible", timeout=10000)
            await element.hover()
            logger.info(f"Hovered over element: {selector}")
            return {"status": "success", "message": f"Hovered over element '{selector}'"}
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for element: {selector}")
            return {"status": "error", "message": f"Timeout waiting for element: {selector}"}
        except Exception as e:
            logger.error(f"Error hovering over element: {str(e)}")
            return {"status": "error", "message": f"Failed to hover over element: {str(e)}"}

    async def find_element_by_description(self, description: str):
        try:
            logger.info(f"Finding element by description: {description}")
            
            possible_selectors = [
                f"text={description}",
                f"[aria-label*='{description}']",
                f"[title*='{description}']",
                f"[placeholder*='{description}']"
            ]
            
            for selector in possible_selectors:
                try:
                    element = self.page.locator(selector).first
                    await element.wait_for(state="visible", timeout=2000)
                    logger.info(f"Found element by description using selector: {selector}")
                    return {
                        "status": "success",
                        "message": f"Found element by description: {description}",
                        "selector": selector
                    }
                except PlaywrightTimeoutError:
                    continue
            
            logger.warning(f"Element not found by description: {description}")
            return {"status": "error", "message": f"Element not found by description: {description}"}
            
        except Exception as e:
            logger.error(f"Error finding element by description: {str(e)}")
            return {"status": "error", "message": f"Failed to find element by description: {str(e)}"}