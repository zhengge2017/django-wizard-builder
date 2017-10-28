# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-28 06:13
from __future__ import unicode_literals

from django.db import migrations, models


def add_dropdowns(apps, schema_editor):
    current_database = schema_editor.connection.alias
    Question = apps.get_model('wizard_builder.FormQuestion')
    questions = Question.objects.filter(is_dropdown=True).using(current_database)
    for question in questions:
        question.type = 'dropdown'
        question.save()


class Migration(migrations.Migration):

    dependencies = [
        ('wizard_builder', '0039_dropdown_proxy'),
    ]

    operations = [
        migrations.RunPython(
            add_dropdowns,
            migrations.RunPython.noop,
        ),
    ]
