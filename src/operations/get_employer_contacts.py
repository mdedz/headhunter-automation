import argparse
import logging

from ..main import BaseOperation
from ..main import Namespace as BaseNamespace

logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    username: str | None
    password: str | None
    search: str | None
    export: bool


class Operation(BaseOperation):
    """Sends contact info of employers, who sent u invatations"""

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-s",
            "--search",
            type=str,
            default="",
            help="Строка поиска контактов работодателя (email, имя, название компании)",
        )
        parser.add_argument(
            "-p",
            "--page",
            default=1,
            help="Номер страницы в выдаче. Игнорируется при экспорте.",
        )
        parser.add_argument(
            "--export",
            action=argparse.BooleanOptionalAction,
            default=False,
            help="Экспортировать контакты работодателей.",
        )
        parser.add_argument(
            "-f",
            "--format",
            default="html",
            choices=["html", "jsonl"],
            help="Формат вывода",
        )

    def run(self, args: Namespace, _) -> None:
        if args.export:
            contact_persons = []
            if args.format == "jsonl":
                import json
                import sys

                for contact in contact_persons:
                    json.dump(contact, sys.stdout, ensure_ascii=False)
                    sys.stdout.write("\n")
                    sys.stdout.flush()
            else:
                print(generate_html_report(contact_persons))
            return



def generate_html_report(data: list[dict]) -> str:
    """
    Генерирует HTML-отчет на основе предоставленных данных.
    """
    html_content = """\
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Контакты работодателей</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f4f7f6;
            color: #333;
        }
        .container {
            max-width: 900px;
            margin: 20px auto;
            background-color: #ffffff;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #0056b3;
            text-align: center;
            margin-bottom: 30px;
        }
        .person-card {
            background-color: #e9f0f8;
            border: 1px solid #cce5ff;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
            transition: transform 0.2s ease-in-out;
        }
        .person-card:hover {
            transform: translateY(-5px);
        }
        .person-card h2 {
            color: #004085;
            margin-top: 0;
            margin-bottom: 10px;
            border-bottom: 2px solid #0056b3;
            padding-bottom: 5px;
        }
        .person-card p {
            margin: 5px 0;
        }
        .person-card strong {
            color: #004085;
        }
        .employer-info {
            background-color: #d1ecf1;
            border-left: 5px solid #007bff;
            padding: 15px;
            margin-top: 15px;
            border-radius: 5px;
        }
        .employer-info h3 {
            color: #0056b3;
            margin-top: 0;
            margin-bottom: 10px;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        ul li {
            background-color: #f8fafd;
            padding: 8px 12px;
            margin-bottom: 5px;
            border-radius: 4px;
            border: 1px solid #e0e9f1;
        }
        a {
            color: #007bff;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .no-data {
            color: #6c757d;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Полученные контакты</h1>
"""

    for item in data:
        name = item.get("name", "N/A")
        email = item.get("email", "N/A")
        employer = item.get("employer") or {}

        employer_name = employer.get("name", "N/A")
        employer_area = employer.get("area", "N/A")
        employer_site_url = employer.get("site_url", "")

        phone_numbers = [
            pn["phone_number"]
            for pn in item.get("phone_numbers", [])
            if "phone_number" in pn
        ]
        telegram_usernames = [
            tu["username"]
            for tu in item.get("telegram_usernames", [])
            if "username" in tu
        ]

        html_content += f"""\
        <div class="person-card">
            <h2>{name}</h2>
            <p><strong>Email:</strong> <a href="mailto:{email}">{email}</a></p>
        """

        if employer_name != "N/A":
            html_content += f"""\
            <div class="employer-info">
                <h3>Работодатель: {employer_name}</h3>
                <p><strong>Город:</strong> {employer_area}</p>
            """
            if employer_site_url:
                html_content += f"""\
                <p><strong>Сайт:</strong> <a href="{employer_site_url}" target="_blank">{employer_site_url}</a></p>
                """
            html_content += "</div>"  # Закрываем employer-info
        else:
            html_content += (
                '<p class="no-data">Информация о работодателе отсутствует.</p>'
            )

        if phone_numbers:
            html_content += "<p><strong>Номера телефонов:</strong></p><ul>"
            for phone in phone_numbers:
                html_content += f"<li><a href='tel:{phone}'>{phone}</a></li>"
            html_content += "</ul>"
        else:
            html_content += '<p class="no-data">Номера телефонов отсутствуют.</p>'

        if telegram_usernames:
            html_content += "<p><strong>Имена пользователей Telegram:</strong></p><ul>"
            for username in telegram_usernames:
                html_content += f"<li><a href='https://t.me/{username}' target='_blank'>@{username}</a></li>"
            html_content += "</ul>"
        else:
            html_content += (
                '<p class="no-data">Имена пользователей Telegram отсутствуют.</p>'
            )

        html_content += "</div>"  # Закрываем person-card

    html_content += """\
    </div>
</body>
</html>"""
    return html_content


def print_contacts(data: dict) -> None:
    """Вывод всех контактов в древовидной структуре."""
    page = data["page"]
    pages = (data["total"] // data["per_page"]) + 1
    print(f"Страница {page}/{pages}:")
    contacts = data.get("contact_persons", [])
    for idx, contact in enumerate(contacts):
        is_last_contact = idx == len(contacts) - 1
        print_contact(contact, is_last_contact)
    print()


def print_contact(contact: dict, is_last_contact: bool) -> None:
    """Вывод информации о конкретном контакте."""
    prefix = "└──" if is_last_contact else "├──"
    print(f" {prefix} 🧑 {contact.get('name', 'Имя скрыто')}")
    prefix2 = "    " if is_last_contact else " │   "
    print(f"{prefix2}├── 📧 Email: {contact.get('email', 'н/д')}")
    employer = contact.get("employer") or {}
    print(f"{prefix2}├── 🏢 Работодатель: {employer.get('name', 'н/д')}")
    print(f"{prefix2}├── 🏠 Город: {employer.get('area', 'н/д')}")
    print(f"{prefix2}└── 🌐 Сайт: {employer.get('site_url', 'н/д')}")
    print(prefix2)
