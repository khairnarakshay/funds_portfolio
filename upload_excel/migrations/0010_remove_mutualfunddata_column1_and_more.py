# Generated by Django 5.0.6 on 2025-02-24 06:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('upload_excel', '0009_mutualfunddata_industry_rating_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mutualfunddata',
            name='column1',
        ),
        migrations.RemoveField(
            model_name='mutualfunddata',
            name='column2',
        ),
    ]
