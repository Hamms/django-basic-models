# Copyright 2011 Concentric Sky, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from django import forms
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import models
from django.template.defaultfilters import slugify
from cachemodel import models as cachemodels
from copy import deepcopy
import re

from basic_models.managers import HasActiveManager, IsActiveManager, SlugModelManager, IsActiveSlugModelManager, OnlyOneActiveManager


class ActiveModel(cachemodels.CacheModel):
    is_active = models.BooleanField(default=True, db_index=True)
    objects = HasActiveManager()
    active_objects = IsActiveManager()

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserModel(models.Model):
    created_by = models.ForeignKey(User, related_name='%(class)s_created', null=True, blank=True, on_delete=models.SET_NULL)
    updated_by = models.ForeignKey(User, related_name='%(class)s_updated', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        abstract = True


class DefaultModel(UserModel, TimestampedModel, ActiveModel):
    class Meta:
        abstract = True


class SlugModel(DefaultModel):
    name = models.CharField(max_length=1024)
    slug = models.CharField(max_length=255, unique=True, blank=True)

    objects = SlugModelManager()
    active_objects = IsActiveSlugModelManager()

    class Meta:
        abstract = True

    def natural_key(self):
        return [self.slug]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(UnicodeSlugModel, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.name


# Maintained for backwards compatibility
UnicodeSlugModel = SlugModel


class OnlyOneActiveModel(models.Model):
    is_active = models.BooleanField(default=False)
    objects = OnlyOneActiveManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        cache.delete('active_%s' % (self.__class__.__name__,))
        super(OnlyOneActiveModel, self).save(*args, **kwargs)
        if self.is_active:
            self.__class__.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)

    def clone(self, *args, **kwargs):
        new_obj = deepcopy(self)
        new_obj.id = None
        new_obj.is_active = False
        new_obj.save()
        reverse_foreignkeys = self._meta.get_all_related_objects()
        for relation in reverse_foreignkeys:
            relation_items = getattr(self, relation.get_accessor_name(), None) 
            for item in relation_items.all():
                new_item = deepcopy(item)
                new_item.id = None
                setattr(new_item, relation.field.name, new_obj)
                new_item.save()
        reverse_m2ms = self._meta.get_all_related_many_to_many_objects()
        for relation in reverse_m2ms:
            relation_items = getattr(self, relation.get_accessor_name(), None) 
            for item in relation_items.all():
                new_item = deepcopy(item)
                new_item.id = None
                setattr(new_item, relation.field.name, new_obj)
                new_item.save()
        return new_obj