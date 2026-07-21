import fs from 'fs';
import path from 'path';

export async function getBacktestResults() {
  try {
    const backtest_dir = path.join(process.cwd(), '../backtest_results');
    
    // Find latest results file
    const files = fs.readdirSync(backtest_dir).filter(f => f.endsWith('_results.json'));
    if (files.length === 0) return null;
    
    const latest = files.sort().pop();
    const data = JSON.parse(fs.readFileSync(path.join(backtest_dir, latest), 'utf8'));
    return data;
  } catch (error) {
    console.error('Error reading backtest results:', error);
    return null;
  }
}

export async function getBacktestTrades() {
  try {
    const backtest_dir = path.join(process.cwd(), '../backtest_results');
    
    // Find latest trades file
    const files = fs.readdirSync(backtest_dir).filter(f => f.endsWith('_trades.csv'));
    if (files.length === 0) return [];
    
    const latest = files.sort().pop();
    const csv = fs.readFileSync(path.join(backtest_dir, latest), 'utf8');
    
    // Parse CSV
    const lines = csv.trim().split('\n');
    const headers = lines[0].split(',');
    const trades = lines.slice(1).map(line => {
      const values = line.split(',');
      const trade = {};
      headers.forEach((header, i) => {
        trade[header.trim()] = values[i]?.trim();
      });
      return trade;
    });
    
    return trades;
  } catch (error) {
    console.error('Error reading backtest trades:', error);
    return [];
  }
}