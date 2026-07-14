from app.core.config import settings


def main() -> None:
    print(settings.project_name)
    print(f"Version: {settings.version}")
    print("Status: Ready")


if __name__ == "__main__":
    main()
