from werkzeug.security import check_password_hash


class User:
    """Base class: attributes and behavior shared by every account type."""
    ROLE = "User"

    def __init__(self, school_id, name, email, password_hash):
        self.school_id = school_id
        self.name = name
        self.email = email
        self.password_hash = password_hash

    def verify_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def permissions(self):               # overridden by each subclass
        return set()

    def can(self, action):
        return action in self.permissions()

    def dashboard_route(self):           # overridden by each subclass
        raise NotImplementedError


class Borrower(User):
    """Shared behavior of users who can rent a locker."""
    def permissions(self):
        return {"view_availability", "request_locker", "cancel_request", "view_own_locker"}
    def dashboard_route(self):
        return "/lockers"


class Student(Borrower):
    ROLE = "Student"


class ProfessorStaff(Borrower):
    ROLE = "Professor/Staff"


class Maintenance(User):
    ROLE = "Maintenance"
    def permissions(self):
        return {"view_availability", "set_maintenance_status"}
    def dashboard_route(self):
        return "/maintenance"


class Administrator(User):
    ROLE = "Administrator"
    def permissions(self):
        return {"view_availability", "manage_lockers", "review_requests",
                "release_locker", "view_usage", "view_activity_log"}
    def dashboard_route(self):
        return "/admin"


USER_CLASSES = {c.ROLE: c for c in (Student, ProfessorStaff, Maintenance, Administrator)}

def create_user(row):                    # builds the right subclass from a database row
    return USER_CLASSES[row["role"]](row["school_id"], row["name"],
                                     row["email"], row["password_hash"])
