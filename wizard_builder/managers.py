import logging

from django.contrib.sites.models import Site
from django.db.models.manager import Manager
from django.db.models.query import QuerySet

from . import forms, mocks, models

logger = logging.getLogger(__name__)


class FormManager(object):

    @classmethod
    def get_serialized_forms(cls, site_id=1):
        return [
            form.serialized
            for form in cls.get_form_models(site_id=site_id)
        ]

    @classmethod
    def get_form_models(cls, form_data={}, answer_data={}, site_id=1):
        self = cls()
        self.site_id = site_id
        self.answer_data = answer_data
        self.form_data = form_data
        if not form_data:
            self.form_data = self._get_form_data_from_db()
        return self._create_forms_via_data()

    def _get_form_data_from_db(self):
        return [
            page.serialized_questions
            for page in models.Page.objects.wizard_set(self.site_id)
        ]

    def _create_forms_via_data(self):
        return [
            self._transform_page_to_form(page)
            for page in self._pages_via_form_data()
        ]

    def _pages_via_form_data(self):
        pages = []
        for page_questions in self.form_data:
            page = mocks.MockPage(page_questions)
            pages.append(page)
        return pages

    def _transform_page_to_form(self, page):
        FormClass = forms.PageForm.setup(page)
        form = FormClass(self.answer_data)
        form.full_clean()
        form.page = page
        return form


class PageQuerySet(QuerySet):

    def on_site(self, site_id=None):
        try:
            site_id = site_id or Site.objects.get_current().id
        except Site.DoesNotExist:
            site_id = 1
        return self.filter(
            sites__id__in=[site_id],
        )


class PageManager(Manager):
    _queryset_class = PageQuerySet

    def wizard_set(self, site_id=None):
        return self.on_site(site_id).order_by('position')

    def on_site(self, site_id=None):
        return self.get_queryset().on_site(site_id)
