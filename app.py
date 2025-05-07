from flask import Flask, render_template, request, redirect, url_for, flash # type: ignore
from flask_sqlalchemy import SQLAlchemy # type: ignore
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key' # Change this!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_center.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Add this after creating the Flask app
@app.context_processor
def utility_processor():
    return {'current_year': datetime.now().year}

# --- Database Models ---

class TestType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    default_duration_minutes = db.Column(db.Integer, default=180)
    technical_requirements = db.Column(db.Text, nullable=True)
    staffing_needs_description = db.Column(db.Text, nullable=True)
    admin_manual_link = db.Column(db.String(255), nullable=True)
    training_materials_link = db.Column(db.String(255), nullable=True)
    requires_readiness_check = db.Column(db.Boolean, default=False)
    readiness_check_details = db.Column(db.Text, nullable=True)
    scheduled_tests = db.relationship('ScheduledTest', backref='test_type', lazy=True)

    def __repr__(self):
        return f'<TestType {self.name}>'

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number_or_name = db.Column(db.String(50), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    has_computers = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    scheduled_tests = db.relationship('ScheduledTest', backref='room', lazy=True)

    def __repr__(self):
        return f'<Room {self.room_number_or_name}>'

class StaffMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_info = db.Column(db.String(100), nullable=True)
    # Storing roles as a comma-separated string for simplicity here.
    # A many-to-many relationship with a Role model would be more robust.
    roles_can_perform = db.Column(db.String(200), nullable=True) # e.g., "TCA,Proctor"
    certifications_trainings = db.Column(db.Text, nullable=True)
    assignments = db.relationship('StaffAssignment', backref='staff_member', lazy=True)

    def __repr__(self):
        return f'<StaffMember {self.name}>'

class ScheduledTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_type_id = db.Column(db.Integer, db.ForeignKey('test_type.id'), nullable=False)
    test_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    actual_duration_minutes = db.Column(db.Integer, nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    expected_students = db.Column(db.Integer, default=0)
    readiness_check_status = db.Column(db.String(50), default="Not Required") # Pending, Completed, Failed
    notes = db.Column(db.Text, nullable=True)
    staff_assignments = db.relationship('StaffAssignment', backref='scheduled_test', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ScheduledTest {self.test_type.name} on {self.test_date}>'

class StaffAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scheduled_test_id = db.Column(db.Integer, db.ForeignKey('scheduled_test.id'), nullable=False)
    staff_member_id = db.Column(db.Integer, db.ForeignKey('staff_member.id'), nullable=False)
    assigned_role = db.Column(db.String(50), nullable=False) # e.g., "Proctor", "TCA"

    def __repr__(self):
        return f'{self.staff_member.name} as {self.assigned_role} for test {self.scheduled_test_id}'

# --- Routes ---

@app.route('/')
def index():
    # Get all scheduled tests and filter for Fridays (4) and Saturdays (5)
    all_tests = ScheduledTest.query.order_by(ScheduledTest.test_date, ScheduledTest.start_time).all()
    
    # Group tests by date for better display
    tests_by_date = {}
    for test in all_tests:
        # Only include Fridays and Saturdays
        if test.test_date.weekday() in [4, 5]: # Monday is 0 and Sunday is 6
            date_str = test.test_date.strftime('%Y-%m-%d (%A)')
            if date_str not in tests_by_date:
                tests_by_date[date_str] = []
            tests_by_date[date_str].append(test)
            
    return render_template('index.html', tests_by_date=tests_by_date)

# --- Management Routes for TestTypes, Rooms, Staff ---
@app.route('/manage/test_types', methods=['GET', 'POST'])
def manage_test_types():
    if request.method == 'POST':
        name = request.form['name']
        duration = request.form.get('default_duration_minutes', 180, type=int)
        tech_req = request.form.get('technical_requirements')
        staff_needs = request.form.get('staffing_needs_description')
        # ... (add other fields from TestType model)
        requires_readiness = 'requires_readiness_check' in request.form

        new_test_type = TestType(
            name=name, default_duration_minutes=duration,
            technical_requirements=tech_req, staffing_needs_description=staff_needs,
            requires_readiness_check=requires_readiness
            # ...
        )
        db.session.add(new_test_type)
        db.session.commit()
        flash(f'Test Type "{name}" added!', 'success')
        return redirect(url_for('manage_test_types'))
    test_types = TestType.query.all()
    return render_template('manage_test_types.html', test_types=test_types)

@app.route('/manage/rooms', methods=['GET', 'POST'])
def manage_rooms():
    if request.method == 'POST':
        room_name = request.form['room_number_or_name']
        capacity = request.form.get('capacity', type=int)
        has_computers = 'has_computers' in request.form
        new_room = Room(room_number_or_name=room_name, capacity=capacity, has_computers=has_computers)
        db.session.add(new_room)
        db.session.commit()
        flash(f'Room "{room_name}" added!', 'success')
        return redirect(url_for('manage_rooms'))
    rooms = Room.query.all()
    return render_template('manage_rooms.html', rooms=rooms)

@app.route('/manage/staff', methods=['GET', 'POST'])
def manage_staff():
    if request.method == 'POST':
        name = request.form['name']
        contact = request.form.get('contact_info')
        roles = request.form.get('roles_can_perform') # e.g., TCA,Proctor
        new_staff = StaffMember(name=name, contact_info=contact, roles_can_perform=roles)
        db.session.add(new_staff)
        db.session.commit()
        flash(f'Staff Member "{name}" added!', 'success')
        return redirect(url_for('manage_staff'))
    staff_members = StaffMember.query.all()
    return render_template('manage_staff.html', staff_members=staff_members)


# --- Schedule a Test Route ---
@app.route('/schedule_test', methods=['GET', 'POST'])
def schedule_test():
    if request.method == 'POST':
        try:
            test_type_id = request.form.get('test_type_id', type=int)
            test_date_str = request.form['test_date']
            start_time_str = request.form['start_time']
            duration = request.form.get('actual_duration_minutes', type=int)
            room_id = request.form.get('room_id', type=int)
            expected_students = request.form.get('expected_students', type=int)
            notes = request.form.get('notes')

            # Validate date is Friday or Saturday
            test_date_obj = datetime.strptime(test_date_str, '%Y-%m-%d').date()
            if test_date_obj.weekday() not in [4, 5]: # 4 is Friday, 5 is Saturday
                flash('Tests can only be scheduled on Fridays or Saturdays.', 'danger')
                return redirect(url_for('schedule_test')) # Or re-render form with error

            start_time_obj = datetime.strptime(start_time_str, '%H:%M').time()
            
            test_type = TestType.query.get(test_type_id)
            if not test_type:
                 flash('Invalid Test Type selected.', 'danger')
                 return redirect(url_for('schedule_test'))


            new_scheduled_test = ScheduledTest(
                test_type_id=test_type_id,
                test_date=test_date_obj,
                start_time=start_time_obj,
                actual_duration_minutes=duration,
                room_id=room_id,
                expected_students=expected_students,
                notes=notes,
                readiness_check_status="Pending" if test_type.requires_readiness_check else "Not Required"
            )
            db.session.add(new_scheduled_test)
            db.session.flush() # To get the ID for staff assignments

            # Handle Staff Assignments (Simplified: assumes one of each role for this example)
            # A more robust solution would allow multiple staff per role and dynamic form fields.
            coordinator_ids = request.form.getlist('coordinator_ids')
            proctor_ids = request.form.getlist('proctor_ids')
            tca_ids = request.form.getlist('tca_ids')
            tech_monitor_ids = request.form.getlist('tech_monitor_ids')

            for staff_id in coordinator_ids:
                if staff_id:
                    assignment = StaffAssignment(scheduled_test_id=new_scheduled_test.id, staff_member_id=int(staff_id), assigned_role="Coordinator")
                    db.session.add(assignment)
            for staff_id in proctor_ids:
                if staff_id:
                    assignment = StaffAssignment(scheduled_test_id=new_scheduled_test.id, staff_member_id=int(staff_id), assigned_role="Proctor")
                    db.session.add(assignment)
            for staff_id in tca_ids:
                if staff_id:
                    assignment = StaffAssignment(scheduled_test_id=new_scheduled_test.id, staff_member_id=int(staff_id), assigned_role="TCA")
                    db.session.add(assignment)
            for staff_id in tech_monitor_ids:
                if staff_id:
                    assignment = StaffAssignment(scheduled_test_id=new_scheduled_test.id, staff_member_id=int(staff_id), assigned_role="Technical Monitor")
                    db.session.add(assignment)
            
            db.session.commit()
            flash('Test scheduled successfully!', 'success')
            return redirect(url_for('index'))

        except ValueError as e:
            flash(f'Error in form data: {e}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {e}', 'danger')
            app.logger.error(f"Error scheduling test: {e}", exc_info=True)


    test_types = TestType.query.all()
    rooms = Room.query.all()
    staff_members = StaffMember.query.all()
    return render_template('schedule_test.html', test_types=test_types, rooms=rooms, staff_members=staff_members)

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Create database tables if they don't exist
    app.run(debug=True)