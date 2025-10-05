import argparse
from .geocode import geocode_csv


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="itur", description="Itur CLI")
    sub = parser.add_subparsers(dest="command")

    hello = sub.add_parser("hello", help="ברכה מהירה")
    hello.add_argument("--name", "-n", default="עולם", help="שם לברכה")

    geo = sub.add_parser("geocode", help="גאוקודינג לקובץ CSV של כתובות")
    geo.add_argument("--in", dest="in_path", required=True, help="קובץ קלט CSV")
    geo.add_argument("--out", dest="out_path", required=True, help="קובץ פלט CSV")
    geo.add_argument("--col", dest="address_column", default=None, help="שם עמודת הכתובת")
    geo.add_argument("--sep", dest="delimiter", default=",", help="תו מפריד (ברירת מחדל: ,)")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "hello" or args.command is None:
        name = getattr(args, "name", "עולם")
        print(f"שלום, {name}!")
        return

    if args.command == "geocode":
        geocode_csv(args.in_path, args.out_path, address_column=args.address_column, delimiter=args.delimiter)
        print(f"נכתב קובץ פלט אל: {args.out_path}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()

