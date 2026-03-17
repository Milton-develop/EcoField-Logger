from flask import Flask, render_template, request, redirect, url_for, send_file, session
import csv
import os
from datetime import datetime
import io
from werkzeug.utils import secure_filename  # NEW

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}  # NEW

def allowed_file(filename):  # NEW
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ------------------------- CONFIG -------------------------
CURRENT_YEAR = "2025/2026"
ADMIN_PASSWORD = "fieldadmin2026"

DATA_FILE = "data/observations.csv"
GROUPS_FILE = "data/groups.csv"
ARCHIVE_FOLDER = "data/archive"

os.makedirs("data", exist_ok=True)
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ------------------------- HOME / LOG OBSERVATIONS -------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # ---- HANDLE FILE UPLOADS ----
        uploaded_files = request.files.getlist("photos")  # matches name="photos"
        saved_filenames = []

        for file in uploaded_files:
            if file and allowed_file(file.filename):
                # Secure + unique filename
                base_name = secure_filename(file.filename)
                unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{base_name}"
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
                file.save(save_path)
                saved_filenames.append(unique_name)

        # Join multiple filenames with ; so we can split later
        photo_files_str = ";".join(saved_filenames)

        # ---- EXISTING DATA DICT, ADDING photo_files ----
        data = {
            "year_group": request.form.get("year_group"),
            "group_id": request.form.get("group_id"),
            "member_name": request.form.get("member_name"),
            "species_list": ", ".join(request.form.getlist("species[]")), # Change this
            "count_list": ", ".join(request.form.getlist("count[]")),   # Change this
            "species_manual": ", ".join(request.form.getlist("species_manual")),
            "count_manual": ", " .join(request.form.getlist("count_manual")),
            "habitat": request.form.get("habitat"),
            "location": request.form.get("location"),
            "notes": request.form.get("notes"),
            "latitude": request.form.get("latitude"),
            "longitude": request.form.get("longitude"),
            "survey_type": request.form.get("survey_type"),
            "temperature": request.form.get("temperature"),
            "humidity": request.form.get("humidity"),
            "rainfall": request.form.get("rainfall"),
            "wind_speed": request.form.get("wind_speed"),
            "wind_direction": request.form.get("wind_direction"),
            "light_intensity": request.form.get("light_intensity"),
            "canopy_cover": request.form.get("canopy_cover"),
            "canopy_height": request.form.get("canopy_height"),
            "site_location": request.form.get("site_location"),
            "photo_files": photo_files_str,  # NEW FIELD
            "student_id": request.form.get("student_id"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    

        with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(data)

        return redirect(url_for("index"))

    return render_template("index.html", year=CURRENT_YEAR)


# ------------------------- GROUP LOGIN -------------------------
@app.route("/group", methods=["GET", "POST"])
def group_login():
    error = None
    if request.method == "POST":
        group_id = request.form.get("group_id").strip()
        password = request.form.get("password").strip()
        valid = False

        if os.path.isfile(GROUPS_FILE):
            with open(GROUPS_FILE, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["group_id"].strip() == group_id and row["password"].strip() == password:
                        valid = True
                        break

        if valid:
            session["group_id"] = group_id
            return redirect(url_for("view_group"))
        else:
            error = "Invalid Group ID or Password"

    return render_template("group_login.html", error=error)


# ------------------------- VIEW GROUP DATA -------------------------
@app.route("/view_group")
def view_group():
    if "group_id" not in session:
        return redirect(url_for("group_login"))

    rows = []
    if os.path.isfile(DATA_FILE):
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["group_id"].strip() == session["group_id"]:
                    # --- Process Standard Species ---
                    # We split the strings into lists first
                    s_names = row["species_list"].split(", ") if row["species_list"] else []
                    s_counts = row["count_list"].split(", ") if row["count_list"] else []
                    
                    # CRITICAL: Wrap zip in list() so the HTML can loop over it multiple times
                    row['zipped_species'] = list(zip(s_names, s_counts))
                    
                    # --- Process Manual Species ---
                    m_names = row["species_manual"].split(", ") if row["species_manual"] else []
                    m_counts = row["count_manual"].split(", ") if row["count_manual"] else []
                    
                    # CRITICAL: Wrap zip in list() here as well
                    row['zipped_manual'] = list(zip(m_names, m_counts))
                    
                    rows.append(row)

    return render_template("group.html", rows=rows, group_id=session["group_id"])
# ------------------------- DOWNLOAD GROUP DATA -------------------------
@app.route("/download_group")
def download_group():
    if "group_id" not in session:
        return redirect(url_for("group_login"))

    filtered = []
    if os.path.isfile(DATA_FILE):
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["group_id"].strip() == session["group_id"]:
                    filtered.append(row)

    if not filtered:
        return "No data available", 404

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=filtered[0].keys())
    writer.writeheader()
    writer.writerows(filtered)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        as_attachment=True,
        download_name=f"{session['group_id']}_{CURRENT_YEAR}.csv"
    )


# ------------------------- MANAGE GROUPS -------------------------
@app.route("/manage_groups", methods=["GET", "POST"])
def manage_groups():
    # 1. Security: Only allow logged-in admins
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    error = None
    success = None
    

    if request.method == "POST":
        entered_admin = request.form.get("admin_password")
        new_group_id = request.form.get("group_id", "").strip()
        new_password = request.form.get("password", "").strip()

        # 2. Password and Input Validation
        if entered_admin != ADMIN_PASSWORD:
            error = "❌ Invalid admin password!"
        elif not new_group_id or not new_password:
            error = "❌ Provide both Group ID and Password."
        else:
            # 3. Read existing groups to check for duplicates
            existing_ids = []
            existing_passwords = []
            
            if os.path.isfile(GROUPS_FILE):
                with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing_ids.append(row["group_id"].strip())
                        existing_passwords.append(row["password"].strip())

            # 4. Strict Uniqueness Check
            if new_group_id in existing_ids:
                error = f"❌ Group ID '{new_group_id}' already exists."
            elif new_password in existing_passwords:
                error = "❌ This password is already in use by another group."
            else:
                # 5. Write to file safely
                file_is_empty = not os.path.isfile(GROUPS_FILE) or os.stat(GROUPS_FILE).st_size == 0
                
                with open(GROUPS_FILE, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["group_id", "password"])
                    if file_is_empty:
                        writer.writeheader()
                    writer.writerow({"group_id": new_group_id, "password": new_password})
                
                success = f"✅ Group {new_group_id} added successfully!"

    # 6. Pass CURRENT_YEAR so the header stays updated
    return render_template("manage_groups.html", error=error, success=success, year=CURRENT_YEAR)

# ------------------------- ADMIN LOGIN -------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        entered = request.form.get("admin_password")
        if entered == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("view_archive"))
        else:
            error = "Invalid admin password!"
    return render_template("admin_login.html", error=error)

# ------------------------- ADMIN LOGOUT -------------------------
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return render_template("index.html")


# ------------------------- ARCHIVE CURRENT DATA -------------------------
@app.route("/admin/archive", methods=["GET", "POST"])
def archive_data():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    msg = None
    if request.method == "POST":
        # 1. GET THE PASSWORD FROM THE FORM
        entered_admin = request.form.get("admin_password")

        # 2. VALIDATE THE PASSWORD
        if entered_admin != ADMIN_PASSWORD:
            msg = "❌ Invalid admin password! Data not archived."
        elif not os.path.isfile(DATA_FILE):
            msg = "No data to archive"
        else:
            # 3. PROCEED ONLY IF PASSWORD IS CORRECT
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f"{ARCHIVE_FOLDER}/observations_{CURRENT_YEAR.replace('/', '_')}_{timestamp}.csv"
            os.rename(DATA_FILE, archive_name)
            msg = f"Data archived successfully as {os.path.basename(archive_name)}"
    
    # We must pass year=CURRENT_YEAR here so the header works
    return render_template("manage_groups.html", message=msg, year=CURRENT_YEAR)


# ------------------------- VIEW ARCHIVE FILES -------------------------
@app.route("/admin/view_archive")
def view_archive():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    files = sorted(os.listdir(ARCHIVE_FOLDER), reverse=True)
    return render_template("archive.html", files=files)


# ------------------------- DOWNLOAD ARCHIVE FILE -------------------------
@app.route("/admin/download_archive/<filename>")
def download_archive(filename):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    path = os.path.join(ARCHIVE_FOLDER, filename)
    if os.path.isfile(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404

# ------------------------- DELETE ARCHIVE FILE -------------------------
@app.route("/admin/delete_archive/<filename>", methods=["POST"])
def delete_archive(filename):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    file_path = os.path.join(ARCHIVE_FOLDER, secure_filename(filename))
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    return redirect(url_for("view_archive"))

@app.route("/delete_entry/<timestamp>", methods=["POST"])
def delete_entry(timestamp):
    if "group_id" not in session:
        return redirect(url_for("group_login"))

    updated_rows = []
    if os.path.isfile(DATA_FILE):
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                # Only keep the row if the timestamp and group_id don't match the one to delete
                if not (row["timestamp"] == timestamp and row["group_id"] == session["group_id"]):
                    updated_rows.append(row)

        # Write the filtered data back to the CSV
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

    return redirect(url_for("view_group"))

# ------------------------- HELP -------------------------
@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/logout")
def group_logout():
    session.pop("group_id", None)
    return redirect(url_for("index"))

@app.route('/manifest.json')
def serve_manifest():
    return send_file('static/manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_sw():
    return send_file('static/sw.js', mimetype='application/javascript')

@app.route('/dashboard')
def go_to_stats():
    # Redirect the user to the Streamlit port
    return redirect("https://milton-develop-ecofield-eco-stats-6k4jtq.streamlit.app/") 


# ------------------------- RUN APP -------------------------
if __name__ == "__main__":
    # Change port to 5002
    app.run(host="0.0.0.0",port=5000, debug=True) 
