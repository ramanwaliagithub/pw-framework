from __future__ import annotations

from src.pages.base.base_page import BasePage


class CartPage(BasePage):
    URL_PATH = "/cart.html"
    CART_ITEM = ".cart_item"
    ITEM_NAME = ".inventory_item_name"
    CHECKOUT_BUTTON = "#checkout"

    def item_names(self) -> list[str]:
        return [t.strip() for t in self.page.locator(self.ITEM_NAME).all_inner_texts()]

    def item_count(self) -> int:
        return self.page.locator(self.CART_ITEM).count()

    def proceed_to_checkout(self) -> "CheckoutInfoPage":
        self.click(self.CHECKOUT_BUTTON)
        return CheckoutInfoPage(self.page)


class CheckoutInfoPage(BasePage):
    FIRST_NAME = "#first-name"
    LAST_NAME = "#last-name"
    ZIP_CODE = "#postal-code"
    CONTINUE_BUTTON = "#continue"

    def fill_info(self, first_name: str, last_name: str, zip_code: str) -> "CheckoutOverviewPage":
        self.fill(self.FIRST_NAME, first_name)
        self.fill(self.LAST_NAME, last_name)
        self.fill(self.ZIP_CODE, zip_code)
        self.click(self.CONTINUE_BUTTON)
        return CheckoutOverviewPage(self.page)


class CheckoutOverviewPage(BasePage):
    FINISH_BUTTON = "#finish"
    TOTAL_LABEL = ".summary_total_label"

    def total_price(self) -> float:
        text = self.text_of(self.TOTAL_LABEL)  # e.g. "Total: $32.39"
        return float(text.split("$")[-1])

    def finish(self) -> "CheckoutCompletePage":
        self.click(self.FINISH_BUTTON)
        return CheckoutCompletePage(self.page)


class CheckoutCompletePage(BasePage):
    COMPLETE_HEADER = ".complete-header"

    def confirmation_text(self) -> str:
        return self.text_of(self.COMPLETE_HEADER)
