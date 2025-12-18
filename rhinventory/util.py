from typing import Callable, TypeVar, Any, cast
from functools import wraps
import re
import unicodedata

from flask import flash, redirect
from flask_login import current_user

from sqlalchemy.orm import Query

# from bokeh.plotting import figure
# import bokeh.embed

# From https://matthieu.io/blog/2019/02/09/bokeh-sqlalchemy/
# def figure_counter(
#         session,
#         field_identifier,
#         field_date,
#         filter,
#         groups,
#         to_x,
#         count_total,
#         title):
#     """Makes a bar figure with time as x, and something counted as y.

#     `field_identifier` is what is counted (e.g. Action.id)
#     `field_date` is how it is counted (eg. Action.date_created)
#     `groups` is how to group the dates (e.g. ['year', 'month'])
#     `to_x` is a function that will create a datetime from a row
#       (e.g. lambda x: datetime.date(int(x.year), (x.month), 1))
#     `title` is the title of the plot
#     """
#     groups = [func.extract(x, field_date).label(x) for x in groups]
#     q = (session.query(func.count(field_identifier).label('count'),
#                        *groups)
#                 .filter(filter)
#                 .group_by(*groups)
#                 .order_by(*groups)
#                 .all())
#     x = []
#     y = []
#     if len(q):
#         date = datetime.datetime(int(q[0].year), int(q[0].month), int(q[0].day))
#         today = datetime.date.today()
#         today = datetime.datetime(today.year, today.month, today.day)
#         delta = datetime.timedelta(days=1)
#         it = iter(q)
#         total = 0
#         el = next(it)
#         el_date = datetime.datetime(int(el.year), int(el.month), int(el.day))
#         while date <= today:
#             x.append(date)

#             #print(date, el_date)

#             if not el or el_date > date:
#                 y.append(total)
#             elif el:
#                 y.append(total)
#                 total += el.count

#                 try:
#                     el = next(it)
#                     el_date = datetime.datetime(int(el.year), int(el.month), int(el.day))
#                 except StopIteration:
#                     el = None
#             date += delta

#         #print(len(x), len(y))

#         width = (x[-1] - x[0]).total_seconds() / len(x) * 900

#     p = figure(plot_height=400,
#                plot_width=900,
#                title=title,
#                x_axis_type='datetime')
#     #p.vbar(x=x, width=width, bottom=0, top=y)
#     p.line(x=x, y=y, line_width=6)

#     return bokeh.embed.components(p) 

# require_edit_rights decorator
#
#

F = TypeVar("F", bound=Callable[..., Any])

def require_write_access(func: F) -> F:
    """Decorator to require edit rights for a view"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.write_access:
            flash("You do not have permission to edit", "error")
            return redirect("/")
        return func(*args, **kwargs)
    return cast(F, wrapper)

# From https://gist.github.com/berlotto/6295018
def slugify(value: str, allow_unicode: bool=False) -> str:
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower()).strip()
    return re.sub(r'[-\s]+', '-', value)


def print_sql_query(query: Query):
    compiled_query = query.compile(compile_kwargs={"literal_binds": True})
    print(str(compiled_query))

def parse_hh_code(value: str) -> int | None:
    code: int | None = None
    if value.lower().startswith('rh') or value.lower().startswith('hh'):
        try:
            code = int(value[2:])
        except ValueError:
            pass
    
    return code
