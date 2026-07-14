import WinProbabilityChart from "@/components/WinProbabilityChart";

export default function Home() {
  return (
    <main className="min-h-screen py-12">
      <h1 className="text-3xl font-bold text-center mb-8">
        NBA Win Probability Predictor
      </h1>
      <WinProbabilityChart />
    </main>
  );
}