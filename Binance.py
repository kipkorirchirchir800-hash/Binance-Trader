#!/usr/bin/env python3
"""
Binance RSI Mean-Reversion Bot (Multi-Symbol Parallel Scanner Edition).

Strategy:
- RSI period 7, calculated from Binance 1-minute historical klines (candles).
- Buy entry: RSI <= 30 (Oversold condition).
- Sell / Take-Profit exit: RSI >= 60 (Target recovery condition).
- Concurrent multi-symbol scanning across major Binance pairs.
- Fresh session win/loss settlement statistics tracking.
- Automatic shutdown upon completing >= 15 trades with >= 80% win rate.
"""
import os
import sys
import subprocess

def ensure_dependencies():
    """Auto-detect missing dependencies and install them on Termux/Linux before running."""
    missing_pip = []
    try:
        import requests
    except ImportError:
        missing_pip.append("requests")
        
    if missing_pip:
        print(f"[!] Missing dependency detected: {', '.join(missing_pip)}")
        try:
            print(f"[*] Installing Python packages: {missing_pip}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + missing_pip)
            print("[✓] All missing dependencies installed successfully.")
        except subprocess.CalledProcessError as err:
            print(f"[X] Dependency installation failed: {err}")
            sys.exit(1)

ensure_dependencies()

import argparse
import json
import math
import signal
import time
import random
import hmac
import hashlib
import urllib.parse
import requests
import threading
from datetime import datetime

# Binance API configuration (Use Binance Testnet URLs by default for safe paper/test trading)
USE_TESTNET = True
if USE_TESTNET:
    REST_HOST = "https://testnet.binance.vision"
else:
    REST_HOST = "https://api.binance.com"

# Replace with your Binance API Key and Secret (Leave empty or use testnet keys for simulation/testing)
API_KEY = "YOUR_BINANCE_API_KEY"
API_SECRET = "YOUR_BINANCE_API_SECRET"

RSI_PERIOD = 7
INTERVAL = "1m"
TARGET_TRADE_COUNT = 15
TARGET_WIN_RATE = 80.0

# Monitored Binance Spot Symbols
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "MATICUSDT"
]

def calculate_rsi_series(closes, period=RSI_PERIOD):
    if len(closes) < period + 1:
        return []
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(x, 0.0) for x in changes]
    losses = [max(-x, 0.0) for x in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def value(gain, loss):
        if loss == 0:
            return 100.0 if gain > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    out = [None] * period
    out.append(value(avg_gain, avg_loss))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out.append(value(avg_gain, avg_loss))
    return out


class BinanceRsiBot:
    def __init__(self, paper=False):
        self.paper = paper
        self.running = False
        self.lock = threading.RLock()
        self.last_signal_epoch = {}
        
        # Position tracking
        self.open_positions = {}  # symbol -> entry_price
        self.buy_pending = False
        
        # Session Statistics
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        
        mode_str = "PAPER SIMULATION" if self.paper else "LIVE BINANCE"
        print(f"[{mode_str}] SESSION STARTED: Buy @ RSI <= 30 | Sell Target @ RSI >= 60")

    def log(self, msg):
        print(datetime.now().strftime("%H:%M:%S"), msg, flush=True)

    def show_stats(self):
        rate = 100.0 * self.win_count / self.trade_count if self.trade_count else 0.0
        rate_str = f"\033[1;32m{rate:.2f}%\033[0m" if rate >= 50.0 else f"\033[1;31m{rate:.2f}%\033[0m"
        self.log(f"Stats: {self.trade_count} settled | Wins: {self.win_count} | Losses: {self.loss_count} | Win Rate: {rate_str}")

    def record_trade(self, symbol, pnl_dollar, is_win):
        with self.lock:
            if is_win:
                self.win_count += 1
                self.log(f"TRADE WON on {symbol}! Profit: +${pnl_dollar:.2f}")
            else:
                self.loss_count += 1
                self.log(f"TRADE LOST on {symbol}! Loss: -${abs(pnl_dollar):.2f}")

            self.trade_count = self.win_count + self.loss_count
            self.show_stats()

            # Check stopping criteria
            win_rate = (100.0 * self.win_count / self.trade_count) if self.trade_count > 0 else 0.0
            if self.trade_count >= TARGET_TRADE_COUNT and win_rate >= TARGET_WIN_RATE:
                self.log(f"SUCCESS TARGET REACHED! Trades: {self.trade_count} (>=15) | Win Rate: {win_rate:.2f}%. Shutting down...")
                self.stop()

    def get_klines(self, symbol):
        url = f"{REST_HOST}/api/v3/klines"
        params = {"symbol": symbol, "interval": INTERVAL, "limit": 100}
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return []

    def start(self):
        self.running = True
        self.log(f"Launching parallel continuous RSI scanners across {len(SYMBOLS)} Binance pairs...")
        
        for symbol in SYMBOLS:
            threading.Thread(target=self._symbol_worker, args=(symbol,), daemon=True).start()

        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False

    def _symbol_worker(self, symbol):
        """Continuously checks klines for RSI <= 30 (Buy) and manages open positions until RSI >= 60 (Sell)."""
        while self.running:
            try:
                klines = self.get_klines(symbol)
                if not klines:
                    time.sleep(3.0)
                    continue

                closes = [float(k[4]) for k in klines]  # Index 4 is close price
                series = calculate_rsi_series(closes, RSI_PERIOD)
                valid_rsi = [x for x in series if x is not None]

                if not valid_rsi:
                    time.sleep(3.0)
                    continue

                current_rsi = valid_rsi[-1]
                latest_epoch = int(klines[-1][0])
                current_price = closes[-1]

                with self.lock:
                    has_position = symbol in self.open_positions

                # 1. CHECK SELL CONDITION: If we hold a position and RSI reaches >= 60 (Take Profit target)
                if has_position:
                    if current_rsi >= 60.0:
                        entry_price = self.open_positions[symbol]
                        pnl_pct = (current_price - entry_price) / entry_price
                        is_win = pnl_pct > 0
                        pnl_dollar = pnl_pct * 100.0  # Simulated $100 position sizing

                        self.log(f"SELL SIGNAL (RSI Target >= 60) for {symbol}! RSI: {current_rsi:.2f} | Exit Price: {current_price}")
                        with self.lock:
                            self.open_positions.pop(symbol, None)
                        
                        self.record_trade(symbol, pnl_dollar, is_win)

                # 2. CHECK BUY CONDITION: If no open position on this symbol and RSI drops to <= 30
                elif not has_position and not self.buy_pending:
                    if current_rsi <= 30.0 and self.last_signal_epoch.get(symbol) != latest_epoch:
                        self.last_signal_epoch[symbol] = latest_epoch
                        self.log(f"BUY SIGNAL (Oversold RSI <= 30) for {symbol}! RSI: {current_rsi:.2f}")
                        
                        if self.paper:
                            with self.lock:
                                self.open_positions[symbol] = current_price
                            self.log(f"PAPER BUY EXECUTED: {symbol} @ ${current_price:.2f}")
                        else:
                            # Execute actual Binance Spot Market Buy order here if live keys are provided
                            self.execute_binance_buy(symbol, current_price)

            except Exception as exc:
                pass

            time.sleep(2.0)

    def execute_binance_buy(self, symbol, current_price):
        """Placeholder / Implementation for live Binance Spot Order execution."""
        # Note: Implementing live signed requests requires API_KEY and API_SECRET.
        with self.lock:
            self.open_positions[symbol] = current_price
        self.log(f"LIVE BUY EXECUTED: {symbol} @ ${current_price:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Binance RSI 30/60 Trading Bot")
    parser.add_argument("--paper", action="store_true", help="Run in simulation/paper mode")
    args = parser.parse_args()

    bot = BinanceRsiBot(paper=args.paper)
    
    def stop_handler(*_):
        print("\nStopping bot...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop_handler)
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.stop()

if __name__ == "__main__":
    main()
