import { NextResponse } from 'next/server';

export async function GET() {
  try {
    // Fetch from live_stream.py or call Kite API directly
    const response = await fetch('http://localhost:8000/api/live-quote');
    const data = await response.json();
    
    return NextResponse.json({
      data,
      timestamp: new Date()
    });
  } catch (error) {
    return NextResponse.json({ 
      error: 'Failed to fetch live data',
      status: 500 
    });
  }
}