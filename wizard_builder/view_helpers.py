import logging

from django.core.urlresolvers import reverse

logger = logging.getLogger(__name__)


class SerializedDataHelper(object):
    metadata_fields = [
        'csrfmiddlewaretoken',
        'wizard_current_step',
        'wizard_goto_step',
        'form_pk',
    ]
    conditional_fields = [
        'extra_info',
        'extra_options',
    ]
    question_id_error_message = 'field_id={} not found in {}'
    choice_id_error_message = 'choices(pk={}) not found in {}'

    def __init__(self, data, forms):
        self.forms = forms
        self.data = data
        self.zipped_data = []
        self._format_data()

    @property
    def cleaned_data(self):
        return self.zipped_data

    def _format_data(self):
        for index, page_data in enumerate(self.data):
            self._cleaned_form_data(page_data, index)

    def _cleaned_form_data(self, page_data, index):
        self._parse_answer_fields(
            self._form_data_without_metadata(page_data),
            self._form_questions_serialized(index),
        )

    def _form_data_without_metadata(self, data):
        return {
            key: value
            for key, value in data.items()
            if key not in self.metadata_fields
        }

    def _form_questions_serialized(self, index):
        return self.forms[index].serialized

    def _parse_answer_fields(self, answers, questions):
        for answer_key, answer_value in answers.items():
            if answer_key not in self.conditional_fields:
                question = self._get_question(answer_key, questions)
                answer = self._question_answer(answers, question)
                self._parse_answers(questions, question, answers, answer)

    def _parse_answers(self, question_dict, question, answer_dict, answer):
        if question['type'] == 'Singlelinetext':
            self._append_text_answer(answer, question)
        else:
            answer_list = answer if isinstance(answer, list) else [answer]
            self._append_list_answers(answer_dict, answer_list, question)

    def _question_answer(self, answers, question):
        return answers[question['field_id']]

    def _append_text_answer(self, answer, question):
        if len(answer) > 0:
            self.zipped_data.append({
                question['question_text']: [answer],
            })

    def _append_list_answers(self, answer_dict, answer_list, question):
        choice_list = []
        for answer in answer_list:
            choice_list.append(self._get_choice_text(
                answer_dict, answer, question))
        self.zipped_data.append({
            question['question_text']: choice_list,
        })

    def _get_question(self, answer_key, questions):
        return self._get_from_serialized_id(
            stored_id=answer_key,
            current_objects=questions,
            id_field='field_id',
            message=self.question_id_error_message,
        )

    def _get_choice_text(self, answer_dict, answer, question):
        choice = self._get_from_serialized_id(
            stored_id=answer,
            current_objects=question['choices'],
            id_field='pk',
            message=self.choice_id_error_message,
        )
        choice_text = choice['text']
        if choice.get('extra_info_text') and answer_dict.get('extra_info'):
            choice_text += ': ' + answer_dict['extra_info']
        if choice.get('options') and answer_dict.get('extra_options'):
            choice_text += ': ' + self._get_choice_option_text(
                choice, answer_dict)
        return choice_text

    def _get_choice_option_text(self, choice, answer_dict):
        index = int(answer_dict['extra_options'])
        return choice['options'][index]['text']

    def _get_from_serialized_id(
        self,
        stored_id,
        current_objects,
        id_field,
        message,
    ):
        try:
            related_object = None
            for _object in current_objects:
                if str(stored_id) == str(_object[id_field]):
                    related_object = _object
            if related_object is not None:
                return related_object
            else:
                raise ValueError(message.format(stored_id, current_objects))
        except Exception as e:
            # Catch exceptions raised from questions being edited
            # after the user originally answered them
            logger.exception(e)


class StepsHelper(object):
    done_name = 'done'
    review_name = 'Review'
    next_name = 'Next'
    back_name = 'Back'

    def __init__(self, view):
        self.view = view

    @property
    def all(self):
        return self.view.manager.forms

    @property
    def step_count(self):
        return len(self.all)

    @property
    def current(self):
        _step = self._current or self.first
        if _step == self.done_name:
            return _step
        elif _step <= self.last:
            return _step
        else:
            return self.last

    @property
    def _current(self):
        _step = self.view.request.session.get('current_step', self.first)
        if _step == self.done_name:
            return _step
        else:
            return int(_step)

    @property
    def _goto_step_back(self):
        return self._goto_step(self.back_name)

    @property
    def _goto_step_next(self):
        return self._goto_step(self.next_name)

    @property
    def _goto_step_review(self):
        return self._goto_step(self.review_name)

    @property
    def first(self):
        return 0

    @property
    def last(self):
        return self.all[-1].manager_index

    @property
    def next(self):
        return self.adjust_step(1)

    @property
    def prev(self):
        return self.adjust_step(0)

    @property
    def next_is_done(self):
        return self.next == self.done_name

    @property
    def current_is_done(self):
        return self.current == self.done_name

    @property
    def current_url(self):
        return self.url(self.current)

    @property
    def last_url(self):
        return self.url(self.last)

    @property
    def done_url(self):
        return self.url(self.done_name)

    def _goto_step(self, step_type):
        post = self.view.request.POST
        return post.get('wizard_goto_step', None) == step_type

    def url(self, step):
        return reverse(
            self.view.request.resolver_match.view_name,
            kwargs={'step': step},
        )

    def overflowed(self, step):
        return int(step) > int(self.last)

    def finished(self, step):
        return self._goto_step_review or step == self.done_name

    def set_from_get(self, step_url_param):
        step = step_url_param or self.current
        self.view.request.session['current_step'] = step

    def set_from_post(self):
        step = self.view.request.POST.get('wizard_current_step', self.current)
        if self._goto_step_back:
            step = self.adjust_step(-1)
        if self._goto_step_next:
            step = self.adjust_step(1)
        self.view.request.session['current_step'] = step

    def adjust_step(self, adjustment):
        # TODO: tests as spec
        key = self.current + adjustment
        if key < self.first:
            return None
        if key == self.first:
            return self.first
        elif self.step_count > key:
            return self.view.manager.forms[key].manager_index
        elif self.step_count == key:
            return self.done_name
        else:
            return None


class StorageHelper(object):
    data_manager = SerializedDataHelper

    def __init__(self, view):
        self.view = view

    @property
    def form_data(self):
        return {'data': [
            self.data_from_pk(form.pk)
            for form in self.view.manager.forms
        ]}

    @property
    def cleaned_form_data(self):
        return self.data_manager(
            self.form_data['data'],
            self.view.manager.forms,
        ).cleaned_data

    @property
    def post_form_pk(self):
        return self.view.form_pk(self.view.request.POST[
            self.view.form_pk_field])

    @property
    def post_data(self):
        data = self._data_from_key(self.post_form_pk)
        data.update(self.view.request.POST)
        return data

    def set_form_data(self):
        self.view.request.session[self.post_form_pk] = self.post_data

    def data_from_pk(self, pk):
        key = self.view.form_pk(pk)
        return self._data_from_key(key)

    def _data_from_key(self, key):
        return self.view.request.session.get(key, {})