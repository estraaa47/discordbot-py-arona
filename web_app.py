import os
from flask import Flask, redirect, url_for, render_template, session
from flask_discord import DiscordOAuth2Session
import pymysql
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

app = Flask(__name__, 
            static_folder='images', 
            static_url_path='/images', 
            template_folder='templates')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.secret_key = os.getenv("FLASK_SECRET_KEY")



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
    base_path = 'images'
    
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) and file.lower() != 'hidden.jpg':
                relative_path = os.path.relpath(os.path.join(root, file), base_path)
                card_name = os.path.splitext(file)[0]
                
                image_list.append({
                    "name": card_name,
                    "path": relative_path.replace("\\", "/") 
                })
    image_list.sort(key=lambda x: x['name'])
    
    return image_list

@app.route("/")
def index():
    if discord.authorized:
        return redirect(url_for("inventory"))
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
    return redirect(url_for("inventory"))

@app.route("/inventory")
def inventory():
    if not discord.authorized:
        return redirect(url_for("login"))
    
    user = discord.fetch_user()
    all_cards = get_all_card_files() 
    
    owned_names = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT item_name FROM inventory WHERE user_id = %s"
            cursor.execute(sql, (user.id,))
            owned_data = cursor.fetchall()
            owned_names = [os.path.splitext(item['item_name'])[0] for item in owned_data]
            
    except Exception as e:
        print(f"❌ 데이터베이스 오류: {e}")
    finally:
        conn.close()

    return render_template("inventory.html", 
                           user=user, 
                           all_cards=all_cards, 
                           owned_names=owned_names)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    run_flask()