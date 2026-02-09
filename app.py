import os
import random
import uuid
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907'
socketio = SocketIO(app, cors_allowed_origins="*")

odalar = {}
bekleyen_oyuncular = []
HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ"

# --- VERİ YÜKLEME MOTORU ---
KELIME_HAVUZU = {
    "İsim": set(), "Şehir": set(), "Hayvan": set(), "Bitki": set(),
    "Ülke": set(), "Ünlü": set(), "Eşya": set(), "Yemek": set()
}

def verileri_yukle():
    dosya_eslesmeleri = {
        "İsim": "isim.txt", "Şehir": "sehir.txt", "Hayvan": "hayvan.txt",
        "Bitki": "bitki.txt", "Ülke": "ulke.txt", "Ünlü": "unlu.txt",
        "Eşya": "esya.txt", "Yemek": "yemek.txt"
    }
    
    base_path = os.path.join(os.path.dirname(__file__), 'data')
    
    if not os.path.exists(base_path):
        os.makedirs(base_path)
        print("UYARI: 'data' klasörü bulunamadı, oluşturuldu.")

    for kategori, dosya_adi in dosya_eslesmeleri.items():
        dosya_yolu = os.path.join(base_path, dosya_adi)
        if os.path.exists(dosya_yolu):
            with open(dosya_yolu, 'r', encoding='utf-8') as f:
                icerik = set(line.strip().upper() for line in f if line.strip())
                KELIME_HAVUZU[kategori] = icerik
            print(f"{kategori} yüklendi: {len(KELIME_HAVUZU[kategori])} kelime.")
        else:
            print(f"UYARI: {dosya_adi} bulunamadı! Bu kategori için sadece harf kontrolü yapılacak.")

verileri_yukle()

# --- DOĞRULAMA FONKSİYONU ---
def kelime_gecerli_mi(kategori, kelime, harf):
    kelime = kelime.strip().upper()
    if not kelime or not kelime.startswith(harf):
        return False
    
    if len(KELIME_HAVUZU.get(kategori, [])) == 0:
        return True 
        
    return kelime in KELIME_HAVUZU.get(kategori, set())

# --- SOCKET EVENTLERİ (FLUTTER UYUMLU) ---

@socketio.on('create_room')
def handle_create(data):
    # Flutter'dan gelen keyler: roomName, password, nickname
    room_name = data['roomName']
    password = data['password']
    nick = data.get('nickname', 'Anonim')

    odalar[room_name] = {
        'password': password, 
        'host': request.sid, 
        'letter': '',
        'categories': ["İsim", "Şehir", "Hayvan", "Bitki", "Eşya"],
        'players': {request.sid: nick}, 
        'answers': {}, 
        'scored': False
    }
    join_room(room_name)
    
    # Host'a bildirim (room_joined)
    emit('room_joined', {
        'roomName': room_name, 
        'isHost': True, 
        'categories': odalar[room_name]['categories']
    })
    
    # Oyuncu listesini güncelle (update_players)
    player_list = list(odalar[room_name]['players'].values())
    emit('update_players', {'players': player_list})

@socketio.on('join_room')
def handle_join(data):
    room_name = data['roomName']
    password = data['password']
    nick = data.get('nickname', 'Misafir')

    if room_name in odalar and odalar[room_name]['password'] == password:
        join_room(room_name)
        odalar[room_name]['players'][request.sid] = nick
        
        player_list = list(odalar[room_name]['players'].values())
        
        # Katılan kişiye bildirim
        emit('room_joined', {
            'roomName': room_name, 
            'isHost': False, 
            'categories': odalar[room_name]['categories']
        })
        
        # Odaya kategori bilgisini güncelle (update_categories) - Mevcut durumu görmek için
        emit('update_categories', {'categories': odalar[room_name]['categories']}, room=room_name)
        
        # Tüm odaya oyuncu listesi (update_players)
        emit('update_players', {'players': player_list}, room=room_name)
    else:
        emit('hata', {'mesaj': 'Hatalı giriş veya oda yok!'})

@socketio.on('find_match')
def handle_matchmaking(data):
    nick = data.get('nickname', 'Oyuncu')
    bekleyen_oyuncular.append({'sid': request.sid, 'nick': nick})
    # Flutter tarafında bu event için bir dinleyici yoktu ama log için kalabilir
    emit('match_waiting', {'mesaj': 'Rakip aranıyor...'})

    if len(bekleyen_oyuncular) >= 2:
        p1 = bekleyen_oyuncular.pop(0)
        p2 = bekleyen_oyuncular.pop(0)
        match_room = f"match_{uuid.uuid4().hex[:8]}"
        
        all_cats = ["İsim", "Şehir", "Hayvan", "Bitki", "Ülke", "Eşya", "Yemek", "Ünlü"]
        selected_cats = random.sample(all_cats, 5)
        
        odalar[match_room] = {
            'password': None, 
            'host': p1['sid'], 
            'letter': random.choice(HARFLER),
            'categories': selected_cats,
            'players': {p1['sid']: p1['nick'], p2['sid']: p2['nick']},
            'answers': {}, 
            'scored': False
        }
        
        for p in [p1, p2]: 
            join_room(match_room, sid=p['sid'])
            
        # Flutter: onMatchFound -> 'match_found'
        emit('match_found', {
            'roomName': match_room, 
            'letter': odalar[match_room]['letter'], 
            'categories': selected_cats
        }, room=match_room)

@socketio.on('stop_matchmaking')
def handle_cancel():
    global bekleyen_oyuncular
    bekleyen_oyuncular = [p for p in bekleyen_oyuncular if p['sid'] != request.sid]

@socketio.on('start_game')
def handle_start(data):
    room_name = data['roomName']
    if room_name in odalar and odalar[room_name]['host'] == request.sid:
        odalar[room_name].update({
            'letter': random.choice(HARFLER), 
            'answers': {}, 
            'scored': False
        })
        # Flutter: onGameStarted -> 'game_started'
        emit('game_started', {
            'letter': odalar[room_name]['letter'], 
            'categories': odalar[room_name]['categories']
        }, room=room_name)

@socketio.on('submit_answers')
def handle_answers(data):
    room_name = data['roomName']
    if room_name in odalar:
        # data['answers'] formatı Flutter'dan Map<String, String> geliyor
        odalar[room_name]['answers'][request.sid] = data['answers']

@socketio.on('finish_early')
def handle_finish(data):
    room_name = data['roomName']
    # Flutter: onCountdownStarted -> 'countdown'
    emit('countdown', {'duration': 10}, room=room_name)
    socketio.sleep(12) # Gecikme payı
    if room_name in odalar and not odalar[room_name]['scored']:
        puanla(room_name)
        odalar[room_name]['scored'] = True

@socketio.on('update_categories')
def handle_category_change(data):
    room_name = data['roomName']
    if room_name in odalar and odalar[room_name]['host'] == request.sid:
        odalar[room_name]['categories'] = data['categories']
        # Flutter: onCategoriesChanged -> 'update_categories'
        emit('update_categories', {'categories': odalar[room_name]['categories']}, room=room_name)

@socketio.on('disconnect')
def handle_disconnect():
    # Basit bir temizlik mantığı
    # Gerçek projede oyuncu odadan düştüğünde diğerlerine haber vermek gerekir
    pass

def puanla(room_name):
    results = {}
    room_data = odalar[room_name]
    cats, letter = room_data['categories'], room_data['letter']
    answers_pool, players = room_data['answers'], room_data['players']
    
    for sid, player_answers in answers_pool.items():
        total_score = 0
        details = {}
        
        for cat in cats:
            word = player_answers.get(cat, "").strip().upper()
            
            if kelime_gecerli_mi(cat, word, letter):
                # Pişti kontrolü
                others_words = [
                    v.get(cat, "").strip().upper() 
                    for s, v in answers_pool.items() 
                    if s != sid
                ]
                score = 5 if word in others_words else 10
            else:
                score = 0
            
            total_score += score
            details[cat] = {"word": word, "score": score}
            
        results[sid] = {
            "totalScore": total_score, 
            "details": details, 
            "nickname": players.get(sid, "Bilinmiyor")
        }
        
    # Flutter: onResultsReceived -> 'game_result'
    emit('game_result', results, room=room_name)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
