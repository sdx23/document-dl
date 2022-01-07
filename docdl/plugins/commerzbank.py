"""download documents from commerzbank.de"""

import time
import os
import itertools
import click
import watchdog
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import docdl
import docdl.util


class Commerzbank(docdl.SeleniumWebPortal):
    """download documents from commerzbank.de"""

    URL_LOGIN = "https://www.commerzbank.de/lp/login"
    URL_LOGOUT = "https://kunden.commerzbank.de/lp/logout"
    URL_POSTBOX = "https://kunden.commerzbank.de/banking/postbox"
    PHOTOTAN_TIMEOUT = 120
    SCROLL_PAGES = 5

    def login(self):
        # load login page
        self.webdriver.get(self.URL_LOGIN)
        # wait for username entry
        WebDriverWait(self.webdriver, self.TIMEOUT).until(
            lambda d:
                d.find_elements(
                    By.XPATH, "//input[@id='teilnehmer']"
                ) or
                d.find_elements(
                    By.XPATH, '//button[@id = "uc-btn-accept-banner"]'
                )
        )
        # wait for cookiebanner to load
        time.sleep(1)

        # cookiebanner?
        if cookiebutton := self.webdriver.find_elements(
            By.XPATH, '//button[@id = "uc-btn-accept-banner"]'
        ):
            cookiebutton[0].click()
        # wait for username entry
        WebDriverWait(self.webdriver, self.TIMEOUT).until(
            lambda d:
                d.find_elements(
                    By.XPATH, "//input[@id='teilnehmer']"
                )
        )

        # get username entry
        username = self.webdriver.find_element(
            By.XPATH, "//input[@id='teilnehmer']"
        )
        # password entry
        password = self.webdriver.find_element(
            By.XPATH, "//input[@id='pin']"
        )
        # enter credentials
        username.send_keys(self.login_id)
        password.send_keys(self.password)
        password.submit()
        # wrong password?
        if self.webdriver.find_elements(
            By.XPATH, "//div[contains(@class, 'type-error')]"
        ):
            # login failed
            return False
        # wait for page asking for photoTAN-Push
        WebDriverWait(self.webdriver, self.TIMEOUT).until(
            lambda d: "/lp/approval" in d.current_url
        )
        print("Confirm login via photoTAN-Push now... ", end="", flush=True)
        # save current url
        current_url = self.webdriver.current_url
        # wait for page to load
        WebDriverWait(self.webdriver, self.PHOTOTAN_TIMEOUT).until(
            EC.url_changes(current_url)
        )
        print("ok.")
        # wait for page loaded
        WebDriverWait(self.webdriver, self.TIMEOUT).until(
            lambda d: "landingpage" in d.current_url
        )
        # login successful?
        return "landingpage" in self.webdriver.current_url

    def logout(self):
        self.webdriver.get(self.URL_LOGOUT)

    def documents(self):
        # there is no "real" document id, so create one for this run
        for i, document in enumerate(itertools.chain(self._postbox())):
            # set an id
            document.attributes['id'] = i
            # return document
            yield document

    def _postbox(self):
        # load postbox
        self.webdriver.get(self.URL_POSTBOX)
        # wait for table
        postboxdiv = WebDriverWait(self.webdriver, self.TIMEOUT).until(
            EC.visibility_of_element_located((
                By.XPATH, "//div[@id='postbox-table']"
            ))
        )

        # find the rows and scroll down multiple times
        for _ in range(self.SCROLL_PAGES):
            rows = postboxdiv.find_elements(
                    By.XPATH,
                    './/div[@class="postbox-table-row-title "]/..')
            self.scroll_to_element(rows[-1])

        # find and iterate the rows
        rows = postboxdiv.find_elements(By.XPATH, './/div[@class="postbox-table-row-title "]/..')
        for row in rows:
            # read status
            unread = "read" not in row.find_element(By.XPATH, '..').get_attribute("class")
            # stupid way to "activate" the row so download button shows, but
            # we'll do this only at download later
            # row.click()
            # row.click()
            # download button, usually that'd be
            # download_element = row.find_element(
            #   By.XPATH, './/div[@class="action-item download-action-item"]')
            # but we'll need the row to click it...
            download_element = row
            # date
            date = row.find_element(
                        By.XPATH,
                        ".//div[@class='date-in-documents-row']"). \
                get_attribute("textContent").strip()
            # konto
            konto = row.find_element(
                        By.XPATH,
                        ".//div[@class='document-main-heading']"). \
                get_attribute("textContent").strip()
            # subject
            subject = row.find_element(
                        By.XPATH,
                        ".//div[@class='document-sub-heading']"). \
                get_attribute("textContent").strip()

            print(subject)

            yield docdl.Document(
               download_element=download_element,
               attributes={
                   'date': docdl.util.parse_date(date),
                   'category': 'bank-document',
                   'subject': subject,
                   'unread': unread,
                   'konto': konto
               })

    def download(self, document):
        """download a document"""
        if document.download_element:
            filename = self.download_with_selenium(document)
        else:
            raise RuntimeError(
                "can't download: document has no download_element"
            )
        return document.rename_after_download(filename)

    def download_with_selenium(self, document):
        """download a file using the selenium webdriver"""
        class DownloadFileCreatedHandler(
            watchdog.events.PatternMatchingEventHandler
        ):
            """
            directory watchdog to store filename of newly created file
            """
            filename = None

            def on_created(self, event):
                self.filename = os.path.basename(event.src_path)

        # scroll to download element
        self.scroll_to_element(document.download_element)

        # setup download directory watchdog
        # pylint: disable=C0103
        OBSERVER = watchdog.observers.Observer()
        # ignore temporary download files
        handler = DownloadFileCreatedHandler(ignore_patterns=['*.crdownload'])
        OBSERVER.schedule(handler, os.getcwd(), recursive=False)

        # click element twice to show buttons
        document.download_element.click()
        document.download_element.click()
        # finally click the download button
        document.download_element.find_element(
                By.XPATH,
                './/div[@class="action-item download-action-item"]'
            ).click()

        # wait for download completed
        OBSERVER.start()
        try:
            while not handler.filename:
                time.sleep(0.1)
        finally:
            OBSERVER.stop()
        OBSERVER.join()

        return handler.filename


@click.command()
@click.pass_context
def commerzbank(ctx):
    """commerzbank.de with photoTAN-Push (postbox)"""
    docdl.cli.run(ctx, Commerzbank)
