from __future__ import annotations


class Locator:
    @staticmethod
    def css(selector: str) -> str:
        return selector

    @staticmethod
    def xpath(selector: str) -> str:
        return f"xpath={selector}"

    @staticmethod
    def text(text: str) -> str:
        return f"text={text}"

    @staticmethod
    def role(role: str, name: str = "") -> str:
        if name:
            return f"role={role}[name='{name}']"
        return f"role={role}"

    @staticmethod
    def test_id(test_id: str) -> str:
        return f"[data-testid='{test_id}']"

    @staticmethod
    def button(text: str) -> str:
        return f"button:text('{text}')"

    @staticmethod
    def link(text: str) -> str:
        return f"a:text('{text}')"

    @staticmethod
    def input_(placeholder: str = "", label: str = "") -> str:
        if placeholder:
            return f"input:placeholder('{placeholder}')"
        if label:
            return f"input:label('{label}')"
        return "input"
