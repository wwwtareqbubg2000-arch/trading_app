import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime
import time

# ==========================================
# 1. إعدادات التطبيق والمكتبات (Requirements)
# ==========================================
# لتشغيل هذا التطبيق، يجب عليك تثبيت المكتبات التالية عبر التيرمينال:
# pip install streamlit ccxt pandas pandas_ta plotly
#
# طريقة التشغيل:
# streamlit run trading_app.py
# ==========================================

# إعداد صفحة الويب
st.set_page_config(page_title="المحلل الذكي الشامل - 4H", layout="wide")
st.title("📊 تطبيق المحلل الذكي: فريم 4 ساعات (Multi-Strategy)")

# ==========================================
# 2. وظائف جلب البيانات (Data Fetching)
# ==========================================
@st.cache_data(ttl=300)  # تخزين مؤقت للبيانات لتسريع التطبيق
def get_market_data(symbol, timeframe='4h', limit=500):
    try:
        exchange = ccxt.binance() # استخدام منصة بينانس (بيانات عامة)
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        st.error(f"خطأ في جلب البيانات: {e}")
        return pd.DataFrame()

# ==========================================
# 3. محرك الاستراتيجيات (Strategy Engine)
# ==========================================
def analyze_market(df):
    # --- المؤشرات الفنية ---
    # 1. الاتجاه (Trend): المتوسطات المتحركة الأسية
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['EMA_200'] = ta.ema(df['close'], length=200)
    
    # 2. الزخم (Momentum): RSI
    df['RSI'] = ta.rsi(df['close'], length=14)
    
    # 3. الماكد (MACD)
    macd = ta.macd(df['close'])
    df['MACD'] = macd['MACD_12_26_9']
    df['MACD_SIGNAL'] = macd['MACDs_12_26_9']
    
    # 4. التقلب (Volatility) لحساب الأهداف: ATR
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)

    # --- منطق التحليل (الخوارزمية) ---
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    signal = "محايد"
    score = 0
    reasons = []

    # استراتيجية 1: تقاطع السعر مع المتوسطات (Trend Following)
    if last_row['close'] > last_row['EMA_200']:
        score += 1
        reasons.append("السعر فوق EMA 200 (اتجاه عام صاعد)")
    elif last_row['close'] < last_row['EMA_200']:
        score -= 1
        reasons.append("السعر تحت EMA 200 (اتجاه عام هابط)")

    # استراتيجية 2: مؤشر القوة النسبية (RSI) - مناطق التشبع
    if last_row['RSI'] < 30:
        score += 2
        reasons.append("RSI في منطقة تشبع بيعي (فرصة شراء قوية)")
    elif last_row['RSI'] > 70:
        score -= 2
        reasons.append("RSI في منطقة تشبع شرائي (احتمال انعكاس)")

    # استراتيجية 3: تقاطع الماكد (MACD Crossover)
    if last_row['MACD'] > last_row['MACD_SIGNAL'] and prev_row['MACD'] <= prev_row['MACD_SIGNAL']:
        score += 2
        reasons.append("تقاطع إيجابي لمؤشر MACD")
    elif last_row['MACD'] < last_row['MACD_SIGNAL'] and prev_row['MACD'] >= prev_row['MACD_SIGNAL']:
        score -= 2
        reasons.append("تقاطع سلبي لمؤشر MACD")

    # --- القرار النهائي ---
    if score >= 3:
        signal = "شراء قوي 🟢"
        signal_type = "BUY"
    elif score >= 1:
        signal = "شراء محتمل 🔵"
        signal_type = "BUY_WEAK"
    elif score <= -3:
        signal = "بيع قوي 🔴"
        signal_type = "SELL"
    elif score <= -1:
        signal = "بيع محتمل 🟠"
        signal_type = "SELL_WEAK"
    else:
        signal = "انتظار / تذبذب ⚪"
        signal_type = "NEUTRAL"

    return df, signal, signal_type, reasons, last_row['ATR']

# ==========================================
# 4. واجهة المستخدم (User Interface)
# ==========================================
sidebar = st.sidebar
sidebar.header("إعدادات البحث")

# قائمة ببعض الأزواج الشهيرة (يمكن إضافة المزيد)
pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "BNB/USDT", "DOGE/USDT"]
selected_pair = sidebar.selectbox("اختر زوج العملات:", pairs)

if sidebar.button("حلل الآن 🚀"):
    with st.spinner('جاري الاتصال بالسوق وتحليل البيانات...'):
        # جلب البيانات
        df = get_market_data(selected_pair)
        
        if not df.empty:
            # التحليل
            df_analyzed, signal, signal_type, reasons, atr = analyze_market(df)
            current_price = df_analyzed.iloc[-1]['close']
            
            # --- عرض النتائج ---
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(label="السعر الحالي", value=f"{current_price:.4f}")
            with col2:
                st.metric(label="الإشارة", value=signal)
            with col3:
                st.metric(label="قوة الإشارة (Score)", value=f"{len(reasons)} عوامل")

            st.markdown("---")

            # --- حساب مناطق الدخول والخروج (Risk Management) ---
            if "BUY" in signal_type:
                sl = current_price - (1.5 * atr) # وقف الخسارة تحت السعر بـ 1.5 ضعف الـ ATR
                tp1 = current_price + (1.5 * atr) # هدف اول
                tp2 = current_price + (3 * atr)   # هدف ثاني
                
                st.success(f"### 🎯 توصية الشراء لـ {selected_pair}")
                c1, c2, c3, c4 = st.columns(4)
                c1.info(f"**منطقة الدخول:**\n {current_price:.4f}")
                c2.error(f"**وقف الخسارة (SL):**\n {sl:.4f}")
                c3.success(f"**هدف أول (TP1):**\n {tp1:.4f}")
                c4.success(f"**هدف ثاني (TP2):**\n {tp2:.4f}")
                
            elif "SELL" in signal_type:
                sl = current_price + (1.5 * atr)
                tp1 = current_price - (1.5 * atr)
                tp2 = current_price - (3 * atr)
                
                st.error(f"### 📉 توصية البيع (Short) لـ {selected_pair}")
                c1, c2, c3, c4 = st.columns(4)
                c1.info(f"**منطقة الدخول:**\n {current_price:.4f}")
                c2.error(f"**وقف الخسارة (SL):**\n {sl:.4f}")
                c3.success(f"**هدف أول (TP1):**\n {tp1:.4f}")
                c4.success(f"**هدف ثاني (TP2):**\n {tp2:.4f}")
            else:
                st.warning("السوق غير واضح حالياً، يفضل الانتظار.")

            # --- عرض أسباب التحليل ---
            st.write("### 🧠 لماذا تم اتخاذ هذا القرار؟")
            for reason in reasons:
                st.write(f"- {reason}")

            # --- الرسم البياني (Chart) ---
            st.write("### 📈 الرسم البياني (4 ساعات)")
            fig = go.Figure(data=[go.Candlestick(x=df['timestamp'],
                            open=df['open'], high=df['high'],
                            low=df['low'], close=df['close'], name='Price')])
            
            # إضافة المتوسطات للرسم
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='orange', width=1), name='EMA 50'))
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='blue', width=2), name='EMA 200'))

            fig.update_layout(height=600, template='plotly_dark')
            st.plotly_chart(fig, use_container_width=True)

            # عرض البيانات الخام (اختياري)
            with st.expander("عرض البيانات الرقمية"):
                st.dataframe(df.tail(10))

        else:
            st.error("لم نتمكن من جلب البيانات، تأكد من الاتصال بالإنترنت.")

# تذييل الصفحة
st.markdown("---")
st.caption("تم التطوير بواسطة مساعدك الذكي Gemini | البيانات من Binance API")
              
