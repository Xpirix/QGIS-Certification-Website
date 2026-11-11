import certification.models.certificate
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("certification", "0034_merge_20261109_0855"),
    ]

    operations = [
        # Added without a default first, so existing certificates keep a null code.
        migrations.AddField(
            model_name="certificate",
            name="verification_code",
            field=models.CharField(
                editable=False, max_length=14, null=True, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="certificate",
            name="verification_code",
            field=models.CharField(
                default=certification.models.certificate.generate_verification_code,
                editable=False,
                max_length=14,
                null=True,
                unique=True,
            ),
        ),
    ]
