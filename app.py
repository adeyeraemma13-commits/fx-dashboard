import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import tradingeconomics as te

# Page config
st.set_page_config(
    page_title="FX Live Dashboard",
    page_icon="📊",
    layout="wide"
)

# Title and auto-refresh
st.title("📊 FX Live Dashboard - Technical & Fundamental Analysis")
st.caption("Auto-refreshes every 5 minutes | Last updated: " + datetime.now().strftime("%H:%M:%S WAT"))

# Initialize TradingEconomics API
if 'api' in st.secrets:
    try:
        api_key = st.secrets['api']['tradingeconomics']
        te.login(api_key)
        st.sidebar.success("✅ TradingEconomics API connected")
    except:
        st.sidebar.warning("⚠️ API key not found in secrets.toml")
        te.login('guest:guest')  # Demo mode
else:
    st.sidebar.warning("⚠️ Add API key to .streamlit/secrets.toml")
    te.login('guest:guest')  # Demo mode

# Currency mapping for TradingEconomics
CURRENCY_MAP = {
    'EUR': 'euro-area',
    'USD': 'united states',
    'GBP': 'united kingdom',
    'JPY': 'japan',
    'AUD': 'australia',
    'NZD': 'new zealand',
    'CAD': 'canada',
    'CHF': 'switzerland',
    'CNY': 'china',
    'SEK': 'sweden',
    'NOK': 'norway'
}

# Economic indicators to fetch
INDICATORS = [
    'Inflation Rate',  # CPI
    'Interest Rate',   # Central bank rate
    'GDP Growth Rate',
    'Unemployment Rate',
    'Current Account'
]

# Initialize session state for pairs
if 'pairs' not in st.session_state:
    st.session_state.pairs = ['EURUSD=X']

# Auto-refresh every 5 minutes (300 seconds)
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()

if (datetime.now() - st.session_state.last_refresh).seconds >= 300:
    st.rerun()

# Sidebar for pair management
st.sidebar.header("⚙️ Manage Pairs")
new_pair = st.sidebar.text_input("Add new pair (e.g., GBPUSD=X)", placeholder="EURUSD=X")

if st.sidebar.button("➕ Add Pair"):
    if new_pair and new_pair not in st.session_state.pairs:
        st.session_state.pairs.append(new_pair)
        st.sidebar.success(f"Added {new_pair}!")
    elif new_pair in st.session_state.pairs:
        st.sidebar.warning("Pair already exists!")

st.sidebar.divider()

# Display and allow removal of pairs
st.sidebar.subheader("Active Pairs")
pairs_to_remove = []
for i, pair in enumerate(st.session_state.pairs):
    col1, col2 = st.sidebar.columns([3, 1])
    col1.write(pair.replace('=X', ''))
    if col2.button("❌", key=f"remove_{i}"):
        pairs_to_remove.append(pair)

for pair in pairs_to_remove:
    st.session_state.pairs.remove(pair)

# Helper function to get fundamental bias
def get_fundamental_bias(country, currency):
    """Fetch economic indicators and calculate fundamental bias"""
    try:
        # Get indicator data
        indicators_data = te.getIndicatorData(
            country=country,
            indicator=INDICATORS,
            output_type='df'
        )
        
        if indicators_data.empty:
            return None, {}
        
        # Extract latest values
        latest = indicators_data[indicators_data['Date'] == indicators_data['Date'].max()]
        
        fundamentals = {}
        score = 0
        
        # Inflation Rate (CPI)
        cpi_row = latest[latest['Indicator'] == 'Inflation Rate']
        if not cpi_row.empty:
            cpi = cpi_row['Last'].iloc[0]
            fundamentals['CPI'] = cpi
            # Higher CPI = more hawkish (good for currency)
            if cpi > 3:
                score += 2
            elif cpi > 2:
                score += 1
            elif cpi < 1:
                score -= 1
        
        # Interest Rate
        rate_row = latest[latest['Indicator'] == 'Interest Rate']
        if not rate_row.empty:
            rate = rate_row['Last'].iloc[0]
            fundamentals['Interest Rate'] = rate
            # Higher rates = more attractive currency
            if rate > 4:
                score += 3
            elif rate > 2:
                score += 2
            elif rate > 0:
                score += 1
            else:
                score -= 1
        
        # GDP Growth
        gdp_row = latest[latest['Indicator'] == 'GDP Growth Rate']
        if not gdp_row.empty:
            gdp = gdp_row['Last'].iloc[0]
            fundamentals['GDP Growth'] = gdp
            if gdp > 2:
                score += 2
            elif gdp > 0:
                score += 1
            else:
                score -= 1
        
        # Unemployment
        unemp_row = latest[latest['Indicator'] == 'Unemployment Rate']
        if not unemp_row.empty:
            unemp = unemp_row['Last'].iloc[0]
            fundamentals['Unemployment'] = unemp
            # Lower unemployment = stronger economy
            if unemp < 4:
                score += 1
            elif unemp > 8:
                score -= 1
        
        # Determine bias
        if score >= 4:
            bias = "🟢 BULLISH"
            bias_color = "green"
        elif score <= -2:
            bias = "🔴 BEARISH"
            bias_color = "red"
        else:
            bias = "🟡 NEUTRAL"
            bias_color = "orange"
        
        return bias, fundamentals
        
    except Exception as e:
        return None, {'Error': str(e)}

# Main dashboard
if not st.session_state.pairs:
    st.warning("No pairs selected. Add a pair in the sidebar!")
    st.stop()

# Create cards for each pair
for pair in st.session_state.pairs:
    st.divider()
    
    # Fetch data
    ticker = yf.Ticker(pair)
    
    try:
        # Get historical data for technicals
        hist = ticker.history(period='1mo', interval='1d')
        hist_1h = ticker.history(period='5d', interval='1h')
        
        if hist.empty:
            st.error(f"No data for {pair}")
            continue
        
        current_price = hist['Close'].iloc[-1]
        price_change = current_price - hist['Close'].iloc[-2]
        price_change_pct = (price_change / hist['Close'].iloc[-2]) * 100
        
        # Calculate technical indicators
        sma_20 = hist['Close'].rolling(20).mean().iloc[-1]
        sma_50 = hist['Close'].rolling(50).mean().iloc[-1] if len(hist) >= 50 else np.nan
        ema_12 = hist['Close'].ewm(span=12).mean().iloc[-1]
        ema_26 = hist['Close'].ewm(span=26).mean().iloc[-1]
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_current = rsi.iloc[-1]
        
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9).mean()
        macd_current = macd.iloc[-1]
        signal_current = signal.iloc[-1]
        
        bb_middle = sma_20
        bb_std = hist['Close'].rolling(20).std().iloc[-1]
        bb_upper = bb_middle + (bb_std * 2)
        bb_lower = bb_middle - (bb_std * 2)
        
        # Technical Bias Calculation
        bullish_signals = 0
        bearish_signals = 0
        
        if current_price > sma_20:
            bullish_signals += 1
        else:
            bearish_signals += 1
            
        if not np.isnan(sma_50) and current_price > sma_50:
            bullish_signals += 1
        elif not np.isnan(sma_50):
            bearish_signals += 1
        
        if ema_12 > ema_26:
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        if rsi_current > 50:
            bullish_signals += 1
        else:
            bearish_signals += 1
            
        if rsi_current > 70:
            bearish_signals += 2
        elif rsi_current < 30:
            bullish_signals += 2
        
        if macd_current > signal_current:
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        if current_price > bb_middle:
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        if bullish_signals > bearish_signals + 2:
            tech_bias = "🟢 BULLISH"
            tech_color = "green"
        elif bearish_signals > bullish_signals + 2:
            tech_bias = "🔴 BEARISH"
            tech_color = "red"
        else:
            tech_bias = "🟡 NEUTRAL"
            tech_color = "orange"
        
        # Extract currencies from pair
        pair_name = pair.replace('=X', '')
        base_currency = pair_name[:3]
        quote_currency = pair_name[3:]
        
        # Get fundamental data for both currencies
        base_country = CURRENCY_MAP.get(base_currency, 'united states')
        quote_country = CURRENCY_MAP.get(quote_currency, 'united states')
        
        with st.spinner(f"Loading fundamentals for {pair_name}..."):
            base_fund_bias, base_fundamentals = get_fundamental_bias(base_country, base_currency)
            quote_fund_bias, quote_fundamentals = get_fundamental_bias(quote_country, quote_currency)
        
        # Calculate overall fundamental bias for the pair
        fund_bias = "🟡 NEUTRAL"
        if base_fund_bias == "🟢 BULLISH" and quote_fund_bias == "🔴 BEARISH":
            fund_bias = "🟢 BULLISH"
        elif base_fund_bias == "🔴 BEARISH" and quote_fund_bias == "🟢 BULLISH":
            fund_bias = "🔴 BEARISH"
        elif base_fund_bias == "🟢 BULLISH" and quote_fund_bias == "🟡 NEUTRAL":
            fund_bias = "🟢 Bullish (base)"
        elif base_fund_bias == "🔴 BEARISH" and quote_fund_bias == "🟡 NEUTRAL":
            fund_bias = "🔴 Bearish (base)"
        elif base_fund_bias == "🟡 NEUTRAL" and quote_fund_bias == "🟢 BULLISH":
            fund_bias = "🔴 Bearish (quote)"
        elif base_fund_bias == "🟡 NEUTRAL" and quote_fund_bias == "🔴 BEARISH":
            fund_bias = "🟢 Bullish (quote)"
        
        # Display pair card
        st.subheader(f"🔹 {pair_name}")
        
        # Price section
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Price", f"{current_price:.5f}", f"{price_change_pct:.2f}%")
        col2.metric("20-Day SMA", f"{sma_20:.5f}")
        col3.metric("RSI (14)", f"{rsi_current:.1f}", 
                    "Overbought" if rsi_current > 70 else "Oversold" if rsi_current < 30 else "Neutral")
        col4.markdown(f"**Technical Bias:** {tech_bias}")
        
        # Detailed technicals
        with st.expander("📈 Detailed Technical Indicators"):
            st.markdown("#### Moving Averages")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.write(f"- **SMA 20:** {sma_20:.5f}")
                st.write(f"- **SMA 50:** {sma_50:.5f}" if not np.isnan(sma_50) else "- **SMA 50:** N/A")
                st.write(f"- **EMA 12:** {ema_12:.5f}")
                st.write(f"- **EMA 26:** {ema_26:.5f}")
            
            with col_t2:
                st.markdown("#### MACD")
                st.write(f"- **MACD Line:** {macd_current:.5f}")
                st.write(f"- **Signal Line:** {signal_current:.5f}")
                st.write(f"- **Histogram:** {macd_current - signal_current:.5f}")
                if macd_current > signal_current:
                    st.success("✅ Bullish Crossover")
                else:
                    st.error("❌ Bearish Crossover")
            
            st.markdown("#### Bollinger Bands")
            st.write(f"- **Upper Band:** {bb_upper:.5f}")
            st.write(f"- **Middle Band:** {bb_middle:.5f}")
            st.write(f"- **Lower Band:** {bb_lower:.5f}")
            band_position = ((current_price - bb_lower) / (bb_upper - bb_lower) * 100)
            st.write(f"**Price Position:** {band_position:.1f}% of band width")
            if band_position > 80:
                st.warning("⚠️ Price near upper band (potential resistance)")
            elif band_position < 20:
                st.warning("⚠️ Price near lower band (potential support)")
        
        # Fundamentals section
        with st.expander("📰 Fundamental Analysis"):
            st.markdown(f"#### Overall Fundamental Bias: {fund_bias}")
            
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                st.markdown(f"### {base_currency} ({base_country.title()})")
                if base_fund_bias:
                    st.markdown(f"**Bias:** {base_fund_bias}")
                else:
                    st.warning("Data unavailable")
                
                st.markdown("#### Key Indicators:")
                if base_fundamentals:
                    if 'CPI' in base_fundamentals:
                        st.write(f"📈 **Inflation (CPI):** {base_fundamentals['CPI']:.2f}%")
                    if 'Interest Rate' in base_fundamentals:
                        st.write(f"🏦 **Interest Rate:** {base_fundamentals['Interest Rate']:.2f}%")
                    if 'GDP Growth' in base_fundamentals:
                        st.write(f"💰 **GDP Growth:** {base_fundamentals['GDP Growth']:.2f}%")
                    if 'Unemployment' in base_fundamentals:
                        st.write(f"👥 **Unemployment:** {base_fundamentals['Unemployment']:.2f}%")
                else:
                    st.error("No data available")
            
            with col_f2:
                st.markdown(f"### {quote_currency} ({quote_country.title()})")
                if quote_fund_bias:
                    st.markdown(f"**Bias:** {quote_fund_bias}")
                else:
                    st.warning("Data unavailable")
                
                st.markdown("#### Key Indicators:")
                if quote_fundamentals:
                    if 'CPI' in quote_fundamentals:
                        st.write(f"📈 **Inflation (CPI):** {quote_fundamentals['CPI']:.2f}%")
                    if 'Interest Rate' in quote_fundamentals:
                        st.write(f"🏦 **Interest Rate:** {quote_fundamentals['Interest Rate']:.2f}%")
                    if 'GDP Growth' in quote_fundamentals:
                        st.write(f"💰 **GDP Growth:** {quote_fundamentals['GDP Growth']:.2f}%")
                    if 'Unemployment' in quote_fundamentals:
                        st.write(f"👥 **Unemployment:** {quote_fundamentals['Unemployment']:.2f}%")
                else:
                    st.error("No data available")
            
            # Economic calendar
            st.markdown("#### 📅 Recent Economic Events")
            try:
                calendar_data = te.getCalendarData(country=[base_country, quote_country])
                if calendar_data and not calendar_data.empty:
                    recent = calendar_data[calendar_data['Date'] >= (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')]
                    if not recent.empty:
                        st.dataframe(recent[['Date', 'Country', 'Event', 'Actual', 'Forecast', 'Previous']].head(10))
                    else:
                        st.info("No recent events in the last 7 days")
            except:
                st.info("Calendar data unavailable in demo mode")
        
        # Mini chart
        with st.expander("📊 Price Chart (5 Days)"):
            if not hist_1h.empty:
                st.line_chart(hist_1h['Close'])
            else:
                st.write("No intraday data available")
        
        # Combined signals summary
        with st.expander("🎯 Trading Signals Summary"):
            col_s1, col_s2, col_s3 = st.columns(3)
            
            with col_s1:
                st.markdown(f"### {tech_bias}")
                st.write("Technical Analysis")
            
            with col_s2:
                st.markdown(f"### {fund_bias}")
                st.write("Fundamental Analysis")
            
            with col_s3:
                if tech_bias == fund_bias and "🟡" not in tech_bias and "🟡" not in fund_bias:
                    st.markdown("### 🎯 STRONG SIGNAL")
                    st.write("Both align")
                elif "🟡" in tech_bias or "🟡" in fund_bias:
                    st.markdown("### ⚠️ MIXED")
                    st.write("One signal neutral")
                else:
                    st.markdown("### ⚠️ CONFLICT")
                    st.write("Diverging signals")
        
    except Exception as e:
        st.error(f"Error loading {pair}: {str(e)}")

# Footer
st.divider()
st.caption("""
**Data Sources:** 
- **Prices & Technicals:** Yahoo Finance (1-2 min delay)
- **Fundamentals:** TradingEconomics API

**Note:** Free API tier provides limited requests. For high-frequency updates, consider:
- Upgrading TradingEconomics API plan
- Implementing data caching
- Reducing refresh frequency
""")

# Manual refresh button
if st.button("🔄 Refresh Now"):
    st.rerun()
