import re
from typing import Any

from flask import current_app, session
from wtforms import Form, IntegerField, SelectField, StringField, SubmitField
from wtforms.csrf.session import SessionCSRF
from wtforms.validators import NumberRange, Optional

from rhinventory.models.enums import Privacy

DEFAULT_COUNT = 50
MAX_COUNT = 500

# None is a blank decision: the reviewer didn't judge the asset or file.
DECISIONS: dict[str, Privacy | None] = {
    'public': Privacy.public,
    'private': Privacy.private,
    'default': None,
}
DECISION_FIELD_NAME = re.compile(r'(asset|file)-([0-9]{1,18})')


class PublicizeFilterForm(Form):
    start_id = IntegerField(default=0, validators=[Optional(), NumberRange(min=0)])
    count = IntegerField(default=DEFAULT_COUNT, validators=[Optional(), NumberRange(min=1, max=MAX_COUNT)])
    tag = StringField(validators=[Optional()])

    @property
    def url_args(self) -> dict[str, Any]:
        """The filters that differ from the defaults, to carry over to other URLs."""
        return {
            'start_id': self.start_id.data or None,
            'count': self.count.data if self.count.data != DEFAULT_COUNT else None,
            'tag': self.tag.data or None,
        }


class PublicizeForm(Form):
    class Meta:
        csrf = True
        csrf_class = SessionCSRF
        # Judging a batch can take a while, and the token is tied to the session anyway.
        csrf_time_limit = None

        @property
        def csrf_secret(self) -> bytes:
            secret_key = current_app.secret_key
            return secret_key.encode() if isinstance(secret_key, str) else secret_key

        @property
        def csrf_context(self) -> Any:
            return session

    publicize_all = SubmitField("Publicize all except private")
    save = SubmitField("Save")

    def decisions(self, kind: str) -> dict[int, Privacy | None]:
        """The submitted decisions for `kind` ('asset' or 'file'), by ID."""
        decisions: dict[int, Privacy | None] = {}
        for field in self:
            match = DECISION_FIELD_NAME.fullmatch(field.name)
            if match and match[1] == kind:
                decisions[int(match[2])] = DECISIONS[field.data]
        return decisions


def make_publicize_form(formdata: Any = None) -> PublicizeForm:
    """Build the form with a field for each submitted decision.

    WTForms declares fields on the class, but these depend on what was on the reviewer's page.
    """
    class SubmittedPublicizeForm(PublicizeForm):
        pass

    for name in formdata or ():
        if DECISION_FIELD_NAME.fullmatch(name):
            setattr(SubmittedPublicizeForm, name, SelectField(choices=list(DECISIONS)))

    return SubmittedPublicizeForm(formdata)
