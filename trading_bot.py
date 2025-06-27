
import ccxt
import pandas as pd
import time
import requests
import ta
from datetime import datetime

# === API DE BYBIT ===
api_key = '6R1hjZZk2O6hjjyei1'
api_secret = 'RSMisCCXOhsSuFKkC1lSwX4JjXXQwypDSQrF'

# === TELEGRAM BOT ===
telegram_token = '7625060062:AAHzUlJZRnxGqlFqo-owajzxIjdg2xOwoH4'
telegram_chat_id = '6751348393'

# === CONFIGURACIÓN DEL EXCHANGE (BYBIT FUTUROS) ===
exchange = ccxt.bybit({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'recvWindow': 10000
    }
})

symbols = ['BTC/USDT', 'ETH/USDT']
timeframe = '5m'
leverage = 5
sl_percent = 1.5
tp_percent = 3.0
operacion_abierta = {}

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    data = {'chat_id': telegram_chat_id, 'text': msg}
    try:
        requests.post(url, data=data)
    except:
        print("❌ Error al enviar mensaje a Telegram.")

def get_ohlcv(symbol):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def add_indicators(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    df['ema200'] = ta.trend.EMAIndicator(df['close'], window=200).ema_indicator()
    return df

def detectar_soporte_resistencia(df):
    soporte = df['low'].max()
    resistencia = df['high'].max()
    return soporte, resistencia

def check_signal(df, soporte, resistencia):
    last = df.iloc[-1]
    if last['close'] < soporte and last['rsi'] < 30 and last['ema50'] > last['ema200']:
        return 'buy'
    elif last['close'] > resistencia and last['rsi'] > 70 and last['ema50'] < last['ema200']:
        return 'sell'
    else:
        return None

def save_to_csv(symbol, side, price, tp, sl):
    data = {
        'datetime': [datetime.utcnow()],
        'symbol': [symbol],
        'side': [side],
        'price': [price],
        'tp': [tp],
        'sl': [sl]
    }
    df = pd.DataFrame(data)
    df.to_csv('historial_operaciones.csv', mode='a', header=False, index=False)

def open_order(symbol, side):
    balance = exchange.fetch_balance()
    usdt = balance['total']['USDT']
    ticker = exchange.fetch_ticker(symbol)
    price = ticker['last']
    amount = (usdt * leverage) / price

    if side == 'buy':
        order = exchange.create_market_buy_order(symbol, amount)
        tp = price + (price * tp_percent / 100)
        sl = price - (price * sl_percent / 100)
    else:
        order = exchange.create_market_sell_order(symbol, amount)
        tp = price - (price * tp_percent / 100)
        sl = price + (price * sl_percent / 100)

    msg = f"📈 {side.upper()} en {symbol}\n💵 Precio: {price:.2f}\n🎯 TP: {tp:.2f} | SL: {sl:.2f}"
    send_telegram(msg)
    save_to_csv(symbol, side, price, tp, sl)
    operacion_abierta[symbol] = True
    return order

def run_bot():
    for symbol in symbols:
        try:
            if operacion_abierta.get(symbol):
                send_telegram(f"⏳ {symbol}: Ya hay una operación abierta.")
                continue

            df = get_ohlcv(symbol)
            df = add_indicators(df)
            soporte, resistencia = detectar_soporte_resistencia(df)
            signal = check_signal(df, soporte, resistencia)

            if signal:
                open_order(symbol, signal)
            else:
                send_telegram(f"🔍 {symbol}: No hay señales claras para operar.")
        except Exception as e:
            send_telegram(f"⚠️ Error en ejecución para {symbol}: {str(e)}")

send_telegram("🤖 BOT DE TRADING INICIADO. Ahora analiza BTC/USDT y ETH/USDT cada 5 minutos.")

while True:
    run_bot()
    time.sleep(300)
