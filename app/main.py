from app.interfaces.cli import run_cli_chat
from app.logger import setup_logger


def main() -> None:
    setup_logger()
    run_cli_chat()


if __name__ == "__main__":
    main()