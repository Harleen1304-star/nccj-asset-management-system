import csv
import io
import os
import smtplib
from flask import send_file
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from dotenv import load_dotenv

from database import get_db


load_dotenv()



app = Flask(__name__)

app.secret_key = "asset_tracking_secret"

# =====================================
# EMAIL CONFIGURATION
# =====================================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'

app.config['MAIL_PORT'] = 587

app.config['MAIL_USE_TLS'] = True

app.config['MAIL_USE_SSL'] = False

app.config['MAIL_USERNAME'] = os.getenv(
    'MAIL_USERNAME',
    'assetsystem.demo@gmail.com'
)

app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

app.config['MAIL_DEFAULT_SENDER'] = os.getenv(
    'MAIL_DEFAULT_SENDER',
    'assetsystem.demo@gmail.com'
)

mail = Mail(app)
# =====================================
# EMAIL FUNCTION
# =====================================

def send_email(to_email, subject, body):

    msg = Message(

        subject,

        sender='assetsystem.demo@gmail.com',

        recipients=[to_email]

    )


    msg.body = body


    try:
        mail.send(msg)
    except (smtplib.SMTPException, OSError):
        app.logger.exception("Unable to send email to %s", to_email)
        return False

    return True

# =====================================
# HELPER FUNCTIONS
# =====================================

def verify_password(stored_password, supplied_password):

    if not stored_password:
        return False

    if stored_password == supplied_password:
        return True

    return check_password_hash(
        stored_password,
        supplied_password
    )


def create_request_notification(db, request_data, status):

    asset = db.execute(
        """
        SELECT asset_name, asset_tag
        FROM assets
        WHERE asset_id=?
        """,
        (request_data["asset_id"],)
    ).fetchone()

    if not asset:
        return

    processed_at = datetime.now()
    message = (
        f"Your asset request has been {status.lower()}.\n\n"
        f"Asset: {asset['asset_name']} ({asset['asset_tag']})\n"
        f"Status: {status}\n"
        f"Processed: {processed_at.strftime('%B %d, %Y at %I:%M %p')}\n"
    )

    if request_data["reason"]:
        message += f"Reason: {request_data['reason']}"

    db.execute(
        """
        INSERT INTO notifications
        (user_id, request_id, status, message, created_at, is_read)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (
            request_data["user_id"],
            request_data["request_id"],
            status,
            message,
            processed_at,
        )
    )



def login_required():

    if "user_id" not in session:
        return False

    return True



def admin_required():

    if "user_id" not in session:
        return False

    if session.get("role") != "Admin":
        return False

    return True


# =====================================
# HOME PAGE
# =====================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =====================================
# LOGIN
# =====================================

@app.route(
    "/login",
    methods=["GET","POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        db = get_db()

        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            AND status='Active'
            """,
            (email,)
        ).fetchone()


        db.close()


        if user and verify_password(
            user["password"],
            password
        ):

            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]


            # Role based redirect

            if user["role"] == "Admin":

                return redirect(
                    "/admin/dashboard"
                )


            elif user["role"] == "Staff":

                return redirect(
                    "/user/dashboard"
                )


            elif user["role"] == "User":

                return redirect(
                    "/user/dashboard"
                )


        else:

            flash(
                "Invalid email or password",
                "danger"
            )


    return render_template(
        "login.html"
    )


# =====================================
# LOGOUT
# =====================================

@app.route("/logout")

def logout():


    session.clear()


    return redirect(
        "/login"
    )

# =====================================
# REGISTER USER
# =====================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]


        db = get_db()


        # Check if email already exists
        existing_user = db.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            """,
            (email,)
        ).fetchone()


        if existing_user:

            flash(
                "Email already registered",
                "danger"
            )

            db.close()

            return redirect("/register")



        # Hash password
        hashed_password = generate_password_hash(password)



        # Create user account
        db.execute(
            """
            INSERT INTO users
            (
            username,
            email,
            password,
            role,
            status
            )

            VALUES (?,?,?,?,?)
            """,
            (
            username,
            email,
            hashed_password,
            "User",
            "Active"
            )
        )


        db.commit()
        db.close()



        flash(
            "Registration successful. Please login.",
            "success"
        )


        return redirect("/login")



    return render_template(
        "register.html"
    )

# =====================================
# ADMIN DASHBOARD
# =====================================

@app.route(
    "/admin/dashboard"
)

def admin_dashboard():


    if not admin_required():

        return redirect("/login")



    db = get_db()



    total_assets = db.execute(

        """

        SELECT COUNT(*)

        FROM assets

        """

    ).fetchone()[0]



    available_assets = db.execute(

        """

        SELECT COUNT(*)

        FROM assets

        WHERE status='Available'

        """

    ).fetchone()[0]



    assigned_assets = db.execute(

        """

        SELECT COUNT(*)

        FROM assets

        WHERE status='Assigned'

        """

    ).fetchone()[0]



    total_users = db.execute(

        """

        SELECT COUNT(*)

        FROM users

        """

    ).fetchone()[0]



    pending_requests = db.execute(

        """

        SELECT COUNT(*)

        FROM asset_requests

        WHERE status='Pending'

        """

    ).fetchone()[0]

    today = datetime.now().date()
    audit_deadline = today + timedelta(days=15)

    audit_rows = db.execute(
        """
        SELECT
            assets.asset_id,
            assets.asset_tag,
            assets.asset_name,
            assets.funder,
            assets.next_audit_date,
            users.username AS assigned_user,
            CASE
                WHEN date(assets.next_audit_date) < date(?) THEN 0
                ELSE 1
            END AS urgency_group,
            CAST(julianday(assets.next_audit_date) - julianday(?) AS INTEGER)
                AS days_remaining_value
        FROM assets
        LEFT JOIN asset_assignments
            ON asset_assignments.asset_id = assets.asset_id
            AND asset_assignments.status='Assigned'
        LEFT JOIN users
            ON users.user_id = asset_assignments.user_id
        WHERE assets.next_audit_date IS NOT NULL
        AND (
            date(assets.next_audit_date) < date(?)
            OR date(assets.next_audit_date) BETWEEN date(?) AND date(?)
        )
        ORDER BY urgency_group ASC,
                 days_remaining_value ASC,
                 date(assets.next_audit_date) DESC
        """,
        (today, today, today, today, audit_deadline)
    ).fetchall()

    audits_due_soon = [
        {
            **dict(audit),
            "assigned_user_or_funder": (
                audit["assigned_user"] or audit["funder"] or "Unassigned"
            ),
            "days_remaining": (
                "Overdue"
                if audit["days_remaining_value"] < 0
                else audit["days_remaining_value"]
            ),
            "audit_status": (
                "Overdue"
                if audit["days_remaining_value"] < 0
                else "Due Soon"
            ),
        }
        for audit in audit_rows
    ]

    db.close()



    return render_template(

        "admin/admin_dashboard.html",

        total_assets=total_assets,

        available_assets=available_assets,

        assigned_assets=assigned_assets,

        total_users=total_users,

        pending_requests=pending_requests,

        audits_due_soon=audits_due_soon

    )



# =====================================
# USER DASHBOARD
# =====================================
@app.route(
    "/user/dashboard"
)
def user_dashboard():

    if session.get("role") not in ["User", "Staff"]:

        return redirect("/login")


    db = get_db()



    # Count assigned assets
    assigned_assets = db.execute(
        """
        SELECT COUNT(*)
        FROM asset_assignments
        WHERE user_id=?
        AND status='Assigned'
        """,
        (
        session["user_id"],
        )

    ).fetchone()[0]




    # Count pending requests
    pending_requests = db.execute(
        """
        SELECT COUNT(*)
        FROM asset_requests
        WHERE user_id=?
        AND status='Pending'
        """,
        (
        session["user_id"],
        )

    ).fetchone()[0]

    unread_notifications = db.execute(
        """
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id=? AND is_read=0
        """,
        (session["user_id"],)
    ).fetchone()[0]





    # User reminders
    reminders = db.execute(
        """
        SELECT

        assets.asset_tag,

        assets.asset_name,

        assets.status,

        assets.next_audit_date


        FROM asset_assignments


        JOIN assets


        ON asset_assignments.asset_id = assets.asset_id


        WHERE asset_assignments.user_id=?

        AND asset_assignments.status='Assigned'


        ORDER BY assets.next_audit_date ASC

        """,
        (
        session["user_id"],
        )

    ).fetchall()





    db.close()



    return render_template(
        "users/users_dashboard.html",
        assigned_assets=assigned_assets,
        pending_requests=pending_requests,
        unread_notifications=unread_notifications,
        reminders=reminders
    )


# =====================================
# USER NOTIFICATIONS
# =====================================

@app.route("/user/notifications")
def user_notifications():

    if session.get("role") not in ["User", "Staff"]:
        return redirect("/login")

    db = get_db()

    notifications = db.execute(
        """
        SELECT notification_id, status, message, created_at
        FROM notifications
        WHERE user_id=?
        ORDER BY created_at DESC, notification_id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    db.execute(
        """
        UPDATE notifications
        SET is_read=1
        WHERE user_id=? AND is_read=0
        """,
        (session["user_id"],)
    )
    db.commit()
    db.close()

    return render_template(
        "users/notifications.html",
        notifications=notifications
    )


@app.route("/user/notifications/delete/<int:notification_id>", methods=["POST"])
def delete_notification(notification_id):

    if session.get("role") not in ["User", "Staff"]:
        return redirect("/login")

    db = get_db()
    db.execute(
        """
        DELETE FROM notifications
        WHERE notification_id=? AND user_id=?
        """,
        (notification_id, session["user_id"])
    )
    db.commit()
    db.close()

    return redirect("/user/notifications")


@app.route("/user/notifications/delete-selected", methods=["POST"])
def delete_selected_notifications():

    if session.get("role") not in ["User", "Staff"]:
        return redirect("/login")

    notification_ids = request.form.getlist("notification_ids")
    if notification_ids:
        placeholders = ",".join("?" for _ in notification_ids)
        db = get_db()
        db.execute(
            f"DELETE FROM notifications WHERE user_id=? AND notification_id IN ({placeholders})",
            [session["user_id"], *notification_ids]
        )
        db.commit()
        db.close()

    return redirect("/user/notifications")

# =====================================
# USER MY ASSETS
# =====================================

@app.route("/user/my_assets")
def my_assets():

    if session.get("role") not in ["User", "Staff"]:
        return redirect("/login")


    db = get_db()


    assets = db.execute(
        """
        SELECT 
        assets.*,
        asset_assignments.assigned_date

        FROM asset_assignments

        JOIN assets

        ON asset_assignments.asset_id = assets.asset_id

        WHERE asset_assignments.user_id=?
        AND asset_assignments.status='Assigned'
        """,
        (session["user_id"],)
    ).fetchall()


    db.close()


    return render_template(
        "users/my_assets.html",
        assets=assets
    )

# =====================================
# CREATE ASSET
# =====================================

@app.route(
    "/admin/create_asset",
    methods=["GET","POST"]
)
def create_asset():

    if not admin_required():

        return redirect("/login")



    if request.method == "POST":


        asset_tag = request.form["asset_tag"]

        asset_name = request.form["asset_name"]

        funder = request.form["funder"]

        status = request.form["status"]



        today = datetime.now().date()

        next_audit = today + timedelta(days=90)



        db = get_db()



        db.execute(

            """

            INSERT INTO assets

            (

            asset_tag,

            asset_name,

            status,

            funder,

            last_audit_date,

            next_audit_date

            )


            VALUES (?,?,?,?,?,?)

            """,


            (

            asset_tag,

            asset_name,

            status,

            funder,

            today,

            next_audit

            )

        )



        db.commit()

        db.close()



        flash(
            "Asset created successfully",
            "success"
        )


        return redirect(
            "/admin/assets"
        )



    return render_template(

        "admin/create_asset.html"

    )



# =====================================
# VIEW ALL ASSETS
# =====================================

@app.route(
    "/admin/assets"
)

def admin_assets():


    if not admin_required():

        return redirect("/login")



    db = get_db()



    selected_assignee = request.args.get("assigned_to", "all")

    assets_query = """
        SELECT
            assets.*,
            assigned_user.username AS assigned_to,
            assigned_user.user_id AS assigned_to_id
        FROM assets
        LEFT JOIN asset_assignments
            ON asset_assignments.asset_id = assets.asset_id
            AND asset_assignments.status='Assigned'
        LEFT JOIN users AS assigned_user
            ON assigned_user.user_id = asset_assignments.user_id
    """
    assets_parameters = []

    if selected_assignee == "unassigned":
        assets_query += " WHERE assigned_user.user_id IS NULL"
    elif selected_assignee.isdigit():
        assets_query += " WHERE assigned_user.user_id=?"
        assets_parameters.append(int(selected_assignee))

    assets_query += " ORDER BY assets.asset_id DESC"

    assets = db.execute(
        assets_query,
        assets_parameters
    ).fetchall()

    users = db.execute(
        """
        SELECT user_id, username
        FROM users
        WHERE status='Active'
        ORDER BY username ASC
        """
    ).fetchall()



    db.close()



    return render_template(

        "admin/admin_assets.html",

        assets=assets,

        users=users,

        selected_assignee=selected_assignee

    )



# =====================================
# RE-CERTIFY ASSET AUDIT
# =====================================

@app.route(
    "/admin/recertify_asset/<int:id>",
    methods=["POST"]
)
def recertify_asset(id):

    if not admin_required():

        return redirect("/login")

    db = get_db()

    asset = db.execute(
        """
        SELECT asset_name, next_audit_date
        FROM assets
        WHERE asset_id=?
        """,
        (id,)
    ).fetchone()

    if not asset or not asset["next_audit_date"]:

        db.close()

        flash(
            "Asset does not have a next audit date",
            "danger"
        )

        return redirect("/admin/assets")

    current_next_audit = datetime.strptime(
        asset["next_audit_date"],
        "%Y-%m-%d"
    ).date()
    recertification_date = datetime.now().date()
    next_audit = current_next_audit + timedelta(days=90)

    db.execute(
        """
        UPDATE assets
        SET last_audit_date=?, next_audit_date=?
        WHERE asset_id=?
        """,
        (recertification_date, next_audit, id)
    )

    db.execute(
        """
        INSERT INTO asset_history
        (asset_id, user_id, action, action_date, notes)
        VALUES (?,?,?,?,?)
        """,
        (
            id,
            session["user_id"],
            "Audit re-certified",
            recertification_date,
            f"Next audit moved from {current_next_audit} to {next_audit}",
        )
    )

    db.commit()
    db.close()

    flash(
        f"{asset['asset_name']} audit re-certified successfully",
        "success"
    )

    return redirect("/admin/assets")


# =====================================
# DELETE ASSET
# =====================================

@app.route(
    "/admin/delete_asset/<int:id>"
)

def delete_asset(id):


    if not admin_required():

        return redirect("/login")



    db = get_db()



    db.execute(

        """

        DELETE FROM assets

        WHERE asset_id=?

        """,

        (
        id,
        )

    )



    db.commit()

    db.close()



    flash(
        "Asset deleted",
        "success"
    )



    return redirect(

        "/admin/assets"

    )



# =====================================
# ASSIGN ASSET
# =====================================

@app.route(

    "/admin/assign_asset",

    methods=["GET","POST"]

)

def assign_asset():


    if not admin_required():

        return redirect("/login")



    db = get_db()



    if request.method == "POST":



        user_id = request.form.get("user_id")

        asset_id = request.form.get("asset_id")

        if not user_id:

            db.close()

            flash(
                "Please select a user.",
                "danger"
            )

            return redirect("/admin/assets")



        today = datetime.now().date()



        # Check if asset already assigned


        existing = db.execute(

            """

            SELECT *

            FROM asset_assignments

            WHERE asset_id=?

            AND status='Assigned'

            """,

            (
            asset_id,
            )

        ).fetchone()



        if existing:


            flash(

            "Asset already assigned",

            "danger"

            )


            db.close()


            return redirect(
                "/admin/assets"
            )



        # Create assignment


        db.execute(

            """

            INSERT INTO asset_assignments

            (

            user_id,

            asset_id,

            assigned_date,

            status

            )


            VALUES (?,?,?,?)

            """,


            (

            user_id,

            asset_id,

            today,

            "Assigned"

            )

        )



        # Update asset status


        db.execute(

            """

            UPDATE assets

            SET status='Assigned'

            WHERE asset_id=?

            """,

            (

            asset_id,

            )

        )



        # Create history record


        db.execute(

            """

            INSERT INTO asset_history

            (

            asset_id,

            user_id,

            action,

            action_date,

            notes

            )


            VALUES (?,?,?,?,?)

            """,


            (

            asset_id,

            user_id,

            "Assigned",

            today,

            "Asset assigned by administrator"

            )

        )



        db.commit()

        db.close()



        flash(

        "Asset assigned successfully",

        "success"

        )



        return redirect(

            "/admin/assets"

        )




    # GET REQUEST


    users = db.execute(

        """

        SELECT *

        FROM users

        WHERE status='Active'

        """

    ).fetchall()



    assets = db.execute(

        """

        SELECT *

        FROM assets

        WHERE status='Available'

        """

    ).fetchall()



    db.close()



    return render_template(

        "admin/assign_asset.html",

        users=users,

        assets=assets

    )

# =====================================
# USER REQUEST ASSET
# =====================================

@app.route(
    "/user/request_asset",
    methods=["GET","POST"]
)
def request_asset():

    if session.get("role") not in ["User", "Staff"]:
        return redirect("/login")


    db = get_db()


    if request.method == "POST":


        asset_id = request.form["asset_id"]

        reason = request.form["reason"]


        today = datetime.now().date()



        db.execute(
            """
            INSERT INTO asset_requests
            (
            user_id,
            asset_id,
            reason,
            status,
            request_date
            )

            VALUES (?,?,?,?,?)
            """,
            (
            session["user_id"],
            asset_id,
            reason,
            "Pending",
            today
            )
        )


        db.commit()


        flash(
            "Asset request submitted",
            "success"
        )


        db.close()


        return redirect(
            "/user/dashboard"
        )



    # Show available assets

    assets = db.execute(
        """
        SELECT *
        FROM assets
        WHERE status='Available'
        ORDER BY asset_id DESC
        """
    ).fetchall()



    db.close()



    return render_template(
        "users/request_asset.html",
        assets=assets
    )
# =====================================
# ADMIN VIEW REQUESTS
# =====================================

@app.route(
    "/admin/requests"
)

def admin_requests():


    if not admin_required():

        return redirect("/login")



    db = get_db()



    requests = db.execute(

        """

        SELECT

        asset_requests.*,

        users.username,

        assets.asset_name,

        assets.asset_tag



        FROM asset_requests



        JOIN users

        ON asset_requests.user_id =
        users.user_id



        JOIN assets

        ON asset_requests.asset_id =
        assets.asset_id



        ORDER BY request_id DESC

        """

    ).fetchall()



    db.close()



    return render_template(

        "admin/admin_requests.html",

        requests=requests

    )



# =====================================
# APPROVE ASSET REQUEST
# =====================================

@app.route(
    "/admin/approve_request/<int:id>"
)
def approve_request(id):


    if not admin_required():

        return redirect("/login")



    db = get_db()



    request_data = db.execute(

        """
        SELECT *
        FROM asset_requests
        WHERE request_id=?
        """,

        (
        id,
        )

    ).fetchone()



    if not request_data:


        db.close()


        return "Request not found"




    today = datetime.now().date()



    # =====================================
    # UPDATE REQUEST STATUS
    # =====================================

    db.execute(

        """
        UPDATE asset_requests

        SET status='Accepted'

        WHERE request_id=?
        """,

        (
        id,
        )

    )

    create_request_notification(db, request_data, "Accepted")




    # =====================================
    # CREATE ASSET ASSIGNMENT
    # =====================================

    db.execute(

        """
        INSERT INTO asset_assignments

        (
        user_id,
        asset_id,
        assigned_date,
        status
        )

        VALUES (?,?,?,?)

        """,

        (

        request_data["user_id"],

        request_data["asset_id"],

        today,

        "Assigned"

        )

    )




    # =====================================
    # UPDATE ASSET STATUS
    # =====================================

    db.execute(

        """
        UPDATE assets

        SET status='Assigned'

        WHERE asset_id=?

        """,

        (

        request_data["asset_id"],

        )

    )





    # =====================================
    # CREATE HISTORY RECORD
    # =====================================

    db.execute(

        """
        INSERT INTO asset_history

        (
        asset_id,
        user_id,
        action,
        action_date,
        notes
        )

        VALUES (?,?,?,?,?)

        """,

        (

        request_data["asset_id"],

        request_data["user_id"],

        "Assigned",

        today,

        "Approved through request system"

        )

    )





    db.commit()





    # =====================================
    # SEND EMAIL NOTIFICATION
    # =====================================

    user = db.execute(

        """
        SELECT username, email

        FROM users

        WHERE user_id=?

        """,

        (

        request_data["user_id"],

        )

    ).fetchone()





    email_sent = False

    if user:


        email_sent = send_email(

            user["email"],

            "Asset Request Approved",

            f"""

Hello {user['username']},


Your asset request has been approved.



Asset Information:

Asset ID:
{request_data['asset_id']}



Status:
Approved



You can login to the NCCJ Asset Management System
to view your assigned asset.



Thank you,

Lake Miller

"""

        )





    db.close()





    if email_sent:
        flash(
            "Request approved and email notification sent",
            "success"
        )
    else:
        flash(
            "Request approved, but the email notification could not be sent",
            "warning"
        )





    return redirect(

        "/admin/requests"

    )


# =====================================
# REJECT REQUEST
# =====================================

@app.route(
    "/admin/reject_request/<int:id>"
)

def reject_request(id):


    if not admin_required():

        return redirect("/login")



    db = get_db()

    request_data = db.execute(
        """
        SELECT *
        FROM asset_requests
        WHERE request_id=?
        """,
        (id,)
    ).fetchone()

    if not request_data:
        db.close()
        return "Request not found"



    db.execute(

        """

        UPDATE asset_requests

        SET status='Rejected'

        WHERE request_id=?

        """,

        (
        id,
        )

    )

    create_request_notification(db, request_data, "Rejected")



    db.commit()

    db.close()



    flash(

        "Request rejected",

        "success"

    )



    return redirect(

        "/admin/requests"

    )



# =====================================
# RETURN ASSET
# =====================================

@app.route(
    "/admin/return_asset/<int:id>"
)

def return_asset(id):


    if not admin_required():

        return redirect("/login")



    db = get_db()



    assignment = db.execute(

        """

        SELECT *

        FROM asset_assignments

        WHERE assignment_id=?

        """,

        (
        id,
        )

    ).fetchone()



    if assignment:


        today = datetime.now().date()



        # Update assignment


        db.execute(

            """

            UPDATE asset_assignments

            SET

            return_date=?,

            status='Returned'


            WHERE assignment_id=?

            """,

            (
            today,

            id

            )
        )



        # Make asset available again


        db.execute(

            """

            UPDATE assets

            SET status='Available'

            WHERE asset_id=?

            """,

            (

            assignment["asset_id"],

            )

        )



        # History


        db.execute(

            """

            INSERT INTO asset_history

            (

            asset_id,

            user_id,

            action,

            action_date,

            notes

            )


            VALUES (?,?,?,?,?)

            """,

            (

            assignment["asset_id"],

            assignment["user_id"],

            "Returned",

            today,

            "Asset returned to inventory"

            )

        )



        db.commit()



    db.close()



    flash(

        "Asset returned successfully",

        "success"

    )



    return redirect(

        "/admin/assets"

    )

# =====================================
# ADMIN USER REQUESTS
# =====================================

@app.route("/admin/user_requests")
def admin_user_requests():

    if not admin_required():

        return redirect("/login")

    db = get_db()

    users = db.execute(
        """
        SELECT *
        FROM user_requests
        WHERE status='Pending'
        """
    ).fetchall()

    db.close()

    return render_template(
        "admin/user_requests.html",
        users=users
    )



# =====================================
# APPROVE USER
# =====================================

@app.route("/admin/approve_user/<int:id>")
def approve_user(id):

    if not admin_required():

        return redirect("/login")


    db = get_db()


    user_request = db.execute(
        """
        SELECT *
        FROM user_requests
        WHERE request_id=?
        """,
        (id,)
    ).fetchone()



    if user_request:

        db.execute(
            """
            INSERT INTO users
            (
            username,
            email,
            password,
            role,
            status
            )

            VALUES (?,?,?,?,?)
            """,
            (
            user_request["full_name"],
            user_request["email"],
            user_request["password"],
            user_request["role"],
            "Active"
            )
        )


        db.execute(
            """
            UPDATE user_requests

            SET status='Approved'

            WHERE request_id=?
            """,
            (id,)
        )


        db.commit()


    db.close()


    return redirect(
        "/admin/user_requests"
    )



# =====================================
# SEARCH ASSETS
# =====================================

@app.route("/admin/search")
def search_assets():

    if not admin_required():

        return redirect("/login")


    keyword = request.args.get("query")


    db = get_db()


    assets = db.execute(
        """
        SELECT *

        FROM assets

        WHERE asset_name LIKE ?

        OR asset_tag LIKE ?

        """,
        (
        "%" + keyword + "%",
        "%" + keyword + "%"
        )
    ).fetchall()


    db.close()


    return render_template(
        "admin/admin_assets.html",
        assets=assets
    )


# =====================================
# RUN APPLICATION
# =====================================

if __name__ == "__main__":

    app.run(debug=True)