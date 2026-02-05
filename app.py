import os
import random
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Odaların verilerini tutan sözlük
# Yapı: { 'oda_adi': { 'sifre': '123', 'host': 'sid', 'kategoriler': [], 'harf': '', 'cevaplar': {}, 'geri_sayim_basladi': False } }
odalar = {}

HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ"

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('oda_olustur')
def handle_create(data):
    oda = data.get('oda', '').strip()
    sifre = data.get('sifre', '').strip()
    if not oda or not sifre:
        emit('hata', {'mesaj': 'Oda adı ve şifre zorunludur!'})
        return
    if oda in odalar:
        emit('hata', {'mesaj': 'Bu oda zaten var!'})
    else:
        odalar[oda] = {
            'sifre': sifre,
            'host': request.sid,
            'kategoriler': ["İsim", "Şehir", "Hayvan"],
            'harf': '',
            'cevaplar': {},
            'geri_sayim_basladi': False
        }
        join_room(oda)
        emit('oda_katildi', {'oda': oda, 'is_host': True})

@socketio.on('oda_katil')
def handle_join(data):
    oda = data.get('oda', '').strip()
    sifre = data.get('sifre', '').strip()
    if not oda or not sifre:
        emit('hata', {'mesaj': 'Oda adı ve şifre zorunludur!'})
        return
    if oda in odalar and odalar[oda]['sifre'] == sifre:
        join_room(oda)
        emit('oda_katildi', {'oda': oda, 'is_host': False})
        # Yeni katılan kişiye mevcut kategorileri gönder
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)
    else:
        emit('hata', {'mesaj': 'Oda adı veya şifre hatalı!'})

@socketio.on('kategori_degistir')
def handle_category_change(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        odalar[oda]['kategoriler'] = data['kategoriler']
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)

@socketio.on('oyunu_baslat')
def handle_start(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        odalar[oda]['harf'] = random.choice(HARFLER)
        odalar[oda]['cevaplar'] = {}
        odalar[oda]['geri_sayim_basladi'] = False
        emit('yeni_oyun_basladi', {
            'harf': odalar[oda]['harf'],
            'kategoriler': odalar[oda]['kategoriler']
        }, room=oda)

@socketio.on('oyunu_bitir')
def handle_finish(data):
    oda = data['oda']
    if oda in odalar and not odalar[oda]['geri_sayim_basladi']:
        odalar[oda]['geri_sayim_basladi'] = True
        emit('bitirildi', room=oda)
        emit('geri_sayim_baslat', {'sure': 10}, room=oda)

@socketio.on('cevaplari_gonder')
def handle_answers(data):
    oda = data['oda']
    oyuncu_id = request.sid
    if oda in odalar:
        odalar[oda]['cevaplar'][oyuncu_id] = data['cevaplar']
        # Basitlik için odadaki herkesin gönderdiğini varsayalım veya manuel puanla
        if len(odalar[oda]['cevaplar']) >= 2:
            puanla(oda)

def puanla(oda):
    sonuclar = {}
    kategoriler = odalar[oda]['kategoriler']
    harf = odalar[oda]['harf']
    cevaplar_havuzu = odalar[oda]['cevaplar']
    
    for oyuncu, cevaplar in cevaplar_havuzu.items():
        toplam = 0
        detay = {}
        for kat in kategoriler:
            kelime = cevaplar.get(kat, "").strip().upper()
            puan = 0
            if kelime and kelime.startswith(harf):
                digerleri = [v.get(kat, "").strip().upper() for k, v in cevaplar_havuzu.items() if k != oyuncu]
                puan = 5 if kelime in digerleri else 10
            toplam += puan
            detay[kat] = {"kelime": kelime, "puan": puan}
        sonuclar[oyuncu] = {"toplam": toplam, "detay": detay}
    emit('puan_durumu', sonuclar, room=oda)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
