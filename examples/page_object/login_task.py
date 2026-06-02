from __future__ import annotations

from robocorp import browser
from robocorp.tasks import task

from ui_autoplat.assertions import expect_text_contains, expect_url_contains, expect_visible
from ui_autoplat.browser.page_objects import BasePage


class LoginPage(BasePage):
    url = (
        "data:text/html,%3Ctitle%3ELogin%3C/title%3E%3Ch1%3ELogin%3C/h1%3E"
        "%3Cinput%20id%3D%27username%27%3E%3Cinput%20id%3D%27password%27%20type%3D%27password%27%3E"
        "%3Cbutton%20id%3D%27submit%27%3ESign%20in%3C/button%3E"
        "%3Cscript%3Edocument.getElementById%28%27submit%27%29.onclick%3Dfunction%28%29%7B"
        "document.body.innerHTML%3D%27%3Ch1%3EDashboard%3C/h1%3E%3Cp%20id%3D%22status%22%3EWelcome%20admin%3C/p%3E%27%3B"
        "location.hash%3D%27dashboard%27%3B%7D%3C/script%3E"
    )

    username = "#username"
    password = "#password"
    submit = "#submit"

    def wait_for_ready(self) -> None:
        self.wait_visible(self.username)

    def login(self, username: str, password: str) -> "LoginPage":
        self.fill(self.username, username)
        self.fill(self.password, password)
        self.click(self.submit)
        return self


@task
def test_login_with_page_object():
    """PageObject example. Tags: example, page-object, P1"""
    page = LoginPage().goto()
    page.login("admin", "secret")

    expect_visible("h1", page=browser.page())
    expect_text_contains("#status", "Welcome admin", page=browser.page())
    expect_url_contains("dashboard", page=browser.page())
