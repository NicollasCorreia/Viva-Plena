from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="last_appointment_reminder_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="last_engagement_reminder_at",
            field=models.DateField(blank=True, null=True),
        ),
    ]
