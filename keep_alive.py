from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "ระบบเว็บเซิร์ฟเวอร์บอทออนไลน์แล้ว"

def run():
    # ใช้พอร์ต 8080 ซึ่งเป็นพอร์ตมาตรฐานสำหรับระบบเว็บพรีวิวของ Replit
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
