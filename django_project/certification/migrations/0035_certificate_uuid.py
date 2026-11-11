import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("certification", "0034_merge_20261109_0855"),
    ]

    operations = [
        # Added without a default first, so existing certificates keep a null uuid.
        migrations.AddField(
            model_name="certificate",
            name="uuid",
            field=models.UUIDField(editable=False, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="certificate",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, null=True, unique=True
            ),
        ),
    ]
