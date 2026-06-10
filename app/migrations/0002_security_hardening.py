import secrets

from django.conf import settings
from django.db import migrations


def add_user_secret_column(apps, schema_editor):
    connection = schema_editor.connection
    existing_tables = connection.introspection.table_names()

    for table_name in ("app_user", "auth_user"):
        if table_name not in existing_tables:
            continue

        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                connection.cursor(),
                table_name,
            )
        }
        if "secret" not in columns:
            schema_editor.execute(f"ALTER TABLE {table_name} ADD COLUMN secret varchar(128)")

        rows = connection.cursor()
        rows.execute(f"SELECT id FROM {table_name} WHERE secret IS NULL OR secret = ''")
        ids = [row[0] for row in rows.fetchall()]
        for user_id in ids:
            secret = secrets.token_hex(32)
            cursor = connection.cursor()
            cursor.execute(
                f"UPDATE {table_name} SET secret = %s WHERE id = %s",
                [secret, user_id],
            )


def encrypt_existing_card_columns(apps, schema_editor):
    from app.security import encrypt_card, is_fernet_token

    connection = schema_editor.connection
    existing_tables = connection.introspection.table_names()
    quote = connection.ops.quote_name
    direct_card_columns = {"card", "card_number", "card_num", "pan"}

    for table_name in existing_tables:
        if not table_name.startswith("app_"):
            continue

        with connection.cursor() as cursor:
            table_description = connection.introspection.get_table_description(cursor, table_name)
            columns = {column.name for column in table_description}

        if "id" not in columns:
            continue

        card_columns = [
            column
            for column in columns
            if column.lower() in direct_card_columns
            or ("card" in table_name.lower() and column.lower() == "number")
        ]

        for column in card_columns:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {quote('id')}, {quote(column)} FROM {quote(table_name)} "
                    f"WHERE {quote(column)} IS NOT NULL AND {quote(column)} != ''"
                )
                rows = cursor.fetchall()

            for row_id, value in rows:
                value = str(value)
                if is_fernet_token(value):
                    continue
                encrypted_value = encrypt_card(value)
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {quote(table_name)} SET {quote(column)} = %s WHERE {quote('id')} = %s",
                        [encrypted_value, row_id],
                    )


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(add_user_secret_column, migrations.RunPython.noop),
        migrations.RunPython(encrypt_existing_card_columns, migrations.RunPython.noop),
    ]
