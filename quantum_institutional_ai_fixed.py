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
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

# کاهش لاگ‌های TensorFlow
tf.get_logger().setLevel('ERROR')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

print("=" * 80)
print("QUANTUM INSTITUTIONAL AI - PRODUCTION READY")
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
        self.is_fitted = False  # وضعیت fit بودن scaler و feature_selector
        
        # Q-Learning با هایپرپارامترهای بهینه
        self.q_table = {}
        self.learning_rate = 0.15
        self.discount_factor = 0.90
        self.epsilon = 0.08
        self.epsilon_decay = 0.995
        self.min_epsilon = 0.02  # حداقل epsilon برای اکتشاف مداوم
        
        # مدیریت ریسک و موقعیت
        self.daily_risk_limit = 0.02
        self.daily_loss = 0.0
        self.position_size = 0.01
        self.open_positions = {} 
        self.trade_history = []
        
        # هایپرپارامترهای بهینه‌شده
        self.atr_multiplier = 2.5
        self.rr_ratio = 1.8
        
        # کش داده‌های میان‌بازاری
        self.market_data_cache = {}
        
        # تنظیمات بک‌تست
        self.backtest_mode = False
        self.backtest_results = []

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
        return tr.ewm(span=period).mean()

    def calculate_adx(self, high, low, close, period=14):
        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.ewm(span=period).mean()
        
        plus_di = 100 * (plus_dm.ewm(span=period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        return dx.ewm(span=period).mean()

    def get_market_session(self, hour):
        """تعیین session بازار (UTC)"""
        if 0 <= hour < 8:
            return 0  # Asia
        elif 8 <= hour < 16:
            return 1  # London
        elif 13 <= hour < 22:
            return 2  # New York
        else:
            return 3  # Off-hours

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
        df['volume_ratio'] = volume / (df['volume_ma_20'] + 1e-6)
        df['volume_anomaly'] = (df['volume_ratio'] - 1).abs()
        
        # ویژگی‌های زمانی
        df['hour'] = df['time'].dt.hour
        df['day_of_week'] = df['time'].dt.dayofweek
        df['session'] = df['hour'].apply(self.get_market_session)
        
        # پر کردن NaN اولیه
        df = df.fillna(method='bfill').fillna(0)
        
        return df
    
    # === متدهای MT5 و داده ===
    def connect_mt5(self):
        """اتصال به MT5 و فعال‌سازی نمادها"""
        try:
            if not mt5.initialize():
                print(f"❌ MT5 initialization failed: {mt5.last_error()}")
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
            if rates is None or len(rates) == 0:
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
        last_idx = len(primary_df) - 1
        
        for aux_symbol, aux_df in auxiliary_dfs.items():
            if aux_df is None or len(aux_df) < 20:
                continue
                
            # هم‌تراز کردن داده‌ها بر اساس زمان
            merged_df = pd.merge(
                primary_df[['time', 'close']].tail(100),
                aux_df[['time', 'close']].tail(100),
                on='time',
                suffixes=('_primary', f'_{aux_symbol}')
            )
            
            if len(merged_df) < 20:
                continue
            
            # همبستگی قیمت
            price_corr = merged_df[f'close_primary'].corr(merged_df[f'close_{aux_symbol}'])
            features[f'corr_{aux_symbol}'] = price_corr if not np.isnan(price_corr) else 0
            
            # همبستگی بازده
            primary_returns = merged_df[f'close_primary'].pct_change().dropna()
            aux_returns = merged_df[f'close_{aux_symbol}'].pct_change().dropna()
            
            if len(primary_returns) > 10 and len(aux_returns) > 10:
                return_corr = primary_returns.corr(aux_returns)
                features[f'return_corr_{aux_symbol}'] = return_corr if not np.isnan(return_corr) else 0
            
            # نسبت قیمت (آخرین مقدار)
            if len(merged_df) > 0:
                features[f'price_ratio_{aux_symbol}'] = (
                    merged_df[f'close_primary'].iloc[-1] / 
                    (merged_df[f'close_{aux_symbol}'].iloc[-1] + 1e-10)
                )
        
        return features

    def get_intermarket_features(self, bars=500):
        """دریافت و پردازش داده‌های میان‌بازاری"""
        # داده‌های نماد اصلی
        primary_df = self.get_multi_symbol_data(self.primary_symbol, bars)
        if primary_df is None or len(primary_df) < 50:
            return None
        
        # داده‌های نمادهای کمکی
        auxiliary_dfs = {}
        for symbol in self.auxiliary_symbols:
            aux_data = self.get_multi_symbol_data(symbol, bars)
            if aux_data is not None:
                auxiliary_dfs[symbol] = aux_data
        
        # محاسبه ویژگی‌های اصلی
        primary_df = self.calculate_advanced_features(primary_df)
        
        # اضافه کردن ویژگی‌های همبستگی
        correlation_features = self.calculate_correlation_features(primary_df, auxiliary_dfs)
        
        # اضافه کردن ویژگی‌های همبستگی به DataFrame
        for feature_name, value in correlation_features.items():
            primary_df[feature_name] = value

        # پر کردن مقادیر گمشده
        primary_df = primary_df.fillna(method='bfill').fillna(0)
        
        return primary_df


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
        
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy', 
            metrics=['accuracy']
        )
        return model

    def train_lstm_for_stacking(self, X_scaled, y):
        """آموزش LSTM برای استفاده در Stacking"""
        TIMESTEPS = 8
        
        if len(X_scaled) < TIMESTEPS + 20:
            return None
            
        X_lstm, y_lstm = [], []
        for i in range(TIMESTEPS, len(X_scaled)):
            X_lstm.append(X_scaled[i-TIMESTEPS:i])
            y_lstm.append(y[i])
        
        X_lstm = np.array(X_lstm)
        y_lstm = np.array(y_lstm)
        
        # بررسی NaN در داده‌های LSTM
        if np.isnan(X_lstm).any() or np.isnan(y_lstm).any():
            return None
        
        self.lstm_model = self.create_lstm_model((TIMESTEPS, X_scaled.shape[1]))
        
        # آموزش سریع با Early Stopping ضمنی
        try:
            self.lstm_model.fit(
                X_lstm, y_lstm, 
                epochs=8, 
                batch_size=16, 
                verbose=0,
                validation_split=0.2,
                shuffle=False
            )
            
            # پیش‌بینی برای Stacking
            lstm_predictions = self.lstm_model.predict(X_lstm, verbose=0).flatten()
            
            # ایجاد ویژگی‌های LSTM برای داده‌های جدید
            lstm_features = np.zeros(len(X_scaled))
            lstm_features[TIMESTEPS:] = lstm_predictions
            
            return lstm_features
            
        except Exception as e:
            print(f"⚠️  LSTM training failed: {e}")
            return None

    def train_stacking_ensemble(self, df):
        """آموزش Stacking Ensemble با LSTM"""
        print("🤖 Training Stacking Ensemble with LSTM...")
        
        # آماده‌سازی داده‌ها
        exclude_cols = ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'real_volume', 'spread']
        feature_columns = [col for col in df.columns if col not in exclude_cols]
        
        if len(feature_columns) == 0:
            print("❌ No features available for training")
            return False
        
        # داده‌های آموزشی (بدون آخرین کندل برای جلوگیری از lookahead bias)
        X = df[feature_columns].iloc[:-1].copy()
        
        # Target: آیا قیمت سه کندل بعد 0.1% بالاتر است؟
        future_returns = (df['close'].shift(-3) / df['close'] - 1)
        y = (future_returns > 0.001).astype(int)
        
        # حذف سه کندل آخر از target
        y = y.iloc[:-3]
        
        # هم‌اندازه کردن X و Y
        X = X.iloc[:len(y)]
        
        # حذف NaN
        valid_idx = ~(X.isna().any(axis=1) | y.isna())
        X = X[valid_idx]
        y = y[valid_idx]
        
        if len(X) < 100:
            print(f"⚠️  Insufficient data for Stacking Ensemble ({len(X)} bars)")
            return False
        
        # انتخاب ویژگی
        k_features = min(15, X.shape[1])
        self.feature_selector = SelectKBest(score_func=f_classif, k=k_features)
        X_selected = self.feature_selector.fit_transform(X, y)
        
        # استانداردسازی
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X_selected)
        
        # ذخیره وضعیت fit
        self.is_fitted = True
        
        # آموزش LSTM و دریافت ویژگی‌های آن
        print(f"🧠 Training LSTM for feature generation on {X_scaled.shape[1]} selected features...")
        lstm_features = self.train_lstm_for_stacking(X_scaled, y)
        
        if lstm_features is not None and len(lstm_features) == len(X_scaled):
            # اضافه کردن ویژگی‌های LSTM به داده‌ها
            X_final = np.column_stack([X_scaled, lstm_features])
            print(f"✅ LSTM features added. Final feature count: {X_final.shape[1]}")
        else:
            X_final = X_scaled
            print("⚠️  Using standard ensemble (LSTM failed)")
        
        # پایه‌های مدل (Base Estimators)
        base_estimators = [
            ('rf', RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced', n_jobs=-1)),
            ('lr', LogisticRegression(random_state=42, C=0.1, solver='liblinear', max_iter=1000)),
            ('svc', SVC(probability=True, random_state=42, C=0.5, kernel='rbf'))
        ]
        
        # متا-یادگیر (Meta-Learner)
        meta_learner = LogisticRegression(random_state=42, max_iter=1000)
        
        # Stacking Ensemble
        self.stacking_ensemble = StackingClassifier(
            estimators=base_estimators,
            final_estimator=meta_learner,
            cv=3,
            passthrough=True,
            n_jobs=-1
        )
        
        try:
            self.stacking_ensemble.fit(X_final, y)
            
            accuracy = self.stacking_ensemble.score(X_final, y)
            print(f"✅ Stacking Ensemble trained - Accuracy (Train): {accuracy:.3f}")
            return True
            
        except Exception as e:
            print(f"❌ Stacking training failed: {e}")
            return False

    # === متدهای Q-Learning ===
    def discretize_state(self, row, ensemble_signal, confidence):
        """تبدیل حالت به فضای گسسته برای Q-Learning"""
        # اطمینان از دسترسی به مقادیر
        rsi = row.get('rsi_14', 50) if hasattr(row, 'get') else row['rsi_14']
        macd = row.get('macd', 0) if hasattr(row, 'get') else row['macd']
        macd_signal = row.get('macd_signal', 0) if hasattr(row, 'get') else row['macd_signal']
        close = row.get('close', 0) if hasattr(row, 'get') else row['close']
        sma_20 = row.get('sma_20', 0) if hasattr(row, 'get') else row['sma_20']
        dxy_corr = row.get('corr_DXY', 0) if hasattr(row, 'get') else 0
        
        # حالت‌های تکنیکال
        rsi_state = 0 if rsi < 35 else 1 if rsi > 65 else 2
        macd_state = 0 if (macd < 0 and macd < macd_signal) else 1 if (macd > 0 and macd > macd_signal) else 2
        trend_state = 0 if close < sma_20 else 1
        
        # حالت‌های میان‌بازاری
        market_corr_state = 0 if dxy_corr < -0.6 else 1 if dxy_corr > 0.6 else 2
        
        # حالت Ensemble
        ensemble_state = 0 if ensemble_signal == "BUY" else 1 if ensemble_signal == "SELL" else 2
        confidence_state = 0 if confidence < 0.6 else 1 if confidence < 0.75 else 2
        
        return f"{rsi_state}_{macd_state}_{trend_state}_{market_corr_state}_{ensemble_state}_{confidence_state}"

    def q_learning_decision(self, state, ensemble_signal, exploration=True):
        """تصمیم‌گیری نهایی با Q-Learning"""
        if state not in self.q_table:
            # مقادیر اولیه با بایاس کم به سمت HOLD
            self.q_table[state] = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.01} 
        
        # اکتشاف (Exploration)
        if exploration and random.random() < self.epsilon:
            action = random.choice(['BUY', 'SELL', 'HOLD'])
        else:
            # بهره‌برداری (Exploitation)
            q_values = self.q_table[state].copy()
            
            # تقویت سیگنال Ensemble برای بهره‌برداری هدفمند
            if ensemble_signal == "BUY":
                q_values['BUY'] += 0.05
            elif ensemble_signal == "SELL":
                q_values['SELL'] += 0.05
                
            action = max(q_values, key=q_values.get)
        
        # کاهش epsilon با حداقل
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
        return action

    def update_q_learning(self, state, action, reward, next_state, ensemble_confidence):
        """آپدیت Q-Table با پاداش وزندار"""
        # اطمینان از وجود حالت‌ها
        if state not in self.q_table:
            self.q_table[state] = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
        if next_state not in self.q_table:
            self.q_table[next_state] = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
        
        current_q = self.q_table[state].get(action, 0.0)
        max_next_q = max(self.q_table[next_state].values())
        
        # پاداش وزندار بر اساس اطمینان Ensemble
        weighted_reward = reward * ensemble_confidence
        
        new_q = current_q + self.learning_rate * (
            weighted_reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state][action] = new_q
        
    def calculate_trade_reward(self, entry_price, exit_price, action, holding_period_min, spread_cost):
        """محاسبه پاداش هوشمند برای معامله (با در نظر گرفتن Spread)"""
        if action == 'HOLD':
            return -0.01  # جریمه کوچک برای HOLD
        
        # محاسبه سود/زیان نسبی
        if action == 'BUY':
            pnl_ratio = (exit_price - entry_price) / entry_price
        else:  # SELL
            pnl_ratio = (entry_price - exit_price) / entry_price

        # کسر هزینه تراکنش (Spread)
        spread_cost_ratio = spread_cost / entry_price
        net_pnl_ratio = pnl_ratio - spread_cost_ratio
        
        # پاداش مبتنی بر سوددهی (با بزرگنمایی مناسب)
        base_reward = net_pnl_ratio * 1000  # افزایش ضریب برای تأثیر بیشتر
        
        # جریمه زمان نگهداری: ترجیح به معاملات سریع
        time_penalty = holding_period_min * 0.001
        
        final_reward = base_reward - time_penalty
        return final_reward


    # === متدهای مدیریت موقعیت و اجرا ===
    def calculate_dynamic_position_size(self, balance, risk_score, atr, confidence):
        """محاسبه سایز پوزیشن داینامیک"""
        base_risk_percent = 0.015  # 1.5% ریسک پایه
        
        # تنظیم بر اساس اطمینان و ریسک بازار
        confidence_factor = 0.5 + (confidence * 0.5)  # 0.5 تا 1.0
        risk_factor = 1.0 - (risk_score * 0.5)  # 0.5 تا 1.0
        
        adjusted_risk = base_risk_percent * confidence_factor * risk_factor
        risk_amount = balance * adjusted_risk
        
        # محاسبه فاصله SL بر حسب قیمت
        atr_distance = atr * self.atr_multiplier
        
        # سایز پوزیشن (برای XAUUSD، هر لات = 100 اونس)
        # Risk Amount = Position Size (lots) * ATR Distance * 100
        position_size = risk_amount / (atr_distance * 100)
        
        # محدودیت‌های سایز
        return max(0.01, min(position_size, 5.0))

    def calculate_adaptive_sl_tp(self, action, entry_price, atr, volatility, market_regime):
        """محاسبه هوشمند حد ضرر و حد سود"""
        # تنظیم ATR بر اساس رژیم بازار
        if market_regime == "HIGH_VOL":
            atr_multiplier = self.atr_multiplier * 1.1
        else:
            atr_multiplier = self.atr_multiplier
        
        atr_distance = atr * atr_multiplier
        
        # دریافت دقت نماد
        symbol_info = mt5.symbol_info(self.primary_symbol)
        digits = symbol_info.digits if symbol_info else 2
        
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
                print(f"❌ Cannot get tick or symbol info for {self.primary_symbol}")
                return False
            
            entry_price = tick.ask if action == "BUY" else tick.bid
            order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
            
            # محاسبات مدیریت ریسک
            account_info = mt5.account_info()
            if not account_info:
                return False
                
            atr = df['atr'].iloc[-1]
            volatility = df['volatility_20'].iloc[-1]
            avg_volatility = df['volatility_20'].mean()
            market_regime = "HIGH_VOL" if volatility > avg_volatility else "LOW_VOL"
            current_spread = tick.ask - tick.bid
            
            # محاسبه سایز و SL/TP
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
                "volume": round(position_size, 2),
                "type": order_type,
                "price": entry_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 20,
                "magic": 202501,
                "comment": f"QL_{action}_C{confidence:.2f}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result is None:
                print(f"❌ Order send returned None")
                return False
            
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
                    'state_at_entry': current_state,
                    'spread_at_entry': current_spread,
                    'timestamp': datetime.now()
                }
                self.trade_history.append(trade_record)
                self.open_positions[result.order] = trade_record
                
                print(f"✅ ORDER EXECUTED:")
                print(f"    {action} {self.primary_symbol} at {entry_price:.2f}")
                print(f"    Size: {position_size:.3f}, SL: {sl_price:.2f}, TP: {tp_price:.2f}")
                return True
            else:
                print(f"❌ Order failed. Retcode: {result.retcode}, Comment: {result.comment}")
                return False
                
        except Exception as e:
            print(f"❌ Order execution error: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def close_position(self, ticket):
        """بستن یک موقعیت باز"""
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position or len(position) == 0:
                return False
            
            position = position[0]
            
            # سفارش بستن مخالف
            close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            close_price = mt5.symbol_info_tick(self.primary_symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(self.primary_symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.primary_symbol,
                "volume": position.volume,
                "type": close_type,
                "position": ticket,
                "price": close_price,
                "deviation": 20,
                "magic": 202501,
                "comment": "Close position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
            
        except Exception as e:
            print(f"❌ Error closing position: {e}")
            return False

    def close_and_update_q_learning(self, current_df, current_state, ensemble_confidence):
        """بررسی موقعیت‌های باز و به‌روزرسانی Q-Table"""
        positions = mt5.positions_get(symbol=self.primary_symbol)
        
        if positions is None:
            positions = []
        
        position_tickets = {p.ticket for p in positions}
        closed_tickets = []
        
        for ticket, trade in list(self.open_positions.items()):
            is_open = ticket in position_tickets
            
            # محاسبه زمان نگهداری
            time_diff = (datetime.now() - trade['timestamp']).total_seconds()
            holding_period_min = time_diff / 60
            
            # شرایط بستن: بسته شده در MT5 یا زمان زیاد
            should_close = not is_open or holding_period_min > 45
            
            if should_close:
                closed_tickets.append(ticket)
                
                # اگر هنوز باز است، ببندیم
                if is_open:
                    self.close_position(ticket)
                
                # قیمت خروج
                exit_price = current_df['close'].iloc[-1]
                
                # محاسبه پاداش
                reward = self.calculate_trade_reward(
                    entry_price=trade['entry_price'],
                    exit_price=exit_price,
                    action=trade['action'],
                    holding_period_min=holding_period_min,
                    spread_cost=trade['spread_at_entry']
                )
                
                # آپدیت Q-Table
                self.update_q_learning(
                    state=trade['state_at_entry'],
                    action=trade['action'],
                    reward=reward,
                    next_state=current_state,
                    ensemble_confidence=trade['confidence']
                )
                
                pnl = reward / 1000  # تبدیل به درصد تقریبی
                status = "✅ Profit" if reward > 0 else "❌ Loss"
                print(f"  {status} | Ticket {ticket}, {trade['action']}, Reward: {reward:.4f} ({pnl:.2f}%)")

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
        
        # دریافت همبستگی DXY
        dxy_corr_col = 'corr_DXY'
        dxy_corr = abs(df[dxy_corr_col].iloc[-1]) if dxy_corr_col in df.columns else 0
        
        # محاسبه ریسک
        vol_ratio = current_vol / (avg_vol + 1e-10)
        risk_score = (
            vol_ratio * 0.25 +
            min(volume_anomaly, 2) * 0.20 +
            dxy_corr * 0.25 +
            (self.daily_loss / (self.daily_risk_limit + 1e-10)) * 0.30
        )
        
        return min(risk_score, 1.0)

    def get_institutional_signal(self, df):
        """سیگنال‌دهی نهایی Institutional"""
        default_return = ("HOLD", 0.5, 0.5, "0_0_0_0_0_0")
        
        if self.stacking_ensemble is None or not self.is_fitted or len(df) < 50:
            return default_return
        
        try:
            # ستون‌های ویژگی
            exclude_cols = ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'real_volume', 'spread']
            feature_columns = [col for col in df.columns if col not in exclude_cols]
            
            if len(feature_columns) == 0:
                return default_return
            
            # آخرین کندل
            current_features = df[feature_columns].iloc[-1:].values
            
            if np.isnan(current_features).any():
                return default_return
            
            # تبدیل ویژگی‌ها
            X_selected = self.feature_selector.transform(current_features)
            X_scaled = self.scaler.transform(X_selected)
            
            # پیش‌بینی Stacking Ensemble
            ensemble_proba = self.stacking_ensemble.predict_proba(X_scaled)[0]
            ensemble_confidence = float(np.max(ensemble_proba))
            ensemble_signal = "BUY" if ensemble_proba[1] > ensemble_proba[0] else "SELL"
            
            # Q-Learning Decision
            current_row = df.iloc[-1]
            current_state = self.discretize_state(current_row, ensemble_signal, ensemble_confidence)
            final_signal = self.q_learning_decision(current_state, ensemble_signal, exploration=True)
            
            # محاسبه ریسک
            risk_score = self.calculate_institutional_risk(df)
            
            return final_signal, ensemble_confidence, risk_score, current_state
            
        except Exception as e:
            print(f"❌ Institutional signal error: {e}")
            import traceback
            traceback.print_exc()
            return default_return

    # === متد اصلی اجرا ===
    def timeframe_to_seconds(self, timeframe):
        """تبدیل تایم‌فریم به ثانیه"""
        if timeframe == mt5.TIMEFRAME_M1:
            return 60
        elif timeframe == mt5.TIMEFRAME_M5:
            return 300
        elif timeframe == mt5.TIMEFRAME_M15:
            return 900
        elif timeframe == mt5.TIMEFRAME_M30:
            return 1800
        elif timeframe == mt5.TIMEFRAME_H1:
            return 3600
        return 300  # Default M5

    def run_complete_institutional_system(self, cycles=12):
        """اجرای سیستم Institutional کامل"""
        print("🚀 QUANTUM INSTITUTIONAL AI - FULL SYSTEM ACTIVATED")
        print("=" * 60)
        
        if not self.connect_mt5():
            print("🛑 MT5 connection failed. System stopped.")
            return
        
        # ۱. مرحله آموزش اولیه
        print("\n📚 Collecting data for initial training...")
        df = self.get_intermarket_features(1000)
        
        if df is None or len(df) < 150:
            print("❌ No market data available for initial training")
            mt5.shutdown()
            return
        
        print(f"✅ Loaded {len(df)} bars of data")
        
        # آموزش مدل‌های پیشرفته
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
                print(f"❌ Cycle {cycle+1}: Insufficient data. Skipping...")
                time.sleep(20)
                continue
            
            # ب. به‌روزرسانی Q-Learning
            current_state_temp = "0_0_0_0_0_0"
            self.close_and_update_q_learning(df, current_state_temp, 0.7)
            
            # ج. سیگنال Institutional
            signal, confidence, risk_score, current_state = self.get_institutional_signal(df)
            
            print(f"\n🏛️ CYCLE {cycle+1}/{cycles} [{datetime.now().strftime('%H:%M:%S')}]")
            print(f"  Decision: {signal} | State: {current_state}")
            print(f"  Confidence: {confidence:.3f} | Risk: {risk_score:.2f} | Epsilon: {self.epsilon:.3f}")
            
            # د. اجرای معامله
            if signal in ["BUY", "SELL"]:
                if not self.open_positions:
                    self.send_institutional_order(signal, confidence, risk_score, current_state, df)
                else:
                    print(f"  ⏸️  Holding existing position")
            else:
                print(f"  🔄 No trade signal (HOLD)")
            
            # انتظار برای کندل بعدی
            if cycle < cycles - 1:
                sleep_time = max(10, self.timeframe_to_seconds(self.timeframe) - 5)
                print(f"  ⏳ Waiting {sleep_time}s for next candle...")
                time.sleep(sleep_time)

        # ۳. خلاصه عملکرد
        print(f"\n" + "=" * 60)
        print(f"📊 SESSION SUMMARY")
        print(f"  Total Trades: {len(self.trade_history)}")
        print(f"  Open Positions: {len(self.open_positions)}")
        print(f"  Q-Learning States: {len(self.q_table)}")
        print(f"  Final Epsilon: {self.epsilon:.3f}")
        
        if len(self.trade_history) > 0:
            wins = sum(1 for t in self.trade_history if t.get('profit', 0) > 0)
            win_rate = wins / len(self.trade_history) * 100
            print(f"  Win Rate: {win_rate:.1f}%")
        
        mt5.shutdown()
        print("✅ Institutional trading session completed!")


# اجرای سیستم
if __name__ == "__main__":
    institution = QuantumInstitutionalAI()
    institution.run_complete_institutional_system(cycles=20)
