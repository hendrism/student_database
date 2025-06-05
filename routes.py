from flask import request, redirect, url_for, render_template, flash, Blueprint, jsonify
from models import Student, Objective, Goal, TrialLog, Event, Activity, SoapNote, QuarterlyReport, db, MonthlyQuota
import csv
from io import StringIO
from flask import Response
from datetime import datetime, date, timedelta
from sqlalchemy import extract, or_
from sqlalchemy.orm import joinedload

from collections import defaultdict
from calendar import monthrange


routes_bp = Blueprint('routes', __name__)

@routes_bp.route('/')
def index():
    """
    Dashboard landing page: caseload summary and upcoming sessions.
    """
    # Summary metrics
    total_students = Student.query.filter_by(active=True).count()
    total_goals    = Goal.query.filter_by(active=True).count()

    # Upcoming sessions
    today = date.today()
    upcoming_sessions = (
        Event.query
             .filter(
                 Event.active.is_(True),
                 Event.event_type == 'Session',
                 Event.status == 'Scheduled',
                 Event.date_of_session >= today
             )
             .order_by(Event.date_of_session, Event.time_of_start)
             .limit(5)
             .all()
    )

    # Format today for filtering
    today_str = today.strftime('%Y-%m-%d')

    return render_template(
        'index.html',
        total_students=total_students,
        total_goals=total_goals,
        upcoming_sessions=upcoming_sessions,
        today_str=today_str
    )


# --------- Calendar View ---------
@routes_bp.route('/calendar')
def calendar():
    """
    Display the interactive calendar page with student selector and optional date filter.
    """
    filter_date = request.args.get('filter_date')
    students    = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    return render_template('calendar.html', students=students, filter_date=filter_date)


# --------- API Endpoint for Calendar Events ---------
@routes_bp.route('/api/events')
def api_events():
    """
    Return JSON list of all active events for calendar.
    """
    events = Event.query.filter_by(active=True).all()
    data = []
    for e in events:
        # combine date and time into ISO strings
        start_dt = datetime.combine(e.date_of_session, e.time_of_start)
        end_dt   = datetime.combine(e.date_of_session, e.time_of_end)
        data.append({
            'id':         e.event_id,
            'title':      f"{e.event_type}" + (f" - {e.student.first_name} {e.student.last_name}" if e.student else ""),
            'start':      start_dt.isoformat(),
            'end':        end_dt.isoformat(),
            'status':     e.status,
            'plan_notes': e.plan_notes
        })
    return jsonify(data)


# --------- API Endpoints for Creating and Updating Events ---------
@routes_bp.route('/api/events', methods=['POST'])
def create_event():
    """
    Create new Event(s) from posted form-data.
    Supports:
      - Session: Multi-student (creates one event per student)
      - Meeting/Assessment: Single-student (one event)
      - Reminder/Other: Student optional (one event, may have student_id=None)
    """
    event_type     = request.form.get('event_type', 'Session')
    date_str       = request.form['date_of_session']
    start_str      = request.form['time_of_start']
    end_str        = request.form['time_of_end']
    status         = request.form.get('status', 'Scheduled')
    plan_notes     = request.form.get('plan_notes', '')

    # Parse date/time once
    date_obj  = datetime.strptime(date_str, '%Y-%m-%d').date()
    start_obj = datetime.strptime(start_str, '%H:%M').time()
    end_obj   = datetime.strptime(end_str, '%H:%M').time()

    events_created = 0

    if event_type == 'Session':
        student_ids = request.form.getlist('student_ids')
        for sid in student_ids:
            ev = Event(
                student_id      = int(sid),
                event_type      = event_type,
                date_of_session = date_obj,
                time_of_start   = start_obj,
                time_of_end     = end_obj,
                status          = status,
                active          = True,
                plan_notes      = plan_notes
            )
            db.session.add(ev)
            events_created += 1
    elif event_type in ('Meeting', 'Assessment'):
        student_id = request.form.get('student_id')
        if not student_id:
            return jsonify({'error': 'Student required for this event type.'}), 400
        ev = Event(
            student_id      = int(student_id),
            event_type      = event_type,
            date_of_session = date_obj,
            time_of_start   = start_obj,
            time_of_end     = end_obj,
            status          = status,
            active          = True,
            plan_notes      = plan_notes
        )
        db.session.add(ev)
        events_created += 1
    else:  # Reminder, Other, Misc
        student_id = request.form.get('student_id')  # Might be blank
        ev = Event(
            student_id      = int(student_id) if student_id else None,
            event_type      = event_type,
            date_of_session = date_obj,
            time_of_start   = start_obj,
            time_of_end     = end_obj,
            status          = status,
            active          = True,
            plan_notes      = plan_notes
        )
        db.session.add(ev)
        events_created += 1

    db.session.commit()
    return jsonify({'created': events_created}), 201


@routes_bp.route('/api/events/<int:event_id>', methods=['POST'])
def update_event(event_id):
    """
    Update an existing Event from posted form-data.
    """
    ev = Event.query.get_or_404(event_id)

    if 'student_id' in request.form:
        ev.student_id = request.form['student_id']
    if 'event_type' in request.form:
        ev.event_type = request.form['event_type']
    if 'date_of_session' in request.form:
        ev.date_of_session = datetime.strptime(request.form['date_of_session'], '%Y-%m-%d').date()
    if 'time_of_start' in request.form:
        ev.time_of_start = datetime.strptime(request.form['time_of_start'], '%H:%M').time()
    if 'time_of_end' in request.form:
        ev.time_of_end = datetime.strptime(request.form['time_of_end'], '%H:%M').time()
    if 'status' in request.form:
        ev.status = request.form['status']
    if 'plan_notes' in request.form:
        ev.plan_notes = request.form['plan_notes']

    db.session.commit()
    return ('', 200)

@routes_bp.route('/trial_log', methods=['GET', 'POST'])
def trial_log():
    """
    Handle trial log submissions and display objectives for a selected student.
    """

    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()  # for the dropdown
    selected_student_id = request.args.get('student_id')  # when selecting a student via GET

    # ---------- Handling trial submission ----------
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        objective_ids = request.form.getlist('objective_ids')
        date_of_session = request.form.get('date_of_session')
        correct_no_support = request.form.get('correct_no_support', type=int, default=0)
        correct_visual_cue = request.form.get('correct_visual_cue', type=int, default=0)
        correct_verbal_cue = request.form.get('correct_verbal_cue', type=int, default=0)
        correct_visual_verbal_cue = request.form.get('correct_visual_verbal_cue', type=int, default=0)
        correct_modeling = request.form.get('correct_modeling', type=int, default=0)
        incorrect = request.form.get('incorrect', type=int, default=0)
        notes = request.form.get('notes', '')

        # New support-level fields (2024-06)
        independent = request.form.get('independent', type=int, default=0)
        minimal_support = request.form.get('minimal_support', type=int, default=0)
        moderate_support = request.form.get('moderate_support', type=int, default=0)
        maximal_support = request.form.get('maximal_support', type=int, default=0)
        incorrect_new = request.form.get('incorrect_new', type=int, default=0)

        # Loop through each selected objective and save trial log
        for objective_id in objective_ids:
            trial_log = TrialLog(
                student_id=student_id,
                objective_id=objective_id,
                date_of_session=datetime.strptime(date_of_session, '%Y-%m-%d').date(),
                correct_no_support=correct_no_support,
                correct_visual_cue=correct_visual_cue,
                correct_verbal_cue=correct_verbal_cue,
                correct_visual_verbal_cue=correct_visual_verbal_cue,
                correct_modeling=correct_modeling,
                incorrect=incorrect,
                notes=notes,
                # New support-level fields (2024-06)
                independent=independent,
                minimal_support=minimal_support,
                moderate_support=moderate_support,
                maximal_support=maximal_support,
                incorrect_new=incorrect_new
            )
            db.session.add(trial_log)

        db.session.commit()
        flash('Trial log(s) submitted successfully!', 'success')
        return redirect(url_for('routes.trial_log'))

    # ---------- Handling objective fetching for selected student ----------
    objectives = []
    if selected_student_id:
        try:
            selected_student_id_int = int(selected_student_id)  # Convert to int for query
            print("Selected student ID:", selected_student_id_int)  # TEMP DEBUGGING
            objectives = Objective.query.filter(
                Objective.goal.has(Goal.student_id == selected_student_id_int),
                Objective.active
            ).all()
            print(f"Objectives found: {len(objectives)}")  # TEMP DEBUGGING
        except ValueError:
            print("Invalid student ID received:", selected_student_id)
            objectives = []

    return render_template(
        'trial_log.html',
        students=students,
        objectives=objectives,
        today=datetime.utcnow().date(),
        selected_student_id=selected_student_id
    )
  
@routes_bp.route('/add_student', methods=['GET', 'POST'])
def add_student():
    """
    Add a new student.
    """
    if request.method == 'POST':
        first_name       = request.form.get('first_name', '').strip()
        last_name        = request.form.get('last_name', '').strip()
        grade_level      = request.form.get('grade_level', '').strip()
        preferred_name   = request.form.get('preferred_name', '').strip()
        pronouns         = request.form.get('pronoun', '').strip()
        monthly_services = request.form.get('monthly_services', '').strip()

        new_student = Student(
            first_name       = first_name,
            last_name        = last_name,
            grade            = grade_level,
            preferred_name   = preferred_name,
            pronouns         = pronouns,
            monthly_services = monthly_services
        )
        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('add_student.html')

@routes_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    """
    Edit an existing student's details, including goals and objectives.
    """

    student = Student.query.get_or_404(student_id)
    goals = Goal.query.filter_by(student_id=student_id).all()
    objectives = Objective.query.join(Goal).filter(Goal.student_id == student_id).all()

    if request.method == 'POST':
        student.first_name = request.form['first_name']
        student.last_name = request.form['last_name']
        student.grade = request.form['grade_level']
        student.pronouns = request.form['pronoun']  # Updated to use "pronoun"
        student.preferred_name = request.form.get('preferred_name', student.preferred_name)
        student.monthly_services = request.form['monthly_services']

        for goal in goals:
            goal_key = f'goal_{goal.goal_id}'
            if goal_key in request.form:
                goal.goal_description = request.form[goal_key]

        for objective in objectives:
            obj_key = f'objective_{objective.objective_id}'
            if obj_key in request.form:
                objective.objective_description = request.form[obj_key]

        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('routes.index'))

    return render_template('edit_student.html', student=student, goals=goals, objectives=objectives)

@routes_bp.route('/delete_student/<int:student_id>')
def delete_student(student_id):
    """
    Archive (soft-delete) a student by marking them as inactive.
    """

    student = Student.query.get_or_404(student_id)
    student.active = False
    db.session.commit()
    flash('Student archived (soft-deleted) successfully!', 'success')
    return redirect(url_for('routes.index'))


@routes_bp.route('/sessions')
def sessions():
    filter_date = request.args.get('filter_date')
    filter_student = request.args.get('filter_student', type=int)
    filter_status = request.args.get('filter_status')

    # Query active students for the student dropdown
    students = Student.query.filter_by(active=True).order_by(Student.last_name.asc(), Student.first_name.asc()).all()

    # Build the base query for sessions
    base_q = Event.query.filter_by(active=True, event_type='Session')
    if filter_date:
        base_q = base_q.filter_by(date_of_session=filter_date)
    if filter_student:
        base_q = base_q.filter_by(student_id=filter_student)
    if filter_status:
        base_q = base_q.filter_by(status=filter_status)

    events = base_q.order_by(Event.time_of_start).all()

    return render_template(
        'sessions.html',
        sessions=events,
        filter_date=filter_date,
        filter_student=filter_student,
        filter_status=filter_status,
        students=students
    )
  

@routes_bp.route('/add_goal/<int:student_id>', methods=['GET', 'POST'])
def add_goal(student_id):
    """
    Add a new goal for a specific student, optionally with an initial objective.
    """

    student = Student.query.filter_by(student_id=student_id, active=True).first_or_404()
    if request.method == 'POST':
        goal_description = request.form['goal_description']
        first_objective = request.form.get('first_objective')

        # Create goal
        new_goal = Goal(student_id=student.student_id, goal_description=goal_description)
        db.session.add(new_goal)
        db.session.commit()

        # If an objective was added, create and link it
        if first_objective:
            new_objective = Objective(goal_id=new_goal.goal_id, objective_description=first_objective)
            db.session.add(new_objective)
            db.session.commit()

        flash('Goal added successfully!', 'success')
        return redirect(url_for('routes.edit_student', student_id=student.student_id))

    return render_template('add_goal.html', student=student)

@routes_bp.route('/add_objective/<int:goal_id>', methods=['GET', 'POST'])
def add_objective(goal_id):
  """
  Add an objective for a specific goal.
  """
  goal = Goal.query.get_or_404(goal_id)
  if request.method == 'POST':
    objective_description = request.form['objective_description']
    with_accuracy = request.form.get('with_accuracy', '')  # Optional
    
    new_objective = Objective(
      goal_id=goal.goal_id,
      objective_description=objective_description,
      with_accuracy=with_accuracy
    )
    db.session.add(new_objective)
    db.session.commit()
    flash('Objective added successfully!', 'success')
    
    # Redirect to student edit page after adding objective
    return redirect(url_for('routes.edit_student', student_id=goal.student.student_id))
  
  return render_template('add_objective.html', goal=goal)

@routes_bp.route('/edit_objective/<int:objective_id>', methods=['GET', 'POST'])
def edit_objective(objective_id):
    """
    Edit an existing objective.
    """

    objective = Objective.query.get_or_404(objective_id)
    if request.method == 'POST':
        objective.objective_description = request.form['objective_description']
        objective.with_accuracy = request.form['with_accuracy']
        db.session.commit()
        flash('Objective updated successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('edit_objective.html', objective=objective)

@routes_bp.route('/delete_objective/<int:objective_id>', methods=['POST'])
def delete_objective(objective_id):
    """
    Delete an objective from the database.
    """

    objective = Objective.query.get_or_404(objective_id)
    db.session.delete(objective)
    db.session.commit()
    flash('Objective deleted successfully!', 'success')
    return redirect(url_for('routes.index'))

@routes_bp.route('/edit_goal/<int:goal_id>', methods=['GET', 'POST'])
def edit_goal(goal_id):
    """
    Edit an existing goal.
    """

    goal = Goal.query.get_or_404(goal_id)
    if request.method == 'POST':
        goal.goal_description = request.form['goal_description']
        db.session.commit()
        flash('Goal updated successfully!', 'success')
        return redirect(url_for('routes.edit_student', student_id=goal.student_id))
    return render_template('edit_goal.html', goal=goal)


@routes_bp.route('/delete_goal/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    """
    Delete a goal from the database.
    """
    goal = Goal.query.get_or_404(goal_id)
    db.session.delete(goal)
    db.session.commit()
    flash('Goal deleted successfully!', 'success')
    return redirect(url_for('routes.index'))


# --------- Archive Goal (Soft Delete) ---------
@routes_bp.route('/archive_goal/<int:goal_id>', methods=['POST'])
def archive_goal(goal_id):
    """
    Archive (soft-delete) a goal and its objectives by marking them inactive.
    """
    goal = Goal.query.get_or_404(goal_id)
    goal.active = False
    # Objectives will be archived via cascade
    db.session.commit()
    flash('Goal archived successfully!', 'success')
    return redirect(url_for('routes.edit_student', student_id=goal.student_id))



@routes_bp.route('/student_search', methods=['GET'])
def student_search():
    """
    Search for students by first or last name.
    """

    query = request.args.get('q')
    students = []
    if query:
        students = Student.query.filter(
            ((Student.first_name.ilike(f'%{query}%')) |
             (Student.last_name.ilike(f'%{query}%'))) &
            (Student.active)
        ).all()

    return render_template('student_search.html', students=students, query=query)

@routes_bp.route('/student/<int:student_id>/trial_logs')
def student_trial_logs(student_id):
    student = Student.query.get_or_404(student_id)
    trial_logs = (
    TrialLog.query
        .filter_by(student_id=student_id)
        .options(joinedload(TrialLog.objective))
        .order_by(TrialLog.date_of_session.desc())
        .all()
  )

    legacy_logs = [log for log in trial_logs if log.uses_legacy_system()]
    new_logs = [log for log in trial_logs if log.uses_new_system()]

    return render_template(
        'student_trial_logs.html',
        student=student,
        legacy_logs=legacy_logs,
        new_logs=new_logs
    )  

@routes_bp.route('/soap_note', methods=['GET', 'POST'])
def soap_note():
    """
    Generate a SOAP note for a student session, including S, O, A, and P sections.
    """

    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()

    # Handle selected student for filtering
    selected_student_id = request.args.get('student_id', type=int)
    selected_student = Student.query.get(selected_student_id) if selected_student_id else None

    # Monthly services display
    monthly_services = selected_student.monthly_services if selected_student and selected_student.monthly_services else "Not specified"

    # Session count for the current month
    session_count = 0  # Default if no student is selected
    if selected_student:
        current_month = datetime.now().month
        current_year = datetime.now().year
        session_count = (
            Event.query
                .filter(
                    Event.event_type == "Session",
                    Event.active == True,
                    Event.student_id == selected_student_id,
                    extract('month', Event.date_of_session) == current_month,
                    extract('year',  Event.date_of_session) == current_year,
                    Event.status.in_(["Completed", "Excused Absence"])
                )
                .count()
        )

    # Filter objectives if student selected
    if selected_student_id:
        objectives = Objective.query.join(Goal).filter(
            Goal.student_id == selected_student_id, Objective.active
        ).all()
    else:
        objectives = []

    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    current_month_str = datetime.now().strftime('%B')
    # Load activities for the SOAP Note form
    activities = Activity.query.filter_by(active=True).order_by(Activity.name).all()

    if request.method == 'POST':
        # Fetch form data
        student_id = request.form.get('student_id')
        student = Student.query.get(student_id) if student_id else None  # Needed for pronouns and name

        month = request.form.get('month')
        session_number = request.form.get('session_number')
        total_sessions = request.form.get('total_sessions')
        performance = request.form.get('performance')
        additional_s = request.form.get('additional_S')

        # New: Session Type dropdown (defaults to Individual)
        session_type = request.form.get('session_type', 'Individual')

        # Activity dropdown with custom option restored
        activity = request.form.get('activity') if request.form.get('activity') != 'Other' else request.form.get('activity_other')

        # Objective dropdown with custom option restored
        objective = request.form.get('objective') if request.form.get('objective') != 'Other' else request.form.get('objective_other')

        accuracy = request.form.get('accuracy')

        # Support level dropdown with custom option restored
        support_level = request.form.get('support_level')
        if support_level == 'Other':
            support_level = request.form.get('support_level_other', 'with support')

        additional_O = request.form.get('additional_O')

        # Gather visual and verbal cues, including "Other" input if provided
        visual_cues = request.form.getlist('visual_cues')
        visual_cues_other = request.form.get('visual_cues_other', '').strip()
        if visual_cues_other:
            visual_cues.append(visual_cues_other)

        verbal_cues = request.form.getlist('verbal_cues')
        verbal_cues_other = request.form.get('verbal_cues_other', '').strip()
        if verbal_cues_other:
            verbal_cues.append(verbal_cues_other)

        # Proper formatting for cue lists
        def format_list(items):
            if len(items) == 1:
                return items[0].lower()
            elif len(items) == 2:
                return f"{items[0].lower()} and {items[1].lower()}"
            else:
                return f"{', '.join(item.lower() for item in items[:-1])}, and {items[-1].lower()}"

        visual_cues_formatted = format_list(visual_cues) if visual_cues else 'N/A'
        verbal_cues_formatted = format_list(verbal_cues) if verbal_cues else 'N/A'

        # Enhanced Pronoun Handling
        pronoun_map = {
            "he/him": ("he", "his", "him"),
            "she/her": ("she", "her", "her"),
            "they/them": ("they", "their", "them"),
            "other": ("they", "their", "them")
        }

        if student and student.pronouns:
            pronoun_key = student.pronouns.lower().strip()
            if pronoun_key not in pronoun_map:
                if "she" in pronoun_key:
                    pronoun_key = "she/her"
                elif "he" in pronoun_key:
                    pronoun_key = "he/him"
                else:
                    pronoun_key = "they/them"
        else:
            pronoun_key = "they/them"

        pronoun_subject, pronoun_possessive, pronoun_object = pronoun_map.get(pronoun_key, ("they", "their", "them"))
        verb_be = "was" if pronoun_subject in ["he", "she"] else "were"

        # Formatted SOAP Note Sections
        # S Section with Session Type and corrected possessive pronoun
        s_note = f"{month} Session {session_number}/{total_sessions}: {student.first_name} attended {pronoun_possessive} {session_type.lower()} speech therapy session. {pronoun_subject.capitalize()} {verb_be} {performance}."
        if additional_s:
            s_note += f" {additional_s}"

        # O Section
        o_note = f"{pronoun_subject.capitalize()} {verb_be} given {activity.lower()}. {pronoun_subject.capitalize()} {verb_be} able to {objective} with {accuracy}% accuracy {support_level}."
        if additional_O:
            o_note += f" {additional_O}"

        # A Section (adaptive wording based on what's filled)
        if visual_cues and verbal_cues:
            a_note = f"{pronoun_subject.capitalize()} benefited from visual and verbal cues. Visual cues included {visual_cues_formatted}. Verbal cues included {verbal_cues_formatted}."
        elif visual_cues:
            a_note = f"{pronoun_subject.capitalize()} benefited from visual cues. Visual cues included {visual_cues_formatted}."
        elif verbal_cues:
            a_note = f"{pronoun_subject.capitalize()} benefited from verbal cues. Verbal cues included {verbal_cues_formatted}."
        else:
            a_note = f"{pronoun_subject.capitalize()} did not require visual or verbal cues during this session."

        p_note = "Continue to target IEP goals. -Sean Hendricks, MA CCC-SLP"

        # Compose full_note for saving
        full_note = f"S: {s_note}\nO: {o_note}\nA: {a_note}\nP: {p_note}"

        # Determine selected_date for passing to template
        selected_date = datetime.now().date()

        return render_template(
            'soap_note_result.html',
            student_id=selected_student_id,
            note_date=selected_date.isoformat(),
            s_note=s_note,
            o_note=o_note,
            a_note=a_note,
            p_note=p_note,
            full_note=full_note
        )

    return render_template(
        'soap_note.html',
        students=students,
        objectives=objectives,
        months=months,
        current_month=current_month_str,
        selected_student=selected_student,
        monthly_services=monthly_services,
        session_count=session_count,
        activities=activities
    )


# --------- SOAP Note Database Routes ---------
@routes_bp.route('/soap_note/add', methods=['POST'])
def add_soap_note():
    """
    Handle the “Add to Database” form submission from soap_note_result.html.
    Expects: student_id (int), optional note_date (YYYY-MM-DD), full_note (text).
    """
    student_id = request.form.get('student_id', type=int)
    note_date_str  = request.form.get('note_date')
    full_note  = request.form.get('full_note', '').strip()

    # student_id and full_note are required; note_date is optional
    if not student_id or not full_note:
        flash('Missing required fields; note was not saved.', 'warning')
        return redirect(url_for('routes.soap_note'))

    # Determine note_date: if provided, parse; otherwise use today
    if note_date_str:
        try:
            note_dt = datetime.strptime(note_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format; note was not saved.', 'danger')
            return redirect(url_for('routes.soap_note'))
    else:
        note_dt = date.today()

    new_note = SoapNote(
        student_id=student_id,
        note_date=note_dt,
        note_text=full_note
    )
    db.session.add(new_note)
    db.session.commit()

    flash('SOAP note saved successfully.', 'success')
    return redirect(url_for('routes.view_soap_notes'))


@routes_bp.route('/soap_notes/bulk_add', methods=['GET', 'POST'])
def bulk_add_soap():
    """
    Bulk-create one SOAP note at a time for a selected student and date.
    """
    # Fetch active students for the dropdown
    students = Student.query.filter_by(active=True).order_by(
        Student.last_name, Student.first_name
    ).all()

    if request.method == 'POST':
        # Retrieve form fields by name
        student_id_str = request.form.get('student_id')
        note_date_str = request.form.get('note_date')
        note_text = request.form.get('note_text', '').strip()

        # Validate presence
        if not student_id_str or not note_date_str or not note_text:
            flash('All fields are required.', 'warning')
            return redirect(url_for('routes.bulk_add_soap'))

        # Convert student_id to integer
        try:
            student_id = int(student_id_str)
        except ValueError:
            flash('Invalid student selection.', 'danger')
            return redirect(url_for('routes.bulk_add_soap'))

        # Parse note_date
        try:
            note_dt = datetime.strptime(note_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash(f'Invalid date format: {note_date_str}', 'danger')
            return redirect(url_for('routes.bulk_add_soap'))

        # Create and commit new SoapNote
        try:
            new_note = SoapNote(
                student_id=student_id,
                note_date=note_dt,
                note_text=note_text
            )
            db.session.add(new_note)
            db.session.commit()
            flash(f'Successfully added SOAP note for {note_date_str}.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding SOAP note: {str(e)}', 'danger')

        # Redirect back to the form for another entry
        return redirect(url_for('routes.bulk_add_soap'))

    # On GET, render the blank form
    return render_template('bulk_add_soap.html', students=students)


@routes_bp.route('/soap_notes')
def view_soap_notes():
    """
    Display all saved SOAP notes, with optional filters by student and date range.
    """
    filter_student = request.args.get('filter_student', type=int)
    filter_start_date = request.args.get('start_date')
    filter_end_date   = request.args.get('end_date')

    students = Student.query.filter_by(active=True).order_by(Student.last_name, Student.first_name).all()

    query = SoapNote.query.join(SoapNote.student)
    if filter_student:
        query = query.filter(SoapNote.student_id == filter_student)
    if filter_start_date:
        try:
            dt1 = datetime.strptime(filter_start_date, '%Y-%m-%d').date()
            query = query.filter(SoapNote.note_date >= dt1)
        except ValueError:
            flash('Invalid start date format.', 'warning')
    if filter_end_date:
        try:
            dt2 = datetime.strptime(filter_end_date, '%Y-%m-%d').date()
            query = query.filter(SoapNote.note_date <= dt2)
        except ValueError:
            flash('Invalid end date format.', 'warning')

    soap_notes = query.order_by(SoapNote.note_date.desc()).all()

    return render_template(
        'view_soap_notes.html',
        soap_notes=soap_notes,
        students=students,
        filter_student=filter_student,
        filter_start_date=filter_start_date,
        filter_end_date=filter_end_date
    )


@routes_bp.route('/soap_notes/export')
def export_soap_notes_csv():
    """
    Return a CSV download of all filtered SOAP notes.
    Accepts same filters: filter_student, start_date, end_date
    """
    filter_student = request.args.get('filter_student', type=int)
    filter_start_date = request.args.get('start_date')
    filter_end_date   = request.args.get('end_date')

    query = SoapNote.query.join(SoapNote.student)
    if filter_student:
        query = query.filter(SoapNote.student_id == filter_student)
    if filter_start_date:
        try:
            dt1 = datetime.strptime(filter_start_date, '%Y-%m-%d').date()
            query = query.filter(SoapNote.note_date >= dt1)
        except ValueError:
            pass
    if filter_end_date:
        try:
            dt2 = datetime.strptime(filter_end_date, '%Y-%m-%d').date()
            query = query.filter(SoapNote.note_date <= dt2)
        except ValueError:
            pass

    soap_notes = query.order_by(SoapNote.note_date.desc()).all()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Note ID', 'Student ID', 'Date', 'Student', 'Note Text'])
    for note in soap_notes:
        first_name = note.student.first_name
        anonymized_text = note.note_text.replace(first_name, str(note.student_id))
        full_name = f"{note.student.first_name} {note.student.last_name}"
        cw.writerow([
            note.soap_note_id,
            note.student_id,
            note.note_date.strftime('%Y-%m-%d'),
            full_name,
            anonymized_text.replace('\n',' ')
        ])
    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition":
                 "attachment; filename=soap_notes.csv"})
@routes_bp.route('/archive_session/<int:event_id>', methods=['POST'])
def archive_event(event_id):
    ev = Event.query.get_or_404(event_id)
    ev.active = False
    db.session.commit()
    flash('Event archived successfully!', 'success')
    # Preserve the current filter by redirecting to the 'next' URL if provided
    next_url = request.form.get('next') or url_for('routes.sessions')
    return redirect(next_url)


# Delete event route
@routes_bp.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    ev = Event.query.get_or_404(event_id)
    db.session.delete(ev)
    db.session.commit()
    flash('Event deleted successfully!', 'success')
    next_url = request.form.get('next') or url_for('routes.sessions')
    return redirect(next_url)

# Update session status route
@routes_bp.route('/update_session_status/<int:event_id>', methods=['POST'])
def update_session_status(event_id):
    ev = Event.query.get_or_404(event_id)
    new_status = request.form.get('status')
    if new_status:
        ev.status = new_status
        db.session.commit()
        flash('Session status updated!', 'success')
    next_url = request.form.get('next') or url_for('routes.sessions')
    return redirect(next_url)
  




@routes_bp.route('/scheduled_sessions_pending')
def scheduled_sessions_pending():
    """
    Display unupdated “Scheduled” sessions.
    """
    sessions = (
        Event.query
             .filter_by(event_type='Session', status='Scheduled', active=True)
             .order_by(Event.date_of_session, Event.time_of_start)
             .all()
    )
    return render_template('scheduled_sessions_pending.html', sessions=sessions)

@routes_bp.route('/reports')
def reports():
    """
    Display the main reports page.
    """

    return render_template('reports.html')

@routes_bp.route('/monthly_sessions_report')
def monthly_sessions_report():
    """
    Generate a monthly sessions report for all active students, with sorting options.
    """

    # Get month and year from query parameters (or default to current)
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    sort_by = request.args.get('sort_by', '')

    # Build a "YYYY-MM" string to match MonthlyQuota.month
    month_str = f"{year}-{month:02d}"

    # Find first day of month and first day of next month
    first_of_month = date(year, month, 1)
    next_month = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    # Fetch all active students
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()

    report_data = []

    for student in students:
        # Try to find a quota entry for this student and month
        quota_entry = MonthlyQuota.query.filter_by(student_id=student.student_id, month=month_str).first()
        if quota_entry:
            expected_sessions = quota_entry.required_sessions
        else:
            # Fallback to student.monthly_services if no quota row
            try:
                expected_sessions = int(student.monthly_services)
            except (TypeError, ValueError):
                expected_sessions = 0

        # Count completed sessions for the current month
        completed_sessions = (
            Event.query
                .filter(
                    Event.student_id == student.student_id,
                    Event.event_type == 'Session',
                    Event.status == 'Completed',
                    Event.is_makeup.is_(False),
                    Event.active.is_(True),
                    extract('month', Event.date_of_session) == month,
                    extract('year',  Event.date_of_session) == year
                )
                .count()
        )

        # Count excused absence sessions for the current month
        excused_sessions = (
            Event.query
                .filter(
                    Event.student_id == student.student_id,
                    Event.event_type == 'Session',
                    Event.status == 'Excused Absence',
                    Event.active.is_(True),
                    extract('month', Event.date_of_session) == month,
                    extract('year',  Event.date_of_session) == year
                )
                .count()
        )

        # Count open "Makeup Needed" flags for the current month
        makeup_needed = (
            Event.query
                .filter(
                    Event.student_id == student.student_id,
                    Event.event_type == 'Session',
                    Event.status == 'Makeup Needed',
                    Event.active.is_(True),
                    extract('month', Event.date_of_session) == month,
                    extract('year',  Event.date_of_session) == year
                )
                .count()
        )

        # Count open "Makeup Needed" sessions from prior months
        total_makeups = (
            Event.query
                .filter(
                    Event.student_id == student.student_id,
                    Event.event_type == 'Session',
                    Event.status == 'Makeup Needed',
                    Event.active.is_(True),
                    Event.date_of_session < first_of_month
                )
                .count()
        )

        # Calculate remaining sessions needed = expected_sessions minus (completed + excused)
        credited = completed_sessions + excused_sessions
        remaining = max(expected_sessions - credited, 0)

        report_data.append({
            'student_name': f"{student.first_name} {student.last_name}",
            'expected_sessions': expected_sessions,
            'completed_sessions': completed_sessions,
            'excused_sessions': excused_sessions,
            'makeup_needed': makeup_needed,
            'remaining_sessions': remaining,
            'total_makeups': total_makeups
        })

    # Sort the report data if sorting is selected
    if sort_by == 'student_az':
        report_data.sort(key=lambda x: x['student_name'])
    elif sort_by == 'student_za':
        report_data.sort(key=lambda x: x['student_name'], reverse=True)
    elif sort_by == 'remaining_desc':
        report_data.sort(key=lambda x: x['remaining_sessions'], reverse=True)
    elif sort_by == 'remaining_asc':
        report_data.sort(key=lambda x: x['remaining_sessions'])
    elif sort_by == 'makeups_desc':
        report_data.sort(key=lambda x: x['total_makeups'], reverse=True)
    elif sort_by == 'makeups_asc':
        report_data.sort(key=lambda x: x['total_makeups'])

    return render_template(
        'monthly_sessions_report.html',
        report_data=report_data,
        month=month,
        year=year,
        sort_by=sort_by
    )
  
@routes_bp.route('/reports/makeup_needed')
def makeup_needed_report():
    """
    Display reports of all Session‐type events with 'Makeup Needed' status,
    both overall and for the current month.
    """
    now = datetime.now()
    current_month = now.month
    current_year = now.year

    sort_by = request.args.get('sort_by', '')
    base_query = Event.query.filter_by(
        event_type='Session',
        status='Makeup Needed',
        active=True
    )
    if sort_by == 'date_asc':
        base_query = base_query.order_by(Event.date_of_session.asc(), Event.time_of_start.asc())
    elif sort_by == 'date_desc':
        base_query = base_query.order_by(Event.date_of_session.desc(), Event.time_of_start.asc())
    elif sort_by == 'student_az':
        base_query = base_query.join(Event.student).order_by(Student.last_name.asc(), Student.first_name.asc())
    elif sort_by == 'student_za':
        base_query = base_query.join(Event.student).order_by(Student.last_name.desc(), Student.first_name.desc())
    elif sort_by == 'status_asc':
        base_query = base_query.order_by(Event.status.asc())
    elif sort_by == 'status_desc':
        base_query = base_query.order_by(Event.status.desc())
    else:
        base_query = base_query.order_by(Event.time_of_start.asc())

    all_makeup_needed = base_query.all()
    this_month_makeup_needed = base_query.filter(
        extract('month', Event.date_of_session) == current_month,
        extract('year', Event.date_of_session) == current_year
    ).all()

    return render_template(
        'makeup_needed_report.html',
        all_makeup_needed=all_makeup_needed,
        this_month_makeup_needed=this_month_makeup_needed,
        current_month=current_month,
        current_year=current_year,
        sort_by=sort_by
    )
  
@routes_bp.route('/trial_logs_by_date', methods=['GET'])
def trial_logs_by_date():
    """
    Display all trial logs for a specific date.
    """

    # Get selected date from query or default to today
    selected_date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format!', 'danger')
        selected_date = datetime.now().date()

    # ✅ Query trial logs for that date using correct field name
    trial_logs = TrialLog.query.filter(
        TrialLog.date_of_session == selected_date
    ).order_by(TrialLog.student_id).all()
    legacy_logs = [log for log in trial_logs if log.uses_legacy_system()]
    new_logs = [log for log in trial_logs if log.uses_new_system()]

    return render_template(
        'trial_logs_by_date.html',
        legacy_logs=legacy_logs,
        new_logs=new_logs,
        selected_date=selected_date_str
    )
  
@routes_bp.route('/quarterly_report', methods=['GET', 'POST'])
def quarterly_report():
    """
    Generate a quarterly progress report for a selected student.
    """

    # Query active students for the dropdown.
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']
    overall_progress_options = ["Significant Progress", "Steady Progress", "Minimal Progress", "Other"]
    closing_sentence_options = [
        "Great work this year! Have a great summer!",
        "Keep up the great work!",
        "We will continue to focus on these skills in the next quarter.",
        "Progress is steady; adjustments will be made next quarter.",
        "Other"
    ]

    selected_student = None

    if request.method == 'POST':
        form_stage = request.form.get('form_stage')
        if form_stage == 'start':
            # Stage 1: Student selected; show full progress form.
            student_id = request.form.get('student_id')
            if student_id:
                selected_student = Student.query.get(student_id)
            else:
                flash("Please select a student.", "danger")
                return render_template('quarterly_report.html', students=students)
            return render_template('quarterly_report.html',
                        students=students,
                        selected_student=selected_student,
                        quarters=quarters,
                        overall_progress_options=overall_progress_options,
                        closing_sentence_options=closing_sentence_options)
        elif form_stage == 'generate':
            # Stage 2: Full form submitted; generate report.
            student_id = request.form.get('student_id')
            if student_id:
                selected_student = Student.query.get(student_id)
            else:
                flash("Please select a student.", "danger")
                return render_template('quarterly_report.html', students=students)

            quarter = request.form.get('quarter')
            overall_progress = request.form.get('overall_progress')
            if overall_progress == 'Other':
                overall_progress = request.form.get('overall_progress_custom')
            closing_sentence = request.form.get('closing_sentence')
            if closing_sentence == 'Other':
                closing_sentence = request.form.get('closing_sentence_custom')

            # Map quarter codes to full text.
            quarter_map = {
                "Q1": "the first quarter",
                "Q2": "the second quarter",
                "Q3": "the third quarter",
                "Q4": "the fourth quarter"
            }
            first_name = selected_student.first_name
            # Use the first part of the pronouns field as the subject pronoun (default to first name if missing).
            subject_pronoun = (selected_student.pronouns.split('/')[0].capitalize()
                        if selected_student.pronouns else first_name)
            overall_progress_text = overall_progress.lower()
            quarter_text = quarter_map.get(quarter, quarter)

            report_paragraphs = []

            # Process each goal separately.
            for goal in selected_student.goals:
                paragraph_lines = []
                # Intro sentence (without goal number).
                intro_sentence = f"{first_name} demonstrated {overall_progress_text} in {quarter_text}."
                paragraph_lines.append(intro_sentence)

                # Process each objective in this goal.
                for obj in goal.objectives:
                    performances = request.form.getlist(f'performance_{obj.objective_id}')
                    supports = request.form.getlist(f'support_{obj.objective_id}')
                    entries = []
                    for perf, supp in zip(performances, supports):
                        if perf.strip():
                            entries.append(
                                f"with {perf}% accuracy {supp.lower()}"
                            )
                    if entries:
                        if len(entries) == 1:
                            performance_text = entries[0]
                        elif len(entries) == 2:
                            performance_text = " and ".join(entries)
                        else:
                            performance_text = (
                                ", ".join(entries[:-1]) + ", and " + entries[-1]
                            )
                        sentence = (
                            f"{subject_pronoun} was able to {obj.objective_description} {performance_text}."
                        )
                        paragraph_lines.append(sentence)

                # Retrieve selected visual and verbal cues for this goal
                visual_cues = request.form.getlist(f"visual_{goal.goal_id}")
                verbal_cues = request.form.getlist(f"verbal_{goal.goal_id}")

                # Append visual cues sentence if any were selected
                if visual_cues:
                    if len(visual_cues) == 1:
                        vc_text = visual_cues[0]
                    elif len(visual_cues) == 2:
                        vc_text = f"{visual_cues[0]} and {visual_cues[1]}"
                    else:
                        vc_text = ", ".join(visual_cues[:-1]) + ", and " + visual_cues[-1]
                    paragraph_lines.append(f"{subject_pronoun.capitalize()} benefited from visual cues, including {vc_text}.")

                # Append verbal cues sentence if any were selected
                if verbal_cues:
                    if len(verbal_cues) == 1:
                        vb_text = verbal_cues[0]
                    elif len(verbal_cues) == 2:
                        vb_text = f"{verbal_cues[0]} and {verbal_cues[1]}"
                    else:
                        vb_text = ", ".join(verbal_cues[:-1]) + ", and " + verbal_cues[-1]
                    paragraph_lines.append(f"{subject_pronoun.capitalize()} benefited from verbal cues, including {vb_text}.")

                paragraph_lines.append(closing_sentence)
                # Join the lines into one paragraph (space-separated, no line breaks).
                report_paragraphs.append(" ".join(paragraph_lines))

            # Instead of joining report_paragraphs into one string, pass the list directly:
            return render_template(
                'quarterly_report_result.html',
                report_paragraphs=report_paragraphs,
                selected_student=selected_student,
                student_id=selected_student.student_id,
                quarter=quarter
            )

    # GET request: show only the student selection form.
    return render_template('quarterly_report.html', students=students)

@routes_bp.route('/bulk_sessions', methods=['GET', 'POST'])
def bulk_sessions():
  """
  Bulk-create one Session event per student for a chosen date.
  """
  students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
  
  if request.method == 'POST':
    # 1) Read and parse the date
    date_str = request.form['session_date']
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # 2) Loop through students, skipping blanks
    for student in students:
      time_key   = f"time_{student.student_id}"
      status_key = f"status_{student.student_id}"
      start_str  = request.form.get(time_key)
      if not start_str:
        continue  # skip any student with no time entered
      
      start_obj  = datetime.strptime(start_str, '%H:%M').time()
      # default 30-minute end
      end_obj    = (datetime.combine(date_obj, start_obj) + timedelta(minutes=30)).time()
      status_val = request.form.get(status_key, 'Scheduled')
      
      ev = Event(
        student_id      = student.student_id,
        event_type      = 'Session',
        date_of_session = date_obj,
        time_of_start   = start_obj,
        time_of_end     = end_obj,
        status          = status_val,
        active          = True,
        plan_notes      = ''
      )
      db.session.add(ev)
      
    db.session.commit()
    flash(f"Created sessions for {date_str}", 'success')
    return redirect(url_for('routes.sessions', filter_date=date_str))
  
  # Only render the form on GET
  return render_template('bulk_sessions.html', students=students)

@routes_bp.route('/student/<int:student_id>/sessions')
def student_sessions(student_id):
    student = Student.query.get_or_404(student_id)

    sessions = (Event.query
                       .filter_by(student_id=student_id, event_type='Session')
                       .order_by(Event.date_of_session.desc(), Event.time_of_start)
                       .all())

    trial_logs = (TrialLog.query
                         .filter_by(student_id=student_id)
                         .order_by(TrialLog.date_of_session.desc())
                         .all())

    # Fetch all active objectives for this student
    objectives = (
        Objective.query
        .join(Goal)
        .filter(Goal.student_id == student_id, Objective.active == True)
        .order_by(Objective.objective_description)
        .all()
    )

    legacy_logs = [log for log in trial_logs if log.uses_legacy_system()]
    new_logs = [log for log in trial_logs if log.uses_new_system()]

    return render_template(
        'student_sessions.html',
        student=student,
        sessions=sessions,
        legacy_logs=legacy_logs,
        new_logs=new_logs,
        objectives=objectives
    )


# --------- Makeups by Month Report ---------
@routes_bp.route('/makeups_by_month')
def makeups_by_month():
    """
    Show a matrix of Makeup Needed session counts per student per month.
    """
    # Get all active students
    students = Student.query.filter_by(active=True).order_by(Student.last_name, Student.first_name).all()

    # Define school year months (adjust years as needed)
    months = [
        ("September", 9), ("October", 10), ("November", 11), ("December", 12),
        ("January", 1), ("February", 2), ("March", 3), ("April", 4),
        ("May", 5), ("June", 6)
    ]
    year_start = 2024  # Adjust to match your school year

    # Prepare: {student_id: {month_name: count}}
    makeups_matrix = defaultdict(lambda: defaultdict(int))

    for student in students:
        for month_name, month_num in months:
            # Jan–June = next year; Sep–Dec = year_start
            year = year_start if month_num >= 9 else year_start + 1
            first_day = f"{year}-{month_num:02d}-01"
            last_day = f"{year}-{month_num:02d}-{monthrange(year, month_num)[1]}"
            count = (
                Event.query
                .filter_by(student_id=student.student_id, status="Makeup Needed", active=1)
                .filter(Event.date_of_session >= first_day)
                .filter(Event.date_of_session <= last_day)
                .count()
            )
            makeups_matrix[student.student_id][month_name] = count

    return render_template(
        "makeups_by_month.html",
        students=students,
        months=[name for name, _ in months],
        makeups_matrix=makeups_matrix
    )

@routes_bp.route('/students')
def students():
    """
    List all active students, with optional grade filter.
    """
    grade_filter = request.args.get('grade')
    if grade_filter:
        students = Student.query.filter_by(active=True, grade=grade_filter)\
                               .order_by(Student.first_name).all()
    else:
        students = Student.query.filter_by(active=True)\
                               .order_by(Student.first_name).all()
    return render_template('students.html',
                           students=students,
                           grade_filter=grade_filter)


# --------- Student Info Route ---------
@routes_bp.route('/student/<int:student_id>')
def student_info(student_id):
    """
    Display detailed information for a single student, including goals and objectives.
    """
    student = Student.query.get_or_404(student_id)
    goals = Goal.query.filter_by(student_id=student_id).all()
    objectives = Objective.query.join(Goal).filter(Goal.student_id == student_id).all()
    return render_template(
        'student_info.html',
        student=student,
        goals=goals,
        objectives=objectives
    )


# --------- Save Quarterly Report Route ---------
@routes_bp.route('/save_quarterly_report', methods=['POST'])
def save_quarterly_report():
    student_id = request.form.get('student_id', type=int)
    quarter = request.form.get('quarter', '')
    # Gather all paragraphs from the form
    paragraphs = request.form.getlist('paragraphs')
    # Combine into one text block with double line breaks
    report_text = "\n\n".join(paragraphs)
    # Append signature to saved report
    signature = "\n\n- Sean Hendricks, MA CCC-SLP MD License #07304"
    report_text_with_signature = report_text + signature

    # Create and save the QuarterlyReport record
    new_report = QuarterlyReport(
        student_id=student_id,
        quarter=quarter,
        report_text=report_text_with_signature
    )
    db.session.add(new_report)
    db.session.commit()

    flash('Quarterly report saved successfully.', 'success')
    return redirect(url_for('routes.quarterly_report'))


# --------- Activity CRUD Routes ---------
@routes_bp.route('/activities')
def activities():
    """
    List all active activities.
    """
    activities = Activity.query.filter_by(active=True).order_by(Activity.name).all()
    return render_template('activities.html', activities=activities)

@routes_bp.route('/activities/add', methods=['GET', 'POST'])
def add_activity():
    """
    Add a new activity.
    """
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
    """
    Edit an existing activity.
    """
    act = Activity.query.get_or_404(activity_id)
    if request.method == 'POST':
        act.name = request.form.get('name', act.name).strip()
        db.session.commit()
        flash('Activity updated.', 'success')
        return redirect(url_for('routes.activities'))
    return render_template('edit_activity.html', activity=act)


@routes_bp.route('/activities/delete/<int:activity_id>', methods=['POST'])
def delete_activity(activity_id):
    """
    Soft-delete (archive) an activity.
    """
    act = Activity.query.get_or_404(activity_id)
    act.active = False
    db.session.commit()
    flash('Activity archived.', 'warning')
    return redirect(url_for('routes.activities'))

@routes_bp.route('/quarterly_report_history', methods=['GET'])
def quarterly_report_history():
    """
    Display filters to select a student and/or quarter and show matching quarterly reports.
    """
    # Fetch all active students for the dropdown
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    # Fetch distinct quarter values from existing reports
    quarters = [q[0] for q in db.session.query(QuarterlyReport.quarter).distinct().order_by(QuarterlyReport.quarter).all()]

    # Read optional filters from query parameters
    student_id = request.args.get('student_id', type=int)
    selected_quarter = request.args.get('quarter', type=str)
    selected_student = None

    # Build base query
    query = QuarterlyReport.query

    if student_id:
        selected_student = Student.query.get_or_404(student_id)
        query = query.filter_by(student_id=student_id)

    if selected_quarter:
        query = query.filter_by(quarter=selected_quarter)

    # Execute query, ordering by quarter and creation date
    reports = query.order_by(QuarterlyReport.quarter, QuarterlyReport.date_created).all()

    return render_template(
        'quarterly_report_history.html',
        students=students,
        quarters=quarters,
        selected_student=selected_student,
        selected_quarter=selected_quarter,
        reports=reports
    )


# Context processor to inject current_date into all templates
@routes_bp.app_context_processor
def inject_current_date():
    return {'current_date': date.today().isoformat()}
