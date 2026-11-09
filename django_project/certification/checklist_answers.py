# coding=utf-8
"""Rules for the checklist answers an applicant gives.

The checklist is rendered outside the Django form, so its answers arrive as
raw ``checklist-<id>`` and ``textarea-<id>`` keys rather than as form fields.
This module turns those keys into answers and decides whether an answer is
good enough, so the form and the view apply one rule rather than two.
"""
import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import QuerySet
from django.http import QueryDict

from .models import Checklist

#: One answer: an optional 'answer' of 'yes' or 'no', and an optional 'text'.
Answer = dict[str, str]

LINK_PATTERN = re.compile(r'https?://\S+')

#: Punctuation a writer leaves against a link when it ends a sentence.
TRAILING_PUNCTUATION = '.,;:!?)]}>"\''


def parse_checklist_answers(data: QueryDict) -> dict[str, Answer]:
    """Collect checklist answers out of posted data, keyed by question id.

    Keys whose suffix is not a question id are ignored, so a forged key
    cannot reach a database lookup.

    :param data: Raw posted data.
    :type data: QueryDict

    :returns: Answers keyed by question id.
    :rtype: dict
    """

    answers: dict[str, Answer] = {}
    for key, value in data.items():
        for prefix, field in (('checklist-', 'answer'), ('textarea-', 'text')):
            if not key.startswith(prefix):
                continue
            question_id = key[len(prefix):]
            if question_id.isdigit():
                answers.setdefault(question_id, {})[field] = value
    return answers


def contains_link(text: str) -> bool:
    """Does the text hold at least one usable http or https link?

    The text may be free prose with links in it, so we look for links
    anywhere rather than expecting one per line.

    :param text: Content of a checklist text box.
    :type text: str

    :returns: True when at least one link validates.
    :rtype: bool
    """

    validate_url = URLValidator(schemes=['http', 'https'])
    for candidate in LINK_PATTERN.findall(text):
        try:
            validate_url(candidate.rstrip(TRAILING_PUNCTUATION))
        except ValidationError:
            continue
        return True
    return False


def answer_error(question: Checklist, answer: Answer) -> str | None:
    """Work out what to tell the applicant about one answer.

    :param question: The question that was asked.
    :type question: Checklist

    :param answer: The answer as posted.
    :type answer: dict

    :returns: A message to show beside the question, or None when the answer
        is good.
    :rtype: str
    """

    if answer.get('answer') not in ('yes', 'no'):
        return 'Answer yes or no.'

    if answer.get('answer') == 'no' or not question.show_text_box:
        return None

    text = answer.get('text', '').strip()
    if not text:
        return 'Tell us what you did.'

    if question.link_required and not contains_link(text):
        return 'Add at least one URL.'

    return None


def shows_evidence(
        questions: QuerySet[Checklist],
        answers: dict[str, Answer]) -> bool:
    """Has the applicant shown us anything we can review?

    An application needs at least one yes, and every yes has to carry what
    its question asks for. Questions left unanswered are the form's business,
    not this one's, so they are ignored here.

    :param questions: The questions we put to the applicant.
    :type questions: QuerySet

    :param answers: Answers keyed by question id.
    :type answers: dict

    :returns: True when the application is worth a reviewer's time.
    :rtype: bool
    """

    found_one = False
    for question in questions:
        answer = answers.get(str(question.id), {})
        if answer.get('answer') != 'yes':
            continue
        if not question.show_text_box:
            continue
        if answer_error(question, answer):
            return False
        found_one = True
    return found_one
