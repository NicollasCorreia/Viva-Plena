from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_core", "0002_user_monthly_reminder_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="same_day_reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appointment",
            name="three_day_reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
