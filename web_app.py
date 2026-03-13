import os
import random
from flask import Flask, redirect, url_for, render_template, session, send_from_directory, request, jsonify 
from flask_discord import DiscordOAuth2Session
import pymysql
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from waitress import serve 

load_dotenv()

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
            static_folder='static',           
            template_folder='templates')

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# ==========================================
# [이미지 최적화 및 서빙]
# ==========================================
@app.after_request
def add_header(response):
    if request.path.startswith('/images/'):
        response.cache_control.max_age = 2592000 
    return response

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(os.path.join(base_dir, 'images'), filename)

# ==========================================
# [Discord OAuth2 설정]
# ==========================================
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")
app.config["DISCORD_BOT_TOKEN"] = os.getenv("TOKEN")

discord = DiscordOAuth2Session(app)

def get_db_connection():
    try:
        return pymysql.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 31572)),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            db=os.getenv('DB_NAME'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

def get_all_card_files():
    image_list = []
    card_base_path = os.path.join(base_dir, 'images')
    
    if not os.path.exists(card_base_path):
        return image_list

    for root, dirs, files in os.walk(card_base_path):
        if 'thumbnails' in root: 
            continue

        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')) and file.lower() != 'hidden.jpg':
                relative_path = os.path.relpath(os.path.join(root, file), card_base_path)
                card_name = os.path.splitext(file)[0]
                
                parts = file.rsplit('_', 1)
                grade = parts[0] if len(parts) > 1 else "normal"
                
                image_list.append({
                    "name": card_name,
                    "path": relative_path.replace("\\", "/"),
                    "grade": grade 
                })

    image_list.sort(key=lambda x: x['name'])
    return image_list

# ==========================================
# [라우트]
# ==========================================
@app.route("/")
def index():
    if discord.authorized:
        return redirect(url_for("collection"))
    return render_template("index.html")

@app.route("/login")
def login():
    return discord.create_session(scope=["identify"]) 

@app.route("/logout")
def logout():
    session.clear()  
    return redirect(url_for("index")) 

@app.route("/callback")
def callback():
    discord.callback() 
    return redirect(url_for("collection"))

@app.route("/collection")
def collection():
    if not discord.authorized:
        return redirect(url_for("login"))
    
    user = discord.fetch_user()
    all_cards = get_all_card_files() 
    owned_names = []
    conn = get_db_connection()
    
    if conn:
        try:
            with conn.cursor() as cursor:
                sql = "SELECT item_name FROM collection WHERE user_id = %s"
                cursor.execute(sql, (user.id,))
                owned_data = cursor.fetchall()
                owned_names = [os.path.splitext(item['item_name'])[0] for item in owned_data]
        except Exception as e:
            print(f"DB Error: {e}")
        finally:
            conn.close()

    return render_template("collection.html", 
                           user=user, 
                           all_cards=all_cards, 
                           owned_names=owned_names)

@app.route("/inventory")
def inventory():
    if not discord.authorized:
        return redirect(url_for("login"))
    
    user = discord.fetch_user()
    inventory_items = []
    conn = get_db_connection()
    
    if conn:
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT id, item_name, rarity, upgrade_level, is_locked 
                    FROM inventory 
                    WHERE user_id = %s 
                    ORDER BY rarity DESC, item_name ASC
                """
                cursor.execute(sql, (user.id,))
                inventory_items = cursor.fetchall()
                
                for item in inventory_items:
                    item['clean_name'] = os.path.splitext(item['item_name'])[0]
        except Exception as e:
            print(f"DB Error: {e}")
        finally:
            conn.close()

    return render_template("inventory.html", 
                           user=user, 
                           inventory_items=inventory_items)

@app.route("/api/inventory/lock", methods=["POST"])
def toggle_inventory_lock():
    if not discord.authorized:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.json
    card_id = data.get("card_id")
    new_lock_status = data.get("lock")
    user = discord.fetch_user()

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                sql = "UPDATE inventory SET is_locked = %s WHERE id = %s AND user_id = %s"
                cursor.execute(sql, (new_lock_status, card_id, user.id))
                conn.commit()
                return jsonify({"success": True})
        except Exception as e:
            print(f"Lock API Error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            conn.close()
    
    return jsonify({"success": False, "message": "DB Connection Error"}), 500

@app.route("/gacha")
def gacha():
    if not discord.authorized:
        return redirect(url_for("login"))
    
    user = discord.fetch_user()
    conn = get_db_connection()
    user_points = 0
    owned_names = []

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT points FROM users WHERE user_id = %s", (user.id,))
                res = cursor.fetchone()
                user_points = res['points'] if res else 0

                cursor.execute("SELECT item_name FROM collection WHERE user_id = %s", (user.id,))
                owned_data = cursor.fetchall()
                owned_names = [os.path.splitext(item['item_name'])[0] for item in owned_data]
        finally:
            conn.close()

    return render_template("gacha.html", 
                           user=user, 
                           user_points=user_points, 
                           owned_names=owned_names)

@app.route("/api/gacha", methods=["POST"])
def do_gacha():
    if not discord.authorized:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    user = discord.fetch_user()
    data = request.json
    pull_count = data.get("count", 1)
    cost = 120 * pull_count

    rarities = ["Normal", "Rare", "Super Rare", "Ultra Rare"]
    weights = [70, 20, 8, 2]
    image_base_path = os.path.join(base_dir, 'images')

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "DB Connection Error"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT points FROM users WHERE user_id = %s", (user.id,))
            res = cur.fetchone()
            if not res or res['points'] < cost:
                return jsonify({"success": False, "message": f"포인트가 부족합니다. ({cost}P 필요)"}), 400

            pull_results = []
            valid_exts = ('.png', '.jpg', '.jpeg', '.gif', '.webp')

            for _ in range(pull_count):
                rarity = random.choices(rarities, weights=weights, k=1)[0]
                folder_name = rarity.lower().replace(" ", "_")
                path = os.path.join(image_base_path, folder_name)

                if not os.path.exists(path):
                    continue 

                files = [f for f in os.listdir(path) if f.lower().endswith(valid_exts) and f.lower() != 'hidden.jpg']
                
                if not files:
                    continue

                selected_file = random.choice(files)
                card_name = os.path.splitext(selected_file)[0]

                cur.execute("SELECT 1 FROM collection WHERE user_id = %s AND item_name = %s", (user.id, selected_file))
                is_duplicate = cur.fetchone()

                if not is_duplicate:
                    cur.execute("INSERT INTO collection (user_id, item_name, rarity) VALUES (%s, %s, %s)", 
                                (user.id, selected_file, rarity))

                cur.execute("INSERT INTO inventory (user_id, item_name, rarity) VALUES (%s, %s, %s)", 
                            (user.id, selected_file, rarity))

                pull_results.append({
                    "name": card_name,
                    "grade": rarity,
                    "path": f"{folder_name}/{selected_file}" 
                })

            cur.execute("UPDATE users SET points = points - %s WHERE user_id = %s", (cost, user.id))
            conn.commit()
            
            return jsonify({"success": True, "results": pull_results})

    except Exception as e:
        conn.rollback()
        print(f"Gacha API Error: {e}")
        return jsonify({"success": False, "message": "Server Processing Error"}), 500
    finally:
        conn.close()

# ==========================================
# [서버 실행]
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Waitress Server running on port {port} with 20 threads.")
    serve(app, host='0.0.0.0', port=port, threads=20, clear_untrusted_proxy_headers=False)

if __name__ == "__main__":
    run_flask()