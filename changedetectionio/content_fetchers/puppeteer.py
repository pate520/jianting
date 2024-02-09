import json
import os
import time
from urllib.parse import urlparse

from loguru import logger
from changedetectionio.content_fetchers.base import Fetcher
from changedetectionio.content_fetchers.exceptions import PageUnloadable, Non200ErrorCodeReceived, EmptyReply, ScreenshotUnavailable


class fetcher(Fetcher):
    fetcher_description = "Puppeteer/direct {}/Javascript".format(
        os.getenv("PLAYWRIGHT_BROWSER_TYPE", 'chromium').capitalize()
    )
    if os.getenv("PLAYWRIGHT_DRIVER_URL"):
        fetcher_description += " via '{}'".format(os.getenv("PLAYWRIGHT_DRIVER_URL"))

    browser_type = ''
    command_executor = ''

    # Configs for Proxy setup
    # In the ENV vars, is prefixed with "playwright_proxy_", so it is for example "playwright_proxy_server"
    playwright_proxy_settings_mappings = ['bypass', 'server', 'username', 'password']

    proxy = None
    loop = None

    def __init__(self, proxy_override=None, custom_browser_connection_url=None):
        super().__init__()

        if custom_browser_connection_url:
            self.browser_connection_is_custom = True
            self.browser_connection_url = custom_browser_connection_url
        else:
            # Fallback to fetching from system
            # .strip('"') is going to save someone a lot of time when they accidently wrap the env value
            self.browser_connection_url = os.getenv("PLAYWRIGHT_DRIVER_URL", 'ws://playwright-chrome:3000').strip('"')

        # If any proxy settings are enabled, then we should setup the proxy object
        proxy_args = {}
        for k in self.playwright_proxy_settings_mappings:
            v = os.getenv('playwright_proxy_' + k, False)
            if v:
                proxy_args[k] = v.strip('"')

        if proxy_args:
            self.proxy = proxy_args

        # allow per-watch proxy selection override
        if proxy_override:
            self.proxy = {'server': proxy_override}

        if self.proxy:
            # Playwright needs separate username and password values
            parsed = urlparse(self.proxy.get('server'))
            if parsed.username:
                self.proxy['username'] = parsed.username
                self.proxy['password'] = parsed.password

    # def screenshot_step(self, step_n=''):
    #     screenshot = self.page.screenshot(type='jpeg', full_page=True, quality=85)
    #
    #     if self.browser_steps_screenshot_path is not None:
    #         destination = os.path.join(self.browser_steps_screenshot_path, 'step_{}.jpeg'.format(step_n))
    #         logger.debug(f"Saving step screenshot to {destination}")
    #         with open(destination, 'wb') as f:
    #             f.write(screenshot)
    #
    # def save_step_html(self, step_n):
    #     content = self.page.content()
    #     destination = os.path.join(self.browser_steps_screenshot_path, 'step_{}.html'.format(step_n))
    #     logger.debug(f"Saving step HTML to {destination}")
    #     with open(destination, 'w') as f:
    #         f.write(content)

    def run(self,
            url,
            timeout,
            request_headers,
            request_body,
            request_method,
            ignore_status_codes=False,
            current_include_filters=None,
            is_binary=False):
        import asyncio
        async def fetch_page(url,
                             timeout,
                             request_headers,
                             request_body,
                             request_method,
                             ignore_status_codes,
                             current_include_filters,
                             is_binary
                             ):
            import pyppeteer
            from changedetectionio.content_fetchers import visualselector_xpath_selectors
            self.delete_browser_steps_screenshots()

            browser = await pyppeteer.launcher.connect(
                browserWSEndpoint=self.browser_connection_url,
                width=1024,
                height=768
            )

            self.page = await browser.newPage()
            await self.page.setBypassCSP(True)
            if request_headers:
                await self.page.setExtraHTTPHeaders(request_headers)
                # @todo check user-agent worked

            # SOCKS5 with authentication is not supported (yet)
            # https://github.com/microsoft/playwright/issues/10567
            self.page.setDefaultNavigationTimeout(0)

            # @todo proxy auth
            # if proxy_username:
            #     # Setting Proxy-Authentication header is deprecated, and doing so can trigger header change errors from Puppeteer
            #     # https://github.com/puppeteer/puppeteer/issues/676 ?
            #     # https://help.brightdata.com/hc/en-us/articles/12632549957649-Proxy-Manager-How-to-Guides#h_01HAKWR4Q0AFS8RZTNYWRDFJC2
            #     # https://cri.dev/posts/2020-03-30-How-to-solve-Puppeteer-Chrome-Error-ERR_INVALID_ARGUMENT/
            #     await page.authenticate({
            #         'username': proxy_username,
            #         'password': proxy_password
            #     })

            # Re-use as much code from browser steps as possible so its the same
            from changedetectionio.blueprint.browser_steps.browser_steps import steppable_browser_interface
            browsersteps_interface = steppable_browser_interface()
            browsersteps_interface.page = self.page

            response = await self.page.goto(url, {"waitUntil": "load"})
            self.headers = response.headers

            if response is None:
                await self.page.close()
                await browser.close()
                logger.warning("Content Fetcher > Response object was none")
                raise EmptyReply(url=url, status_code=None)

            try:
                if self.webdriver_js_execute_code is not None and len(self.webdriver_js_execute_code):
                    await self.page.evaluate(self.webdriver_js_execute_code)
            except Exception as e:
                logger.warning("Got exception when running evaluate on custom JS code")
                logger.error(str(e))
                await self.page.close()
                await browser.close()
                # This can be ok, we will try to grab what we could retrieve
                raise PageUnloadable(url=url, status_code=None, message=str(e))

            extra_wait = int(os.getenv("WEBDRIVER_DELAY_BEFORE_CONTENT_READY", 5)) + self.render_extract_delay
            await asyncio.sleep(1 + extra_wait)

            try:
                self.status_code = response.status
            except Exception as e:
                # https://github.com/dgtlmoon/changedetection.io/discussions/2122#discussioncomment-8241962
                logger.critical(f"Response from the browser/Playwright did not have a status_code! Response follows.")
                logger.critical(response)
                await self.page.close()
                await browser.close()
                raise PageUnloadable(url=url, status_code=None, message=str(e))

            if self.status_code != 200 and not ignore_status_codes:
                screenshot = self.page.screenshot(type='jpeg', full_page=True,
                                                  quality=int(os.getenv("SCREENSHOT_QUALITY", 72)))

                raise Non200ErrorCodeReceived(url=url, status_code=self.status_code, screenshot=screenshot)
            content = await self.page.content()
            if len(content.strip()) == 0:
                await self.page.close()
                await browser.close()
                logger.error("Content Fetcher > Content was empty")
                raise EmptyReply(url=url, status_code=response.status)

            # Run Browser Steps here
            if self.browser_steps_get_valid_steps():
                self.iterate_browser_steps()

            await asyncio.sleep(1 + extra_wait)

            # So we can find an element on the page where its selector was entered manually (maybe not xPath etc)
            # Setup the xPath/VisualSelector scraper
            if current_include_filters is not None:
                js = json.dumps(current_include_filters)
                await self.page.evaluate(f"var include_filters={js}")
            else:
                await self.page.evaluate(f"var include_filters=''")

            self.xpath_data = await self.page.evaluate(
                "async () => {" + self.xpath_element_js.replace('%ELEMENTS%', visualselector_xpath_selectors) + "}")
            self.instock_data = await self.page.evaluate("async () => {" + self.instock_data_js + "}")

            self.content = await self.page.content()
            # Bug 3 in Playwright screenshot handling
            # Some bug where it gives the wrong screenshot size, but making a request with the clip set first seems to solve it
            # JPEG is better here because the screenshots can be very very large

            # Screenshots also travel via the ws:// (websocket) meaning that the binary data is base64 encoded
            # which will significantly increase the IO size between the server and client, it's recommended to use the lowest
            # acceptable screenshot quality here
            try:
                self.screenshot = await self.page.screenshot({"encoding": "binary",
                                                              "fullPage": True,
                                                              "quality": int(os.getenv("SCREENSHOT_QUALITY", 72)), "type": 'jpeg'})
            except Exception as e:
                logger.error("Error fetching screenshot")
                # // May fail on very large pages with 'WARNING: tile memory limits exceeded, some content may not draw'
                # // @ todo after text extract, we can place some overlay text with red background to say 'croppped'
                logger.error('ERROR: content-fetcher page was maybe too large for a screenshot, reverting to viewport only screenshot')
                try:
                    self.screenshot = await self.page.screenshot({"encoding": "binary",
                                                                  "quality": int(os.getenv("SCREENSHOT_QUALITY", 72)),
                                                                  "fullPage": False,
                                                                  "type": 'jpeg'})
                except Exception as e:
                    logger.error('ERROR: Failed to get viewport-only reduced screenshot :(')
                    pass
            finally:
                await self.page.close()
                await browser.close()

        async def main(**kwargs):
            kwargs = locals()
            kwargs.pop("self", None)  # Remove 'self' if this is inside a class method
            task1 = asyncio.create_task(fetch_page(url=url,
                                                   timeout=timeout,
                                                   request_headers=request_headers,
                                                   request_body=request_body,
                                                   request_method=request_method,
                                                   ignore_status_codes=ignore_status_codes,
                                                   current_include_filters=current_include_filters,
                                                   is_binary=is_binary))
            await task1

        # launch as asyncio processor
        asyncio.run(main(
            url=url,
            timeout=timeout,
            request_headers=request_headers,
            request_body=request_body,
            request_method=request_method,
            ignore_status_codes=ignore_status_codes,
            current_include_filters=current_include_filters,
            is_binary=is_binary,
        ))
