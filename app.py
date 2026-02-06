import os
import random
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907' #
socketio = SocketIO(app, cors_allowed_origins="*")

odalar = {}
HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ" #

@socketio.on('oda_olustur')
def handle_create(data):
    oda = data['oda']
    sifre = data['sifre']
    # Odayı sıfırlayarak oluştur (Yeniden başlatma desteği)
    odalar[oda] = {
        'sifre': sifre, 'host': request.sid, 'harf': '',
        'kategoriler': ["İsim", "Şehir", "Hayvan"],
        'cevaplar': {}, 'puanlandi': False
    }
    join_room(oda)
    emit('oda_katildi', {'oda': oda, 'is_host': True})

@socketio.on('oda_katil')
def handle_join(data):
    oda, sifre = data['oda'], data['sifre']
    if oda in odalar and odalar[oda]['sifre'] == sifre:
        join_room(oda)
        emit('oda_katildi', {'oda': oda, 'is_host': False})
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)
    else:
        emit('hata', {'mesaj': 'Hatalı oda adı veya şifre!'})

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
        odalar[oda].update({'harf': random.choice(HARFLER), 'cevaplar': {}, 'puanlandi': False})
        emit('yeni_oyun_basladi', {'harf': odalar[oda]['harf'], 'kategoriler': odalar[oda]['kategoriler']}, room=oda)

@socketio.on('oyunu_bitir')
def handle_finish(data):
    oda = data['oda']
    emit('geri_sayim_baslat', {'sure': 10}, room=oda)
    socketio.sleep(12) # Cevapların gelmesi için güvenli bekleme süresi
    if oda in odalar and not odalar[oda]['puanlandi']:
        puanla(oda)
        odalar[oda]['puanlandi'] = True

@socketio.on('cevaplari_gonder')
def handle_answers(data):
    oda = data['oda']
    if oda in odalar:
        odalar[oda]['cevaplar'][request.sid] = data['cevaplar']

def puanla(oda):
    sonuclar = {}
    kats = odalar[oda]['kategoriler']
    harf = odalar[oda]['harf']
    havuz = odalar[oda]['cevaplar']
    
    for oyuncu, cevaplar in havuz.items():
        toplam, detay = 0, {}
        for k in kats:
            kelime = cevaplar.get(k, "").strip().upper()
            puan = 0
            if kelime and kelime.startswith(harf):
                digerleri = [v.get(k, "").strip().upper() for sid, v in havuz.items() if sid != oyuncu]
                puan = 5 if kelime in digerleri else 10 # Aynı kelimeye 5, benzersize 10
            toplam += puan
            detay[k] = {"kelime": kelime, "puan": puan}
        sonuclar[oyuncu] = {"toplam": toplam, "detay": detay}
    emit('puan_durumu', sonuclar, room=oda)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
