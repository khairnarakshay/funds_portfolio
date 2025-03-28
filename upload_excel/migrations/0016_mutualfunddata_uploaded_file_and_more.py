# Generated by Django 5.0.6 on 2025-02-25 09:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('upload_excel', '0015_rename_uploaded_at_uploadedfile_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='mutualfunddata',
            name='uploaded_file',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='mutual_fund_data', to='upload_excel.uploadedfile'),
        ),
        migrations.AlterField(
            model_name='uploadedfile',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
