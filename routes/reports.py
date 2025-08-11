from datetime import datetime, date, timedelta
from collections import defaultdict
from calendar import monthrange

from flask import request, render_template, flash, redirect, url_for
from sqlalchemy import extract

from . import routes_bp
from models import (
    Student, TrialLog, Event, Goal, Objective, MonthlyQuota,
    QuarterlyReport, db
)


@routes_bp.route('/reports')
def reports():
    return render_template('reports.html')


@routes_bp.route('/monthly_sessions_report')
def monthly_sessions_report():
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    sort_by = request.args.get('sort_by', '')

    month_str = f"{year}-{month:02d}"
    first_of_month = date(year, month, 1)
    next_month = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()

    report_data = []
    for student in students:
        quota_entry = MonthlyQuota.query.filter_by(student_id=student.student_id, month=month_str).first()
        if quota_entry:
            expected_sessions = quota_entry.required_sessions
        else:
            try:
                expected_sessions = int(student.monthly_services)
            except (TypeError, ValueError):
                expected_sessions = 0

        status_counts = dict(
            db.session.query(Event.status, db.func.count())
            .filter(
                Event.student_id == student.student_id,
                Event.event_type == 'Session',
                Event.active.is_(True),
                Event.is_makeup.is_(False),
                extract('month', Event.date_of_session) == month,
                extract('year', Event.date_of_session) == year,
            )
            .group_by(Event.status)
            .all()
        )

        completed_sessions = status_counts.get('Completed', 0)
        excused_sessions = status_counts.get('Excused Absence', 0)
        makeup_needed = status_counts.get('Makeup Needed', 0)

        total_makeups = (
            Event.query
            .filter(
                Event.student_id == student.student_id,
                Event.event_type == 'Session',
                Event.status == 'Makeup Needed',
                Event.active.is_(True),
                Event.date_of_session < first_of_month,
            )
            .count()
        )

        credited = completed_sessions + excused_sessions
        remaining = max(expected_sessions - credited, 0)

        report_data.append({
            'student_name': f"{student.first_name} {student.last_name}",
            'expected_sessions': expected_sessions,
            'completed_sessions': completed_sessions,
            'excused_sessions': excused_sessions,
            'makeup_needed': makeup_needed,
            'remaining_sessions': remaining,
            'total_makeups': total_makeups,
        })

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
        month=month,
        year=year,
        report_data=report_data,
        sort_by=sort_by,
    )


@routes_bp.route('/reports/makeup_needed')
def makeup_needed_report():
    now = datetime.now()
    current_month = now.month
    current_year = now.year

    sort_by = request.args.get('sort_by', '')
    base_query = Event.query.filter_by(
        event_type='Session',
        status='Makeup Needed',
        active=True,
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
        extract('year', Event.date_of_session) == current_year,
    ).all()

    return render_template(
        'makeup_needed_report.html',
        all_makeup_needed=all_makeup_needed,
        this_month_makeup_needed=this_month_makeup_needed,
        current_month=current_month,
        current_year=current_year,
        sort_by=sort_by,
    )


@routes_bp.route('/trial_logs_by_date', methods=['GET'])
def trial_logs_by_date():
    selected_date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format!', 'danger')
        selected_date = datetime.now().date()

    trial_logs = TrialLog.query.filter(
        TrialLog.date_of_session == selected_date
    ).order_by(TrialLog.student_id).all()
    legacy_logs = [log for log in trial_logs if log.uses_legacy_system()]
    new_logs = [log for log in trial_logs if log.uses_new_system()]

    return render_template(
        'trial_logs_by_date.html',
        legacy_logs=legacy_logs,
        new_logs=new_logs,
        selected_date=selected_date_str,
    )


@routes_bp.route('/quarterly_report', methods=['GET', 'POST'])
def quarterly_report():
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']
    overall_progress_options = ['Significant Progress', 'Steady Progress', 'Minimal Progress', 'Other']
    closing_sentence_options = [
        'Great work this year! Have a great summer!',
        'Keep up the great work!',
        'We will continue to focus on these skills in the next quarter.',
        'Progress is steady; adjustments will be made next quarter.',
        'Other',
    ]

    selected_student = None

    if request.method == 'POST':
        form_stage = request.form.get('form_stage')
        if form_stage == 'start':
            student_id = request.form.get('student_id')
            if student_id:
                selected_student = Student.query.get(student_id)
            else:
                flash('Please select a student.', 'danger')
                return render_template('quarterly_report.html', students=students)
            # Only include active goals for the selected student
            goals = [g for g in selected_student.goals if getattr(g, 'active', True)]
            return render_template(
                'quarterly_report.html',
                students=students,
                selected_student=selected_student,
                quarters=quarters,
                overall_progress_options=overall_progress_options,
                closing_sentence_options=closing_sentence_options,
                goals=goals
            )
        elif form_stage == 'generate':
            student_id = request.form.get('student_id')
            if student_id:
                selected_student = Student.query.get(student_id)
            else:
                flash('Please select a student.', 'danger')
                return render_template('quarterly_report.html', students=students)

            quarter = request.form.get('quarter')
            overall_progress = request.form.get('overall_progress')
            if overall_progress == 'Other':
                overall_progress = request.form.get('overall_progress_custom')
            closing_sentence = request.form.get('closing_sentence')
            if closing_sentence == 'Other':
                closing_sentence = request.form.get('closing_sentence_custom')

            quarter_map = {
                'Q1': 'the first quarter',
                'Q2': 'the second quarter',
                'Q3': 'the third quarter',
                'Q4': 'the fourth quarter',
            }
            first_name = selected_student.first_name
            subject_pronoun = (
                selected_student.pronouns.split('/')[0].capitalize()
                if selected_student.pronouns else first_name
            )
            overall_progress_text = overall_progress.lower()
            quarter_text = quarter_map.get(quarter, quarter)

            # Only include active goals
            goals = [g for g in selected_student.goals if getattr(g, 'active', True)]
            report_paragraphs = []
            for goal in goals:
                paragraph_lines = []
                intro_sentence = f"{first_name} demonstrated {overall_progress_text} in {quarter_text}."
                paragraph_lines.append(intro_sentence)

                for obj in goal.objectives:
                    performances = request.form.getlist(f'performance_{obj.objective_id}')
                    supports = request.form.getlist(f'support_{obj.objective_id}')
                    entries = []
                    for perf, supp in zip(performances, supports):
                        if perf.strip():
                            entries.append(f"with {perf}% accuracy {supp.lower()}")
                    if entries:
                        if len(entries) == 1:
                            performance_text = entries[0]
                        elif len(entries) == 2:
                            performance_text = ' and '.join(entries)
                        else:
                            performance_text = (
                                ', '.join(entries[:-1]) + ', and ' + entries[-1]
                            )
                        sentence = (
                            f"{subject_pronoun} was able to {obj.objective_description} {performance_text}."
                        )
                        paragraph_lines.append(sentence)

                visual_cues = request.form.getlist(f"visual_{goal.goal_id}")
                verbal_cues = request.form.getlist(f"verbal_{goal.goal_id}")

                if visual_cues:
                    if len(visual_cues) == 1:
                        vc_text = visual_cues[0]
                    elif len(visual_cues) == 2:
                        vc_text = f"{visual_cues[0]} and {visual_cues[1]}"
                    else:
                        vc_text = ', '.join(visual_cues[:-1]) + ', and ' + visual_cues[-1]
                    paragraph_lines.append(f"{subject_pronoun.capitalize()} benefited from visual cues, including {vc_text}.")

                if verbal_cues:
                    if len(verbal_cues) == 1:
                        vb_text = verbal_cues[0]
                    elif len(verbal_cues) == 2:
                        vb_text = f"{verbal_cues[0]} and {verbal_cues[1]}"
                    else:
                        vb_text = ', '.join(verbal_cues[:-1]) + ', and ' + verbal_cues[-1]
                    paragraph_lines.append(f"{subject_pronoun.capitalize()} benefited from verbal cues, including {vb_text}.")

                paragraph_lines.append(closing_sentence)
                report_paragraphs.append(' '.join(paragraph_lines))

            return render_template(
                'quarterly_report_result.html',
                report_paragraphs=report_paragraphs,
                selected_student=selected_student,
                student_id=selected_student.student_id,
                quarter=quarter,
            )

    return render_template('quarterly_report.html', students=students)


@routes_bp.route('/makeups_by_month')
def makeups_by_month():
    students = Student.query.filter_by(active=True).order_by(Student.last_name, Student.first_name).all()
    months = [
        ('September', 9), ('October', 10), ('November', 11), ('December', 12),
        ('January', 1), ('February', 2), ('March', 3), ('April', 4),
        ('May', 5), ('June', 6)
    ]
    year_start = 2024

    makeups_matrix = defaultdict(lambda: defaultdict(int))
    for student in students:
        for month_name, month_num in months:
            year = year_start if month_num >= 9 else year_start + 1
            first_day = f"{year}-{month_num:02d}-01"
            last_day = f"{year}-{month_num:02d}-{monthrange(year, month_num)[1]}"
            count = (
                Event.query
                .filter_by(student_id=student.student_id, status='Makeup Needed', active=1)
                .filter(Event.date_of_session >= first_day)
                .filter(Event.date_of_session <= last_day)
                .count()
            )
            makeups_matrix[student.student_id][month_name] = count

    return render_template(
        'makeups_by_month.html',
        students=students,
        months=[name for name, _ in months],
        makeups_matrix=makeups_matrix,
    )


@routes_bp.route('/save_quarterly_report', methods=['POST'])
def save_quarterly_report():
    student_id = request.form.get('student_id', type=int)
    quarter = request.form.get('quarter', '')
    paragraphs = request.form.getlist('paragraphs')
    report_text = '\n\n'.join(paragraphs)
    signature = '\n\n- Sean Hendricks, MA CCC-SLP MD License #07304'
    report_text_with_signature = report_text + signature

    new_report = QuarterlyReport(
        student_id=student_id,
        quarter=quarter,
        report_text=report_text_with_signature,
    )
    db.session.add(new_report)
    db.session.commit()

    flash('Quarterly report saved successfully.', 'success')
    return redirect(url_for('routes.quarterly_report'))


@routes_bp.route('/quarterly_report_history', methods=['GET'])
def quarterly_report_history():
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    quarters = [q[0] for q in db.session.query(QuarterlyReport.quarter).distinct().order_by(QuarterlyReport.quarter).all()]

    student_id = request.args.get('student_id', type=int)
    selected_quarter = request.args.get('quarter', type=str)
    selected_student = None

    query = QuarterlyReport.query
    if student_id:
        selected_student = Student.query.get_or_404(student_id)
        query = query.filter_by(student_id=student_id)
    if selected_quarter:
        query = query.filter_by(quarter=selected_quarter)

    reports = query.order_by(QuarterlyReport.quarter, QuarterlyReport.date_created).all()

    return render_template(
        'quarterly_report_history.html',
        students=students,
        quarters=quarters,
        selected_student=selected_student,
        selected_quarter=selected_quarter,
        reports=reports,
    )
