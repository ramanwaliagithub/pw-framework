from __future__ import annotations

from src.pages.base.base_page import BasePage
from src.pages.components.common_components import CartBadge, SortDropdown


class InventoryPage(BasePage):
    URL_PATH = "/inventory.html"

    SORT_DROPDOWN = "[data-test='product-sort-container']"
    CART_ICON = "#shopping_cart_container a"
    CART_BADGE = ".shopping_cart_badge"
    ITEM_NAME = ".inventory_item_name"
    ITEM_PRICE = ".inventory_item_price"
    ADD_TO_CART_BUTTON_TEMPLATE = "button[data-test='add-to-cart-{slug}']"

    def __init__(self, page) -> None:
        super().__init__(page)
        self.sort = SortDropdown(page, self.SORT_DROPDOWN)
        self.cart = CartBadge(page, self.CART_BADGE, self.CART_ICON)

    def is_loaded(self) -> bool:
        return self.is_visible(self.SORT_DROPDOWN, timeout_ms=5000)

    def product_names(self) -> list[str]:
        return [el.strip() for el in self.page.locator(self.ITEM_NAME).all_inner_texts()]

    def product_prices(self) -> list[float]:
        raw = self.page.locator(self.ITEM_PRICE).all_inner_texts()
        return [float(p.replace("$", "").strip()) for p in raw]

    def add_product_to_cart(self, product_slug: str) -> "InventoryPage":
        """product_slug e.g. 'sauce-labs-backpack' matching SauceDemo's data-test attrs."""
        self.click(self.ADD_TO_CART_BUTTON_TEMPLATE.format(slug=product_slug))
        return self

    def open_cart(self) -> "InventoryPage":
        self.cart.open()
        return self
