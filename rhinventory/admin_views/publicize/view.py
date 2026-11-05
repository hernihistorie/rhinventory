from flask import Blueprint, flash, redirect, request, url_for
from flask_admin import expose

from rhinventory.admin_views.publicize.forms import DEFAULT_COUNT, SORTS, PublicizeFilterForm, make_publicize_form
from rhinventory.admin_views.publicize.service import apply_decisions, find_tag, get_progress, get_queue
from rhinventory.extensions import db
from rhinventory.util import require_write_access

# Only makes this directory's templates available.  The route stays on AssetView, because the
# asset menu bar it renders relies on being in an asset view.
publicize_bp = Blueprint('publicize', __name__, template_folder='templates')


class PublicizeMixin:
    @expose('/publicize/', methods=['GET', 'POST'])
    @require_write_access
    def publicize_view(self):
        filters = PublicizeFilterForm(request.args)
        if not filters.validate():
            flash("Invalid Publicize filter.", 'error')
            return redirect(url_for('.publicize_view'))

        if request.method == 'POST':
            return self._save_publicize_decisions(filters)

        tag = None
        if filters.tag.data:
            tag = find_tag(filters.tag.data)
            if not tag:
                flash(f"Tag {filters.tag.data} not found.", 'error')
                return redirect(url_for('.publicize_view'))

        count = filters.count.data or DEFAULT_COUNT
        offset = filters.offset.data or 0
        items = get_queue(filters.sort.data, offset, count, tag)
        needs_judging_count, all_assets_count = get_progress()

        def filtered_url(**changes) -> str:
            return url_for('.publicize_view', **(filters.url_args | changes))

        return self.render('publicize/index.html',
                           items=items,
                           publicize_form=make_publicize_form(),
                           all_assets_count=all_assets_count,
                           needs_judging_count=needs_judging_count,
                           count=count,
                           tag=tag,
                           filter_args=filters.url_args,
                           sort_links=[
                               (label, filtered_url(sort=sort, offset=None), sort == filters.sort.data)
                               for sort, label in SORTS.items()
                           ],
                           skip_url=filtered_url(offset=offset + len(items)) if items else None,
                           first_batch_url=filtered_url(offset=None),
                           clear_tag_url=filtered_url(tag=None, offset=None))

    def _save_publicize_decisions(self, filters: PublicizeFilterForm):
        form = make_publicize_form(request.form)
        if form.validate():
            result = apply_decisions(
                form.decisions('asset'),
                form.decisions('file'),
                publicize_blanks=form.publicize_all.data,
            )
            db.session.commit()
            flash(f"Saved {result.assets_changed} assets and {result.files_changed} files.")
        else:
            flash("Nothing was saved because the form was invalid or expired.  Please try again.", 'error')

        return redirect(url_for('.publicize_view', **filters.url_args))
