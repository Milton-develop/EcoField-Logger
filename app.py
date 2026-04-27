from flask import Flask, render_template, request, redirect, url_for, send_file, session
import csv
import os
from datetime import datetime
import io 
from werkzeug.utils import secure_filename  # NEW
from supabase import create_client, Client

NEXT_PUBLIC_SUPABASE_URL="https://yedpxbqdyikdjvuunaeh.supabase.co"
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY="sb_publishable_qU9Cy9Cb_MWftgbxwmeCNQ_XeBRq3nR"
supabase: Client = create_client(NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}  # NEW

def allowed_file(filename):  # NEW
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ------------------------- CONFIG -------------------------
def get_current_academic_year():
    now = datetime.now()
    if now.month >= 8:
        return f"{now.year}/{now.year + 1}"
    return f"{now.year - 1}/{now.year}"

def get_admin_password():
    try:
        response = supabase.table("admin_settings").select("setting_value").eq("setting_key", "admin_password").execute()
        if response.data:
            return response.data[0]["setting_value"]
    except Exception as e:
        print(f"Error fetching admin password: {e}")
    return "fieldadmin2026" # Fallback just in case

def set_admin_password(new_password):
    try:
        supabase.table("admin_settings").update({"setting_value": new_password}).eq("setting_key", "admin_password").execute()
        return True
    except Exception as e:
        print(f"Error updating admin password: {e}")
        return False

DATA_FILE = "data/observations.csv"
GROUPS_FILE = "data/groups.csv"
ARCHIVE_FOLDER = "data/archive"

os.makedirs("data", exist_ok=True)
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Safe get with default empty string in case it's missing
        username = request.form.get('username', '').strip().lower()
        if username == 'admin':
            session['user_role'] = 'admin'
            # return redirect(url_for("archive.html"))
            return render_template("admin_login.html")
        elif username == 'student':
            session['user_role'] = 'student'
            return redirect(url_for('index'))
        else:
            return render_template("login.html", error="Please specify your role")
    
    # Render the login form for GET requests
    return render_template("login.html")

# -------------------- HOME --------------------
@app.route("/home")
def index():
    if "user_role" not in session:
        return redirect(url_for('login'))
    return render_template("index.html")

# ------------------------- LOG OBSERVATIONS -------------------------
@app.route("/form", methods=["GET", "POST"])
def form():
    if request.method == "POST":
        # ---- VERIFY GROUP ID ----
        group_id_val = request.form.get("group_id", "").strip()
        if group_id_val:
            try:
                res = supabase.table("manage_groups").select("group_id").eq("group_id", group_id_val).execute()
                if not res.data or len(res.data) == 0:
                    return render_template("form.html", year=get_current_academic_year(), error=f"Invalid Group ID '{group_id_val}'. Please ask your administrator to register it.")
            except Exception as e:
                print("DB group check error:", e)

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
        def get_val(k):
            val = request.form.get(k)
            return val.strip() if val and val.strip() != "" else None

        data = {
            "year_group": get_val("year_group"),
            "group_id": get_val("group_id"),
            "member_name": get_val("member_name"),
            "species_list": ", ".join(request.form.getlist("species[]")) or None, 
            "count_list": ", ".join(request.form.getlist("count[]")) or None,  
            "species_manual": ", ".join(request.form.getlist("species_manual")) or None,
            "count_manual": ", ".join(request.form.getlist("count_manual")) or None,
            "habitat": get_val("habitat"),
            "location": get_val("location"),
            "notes": get_val("notes"),
            "latitude": get_val("latitude"),
            "longitude": get_val("longitude"),
            "survey_type": get_val("survey_type"),
            "temperature": get_val("temperature"),
            "humidity": get_val("humidity"),
            "rainfall": get_val("rainfall"),
            "wind_speed": get_val("wind_speed"),
            "wind_direction": get_val("wind_direction"),
            "light_intensity": get_val("light_intensity"),
            "canopy_cover": get_val("canopy_cover"),
            "canopy_height": get_val("canopy_height"),
            "site_location": get_val("site_location"),
            "photo_files": photo_files_str,  # NEW FIELD
            "student_id": get_val("student_id"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    

        try:
            supabase.table("observations").insert(data).execute()
        except Exception as e:
            print(f"Supabase Insert Error: {e}")
            return render_template("form.html", year=get_current_academic_year(), error=f"Database Save Error: {e}")
            
        return redirect(url_for("form"))

    return render_template("form.html", year=get_current_academic_year())


# ------------------------- GROUP LOGIN -------------------------
@app.route("/group", methods=["GET", "POST"])
def group_login():
    error = None
    if request.method == "POST":
        group_id = request.form.get("group_id").strip()
        password = request.form.get("password").strip()
        valid = False

        if group_id and password:
            try:
                response = supabase.table("manage_groups").select("*").eq("group_id", group_id).eq("password", password).execute()
                if response.data and len(response.data) > 0:
                    valid = True
            except Exception as e:
                print(f"Supabase Select Error: {e}")

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
    try:
        response = supabase.table("observations").select("*").eq("group_id", session["group_id"]).execute()
        for row in response.data:
            # --- Process Standard Species ---
            # We split the strings into lists first
            s_names = row.get("species_list") or ""
            s_names = str(s_names).split(", ") if s_names else []
            
            s_counts = row.get("count_list") or ""
            s_counts = str(s_counts).split(", ") if s_counts else []
            
            # CRITICAL: Wrap zip in list() so the HTML can loop over it multiple times
            row['zipped_species'] = list(zip(s_names, s_counts))
            
            # --- Process Manual Species ---
            m_names = row.get("species_manual") or ""
            m_names = str(m_names).split(", ") if m_names else []
            
            m_counts = row.get("count_manual") or ""
            m_counts = str(m_counts).split(", ") if m_counts else []
            
            # CRITICAL: Wrap zip in list() here as well
            row['zipped_manual'] = list(zip(m_names, m_counts))
            
            rows.append(row)
    except Exception as e:
        print(f"Error fetching group data: {e}")

    return render_template("group.html", rows=rows, group_id=session["group_id"])
# ------------------------- DOWNLOAD GROUP DATA -------------------------
@app.route("/download_group")
def download_group():
    if "group_id" not in session:
        return redirect(url_for("group_login"))

    filtered = []
    try:
        response = supabase.table("observations").select("*").eq("group_id", session["group_id"]).execute()
        filtered = response.data
    except Exception as e:
        print(f"Error downloading group data: {e}")

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
        download_name=f"{session['group_id']}_{get_current_academic_year()}.csv"
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
        if entered_admin != get_admin_password():
            error = "❌ Invalid admin password!"
        elif not new_group_id or not new_password:
            error = "❌ Provide both Group ID and Password."
        else:
            # 3. Read existing groups to check for duplicates
            existing_ids = []
            existing_passwords = []
            
            try:
                response = supabase.table("manage_groups").select("*").execute()
                for row in response.data:
                    existing_ids.append(row.get("group_id", "").strip())
                    existing_passwords.append(row.get("password", "").strip())
            except Exception as e:
                error = f"Database read error: {e}"

            # 4. Strict Uniqueness Check
            if error is None:
                if new_group_id in existing_ids:
                    error = f"❌ Group ID '{new_group_id}' already exists."
                elif new_password in existing_passwords:
                    error = "❌ This password is already in use by another group."
                else:
                    # 5. Write to supabase SAFELY
                    try:
                        supabase.table("manage_groups").insert({"group_id": new_group_id, "password": new_password}).execute()
                        success = f"Group {new_group_id} added successfully!"
                    except Exception as e:
                        error = f"Database insert error: {e}"

    # 6. Pass the dynamic year so the header stays updated
    return render_template("manage_groups.html", error=error, success=success, year=get_current_academic_year())

# ------------------------- VIEW GROUPS -------------------------
@app.route("/admin/view_groups")
def admin_view_groups():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    groups = []
    try:
        response = supabase.table("manage_groups").select("*").execute()
        groups = response.data
    except Exception as e:
        print(f"Error fetching groups: {e}")

    return render_template("admin_groups.html", groups=groups)

# ------------------------- DELETE GROUP -------------------------
@app.route("/admin/delete_group/<group_id>", methods=["POST"])
def delete_group(group_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    try:
        supabase.table("manage_groups").delete().eq("group_id", group_id).execute()
    except Exception as e:
        print(f"Error deleting group: {e}")

    return redirect(url_for("admin_view_groups"))

# ------------------------- ADMIN LOGIN -------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        entered = request.form.get("admin_password")
        if entered == get_admin_password():
            session["admin_logged_in"] = True
            return redirect(url_for("view_archive"))
        else:
            error = "Invalid admin password!"
    return render_template("admin_login.html", error=error)

# ------------------------- CHANGE ADMIN PASSWORD -------------------------
@app.route("/admin/change_password", methods=["POST"])
def change_admin_password():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    current_pw = request.form.get("current_password")
    new_pw = request.form.get("new_password")
    confirm_pw = request.form.get("confirm_password")

    if current_pw != get_admin_password():
        return render_template("manage_groups.html", error="❌ Incorrect current password.", year=get_current_academic_year())
    if new_pw != confirm_pw:
        return render_template("manage_groups.html", error="❌ New passwords do not match.", year=get_current_academic_year())
    if len(new_pw) < 6:
        return render_template("manage_groups.html", error="❌ New password must be at least 6 characters long.", year=get_current_academic_year())

    if set_admin_password(new_pw):
        return render_template("manage_groups.html", success="✅ Admin password updated successfully!", year=get_current_academic_year())
    else:
        return render_template("manage_groups.html", error="❌ Failed to update password.", year=get_current_academic_year())

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
        if entered_admin != get_admin_password():
            msg = "❌ Invalid admin password! Data not archived."
        else:
            # 3. PROCEED ONLY IF PASSWORD IS CORRECT
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f"{ARCHIVE_FOLDER}/observations_{get_current_academic_year().replace('/', '_')}_{timestamp}.csv"
            try:
                # 1. Fetch all data
                response = supabase.table("observations").select("*").execute()
                all_data = response.data
                
                if not all_data:
                    msg = "No data to archive."
                else:
                    # 2. Write to CSV in ARCHIVE_FOLDER
                    with open(archive_name, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
                        writer.writeheader()
                        writer.writerows(all_data)
                    
                    # 3. Delete from Supabase
                    supabase.table("observations").delete().neq("id", "0").execute()
                    
                    msg = f"Data archived successfully as {os.path.basename(archive_name)}"
            except Exception as e:
                msg = f"Error archiving data: {e}"
    
    # We must pass year=get_current_academic_year() here so the header works
    return render_template("manage_groups.html", message=msg, year=get_current_academic_year())


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

    try:
        supabase.table("observations").delete().eq("timestamp", timestamp).eq("group_id", session["group_id"]).execute()
    except Exception as e:
        print(f"Error deleting entry: {e}")

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
    return redirect("http://localhost:8501/") 

# ------------------------- VIEW NEW SPECIES -------------------------
@app.route("/add_species")
def add_species():
    # if "group_id" not in session:
    #     return redirect(url_for("group_login"))

    new_species_rows = []
    unique_species = set()
    total_count = 0

    try:
        response = supabase.table("observations").select("*").execute()
        for row in response.data:
            s_manual = row.get("species_manual") or ""
            c_manual = row.get("count_manual") or ""
            
            m_names  = [n.strip() for n in str(s_manual).split(",") if n.strip()] if s_manual else []
            m_counts = [c.strip() for c in str(c_manual).split(",")   if c.strip()] if c_manual else []

            if not m_names:
                continue  # skip rows with no manual species

            row["zipped_manual"] = list(zip(m_names, m_counts))

            for sp, cnt in row["zipped_manual"]:
                unique_species.add(sp)
                try:
                    total_count += int(cnt)
                except (ValueError, TypeError):
                    pass

            new_species_rows.append(row)
    except Exception as e:
        print(f"Error fetching manual species: {e}")

    return render_template(
        "add_species.html",
        new_species_rows=new_species_rows,
        group_id='All Groups',
        total_entries=len(new_species_rows),
        unique_species=unique_species,
        total_count=total_count,
    )
    
# ------------------------- RUN APP -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000, debug=True) 
