# Generated by Django 3.2 on 2024-06-07 12:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0005_auto_20240605_0308'),
    ]

    operations = [
        migrations.AlterField(
            model_name='survey',
            name='Category',
            field=models.IntegerField(default=0),
        ),
    ]
