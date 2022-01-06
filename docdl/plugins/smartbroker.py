"""download documents from smartbroker.de"""

import click
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

import docdl
import docdl.util


class Smartbroker(docdl.SeleniumWebPortal):
    """download documents from smartbroker.de"""

    URL_LOGIN = "https://b2b.dab-bank.de/smartbroker/"
    URL_LOGOUT = "https://b2b.dab-bank.de/smartbroker/" \
        "Finanzuebersicht/securityLogoff.xhtml"
    URL_INBOX = "https://b2b.dab-bank.de/Tradingcenter/Postmanager/index.xhtml"

    def login(self):
        # load login page
        self.webdriver.get(self.URL_LOGIN)
        # wait for username entry
        WebDriverWait(self.webdriver, self.TIMEOUT).until(
            lambda d:
                d.find_elements(
                    By.XPATH, "//input[@id='zugangsnummer']"
                ) and
                d.find_elements(
                    By.XPATH, "//input[@id='identifier']"
                )
        )
        # get username entry
        username = self.webdriver.find_element(
            By.XPATH, "//input[@id='zugangsnummer']"
        )
        # password entry
        password = self.webdriver.find_element(
            By.XPATH, "//input[@id='identifier']"
        )
        # enter credentials
        username.send_keys(self.login_id)
        password.send_keys(self.password)
        password.submit()

        # wait for logout button
        WebDriverWait(self.webdriver, self.TIMEOUT).until(
            lambda d: d.current_url.endswith("Finanzuebersicht/")
        )

        # load the postbox here already as 2fa is only required at this point
        # load inbox
        self.webdriver.get(self.URL_INBOX)

        # tan requested - click button
        tanbutton = self.webdriver.find_element(
            By.XPATH, "//a[contains(text(), 'Zur TAN-Freigabe')]"
        )
        tanbutton.click()

        # get qr code
        WebDriverWait(self.webdriver, self.TIMEOUT).until(
            EC.visibility_of_element_located((
                By.XPATH,
                "//img[@id='strongLogin_confirm_def_auth_securePlusCodeImage']"
            )))

        # handle TAN
        if not (qrcode := self.webdriver.find_element(
                By.XPATH,
                "//img[@id='strongLogin_confirm_def_auth_securePlusCodeImage']"
        )):
            # debug("error confirming TAN")
            return False

        tan_entry = self.webdriver.find_element(
            By.XPATH, "//input[@id='strongLogin_confirm_da_secureplus']"
        )

        # enter TAN
        self.captcha(qrcode, tan_entry, "please enter SecurePlus-TAN: ")

        # confirm
        confirmbutton = self.webdriver.find_element(
            By.XPATH, "//*[@id='confirmStrongLogin_submitButton']"
        )
        confirmbutton.click()

        return "Postmanager" in self.webdriver.current_url

    def logout(self):
        self.webdriver.get(self.URL_LOGOUT)

    def documents(self):
        # load inbox
        self.webdriver.get(self.URL_INBOX)

        # Zeitraum wählen
        # find <select> for order filter
        orderfilter = WebDriverWait(self.webdriver, self.TIMEOUT).until(
            EC.presence_of_element_located((
                By.XPATH, "//*[@id='jq_queryInterval']"
            ))
        )
        # select longest time-frame
        orderfilter_select = Select(orderfilter)
        orderfilter_select.select_by_value("LAST_360")

        # search documents
        searchbutton = self.webdriver.find_element(
                By.LINK_TEXT, "Dokumente suchen")
        searchbutton.click()

        table = WebDriverWait(self.webdriver, self.TIMEOUT).until(
                EC.visibility_of_element_located((
                    By.XPATH, "//tr[@id]")))

        table = WebDriverWait(self.webdriver, self.TIMEOUT).until(
                EC.visibility_of_element_located((
                    By.XPATH, "//table[@id='tableInhalt']")))

        # remove session timer element, so it doesn't get in the way
        self.webdriver.execute_script(
            'document.getElementById("sessionTimer").style.display = "none";'
            'document.getElementById("sessionTimer").style.visibility'
            ' = "hidden";')

        # iterate rows (only rows with id are documents)
        for row in table.find_elements(By.XPATH, ".//tr[@id]"):
            idn = row.get_attribute("id")
            # read status in fifth column
            readtd = row.find_element(By.XPATH, ".//td[@class='cell-4']")
            unread = "Gelesen" not in \
                readtd.get_attribute("textContent").strip()
            # date in sixth column
            datetd = row.find_element(By.XPATH, ".//td[@class='cell-5']")
            date = datetd.get_attribute("textContent").strip()
            # konto in fourth column
            kontotd = row.find_element(By.XPATH, ".//td[@class='cell-3']")
            konto = kontotd.get_attribute("textContent").strip()
            # subject in third column
            subjecttd = row.find_element(By.XPATH, ".//td[@class='cell-2']")
            subject = subjecttd.get_attribute("textContent").strip()
            # download button
            download_button = row.find_element(
                By.XPATH, ".//a[@class='ic_pm_save_doc']"
            )
            # create document
            yield docdl.Document(
                download_element=download_button,
                attributes={
                    'id': idn,
                    'date': docdl.util.parse_date(date),
                    'category': 'report',
                    'subject': subject,
                    'unread': unread,
                    'konto': konto
                })


@click.command()
@click.pass_context
def smartbroker(ctx):
    """smartbroker.de"""
    docdl.cli.run(ctx, Smartbroker)
