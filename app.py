import os
import random
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Oyunun durumunu takip eden ana değişken
oyun_verileri = {
    "mevcut_harf": "",
    "secilen_kategoriler": ["isim", "sehir", "hayvan"], # Başlangıç varsayılanları
    "cevaplar": {}
}

HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ"

@app.route('/')
def index():
    return render_template('index.html')

# Lobide kategori seçimlerini senkronize eder
@socketio.on('kategori_degistir')
def handle_category_change(data):
    oyun_verileri["secilen_kategoriler"] = data['kategoriler']
    emit('kategorileri_guncelle', {'kategoriler': oyun_verileri["secilen_kategoriler"]}, broadcast=True)

@socketio.on('oyunu_baslat')
def handle_start():
    oyun_verileri["mevcut_harf"] = random.choice(HARFLER)
    oyun_verileri["cevaplar"] = {}
    emit('yeni_oyun_basladi', {
        'harf': oyun_verileri["mevcut_harf"],
        'kategoriler': oyun_verileri["secilen_kategoriler"]
    }, broadcast=True)

@socketio.on('oyunu_bitir')
def handle_finish():
    emit('geri_sayim_baslat', {'sure': 10}, broadcast=True)

@socketio.on('cevaplari_gonder')
def handle_answers(data):
    oyuncu_id = request.sid
    oyun_verileri["cevaplar"][oyuncu_id] = data['cevaplar']
    if len(oyun_verileri["cevaplar"]) >= 2:
        puanlari_hesapla_ve_yayinla()

def puanlari_hesapla_ve_yayinla():
    sonuclar = {}
    kategoriler = oyun_verileri["secilen_kategoriler"]
    harf = oyun_verileri["mevcut_harf"]
    
    for oyuncu, cevaplar in oyun_verileri["cevaplar"].items():
        toplam_puan = 0
        detaylar = {}
        for kat in kategoriler:
            kelime = cevaplar.get(kat, "").strip().upper()
            puan = 0
            if kelime and kelime.startswith(harf):
                diger_cevaplar = [v.get(kat, "").strip().upper() for k, v in oyun_verileri["cevaplar"].items() if k != oyuncu]
                puan = 5 if kelime in diger_cevaplar else 10
            toplam_puan += puan
            detaylar[kat] = {"kelime": kelime, "puan": puan}
        sonuclar[oyuncu] = {"toplam": toplam_puan, "detay": detaylar}
    
    emit('puan_durumu', sonuclar, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
