import os
from flask import Flask, redirect, url_for, render_template, session, send_from_directory, request, jsonify 
from flask_discord import DiscordOAuth2Session
import pymysql
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# ✨ Waitress 임포트 추가 (프로 서빙팀 고용!)
from waitress import serve 

load_dotenv()

# ✨ 절대 경로 설정
base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
            static_folder='static',           
            template_folder='templates')

# ✨ 프록시 설정 (클라우드타입 호스팅 필수)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# ==========================================
# ⚡ [이미지 최적화 및 서빙]
# ==========================================

# 💡 이미지 캐싱: 로딩 속도 향상을 위해 브라우저에 30일간 저장 명령
@app.after_request
def add_header(response):
    if request.path.startswith('/images/'):
        response.cache_control.max_age = 2592000 
    return response

# 💡 카드 이미지 전용 라우트 (images 폴더 및thumbnails 폴더 서빙)
@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(os.path.join(base_dir, 'images'), filename)

# Discord OAuth2 설정
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
        print(f"⚠️ DB 연결 실패: {e}")
        return None

def get_all_card_files():
    image_list = []
    card_base_path = os.path.join(base_dir, 'images')
    
    if not os.path.exists(card_base_path):
        return image_list

    for root, dirs, files in os.walk(card_base_path):
        # 썸네일 폴더는 목록 생성에서 제외
        if 'thumbnails' in root: continue

        for file in files:
            # WebP 포함 이미지 확장자 체크
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

# ==========================================
# 📖 1. 도감 페이지
# ==========================================
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
            print(f"❌ 데이터베이스 오류: {e}")
        finally:
            conn.close()

    return render_template("collection.html", 
                           user=user, 
                           all_cards=all_cards, 
                           owned_names=owned_names)

# ==========================================
# 🎒 2. 인벤토리 페이지 (WebP 최적화 적용)
# ==========================================
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
                
                # 💡 HTML에서 .webp 확장자를 쉽게 붙여 쓰도록 이름 전처리
                for item in inventory_items:
                    item['clean_name'] = os.path.splitext(item['item_name'])[0]
        except Exception as e:
            print(f"❌ 데이터베이스 오류: {e}")
        finally:
            conn.close()

    return render_template("inventory.html", 
                           user=user, 
                           inventory_items=inventory_items)

# ==========================================
# 🔒 3. 자물쇠 잠금 API
# ==========================================
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
            print(f"❌ 잠금 API 오류: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            conn.close()
    
    return jsonify({"success": False, "message": "DB Connection Error"}), 500


# ==========================================
# 🚀 서버 실행 (Waitress 적용)
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Waitress 웹 서버가 포트 {port}에서 8개의 스레드로 가동됩니다!")
    serve(app, host='0.0.0.0', port=port, threads=8)

if __name__ == "__main__":
    run_flask()