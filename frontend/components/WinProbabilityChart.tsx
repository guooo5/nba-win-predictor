"use client";

import { useState, useEffect, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

type GameEvent = {
  seconds_elapsed: number;
  seconds_remaining: number;
  score_diff: number;
  score_home: number;
  score_away: number;
  description: string;
  win_probability: number;
  period: number;
  clock: string;
};

type ReplayData = {
    game_id: string;
    home_team: string;
    away_team: string;
    events: GameEvent[];
  };

//
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"; 

export default function WinProbabilityChart() {
  const [gameIdInput, setGameIdInput] = useState("0022300061");
  const [data, setData] = useState<ReplayData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  async function loadGame(gameId: string) {
    setLoading(true);
    setError(null);
    setIsPlaying(false);
    setData(null);

    try {
      const res = await fetch(`${API_BASE}/replay/${gameId}`);
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || "Failed to load game");
      }
      const json: ReplayData = await res.json();
      setData(json);
      setCurrentIndex(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadGame(gameIdInput);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isPlaying || !data) return;
    const interval = setInterval(() => {
      setCurrentIndex((prev) => {
        if (prev >= data.events.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 50);
    return () => clearInterval(interval);
  }, [isPlaying, data]);

  const visibleEvents = useMemo(() => {
    if (!data) return [];
    return data.events.slice(0, currentIndex + 1).map((e) => ({
      ...e,
      winProbabilityPct: e.win_probability * 100,
    }));
  }, [data, currentIndex]);

  if (!data && loading) {
    return <div className="text-center p-8 text-gray-400">Loading game...</div>;
  }

  const current = data?.events[currentIndex];

  const history = data ? data.events
        .slice(Math.max(0, currentIndex - 5), currentIndex)
        .reverse()
    : [];

  return (
    <div className="w-full max-w-5xl mx-auto p-6">
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={gameIdInput}
          onChange={(e) => setGameIdInput(e.target.value)}
          placeholder="Enter a game ID, e.g. 0022300061"
          className="flex-1 border rounded px-3 py-2 text-gray-900 bg-white"
        />
        <button
          onClick={() => loadGame(gameIdInput)}
          disabled={loading}
          className="px-4 py-2 bg-gray-900 text-white rounded disabled:opacity-50"
          style={{ backgroundColor: "#b5c7eb"}}
        >
          {loading ? "Loading..." : "Load game"}
        </button>
      </div>

      {error && <div className="text-red-600 text-sm mb-4">Error: {error}</div>}

      {data && current && (
        <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
          <div>
            <div className="bg-gray-50 rounded-xl p-5 mb-4">
              <div className="flex justify-between items-center">
                <div className="text-center flex-1">
                  <div className="text-xs text-gray-500">{data.home_team}</div>
                  <div className="font-mono text-3xl font-medium text-gray-900">
                    {current.score_home}
                  </div>
                </div>
                <div className="font-mono text-sm text-gray-400">
                  Q{current.period} &middot; {current.clock}
                </div>
                <div className="text-center flex-1">
                  <div className="text-xs text-gray-500">{data.away_team}</div>
                  <div className="font-mono text-3xl font-medium text-gray-900">
                    {current.score_away}
                  </div>
                </div>
              </div>
              <div className="text-center mt-3 text-sm text-gray-600">
                Win probability{" "}
                <span className="font-medium text-gray-900">
                  {(current.win_probability * 100).toFixed(1)}%
                </span>{" "}
                {data.home_team}
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-4">
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={visibleEvents}>
                  <CartesianGrid vertical={false} stroke="#e5e7eb" />
                  <XAxis
                    dataKey="seconds_elapsed"
                    hide
                    domain={[0, data.events[data.events.length - 1].seconds_elapsed]}
                    type="number"
                  />
                  <YAxis domain={[0, 100]} hide />
                  <Line
                    type="monotone"
                    dataKey="winProbabilityPct"
                    stroke="#b5c7eb"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex justify-between text-xs text-gray-400 font-mono px-1">
                <span>Q1</span>
                <span>Q2</span>
                <span>Q3</span>
                <span>Q4</span>
              </div>
            </div>

            <div className="flex items-center gap-4 mt-4">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="px-4 py-2 bg-gray-900 text-white rounded"
                style={{ backgroundColor: "#b5c7eb" }}
              >
                {isPlaying ? "Pause" : "Play"}
              </button>
              <input
                type="range"
                min={0}
                max={data.events.length - 1}
                value={currentIndex}
                onChange={(e) => {
                  setIsPlaying(false);
                  setCurrentIndex(Number(e.target.value));
                }}
                className="flex-1"
                style={{accentColor: "#b5c7eb"}}
              />
            </div>
          </div>

          <div className="bg-gray-50 rounded-xl p-5">
            <div className="border-l-[3px] border-[#b5c7eb] pl-3 mb-4">
              <div className="font-mono text-xs text-gray-400">
                Q{current.period} &middot; {current.clock}
              </div>
              <div className="text-[15px] font-medium mt-0.5 text-gray-900">
                {current.description}
              </div>
            </div>

            <div className="relative pl-4 border-l border-gray-200">
              {history.map((event, i) => (
                <div
                  key={event.seconds_elapsed + "-" + i}
                  className="mb-3"
                  style={{ opacity: 1 - i * 0.15 }}
                >
                  <div className="font-mono text-[11px] text-gray-400">
                    {event.clock}
                  </div>
                  <div className="text-[13px] text-gray-700">
                    {event.description}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}