from django.http import QueryDict
from django.test import TestCase

from base.tests.model_factories import ProjectF
from certification.checklist_answers import (
    answer_error,
    contains_link,
    parse_checklist_answers,
    shows_evidence,
)
from certification.models import ORGANIZATION_OWNER, Checklist
from certification.tests.model_factories import ChecklistF


class TestParseChecklistAnswers(TestCase):
    """Answers arrive as raw post keys, not as form fields."""

    def test_reads_an_answer_and_its_details(self):
        data = QueryDict('checklist-7=yes&textarea-7=something')
        self.assertEqual(
            parse_checklist_answers(data),
            {'7': {'answer': 'yes', 'text': 'something'}}
        )

    def test_keeps_questions_apart(self):
        data = QueryDict('checklist-1=yes&checklist-2=no')
        answers = parse_checklist_answers(data)
        self.assertEqual(answers['1']['answer'], 'yes')
        self.assertEqual(answers['2']['answer'], 'no')

    def test_ignores_other_fields(self):
        data = QueryDict('name=Acme&csrfmiddlewaretoken=abc')
        self.assertEqual(parse_checklist_answers(data), {})

    def test_ignores_a_key_that_is_not_a_question_id(self):
        data = QueryDict('checklist-not-a-number=yes&textarea-=x')
        self.assertEqual(parse_checklist_answers(data), {})


class TestContainsLink(TestCase):
    """A link has to be usable, and may sit anywhere in the text."""

    def test_prose_holds_no_link(self):
        self.assertFalse(contains_link('I helped with the documentation'))

    def test_a_bare_domain_is_not_a_link(self):
        self.assertFalse(contains_link('qgis.org/community'))

    def test_empty_text_holds_no_link(self):
        self.assertFalse(contains_link(''))

    def test_finds_a_link_on_its_own(self):
        self.assertTrue(contains_link('https://github.com/qgis/QGIS/pull/1'))

    def test_finds_a_link_wrapped_in_prose(self):
        self.assertTrue(contains_link(
            'We rewrote the install guide, see '
            'https://docs.qgis.org/latest/en/docs/ for the result.'
        ))

    def test_accepts_http_as_well_as_https(self):
        self.assertTrue(contains_link('http://docs.qgis.org/page'))

    def test_ignores_punctuation_closing_the_sentence(self):
        self.assertTrue(contains_link(
            'It landed in https://github.com/qgis/QGIS/pull/1.'
        ))

    def test_finds_a_good_link_after_a_bad_one(self):
        self.assertTrue(contains_link(
            'https://. https://github.com/qgis/QGIS/pull/1'
        ))


class TestAnswerError(TestCase):
    """One rule for one answer, shared by the form and the view."""

    def setUp(self):
        self.project = ProjectF.create()

    def question(self, **kwargs) -> Checklist:
        return ChecklistF.create(
            project=self.project,
            target=ORGANIZATION_OWNER,
            active=True,
            **kwargs
        )

    def test_no_answer_at_all(self):
        question = self.question(show_text_box=True)
        self.assertEqual(answer_error(question, {}), 'Answer yes or no.')

    def test_an_answer_we_do_not_recognise(self):
        question = self.question(show_text_box=True)
        self.assertEqual(
            answer_error(question, {'answer': 'maybe'}),
            'Answer yes or no.'
        )

    def test_no_needs_nothing_else(self):
        question = self.question(show_text_box=True, link_required=True)
        self.assertIsNone(answer_error(question, {'answer': 'no'}))

    def test_yes_needs_nothing_when_there_is_no_text_box(self):
        question = self.question(show_text_box=False)
        self.assertIsNone(answer_error(question, {'answer': 'yes'}))

    def test_yes_needs_the_text_box_filled(self):
        question = self.question(show_text_box=True)
        self.assertEqual(
            answer_error(question, {'answer': 'yes', 'text': '   '}),
            'Tell us what you did.'
        )

    def test_yes_accepts_prose_when_no_link_is_required(self):
        question = self.question(show_text_box=True, link_required=False)
        self.assertIsNone(answer_error(
            question, {'answer': 'yes', 'text': 'We ran a training course'}
        ))

    def test_yes_needs_a_link_when_one_is_required(self):
        question = self.question(show_text_box=True, link_required=True)
        self.assertEqual(
            answer_error(
                question, {'answer': 'yes', 'text': 'We ran a course'}
            ),
            'Add at least one URL.'
        )

    def test_yes_accepts_prose_around_a_link(self):
        question = self.question(show_text_box=True, link_required=True)
        self.assertIsNone(answer_error(question, {
            'answer': 'yes',
            'text': 'We ran a course, see https://qgis.org/x for the notes.'
        }))


class TestShowsEvidence(TestCase):
    """An application needs at least one yes that stands up."""

    def setUp(self):
        self.project = ProjectF.create()
        self.question = ChecklistF.create(
            project=self.project,
            target=ORGANIZATION_OWNER,
            active=True,
            show_text_box=True,
            link_required=True
        )
        self.plain_question = ChecklistF.create(
            project=self.project,
            target=ORGANIZATION_OWNER,
            active=True,
            show_text_box=False
        )
        self.questions = Checklist.objects.filter(project=self.project)

    def test_every_answer_no(self):
        answers = {
            str(self.question.id): {'answer': 'no'},
            str(self.plain_question.id): {'answer': 'no'},
        }
        self.assertFalse(shows_evidence(self.questions, answers))

    def test_no_answers_at_all(self):
        self.assertFalse(shows_evidence(self.questions, {}))

    def test_a_yes_with_nothing_behind_it(self):
        answers = {
            str(self.question.id): {'answer': 'yes', 'text': 'we did things'},
            str(self.plain_question.id): {'answer': 'no'},
        }
        self.assertFalse(shows_evidence(self.questions, answers))

    def test_a_yes_with_a_link(self):
        answers = {
            str(self.question.id): {
                'answer': 'yes', 'text': 'https://qgis.org/x'
            },
            str(self.plain_question.id): {'answer': 'no'},
        }
        self.assertTrue(shows_evidence(self.questions, answers))

    def test_a_yes_on_a_question_with_no_text_box_is_not_evidence(self):
        answers = {
            str(self.question.id): {'answer': 'no'},
            str(self.plain_question.id): {'answer': 'yes'},
        }
        self.assertFalse(shows_evidence(self.questions, answers))

    def test_an_unanswered_question_does_not_count_against_it(self):
        answers = {
            str(self.question.id): {
                'answer': 'yes', 'text': 'https://qgis.org/x'
            },
        }
        self.assertTrue(shows_evidence(self.questions, answers))
