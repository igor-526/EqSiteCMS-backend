from pathlib import Path

from main import app
from maintain.route_inventory import write


if __name__ == "__main__":
    write(app, Path("docs/backend-route-inventory.md"))
