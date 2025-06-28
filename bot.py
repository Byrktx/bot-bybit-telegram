import os
import ccxt
import pandas as pd
import requests
import ta
from datetime import datetime

# Leer variables de entorno
api_key = os.getenv(BYBIT_API_KEY)
api_secret = os.getenv(BYBIT_API_SECRET)
telegram_token = os.getenv(TELEGRAM_TOKEN)
telegram_chat_id = os.getenv(TELEGRAM_CHAT_ID)

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
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

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
    soporte = df['low'].min()  # soporte es mínimo
    resistencia = df['high'].max()  # resistencia es máximo
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
    usdt = balance['total'].get('USDT', 0)
    if usdt == 0:
        send_telegram(f"❌ No hay saldo USDT para abrir orden en {symbol}")
        return None
    ticker = exchange.fetch_ticker(symbol)
    price = ticker['last']
    amount = (usdt * leverage) / price

    try:
        if side == 'buy':
            order = exchange.create_market_buy_order(symbol, amount)
            tp = price + (price * tp_percent / 100)
            sl = price - (price * sl_percent / 100)
        else:
            order = exchange.create_market_sell_order(symbol, amount)
            tp = price - (price * tp_percent / 100)
            sl = price + (price * sl_percent / 100)
    except Exception as e:
        send_telegram(f"❌ Error al abrir orden en {symbol}: {e}")
        return None

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

if __name__ == "__main__":
    send_telegram("🤖 BOT DE TRADING INICIADO. Analiza BTC/USDT y ETH/USDT.")
    run_bot()
