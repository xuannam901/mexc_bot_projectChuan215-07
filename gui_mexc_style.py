import os, json, requests, threading, webbrowser
import tkinter as tk
from tkinter import ttk
from datetime import datetime, date
from core.multi_timeframe_filter import passes_conditions

# API endpoint
API_24H = "https://api.mexc.com/api/v3/ticker/24hr"

# File paths
data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
state_file = os.path.join(data_dir, 'trade_state.json')
log_file = os.path.join(data_dir, f"trade_log_{date.today()}.txt")
os.makedirs(data_dir, exist_ok=True)

# Rocket.Chat config
ROCKETCHAT = {
    'server': 'https://48db67704058.ngrok-free.app',
    'user': 'caothu78',
    'pass': 'Namhk123#'
}
session = requests.Session()
rc_token = rc_uid = ''

def rocket_login():
    global rc_token, rc_uid
    try:
        payload = {'user': ROCKETCHAT['user'], 'password': ROCKETCHAT['pass']}
        resp = session.post(f"{ROCKETCHAT['server']}/api/v1/login", json=payload, timeout=5).json()
        if resp.get('success'):
            data = resp.get('data', {})
            rc_token = data.get('authToken')
            rc_uid = data.get('userId')
            session.headers.update({'X-Auth-Token': rc_token, 'X-User-Id': rc_uid})
        else:
            print(f"Rocket.Chat login failed: {resp}")
    except Exception as e:
        print(f"Rocket.Chat login error: {e}")

def ensure_channel(name):
    try:
        info = session.get(f"{ROCKETCHAT['server']}/api/v1/channels.info", params={'roomName': name}, timeout=5).json()
        if not info.get('success'):
            session.post(f"{ROCKETCHAT['server']}/api/v1/channels.create", json={'name': name}, timeout=5)
    except Exception as e:
        print(f"ensure_channel error: {e}")
    return name

def send_rocket(channel, text):
    try:
        ensure_channel(channel)
        session.post(f"{ROCKETCHAT['server']}/api/v1/chat.postMessage", json={'channel': f"#{channel}", 'text': text}, timeout=5)
    except Exception as e:
        print(f"send_rocket error: {e}")

rocket_login()

def load_state():
    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except:
        return {}

trade_state = load_state()
top_list = []

def open_chart(tree):
    sel = tree.selection()
    if sel:
        sym = tree.item(sel[0])['values'][0]
        webbrowser.open(f"https://www.mexc.com/exchange/{sym}_USDT?_from")

def open_chat():
    sel = tree_trade.selection()
    if sel:
        sym = tree_trade.item(sel[0])['values'][0]
        webbrowser.open(f"{ROCKETCHAT['server']}/channel/{sym}")

safe = lambda fn: threading.Thread(target=fn, daemon=True).start()

def format_price(p):
    return f"{p:.8f}".rstrip('0').rstrip('.')

def refresh_top():
    global top_list
    try:
        data = session.get(API_24H, timeout=10).json()
        top_list.clear()
        tree_top.delete(*tree_top.get_children())
        for d in data:
            if not d['symbol'].endswith('USDT'): continue
            open_p = float(d['openPrice'])
            if open_p <= 0: continue
            last_p = float(d['lastPrice'])
            pct = (last_p - open_p) / open_p * 100
            low_p = float(d['lowPrice'])
            high_p = float(d['highPrice'])
            rng = (high_p - low_p) / low_p * 100 if low_p>0 else 0
            if pct >= 40:
                sym = d['symbol'].replace('USDT','')
                top_list.append((sym, last_p))
                tree_top.insert('', 'end', values=(sym, format_price(last_p), f"{pct:.2f}%", f"{rng:.2f}%"))
    except Exception as e:
        print(f"refresh_top error: {e}")

def refresh_trade():

    # Tìm tất cả coin thỏa điều kiện filter
    filtered = [sym for sym, price in top_list if passes_conditions(sym)]
    # Mua tự động 10% vốn cho những coin mới thỏa điều kiện
    for sym in filtered:
        price = next(p for s, p in top_list if s == sym)
        if sym not in trade_state:
            qty = round((float(cap_var.get() or 100) * 0.1) / price, 6)
            trade_state[sym] = {'buy_price': price, 'qty': qty, 'notified_up_pct': 0.0, 'notified_down_pct': 0.0}
            send_rocket(sym, f"🛒 MUA {sym} tại {format_price(price)} USDT – 10% vốn\n🔗 https://www.mexc.com/exchange/{sym}_USDT?_from")
    # Hiển thị tất cả filtered coins
    tree_trade.delete(*tree_trade.get_children())
    for sym in filtered:
        rec = trade_state.get(sym, {})
        last = next((p for s, p in top_list if s == sym), rec.get('buy_price', 0))
        buy_total = rec.get('buy_price', 0) * rec.get('qty', 0) if rec else 0
        current_total = last * rec.get('qty', 0) if rec else 0
        tree_trade.insert('', 'end', values=(
            sym,
            format_price(buy_total) if rec else '',
            format_price(current_total) if rec else '',
            '',
            ''
        ))
    for sym, rec in list(trade_state.items()):
        last = next((p for s, p in top_list if s==sym), rec['buy_price'])
        buy_total = rec['buy_price'] * rec['qty']
        current_total = last * rec['qty']
        pnl = (last - rec['buy_price'])/rec['buy_price']*100
        # Notification for price increase ≥5%
        if pnl - rec['notified_up_pct'] >= 5:
            send_rocket(sym, f"📈 {sym} tăng {pnl:.2f}% so với giá mua – giá hiện tại {format_price(last)} USDT")
            rec['notified_up_pct'] = pnl

        # Notification for price decrease ≥5%
        if rec['notified_down_pct'] > -5 and pnl <= -5:
            send_rocket(sym, f"📉 {sym} giảm {abs(pnl):.2f}% so với giá mua – giá hiện tại {format_price(last)} USDT")
            rec['notified_down_pct'] = pnl
        if pnl <= -20:
            send_rocket(sym, f"🔻 BÁN {sym} do giảm >20%")
            with open(log_file, 'a') as f:
                f.write(f"{datetime.now()} | SELL {sym} | Buy:{format_price(rec['buy_price'])} | Sell:{format_price(last)} | Qty:{rec['qty']}\n")
            trade_state.pop(sym)
        else:
            tree_trade.insert('', 'end', values=(sym, format_price(buy_total), format_price(current_total), '', ''))
    with open(state_file, 'w') as f:
        json.dump(trade_state, f, ensure_ascii=False, indent=2)

# GUI setup
root = tk.Tk()
root.title("🚀 MEXC Spot Trade Tool")
root.geometry("1100x750")

ttk.Label(root, text="🟩 Top Tăng Spot", font=('Arial', 14, 'bold')).pack(pady=(10,0))
frame_top = ttk.Frame(root)
frame_top.pack(fill='x', padx=10, pady=5)
scroll_top = ttk.Scrollbar(frame_top, orient='vertical')
tree_top = ttk.Treeview(frame_top, columns=('Coin','Giá','%24h','Range'), show='headings', height=10, yscrollcommand=scroll_top.set)
scroll_top.config(command=tree_top.yview)
scroll_top.pack(side='right', fill='y')
tree_top.pack(fill='x')
for col in ('Coin','Giá','%24h','Range'):
    tree_top.heading(col, text=col); tree_top.column(col, anchor='center', width=120)
tree_top.bind('<Double-1>', lambda e: open_chart(tree_top))

ttk.Label(root, text="🟦 Coin Đang Trade", font=('Arial', 14, 'bold')).pack(pady=(10,0))
tree_trade = ttk.Treeview(root, columns=('Coin','Số tiền mua','Hiện có','Đã bán','Thu về'), show='headings', height=10)
for col in ('Coin','Số tiền mua','Hiện có','Đã bán','Thu về'):
    tree_trade.heading(col, text=col); tree_trade.column(col, anchor='center', width=130)
tree_trade.pack(fill='x', padx=10, pady=5)
tree_trade.bind('<Double-1>', lambda e: open_chart(tree_trade))

ctrl_frame = ttk.Frame(root); ctrl_frame.pack(pady=10)
tk.Label(ctrl_frame, text='💰 Vốn (USDT):').pack(side='left')
cap_var = tk.StringVar(value='100')
tk.Entry(ctrl_frame, textvariable=cap_var, width=10).pack(side='left', padx=5)
tk.Button(ctrl_frame, text='🔄 Làm mới', command=lambda: [safe(refresh_top), safe(refresh_trade)]).pack(side='left')
tk.Button(ctrl_frame, text='💬 Mở chat', command=open_chat).pack(side='left', padx=5)

root.after(100, lambda: safe(refresh_top))
root.after(100, lambda: safe(refresh_trade))
root.mainloop()
