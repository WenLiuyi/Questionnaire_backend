from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model
import json

def get_model_class(table_name):
    try:
        return apps.get_model(app_label='user', model_name=table_name)
    except LookupError:
        raise ValueError(f"Table '{table_name}' does not exist.")

def add_record(table_name, data):
    ModelClass = get_model_class(table_name)
    instance = ModelClass(**data)
    instance.save()
    return instance.pk

def delete_record(table_name, pk):
    ModelClass = get_model_class(table_name)
    try:
        instance = ModelClass.objects.get(pk=pk)
        instance.delete()
        return True
    except ObjectDoesNotExist:
        return False

def update_record(table_name, pk, data):
    ModelClass = get_model_class(table_name)
    try:
        instance = ModelClass.objects.get(pk=pk)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        return True
    except ObjectDoesNotExist:
        return False

def get_records(table_name, criteria):
    ModelClass = get_model_class(table_name)
    records = ModelClass.objects.filter(**criteria)
    return records