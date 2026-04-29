import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0004_error_transfer"),
    ]

    operations = [
        migrations.AddField(
            model_name="transfer",
            name="sender_card",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sent_transfers",
                to="app.card",
            ),
        ),
        migrations.AddField(
            model_name="transfer",
            name="receiver_card",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="received_transfers",
                to="app.card",
            ),
        ),
    ]
