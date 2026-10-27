# Binance RSI Trading Bot

An automated Python cryptocurrency trading bot designed for Binance Spot and Testnet markets. It implements a momentum-based mean-reversion strategy utilizing the Relative Strength Index (RSI) across multiple cryptocurrency pairs concurrently.

---

## Strategy Overview: RSI 30 / RSI 60
* **Technical Indicator:** 7-period RSI (`RSI_PERIOD = 7`) calculated dynamically using 1-minute historical klines (candles).
* **Buy Entry Trigger:** Continuously scans a basket of popular coin pairs and executes/simulates a buy order when an asset's RSI drops to **$\le 30$** (oversold condition).
* **Take-Profit Exit Target:** Actively tracks open positions and sells/exits when the RSI recovers to **$\ge 60$** to lock in profits.
* **Parallel Multi-Symbol Scanning:** Evaluates multiple crypto assets simultaneously via concurrent worker threads to minimize idle time and catch market bounces across different coins.
* **Smart Session Target:** Runs continuously until a strict performance milestone is achieved—shutting down automatically only when **$\ge 15$ trades** are completed with an overall win rate of **$\ge 80\%$**.

---

## Features
* **Dual Execution Modes:** Fully supports both paper simulation mode (`--paper`) and live trading connectivity via Binance APIs.
* **Testnet Ready:** Defaults safely to Binance Testnet endpoints for risk-free testing and strategy tuning.
* **Real-Time Performance Tracking:** Live terminal output displaying running statistics including settled trades, win/loss ratios, and win-rate percentages.
* **Lightweight & Fast:** Built with simple dependencies (`requests`) making it compatible with Linux, Termux, and cloud environments.

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/kipkorirchirchir800-hash/Dtrader.git](https://github.com/kipkorirchirchir800-hash/Dtrader.git)
   cd Dtrader
