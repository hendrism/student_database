"""Activity management routes."""

from flask import request, render_template, redirect, url_for, flash
from . import routes_bp
from models import Activity, db


@routes_bp.route('/activities')
def activities():
    """List all active activities."""
    activities = Activity.query.filter_by(active=True).order_by(Activity.name).all()
    return render_template('activities.html', activities=activities)


@routes_bp.route('/activities/add', methods=['GET', 'POST'])
def add_activity():
    """Add a new activity."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            new_activity = Activity(name=name)
            db.session.add(new_activity)
            db.session.commit()
            flash(f'Activity "{name}" added.', 'success')
            return redirect(url_for('routes.activities'))
    return render_template('add_activity.html')


@routes_bp.route('/activities/edit/<int:activity_id>', methods=['GET', 'POST'])
def edit_activity(activity_id):
    """Edit an existing activity."""
    act = Activity.query.get_or_404(activity_id)
    if request.method == 'POST':
        act.name = request.form.get('name', act.name).strip()
        db.session.commit()
        flash('Activity updated.', 'success')
        return redirect(url_for('routes.activities'))
    return render_template('edit_activity.html', activity=act)


@routes_bp.route('/activities/delete/<int:activity_id>', methods=['POST'])
def delete_activity(activity_id):
    """Soft-delete (archive) an activity."""
    act = Activity.query.get_or_404(activity_id)
    act.active = False
    db.session.commit()
    flash('Activity archived.', 'warning')
    return redirect(url_for('routes.activities'))
