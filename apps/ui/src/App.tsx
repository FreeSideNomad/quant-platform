import { useEffect, useState } from "react";

interface HealthResponse {
  status: string;
  role: string;
  version: string;
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 32, maxWidth: 720 }}>
      <h1>Quant Platform</h1>
      <p>Skeleton (M1). Real UI ships in M5.</p>
      {error && <pre style={{ color: "crimson" }}>{error}</pre>}
      {health && (
        <pre style={{ background: "#f4f4f4", padding: 16 }}>
          {JSON.stringify(health, null, 2)}
        </pre>
      )}
    </main>
  );
}
