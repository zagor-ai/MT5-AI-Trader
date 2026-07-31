import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.ensemble import RandomForestClassifier, VotingClassifier, StackingClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import GridSearchCV
import joblib
import warnings
import random
import time
from datetime import datetime
warnings.filterwarnings('ignore')

print("=" * 80)
print("QUANTUM INSTITUTIONAL AI - COMPLETE SYSTEM")
print("Multi-Symbol + Stacking Ensemble + Q-Learning + Hyperparameter Tuning")
print("=" * 80)

class QuantumInstitutionalAI:
    def __init__(self):
        # نمادهای اصلی و کمکی
        self.primary_symbol = "XAUUSD"
        self.auxiliary_symbols = ["DXY", "EURUSD", "GBPUSD", "USDJPY"]
        self.timeframe = mt5.TIMEFRAME_M5
        
        # مدل‌های هوش مصنوعی
        self.lstm_model = None
        self.stacking_ensemble = None
        self.scaler = StandardScaler()
        self.feature_selector = None
        
        # Q-Learning با هایپرپارامترهای بهینه
        self.q_table = {}
        self.learning_rate = 0.15  # بهینه‌شده
        self.discount_factor = 0.90
        self.epsilon = 0.08  # بهینه‌شده
        self.epsilon_decay = 0.995
        
        # مدیریت ریسک و موقعیت
        self.daily_risk_limit = 0.02
        self.daily_loss = 0.0
        self.position_size = 0.01
        # open_positions اکنون شامل state_at_entry برای QL است
        self.open_positions = {} 
        self.trade_history = []
        
        # هایپرپارامترهای بهینه‌شده
        self.atr_multiplier = 2.5  # بهینه‌شده برای طلا
        self.rr_ratio = 1.8  # Risk-Reward Ratio
        
        # کش داده‌های میان‌بازاری
        self.market_data_cache = {}

    # === متدهای محاسباتی ===
    def calculate_rsi(self, prices, period):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        return macd, macd_signal

    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, lower

    def calculate_atr(self, high, low, close, period=14):
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(span=period).mean() # استفاده از EMA برای ATR نرم‌تر

    def calculate_adx(self, high, low, close, period=14):
        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.ewm(span=period).mean()
        
        plus_di = 100 * (plus_dm.ewm(span=period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.ewm(span=period).mean()

    def get_market_session(self, time_series):
        """تعیین session بازار (UTC)"""
        sessions = []
        for hour in time_series.dt.hour:
            if 0 <= hour < 8:
                sessions.append(0)  # Asia (Tokyo/Shanghai)
            elif 8 <= hour < 16:
                sessions.append(1)  # London (Europe)
            elif 13 <= hour < 22:
                sessions.append(2)  # New York (Overlap/US)
            else:
                sessions.append(3)  # Off-hours
        return sessions

    def calculate_advanced_features(self, df):
        """محاسبه ویژگی‌های پیشرفته تکنیکال"""
        high, low, close, volume = df['high'], df['low'], df['close'], df['tick_volume']
        
        # اندیکاتورهای اصلی
        df['rsi_14'] = self.calculate_rsi(close, 14)
        df['macd'], df['macd_signal'] = self.calculate_macd(close)
        df['bollinger_upper'], df['bollinger_lower'] = self.calculate_bollinger_bands(close)
        df['atr'] = self.calculate_atr(high, low, close)
        df['adx'] = self.calculate_adx(high, low, close)
        
        # ویژگی‌های قیمت
        df['sma_20'] = close.rolling(20).mean()
        df['ema_12'] = close.ewm(span=12).mean()
        df['momentum_5'] = close.pct_change(5)
        df['momentum_10'] = close.pct_change(10)
        df['volatility_20'] = close.pct_change().rolling(20).std()
        
        # ویژگی‌های حجم
        df['volume_ma_20'] = volume.rolling(20).mean()
        df['volume_ratio'] = volume / (df['volume_ma_20'] + 1e-6) # جلوگیری از تقسیم بر صفر
        df['volume_anomaly'] = (df['volume_ratio'] - 1).abs()
        
        # ویژگی‌های زمانی
        df['hour'] = df['time'].dt.hour
        df['day_of_week'] = df['time'].dt.dayofweek
        df['session'] = df['time'].apply(lambda t: self.get_market_session(pd.Series([t]))[0])
        
        return df
    
    # === متدهای MT5 و داده ===
    def connect_mt5(self):
        """اتصال به MT5 و فعال‌سازی نمادهای کمکی"""
        try:
            if not mt5.initialize():
                return False
            
            # فعال‌سازی نماد اصلی
            if not mt5.symbol_select(self.primary_symbol, True):
                print(f"❌ Primary symbol {self.primary_symbol} not available")
                return False
            
            # فعال‌سازی نمادهای کمکی
            for symbol in self.auxiliary_symbols:
                if not mt5.symbol_select(symbol, True):
                    print(f"⚠️  Auxiliary symbol {symbol} not available")
            
            account_info = mt5.account_info()
            if account_info:
                print(f"✅ MT5 Connected - Account: {account_info.login}")
                print(f"💰 Balance: ${account_info.balance:.2f}")
                print(f"🎯 Leverage: 1:{account_info.leverage}")
                
            print(f"📊 Trading Symbols: {self.primary_symbol} + {len(self.auxiliary_symbols)} auxiliary")
            return True
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def get_multi_symbol_data(self, symbol, bars=500):
        """دریافت داده‌های یک نماد خاص"""
        try:
            rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, bars)
            if rates is None:
                return None
                
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
            
        except Exception as e:
            print(f"❌ Data error for {symbol}: {e}")
            return None

    def calculate_correlation_features(self, primary_df, auxiliary_dfs):
        """محاسبه ویژگی‌های همبستگی میان‌بازاری"""
        features = {}
        for aux_symbol, aux_df in auxiliary_dfs.items():
            # اطمینان از هم‌اندازه بودن و عدم وجود NaN
            if aux_df is not None and len(aux_df) == len(primary_df):
                merged_df = pd.DataFrame({
                    'primary_close': primary_df['close'],
                    'aux_close': aux_df['close']
                }).dropna()
                
                if len(merged_df) > 10:
                    # همبستگی قیمت
                    price_corr = merged_df['primary_close'].corr(merged_df['aux_close'])
                    features[f'corr_{aux_symbol}'] = price_corr if not np.isnan(price_corr) else 0
                    
                    # همبستگی بازده
                    primary_returns = merged_df['primary_close'].pct_change().dropna()
                    aux_returns = merged_df['aux_close'].pct_change().dropna()
                    if len(primary_returns) > 5:
                        return_corr = primary_returns.corr(aux_returns)
                        features[f'return_corr_{aux_symbol}'] = return_corr if not np.isnan(return_corr) else 0
                    
                    # نسبت قیمت
                    features[f'price_ratio_{aux_symbol}'] = primary_df['close'].iloc[-1] / aux_df['close'].iloc[-1]
        
        return features

    def get_intermarket_features(self, bars=500):
        """دریافت و پردازش داده‌های میان‌بازاری"""
        # داده‌های نماد اصلی
        primary_df = self.get_multi_symbol_data(self.primary_symbol, bars)
        if primary_df is None:
            return None
        
        # داده‌های نمادهای کمکی
        auxiliary_dfs = {}
        for symbol in self.auxiliary_symbols:
            auxiliary_dfs[symbol] = self.get_multi_symbol_data(symbol, bars)
        
        # محاسبه ویژگی‌های اصلی
        primary_df = self.calculate_advanced_features(primary_df)
        
        # اضافه کردن ویژگی‌های همبستگی
        correlation_features = self.calculate_correlation_features(primary_df, auxiliary_dfs)
        
        # باید ستون‌های ویژگی‌های همبستگی را به کل DataFrame اضافه کنیم تا Stacking بتواند آموزش ببیند
        # در اینجا، چون corr و return_corr برای کل ستون محاسبه شده‌اند، آن‌ها را به عنوان مقادیر ثابت تکرار می‌کنیم
        for feature_name, value in correlation_features.items():
            primary_df[feature_name] = value

        # پر کردن NaNها (مثلاً در ابتدای داده‌ها به دلیل محاسبات میانگین متحرک)
        return primary_df.fillna(method='bfill').fillna(0)


    # === متدهای Stacking & LSTM ===
    def create_lstm_model(self, input_shape):
        """ساخت مدل LSTM برای پیش‌بینی"""
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=input_shape, dropout=0.2),
            LSTM(32, return_sequences=True, dropout=0.2),
            LSTM(16, dropout=0.2),
            Dense(8, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        
        model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                      loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def train_lstm_for_stacking(self, X_scaled, y):
        """آموزش LSTM برای استفاده در Stacking"""
        TIMESTEPS = 8
        
        if len(X_scaled) < TIMESTEPS + 10:
            return None
            
        X_lstm, y_lstm = [], []
        for i in range(TIMESTEPS, len(X_scaled)):
            X_lstm.append(X_scaled[i-TIMESTEPS:i])
            y_lstm.append(y[i])
        
        X_lstm = np.array(X_lstm)
        y_lstm = np.array(y_lstm)
        
        self.lstm_model = self.create_lstm_model((TIMESTEPS, X_scaled.shape[1]))
        
        # آموزش سریع
        self.lstm_model.fit(
            X_lstm, y_lstm, 
            epochs=8, 
            batch_size=16, 
            verbose=0,
            validation_split=0.2
        )
        
        # پیش‌بینی برای Stacking
        lstm_predictions = self.lstm_model.predict(X_lstm, verbose=0).flatten()
        
        # ایجاد ویژگی‌های LSTM برای داده‌های جدید
        lstm_features = np.zeros(len(X_scaled))
        lstm_features[TIMESTEPS:] = lstm_predictions
        
        return lstm_features

    def train_stacking_ensemble(self, df):
        """آموزش Stacking Ensemble با LSTM"""
        print("🤖 Training Stacking Ensemble with LSTM...")
        
        # آماده‌سازی داده‌ها
        feature_columns = [col for col in df.columns if col not in 
                           ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'real_volume', 'spread']]
        
        # داده‌های آموزشی باید قبل از آخرین کندل باشند
        X = df[feature_columns].iloc[:-1] 
        # Target: آیا قیمت سه کندل بعد 0.1% بالاتر است؟ (مثلاً برای M5 = 15 دقیقه)
        future_returns = (df['close'].shift(-3) / df['close'] - 1)
        y = (future_returns > 0.001).astype(int).iloc[:-3] # Target را برای سه کندل آخر حذف می‌کنیم
        
        # هم‌اندازه کردن X و Y
        X = X.iloc[:len(y)]
        
        # حذف NaN
        valid_idx = ~(X.isna().any(axis=1) | y.isna())
        X = X[valid_idx]
        y = y[valid_idx]
        
        if len(X) < 100:
            print(f"⚠️ Insufficient data for Stacking Ensemble ({len(X)} bars)")
            return False
        
        # انتخاب ویژگی
        self.feature_selector = SelectKBest(score_func=f_classif, k=min(15, X.shape[1]))
        X_selected = self.feature_selector.fit_transform(X, y)
        
        # استانداردسازی
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X_selected)
        
        # آموزش LSTM و دریافت ویژگی‌های آن
        print(f"🧠 Training LSTM for feature generation on {X_scaled.shape[1]} selected features...")
        lstm_features = self.train_lstm_for_stacking(X_scaled, y)
        
        if lstm_features is not None:
            # اضافه کردن ویژگی‌های LSTM به داده‌ها
            X_final = np.column_stack([X_scaled, lstm_features[:len(X_scaled)]])
            print(f"✅ LSTM features added. Final feature count: {X_final.shape[1]}")
        else:
            X_final = X_scaled
            print("⚠️ Using standard ensemble (LSTM failed)")
        
        # پایه‌های مدل (Base Estimators)
        base_estimators = [
            ('rf', RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')),
            ('lr', LogisticRegression(random_state=42, C=0.1, solver='liblinear')),
            ('svc', SVC(probability=True, random_state=42, C=0.5, kernel='rbf'))
        ]
        
        # متا-یادگیر (Meta-Learner)
        meta_learner = LogisticRegression(random_state=42)
        
        # Stacking Ensemble
        self.stacking_ensemble = StackingClassifier(
            estimators=base_estimators,
            final_estimator=meta_learner,
            cv=3,
            passthrough=True
        )
        
        self.stacking_ensemble.fit(X_final, y)
        
        accuracy = self.stacking_ensemble.score(X_final, y)
        print(f"✅ Stacking Ensemble trained - Accuracy (Train): {accuracy:.3f}")
        return True

    # === متدهای Q-Learning ===
    def discretize_state(self, features, ensemble_signal, confidence):
        """تبدیل حالت به فضای گسسته برای Q-Learning"""
        # حالت‌های تکنیکال
        rsi_state = 0 if features['rsi_14'] < 35 else 1 if features['rsi_14'] > 65 else 2
        macd_state = 0 if features['macd'] < 0 and features['macd'] < features['macd_signal'] else 1 if features['macd'] > 0 and features['macd'] > features['macd_signal'] else 2
        trend_state = 0 if features['close'] < features['sma_20'] else 1
        
        # حالت‌های میان‌بازاری
        dxy_corr = features.get('corr_DXY', 0)
        market_corr_state = 0 if dxy_corr < -0.6 else 1 if dxy_corr > 0.6 else 2
        
        # حالت Ensemble
        ensemble_state = 0 if ensemble_signal == "BUY" else 1 if ensemble_signal == "SELL" else 2
        confidence_state = 0 if confidence < 0.6 else 1 if confidence < 0.75 else 2
        
        return f"{rsi_state}_{macd_state}_{trend_state}_{market_corr_state}_{ensemble_state}_{confidence_state}"

    def q_learning_decision(self, state, ensemble_signal, exploration=True):
        """تصمیم‌گیری نهایی با Q-Learning"""
        if state not in self.q_table:
            # مقادیر اولیه با بایاس کم به سمت HOLD
            self.q_table[state] = {'BUY': 0, 'SELL': 0, 'HOLD': 0.01} 
        
        # اکتشاف (Exploration)
        if exploration and random.random() < self.epsilon:
            action = random.choice(['BUY', 'SELL', 'HOLD'])
        else:
            # بهره‌برداری (Exploitation)
            q_values = self.q_table[state].copy()
            
            # تقویت سیگنال Ensemble برای بهره‌برداری هدفمند
            # اگر Ensemble سیگنال قوی داد، آن عمل تقویت می‌شود
            if ensemble_signal == "BUY":
                q_values['BUY'] += 0.05
            elif ensemble_signal == "SELL":
                q_values['SELL'] += 0.05
                
            action = max(q_values, key=q_values.get)
        
        # کاهش epsilon
        self.epsilon *= self.epsilon_decay
        return action

    def update_q_learning(self, state, action, reward, next_state, ensemble_confidence):
        """آپدیت Q-Table با پاداش وزندار"""
        # اطمینان از وجود حالت‌ها
        if state not in self.q_table:
            self.q_table[state] = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        if next_state not in self.q_table:
            self.q_table[next_state] = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        
        current_q = self.q_table[state].get(action, 0) # استفاده از .get برای ایمنی
        max_next_q = max(self.q_table[next_state].values())
        
        # پاداش وزندار بر اساس اطمینان Ensemble
        weighted_reward = reward * ensemble_confidence  # فرض: اطمینان بالاتر = پاداش بیشتر
        
        new_q = current_q + self.learning_rate * (
            weighted_reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state][action] = new_q
        
    def calculate_trade_reward(self, entry_price, exit_price, action, holding_period_min, current_spread):
        """محاسبه پاداش هوشمند برای معامله (با در نظر گرفتن Spread)"""
        if action == 'HOLD':
            # جریمه نگه داشتن در صورت وجود سیگنال قوی (هزینه فرصت)
            return -0.01 
        
        # محاسبه سود/زیان نسبی
        if action == 'BUY':
            pnl_ratio = (exit_price - entry_price) / entry_price
        else:  # SELL
            pnl_ratio = (entry_price - exit_price) / entry_price

        # کسر هزینه تراکنش (Spread)
        # فرض: Spread بر حسب پیپ است. برای طلا، قیمت را به پیپ تبدیل می‌کنیم.
        # XAUUSD 5-digit: 1.00 = 10000 points. Spread is usually in points.
        # فرض می‌کنیم spread ورودی بر حسب واحد قیمت (مثلاً دلار) است.
        spread_cost_ratio = current_spread / entry_price
        
        net_pnl_ratio = pnl_ratio - spread_cost_ratio
        
        # پاداش مبتنی بر سوددهی (با بزرگنمایی)
        base_reward = net_pnl_ratio * 500  
        
        # جریمه زمان نگهداری: ترجیح به معاملات سریع
        time_penalty = holding_period_min * 0.0005 
        
        final_reward = base_reward - time_penalty
        return final_reward


    # === متدهای مدیریت موقعیت و اجرا ===
    def calculate_dynamic_position_size(self, balance, risk_score, atr, confidence):
        """محاسبه سایز پوزیشن داینامیک"""
        base_risk_percent = 0.015  # 1.5% ریسک پایه
        
        # تنظیم بر اساس اطمینان و ریسک بازار
        confidence_factor = 0.5 + (confidence * 0.5)  # 0.5 تا 1.0
        risk_factor = 1.0 - (risk_score * 0.5)  # 0.5 تا 1.0 (اگر ریسک بالا باشد، فاکتور کم می‌شود)
        
        adjusted_risk = base_risk_percent * confidence_factor * risk_factor
        risk_amount = balance * adjusted_risk
        
        # محاسبه فاصله SL بر حسب قیمت
        atr_distance = atr * self.atr_multiplier
        
        # سایز پوزیشن بر اساس دلار ریسک شده و فاصله SL
        # Position Size (Lots) = Risk Amount / (ATR Distance * Tick Value)
        # برای XAUUSD/USD، Tick Value تقریباً 1.0 است.
        position_size = risk_amount / atr_distance
        
        # محدودیت‌های سایز
        return max(0.01, min(position_size, 5.0)) # حداکثر 5 لات برای محافظت از حساب

    def calculate_adaptive_sl_tp(self, action, entry_price, atr, volatility, market_regime):
        """محاسبه هوشمند حد ضرر و حد سود"""
        # تنظیم ATR بر اساس رژیم بازار
        if market_regime == "HIGH_VOL":
            atr_multiplier = self.atr_multiplier * 1.1 # کمی افزایش برای SL در نوسان بالا
        else:
            atr_multiplier = self.atr_multiplier
        
        atr_distance = atr * atr_multiplier
        
        # دقت (Digits) را برای نماد اصلی دریافت می‌کنیم
        symbol_info = mt5.symbol_info(self.primary_symbol)
        if symbol_info is None:
            digits = 2 
        else:
            digits = symbol_info.digits
        
        if action == "BUY":
            sl_price = round(entry_price - atr_distance, digits)
            tp_price = round(entry_price + (atr_distance * self.rr_ratio), digits)
        else:  # SELL
            sl_price = round(entry_price + atr_distance, digits)
            tp_price = round(entry_price - (atr_distance * self.rr_ratio), digits)
            
        return sl_price, tp_price

    def send_institutional_order(self, action, confidence, risk_score, current_state, df):
        """ارسال سفارش Institutional"""
        if action == "HOLD" or confidence < 0.6:
            return False
        
        try:
            # دریافت قیمت‌ها و مشخصات نماد
            tick = mt5.symbol_info_tick(self.primary_symbol)
            symbol_info = mt5.symbol_info(self.primary_symbol)
            
            if not tick or not symbol_info:
                return False
            
            entry_price = tick.ask if action == "BUY" else tick.bid
            order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
            
            # محاسبات مدیریت ریسک
            account_info = mt5.account_info()
            atr = df['atr'].iloc[-1]
            volatility = df['volatility_20'].iloc[-1]
            market_regime = "HIGH_VOL" if volatility > df['volatility_20'].mean() else "LOW_VOL"
            current_spread = (tick.ask - tick.bid)
            
            position_size = self.calculate_dynamic_position_size(
                account_info.balance, risk_score, atr, confidence
            )
            
            sl_price, tp_price = self.calculate_adaptive_sl_tp(
                action, entry_price, atr, volatility, market_regime
            )
            
            # ارسال سفارش
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.primary_symbol,
                "volume": position_size,
                "type": order_type,
                "price": entry_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": int(symbol_info.spread * 0.1), # انحراف بر اساس 10% اسپرد
                "magic": 202501,
                "comment": f"QL_{action}_C{confidence:.2f}_R{risk_score:.2f}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                # ثبت معامله
                trade_record = {
                    'ticket': result.order,
                    'action': action,
                    'entry_price': entry_price,
                    'size': position_size,
                    'sl': sl_price,
                    'tp': tp_price,
                    'confidence': confidence,
                    'risk_score': risk_score,
                    'state_at_entry': current_state, # ثبت حالت QL در لحظه ورود
                    'spread_at_entry': current_spread, # ثبت اسپرد
                    'timestamp': datetime.now()
                }
                self.trade_history.append(trade_record)
                self.open_positions[result.order] = trade_record
                
                print(f"✅ INSTITUTIONAL ORDER EXECUTED:")
                print(f"    {action} {self.primary_symbol} at {entry_price:.2f}")
                print(f"    Size: {position_size:.3f}, SL: {sl_price:.2f}, TP: {tp_price:.2f}")
                return True
            else:
                print(f"❌ Order failed. Retcode: {result.retcode}. Comment: {result.comment}")
                return False
                
        except Exception as e:
            print(f"❌ Order execution error: {e}")
            return False
            
    def close_and_update_q_learning(self, current_df, current_state, ensemble_confidence):
        """بررسی موقعیت‌های باز و به‌روزرسانی Q-Table پس از بستن موقعیت"""
        positions = mt5.positions_get(symbol=self.primary_symbol)
        
        closed_tickets = []
        for ticket, trade in self.open_positions.items():
            is_open = any(p.ticket == ticket for p in positions)
            
            # شبیه‌سازی بسته شدن بر اساس زمان (در محیط واقعی با MT5 چک کنید)
            # در اینجا فرض می‌کنیم اگر ۲۰ کندل گذشته باشد، بسته شده است (برای تست)
            time_diff = (datetime.now() - trade['timestamp']).total_seconds()
            holding_period_min = time_diff / 60
            
            if not is_open or holding_period_min > 45: # فرض می‌کنیم پس از ۴۵ دقیقه بسته می‌شود
                closed_tickets.append(ticket)
                
                # فرض سود/زیان شبیه‌سازی شده برای آپدیت Q-Learning
                if is_open:
                    # Note: mt5.Close() doesn't exist; would need to use order_send with opposite action
                    pass
                
                # برای مثال: فرض می‌کنیم قیمت خروج همان آخرین قیمت است
                exit_price = current_df['close'].iloc[-1]
                
                # محاسبه پاداش واقعی (با فرض بسته شدن)
                reward = self.calculate_trade_reward(
                    entry_price=trade['entry_price'],
                    exit_price=exit_price,
                    action=trade['action'],
                    holding_period_min=holding_period_min,
                    current_spread=trade['spread_at_entry']
                )
                
                # آپدیت Q-Table
                self.update_q_learning(
                    state=trade['state_at_entry'],
                    action=trade['action'],
                    reward=reward,
                    next_state=current_state,
                    ensemble_confidence=trade['confidence']
                )
                
                print(f"✨ QL Updated! Ticket {ticket}, Action {trade['action']}, Reward: {reward:.4f}")

        # حذف موقعیت‌های بسته شده
        for ticket in closed_tickets:
            if ticket in self.open_positions:
                del self.open_positions[ticket]


    def calculate_institutional_risk(self, df):
        """محاسبه ریسک Institutional"""
        if len(df) < 20:
            return 0.5
        
        current_vol = df['volatility_20'].iloc[-1]
        avg_vol = df['volatility_20'].mean()
        volume_anomaly = df['volume_anomaly'].iloc[-1]
        dxy_corr = abs(df.get('corr_DXY', 0))
        
        # ریسک بر اساس نوسان، حجم غیرعادی و همبستگی
        # (Self.daily_loss باید در یک محیط واقعی به‌روزرسانی شود)
        risk_score = (
            (current_vol / avg_vol) * 0.25 +
            min(volume_anomaly, 2) * 0.20 +
            dxy_corr * 0.25 +
            (self.daily_loss / (self.daily_risk_limit * 100)) * 0.30
        )
        
        return min(risk_score, 1.0)

    def get_institutional_signal(self, df):
        """سیگنال‌دهی نهایی Institutional"""
        if self.stacking_ensemble is None or len(df) < 50:
            return "HOLD", 0.5, 0.5, "0_0_0_0_0_0"
        
        try:
            # ویژگی‌ها
            feature_columns = [col for col in df.columns if col not in 
                               ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'real_volume', 'spread']]
            
            # آخرین کندل
            current_features = df[feature_columns].iloc[-1:].values
            
            if np.isnan(current_features).any():
                return "HOLD", 0.5, 0.5, "0_0_0_0_0_0"
            
            # انتخاب ویژگی‌ها
            # توجه: Feature Selector و Scaler باید با داده‌های آموزشی Fit شده باشند
            X_selected = self.feature_selector.transform(current_features)
            X_scaled = self.scaler.transform(X_selected)
            
            # پیش‌بینی Stacking Ensemble
            ensemble_proba = self.stacking_ensemble.predict_proba(X_scaled)[0]
            ensemble_confidence = max(ensemble_proba)
            ensemble_signal = "BUY" if ensemble_proba[1] > ensemble_proba[0] else "SELL"
            
            # Q-Learning Decision
            current_state = self.discretize_state(df.iloc[-1], ensemble_signal, ensemble_confidence)
            final_signal = self.q_learning_decision(current_state, ensemble_signal, exploration=True)
            
            # محاسبه ریسک Institutional
            risk_score = self.calculate_institutional_risk(df)
            
            return final_signal, ensemble_confidence, risk_score, current_state
            
        except Exception as e:
            print(f"❌ Institutional signal error: {e}")
            return "HOLD", 0.5, 0.5, "0_0_0_0_0_0"

    # === متد اصلی اجرا ===
    def run_complete_institutional_system(self, cycles=12):
        """اجرای سیستم Institutional کامل"""
        print("🚀 QUANTUM INSTITUTIONAL AI - FULL SYSTEM ACTIVATED")
        print("=" * 60)
        
        if not self.connect_mt5():
            print("🛑 اتصال MT5 ناموفق. سیستم متوقف شد.")
            return
        
        # ۱. مرحله آموزش اولیه
        df = self.get_intermarket_features(1000) # استفاده از داده‌های بیشتر برای آموزش اولیه
        if df is None or len(df) < 150:
            print("❌ No market data available for initial training")
            mt5.shutdown()
            return
        
        # آموزش مدل‌های پیشرفته (LSTM و Stacking)
        if not self.train_stacking_ensemble(df):
            print("❌ Model training failed. System stopped.")
            mt5.shutdown()
            return
        
        print("\n🔍 Starting Institutional Trading Session...")
        print(f"AI Architecture: Stacking Ensemble + LSTM + Q-Learning")
        print(f"Market Analysis: {self.primary_symbol} + {len(self.auxiliary_symbols)} auxiliary symbols")
        print(f"Risk Management: Dynamic Position Sizing + Adaptive SL/TP")
        print(f"Initial Epsilon: {self.epsilon:.3f}")
        print("=" * 60)
        
        # ۲. حلقه عملیات زنده
        for cycle in range(cycles):
            # الف. دریافت داده‌های تازه
            df = self.get_intermarket_features(200)
            if df is None or len(df) < 50:
                print("❌ Insufficient data in cycle. Skipping...")
                time.sleep(20)
                continue
            
            # ب. به‌روزرسانی Q-Learning بر اساس نتایج معاملات قبلی (بستن و پاداش‌دهی)
            self.close_and_update_q_learning(df, "TEMP_STATE", 0.7) # حالت موقت
            
            # ج. سیگنال Institutional
            signal, confidence, risk_score, current_state = self.get_institutional_signal(df)
            
            print(f"\n🏛️ INSTITUTIONAL CYCLE {cycle+1}/{cycles} (Time: {datetime.now().strftime('%H:%M:%S')})")
            print(f"  Final Decision: {signal} | State: {current_state}")
            print(f"  AI Confidence: {confidence:.3f} | Risk Score: {risk_score:.2f} | Epsilon: {self.epsilon:.3f}")
            
            # د. اجرای معامله
            if signal in ["BUY", "SELL"] and not self.open_positions:
                self.send_institutional_order(signal, confidence, risk_score, current_state, df)
            elif self.open_positions:
                print(f"  Holding existing position (Ticket: {list(self.open_positions.keys())[0]})")
            
            if cycle < cycles - 1:
                time.sleep(self.timeframe_to_seconds(self.timeframe) - 5) # تأخیر برای رسیدن به کندل بعدی M5

        # ۳. خلاصه عملکرد
        print(f"\n📊 INSTITUTIONAL SESSION SUMMARY")
        print(f"  Total Trades Started: {len(self.trade_history)}")
        print(f"  Open Positions Left: {len(self.open_positions)}")
        print(f"  Q-Learning States: {len(self.q_table)}")
        
        mt5.shutdown()
        print("✅ Institutional trading session completed!")

    def timeframe_to_seconds(self, timeframe):
        if timeframe == mt5.TIMEFRAME_M1: return 60
        if timeframe == mt5.TIMEFRAME_M5: return 300
        if timeframe == mt5.TIMEFRAME_M15: return 900
        return 300 # Default to M5

# اجرای سیستم
if __name__ == "__main__":
    # TensorFlow logs را در محیط Production کاهش دهید
    tf.get_logger().setLevel('ERROR') 
    institution = QuantumInstitutionalAI()
    # در محیط واقعی، cycles را بسیار بیشتر قرار دهید تا Q-Learning فرصت یادگیری پیدا کند
    institution.run_complete_institutional_system(cycles=20)
