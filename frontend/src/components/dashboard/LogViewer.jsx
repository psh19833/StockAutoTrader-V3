import { useEffect, useState } from "react";
import { fetchLogs, fetchLogDates } from "../../api/dashboardApi";

const CATS = ["system", "trading", "scanner", "quant", "risk", "websocket", "telegram", "emergency"];
const CAT_LABELS = { system: "시스템", trading: "매매", scanner: "스캐너", quant: "퀀트", risk: "리스크", websocket: "실시간", telegram: "텔레그램", emergency: "비상정지" };

export default function LogViewer() {
  const [dates, setDates] = useState([]);
  const [date, setDate] = useState("");
  const [cat, setCat] = useState("system");
  const [lines, setLines] = useState([]);
  const [availCats, setAvailCats] = useState([]);

  useEffect(() => {
    fetchLogDates().then(d => { setDates(d); if (d.length) setDate(d[0]); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (date) fetchLogs(date, cat).then(d => {
      setLines(d.lines || []);
      setAvailCats(d.available_categories || []);
    }).catch(() => setLines([]));
  }, [date, cat]);

  return (
    <div className="card" style={{ gridColumn: "1 / -1" }}>
      <h3>운영 로그</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <select value={date} onChange={e => setDate(e.target.value)}
          style={{ background: "#21262d", color: "#c9d1d9", border: "1px solid #30363d", padding: 4, borderRadius: 4 }}>
          {dates.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        {CATS.map(c => (
          <button key={c} onClick={() => setCat(c)}
            style={{
              background: cat === c ? "#1f6feb" : "#21262d", color: "#c9d1d9",
              border: "1px solid #30363d", padding: "4px 10px", borderRadius: 4, cursor: "pointer",
              opacity: availCats.length && !availCats.includes(c) ? 0.4 : 1,
            }}>{CAT_LABELS[c]}</button>
        ))}
      </div>
      <pre style={{
        background: "#0d1117", color: "#c9d1d9", padding: 12, borderRadius: 6,
        maxHeight: 300, overflow: "auto", fontSize: 12, margin: 0,
        fontFamily: "Consolas, monospace", whiteSpace: "pre-wrap", wordBreak: "break-all"
      }}>
        {lines.length ? lines.join("\n") : "(로그 데이터 없음)"}
      </pre>
    </div>
  );
}
