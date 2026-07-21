import { getBacktestResults, getBacktestTrades } from '@/lib/api';

export async function GET(request) {
  const results = await getBacktestResults();
  const trades = await getBacktestTrades();
  
  return Response.json({
    results,
    trades,
    tradeCount: trades.length
  });
}