"""Customer Entry Screen — PyQt6.

Thin entry point that delegates to the canonical CustomersWindow in
customers.py. Kept as a separate module so the CS menu leaf
('cust_entry') can still launch it as a subprocess without changing
the menu tree.
"""
from .customers import main

if __name__ == "__main__":
    main()
